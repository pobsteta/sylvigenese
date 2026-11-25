"""Garde IFN `assert_no_fine_extract_on_ifn()` (CLAUDE.md ; spec §6 ; reprise de sylvostation,
R/utils.R:121) : toute variable non préfixée `coarse_` est fine ; seuil de précision 25 m.

Signature et comportement : celles de sylvostation (points, variables, max_precision_m = 25).
"""
import subprocess

import pytest

import helpers as H

CASES = {
    # nom : (construction des points, variables, attendu "OK" ou "ERR")
    "ifn_station_gradients_refuse": ('data.frame(x=1, y=2, source="ifn", loc_precision_m=700)',
                                     'c("station_gradients")', "ERR"),
    "ifn_variable_large_permise": ('data.frame(x=1, y=2, source="ifn", loc_precision_m=700)',
                                   'c("coarse_hydric_700m", "coarse_bioclim_700m")', "OK"),
    "ifn_melange_large_et_fine_refuse": ('data.frame(x=1, y=2, source="ifn", loc_precision_m=700)',
                                         'c("coarse_hydric_700m", "pente")', "ERR"),
    "ifn_variable_inconnue_refusee": ('data.frame(x=1, y=2, source="ifn", loc_precision_m=700)',
                                      'c("variable_inconnue")', "ERR"),
    "ifn_prefixe_sensible_a_la_casse": ('data.frame(x=1, y=2, source="ifn", loc_precision_m=700)',
                                        'c("COARSE_climat")', "ERR"),
    "ifn_source_seule_suffit_meme_precis": ('data.frame(x=1, y=2, source="ifn", loc_precision_m=1)',
                                            'c("pente")', "ERR"),
    "ifn_aucune_variable_passe": ('data.frame(x=1, y=2, source="ifn", loc_precision_m=700)',
                                  "character(0)", "OK"),
    "point_precis_variable_fine_permise": ('data.frame(x=1, y=2, source="terrain", loc_precision_m=5)',
                                           'c("pente")', "OK"),
    "seuil_25_m_inclus": ('data.frame(x=1, y=2, source="terrain", loc_precision_m=25)',
                          'c("pente")', "OK"),
    "au_dela_de_25_m_refuse": ('data.frame(x=1, y=2, source="terrain", loc_precision_m=26)',
                               'c("pente")', "ERR"),
    "precision_absente_refusee": ('data.frame(x=1, y=2, source="terrain")', 'c("pente")', "ERR"),
    "precision_NA_refusee": ('data.frame(x=1, y=2, source="terrain", loc_precision_m=NA_real_)',
                             'c("pente")', "ERR"),
}


@pytest.fixture(scope="module")
def resultats():
    lignes = []
    for nom, (pts, var, _) in CASES.items():
        lignes.append(
            f'cat("{nom}:", tryCatch({{assert_no_fine_extract_on_ifn({pts}, {var}); "OK"}}, '
            f'error = function(e) paste0("ERR|", conditionMessage(e))), "\\n", sep="")')
    expr = H.R_LOAD + "; " + "; ".join(lignes)
    p = subprocess.run(["Rscript", "-e", expr], cwd=H.ROOT, capture_output=True, text=True)
    assert p.returncode == 0, f"la garde n'a pas pu être appelée (R/ chargé comme le Makefile) :\n{p.stderr[-1500:]}"
    out = {}
    for ln in p.stdout.splitlines():
        if ":" in ln:
            k, v = ln.split(":", 1)
            out[k] = v
    return out


@pytest.mark.parametrize("nom", list(CASES))
def test_garde_ifn(resultats, nom):
    attendu = CASES[nom][2]
    assert nom in resultats, f"cas {nom} sans résultat : {resultats}"
    obtenu = resultats[nom]
    assert obtenu.startswith(attendu), f"{nom} : attendu {attendu}, obtenu {obtenu}"
    if attendu == "ERR":
        # Message utilisateur en français (CLAUDE.md), non vide.
        assert "Extraction interdite" in obtenu, obtenu
