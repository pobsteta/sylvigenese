"""Fichiers Parquet : un fichier, ou un dossier de fichiers, partitionné ou non (spec §9).

Partition `year=AAAA`, convention Hive standard (ADR 0002, précisions du 24/11/2026) :
l'année n'est que dans le nom du dossier, comme l'écrit
`pyarrow.dataset.write_dataset(partitioning_flavor="hive")`. Le validateur reconstitue la
colonne `year` depuis le nom du dossier avant le contrôle. Un fichier qui contient aussi une
colonne `year` est refusé (choix de la mission 009) : l'année aurait deux sources, qui
pourraient diverger.
"""
import re
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from . import tables
from .report import Findings

PARTITION = re.compile(r"^year=(\d{4})$")


def list_files(path):
    path = Path(path)
    if path.is_dir():
        return sorted(p for p in path.rglob("*.parquet") if p.is_file())
    return [path]


def read(path):
    """Table Arrow d'un seul fichier, sans deviner de colonne de partition."""
    try:
        return pq.ParquetFile(path).read()
    except (pa.ArrowException, OSError) as exc:
        raise ValueError(f"fichier Parquet illisible ({exc.__class__.__name__})") from exc


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
            table = read(file)
        except ValueError as exc:
            findings.error(str(exc))
            results.append((file, findings))
            continue
        if options.get("partition") == "year":
            table = add_partition_year(file, table, findings)
        tables.check_table(schema, table, findings)
        results.append((file, findings))
    return results


def add_partition_year(file, table, findings):
    """Table complétée par la colonne `year` lue dans le dossier `year=AAAA`."""
    match = PARTITION.match(Path(file).parent.name)
    if not match:
        findings.error(f"partition attendue : le fichier doit être dans un dossier year=AAAA, "
                       f"trouvé {Path(file).parent.name}")
        return table
    year = int(match.group(1))
    if "year" in table.column_names:
        findings.error("colonne year présente dans le fichier : en convention Hive, l'année "
                       f"n'est que dans le nom du dossier year={year}")
        table = table.drop(["year"])
    return table.append_column("year", pa.array([year] * table.num_rows, type=pa.int64()))
