"""M3a, stabilité de l'état initial produit par la chaîne R (prepare, biomes, trees), jugée à part du moteur :
trees_init de la chaîne nominale de cette session contre trees_init figé (tests/m3/reference/entrees/).

Ce qui est comparé, et pourquoi à l'égalité exacte (aucune tolérance) :
  - tree_id, x, y : un sommet est une cellule du MNH à 50 cm (centre de cellule), choisie par des maxima locaux
    départagés explicitement (R/prepare_trees.R, TREES_TIE_EPS) ; c'est un choix discret, pas un calcul flottant ;
  - h : maximum du MNH brut (float32, lu sans perte) sur 3 x 3 cellules ;
  - crown_area : nombre de cellules du houppier x 0,25 m².
  Mesuré le 25/11/2026 : terra 1.7.65 et terra 1.9.60 (celle de la CI) donnent ces colonnes identiques, à
  l'octet, sur les 14 080 arbres ; elles le restent quand station_type.tif est rééchantillonné comme par
  GDAL 3.12.2 (celui de la CI).

Ce qui n'est PAS comparé ici, et pourquoi : species et d130. Ils dépendent du type de station rééchantillonné en
« mode » de 20 m à 25 m dans prepare (R/prepare_grid.R, resample_categorical) ; GDAL 3.11 a changé ce mode
(pondéré par la surface couverte, NEWS de GDAL 3.11.0) : 50 cellules sur 1600 changent de type entre GDAL 3.8.4 et
3.12.2, et jusqu'à 77 arbres hors polygone changent d'essence, donc de d130. C'est un défaut amont, remonté à
l'orchestrateur (correction dans R/prepare_grid.R, règle de départage à trancher) ; aucune tolérance ne le rendrait
juste, il n'est donc pas « testé avec une marge » : il est à corriger."""
import numpy as np
import pyarrow.parquet as pq
from pathlib import Path

import helpers_m3 as H

FIGE = Path(__file__).parent / "reference" / "entrees" / "trees_init" / "trees.parquet"
STABLES = ("x", "y", "h", "crown_area")


def _par_id(table):
    t = table.sort_by("tree_id")
    return {k: t.column(k).to_numpy(zero_copy_only=False) for k in ("tree_id",) + STABLES}


def test_la_detection_et_les_houppiers_ne_dependent_pas_de_la_plateforme(chaine):
    assert chaine["make"].returncode == 0, H.queue(chaine["make"])
    obtenu = _par_id(pq.read_table(chaine["dir"] / "trees_init" / "trees.parquet"))
    fige = _par_id(pq.read_table(FIGE))
    ids_o, ids_f = set(obtenu["tree_id"]), set(fige["tree_id"])
    assert ids_o == ids_f, (f"arbres détectés différents : {len(ids_o - ids_f)} en plus, {len(ids_f - ids_o)} en "
                            f"moins (par exemple {sorted(ids_o ^ ids_f)[:5]})")
    for k in STABLES:
        diff = np.flatnonzero(obtenu[k] != fige[k])
        assert diff.size == 0, (f"{k} : {diff.size} arbre(s) différent(s) du trees_init figé, premier "
                                f"{obtenu['tree_id'][diff[0]]} ({obtenu[k][diff[0]]!r} contre {fige[k][diff[0]]!r})")
