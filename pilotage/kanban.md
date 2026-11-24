# Kanban de sylvigenese

> Cinq colonnes (fiche n° 8). Chaque carte porte l'Homme (qui), la Mission (quoi, quand,
> combien) et les Moyens (comment, où, avec qui), et renvoie à sa fiche dans
> `pilotage/missions/`. Elle note aussi depuis quel cycle de `/boucle` elle est dans sa
> colonne ; on change ce numéro chaque fois qu'elle change de colonne.
> **Une carte qui ne bouge pas est souvent la mauvaise nouvelle à dire tout de suite.**

**Dernier cycle :** 1 _(augmenté de 1 à la fin de chaque `/boucle`, même quand elle n'a
rien lancé. Une carte est immobile quand dernier cycle − N ≥ 2.)_

_Modèle de carte :_

```
- [NNN-titre](missions/NNN-titre.md) · depuis le cycle N
  - Homme : qui
  - Mission : quoi, quand, combien
  - Moyens : comment, où, avec qui
```

## Bac à sable

## Validé

## Planifié





## Terminé

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
