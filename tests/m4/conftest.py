"""Pytest M4a, tranche « état initial » (mission 030) : lance `make prepare biomes trees assets` sur le
jeu fictif, une fois par session, sans réseau, puis les tests lisent les sorties. Des zones variantes
(copies sous data/m4_*, supprimées ensuite) servent de tests discriminants : chacune change UNE chose
(un arbre, une cellule, un polygone, l'année) et les tests exigent que le résultat change exactement là.

Aucune fixture ne saute un test (la CI refuse tout test sauté) : si make échoue, les tests d'exécution
échouent, et ceux qui lisent les sorties échouent sur « sortie absente ».
"""
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import helpers_m4 as H  # noqa: E402


def snapshot(zone_dir: Path) -> dict:
    """Contenu des sorties de assets : octets des json/gltf/bin, valeurs et géoréférence des rasters
    (un TIFF peut porter un horodatage : on compare ce qu'il dit, pas ses octets)."""
    import hashlib

    import rasterio
    out = {}
    for d in ("tiles", "web", "assets"):
        base = zone_dir / d
        for p in (sorted(base.rglob("*")) if base.is_dir() else []):
            if not p.is_file():
                continue
            rel = str(p.relative_to(zone_dir))
            if p.suffix == ".tif":
                with rasterio.open(p) as r:
                    arrs = [r.read(i + 1) for i in range(r.count)]
                    out[rel] = (r.transform.to_gdal(), r.crs.to_epsg(), r.nodata, r.overviews(1),
                                [hashlib.sha1(a.tobytes()).hexdigest() for a in arrs])
            else:
                out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


@pytest.fixture(scope="session")
def chaine():
    """make prepare biomes trees assets sur zone_fictive, depuis des sorties effacées ; puis le rejeu
    (make assets seul), avec l'empreinte des fichiers hors `assets` avant et après, et celle des sorties."""
    # SYLVIGENESE_M4_REUSE=1 (confort du développeur, jamais en CI) : ne pas effacer ni rejouer prepare/biomes/trees,
    # seulement assets, pour ne pas retirer leurs sorties à un autre agent qui travaille sur le même jeu fictif.
    # SYLVIGENESE_M4_REUSE=2 : ne rien lancer, lire les sorties présentes (mise au point des tests).
    if os.environ.get("SYLVIGENESE_M4_REUSE") == "2":
        res = {"make": subprocess.CompletedProcess([], 0, "", ""), "make_2": subprocess.CompletedProcess([], 0, "", "")}
        res["sorties_1"] = res["sorties_2"] = snapshot(H.ZONE)
        res["hors_assets_1"] = res["hors_assets_2"] = H.tree_files(H.ZONE)
        return res
    if os.environ.get("SYLVIGENESE_M4_REUSE") == "1":
        H.clean_asset_outputs(H.ZONE)
        H.remove_sim(H.ZONE)
        res = {"make": H.run_make("assets")}
    else:
        H.clean_chain_outputs(H.ZONE)
        res = {"make": H.run_make(*H.CHAIN)}
    res["sorties_1"] = snapshot(H.ZONE)
    res["hors_assets_1"] = H.tree_files(H.ZONE)
    res["make_2"] = H.run_make("assets")
    res["sorties_2"] = snapshot(H.ZONE)
    res["hors_assets_2"] = H.tree_files(H.ZONE)
    return res


@pytest.fixture(scope="session")
def oracle(chaine):
    return H.Oracle(H.ZONE)


@pytest.fixture(scope="session")
def instances(chaine, oracle):
    inst = H.collect_instances(H.ZONE)
    m = H.match_instances(inst["world"], oracle.trees["x"], oracle.trees["y"]) if len(inst["world"]) else None
    return {"inst": inst, "match": m}


@pytest.fixture(scope="session")
def sheets(chaine):
    return H.read_sheets(H.ZONE)


# ------------------------------------------------------------------ zones variantes
def _build(name, mutate, t0=None, etapes=None):
    """Copie de la zone, mutation, puis `assets` seul, ou `make <etapes>` (ex. trees assets) si demandé."""
    zone_dir, cfg = H.clone_zone(name, mutate, t0)
    res = {"dir": zone_dir, "config": cfg, "name": name}
    res["run"] = H.run_make(*etapes, zone=name, config=cfg) if etapes else H.run_assets(cfg)
    return res


