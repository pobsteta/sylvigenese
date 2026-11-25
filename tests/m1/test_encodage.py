"""Encodage des rapports HTML (spec §1 ; documentation en français) : sous LC_ALL=C, chaque rapport
reste de l'UTF-8 valide, avec ses accents."""
import re

import pytest

import helpers as H

RAPPORTS = ["rapport_prepare.html", "rapport_biomes.html", "rapport_arbres.html"]
ACCENTS = re.compile("[éèêàùçôîû]")


def test_la_chaine_reussit_sous_lc_all_c(lcc_zone):
    for k in ("prepare", "biomes", "trees"):
        p = lcc_zone[k]
        assert p.returncode == 0, f"{k} sous LC_ALL=C : code {p.returncode}\n{p.stderr[-1500:]}"


@pytest.mark.parametrize("nom", RAPPORTS)
def test_rapport_utf8_valide_avec_accents_sous_lc_all_c(lcc_zone, nom):
    p = lcc_zone["dir"] / nom
    assert p.is_file(), f"{nom} absent sous LC_ALL=C"
    txt = H.decode_report(p)  # UTF-8 strict, ni « Ã© », ni « <U+00E9> », ni « \\u00e9 »
    assert ACCENTS.search(txt), f"{nom} : aucun caractère accentué (accents perdus ?)"
    assert re.search(r"(?i)<meta[^>]+charset=[\"']?utf-?8", txt), f"{nom} : charset UTF-8 non déclaré"


def test_rapport_arbres_dit_detectes_avec_ses_accents_sous_lc_all_c(lcc_zone):
    txt = H.decode_report(lcc_zone["dir"] / "rapport_arbres.html")
    assert "détectés" in txt, "« détectés » absent ou mal encodé dans rapport_arbres.html"


@pytest.mark.parametrize("nom", RAPPORTS)
def test_rapport_du_jeu_fictif_utf8_valide(runs, nom):
    assert H.ZONE.joinpath(nom).is_file(), f"{nom} absent"
    H.decode_report(H.ZONE / nom)
