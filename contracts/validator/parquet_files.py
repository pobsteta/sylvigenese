"""Fichiers Parquet : un fichier, ou un dossier de fichiers, partitionné ou non (spec §9).

Partition `year=AAAA` : le dossier porte l'année, et la colonne `year` du fichier doit
valoir cette année sur toutes ses lignes.
"""
import re
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
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
        good = tables.check_table(schema, table, findings)
        if options.get("partition") == "year":
            check_partition(file, table, good, findings)
        results.append((file, findings))
    return results


def check_partition(file, table, good, findings):
    match = PARTITION.match(Path(file).parent.name)
    if not match:
        findings.error(f"partition attendue : le fichier doit être dans un dossier year=AAAA, "
                       f"trouvé {Path(file).parent.name}")
        return
    if "year" in good and table.num_rows:
        year = int(match.group(1))
        wrong = pc.fill_null(pc.not_equal(table["year"], year), True)
        n = pc.sum(pc.cast(wrong, pa.int64())).as_py()
        if n:
            findings.error(f"colonne year : {n} valeur(s) différente(s) de l'année de la "
                           f"partition year={year}")
