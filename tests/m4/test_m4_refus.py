"""Erreurs explicites plutôt que valeurs par défaut (CLAUDE.md : « Signaler plutôt que deviner ») :
saisie incomplète, valeur hors référentiel, doublon."""
import helpers_m4 as H


def test_assets_refuse_les_entrees_incompletes_hors_referentiel_ou_en_double(refus):
    nom, d, p, mots = refus
    assert p.returncode != 0, f"{nom} : assets aurait dû refuser (code {p.returncode})"
    texte = (p.stderr + p.stdout).lower()
    assert any(m.lower() in texte for m in mots), f"{nom} : message sans aucun des mots {mots} :\n{texte[-800:]}"


def test_un_refus_n_ecrit_aucune_tuile_a_moitie(refus):
    nom, d, p, mots = refus
    assert not list((d / "tiles").glob("*/tileset.json")), f"{nom} : un tileset a été écrit malgré le refus"
    assert not list((d / "web" / "cells").glob("*.json")) if (d / "web" / "cells").exists() else True, \
        f"{nom} : des fiches ont été écrites malgré le refus"
