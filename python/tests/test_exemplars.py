"""Exemplaires du générateur lus par fichiers (mission 070, décisions de Pascal Q1, Q3, Q6, contrat assets.exemplars).

La fixture est SYNTHÉTIQUE (exemplars_synthetiques.py) : aucune valeur écologique."""

import numpy as np
import pyarrow.parquet as pq
import pytest

import exemplars_synthetiques as F
from sylvigenese.assets_lib import exemplars
from sylvigenese.common import ModuleError


def test_lecture_d_un_exemplaire(tmp_path):
    path = F.write(tmp_path, "Fagus_sylvatica", "mature")
    ex = exemplars.read_exemplar(path)
    assert (ex.essence, ex.stage, ex.seed, ex.count) == ("Fagus_sylvatica", "mature", 7, 93)
    assert ex.meta["source_commit"] == "0000000" and ex.meta["frame"] == "z-up"
    seg = F.segments("mature")
    assert np.array_equal(ex.segments["z1"], seg["z1"]) and np.array_equal(ex.segments["niveau"], seg["niveau"])
    # le segment repère (dernier) finit en (x, y, z) = (2, 5, 0,6 H) : lu tel quel, sans conversion (repère du fichier)
    assert (ex.segments["x1"][-1], ex.segments["y1"][-1], ex.segments["z1"][-1]) == (2.0, 5.0, pytest.approx(0.6 * 24.0))


def test_lecture_d_un_dossier_et_codes_du_referentiel(tmp_path):
    F.write_set(tmp_path)
    found = exemplars.read_directory(tmp_path)
    assert sorted(found) == sorted((e, s) for e in ("Abies_alba", "Fagus_sylvatica", "Quercus_spec") for s in F.STAGES)


@pytest.mark.parametrize("meta,pattern", [
    ({"frame": "y-up"}, "z-up"),
    ({"frame": None}, "métadonnée"),
    ({"units": "cm"}, "unités"),
    ({"synthetic": "false"}, "synthetic"),
    ({"source_commit": "pas-un-commit"}, "source_commit"),
    ({"D_cm": "-3"}, "strictement positif"),
    ({"H_m": "abc"}, "pas un nombre"),
    ({"seed": "x"}, "entier"),
    ({"b_cible": None}, "b_cible absent"),
    ({"b_cible": "nan"}, "pas fini"),
    ({"calage": "peut-être"}, "calage"),
    ({"stage": "ancien"}, "stade"),
])
def test_exemplaire_hors_contrat_est_refuse_avec_la_cause(tmp_path, meta, pattern):
    path = F.write(tmp_path, "Fagus_sylvatica", "mature", meta=meta)
    with pytest.raises(ModuleError, match=pattern):
        exemplars.read_exemplar(path)


def test_b_cible_absent_est_admis_seulement_si_non_cale(tmp_path):
    path = F.write(tmp_path, "Abies_alba", "mature", meta={"b_cible": None, "calage": "non calé"})
    ex = exemplars.read_exemplar(path)
    assert "b_cible" not in ex.meta and ex.meta["calage"] == "non calé"


def test_nom_different_des_metadonnees_est_refuse(tmp_path):
    path = F.write(tmp_path, "Fagus_sylvatica", "mature")
    path.rename(tmp_path / "Fagus_sylvatica_old.parquet")
    with pytest.raises(ModuleError, match="le nom doit être"):
        exemplars.read_exemplar(tmp_path / "Fagus_sylvatica_old.parquet")


def test_fichier_tronque_ou_sans_colonne_ou_non_fini_est_refuse(tmp_path):
    path = F.write(tmp_path, "Fagus_sylvatica", "mature")
    path.write_bytes(path.read_bytes()[:200])
    with pytest.raises(ModuleError, match="illisible"):
        exemplars.read_exemplar(path)
    other = F.write(tmp_path, "Fagus_sylvatica", "pole")
    table = pq.read_table(other).drop_columns(["axe"])
    pq.write_table(table, other)
    with pytest.raises(ModuleError, match="colonne"):
        exemplars.read_exemplar(other)
    seg = F.segments("old")
    seg["x1"] = seg["x1"].copy()
    seg["x1"][3] = np.nan
    bad = F.write(tmp_path, "Fagus_sylvatica", "old", seg=seg)
    with pytest.raises(ModuleError, match="non finie"):
        exemplars.read_exemplar(bad)


def test_essence_hors_de_species_csv_et_dossier_vide_sont_refuses(tmp_path):
    F.write(tmp_path, "Inventus_ficticius", "mature")
    with pytest.raises(ModuleError, match="n'est pas une essence du générateur"):
        exemplars.read_directory(tmp_path)
    (tmp_path / "vide").mkdir()
    with pytest.raises(ModuleError, match="aucun fichier"):
        exemplars.read_directory(tmp_path / "vide")
    with pytest.raises(ModuleError, match="n'est pas un dossier"):
        exemplars.read_directory(tmp_path / "absent")


def test_alias_et_essences_sans_modele():
    table = exemplars.species_models()
    assert (table["02"].essence, table["02"].owner) == ("Quercus_spec", "02")
    assert (table["03"].essence, table["03"].owner) == ("Quercus_spec", "02")        # alias de 02 : même essence
    assert (table["12V"].owner, table["12P"].owner) == ("12P", "12P")
    assert table["09"].owner == "09" and table["61"].group == "resineux" and table["09"].group == "feuillu"
    assert table["10"].essence is None and table["10"].owner is None                 # châtaignier : aucun modèle propre
    assert table["62"].essence == "Picea_abies"


def test_doublon_essence_stade_est_refuse(tmp_path):
    F.write(tmp_path, "Fagus_sylvatica", "mature")
    (tmp_path / "Fagus_sylvatica_mature_bis.parquet").write_bytes((tmp_path / "Fagus_sylvatica_mature.parquet").read_bytes())
    with pytest.raises(ModuleError, match="doublon"):
        exemplars.read_directory(tmp_path)
