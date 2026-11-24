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
    """Exécute prepare, biomes, puis prepare une seconde fois (rejeu). Renvoie les résultats."""
    H.clean_outputs(H.ZONE)
    res = {}
    res["prepare"] = H.run_make("prepare")
    res["biomes"] = H.run_make("biomes")
    res["snapshot1"] = snapshot()
    res["prepare_2"] = H.run_make("prepare")
    res["snapshot2"] = snapshot()
    return res


def snapshot():
    """Contenu (pas les octets : les horodatages peuvent varier) des sorties rejouables."""
    import numpy as np
    out = {}
    for rel in ("grid.tif", "h0.tif", "chm_date.tif", "ser.tif", "forest_mask.tif"):
        p = H.ZONE / rel
        if p.is_file():
            arr, *_ = H.read_raster(p)
            out[rel] = arr.copy()
    try:
        rows = H.read_parquet(H.trees_init_path())
        out["trees_init"] = sorted(((r["x"], r["y"], r["species"], r["d130"]) for r in rows))
    except Exception:  # noqa: BLE001 - absence déjà signalée par les tests de sortie
        pass
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
