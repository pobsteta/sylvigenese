# Mission 027 — dettes de M1a faisables sans Pascal

## Mission

**En une phrase (quoi, et pourquoi) :** Solder les dettes de M1a reportées au journal qui ne demandent pas Pascal : import_tarif écrit le modèle etage_b depuis tarif-nemeton (colonnes a, b_lnH, c_lnCPA ; c_lnCPA = 0 lu comme absent), messages d'erreur accentués lisibles sous LC_ALL=C, garde des 65 534 polygones de stand_map avant toute écriture, et clé primaire avec valeur nulle dans le validateur, pour que M1b n'hérite que de ce qui demande vraiment Pascal.

**Redite par l'agent :** _à compléter par l'agent avant d'agir._

## Les trois questions

| Question | Réponse | Conséquence |
|---|---|---|
| Redire la mission ? | oui | |
| Sait-il faire ? | oui | |
| A-t-il les moyens ? | oui : /home/user/tarif-nemeton (resultats/etage_b/allometrie_D.csv, allometrie_D_ifn.csv), validateur et tests existants | |

**Temps de la main :** donner. **Degré de la main :** le chef tranche (orchestrateur, par délégation de Pascal).

## Ma réponse d'abord

_Rempli par Pascal seul._

## L'Homme

- **Agent :** `dev` — **Modèle :** sonnet
- **Ce qui ne lui est pas demandé :** les seuils de stade, la zone tampon, l'inventaire vidéo (à Pascal).

## Harnais

- **Peut (périmètre) :** `python/sylvigenese/import_tarif.py` et ses tests sous `python/`, `contracts/validator/` et `contracts/tests/`, `run_module` dans `R/modules.R` (seulement), `stand_map_values` et son appel dans `R/prepare_grid.R`, `R/tests/testthat/test-modules.R`, `R/tests/testthat/test-prepare-grid.R`.
- **Câblé :** pas de `main`, pas de « terminé » sans tests verts, journal en ajout seul ; aucune commande git qui écrit (l'orchestrateur commite).
- **Ne doit pas :** toucher à R/prepare_ifn.R ou au générateur (023) ; copier du code de tarif-nemeton (licence réservée à Pascal) : lire ses CSV de résultats seulement, en citant URL et commit.
- **Sources autorisées :** pilotage/journal.md (lignes de clôture de M1a), /home/user/tarif-nemeton (https://github.com/pobsteta/tarif-nemeton commit 0f51b96, lecture seule), docs/spec.md §3 et §4.3, contracts/README.md.

## Journal

- **Ce que l'agent inscrit :** une ligne par rendu et par aller-retour, proposée à l'orchestrateur.

## Valeur provisoire (chiffre, réglage)

- aucune nouvelle ; les coefficients importés gardent provisoire: true.

## Dépend de / rouge attendu jusqu'à

- aucune ; tourne en même temps que 022.

## Tests

- import_tarif sur un dossier tarif-nemeton réduit en test : modèle etage_b conforme, c absent quand c_lnCPA = 0 ; message accentué lu en UTF-8 sous LC_ALL=C ; stand_map > 65 534 polygones : code 2, aucune sortie ; doublon (H10, NULL) refusé.

## Terrain

- **Échantillon que Pascal vérifiera :** `params/allometry.parquet` produit depuis tarif-nemeton : coefficients par essence, avec et sans c.

## Qui veille, qui tranche

- **Relecteur :** `relecteur`, puis Claude par délégation (validation du jalon et fusion déléguées le 25/11/2026). **Arrêt :** 3 allers-retours. **Qui tranche :** Claude par délégation, Pascal peut défaire.

## Comment saura-t-on que ça marche ?

les quatre lignes de dettes du journal sont closes par une ligne de rendu, tests à l'appui.
