# Mission 021 — tests-m1

## Mission

**En une phrase (quoi, et pourquoi) :** Écrire les tests d'acceptation du jalon M1a à partir de la spec, sans lire le code de prepare et de biomes, pour que les missions 017 à 020 ne s'auto-évaluent pas.

**Redite par l'agent :** _à compléter par l'agent avant d'agir._

## Les trois questions

| Question | Réponse | Conséquence |
|---|---|---|
| Redire la mission ? | oui | |
| Sait-il faire ? | oui | sources ci-dessous |
| A-t-il les moyens ? | oui, en partie | R 4.3.3 avec terra 1.7.65 et sf 1.0.15 ; targets et lidR à installer depuis CRAN ou r-universe, s'ils sont joignables ; sinon le dire |

**Temps de la main :** donner. **Degré de la main :** le chef tranche.

## Ma réponse d'abord

_Rempli par Pascal seul._

## L'Homme

- **Agent :** `testeur` — **Modèle :** sonnet

## Harnais

- **Peut (périmètre) :** `tests/m1/` (pytest qui lance `make prepare` et `make biomes` sur le jeu fictif, puis contrôle les sorties).
- **Périmètre étendu aux reprises (accepté par l'orchestrateur, journal du 24/11/2026) :** variantes de zone dans tests/m1/conftest.py.
- **Câblé :** pas de `main`, pas de « terminé » sans tests verts, journal en ajout seul.
- **Ne doit pas :** lire `R/prepare_*.R` ou `R/biomes.R` avant d'avoir écrit les tests ; faire un commit git.
- **Sources autorisées :** docs/spec.md, contracts/README.md, tests/fixtures/zone_fictive/README.md.

## Valeur provisoire

- aucune

## Dépend de / rouge attendu jusqu'à

- aucune ; rouge attendu jusqu'aux missions 017 à 020

## Tests

- les tests couvrent : grille alignée à 25 m, SER sous-jacente des alluvions avec ligne de rapport, H0 à partir du MNH, garde IFN, trees_init avec sources, aucune cellule forestière orpheline non signalée

## Terrain

- **Échantillon que Pascal vérifiera :** `make prepare biomes trees ZONE=zone_fictive`, puis `rapport_prepare.html`, `rapport_biomes.html` et `rapport_arbres.html` ouverts dans un navigateur (étape trees ajoutée par la décision du journal du 24/11/2026).

## Qui veille, qui tranche

- **Relecteur :** `relecteur`, puis Claude par délégation. **Arrêt :** 3 allers-retours. **Qui tranche :** Claude par délégation, Pascal peut défaire.
