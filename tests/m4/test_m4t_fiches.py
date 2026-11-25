"""Suite de M4a (mission 045) : fiches de cellule v2 (web/cells/<tuile>.json) sur une zone avec sim/.
Toutes les années retenues, chiffres égaux à sim/cells (recalcul arithmétique exact), h_dom_m par année (Q1),
volume et carbone non calculés (Q2), mention « non validée écologiquement » (T9), flags de flags.parquet ;
une année sans ligne dans sim/cells : tiges 0, G 0, h_dom_m null (précision de l'orchestrateur, 25/11/2026)."""
import numpy as np
import pytest

import helpers_m4 as H
import helpers_m4_temps as T

ANNEES = T.retained_years(T.T0, T.YEARS, T.STEP)


@pytest.fixture(scope="module")
def cellules(temps_sheets):
    c = H.sheet_cells(temps_sheets)
    assert c, "fiches sans cellule"
    return c


@pytest.fixture(scope="module")
def oracle_t(temps):
    return H.Oracle(T.exige_temps(temps))


def test_les_fiches_sont_conformes_au_contrat_v2(temps, temps_sheets):
    zdir = T.exige_temps(temps)
    for stem, s in temps_sheets.items():
        assert s["schema_version"] == 2, f"{stem} : schema_version {s['schema_version']} (v2 exigée dès que sim/ existe)"
        assert s["source"] == "sim" and s["tile"] == stem
    p = H.validate("cell_sheet", *[str(p) for p in sorted((zdir / "web" / "cells").glob("*.json"))])
    assert p.returncode == 0, p.stdout[-2000:] + p.stderr[-1000:]


def test_les_notes_disent_non_validee_et_volume_carbone_non_calcules(temps_sheets):
    for stem, s in temps_sheets.items():
        notes = s.get("notes", [])
        assert any(T.MENTION_ECO in n for n in notes), f"{stem} : « {T.MENTION_ECO} » absente des notes"
        assert any(T.MENTION_VC in n for n in notes), f"{stem} : « {T.MENTION_VC} » absente des notes"


def test_aucune_cellule_en_double_et_les_cellules_forestieres_ont_leur_fiche(temps_sheets, cellules, oracle_t):
    ids = [c["cell_id"] for s in temps_sheets.values() for c in s["cells"]]
    assert len(ids) == len(set(ids))
    manque = oracle_t.forest_cells() - set(cellules)
    assert not manque, f"{len(manque)} cellules forestières sans fiche"


def test_chaque_cellule_qui_porte_un_arbre_vivant_a_sa_fiche(temps_cells, cellules):
    portees = {c for (c, y) in temps_cells if y in ANNEES}
    manque = sorted(portees - set(cellules))
    assert not manque, f"{len(manque)} cellules avec des arbres vivants (sim/cells) sans fiche, ex. {manque[:5]}"


def test_chaque_cellule_porte_toutes_les_annees_retenues_dans_l_ordre(cellules):
    for cid, c in cellules.items():
        ys = [e["year"] for e in c["years"]]
        assert ys == ANNEES, f"cellule {cid} : années {ys} != {ANNEES}"


def test_station_vegetation_et_centre_comme_l_etat_initial(cellules, oracle_t):
    for cid, c in cellules.items():
        if cid not in oracle_t.forest_cells():
            continue
        v = oracle_t.cell_values(cid)
        x, y = H.cell_centre(cid)
        assert abs(c["x"] - x) < 0.5 and abs(c["y"] - y) < 0.5, f"cellule {cid} : centre ({c['x']}, {c['y']})"
        assert c["station_type"] == v["station_type"] and c["vegetation_type"] == v["vegetation_type"], cid


def test_le_plafond_est_site_potential(temps, cellules):
    a, nd, _, _ = H.read_raster(T.exige_temps(temps) / "site_potential.tif")
    for cid, c in cellules.items():
        r, k = divmod(cid, H.NCOLS)
        v = float(a[r, k])
        attendu = None if (nd is not None and v == nd) or not np.isfinite(v) else v
        assert T.close(c["h_ceiling_m"], attendu, 1e-6), f"cellule {cid} : h_ceiling_m {c['h_ceiling_m']} != {attendu}"


@pytest.mark.parametrize("champ", ["stems_ha", "basal_area_m2_ha", "d130_mean_cm", "h_dom_m"])
def test_les_chiffres_de_chaque_annee_sont_ceux_de_sim_cells(cellules, temps_cells, champ):
    faux = []
    for cid, c in cellules.items():
        for e in c["years"]:
            att = T.expected_year(temps_cells.get((cid, e["year"])))[champ]
            assert not (isinstance(att, tuple) and att[0] == "DIVERGENT"), \
                f"cellule {cid}, {e['year']} : h_dom_m diffère entre essences dans sim/cells : {att[1]}"
            if champ not in e or not T.close(e[champ], att):
                faux.append((cid, e["year"], e.get(champ, "ABSENT"), att))
    assert not faux, f"{champ} : {len(faux)} écarts (cellule, année, fiche, sim/cells), ex. {faux[:4]}"


