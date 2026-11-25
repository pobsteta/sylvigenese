"""M3a, stabilité de l'état initial produit par la chaîne R (prepare, biomes, trees), jugée à part du moteur :
trees_init de la chaîne nominale de cette session contre trees_init figé (tests/m3/reference/entrees/).

Ce qui est comparé, et pourquoi à l'égalité exacte (aucune tolérance) :
  - tree_id, x, y : un sommet est une cellule du MNH à 50 cm (centre de cellule), choisie par des maxima locaux
    départagés explicitement (R/prepare_trees.R, TREES_TIE_EPS) ; c'est un choix discret, pas un calcul flottant ;
  - h : maximum du MNH brut (float32, lu sans perte) sur 3 x 3 cellules ;
  - crown_area : nombre de cellules du houppier x 0,25 m² ;
  - species : code d'essence (chaîne) ; dans un polygone il vient de nemeton, hors polygone du biome de la
    cellule, donc du type de station passé de 20 à 25 m dans prepare ;
  - d130 : diamètre (float64) de l'étage B de tarif-nemeton (R/prepare_trees.R, exp(a + b ln H [+ c ln CPA]),
    coefficients de l'essence) : il suit species ; calcul flottant (exp, log), exact d'une plateforme à l'autre
    tant que la bibliothèque mathématique rend les mêmes bits : un écart serait à remonter, pas à tolérer.
  Mesuré le 25/11/2026 : terra 1.7.65 et terra 1.9.60 (celle de la CI) donnent x, y, h et crown_area identiques, à
  l'octet, sur les 14 080 arbres.

species et d130 dépendaient de la version de GDAL : prepare passait station_type.tif de 20 à 25 m par le « mode »
de GDAL, changé en 3.11 (50 cellules sur 1600 changeaient de type entre GDAL 3.8.4 et 3.12.2, jusqu'à 77 arbres
hors polygone d'essence). Depuis la mission 042, prepare applique sa propre règle (R/prepare_grid.R,
categorical_majority : majorité pondérée par la surface couverte, à égalité le pixel du centre, décision de Pascal
du 25/11/2026), sans appel au rééchantillonnage de GDAL : species et d130 sont donc comparés ici, à l'égalité
exacte, sans marge."""
import numpy as np
import pyarrow.parquet as pq
from pathlib import Path

import helpers_m3 as H

FIGE = Path(__file__).parent / "reference" / "entrees" / "trees_init" / "trees.parquet"
STABLES = ("x", "y", "h", "crown_area", "species", "d130")


def _par_id(table):
    t = table.sort_by("tree_id")
    return {k: t.column(k).to_numpy(zero_copy_only=False) for k in ("tree_id",) + STABLES}


def test_la_detection_les_houppiers_l_essence_et_le_d130_ne_dependent_pas_de_la_plateforme(chaine):
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
