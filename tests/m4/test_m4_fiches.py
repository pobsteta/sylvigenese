"""Fiches de cellule web/cells/<tuile>.json : cohérence avec vegetation_map, stand_map, station_type, h0,
stands et trees_init ; mention « provisoire » ; volume et carbone vides et signalés (spec §1, §9, §10, §11)."""
import numpy as np
import pytest

import helpers_m4 as H


@pytest.fixture(scope="module")
def cells(sheets):
    assert sheets, "aucune fiche web/cells/*.json"
    c = H.sheet_cells(sheets)
    assert c, "fiches sans cellule"
    return c


def test_le_nom_du_fichier_est_la_tuile(sheets):
    for stem, s in sheets.items():
        assert s["tile"] == stem, f"web/cells/{stem}.json porte tile = {s['tile']!r}"


def test_aucune_cellule_en_double_entre_les_fiches(sheets):
    ids = [c["cell_id"] for s in sheets.values() for c in s["cells"]]
    assert len(ids) == len(set(ids))


def test_les_cellules_des_fiches_sont_les_cellules_forestieres(cells, oracle):
    # Toute cellule qui a un type de végétation (donc forestière, spec §11 M1) a sa fiche, et rien d'autre.
    attendu = oracle.forest_cells()
    assert len(attendu) == 1536
    assert set(cells) == attendu, \
        f"manquantes : {len(attendu - set(cells))}, en trop : {len(set(cells) - attendu)}"


def test_chaque_cellule_qui_porte_un_arbre_a_sa_fiche(cells, oracle):
    assert set(map(int, oracle.tree_cell)) <= set(cells)


def test_cell_id_est_le_rang_ligne_par_ligne_de_grid_tif_et_x_y_le_centre(cells):
    for cid, c in cells.items():
        x, y = H.cell_centre(cid)
        assert abs(c["x"] - x) < 0.5 and abs(c["y"] - y) < 0.5, \
            f"cellule {cid} : centre attendu ({x}, {y}), fiche ({c['x']}, {c['y']})"


def test_station_et_type_de_vegetation_sont_ceux_des_rasters_et_de_leurs_csv(cells, oracle):
    for cid, c in cells.items():
        v = oracle.cell_values(cid)
        assert c["station_type"] == v["station_type"], f"cellule {cid} : station {c['station_type']!r} != {v['station_type']!r}"
        assert c["vegetation_type"] == v["vegetation_type"], f"cellule {cid} : type {c['vegetation_type']!r} != {v['vegetation_type']!r}"


def test_les_noms_viennent_des_csv_et_non_d_un_indice(cells, oracle):
    # Spec §8 : catégories codées par leur nom, jamais par un indice.
    assert all(not str(c["vegetation_type"]).isdigit() and not str(c["station_type"]).isdigit() for c in cells.values())
    assert {c["vegetation_type"] for c in cells.values()} <= set(oracle.veg_names.values())
    assert {c["station_type"] for c in cells.values()} <= set(oracle.station_names.values())


def test_h0_de_chaque_cellule_est_renseigne_et_positif(cells, oracle):
    # Une cellule forestière a une hauteur dominante H0 (spec §5) : sinon la fiche décrirait une cellule sans peuplement.
    for cid in cells:
        h0 = oracle.cell_values(cid)["h0"]
        assert h0 != oracle.h0_nd and h0 > 0, f"cellule {cid} : h0 = {h0}"


def test_composition_codes_au_referentiel_et_parts_sommant_a_un(cells):
    groupe = H.species_group()
    for cid, c in cells.items():
        for y in c["years"]:
            comp = y["composition"]
            assert comp, f"cellule {cid} : composition vide pour une cellule forestière"
            codes = [e["species"] for e in comp]
            assert len(codes) == len(set(codes)), f"cellule {cid} : essence en double dans la composition"
            assert set(codes) <= set(groupe), f"cellule {cid} : essences hors contracts/species.csv : {set(codes) - set(groupe)}"
            assert abs(sum(e["share"] for e in comp) - 1.0) < 1e-6, f"cellule {cid} : parts = {sum(e['share'] for e in comp)}"


def test_composition_contient_l_essence_du_polygone_et_celles_des_arbres(cells, oracle):
    # « Cohérentes avec stands » : l'essence du polygone de la cellule figure dans sa composition ;
    # et chaque essence d'un arbre détecté dans la cellule y figure aussi.
    for cid, c in cells.items():
        codes = {e["species"] for e in c["years"][0]["composition"]}
        stand = oracle.cell_values(cid)["stand"]
        if stand is not None:
            assert oracle.stand_species[stand] in codes, f"cellule {cid} ({stand}) : essence {oracle.stand_species[stand]} absente de {codes}"
        assert oracle.species_in_cell(cid) <= codes, f"cellule {cid} : arbres d'essences {oracle.species_in_cell(cid) - codes} absentes de la composition"


def test_une_seule_annee_celle_du_dossier_de_tuiles(cells):
    annee = int(H.find_tilesets(H.ZONE)[0].parent.name)
    for cid, c in cells.items():
        assert [y["year"] for y in c["years"]] == [annee], f"cellule {cid} : années {[y['year'] for y in c['years']]}"


def test_toutes_les_fiches_sont_provisoires(cells):
    # Spec §10 : « Les vues affichent « résultat provisoire » dès qu'un paramètre utilisé l'est » ; allometry,
    # détection, types de végétation du jeu fictif : tout est provisoire.
    for cid, c in cells.items():
        assert all(y["provisoire"] is True for y in c["years"]), f"cellule {cid} : provisoire != true"


def test_volume_et_carbone_sont_vides_jamais_inventes(cells):
    # `post` (après M3) calcule le volume et le carbone ; en M4a-état initial la fiche les laisse VIDES :
    # null, ou 0 signalé (jamais un nombre positif inventé : « signaler plutôt que deviner »).
    for cid, c in cells.items():
        for y in c["years"]:
            for k in ("volume_m3_ha", "carbon_t_ha"):
                assert y[k] is None or y[k] == 0, f"cellule {cid} : {k} = {y[k]!r} (valeur inventée ?)"


def test_le_vide_du_volume_et_du_carbone_est_dit_dans_la_fiche(sheets):
    # Le signalement est une phrase DANS les fichiers de fiche (champ libre ou note) qui nomme le volume ou le
    # carbone et dit qu'ils ne sont pas calculés (non calculé, vide, absent, indisponible, post, M3...).
    for stem, s in sheets.items():
        textes = [H.sans_accent(t) for t in H.string_values(s)]
        vol = [t for t in textes if "volume" in t and any(m in t for m in H.SIGNAL_VIDE)]
        car = [t for t in textes if ("carbone" in t or "carbon" in t) and any(m in t for m in H.SIGNAL_VIDE)]
        assert vol, f"web/cells/{stem}.json : aucune phrase ne dit que le volume est vide"
        assert car, f"web/cells/{stem}.json : aucune phrase ne dit que le carbone est vide"


def test_aucun_nombre_hors_referentiel_ni_nan(sheets):
    import json
    for stem, s in sheets.items():
        txt = json.dumps(s)
        assert "NaN" not in txt and "Infinity" not in txt, f"web/cells/{stem}.json : NaN ou Infinity"
