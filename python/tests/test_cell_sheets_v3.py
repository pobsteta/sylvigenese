"""Fiche de cellule v3 (mission 053, contrat cell_sheet v3) : une année depuis sim/cells et sim/summary.parquet.

Valeurs d'essai, sans sens écologique. Les tests de bout en bout (assets après post) sont dans tests/post.
"""

import math

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
