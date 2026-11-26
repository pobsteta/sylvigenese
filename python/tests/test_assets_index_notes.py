"""Mission 054 : notes de tiles/index.json et message final d'`assets` selon la version des fiches écrites.

Avant 054, l'index disait « volume et carbone non calculés » même quand post avait tourné (fiches v3), et le
message final disait toujours « fiche(s) v2 ». Ces tests portent sur les deux fonctions qui le décident ; le
contrat tiles_index est vérifié sur l'index produit, par le vrai validateur.
"""

import json

import pytest

from sylvigenese import assets, common
from sylvigenese.common import ModuleError
from sylvigenese.assets_lib import cell_sheets

def _doc(version: int, tarif: str | None = None) -> dict:
    d = {"schema_version": version, "tile": "t", "cells": []}
    if tarif is not None:
        d["tarif"] = {"name": tarif, "commit": "9821693", "provisoire": True}
    return d


def test_fiches_v2_index_inchange():
    notes = assets.index_notes_sim({"a": _doc(2), "b": _doc(2)})
    assert notes == assets.INDEX_NOTES_SIM
    assert any("volume et carbone non calculés" in n for n in notes)


def test_fiches_v3_index_dit_volume_et_carbone_calcules_par_post():
    notes = assets.index_notes_sim({"a": _doc(3, cell_sheets.TARIF_NAME), "b": _doc(3, cell_sheets.TARIF_NAME)})
    assert not any("volume et carbone non calculés" in n for n in notes)
    last = notes[-1]
    for k in ("volume aérien total", "carbone aérien", "calculés par post", "tarif NEMETON v5", "provisoire",
              "sol et bois mort non comptés", "semis non simulés"):
        assert k in last, f"« {k} » absent de la note : {last}"
    assert notes[:-1] == assets.INDEX_NOTES_SIM[:-1]   # les autres notes ne changent pas
    assert any("non validée écologiquement" in n for n in notes)


def test_message_donne_la_version_reellement_ecrite():
    assert assets.sheet_version({"a": _doc(2)}) == "v2"
    assert assets.sheet_version({"a": _doc(3, "x"), "b": _doc(3, "x")}) == "v3"


def test_le_contrat_tiles_index_accepte_la_nouvelle_note(tmp_path):
    # index minimal en mode sim (contrat tiles_index), avec les notes que assets écrit après post
    index = {"schema_version": 1, "source": "sim", "t0": 2022, "year_step": 10, "run_config_sha256": "0" * 64,
             "provisoire": True, "notes": assets.index_notes_sim({"a": _doc(3, cell_sheets.TARIF_NAME)}),
             "basal_area_map": {"unit": "m2/ha", "scale_min_m2_ha": 0.0, "scale_max_m2_ha": 100.0,
                                "mention": "surface terrière ; " + assets.MENTION_SIM},
             "years": [{"year": 2022, "instances": 1, "dead": 0, "tileset": "2022/tileset.json",
                        "tiles": [{"tile": "t_700000_6500000", "instances": 1}]}]}
    p = tmp_path / "index.json"
    p.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    assert common.call_validator(["assets.tiles_index", str(p)]) == 0


# ---- Mission 066 : la note des semis dit l'état réel selon le mode de recrutement (sim/run.json)
RUN_COHORTS = {"recruitment": "cohorts", "not_simulated": ["sous_bois", "gibier", "fructification"]}
RUN_IFN_DIRECT = {"recruitment": "ifn_direct", "not_simulated": ["semis", "sous_bois", "gibier", "fructification"]}


def test_index_ifn_direct_dit_semis_non_simules():
    for run in (RUN_IFN_DIRECT, None):
        notes = assets.index_notes_sim({"a": _doc(2)}, run)
        assert notes == assets.INDEX_NOTES_SIM
        assert "semis non simulés" in notes[-1]


def test_index_cohorts_dit_les_semis_simules_techniques_non_valides():
    notes = assets.index_notes_sim({"a": _doc(2)}, RUN_COHORTS)
    assert not any("semis non simulés" in n for n in notes)
    assert "semis simulés par cohortes" in notes[-1] and "non validée" in notes[-1]
    assert "sous-bois, gibier et fructification non simulés" in notes[-1]
    assert "volume et carbone non calculés" in notes[-1]            # v2 : le reste de la note ne change pas
    assert notes[:-1] == assets.INDEX_NOTES_SIM[:-1]


def test_index_cohorts_avec_fiches_v3_garde_le_volume_calcule():
    notes = assets.index_notes_sim({"a": _doc(3, cell_sheets.TARIF_NAME)}, RUN_COHORTS)
    assert not any("semis non simulés" in n for n in notes)
    assert "semis simulés par cohortes" in notes[-1] and "calculés par post" in notes[-1]
    assert "tarif NEMETON v5" in notes[-1]


def test_index_cohorts_accepte_par_le_contrat_tiles_index(tmp_path):
    index = {"schema_version": 1, "source": "sim", "t0": 2022, "year_step": 10, "run_config_sha256": "0" * 64,
             "provisoire": True, "notes": assets.index_notes_sim({"a": _doc(2)}, RUN_COHORTS),
             "basal_area_map": {"unit": "m2/ha", "scale_min_m2_ha": 0.0, "scale_max_m2_ha": 100.0,
                                "mention": "surface terrière ; " + assets.MENTION_SIM},
             "years": [{"year": 2022, "instances": 1, "dead": 0, "tileset": "2022/tileset.json",
                        "tiles": [{"tile": "t_700000_6500000", "instances": 1}]}]}
    p = tmp_path / "index.json"
    p.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    assert common.call_validator(["assets.tiles_index", str(p)]) == 0


def test_seedling_note_selon_le_mode():
    assert cell_sheets.seedling_note(None) == cell_sheets.NOTES_V2[2]
    assert cell_sheets.seedling_note(RUN_IFN_DIRECT) == cell_sheets.NOTES_V2[2] == "semis non simulés (jusqu'à M5)"
    note = cell_sheets.seedling_note(RUN_COHORTS)
    assert note.startswith("semis simulés par cohortes") and "sous-bois, gibier et fructification non simulés" in note
    assert "semis non simulés" not in note
    une = cell_sheets.seedling_note({"recruitment": "cohorts", "not_simulated": ["gibier"]})
    assert une.endswith("gibier non simulés")
    with pytest.raises(ModuleError):                                # cohorts sans not_simulated : rien n'est deviné
        cell_sheets.seedling_note({"recruitment": "cohorts"})


def test_notes_v2_for_ne_change_que_la_note_des_semis():
    base = cell_sheets.notes_v2_for(RUN_IFN_DIRECT)
    assert base == cell_sheets.NOTES_V2 and cell_sheets.notes_v2_for(None) == cell_sheets.NOTES_V2
    coh = cell_sheets.notes_v2_for(RUN_COHORTS)
    assert len(coh) == len(base)
    assert coh[2] == cell_sheets.seedling_note(RUN_COHORTS)
    assert coh[:2] + coh[3:] == base[:2] + base[3:]
    assert cell_sheets.NOTES_V2[2] == "semis non simulés (jusqu'à M5)"   # la constante n'est pas modifiée
