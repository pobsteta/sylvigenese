# Mission 010 — tests-contrats

## Mission

**En une phrase (quoi, et pourquoi) :** Écrire les tests d'acceptation du validateur `contracts/validate` à partir de la spec et de l'ADR 0002, sans lire son code, pour que la mission 009 ne s'auto-évalue pas.

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

- **Agent :** `testeur` — **Modèle :** sonnet

## Harnais

- **Peut (périmètre) :** `tests/contracts/` (fichiers d'essai conformes et fautifs, tests pytest).
- **Câblé (ne peut pas) :** pas de `main` ; pas de « terminé » sans tests verts ; journal en ajout seul.
- **Ne doit pas (écrit) :** lire `contracts/` avant d'avoir écrit les tests ; affaiblir une assertion pour la faire passer ; faire un commit git (l'orchestrateur intègre).
- **Sources autorisées :** docs/spec.md, docs/adr/0002-contrats-et-formats.md.

## Journal

- **Ce que l'agent inscrit :** une ligne proposée à l'orchestrateur, dans son rendu.

## Valeur provisoire (chiffre, réglage)

- aucune

## Dépend de / rouge attendu jusqu'à

- aucune ; rouge attendu tant que 009 n'est pas intégré

## Tests

- les tests tournent ; chacun échoue sur un fichier fautif ciblé

## Terrain

- **Échantillon que Pascal vérifiera :** au jalon M0, `make validate ZONE=zone_fictive` vert.

## Qui veille, qui tranche

- **Relecteur :** `relecteur`, puis Claude (orchestrateur, par délégation de Pascal).
- **Critère d'arrêt de la relecture :** 3 allers-retours ; au-delà, la décision remonte à Pascal.
- **Qui tranche :** Claude par délégation (pilotage/equipe.md), Pascal peut défaire.

## Comment saura-t-on que ça marche ?

les tests tournent ; chacun échoue sur un fichier fautif ciblé.
