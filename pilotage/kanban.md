# Kanban de sylvigenese

> Cinq colonnes (fiche n° 8). Chaque carte porte l'Homme (qui), la Mission (quoi, quand,
> combien) et les Moyens (comment, où, avec qui), et renvoie à sa fiche dans
> `pilotage/missions/`. Elle note aussi depuis quel cycle de `/boucle` elle est dans sa
> colonne ; on change ce numéro chaque fois qu'elle change de colonne.
> **Une carte qui ne bouge pas est souvent la mauvaise nouvelle à dire tout de suite.**

**Dernier cycle :** 8 _(augmenté de 1 à la fin de chaque `/boucle`, même quand elle n'a
rien lancé. Une carte est immobile quand dernier cycle − N ≥ 2.)_

_Modèle de carte :_

```
- [NNN-titre](missions/NNN-titre.md) · depuis le cycle N
  - Homme : qui
  - Mission : quoi, quand, combien
  - Moyens : comment, où, avec qui
```

## Bac à sable

- M5b · référence technique `cohorts` et bascule de `config.yml` (Q4), `params/regeneration` du jeu fictif · depuis le cycle 8
- M5b · refus de post pour un massif simulé en `cohorts` (tant que le tarif n'est pas validé sur ces trajectoires) · depuis le cycle 8
- M5b · clé `external.*` pour Niinemets (non recopié) ; mise à jour de BRIEF §7.3 · depuis le cycle 8
- M5b · questions de sens à préparer pour Pascal : coefficient d'extinction pris comme conversion vers l'échelle de Niinemets ; troncature du noyau à K cellules · depuis le cycle 8
- M5b · identité de rustfft entre machines (avx/sse) à établir · depuis le cycle 8
- M5b · mentions Q2 et Q3 : aujourd'hui en signalements de t0 (sim/flags.parquet) ; à porter au rapport de simulation quand il existera · depuis le cycle 8
- Analyste · mesurer la forêt seule (option de part forestière) ; S × K à N = 2 000 · depuis le cycle 8

## Validé


## Planifié

- Reprises mineures de la relecture de post (facteurs du domaine lus et non écrits en dur, chemin local dans ifn-g-tiges.csv, docstring exclude_incomplete, rejeu du CSV prouvé) · depuis le cycle 8
- Critère b de post (V de l'IFN sur la SER pilote, décision de Pascal) : attend les données réelles · depuis le cycle 8
- [066-reprises-relecture-m5a](missions/066-reprises-relecture-m5a.md) · depuis le cycle 8
  - Homme : dev (opus), donner
  - Mission : reprises de la relecture de la PR n° 11 (stress_mortality, note d'index, ADR 0006, mineurs CI)
  - Moyens : arbre de travail, tests de .claude/test-command, relecture ensuite
- M5a (PR n° 11, à fusionner après 066), puis M6a (vue Godot) · depuis le cycle 7
- M3b (vraisemblance de la dynamique) : attend les données réelles et Pascal


## Terminé

- [050](missions/050-constantes-tarif-nemeton.md) à [058](missions/058-quantiles-ifn.md) · depuis le cycle 8
  - Homme : `acquereur` ×2, `dev` ×6, `testeur` ×2, `afficheur`, relus par `relecteur` (2 relectures)
  - Mission : post calcule volume aérien total, biomasse et carbone aérien (tarif NEMETON v5, tarif-nemeton 4ee122c), fiche v3 dans la vue, V de l'IFN gardé, quantiles IFN 2021-2025 de G et des tiges/ha ; 176 tests post
  - Moyens : PR pobsteta/sylvigenese#10, PR pobsteta/tarif-nemeton#3 (fusionnée par Pascal)

- [042](missions/042-mode-station-25m.md) à [049](missions/049-reprises-relecture-m4a.md) · depuis le cycle 7
  - Homme : `dev` ×6, `testeur`, `afficheur`, relus par `relecteur` (2 relectures)
  - Mission : suite de M4a remplie le 2026-11-25 sur le jeu fictif (vue iTowns dans le temps, 100 000 instances comptées par l'API, images par seconde relevées) ; type de station à 25 m sans GDAL ; CI découpée en 10 jobs, 10 min au lieu de 33 à 44
  - Moyens : PR pobsteta/sylvigenese#9

- [033](missions/033-contrats-m3.md) à [041](missions/041-reprises-relecture-m3a.md) · depuis le cycle 6
  - Homme : `dev` ×6, `testeur`, relus par `relecteur` (2 allers-retours)
  - Mission : jalon M3a rempli le 2026-11-25 sur le jeu fictif, sur son critère technique (CI verte à 62a5056 ; tests/m3 178/178) ; trajectoire « technique, non validée écologiquement » (décision de Pascal)
  - Moyens : PR pobsteta/sylvigenese#8

- [031](missions/031-dynamics-reponses-pascal.md), [032](missions/032-identifiants-en-anglais.md) · depuis le cycle 6
  - Homme : `dev` ×2, `testeur` · Mission : réponses de Pascal dans dynamics ; identifiants en anglais · Moyens : PR pobsteta/sylvigenese#7 et reprises dans #8

- [028](missions/028-assets-etat-initial.md), [029](missions/029-viewer-web-etat-initial.md), [030](missions/030-tests-m4-etat-initial.md) · depuis le cycle 5
  - Homme : `dev`, `afficheur`, `testeur`, relus par `relecteur` · Mission : vue iTowns de l'état initial, fusionnée le 2026-11-25 · Moyens : PR pobsteta/sylvigenese#6

- [022](missions/022-referentiel-ifn-dynamique.md) à [027](missions/027-dettes-m1a.md) · depuis le cycle 4
  - Homme : `acquereur`, `dev` ×4, `testeur`, relus par `relecteur`
  - Mission : jalon M2a rempli le 2026-11-25 sur le jeu fictif (CI verte à 37fde55 ; tests/m2 93/93)
  - Moyens : PR pobsteta/sylvigenese#5

- [017-prepare-grille](missions/017-prepare-grille.md), [018-prepare-arbres](missions/018-prepare-arbres.md), [019-prepare-ifn](missions/019-prepare-ifn.md), [020-biomes](missions/020-biomes.md), [021-tests-m1](missions/021-tests-m1.md) · depuis le cycle 2
  - Homme : `dev` ×4, `testeur`, relues deux fois par `relecteur`, 3 allers-retours
  - Mission : jalon M1a rempli le 2026-11-24 sur le jeu fictif (test-command vert : pytest 446 + 142, Rust 29 + 7, testthat, 0 sauté, 38 fichiers conformes ; 9 min 48 s) ; fusion soumise à Pascal
  - Moyens : PR pobsteta/sylvigenese#4

- [009-contrats](missions/009-contrats.md), [010-tests-contrats](missions/010-tests-contrats.md), [011-table-essences](missions/011-table-essences.md), [012-squelette](missions/012-squelette.md), [013-jeu-fictif](missions/013-jeu-fictif.md), [014-ci](missions/014-ci.md), [015-lecteur-geotiff-rust](missions/015-lecteur-geotiff-rust.md), [016-referentiels-m0](missions/016-referentiels-m0.md) · depuis le cycle 1
  - Homme : `dev` ×5, `testeur`, `acquereur` ×2, relues par `relecteur`
  - Mission : jalon M0a rempli le 2026-11-24 (CI verte à f1246ca, test-command vert, 410 tests pytest)
  - Moyens : PR pobsteta/sylvigenese#3

- [008-contrats-entrees](missions/008-contrats-entrees.md) · depuis le cycle 0
  - Homme : `acquereur` (sonnet)
  - Mission : rendue le 2026-11-24 : docs/referentiels/entrees-externes.{md,csv} ; 13 questions, tranchées par délégation sauf la licence de tarif-nemeton
  - Moyens : clones en lecture seule

- [007-etude-godot-forest-demo](missions/007-etude-godot-forest-demo.md) · depuis le cycle 0
  - Homme : `acquereur` (sonnet)
  - Mission : rendue le 2026-11-24 : docs/referentiels/godot-forest-demo.{md,-licences.csv} ; fil du forum et page FSF non lus (réseau)
  - Moyens : clone en lecture seule

- [002-banc-python](missions/002-banc-python.md), [003-banc-r](missions/003-banc-r.md), [004-banc-rust](missions/004-banc-rust.md) · depuis le cycle 0
  - Homme : `dev` (sonnet) ×3, relecture croisée `relecteur`
  - Mission : rendues et reprises le 2026-11-24 (AM1 à AM4)
  - Moyens : bench/{python,r,rust}/
- [005-banc-mesures](missions/005-banc-mesures.md) · depuis le cycle 0
  - Homme : `analyste` (sonnet)
  - Mission : rendue le 2026-11-24, préliminaire (conteneur 4 cœurs, 16 Go) : bench/results/RESULTATS.md ; script portable pour le PC de Pascal
  - Moyens : bench/results/run_bench.sh

- [006-surfaces-ser](missions/006-surfaces-ser.md) · depuis le cycle 0
  - Homme : `acquereur` (sonnet), extraction xlsx par l'orchestrateur
  - Mission : rendue le 2026-11-24 : docs/referentiels/surfaces-ser.{md,csv} ; plus grande SER C20 (29 980 km²)
  - Moyens : tableaux IGN ts_2021-2025_ser.zip

- [001-moteurs-existants](missions/001-moteurs-existants.md) · depuis le cycle 0
  - Homme : `acquereur` (sonnet)
  - Mission : rendue le 2026-11-24 : docs/referentiels/moteurs-existants.{md,csv} ; points non vérifiés (hôtes bloqués)
  - Moyens : recherche web sourcée

## Abandonné

_Avec la raison, en une ligne._

## Livraisons

_Une ligne par cycle, ajoutée sous la précédente à la fin de chaque `/boucle`, et une
par `/bilan` : la livraison que Pascal a retenue, pour qui, et ce qu'elle apporte de plus
que la précédente du même rythme. On lance petit (fiche n° 12) : la plus petite version
qui rend déjà un service réel, un MVP, essayée tout de suite sur le terrain. Un cycle sans livraison neuve livre sa mauvaise
nouvelle, car
« une mauvaise nouvelle est une livraison sur laquelle on apprend » (Pascal) : on
l'inscrit avec ce qu'elle nous apprend._

```
- cycle N · livraison · pour qui · ce qu'elle apporte de plus que la précédente
- cycle N · mauvaise nouvelle : … · pour qui · ce qu'elle nous apprend
- bilan du AAAA-MM-JJ · livraison · pour qui · ce qu'elle apporte de plus que la précédente
- bilan du AAAA-MM-JJ · mauvaise nouvelle : … · pour qui · ce qu'elle nous apprend
```

- cycle 1 · livraison : jalon M0 (contrats et validateur, squelette des modules, jeu d'essai fictif, lecteur GeoTIFF Rust, CI) · pour Pascal · `make validate ZONE=<zone>` dit tout de suite si ses propres sorties nemeton, sylvostation et typopeuplement entrent dans la chaîne, ce que rien ne permettait avant
- cycle 6 · livraison : jalon M3a (moteur simulate en Rust : 100 ans sur le massif fictif, identité au bit près de 1 à 7 fils, contrôles et codes de sortie, non-régression sur entrées figées) · pour Pascal · la chaîne va désormais jusqu'à un futur simulé ; mauvaise nouvelle apprise en même temps : la trajectoire fictive n'est pas une forêt (G 91 → 353 m²/ha), et GDAL change ses résultats selon sa version (mission 042)
- cycle 7 · livraison : suite de M4a, la vue iTowns fait défiler les années simulées (curseur, fiche d'évolution avec la hauteur dominante face au plafond, carte de surface terrière à échelle fixe) · pour Pascal · on voit pour la première fois le futur simulé, cellule par cellule ; mauvaise nouvelle : sans carte graphique, la dernière année (402 437 arbres) ne se relève pas, le rendu réel se jugera sur le portable de Pascal (M4 b)
- cycle 8 · livraison : post calcule le volume aérien total et le carbone aérien de chaque cellule et de chaque année avec le tarif NEMETON v5, et la vue les montre, « volume partiel » compris · pour Pascal · le futur simulé se lit en m³ et en tC, sans extrapolation ; mauvaise nouvelle : avec le tarif réel, 78 % de la surface terrière du jeu fictif est hors domaine à t0, et les quantiles IFN confirment que le jeu fictif est trop dense (91 m²/ha contre une médiane de 23,6)
