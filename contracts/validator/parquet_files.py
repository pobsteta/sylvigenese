"""Fichiers Parquet : un fichier, ou un dossier de fichiers, partitionné ou non (spec §9).

Partition `year=AAAA`, convention Hive standard (ADR 0002, précisions du 24/11/2026) :
l'année n'est que dans le nom du dossier, comme l'écrit
`pyarrow.dataset.write_dataset(partitioning_flavor="hive")`. Le validateur reconstitue la
colonne `year` depuis le nom du dossier avant le contrôle. Un fichier qui contient aussi une
colonne `year` est refusé (choix de la mission 009) : l'année aurait deux sources, qui
pourraient diverger.

Lecture par lots (mission 065) : un fichier n'est jamais chargé entier. `FileSource` rend ses
lots de `tables.BATCH_ROWS` lignes au plus (`ParquetFile.iter_batches`, un groupe de lignes
à la fois), colonne `year` de la
partition ajoutée à chaque lot ; un dossier partitionné est lu fichier par fichier. Une erreur
de lecture, même au dernier lot, rend le fichier illisible, avec le seul message de lecture.
"""
import re
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from . import tables
from .report import Findings, Unreadable

PARTITION = re.compile(r"^year=(\d{4})$")


def list_files(path):
    path = Path(path)
    if path.is_dir():
        return sorted(p for p in path.rglob("*.parquet") if p.is_file())
    return [path]


class FileSource:
    """Lots d'un fichier Parquet, relisibles, avec la colonne `year` de la partition s'il y a lieu."""

    def __init__(self, path):
        try:
            self.file = pq.ParquetFile(path)
            arrow_schema = self.file.schema_arrow
            self.num_rows = self.file.metadata.num_rows
        except (pa.ArrowException, OSError) as exc:
            raise Unreadable(_unreadable(exc)) from exc
        self.file_columns = list(arrow_schema.names)
        self.column_names = list(self.file_columns)
        self.types = {f.name: f.type for f in arrow_schema}
        self.year = None

    def set_partition_year(self, year):
        """La colonne `year` vient du dossier ; celle du fichier, s'il y en a une, est écartée."""
        self.year = year
        self.file_columns = [c for c in self.file_columns if c != "year"]
        self.column_names = self.file_columns + ["year"]
        self.types = {**{c: self.types[c] for c in self.file_columns}, "year": pa.int64()}

    def batches(self, columns):
        wanted = [c for c in self.file_columns if c in columns]
        year = self.year is not None and "year" in columns
        try:
            if not wanted:
                for i in range(self.file.metadata.num_row_groups):
                    n = self.file.metadata.row_group(i).num_rows
                    yield pa.RecordBatch.from_arrays([pa.repeat(pa.scalar(self.year, pa.int64()), n)],
                                                     names=["year"])
                return
            # Un groupe de lignes à la fois : iter_batches sur tout le fichier lit plusieurs
            # groupes d'avance (513 Mo alloués par Arrow sur cohorts_init à N = 4 000).
            for group in range(self.file.metadata.num_row_groups):
                for batch in self.file.iter_batches(batch_size=tables.BATCH_ROWS, row_groups=[group],
                                                    columns=wanted, use_pandas_metadata=False):
                    if year:
                        batch = batch.append_column(
                            "year", pa.repeat(pa.scalar(self.year, pa.int64()), batch.num_rows))
                    yield batch
                    del batch
        except (pa.ArrowException, OSError) as exc:
            raise Unreadable(_unreadable(exc)) from exc


def _unreadable(exc):
    return f"fichier Parquet illisible ({exc.__class__.__name__})"


def read(path):
    """Table Arrow d'un seul fichier, sans deviner de colonne de partition (petits fichiers)."""
    try:
        return pq.ParquetFile(path).read()
    except (pa.ArrowException, OSError) as exc:
        raise ValueError(_unreadable(exc)) from exc


def check(path, schema, options):
    """Écarts de `path` (fichier ou dossier) au contrat. Rend une liste (fichier, Findings)."""
    files = list_files(path)
    results = []
    if not files:
        f = Findings()
        f.error("aucun fichier .parquet dans le dossier")
        return [(Path(path), f)]
    for file in files:
        findings = Findings()
        try:
            source = FileSource(file)
            if options.get("partition") == "year":
                add_partition_year(file, source, findings)
            tables.check_source(schema, source, findings)
        except Unreadable as exc:
            # illisible, même au dernier lot : le seul message est celui de la lecture
            findings = Findings()
            findings.error(str(exc))
        results.append((file, findings))
    return results


def add_partition_year(file, source, findings):
    """Source complétée par la colonne `year` lue dans le dossier `year=AAAA`."""
    match = PARTITION.match(Path(file).parent.name)
    if not match:
        findings.error(f"partition attendue : le fichier doit être dans un dossier year=AAAA, "
                       f"trouvé {Path(file).parent.name}")
        return source
    year = int(match.group(1))
    if "year" in source.column_names:
        findings.error("colonne year présente dans le fichier : en convention Hive, l'année "
                       f"n'est que dans le nom du dossier year={year}")
    source.set_partition_year(year)
    return source
