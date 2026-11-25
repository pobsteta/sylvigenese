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
def _build(name, mutate, t0=None):
    zone_dir, cfg = H.clone_zone(name, mutate, t0)
    res = {"dir": zone_dir, "config": cfg, "name": name}
    res["run"] = H.run_assets(cfg)
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
    """L'essence du polygone S02 passe de 61 à 62 dans stands.parquet : les cellules de S02 le disent."""
    import pyarrow.parquet as pq

    def mut(d):
        t = pq.read_table(d / "stands.parquet")
        sp = [("62" if s == "61" else s) for s in t.column("species").to_pylist()]
        i = t.schema.get_field_index("species")
        pq.write_table(t.set_column(i, t.schema.field(i), [sp]), d / "stands.parquet")

    try:
        yield _build("m4_stand", mut)
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
