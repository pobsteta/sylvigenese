"""Fiche de cellule v3 (mission 053, contrat cell_sheet v3) : une année depuis sim/cells et sim/summary.parquet.

Valeurs d'essai, sans sens écologique. Les tests de bout en bout (assets après post) sont dans tests/post.
"""

import math
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from sylvigenese.assets_lib import cell_sheets
from sylvigenese.common import ModuleError


def cells_row(sp, stems, g, d, h=20.0):
    return {"species": sp, "stems_ha": stems, "basal_area_m2_ha": g, "d130_mean": d, "h_dom_m": h}


def summary_row(volume, carbon, share, stems_nc, roots=None):
    r = {"volume_m3_ha": volume, "carbon_t_ha": carbon, "basal_area_not_computed_share": share,
         "stems_not_computed_ha": stems_nc}
    if roots is not None:
        r["carbon_roots_t_ha"] = roots
    return r


def test_annee_partielle_somme_des_essences_et_part_ponderee_par_g():
    rows = [cells_row("09", 32.0, 4.0, 30.0), cells_row("03", 16.0, 1.0, 20.0)]
    summary = {"09": summary_row(30.0, 3.0, 0.25, 16.0, roots=0.3), "03": summary_row(0.0, 0.0, 1.0, 16.0, roots=0.0)}
    e = cell_sheets.year_entry_v3(rows, summary, True, 2022, 0)
    assert e["volume_m3_ha"] == 30.0 and e["carbon_t_ha"] == 3.0 and e["root_carbon_t_ha"] == 0.3
    assert math.isclose(e["basal_area_not_computed_share"], (0.25 * 4.0 + 1.0 * 1.0) / 5.0)
    assert e["volume_partiel"] is True and e["stems_not_computed_ha"] == 32.0
    comp = {c["species"]: c for c in e["composition"]}
    assert comp["03"]["volume_m3_ha"] is None and comp["03"]["carbon_t_ha"] is None, "part 1 : null, jamais 0"
    assert comp["09"]["volume_m3_ha"] == 30.0 and comp["09"]["basal_area_not_computed_share"] == 0.25
    assert "not_computed_reason" not in e


def test_rien_de_calcule_null_avec_sa_raison():
    rows = [cells_row("03", 32.0, 2.0, 50.0)]
    e = cell_sheets.year_entry_v3(rows, {"03": summary_row(0.0, 0.0, 1.0, 32.0, roots=0.0)}, True, 2022, 7)
    assert e["basal_area_not_computed_share"] == 1.0 and e["volume_partiel"] is True
    assert e["volume_m3_ha"] is None and e["carbon_t_ha"] is None and e["root_carbon_t_ha"] is None
    assert "hors du domaine" in e["not_computed_reason"]


def test_cellule_sans_arbre_vivant_vaut_0():
    e = cell_sheets.year_entry_v3([], {}, False, 2023, 3)
    assert e["volume_m3_ha"] == 0 and e["carbon_t_ha"] == 0 and e["basal_area_not_computed_share"] == 0
    assert e["volume_partiel"] is False and "root_carbon_t_ha" not in e


def test_sans_racines_pas_de_cle_racines():
    e = cell_sheets.year_entry_v3([cells_row("09", 16.0, 2.0, 40.0)], {"09": summary_row(29.5, 2.6, 0.0, 0.0)},
                                  False, 2022, 0)
    assert "root_carbon_t_ha" not in e and e["volume_partiel"] is False and e["basal_area_not_computed_share"] == 0.0


def test_essences_du_summary_differentes_de_cells_refusees():
    with pytest.raises(ModuleError, match="ne viennent pas du même run"):
        cell_sheets.year_entry_v3([cells_row("09", 16.0, 2.0, 40.0)], {"61": summary_row(1.0, 0.1, 0.0, 0.0)},
                                  False, 2022, 0)


# ------------------------------------------------------------------ nom du tarif et note des racines (mission 056)
FIXTURE_TARIF = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "zone_fictive" / "params" / "tarif.parquet"


def tarif_row(model, term, biblio, essence="61"):
    return {"essence": essence, "groupe": None, "modele": model, "terme": term, "valeur": 1.0, "unite": "sans_unite",
            "source_code": "essai", "source_biblio": biblio, "source_commit": "abcdef1", "provisoire": True}


def test_jeu_fictif_ni_tarif_nemeton_v5_ni_giec_pour_les_valeurs_synthetiques():
    rows = pq.read_table(FIXTURE_TARIF).to_pylist()
    name = cell_sheets.tarif_name(rows)
    assert "tarif NEMETON v5" not in name, name
    assert "forme synthétique du jeu fictif pour les résineux" in name and "« synthetique_jeu_fictif »" in name
    note = cell_sheets.note_roots(rows, "0000000")
    assert "GIEC" not in note and "« synthetique_jeu_fictif »" in note and "source_commit 0000000" in note
    assert "racines" in note and "PROVISOIRE" in note       # mention « racines » exigée par le contrat cell_sheet v3


def test_nom_et_source_des_racines_suivent_les_colonnes_du_tarif():
    rows = [tarif_row("volume_feuillus", "a", "source A", "09"), tarif_row("profil_tige_resineux", "k0", "source B"),
            tarif_row("expansion_resineux", "D_plafond", "source B"),
            {**tarif_row("racines", "ratio", "GIEC 2006, tableau 4.4"), "essence": None, "groupe": "resineux"}]
    name = cell_sheets.tarif_name(rows)
    assert name.startswith(cell_sheets.TARIF_NAME) and "valeurs de 2 sources" in name
    assert "GIEC 2006, tableau 4.4" in cell_sheets.note_roots(rows, "abcdef1")
    one_source = [{**r, "source_biblio": "source C"} for r in rows[:3]]
    assert "valeurs de source « source C »" in cell_sheets.tarif_name(one_source)
