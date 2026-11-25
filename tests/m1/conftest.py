"""Pytest M1a (mission 021) : lance `make prepare` puis `make biomes` sur le jeu fictif, une fois
par session, sans réseau, puis les tests lisent les sorties.

Aucune fixture ne saute un test (le script de CI refuse tout test sauté) : si make échoue, les
tests d'exécution échouent, et ceux qui lisent les sorties échouent sur « sortie absente ».
"""
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import helpers as H  # noqa: E402


@pytest.fixture(scope="session")
def runs():
    """Exécute prepare, biomes, trees (chaîne de M1a), puis la chaîne une seconde fois (rejeu)."""
    H.clean_outputs(H.ZONE)
    res = {}
    res["prepare"] = H.run_make("prepare")
    res["biomes"] = H.run_make("biomes")
    res["trees"] = H.run_make("trees")
    res["snapshot1"] = snapshot()
    res["prepare_2"] = H.run_make("prepare")
    res["biomes_2"] = H.run_make("biomes")
    res["trees_2"] = H.run_make("trees")
    res["snapshot2"] = snapshot()
    return res


def snapshot():
    """Contenu (pas les octets : les horodatages peuvent varier) des sorties rejouables."""
    import numpy as np
    out = {}
    for rel in ("grid.tif", "h0.tif", "chm_date.tif", "ser.tif", "forest_mask.tif",
                "stand_map.tif", "vegetation_map.tif"):
        p = H.ZONE / rel
        if p.is_file():
            arr, *_ = H.read_raster(p)
            out[rel] = arr.copy()
    try:
        rows = H.read_parquet(H.trees_init_path())
        out["trees_init"] = sorted(((r["x"], r["y"], r["species"], r["d130"]) for r in rows))
    except Exception:  # noqa: BLE001 - absence déjà signalée par les tests de sortie
        pass
    for t in ("plots", "trees", "flora"):
        try:
            rows = H.read_parquet(H.ZONE / "ifn" / f"{t}.parquet")
            out[f"ifn/{t}"] = sorted(repr(sorted(r.items())) for r in rows)
        except Exception:  # noqa: BLE001
            pass
    for rel in ("vegetation_map.csv", "ser.csv", "stand_map.csv"):
        p = H.ZONE / rel
        if p.is_file():
            out[rel] = p.read_text(encoding="utf-8")
    return out


@pytest.fixture(scope="session")
def grid(runs):
    p = H.ZONE / "grid.tif"
    assert p.is_file(), "grid.tif absent : make prepare n'a pas produit la grille"
    return H.Grid(p)


@pytest.fixture(scope="session")
def stands():
    return H.read_stands()


def need(rel: str) -> Path:
    p = H.ZONE / rel
    assert p.exists(), f"sortie absente : tests/fixtures/zone_fictive/{rel}"
    return p


@pytest.fixture(scope="session")
def alluvion_zone():
    """Zone variante : ser.gpkg à la forme brute IGN, où la voisine de plus longue frontière du
    couloir L3 n'est NI la plus grande en surface, NI la première, NI la dernière. Locaux (m) :

        H40  y 600-1000, x 0-1000   (grande surface, ne touche pas le couloir)
        H20  y 520-600,  x 0-1000   (petite surface, frontière de 1000 m avec L3)
        L3   y 420-520,  x 0-1000
        H10  y 0-420,    x 0-400    (frontière de 400 m avec L3)
        H30  y 0-420,    x 400-1000 (frontière de 600 m avec L3, plus grande surface des voisines)
    """
    name = "m1_alluvions"

    def mutate(zone_dir):
        H.write_ser_gpkg(zone_dir / "inputs" / "ser.gpkg", [
            ("H10", (0, 400, 0, 420)), ("H30", (400, 1000, 0, 420)),
            ("H20", (0, 1000, 520, 600)), ("H40", (0, 1000, 600, 1000)),
            ("L3", (0, 1000, 420, 520)),
        ])

    try:
        zone_dir, cfg = H.make_zone_copy(name, mutate)
        res = {"dir": zone_dir, "config": cfg}
        res["prepare"] = H.run_make("prepare", zone=name, config=cfg)
        res["biomes"] = H.run_make("biomes", zone=name, config=cfg)
        yield res
    finally:
        H.remove_zone_copy(name)


