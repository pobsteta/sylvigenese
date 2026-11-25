# Mission 024 — variables de station aux placettes IFN

## Mission

**En une phrase (quoi, et pourquoi) :** Remplir à la placette IFN les colonnes laissées vides en M1a, trophic (moyenne des valeurs indicatrices de la flore, méthode de sylvostation R/placettes.R), coarse_hydric_700m et coarse_bioclim_700m (moyenne des gradients de station dans un disque de 700 m) et ser_code (SER sous-jacente, par une règle grossière à 700 m), sans jamais croiser la placette avec un raster fin (garde IFN), pour que dynamics dispose de la station à l'ajustement (spec §6).

**Redite par l'agent :** _à compléter par l'agent avant d'agir._

## Les trois questions

| Question | Réponse | Conséquence |
|---|---|---|
| Redire la mission ? | oui | |
| Sait-il faire ? | oui : méthode de sylvostation, garde, spec §6 | |
| A-t-il les moyens ? | oui une fois 022 et 023 rendus ; les valeurs indicatrices viennent de la source que 022 aura établie (si elle manque au dépôt : provisoire et signalé) | |

**Temps de la main :** donner. **Degré de la main :** le chef tranche (orchestrateur, par délégation de Pascal).

## Ma réponse d'abord

_Rempli par Pascal seul._

## L'Homme

- **Agent :** `dev` — **Modèle :** opus
- **Ce qui ne lui est pas demandé :** le module dynamics ; TAXREF v13 vers v18 (le réseau vers taxref.mnhn.fr reste fermé : signalé).

## Harnais

- **Peut (périmètre) :** `R/ifn_station.R` (nouveau), `R/tests/testthat/test-ifn-station.R`, l'appel dans `R/prepare_ifn.R` (une ligne, après 023), `params/` ou `contracts/` pour une table des valeurs indicatrices si 022 la fournit.
- **Câblé :** pas de `main`, pas de « terminé » sans tests verts, journal en ajout seul ; aucune commande git qui écrit (l'orchestrateur commite).
- **Ne doit pas :** extraire un raster fin à une placette (la garde doit le refuser, test à l'appui) ; inventer une valeur indicatrice.
- **Sources autorisées :** docs/spec.md §6, CLAUDE.md (règle IFN), R/ifn_guard.R, /tmp/claude-0/repos/sylvostation/R/placettes.R et inst/extdata/ (lecture seule, citer URL et commit), docs/referentiels/ifn-dynamique.md.

## Journal

- **Ce que l'agent inscrit :** une ligne par rendu et par aller-retour, proposée à l'orchestrateur.

## Valeur provisoire (chiffre, réglage)

- la règle de ser_code à la placette (SER majoritaire dans le disque de 700 m) : provisoire, à confirmer avec Pascal en M2b.

## Dépend de / rouge attendu jusqu'à

- dépend de 022 et 023 ; précède 025.

## Tests

- la garde refuse station_gradients.tif aux placettes ; coarse_* recalculées indépendamment sur une grille simple ; trophic recalculé sur deux placettes à la main.

## Terrain

- **Échantillon que Pascal vérifiera :** `rapport_prepare.html` : section IFN sans colonne vide signalée, sauf ce qui reste bloqué (TAXREF).

## Qui veille, qui tranche

- **Relecteur :** `relecteur`, puis Claude par délégation (validation du jalon et fusion déléguées le 25/11/2026). **Arrêt :** 3 allers-retours. **Qui tranche :** Claude par délégation, Pascal peut défaire.

## Comment saura-t-on que ça marche ?

`ifn/plots.parquet` n'a plus de colonne vide de station, et la garde IFN est testée sur ce chemin.
