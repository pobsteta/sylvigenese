"""Outils des tests d'acceptation de la suite de M4a : la vue dans le temps (mission 045).

Sources : docs/plans/m4a-suite-temps.md (§2 mission B, §3, T1 à T10), décisions de Pascal Q1 à Q3 du 25/11/2026,
contrats de la mission 044 (cell_sheet v2, tiles_index, bloc assets de config, h_dom_m de sim.cells,
assets.basal_area_raster, contracts/README.md), précisions de l'orchestrateur au journal. Ces tests ne lisent ni
python/sylvigenese/, ni viewer-web/src, ni simulate/src.

Oracle : tout ce que `assets` doit écrire en mode `sim` est recalculé ICI depuis sim/ (trees, cells, flags.parquet,
run.json), config.yml et les rasters de prepare et biomes. Conventions prises (une seule déclaration ici) :
  - années retenues (T1) : t0, t0 + N, t0 + 2N… <= t0 + years, puis t0 + years si elle n'y est pas déjà ;
  - une instance par arbre `status = alive` de la partition de l'année ; un mort (écrit une fois, l'année de sa mort)
    n'est pas dessiné (T5) ; `dead` de l'index = lignes `dead` de la partition ;
  - tuile d'un arbre : coin sud-ouest = (700 000 + 500 i, 6 500 000 + 500 j), nom t_<x>_<y> (contrat tiles_index) ;
  - fiche v2 (contrat et précision de l'orchestrateur du 25/11) : une année où la cellule n'a aucune ligne dans
    sim/cells a stems_ha = 0, basal_area_m2_ha = 0, d130_mean_cm = null, h_dom_m = null, composition vide ;
  - flags d'une cellule : lignes de flags.parquet dont `entity` est le cell_id en décimal, de la même année ;
  - G de la carte au sol (Q3) : somme des basal_area_m2_ha des essences de la cellule ; 0 pour une cellule
    forestière sans ligne ; nodata hors forêt (cellule sans type de végétation) ;
  - repère des instances : celui de helpers_m4 (ECEF ou EPSG:2154, le test ne tranche pas).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq

import helpers_m4 as H

ROOT = H.ROOT
T0 = 2022
YEARS = 15              # horizon court (CI, plan §6 point 3) : 2037 n'est pas un multiple de 10 après t0
STEP = 10               # config.yml du dépôt (assets.year_step)
STEP_FIN = 5            # second réglage, pour le test discriminant du pas et des années périmées
TILE = 500.0
AIRE_CELLULE_HA = 0.0625
TOL_REL = 1e-9          # « recalcul arithmétique exact » (contrat cell_sheet v2)
MENTION_ECO = "non validée écologiquement"
MENTION_VC = "volume et carbone non calculés"
CHARGE = "m4_charge"
CHARGE_VIVANTS = {2022: 100_013, 2023: 100_000}     # T8 : exactement 100 000 la dernière année
CHARGE_MORTS = {2022: 0, 2023: 13}
POINT_CONNU = (700_012.5, 6_500_987.5)             # fiche 047 : tuile t_700000_6500500, cellule 0


def retained_years(t0: int, years: int, step: int) -> list[int]:
    out = list(range(t0, t0 + years + 1, step))
    if out[-1] != t0 + years:
        out.append(t0 + years)
    return out


# ------------------------------------------------------------------ configuration
def _strip_block(text: str, name: str) -> str:
    return re.sub(rf"(?m)^{name}:[ \t]*\n(?:[ \t#][^\n]*\n?|\n(?=[ \t]))*", "", text)


def write_config(zone_dir: Path, name: str, simulate: dict | None, assets: dict | None, fname: str) -> Path:
    """config.yml du dépôt, zone changée, blocs `simulate` et `assets` remplacés (None : bloc absent)."""
    text = (ROOT / "config.yml").read_text(encoding="utf-8")
    text = re.sub(r"(?m)^zone:\s*\S+", f"zone: {name}", text)
    text = _strip_block(_strip_block(text, "simulate"), "assets").rstrip("\n") + "\n"
    for bloc, vals in (("simulate", simulate), ("assets", assets)):
        if vals is not None:
            text += f"\n{bloc}:\n" + "".join(f"  {k}: {v}\n" for k, v in vals.items())
    cfg = zone_dir / fname
    cfg.write_text(text, encoding="utf-8")
    return cfg


def sim_block(**kw) -> dict:
    return {"level": "massif", "seed": 42, "t0": T0, "years": YEARS, "threads": 4, "recruitment": "ifn_direct", **kw}


# ------------------------------------------------------------------ copies de zone
def link_copy(src: Path, dst: Path, copy_dirs=()) -> None:
    """Copie de `src` en liens physiques (sim/ pèse lourd), sauf les sorties de assets ; `copy_dirs` est copié
    pour de vrai. Une mutation doit DÉLIER un fichier avant de le réécrire (voir rewrite_parquet)."""
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, copy_function=os.link,
                    ignore=shutil.ignore_patterns(*H.ASSET_DIRS, "config_m4*.yml", "__pycache__"))
    for d in copy_dirs:
        if (src / d).is_dir():
            shutil.copytree(src / d, dst / d)


def rewrite_parquet(path: Path, fn) -> None:
    t = fn(pq.read_table(path))
    path.unlink()
    pq.write_table(t, path)


# ------------------------------------------------------------------ lecture de sim/
def sim_dataset(zone_dir: Path, kind: str):
    base = zone_dir / "sim" / kind
    assert base.is_dir(), f"sim/{kind} absent"
    return ds.dataset(base, format="parquet", partitioning="hive")


def sim_years(zone_dir: Path, kind: str) -> list[int]:
    base = zone_dir / "sim" / kind
    return sorted(int(d.name[5:]) for d in base.iterdir() if re.fullmatch(r"year=\d{4}", d.name)) if base.is_dir() else []


def trees_of_year(zone_dir: Path, year: int) -> dict[str, np.ndarray]:
    t = sim_dataset(zone_dir, "trees").to_table(filter=ds.field("year") == year)
    assert t.num_rows > 0, f"sim/trees/year={year} vide ou absente"
    return {n: np.asarray(t.column(n).to_pylist() if t.schema.field(n).type in (pa.string(), pa.large_string())
                          else t.column(n).to_numpy()) for n in t.schema.names}


def cells_rows(zone_dir: Path, years=None) -> list[dict]:
    d = sim_dataset(zone_dir, "cells")
    t = d.to_table() if years is None else d.to_table(filter=ds.field("year").isin(list(years)))
    return t.to_pylist()


def cell_year_table(rows: list[dict]) -> dict[tuple[int, int], list[dict]]:
    out: dict = {}
    for r in rows:
        out.setdefault((int(r["cell_id"]), int(r["year"])), []).append(r)
    return out


def flags_by_cell_year(zone_dir: Path) -> dict[tuple[int, int], list[tuple]]:
    t = pq.read_table(zone_dir / "sim" / "flags.parquet").to_pylist()
    out: dict = {}
    for r in t:
        if re.fullmatch(r"\d+", str(r["entity"])):
            out.setdefault((int(r["entity"]), int(r["year"])), []).append(
                (r["kind"], r["message"], None if r["value"] is None or (isinstance(r["value"], float) and math.isnan(r["value"])) else float(r["value"])))
    return out


def expected_year(rows: list[dict] | None) -> dict:
    """Ce que la fiche v2 doit porter pour une (cellule, année), depuis les lignes de sim/cells."""
    if not rows:
        return {"stems_ha": 0.0, "basal_area_m2_ha": 0.0, "d130_mean_cm": None, "h_dom_m": None, "composition": {}}
    st = sum(float(r["stems_ha"]) for r in rows)
    ba = sum(float(r["basal_area_m2_ha"]) for r in rows)
    dw = sum(float(r["d130_mean"]) * float(r["stems_ha"]) for r in rows
             if r["d130_mean"] is not None and float(r["stems_ha"]) > 0)
    hd = {r.get("h_dom_m") for r in rows}
    comp = {str(r["species"]): (float(r["stems_ha"]), float(r["basal_area_m2_ha"]),
                                float(r["stems_ha"]) / st if st > 0 else 0.0) for r in rows}
    return {"stems_ha": st, "basal_area_m2_ha": ba, "d130_mean_cm": dw / st if st > 0 else None,
            "h_dom_m": hd.pop() if len(hd) == 1 else ("DIVERGENT", sorted(map(str, hd))), "composition": comp}


def close(a, b, tol=TOL_REL) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(float(a) - float(b)) <= tol * max(1.0, abs(float(a)), abs(float(b)))


# ------------------------------------------------------------------ tuiles et instances
def tile_name(x, y) -> np.ndarray:
    i = np.floor((np.asarray(x) - H.X0) / TILE).astype(int)
    j = np.floor((np.asarray(y) - (H.Y0 - 1000.0)) / TILE).astype(int)
    return np.array([f"t_{int(H.X0 + TILE * a)}_{int(H.Y0 - 1000.0 + TILE * b)}" for a, b in zip(i, j)])


def read_index(zone_dir: Path) -> dict:
    p = zone_dir / "tiles" / "index.json"
    assert p.is_file(), f"{p.relative_to(ROOT)} absent"
    return json.loads(p.read_text(encoding="utf-8"))


def tileset_extras(ts_path: Path) -> dict:
    ts = json.loads(ts_path.read_text(encoding="utf-8"))
    return ts.get("extras") or ts.get("asset", {}).get("extras") or ts.get("root", {}).get("extras") or {}


def collect_tileset(ts_path: Path) -> dict:
    """Instances d'UN tileset (une année), en repère monde ; même calcul que helpers_m4.collect_instances, qui lit
    tous les tilesets de la zone à la fois. `tile` : nom de la tuile (fichier de contenu sans extension)."""
    worlds, scales, models, tiles = [], [], [], []
    for c in H.walk_tileset(ts_path):
        gltf = H.read_gltf(c["path"])
        cache: dict = {}
        for i, nm in H.instance_nodes(gltf):
            node = gltf["nodes"][i]
            attrs = node["extensions"][H.EXT]["attributes"]
            tr = H.read_accessor(gltf, attrs["TRANSLATION"], c["path"].parent, cache)
            sc = H.read_accessor(gltf, attrs["SCALE"], c["path"].parent, cache) if "SCALE" in attrs else np.ones_like(tr)
            key = H.mesh_key(gltf, node["mesh"], c["path"].parent, cache)
            p = np.c_[tr, np.ones(len(tr))] @ nm.T
            p = p @ H.Y_UP_TO_Z_UP.T
            rtc = gltf.get("extensions", {}).get("CESIUM_RTC", {}).get("center")
            if rtc:
                p[:, :3] += np.array(rtc)
            p = p @ c["matrix"].T
            worlds.append(p[:, :3])
            scales.append(sc)
            models.extend([key] * len(tr))
            tiles.extend([Path(c["uri"]).stem] * len(tr))
    if not worlds:
        return {"world": np.zeros((0, 3)), "scale": np.zeros((0, 3)), "model": np.array([]), "tile": np.array([])}
    return {"world": np.vstack(worlds), "scale": np.vstack(scales), "model": np.array(models), "tile": np.array(tiles)}


def nearest_match(world: np.ndarray, tx: np.ndarray, ty: np.ndarray) -> dict:
    """Associe chaque instance à l'arbre le plus proche (hachage de 1 m, 3 x 3 voisins), dans chacun des deux repères
    admis ; garde celui qui apparie le plus d'instances à moins de POS_TOL. Les recrues ne sont pas sur le réseau
    des pixels du MNH : l'appariement par clé de réseau de helpers_m4 ne leur convient pas."""
    buckets: dict = {}
    kx, ky = np.floor(tx).astype(np.int64), np.floor(ty).astype(np.int64)
    for i, (a, b) in enumerate(zip(kx.tolist(), ky.tolist())):
        buckets.setdefault((a, b), []).append(i)
    best = None
    for frame in ("ECEF", "EPSG:2154"):
        xy = H.to_lambert(world, frame) if len(world) else np.zeros((0, 2))
        if not np.all(np.isfinite(xy)):
            continue
        tree_of = np.full(len(xy), -1, dtype=np.int64)
        resid = np.full(len(xy), np.inf)
        for n, (x, y) in enumerate(xy.tolist()):
            a, b = math.floor(x), math.floor(y)
            bd, bi = np.inf, -1
            for da in (-1, 0, 1):
                for db in (-1, 0, 1):
                    for i in buckets.get((a + da, b + db), ()):
                        d = (tx[i] - x) ** 2 + (ty[i] - y) ** 2
                        if d < bd:
                            bd, bi = d, i
            if bi >= 0 and math.sqrt(bd) <= H.POS_TOL:
                tree_of[n], resid[n] = bi, math.sqrt(bd)
        res = {"frame": frame, "xy": xy, "tree_of": tree_of, "resid": resid, "n_ok": int((tree_of >= 0).sum())}
        if best is None or res["n_ok"] > best["n_ok"]:
            best = res
    return best


