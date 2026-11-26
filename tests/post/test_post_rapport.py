"""rapport_post.html (plan T10 ; spec §1 à compléter) : il existe à la racine de la zone, comme les autres rapports de
module, et il dit ce qui n'est pas calculé : par essence, avec ses comptes, la part de surface terrière, le statut
provisoire du tarif et la mention « non validée écologiquement »."""
import re

import pytest

import helpers_post as P


def texte(zdir):
    p = zdir / "rapport_post.html"
    assert p.is_file(), "rapport_post.html absent de la racine de la zone"
    brut = p.read_text(encoding="utf-8")
    assert re.search(r"<html|<!doctype", brut, re.I), "rapport_post.html n'est pas du HTML"
    return P.sans_accent(re.sub(r"<[^>]+>", " ", brut))


def test_le_rapport_de_la_zone_simulee_dit_les_parts_non_calculees(base_dir, oracle):
    t = texte(base_dir)
    assert "non calcul" in t, "le rapport doit dire ce qui n'est pas calculé"
    assert "surface terriere" in t, "le rapport doit dire la part de surface terrière non calculée"
    assert "provisoire" in t
    assert "non validee ecologiquement" in t
    for sp in oracle.counts()["out_of_domain"]:
        assert re.search(rf"\b{sp}\b", t), f"essence {sp} (arbres hors domaine) absente du rapport"


def test_le_rapport_de_l_echantillon_nomme_chaque_essence_et_son_compte(ech_dir):
    t = texte(ech_dir)
    assert "non calcul" in t
    # sans tarif : 02, 2 arbres-années ; hors domaine : 09 (4), 03 (4), 61, 62, 64 (2 chacun)
    for sp, n in (("02", 2), ("09", 4), ("03", 4), ("61", 2), ("62", 2), ("64", 2)):
        assert re.search(rf"\b{sp}\b", t), f"essence {sp} absente du rapport"
    assert "sans tarif" in t, "le rapport doit dire qu'une essence n'a pas de tarif"
    assert re.search(r"\b02\b[^0-9]{0,200}\b2\b", t), "le compte de l'essence sans tarif (02 : 2) n'est pas dit"