def _id_arbre(essence=None):
    """Un arbre au centre de la distribution des hauteurs (et d'une essence donnée), loin des bords."""
    t = H.read_trees_init(H.ZONE)
    ok = (t["x"] < H.X0 + 900) & (t["x"] > H.X0 + 100) & (t["y"] > H.Y0 - 900) & (t["y"] < H.Y0 - 100)
    if essence:
        ok &= t["species"] == essence
    idx = np.nonzero(ok)[0]
    idx = idx[np.argsort(t["h"][idx], kind="stable")]
    return str(t["tree_id"][int(idx[len(idx) // 2])])


def _index_par_id(zone_dir, tid):
    return list(map(str, H.read_trees_init(zone_dir)["tree_id"])).index(tid)


@pytest.fixture(scope="session")
def zone_h(chaine):
    """Un seul arbre voit sa hauteur multipliée par 1,5 : une seule instance change, de taille."""
    tid = _id_arbre()
    info = {"tid": tid}

    def mut(d):
        t = H.read_trees_init(d)
        i = _index_par_id(d, tid)
        info.update(x=float(t["x"][i]), y=float(t["y"][i]), h_avant=float(t["h"][i]))
        h = t["h"].copy()
        h[i] = h[i] * 1.5
        H.write_trees_init(d, {"h": h})

    try:
        yield {**_build("m4_h", mut), **info}
    finally:
        H.remove_zone_copy("m4_h")


@pytest.fixture(scope="session")
def zone_deplace(chaine):
    """Un seul arbre est déplacé de 7,0 m vers l'est : une instance disparaît d'un endroit et apparaît ailleurs."""
    tid = _id_arbre()
    info = {"tid": tid}

    def mut(d):
        t = H.read_trees_init(d)
        i = _index_par_id(d, tid)
        info.update(x=float(t["x"][i]), y=float(t["y"][i]))
        x = t["x"].copy()
        x[i] = x[i] + 7.0
        H.write_trees_init(d, {"x": x})

    try:
        yield {**_build("m4_deplace", mut), **info}
    finally:
        H.remove_zone_copy("m4_deplace")


@pytest.fixture(scope="session")
def zone_sans_arbre(chaine):
    """Un seul arbre est retiré de trees_init : 14 079 instances."""
    tid = _id_arbre()
    info = {"tid": tid}

    def mut(d):
        t = H.read_trees_init(d)
        i = _index_par_id(d, tid)
        info.update(x=float(t["x"][i]), y=float(t["y"][i]))
        H.drop_tree_row(d, i)

    try:
        yield {**_build("m4_sans_arbre", mut), **info}
    finally:
        H.remove_zone_copy("m4_sans_arbre")


@pytest.fixture(scope="session")
def zone_essence(chaine):
    """Un résineux (61) devient chêne (03, feuillu) : une instance change de modèle, aucune de place."""
    tid = _id_arbre("61")
    info = {"tid": tid}

    def mut(d):
        t = H.read_trees_init(d)
        i = _index_par_id(d, tid)
        info.update(x=float(t["x"][i]), y=float(t["y"][i]))
        sp = t["species"].astype(object).copy()
        sp[i] = "03"
        H.write_trees_init(d, {"species": sp})

    try:
        yield {**_build("m4_essence", mut), **info}
    finally:
        H.remove_zone_copy("m4_essence")


@pytest.fixture(scope="session")
def zone_vegetation(chaine, oracle):
    """Une seule cellule change de type de végétation (vegetation_map.tif) : une seule fiche change."""
    import rasterio
    r0, c0 = 20, 10     # dans la forêt, hors trouée (trouée : x 400-600, y 100-300 locaux)
    cid = r0 * H.NCOLS + c0
    avant = int(oracle.veg[r0, c0])
    apres = 2 if avant != 2 else 3
    info = {"cell_id": cid, "avant": avant, "apres": apres}

    def mut(d):
        with rasterio.open(d / "vegetation_map.tif", "r+") as r:
            a = r.read(1)
            a[r0, c0] = apres
            r.write(a, 1)

    try:
        yield {**_build("m4_vegetation", mut), **info}
    finally:
        H.remove_zone_copy("m4_vegetation")


@pytest.fixture(scope="session")
def zone_stand(chaine):
    """L'essence du polygone S02 passe de 61 à 62 À LA SOURCE (inputs/nemeton_stands.gpkg et stands.parquet,
    que `trees` lit), puis `make trees assets` : les arbres de S02 prennent 62 (spec §4.1), donc les fiches aussi."""
    import sqlite3

    import pyarrow.parquet as pq

    def mut(d):
        c = sqlite3.connect(d / "inputs" / "nemeton_stands.gpkg")
        c.execute("update stands set species_espar = '62' where species_espar = '61'")
        c.commit()
        c.close()
        t = pq.read_table(d / "stands.parquet")
        sp = [("62" if s == "61" else s) for s in t.column("species").to_pylist()]
        i = t.schema.get_field_index("species")
        pq.write_table(t.set_column(i, t.schema.field(i), [sp]), d / "stands.parquet")

    try:
        yield _build("m4_stand", mut, etapes=("trees", "assets"))
    finally:
        H.remove_zone_copy("m4_stand")


@pytest.fixture(scope="session")
def zone_t0(chaine):
    """simulate.t0 = 2031 : la tuile et les fiches portent l'année 2031."""
    try:
        yield _build("m4_t0", None, t0=2031)
    finally:
        H.remove_zone_copy("m4_t0")


# ------------------------------------------------------------------ refus (saisie incomplète, hors référentiel, doublon)
def _sans_trees_init(d):
    import shutil
    shutil.rmtree(d / "trees_init")


def _sans_vegetation_map(d):
    (d / "vegetation_map.tif").unlink()


def _essence_hors_referentiel(d):
    t = H.read_trees_init(d)
    sp = t["species"].astype(object).copy()
    sp[0] = "99"
    H.write_trees_init(d, {"species": sp})


def _tree_id_en_double(d):
    t = H.read_trees_init(d)
    ids = t["tree_id"].astype(object).copy()
    ids[1] = ids[0]
    H.write_trees_init(d, {"tree_id": ids})


REFUS = {
    "sans_trees_init": (_sans_trees_init, ("trees_init",)),
    "sans_vegetation_map": (_sans_vegetation_map, ("vegetation_map",)),
    "essence_hors_referentiel": (_essence_hors_referentiel, ("99", "species", "essence")),
    "tree_id_en_double": (_tree_id_en_double, ("tree_id", "double", "doublon", "unique")),
}


@pytest.fixture(scope="module", params=list(REFUS))
def refus(request, chaine):
    nom = "m4_refus_" + request.param
    mutate, mots = REFUS[request.param]
    try:
        d, cfg = H.clone_zone(nom, mutate)
        p = H.run_assets(cfg)
        yield request.param, d, p, mots
    finally:
        H.remove_zone_copy(nom)


# ================================================================== suite de M4a : la vue dans le temps (mission 045)
# Zones sous data/ (hors dépôt), supprimées en fin de session. Aucun saut : si `simulate` ou `assets` échoue,
# chaque test qui en dépend échoue en disant la commande et sa sortie.
import json  # noqa: E402
import shutil  # noqa: E402

import pyarrow as pa  # noqa: E402

import helpers_m4_temps as T  # noqa: E402

TEMPS = "m4_temps"


_queue = T.queue
exige_temps = T.exige_temps
exige_charge = T.exige_charge


@pytest.fixture(scope="session")
def temps(chaine):
    """Copie du jeu fictif après la chaîne ; `make dynamics simulate` sur 15 ans (2022 à 2037, plan §6 point 3) ;
    des années périmées plantées (tiles/2021, g_2021.tif) ; puis `assets` au pas de 5, au pas de 10, et encore au pas
    de 10 (rejeu). L'état final est celui du pas de 10 (config.yml du dépôt)."""
    import rasterio
    try:
        zdir, _ = H.clone_zone(TEMPS)
        cfg10 = T.write_config(zdir, TEMPS, T.sim_block(), {"year_step": T.STEP}, "config_m4_pas10.yml")
        cfg5 = T.write_config(zdir, TEMPS, T.sim_block(), {"year_step": T.STEP_FIN}, "config_m4_pas5.yml")
        res = {"dir": zdir, "name": TEMPS, "config": cfg10, "config_5": cfg5}
        res["make"] = H.run_make("dynamics", "simulate", zone=TEMPS, config=cfg10)
        # années périmées : t0 valait 2021 avant le 25/11/2026 (plan §1, point 6)
        (zdir / "tiles" / "2021").mkdir(parents=True)
        (zdir / "tiles" / "2021" / "tileset.json").write_text('{"asset": {"version": "1.1"}}', encoding="utf-8")
        (zdir / "web" / "rasters").mkdir(parents=True)
        with rasterio.open(zdir / "grid.tif") as g:
            prof = {**g.profile, "dtype": "float32", "count": 1, "nodata": -1.0}
        with rasterio.open(zdir / "web" / "rasters" / "g_2021.tif", "w", **prof) as w:
            w.write(np.zeros((H.NROWS, H.NCOLS), dtype="float32"), 1)
        res["assets_5"] = H.run_assets(cfg5)
        res["apres_5"] = {"tiles": sorted(p.name for p in (zdir / "tiles").iterdir()) if (zdir / "tiles").is_dir() else [],
                          "rasters": sorted(p.name for p in (zdir / "web" / "rasters").glob("g_*.tif")),
                          "index": (json.loads((zdir / "tiles" / "index.json").read_text(encoding="utf-8"))
                                    if (zdir / "tiles" / "index.json").is_file() else None)}
        res["assets_10"] = H.run_assets(cfg10)
        res["sorties_10a"] = snapshot(zdir)
        res["assets_10b"] = H.run_assets(cfg10)
        res["sorties_10b"] = snapshot(zdir)
        yield res
    finally:
        H.remove_zone_copy(TEMPS)


@pytest.fixture(scope="session")
def temps_index(temps):
    return T.read_index(exige_temps(temps))


@pytest.fixture(scope="session")
def temps_sheets(temps):
    sh = H.read_sheets(exige_temps(temps))
    assert sh, "aucune fiche web/cells/*.json"
    return sh


@pytest.fixture(scope="session")
def temps_cells(temps):
    zdir = exige_temps(temps)
    return T.cell_year_table(T.cells_rows(zdir))


@pytest.fixture(scope="session")
def temps_instances(temps):
    """Par année retenue : arbres de la partition, instances du tileset de l'année, appariement."""
    zdir = exige_temps(temps)
    out = {}
    for y in T.retained_years(T.T0, T.YEARS, T.STEP):
        tr = T.trees_of_year(zdir, y)
        ts = zdir / "tiles" / str(y) / "tileset.json"
        assert ts.is_file(), f"tiles/{y}/tileset.json absent"
        inst = T.collect_tileset(ts)
        out[y] = {"trees": tr, "inst": inst, "match": T.nearest_match(inst["world"], tr["x"], tr["y"])}
    return out


# ------------------------------------------------------------------ refus de assets en mode sim (code 2)
def _cfg_sim(**kw):
    return lambda zdir, nom: T.write_config(zdir, nom, T.sim_block(**kw), {"year_step": T.STEP}, "config_m4_refus.yml")


def _cfg_nominale(zdir, nom):
    return T.write_config(zdir, nom, T.sim_block(), {"year_step": T.STEP}, "config_m4_refus.yml")


def _sans_run_json(zdir):
    (zdir / "sim" / "run.json").unlink()


def _sans_partition(kind, year):
    def f(zdir):
        shutil.rmtree(zdir / "sim" / kind / f"year={year}")
    return f


def _sans_h_dom_m(zdir):
    for p in sorted((zdir / "sim" / "cells").rglob("*.parquet")):
        T.rewrite_parquet(p, lambda t: t.drop_columns([c for c in ("h_dom_m",) if c in t.schema.names]))


def _arbres_2032(fn):
    def f(zdir):
        for p in sorted((zdir / "sim" / "trees" / "year=2032").glob("*.parquet")):
            T.rewrite_parquet(p, fn)
    return f


def _essence_99(t):
    i = t.schema.get_field_index("species")
    v = t.column("species").to_pylist()
    v[0] = "99"
    return t.set_column(i, t.schema.field(i), pa.array(v, t.schema.field(i).type))


def _tree_id_double(t):
    i = t.schema.get_field_index("tree_id")
    v = t.column("tree_id").to_pylist()
    v[1] = v[0]
    return t.set_column(i, t.schema.field(i), pa.array(v, t.schema.field(i).type))


# nom : (mutation de la copie, config, mots dont l'un doit être dans le message, code exigé)
REFUS_TEMPS = {
    "run_json_absent": (_sans_run_json, _cfg_nominale, ("run.json",), 2),
    "partition_trees_2032_absente": (_sans_partition("trees", 2032), _cfg_nominale, ("2032",), 2),
    "partition_cells_2032_absente": (_sans_partition("cells", 2032), _cfg_nominale, ("2032",), 2),
    "graine_differente_du_run": (None, _cfg_sim(seed=43), ("seed", "graine"), 2),
    "t0_different_du_run": (None, _cfg_sim(t0=2023), ("t0",), 2),
    "years_different_du_run": (None, _cfg_sim(years=14), ("years",), 2),
    "sans_bloc_assets": (None, lambda zdir, nom: T.write_config(zdir, nom, T.sim_block(), None, "config_m4_refus.yml"),
                         ("year_step", "bloc assets", "bloc « assets »", "bloc `assets`"), 2),
    "year_step_nul": (None, lambda zdir, nom: T.write_config(zdir, nom, T.sim_block(), {"year_step": 0}, "config_m4_refus.yml"),
                      ("year_step",), 2),
    "sans_colonne_h_dom_m": (_sans_h_dom_m, _cfg_nominale, ("h_dom_m",), 2),
    # cas du terrain sans code fixé par le plan : un refus (code non nul) qui nomme la cause
    "essence_hors_referentiel": (_arbres_2032(_essence_99), _cfg_nominale, ("99",), None),
    "tree_id_en_double": (_arbres_2032(_tree_id_double), _cfg_nominale, ("tree_id", "double", "doublon", "unique"), None),
}


@pytest.fixture(scope="module", params=list(REFUS_TEMPS))
def refus_temps(request, temps):
    """Copie (liens physiques) de la zone `temps` sans sorties de assets, une seule chose cassée, puis assets."""
    assert temps["make"].returncode == 0, "make dynamics simulate en échec :\n" + _queue(temps["make"])
    # nom de zone NEUTRE : le message de refus cite le chemin de la zone, qui ne doit contenir aucun des mots attendus
    nom = f"m4_refus_t{sorted(REFUS_TEMPS).index(request.param):02d}"
    mutate, config, mots, code = REFUS_TEMPS[request.param]
    zdir = H.ROOT / "data" / nom
    try:
        T.link_copy(temps["dir"], zdir)
        if mutate is not None:
            mutate(zdir)
        p = H.run_assets(config(zdir, nom))
        yield {"cas": request.param, "dir": zdir, "proc": p, "mots": mots, "code": code}
    finally:
        H.remove_zone_copy(nom)


@pytest.fixture(scope="module")
def refus_atomique(temps):
    """Copie de la zone `temps` AVEC ses sorties valides (tiles/, web/ copiés), puis une partition retenue retirée :
    le refus doit laisser les sorties précédentes intactes (écriture atomique, T6)."""
    zdir = exige_temps(temps)
    nom = "m4_refus_tat"
    d = H.ROOT / "data" / nom
    try:
        T.link_copy(zdir, d, copy_dirs=("tiles", "web", "assets", "massif"))
        cfg = _cfg_nominale(d, nom)
        avant = snapshot(d)
        shutil.rmtree(d / "sim" / "trees" / "year=2032")
        p = H.run_assets(cfg)
        yield {"dir": d, "proc": p, "avant": avant, "apres": snapshot(d)}
    finally:
        H.remove_zone_copy(nom)


# ------------------------------------------------------------------ zone de charge synthétique (T8)
@pytest.fixture(scope="session")
def charge(chaine, oracle):
    try:
        zdir, _ = H.clone_zone(T.CHARGE)
        cfg = T.write_config(zdir, T.CHARGE, {"level": "massif", "seed": 42, "t0": 2022, "years": 1, "threads": 1,
                                         "recruitment": "ifn_direct"},
                             {"year_step": T.STEP}, "config_m4_charge.yml")
        info = T.build_charge_sim(zdir, cfg, sorted(oracle.forest_cells()))
        res = {"dir": zdir, "name": T.CHARGE, "config": cfg, **info}
        res["assets"] = H.run_assets(cfg)
        yield res
    finally:
        H.remove_zone_copy(T.CHARGE)