def _copy_zone_run(name, mutate, targets=("prepare", "biomes"), env_extra=None):
    """Zone variante : copie du jeu fictif, mutation des entrées, puis make des cibles."""
    zone_dir, cfg = H.make_zone_copy(name, mutate)
    res = {"dir": zone_dir, "config": cfg}
    for t in targets:
        res[t] = H.run_make(t, zone=name, config=cfg, env_extra=env_extra)
    return res


def _station_sans_valeur(zone_dir):
    """Rend nodata un bloc de station_type.tif (mailles de 20 m) au milieu de S02 : local
    x 100-300, y 600-800. Aucun type de station ne correspond : les cellules forestières du bloc
    n'ont pas de type de végétation (ou doivent être comblées et dites comblées)."""
    import rasterio
    with rasterio.open(zone_dir / "inputs" / "station_type.tif", "r+") as r:
        arr = r.read(1)
        # lignes depuis le nord : y local 800 -> ligne 10, y 600 -> ligne 20 ; x 100-300 -> colonnes 5-15
        arr[10:20, 5:15] = int(r.nodata)
        r.write(arr, 1)


ORPHAN_BLOCK = (100.0, 300.0, 600.0, 800.0)  # x0, x1, y0, y1 en m locaux


@pytest.fixture(scope="session")
def orphan_zone():
    name = "m1_orphelines"
    try:
        yield _copy_zone_run(name, _station_sans_valeur)
    finally:
        H.remove_zone_copy(name)


@pytest.fixture(scope="session")
def lcc_zone():
    """Chaîne prepare, biomes, trees lancée sous LC_ALL=C (locale sans UTF-8)."""
    name = "m1_lc_all_c"
    env = {"LC_ALL": "C", "LANG": "C", "LANGUAGE": "C"}
    try:
        yield _copy_zone_run(name, None, ("prepare", "biomes", "trees"), env)
    finally:
        H.remove_zone_copy(name)


@pytest.fixture(scope="session")
def sans_stands_zone():
    """prepare, puis suppression de inputs/nemeton_stands.gpkg, puis biomes (spec §2 : biomes lit
    stand_map, plus le GeoPackage)."""
    name = "m1_sans_stands"
    try:
        zone_dir, cfg = H.make_zone_copy(name)
        res = {"dir": zone_dir, "config": cfg}
        res["prepare"] = H.run_make("prepare", zone=name, config=cfg)
        (zone_dir / "inputs" / "nemeton_stands.gpkg").unlink()
        res["biomes"] = H.run_make("biomes", zone=name, config=cfg)
        yield res
    finally:
        H.remove_zone_copy(name)


# Houppier (spec §4.3) : c connu pour 09, 62, 64, 03 ; l'essence 61 n'a que a et b.
COEF_HOUPPIER = {
    "09": {"a": 0.10, "b": 1.12, "c": 0.20}, "62": {"a": 0.20, "b": 1.08, "c": 0.15},
    "64": {"a": 0.12, "b": 1.10, "c": 0.18}, "03": {"a": 0.11, "b": 1.09, "c": 0.22},
    "61": {"a": 0.15, "b": 1.10},
}
SANS_C = "61"


def _allometrie_houppier(zone_dir):
    H.write_allometry(zone_dir / "params" / "allometry.parquet", COEF_HOUPPIER)


def _allometrie_sans_09(zone_dir):
    H.write_allometry(zone_dir / "params" / "allometry.parquet",
                      {k: v for k, v in COEF_HOUPPIER.items() if k != "09"})


@pytest.fixture(scope="session")
def houppier_zone():
    name = "m1_houppier"
    try:
        yield _copy_zone_run(name, _allometrie_houppier, ("prepare", "biomes", "trees"))
    finally:
        H.remove_zone_copy(name)


@pytest.fixture(scope="session")
def sans_coefficient_zone():
    """Essence 09 (S01) sans aucun coefficient dans allometry.parquet : erreur explicite."""
    name = "m1_sans_coefficient"
    try:
        zone_dir, cfg = H.make_zone_copy(name, _allometrie_sans_09)
        res = {"dir": zone_dir, "config": cfg}
        res["prepare"] = H.run_make("prepare", zone=name, config=cfg)
        res["biomes"] = H.run_make("biomes", zone=name, config=cfg)
        res["trees"] = H.run_module_status("trees", cfg)
        yield res
    finally:
        H.remove_zone_copy(name)
