"""Stade d'un arbre (mission 070, décision de Pascal Q8, ADR 0007 choix 9) : une fonction, un fichier de seuils."""

import numpy as np
import pytest
import rasterio
import yaml

from sylvigenese.assets_lib import stages
from sylvigenese.common import ModuleError

from test_assets import FICTITIOUS_ZONE, ROOT


def test_les_seuils_sont_ceux_du_fichier_unique():
    doc = yaml.safe_load((ROOT / "biomes" / "stades" / "stage_breaks.yml").read_text(encoding="utf-8"))
    assert list(stages.load_breaks()) == doc["breaks"]
    assert list(stages.STAGES) == doc["stages"]


def test_bornes_basses_incluses_avec_des_seuils_d_essai():
    breaks = (0.2, 0.5, 0.8)          # seuils d'ESSAI (pas ceux du projet) : la règle se teste sans les valeurs du fichier
    ratio = np.array([0.0, 0.1999, 0.2, 0.4999, 0.5, 0.7999, 0.8, 1.0, 1.4])
    got = stages.stage_of(ratio * 30.0, 30.0, breaks)
    assert got.tolist() == ["young", "young", "pole", "pole", "mature", "mature", "old", "old", "old"]


def test_hauteur_au_dessus_du_plafond_est_le_stade_le_plus_age_sans_correction():
    assert stages.stage_of(40.0, 30.0).tolist() == ["old"]


def test_plafond_absent_nul_ou_hauteur_absente_sont_des_erreurs():
    for h, hp in ((10.0, np.nan), (10.0, 0.0), (10.0, -3.0), (np.nan, 30.0)):
        with pytest.raises(ModuleError, match="stade indéterminé"):
            stages.stage_of(h, hp)


def test_fichier_de_seuils_mal_forme_est_refuse(tmp_path):
    for text in ("stages: [young, pole, mature, old]\nbreaks: [0.5, 0.4, 0.9]\n",
                 "stages: [young, pole, mature, old]\nbreaks: [0.1, 0.5]\n",
                 "stages: [a, b, c, d]\nbreaks: [0.1, 0.5, 0.9]\n"):
        path = tmp_path / "s.yml"
        path.write_text(text, encoding="utf-8")
        with pytest.raises(ModuleError):
            stages.load_breaks(path)
    with pytest.raises(ModuleError, match="introuvables"):
        stages.load_breaks(tmp_path / "absent.yml")


def test_plafond_lu_a_la_cellule_de_l_arbre():
    """Cellule (ligne 3, colonne 6) de la grille de 25 m dont le coin nord-ouest est (700 000 ; 6 501 000)."""
    with rasterio.open(FICTITIOUS_ZONE / "site_potential.tif") as src:
        array = src.read(1)
    x, y = 700_000 + 6 * 25 + 24.9, 6_501_000 - 3 * 25 - 0.1
    assert stages.ceiling_at(FICTITIOUS_ZONE, [x], [y]).tolist() == [pytest.approx(float(array[3, 6]))]
    # un autre point de la même cellule, l'autre bord : même plafond
    assert stages.ceiling_at(FICTITIOUS_ZONE, [700_000 + 6 * 25 + 0.1], [6_501_000 - 3 * 25 - 24.9]).tolist() \
        == [pytest.approx(float(array[3, 6]))]
    # la colonne voisine (7) a sa propre valeur
    assert stages.ceiling_at(FICTITIOUS_ZONE, [700_000 + 7 * 25 + 1.0], [6_501_000 - 3 * 25 - 1.0]).tolist() \
        == [pytest.approx(float(array[3, 7]))]


def test_arbre_hors_de_la_grille_est_une_erreur():
    with pytest.raises(ModuleError, match="hors de la grille"):
        stages.ceiling_at(FICTITIOUS_ZONE, [699_990.0], [6_500_500.0])


def test_stade_d_un_arbre_de_la_zone_fictive_suit_h_sur_plafond():
    x, y = np.array([700_162.5]), np.array([6_500_987.5])
    ceiling = float(stages.ceiling_at(FICTITIOUS_ZONE, x, y)[0])
    breaks = stages.load_breaks()
    for ratio, expected in ((breaks[0] - 0.01, "young"), (breaks[0], "pole"), (breaks[1], "mature"), (breaks[2], "old")):
        assert stages.tree_stages(FICTITIOUS_ZONE, x, y, np.array([ratio * ceiling])).tolist() == [expected]
