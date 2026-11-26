#!/usr/bin/env python3
"""Fixture d'exemplaires SYNTHÉTIQUES de M6a (mission 069, contrat assets.exemplars).

Écrit tests/fixtures/exemplars_m6/<essence>_<stade>.parquet : 3 essences x 4 stades (Fagus_sylvatica,
Quercus_spec, Abies_alba ; code espar 09, 02 (alias 03), 61). Les essences 62 et 64 de la zone fictive n'ont
VOLONTAIREMENT pas d'exemplaire : elles servent aux tests du modèle générique signalé (décision Q3).

AUCUNE VALEUR N'EST ÉCOLOGIQUE. Ce sont des arbres géométriques de test : un tronc droit, des branches
tirées d'une graine, toutes du côté est / nord (cime volontairement asymétrique pour attraper un x et un y
inversés, « le piège de la Somalie »). Les dimensions D, H, hbh, Rh valent la même suite pour les trois
essences (D_cm = 10 / 20 / 30 / 40, H_m = 8 / 16 / 24 / 32) : une échelle de test, pas une dendrométrie.
Les métadonnées disent `synthetic = true` et `fixture_note`. `source_commit` = 0000000 (aucun commit
de tarif-nemeton : le fichier n'en vient pas).

Repère du générateur : z-up (x est, y nord, z haut, mètres, base du tronc en z = 0).
Le fichier est déterministe (graines fixes) ; un test le régénère et compare.

Usage : python3 tests/fixtures/make_exemplars_m6.py [dossier de sortie]
"""
import sys
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

STAGES = ("young", "pole", "mature", "old")
D_CM = {"young": 10.0, "pole": 20.0, "mature": 30.0, "old": 40.0}
H_M = {"young": 8.0, "pole": 16.0, "mature": 24.0, "old": 32.0}
ESSENCES = {"Fagus_sylvatica": 11, "Quercus_spec": 22, "Abies_alba": 33}   # essence -> graine de base
MARQUEUR = {"x1": 12.0, "y1": 3.0, "z_frac": 0.6, "r1": 0.04}               # branche repère longue, loin des branches aléatoires (<= 0,4 H)
N_TRONC = 24
N_BRANCHES = 30
NOTE = "synthetique : fixture de test de M6a, aucune valeur ecologique, ne valide aucun tarif"


def tree_segments(essence: str, stage: str) -> tuple[dict, dict]:
    seed = ESSENCES[essence] * 10 + STAGES.index(stage)
    rng = np.random.default_rng(seed)
    h = H_M[stage]
    d = D_CM[stage]
    seg = {k: [] for k in ("x0", "y0", "z0", "x1", "y1", "z1", "r0_m", "r1_m", "niveau", "axe")}

    def add(p0, p1, r0, r1, niveau, axe):
        for k, v in zip(("x0", "y0", "z0", "x1", "y1", "z1", "r0_m", "r1_m", "niveau", "axe"),
                        (*p0, *p1, r0, r1, niveau, axe)):
            seg[k].append(v)

    # tronc : droit sur z, de r = D/200 m (rayon à la base) à 0 au sommet (étendue exacte = H)
    r_base = d / 200.0
    zs = np.linspace(0.0, h, N_TRONC + 1)
    rs = r_base * (1.0 - zs / h)
    for i in range(N_TRONC):
        add((0.0, 0.0, zs[i]), (0.0, 0.0, zs[i + 1]), float(rs[i]), float(rs[i + 1]), 0, 0)
    axe = 1
    # branches de niveau 1 : azimut dans [0, 120] degrés (est vers nord) : jamais de y < 0
    for b in range(N_BRANCHES):
        z = h * (0.25 + 0.5 * b / N_BRANCHES)
        az = np.radians(rng.uniform(0.0, 120.0))
        length = (0.15 + 0.25 * (1.0 - (z / h))) * h * rng.uniform(0.7, 1.0)
        rise = rng.uniform(0.0, 0.25) * length
        r0 = 0.05 * (1.0 - z / h) + 0.012
        p0 = np.array([0.0, 0.0, z])
        prev = p0
        for s in range(4):
            f = (s + 1) / 4.0
            p1 = p0 + np.array([np.cos(az) * length * f, np.sin(az) * length * f, rise * f])
            add(tuple(prev), tuple(p1), float(r0 * (1 - 0.8 * s / 4)), float(r0 * (1 - 0.8 * (s + 1) / 4)), 1, axe)
            prev = p1
        # rameaux de niveau 2 (rayon sous 1 cm : au-dessous du r_min de LOD0)
        for t in range(3):
            q0 = p0 + (prev - p0) * rng.uniform(0.3, 0.9)
            az2 = np.radians(float(np.clip(np.degrees(az) + rng.uniform(-40.0, 40.0), 0.0, 120.0)))
            q1 = q0 + np.array([np.cos(az2), np.sin(az2), rng.uniform(0.0, 0.3)]) * length * 0.3
            add(tuple(q0), tuple(q1), 0.008, 0.003, 2, axe + 1 + t)
        axe += 4
    # branche repère : extrémité en (12, 3, 0.6 H), horizontale, longue et décentrée (loin de toute autre branche) ; rayon final 0,04 m (> 1 cm : présente au LOD0)
    zm = h * MARQUEUR["z_frac"]
    add((0.0, 0.0, zm - 0.3), (MARQUEUR["x1"], MARQUEUR["y1"], zm), 0.06, MARQUEUR["r1"], 1, axe)
    meta = {
        "frame": "z-up", "units": "m", "essence": essence, "stage": stage,
        "D_cm": repr(d), "H_m": repr(h), "hbh_m": repr(h * 0.5), "Rh_m": repr(h * 0.25), "b_cible": "1.0",
        "calage": "non calé" if essence == "Abies_alba" else "calé",
        "seed": str(seed), "source_commit": "0000000", "synthetic": "true", "fixture_note": NOTE,
    }
    if essence == "Abies_alba":
        meta["calage_raisons"] = "resineux : densite des rameaux tiree, stades jeune et perche extrapoles (fixture)"
    return seg, meta


def write_all(out: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    files = []
    for essence in ESSENCES:
        for stage in STAGES:
            seg, meta = tree_segments(essence, stage)
            schema = pa.schema(
                [pa.field(k, pa.float64()) for k in ("x0", "y0", "z0", "x1", "y1", "z1", "r0_m", "r1_m")]
                + [pa.field("niveau", pa.int64()), pa.field("axe", pa.int64())],
                metadata={k.encode(): v.encode() for k, v in meta.items()})
            table = pa.table({f.name: pa.array(seg[f.name], type=f.type) for f in schema}, schema=schema)
            path = out / f"{essence}_{stage}.parquet"
            pq.write_table(table, path, compression="none")
            files.append(path)
    return files


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "exemplars_m6"
    for f in write_all(target):
        print(f)
