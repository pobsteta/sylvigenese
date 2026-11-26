"""Mission 054 : notes de tiles/index.json et message final d'`assets` selon la version des fiches écrites.

Avant 054, l'index disait « volume et carbone non calculés » même quand post avait tourné (fiches v3), et le
message final disait toujours « fiche(s) v2 ». Ces tests portent sur les deux fonctions qui le décident ; le
contrat tiles_index est vérifié sur l'index produit, par le vrai validateur.
"""

import json
from sylvigenese import assets, common
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
