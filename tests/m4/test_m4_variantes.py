"""Zones variantes : on change UN arbre, UNE cellule, UN polygone ou l'année ; le résultat change exactement là
(tests discriminants, fiche 030). Les zones sont des copies sous data/m4_*, supprimées après."""
import json

import numpy as np
import pytest

import helpers_m4 as H


@pytest.fixture(scope="module")
def base(chaine):
    vue, inst, m = H.per_tree_view(H.ZONE)
    return vue


def _ok(z):
    assert z["run"].returncode == 0, f"assets sur {z['name']} : code {z['run'].returncode}\n{z['run'].stderr[-1500:]}"


def _cle(x, y):
    a, b = H.lattice_key(np.array([x]), np.array([y]))
    return (int(a[0]), int(b[0]))


def _diff(base, var):
    """Clés ajoutées, retirées, et clés communes dont (échelle Y, modèle) change."""
    ajoutees = set(var) - set(base)
    retirees = set(base) - set(var)
    changees = {k for k in set(base) & set(var)
                if abs(base[k][0] - var[k][0]) > 1e-4 * max(1.0, base[k][0]) or base[k][1] != var[k][1]}
    return ajoutees, retirees, changees


def test_un_arbre_plus_haut_change_une_seule_instance_et_sa_taille(base, zone_h):
    _ok(zone_h)
    var, _, _ = H.per_tree_view(zone_h["dir"])
    ajoutees, retirees, changees = _diff(base, var)
    k = _cle(zone_h["x"], zone_h["y"])
    assert (ajoutees, retirees, changees) == (set(), set(), {k}), \
        f"attendu : seule l'instance {k} change ; ajoutées {len(ajoutees)}, retirées {len(retirees)}, changées {len(changees)}"
    assert var[k][1] == base[k][1], "le modèle ne doit pas changer"
    assert abs(var[k][0] / base[k][0] - 1.5) < 0.02, f"échelle ×{var[k][0] / base[k][0]:.3f} pour une hauteur ×1,5"


def test_un_arbre_deplace_change_une_seule_position(base, zone_deplace):
    _ok(zone_deplace)
    var, inst, m = H.per_tree_view(zone_deplace["dir"])
    assert len(var) == len(base) == 14080
    ancien = _cle(zone_deplace["x"], zone_deplace["y"])
    nouveau = _cle(zone_deplace["x"] + 7.0, zone_deplace["y"])
    ajoutees, retirees, changees = _diff(base, var)
    assert (ajoutees, retirees, changees) == ({nouveau}, {ancien}, set()), \
        f"ajoutées {sorted(ajoutees)[:3]}, retirées {sorted(retirees)[:3]}, changées {len(changees)}"
    assert var[nouveau] == base[ancien], "l'arbre déplacé garde sa taille et son modèle"


def test_un_arbre_retire_retire_une_seule_instance(base, zone_sans_arbre):
    _ok(zone_sans_arbre)
    var, inst, _ = H.per_tree_view(zone_sans_arbre["dir"])
    assert len(inst["world"]) == 14079
    ajoutees, retirees, changees = _diff(base, var)
    assert (ajoutees, retirees, changees) == (set(), {_cle(zone_sans_arbre["x"], zone_sans_arbre["y"])}, set())


def test_un_arbre_change_de_groupe_change_de_modele_et_rien_d_autre(base, zone_essence):
    _ok(zone_essence)
    var, _, _ = H.per_tree_view(zone_essence["dir"])
    ajoutees, retirees, changees = _diff(base, var)
    k = _cle(zone_essence["x"], zone_essence["y"])
    assert (ajoutees, retirees, changees) == (set(), set(), {k}), f"changées : {len(changees)}"
    assert var[k][1] != base[k][1], "le modèle devrait passer de résineux à feuillu"
    autres_feuillus = {v[1] for key, v in base.items() if key != k and v[1] == var[k][1]}
    assert autres_feuillus, "le nouveau modèle doit être celui des autres feuillus"


def test_une_cellule_dont_le_type_change_change_une_seule_fiche(chaine, zone_vegetation, oracle):
    _ok(zone_vegetation)
    avant = H.sheet_cells(H.read_sheets(H.ZONE))
    apres = H.sheet_cells(H.read_sheets(zone_vegetation["dir"]))
    assert avant.keys() == apres.keys()
    differentes = [cid for cid in avant if avant[cid] != apres[cid]]
    assert differentes == [zone_vegetation["cell_id"]], f"fiches changées : {differentes[:10]}"
    nom = oracle.veg_names[zone_vegetation["apres"]]
    assert apres[zone_vegetation["cell_id"]]["vegetation_type"] == nom
    assert avant[zone_vegetation["cell_id"]]["vegetation_type"] == oracle.veg_names[zone_vegetation["avant"]]


def test_un_polygone_dont_l_essence_change_change_ses_cellules(chaine, zone_stand, oracle):
    _ok(zone_stand)
    avant = H.sheet_cells(H.read_sheets(H.ZONE))
    apres = H.sheet_cells(H.read_sheets(zone_stand["dir"]))
    s2 = [cid for cid in avant if oracle.cell_values(cid)["stand"] == "S02"]
    assert len(s2) > 100
    for cid in s2:
        codes = {e["species"] for e in apres[cid]["years"][0]["composition"]}
        assert "62" in codes, f"cellule {cid} (S02) : l'essence 62 du polygone est absente de {codes}"
    hors = [cid for cid in avant if cid not in set(s2)]
    assert [cid for cid in hors if avant[cid] != apres[cid]] == [], "des cellules hors de S02 ont changé"


def test_l_annee_vient_de_simulate_t0(zone_t0):
    _ok(zone_t0)
    ts = H.find_tilesets(zone_t0["dir"])
    assert [p.parent.name for p in ts] == ["2031"], f"tuiles : {[str(p) for p in ts]}"
    for c in H.sheet_cells(H.read_sheets(zone_t0["dir"])).values():
        assert [y["year"] for y in c["years"]] == [2031]
    assert H.validate("assets.tileset", str(ts[0])).returncode == 0


def test_les_variantes_ne_touchent_pas_la_zone_de_reference(chaine, zone_h):
    # La copie est écrite sous data/ ; la zone fictive du dépôt garde ses 14 080 instances.
    assert len(H.collect_instances(H.ZONE)["world"]) == 14080