# ------------------------------------------------------------------ zone de charge synthétique (T8)
def build_charge_sim(zone_dir: Path, cfg: Path, forest_cells: list[int]) -> dict:
    """Écrit sous zone_dir/sim un sim/ SYNTHÉTIQUE (aucune valeur écologique, zone marquée fictive) : 2022 avec
    100 013 vivants, 2023 avec 100 000 vivants et 13 morts. Positions tirées au hasard (graine fixe) dans les
    cellules forestières ; l'arbre 0 au point connu (700 012,5 ; 6 500 987,5). Renvoie la description du jeu."""
    sim = zone_dir / "sim"
    shutil.rmtree(sim, ignore_errors=True)
    rng = np.random.default_rng(20261125)
    n = CHARGE_VIVANTS[2022]
    cells = np.array(sorted(forest_cells))
    assert cells[0] == 0, "la cellule 0 doit être forestière (point connu de la fiche 047)"
    cell = cells[np.arange(n) % len(cells)]
    r, c = np.divmod(cell, H.NCOLS)
    x = H.X0 + c * H.RES + 0.5 + rng.random(n) * (H.RES - 1.0)
    y = H.Y0 - (r + 1) * H.RES + 0.5 + rng.random(n) * (H.RES - 1.0)
    x[0], y[0] = POINT_CONNU
    sp = np.array(["09", "61", "03", "62", "64"])[np.arange(n) % 5]
    d130 = 10.0 + (np.arange(n) % 50)
    h = 5.0 + (np.arange(n) % 30)
    cw = 2.0 + (np.arange(n) % 5)
    tid = np.array([f"S{i:06d}" for i in range(n)])
    morts = np.arange(1, 1 + CHARGE_MORTS[2023])
    states = {}
    for year in (2022, 2023):
        status = np.array(["alive"] * n, dtype=object)
        hh = h.copy()
        if year == 2023:
            status[morts] = "dead"
            hh = np.where(status == "alive", h + 0.5, h)
        states[year] = {"tree_id": tid, "species": sp, "x": x, "y": y, "d130": d130, "h": hh, "hcb": 0.3 * hh,
                        "cw": cw, "status": status.astype(str)}
        d = sim / "trees" / f"year={year}"
        d.mkdir(parents=True)
        pq.write_table(pa.table({k: pa.array(list(v.tolist())) for k, v in states[year].items()}), d / "part-00000.parquet")
        alive = status == "alive"
        cid = H.NCOLS * np.floor((H.Y0 - y[alive]) / H.RES).astype(int) + np.floor((x[alive] - H.X0) / H.RES).astype(int)
        rows: dict = {}
        hdom: dict = {}
        for k, s, dd, hv in zip(cid.tolist(), sp[alive].tolist(), d130[alive].tolist(), hh[alive].tolist()):
            e = rows.setdefault((k, s), [0, 0.0, 0.0])
            e[0] += 1
            e[1] += math.pi * (dd / 200.0) ** 2
            e[2] += dd
            hdom[k] = max(hdom.get(k, 0.0), hv)
        keys = sorted(rows)
        cols = {"cell_id": [k for k, _ in keys], "species": [s for _, s in keys],
                "stems_ha": [rows[k][0] / AIRE_CELLULE_HA for k in keys],
                "basal_area_m2_ha": [rows[k][1] / AIRE_CELLULE_HA for k in keys],
                "d130_mean": [rows[k][2] / rows[k][0] for k in keys],
                "h_dom_m": [hdom[k[0]] for k in keys]}
        d = sim / "cells" / f"year={year}"
        d.mkdir(parents=True)
        pq.write_table(pa.table({"cell_id": pa.array(cols["cell_id"], pa.int64()), "species": pa.array(cols["species"]),
                                 "stems_ha": pa.array(cols["stems_ha"]), "basal_area_m2_ha": pa.array(cols["basal_area_m2_ha"]),
                                 "d130_mean": pa.array(cols["d130_mean"]), "h_dom_m": pa.array(cols["h_dom_m"])}),
                       d / "part-00000.parquet")
    pq.write_table(pa.table({"year": pa.array([], pa.int64()), "entity": pa.array([], pa.string()),
                             "kind": pa.array([], pa.string()), "message": pa.array([], pa.string()),
                             "value": pa.array([], pa.float64())}), sim / "flags.parquet")
    run = {"schema_version": 1, "level": "massif", "seed": 42, "t0": 2022, "years": 1, "threads": 1,
           "memory_estimate_bytes": 0, "duration_s": 0.0,
           "config_sha256": hashlib.sha256(cfg.read_bytes()).hexdigest(), "zeroed_values": 0,
           "provisional_share": 1.0, "domain_outputs": {"d130": {"below": 0, "above": 0}},
           "cells_at_height_ceiling": 0, "edge_disks": 0, "mixed_cells": 0, "recruits": 0,
           "deaths": CHARGE_MORTS[2023]}
    (sim / "run.json").write_text(json.dumps(run, indent=1), encoding="utf-8")
    (zone_dir / "zone.yml").write_text(
        "schema_version: 1\nfictive: true\nreason: zone de charge synthétique des tests M4a (plan T8) ; sim/ écrit par "
        "l'aide de test, aucune valeur écologique\n", encoding="utf-8")
    return {"states": states}


# ------------------------------------------------------------------ préconditions des fixtures
def queue(p) -> str:
    return f"code {p.returncode}\nSTDOUT: {p.stdout[-1500:]}\nSTDERR: {p.stderr[-1500:]}"


def exige_temps(temps) -> Path:
    """L'état final de la zone `temps` n'est lisible que si simulate puis assets ont réussi."""
    assert temps["make"].returncode == 0, "make dynamics simulate en échec :\n" + queue(temps["make"])
    assert temps["assets_10"].returncode == 0, "assets (pas de 10) en échec sur une zone avec sim/ :\n" + queue(temps["assets_10"])
    return temps["dir"]


def exige_charge(charge) -> Path:
    assert charge["assets"].returncode == 0, "assets en échec sur la zone de charge :\n" + queue(charge["assets"])
    return charge["dir"]
