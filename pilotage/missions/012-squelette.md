# Mission 012 — squelette

## Mission

**En une phrase (quoi, et pourquoi) :** Poser le squelette du dépôt (package R + `_targets.R` pour prepare/biomes/dynamics, espace cargo `simulate/`, package Python pour import_tarif/post/assets, `viewer-web/` npm, `viewer-massif/` Godot 4.6 vide, `config.yml` et `Makefile`), chaque module ne faisant encore que lire `config.yml` et appeler le validateur, pour que le parcours complet existe d'un bout à l'autre (BRIEF §12, spec §2).

**Redite par l'agent :** _à compléter par l'agent avant d'agir._

## Les trois questions (règle de staffing)

| Question | Réponse | Conséquence |
|---|---|---|
| Peut-il redire la mission en une phrase, avec son but ? | oui | |
| Sait-il comment faire ? | oui | sources nommées ci-dessous |
| A-t-il les moyens ? | oui | outils du conteneur (R 4.3, Rust 1.97, Python 3.13, réseau limité) |

**Temps de la main :** donner. **Degré de la main :** le chef tranche.

## Ma réponse d'abord

_Rempli par Pascal seul._

## L'Homme

- **Agent :** `dev` — **Modèle :** sonnet

## Harnais

- **Peut (périmètre) :** `R/`, `DESCRIPTION`, `NAMESPACE`, `_targets.R`, `simulate/`, `python/`, `viewer-web/`, `viewer-massif/`, `config.yml`, `Makefile`, `biomes/`.
- **Câblé (ne peut pas) :** pas de `main` ; pas de « terminé » sans tests verts ; journal en ajout seul.
- **Ne doit pas (écrit) :** écrire de la logique métier ; importer le code d'un module dans un autre ; faire un commit git (l'orchestrateur intègre).
- **Sources autorisées :** docs/spec.md, docs/BRIEF.md §12, CLAUDE.md (lisibilité du Rust).

## Journal

- **Ce que l'agent inscrit :** une ligne proposée à l'orchestrateur, dans son rendu.

## Valeur provisoire (chiffre, réglage)

- versions des outils : choisies et figées dans le README

## Dépend de / rouge attendu jusqu'à

- 009 pour l'appel au validateur (le squelette peut l'appeler par son chemin) ; ordre de fusion : 009 puis 012

## Tests

- chaque module se lance, lit `config.yml` et sort avec le code 0 ou 2 ; un test par langage

## Terrain

- **Échantillon que Pascal vérifiera :** au jalon M0, `make validate ZONE=zone_fictive` vert.

## Qui veille, qui tranche

- **Relecteur :** `relecteur`, puis Claude (orchestrateur, par délégation de Pascal).
- **Critère d'arrêt de la relecture :** 3 allers-retours ; au-delà, la décision remonte à Pascal.
- **Qui tranche :** Claude par délégation (pilotage/equipe.md), Pascal peut défaire.

## Comment saura-t-on que ça marche ?

chaque module se lance, lit `config.yml` et sort avec le code 0 ou 2 ; un test par langage.
