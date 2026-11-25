"""Suite de M4a (mission 045) : zone de charge synthétique `m4_charge` (plan T8). Son sim/ est écrit par l'aide de
test (helpers_m4_temps.build_charge_sim) : 100 013 vivants en 2022 ; 100 000 vivants et 13 morts en 2023 ; aucune
valeur écologique, zone marquée fictive. Côté assets : index, tuiles et point connu (700 012,5 ; 6 500 987,5)."""
import numpy as np
import pytest

import helpers_m4 as H
import helpers_m4_temps as T


@pytest.fixture(scope="module")
def charge_index(charge):
    return T.read_index(T.exige_charge(charge))


def test_assets_ecrit_les_deux_annees_de_la_charge(charge_index):
    assert [e["year"] for e in charge_index["years"]] == [2022, 2023]
    assert {e["year"]: e["instances"] for e in charge_index["years"]} == T.CHARGE_VIVANTS
    assert {e["year"]: e["dead"] for e in charge_index["years"]} == T.CHARGE_MORTS


@pytest.mark.parametrize("annee", [2022, 2023])
def test_les_tuiles_de_la_charge_portent_exactement_les_vivants(charge, annee):
    zdir = T.exige_charge(charge)
    st = charge["states"][annee]
    a = st["status"] == "alive"
    inst = T.collect_tileset(zdir / "tiles" / str(annee) / "tileset.json")
    assert len(inst["world"]) == T.CHARGE_VIVANTS[annee], f"{annee} : {len(inst['world'])} instances"
    m = T.nearest_match(inst["world"], st["x"], st["y"])
    assert m["n_ok"] == len(inst["world"]), f"{annee} : {len(inst['world']) - m['n_ok']} instances loin de tout arbre"
    assert sorted(m["tree_of"].tolist()) == np.nonzero(a)[0].tolist(), f"{annee} : instances != arbres vivants"
    assert T.tileset_extras(zdir / "tiles" / str(annee) / "tileset.json").get("instances") == T.CHARGE_VIVANTS[annee]


def test_le_point_connu_tombe_dans_la_tuile_nord_ouest_et_la_cellule_0(charge):
    # Fiche 047 : (700 012,5 ; 6 500 987,5), EPSG:2154 -> tuile t_700000_6500500, cell_id 0 (coin nord-ouest).
    zdir = T.exige_charge(charge)
    inst = T.collect_tileset(zdir / "tiles" / "2023" / "tileset.json")
    m = T.nearest_match(inst["world"], np.array([T.POINT_CONNU[0]]), np.array([T.POINT_CONNU[1]]))
    ici = np.nonzero(m["tree_of"] == 0)[0]
    assert len(ici) == 1, f"{len(ici)} instances au point connu"
    assert inst["tile"][ici[0]] == "t_700000_6500500", f"point connu dans {inst['tile'][ici[0]]}"
    fiche = H.read_sheets(zdir)["t_700000_6500500"]
    c0 = next((c for c in fiche["cells"] if c["cell_id"] == 0), None)
    assert c0 is not None, "cellule 0 absente de la fiche t_700000_6500500"
    st = charge["states"][2023]
    dans0 = (st["status"] == "alive") & (np.floor((H.Y0 - st["y"]) / H.RES) == 0) & (np.floor((st["x"] - H.X0) / H.RES) == 0)
    e = next(e for e in c0["years"] if e["year"] == 2023)
    assert T.close(e["stems_ha"], dans0.sum() / T.AIRE_CELLULE_HA), f"cellule 0 : stems_ha {e['stems_ha']}"


def test_les_fiches_de_la_charge_sont_conformes(charge):
    zdir = T.exige_charge(charge)
    p = H.validate("cell_sheet", *[str(p) for p in sorted((zdir / "web" / "cells").glob("*.json"))])
    assert p.returncode == 0, p.stdout[-1500:]
    p = H.validate("tiles_index", str(zdir / "tiles" / "index.json"))
    assert p.returncode == 0, p.stdout[-1500:]