def test_une_annee_sans_ligne_dans_sim_cells_est_une_cellule_sans_arbre_vivant(cellules, temps_cells):
    vides = [(cid, e) for cid, c in cellules.items() for e in c["years"] if (cid, e["year"]) not in temps_cells]
    assert vides, "aucune année de cellule sans arbre vivant sur la zone (trouées) : le test n'a pas de pouvoir"
    for cid, e in vides:
        assert e["stems_ha"] == 0 and e["basal_area_m2_ha"] == 0, f"cellule {cid}, {e['year']} : {e}"
        assert e["h_dom_m"] is None and e["d130_mean_cm"] is None and e["composition"] == [], \
            f"cellule {cid}, {e['year']} : valeur inventée pour une cellule sans ligne dans sim/cells : {e}"


def test_la_composition_de_chaque_annee_est_celle_de_sim_cells(cellules, temps_cells):
    faux = []
    for cid, c in cellules.items():
        for e in c["years"]:
            att = T.expected_year(temps_cells.get((cid, e["year"])))["composition"]
            lu = {x["species"]: (x["stems_ha"], x["basal_area_m2_ha"], x["share"]) for x in e["composition"]}
            if len(lu) != len(e["composition"]) or set(lu) != set(att) or \
                    any(not all(T.close(a, b) for a, b in zip(lu[s], att[s])) for s in att):
                faux.append((cid, e["year"], lu, att))
    assert not faux, f"{len(faux)} compositions fausses (share = part des TIGES), ex. {faux[:2]}"


def test_les_essences_de_la_composition_sont_au_referentiel(cellules):
    groupe = H.species_group()
    hors = sorted({x["species"] for c in cellules.values() for e in c["years"] for x in e["composition"]} - set(groupe))
    assert not hors, f"essences hors de contracts/species.csv : {hors}"


def test_les_signalements_sont_ceux_de_flags_parquet(temps, cellules):
    fl = T.flags_by_cell_year(T.exige_temps(temps))
    faux, n = [], 0
    for cid, c in cellules.items():
        for e in c["years"]:
            att = sorted(fl.get((cid, e["year"]), []), key=repr)
            lu = sorted(((f["kind"], f["message"], f.get("value")) for f in e["flags"]), key=repr)
            n += len(lu)
            if len(lu) != len(att) or any(a[:2] != b[:2] or not T.close(a[2], b[2], 1e-6) for a, b in zip(lu, att)):
                faux.append((cid, e["year"], lu[:2], att[:2]))
    assert not faux, f"{len(faux)} (cellule, année) aux signalements différents de flags.parquet, ex. {faux[:2]}"
    assert n > 0, "aucun signalement recopié (hdom_au_dessus_du_plafond, trouee_sans_recrue attendus sur le jeu fictif)"


def test_chaque_annee_est_provisoire_et_volume_carbone_sont_null(cellules):
    for cid, c in cellules.items():
        for e in c["years"]:
            assert e["provisoire"] is True, f"cellule {cid}, {e['year']} : provisoire = {e['provisoire']}"
            assert e["volume_m3_ha"] is None and e["carbon_t_ha"] is None, \
                f"cellule {cid}, {e['year']} : volume ou carbone chiffré (Q2 : non calculés)"


def test_h0_n_est_donne_qu_a_t0_et_vaut_h0_tif(temps, cellules):
    h0, nd, _, _ = H.read_raster(T.exige_temps(temps) / "h0.tif")
    for cid, c in cellules.items():
        for e in c["years"]:
            if e["year"] != T.T0:
                assert "h0_m" not in e, f"cellule {cid}, {e['year']} : h0_m hors de t0"
            elif "h0_m" in e:
                r, k = divmod(cid, H.NCOLS)
                assert T.close(e["h0_m"], float(h0[r, k]), 1e-6), f"cellule {cid} : h0_m {e['h0_m']} != h0.tif"


def test_h_dom_m_varie_dans_le_temps(cellules):
    # Discriminant : une H_dom recopiée de t0 sur toutes les années passerait les comparaisons d'une seule année.
    varie = sum(1 for c in cellules.values()
                if len({e["h_dom_m"] for e in c["years"] if e["h_dom_m"] is not None}) > 1)
    assert varie > len(cellules) // 2, f"h_dom_m ne change que dans {varie} cellules sur {len(cellules)}"
