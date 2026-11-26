"""FIXTURE SYNTHÉTIQUE d'exemplaires du générateur, écrite pour les tests unitaires de la mission 070.

AUCUNE VALEUR N'EST ÉCOLOGIQUE, aucun code du générateur de tarif-nemeton : un tronc droit, des branches tirées
d'une graine fixe (numpy, `default_rng`), toutes du côté est et nord, et une branche repère qui finit en
(x = 2, y = 5, z = 0,6 H) : x et y différents pour attraper une inversion (« la Somalie »). Les dimensions (D, H,
hbh, Rh) sont une échelle de test. Le fichier dit `synthetic = true`, `source_commit = 0000000` (aucun commit de
tarif-nemeton : il n'en vient pas) et porte la note `fixture_note`.

Repère du générateur : z-up (x est, y nord, z haut, mètres, base du tronc en z = 0), dit dans les métadonnées.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

STAGES = ("young", "pole", "mature", "old")
HEIGHT = {"young": 8.0, "pole": 16.0, "mature": 24.0, "old": 32.0}
DIAMETER = {"young": 10.0, "pole": 20.0, "mature": 30.0, "old": 40.0}
MARKER = (2.0, 5.0, 0.6)           # x, y, part de H de l'extrémité de la branche repère
NOTE = "synthetique : fixture de test de la mission 070, aucune valeur ecologique, ne valide aucun tarif"
COLUMNS = ("x0", "y0", "z0", "x1", "y1", "z1", "r0_m", "r1_m", "niveau", "axe")


def segments(stage: str, seed: int = 1, trunk: int = 12, branches: int = 20) -> dict[str, np.ndarray]:
    """Segments d'un arbre synthétique de ce stade (repère z-up)."""
    rng = np.random.default_rng(seed)
    h = HEIGHT[stage]
    rows: list[tuple] = []
    zs = np.linspace(0.0, h, trunk + 1)
    r_base = DIAMETER[stage] / 200.0
    for i in range(trunk):
        rows.append((0.0, 0.0, zs[i], 0.0, 0.0, zs[i + 1], r_base * (1 - zs[i] / h), r_base * (1 - zs[i + 1] / h), 0, 0))
    axe = 1
    for b in range(branches):
        z = h * (0.25 + 0.5 * b / branches)
        azimuth = np.radians(rng.uniform(0.0, 120.0))             # de l'est vers le nord : jamais de y < 0
        length = (0.15 + 0.25 * (1 - z / h)) * h * rng.uniform(0.7, 1.0)
        r0 = 0.04 * (1 - z / h) + 0.012
        previous = np.array([0.0, 0.0, z])
        for s in range(3):
            f = (s + 1) / 3
            point = np.array([np.cos(azimuth) * length * f, np.sin(azimuth) * length * f, z + 0.1 * length * f])
            rows.append((*previous, *point, r0 * (1 - 0.7 * s / 3), r0 * (1 - 0.7 * (s + 1) / 3), 1, axe))
            previous = point
        start = np.array([0.0, 0.0, z]) + (previous - np.array([0.0, 0.0, z])) * 0.6
        rows.append((*start, *(start + np.array([0.3, 0.3, 0.1])), 0.006, 0.002, 2, axe + 1))
        axe += 2
    zm = h * MARKER[2]
    rows.append((0.0, 0.0, zm - 0.3, MARKER[0], MARKER[1], zm, 0.05, 0.04, 1, axe))
    table = np.array([[float(v) for v in row] for row in rows])
    out = {name: table[:, k] for k, name in enumerate(COLUMNS[:8])}
    out["niveau"] = table[:, 8].astype("int64")
    out["axe"] = table[:, 9].astype("int64")
    return out


def minimal(stage: str, trunk: int = 12) -> dict[str, np.ndarray]:
    """Une tige et la seule branche repère : rien d'autre près des conversions fausses (test du repère)."""
    seg = segments(stage, 1, trunk=trunk, branches=0)
    return seg


def metadata(essence: str, stage: str, **overrides) -> dict[str, str]:
    h = HEIGHT[stage]
    meta = {"frame": "z-up", "units": "m", "essence": essence, "stage": stage, "D_cm": repr(DIAMETER[stage]),
            "H_m": repr(h), "hbh_m": repr(h * 0.4), "Rh_m": repr(h * 0.2), "b_cible": "1.0", "calage": "calé", "seed": "7",
            "source_commit": "0000000", "synthetic": "true", "fixture_note": NOTE}
    if essence == "Abies_alba":           # comme l'export de tarif-nemeton : le résineux est dit non calé par l'export lui-même
        meta.update(calage="non calé", calage_raisons="essai : résineux, densité des rameaux non calée")
    meta.update(overrides)
    return {k: v for k, v in meta.items() if v is not None}


def write(directory: Path, essence: str, stage: str, seed: int = 1, meta: dict | None = None,
          seg: dict | None = None) -> Path:
    """Écrit `<essence>_<stade>.parquet` ; `meta` remplace des métadonnées (None retire la clé)."""
    seg = seg or segments(stage, seed)
    schema = pa.schema([pa.field(k, pa.float64()) for k in COLUMNS[:8]]
                       + [pa.field("niveau", pa.int64()), pa.field("axe", pa.int64())],
                       metadata={k.encode(): v.encode() for k, v in {**metadata(essence, stage), **(meta or {})}.items()
                                 if v is not None})
    table = pa.table({f.name: pa.array(seg[f.name], type=f.type) for f in schema}, schema=schema)
    path = Path(directory) / f"{essence}_{stage}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path, compression="none")
    return path


def write_set(directory: Path, essences=("Fagus_sylvatica", "Quercus_spec", "Abies_alba")) -> Path:
    """Trois essences, quatre stades, graines différentes par essence."""
    for k, essence in enumerate(essences):
        for stage in STAGES:
            write(directory, essence, stage, seed=11 + k)
    return Path(directory)
