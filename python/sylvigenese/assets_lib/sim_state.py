"""Lecture de `sim/` par `assets` : années retenues, arbres d'une année, cellules et signalements.

Étape du BRIEF codée : §9 (une tuile par année retenue, « pas de 5 ou 10 ans ») et §10
(statut provisoire) ; spec §2 (assets lit `sim/`). Mission 047, plan `docs/plans/m4a-suite-temps.md`
(T1, T3 à T6) ; contrats `simulate.trees`, `simulate.cells`, `simulate.flags`, `simulate.run`,
`config.assets`.

Ce que fait ce module, et ce qu'il refuse (code 2, cause nommée ; aucune valeur par défaut) :
- `assets.year_step` est exigé dès que `sim/` existe (entier >= 1) ;
- `sim/run.json` est exigé, et le bloc `simulate` de config.yml doit lui être égal sur `t0`,
  `years` et `seed` : sinon `sim/` vient d'un autre run (périmé) ;
- années retenues (T1) : t0, t0 + N, t0 + 2N… jusqu'à t0 + years, puis toujours t0 + years ;
- chaque année retenue doit avoir sa partition `sim/trees/year=AAAA/` ; toutes les années de t0 à
  t0 + years doivent avoir leur partition `sim/cells/year=AAAA/` (l'échelle de la carte de surface
  terrière se calcule sur toutes les années simulées, Q3), avec la colonne `h_dom_m` (Q1) ;
- arbres d'une année : `status` vaut `alive` ou `dead`, `tree_id` est unique dans la partition ;
  seuls les vivants sont dessinés (T5), les morts sont comptés ;
- aucune interpolation entre années (T3) et aucune lecture d'un autre module que par fichiers :
  ni `simulate` ni `post` ne sont importés.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from sylvigenese.common import ModuleError

TREE_COLUMNS = ["tree_id", "species", "x", "y", "d130", "h", "hcb", "cw", "status"]
CELL_COLUMNS = ["cell_id", "species", "stems_ha", "basal_area_m2_ha", "d130_mean", "h_dom_m"]
COMPARED_KEYS = (("t0", "t0"), ("years", "years"), ("seed", "seed (graine)"))
PARTITION = re.compile(r"^year=(\d{4})$")
CELL_ENTITY = re.compile(r"^\d+$")


def year_step(config: dict) -> int:
    """`assets.year_step` de config.yml ; absent, ou pas un entier >= 1 : refus (code 2)."""
    block = config.get("assets")
    if not isinstance(block, dict):
        raise ModuleError("sim/ existe mais le bloc `assets` manque dans config.yml : assets.year_step (une année "
                          "retenue sur N) est exigé, aucune valeur par défaut n'est prise (plan T1)")
    step = block.get("year_step")
    if isinstance(step, bool) or not isinstance(step, int) or step < 1:
        raise ModuleError(f"assets.year_step = {step!r} dans config.yml : un entier supérieur ou égal à 1 est exigé")
    return step


def retained_years(t0: int, years: int, step: int) -> list[int]:
    """t0, t0 + N, t0 + 2N… <= t0 + years, puis t0 + years s'il n'y est pas déjà (T1)."""
    out = list(range(t0, t0 + years + 1, step))
    if out[-1] != t0 + years:
        out.append(t0 + years)
    return out


def read_run(zone: Path, config: dict) -> dict:
    """Lit `sim/run.json` et vérifie qu'il est le run du bloc `simulate` de config.yml."""
    path = zone / "sim" / "run.json"
    if not path.is_file():
        raise ModuleError(f"{path} absent : sim/ sans run.json n'est pas lisible (run interrompu ou incomplet) ; "
                          "relancer simulate")
    try:
        run = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ModuleError(f"{path} illisible : {error}") from error
    block = config.get("simulate")
    if not isinstance(block, dict):
        raise ModuleError("sim/ existe mais le bloc `simulate` manque dans config.yml : impossible de vérifier que "
                          "sim/ vient de ce réglage")
    different = [f"{label} : config.yml {block.get(key)!r}, run.json {run.get(key)!r}"
                 for key, label in COMPARED_KEYS if block.get(key) != run.get(key)]
    if different:
        raise ModuleError("le bloc simulate de config.yml diffère de sim/run.json (" + " ; ".join(different) +
                          ") : sim/ vient d'un autre run ; relancer simulate ou corriger config.yml")
    return run


def _partition_files(zone: Path, kind: str, year: int) -> list[Path]:
    directory = zone / "sim" / kind / f"year={year}"
    files = sorted(directory.glob("*.parquet")) if directory.is_dir() else []
    if not files:
        raise ModuleError(f"partition {directory.relative_to(zone)} absente ou vide : l'année {year} est attendue "
                          f"dans sim/{kind} (run de {kind}) ; relancer simulate")
    return files


def check_partitions(zone: Path, t0: int, years: int, retained: list[int]) -> None:
    """Partitions attendues présentes ; aucune hors de l'horizon du run."""
    for year in retained:
        _partition_files(zone, "trees", year)
    for year in range(t0, t0 + years + 1):
        _partition_files(zone, "cells", year)
    for kind in ("trees", "cells"):
        base = zone / "sim" / kind
        extra = sorted(int(m.group(1)) for d in base.iterdir() if (m := PARTITION.match(d.name))
                       and not t0 <= int(m.group(1)) <= t0 + years)
        if extra:
            raise ModuleError(f"sim/{kind} porte des années hors de l'horizon du run ({t0} à {t0 + years}) : "
                              f"{extra[:5]} ; sim/ mêle deux runs")
    if not (zone / "sim" / "flags.parquet").is_file():
        raise ModuleError(f"{zone / 'sim' / 'flags.parquet'} absent : les signalements de la fiche ne seraient pas lus")


def _read_file(path: Path, columns: list[str], what: str) -> pa.Table:
    names = pq.read_schema(path).names
    missing = [c for c in columns if c not in names]
    if missing:
        raise ModuleError(f"{path} : colonne(s) {', '.join(missing)} absente(s) ({what}) ; "
                          + ("h_dom_m est écrit par simulate depuis la mission 046 (décision de Pascal Q1) : relancer simulate"
                             if "h_dom_m" in missing else "contrat non respecté"))
    return pq.ParquetFile(path).read(columns=columns)


def read_trees(zone: Path, year: int) -> dict[str, np.ndarray]:
    """Arbres de `sim/trees/year=AAAA/`, triés par tree_id ; `tree_id` unique, `status` connu."""
    files = _partition_files(zone, "trees", year)
    table = pa.concat_tables([_read_file(f, TREE_COLUMNS, "sim/trees") for f in files])
    if table.num_rows == 0:
        raise ModuleError(f"sim/trees/year={year} ne contient aucun arbre")
    ids = np.array(table.column("tree_id").to_pylist(), dtype=object)
    unique, counts = np.unique(ids, return_counts=True)
    if (counts > 1).any():
        doubles = unique[counts > 1]
        raise ModuleError(f"sim/trees/year={year} : tree_id en double ({len(doubles)}, par exemple {doubles[0]}) ; "
                          "un tree_id doit être unique dans une année")
    status = np.array(table.column("status").to_pylist(), dtype=object)
    unknown = sorted(set(status.tolist()) - {"alive", "dead"})
    if unknown:
        raise ModuleError(f"sim/trees/year={year} : status inconnu {unknown} (alive ou dead attendus)")
    order = np.argsort(ids, kind="stable")
    trees = {"tree_id": ids[order], "status": status[order],
             "species": np.array(table.column("species").to_pylist(), dtype=object)[order]}
    for name in ("x", "y", "d130", "h", "hcb", "cw"):
        trees[name] = table.column(name).to_numpy().astype("float64")[order]
    return trees


def read_cells(zone: Path, t0: int, years: int) -> pa.Table:
    """Toutes les lignes de `sim/cells`, de t0 à t0 + years, avec la colonne `year` reconstituée."""
    parts = []
    for year in range(t0, t0 + years + 1):
        for f in _partition_files(zone, "cells", year):
            t = _read_file(f, CELL_COLUMNS, "sim/cells")
            t = pa.table({"cell_id": t.column("cell_id").cast(pa.int64()), "species": t.column("species").cast(pa.string()),
                          "stems_ha": t.column("stems_ha").cast(pa.float64()),
                          "basal_area_m2_ha": t.column("basal_area_m2_ha").cast(pa.float64()),
                          "d130_mean": t.column("d130_mean").cast(pa.float64()),
                          "h_dom_m": t.column("h_dom_m").cast(pa.float64())})
            parts.append(t.append_column("year", pa.array([year] * t.num_rows, pa.int64())))
    return pa.concat_tables(parts)


def basal_area_scale(cells: pa.Table, forest_cells: set[int]) -> tuple[float, float]:
    """Échelle fixe de la carte de G (Q3) : min et max, sur TOUTES les années simulées, de la surface terrière
    par cellule telle que la carte la montre (somme des essences ; 0 pour une cellule forestière sans ligne)."""
    sums = cells.group_by(["year", "cell_id"]).aggregate([("basal_area_m2_ha", "sum")])
    values = sums.column("basal_area_m2_ha_sum").to_numpy()
    low, high = float(values.min()) if len(values) else 0.0, float(values.max()) if len(values) else 0.0
    years = pc.unique(cells.column("year")).to_pylist()
    ids_by_year = {}
    for y, c in zip(sums.column("year").to_pylist(), sums.column("cell_id").to_pylist()):
        ids_by_year.setdefault(y, set()).add(c)
    if any(forest_cells - ids_by_year.get(y, set()) for y in years):
        low = min(low, 0.0)
    if not high > low:
        raise ModuleError(f"échelle de la carte de surface terrière vide ({low} à {high} m2/ha) : rien à montrer")
    return low, high


def cell_flags(zone: Path, retained: list[int]) -> dict[tuple[int, int], list[dict]]:
    """Signalements de `sim/flags.parquet` dont l'entité est un cell_id (en décimal, contrat simulate.flags),
    pour les années retenues, triés (sorte, message, valeur)."""
    table = pq.read_table(zone / "sim" / "flags.parquet", columns=["year", "entity", "kind", "message", "value"])
    keep = set(retained)
    out: dict[tuple[int, int], list[dict]] = {}
    for year, entity, kind, message, value in zip(*(table.column(n).to_pylist()
                                                    for n in ("year", "entity", "kind", "message", "value"))):
        if int(year) not in keep or not CELL_ENTITY.match(str(entity)):
            continue
        item = {"kind": kind, "message": message}
        if value is not None and np.isfinite(value):
            item["value"] = float(value)
        out.setdefault((int(entity), int(year)), []).append(item)
    for items in out.values():
        items.sort(key=lambda f: (f["kind"], f["message"], f.get("value", float("-inf"))))
    return out
