# Mission 013 — jeu-fictif

## Mission

**En une phrase (quoi, et pourquoi) :** Écrire un générateur à graine fixée du jeu d'essai fictif (`tests/fixtures/zone_fictive/inputs/`) aux formats et noms de colonnes réels de la spec §3, mailles différentes comprises (20 m, 25 m, 26,6 m, MNH 50 cm), avec des paramètres synthétiques marqués `provisoire: true`, pour que tous les jalons « a » tournent sans données réelles.

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

- **Peut (périmètre) :** `tools/fixtures/` (générateur) et `tests/fixtures/zone_fictive/`.
- **Câblé (ne peut pas) :** pas de `main` ; pas de « terminé » sans tests verts ; journal en ajout seul.
- **Ne doit pas (écrit) :** mettre une valeur présentée comme écologique ; dépasser 20 Mo versionnés ; faire un commit git (l'orchestrateur intègre).
- **Sources autorisées :** docs/spec.md §3, docs/referentiels/entrees-externes.{md,csv}, bench/SPEC.md (aléa).

## Journal

- **Ce que l'agent inscrit :** une ligne proposée à l'orchestrateur, dans son rendu.

## Valeur provisoire (chiffre, réglage)

- taille du massif fictif (par ex. 2 km × 2 km) : choisie par l'agent, provisoire

## Dépend de / rouge attendu jusqu'à

- 009 ; ordre de fusion : 009 puis 013

## Tests

- le générateur est rejouable au bit près ; le validateur de 009 accepte les fichiers produits

## Terrain

- **Échantillon que Pascal vérifiera :** au jalon M0, `make validate ZONE=zone_fictive` vert.

## Qui veille, qui tranche

- **Relecteur :** `relecteur`, puis Claude (orchestrateur, par délégation de Pascal).
- **Critère d'arrêt de la relecture :** 3 allers-retours ; au-delà, la décision remonte à Pascal.
- **Qui tranche :** Claude par délégation (pilotage/equipe.md), Pascal peut défaire.

## Comment saura-t-on que ça marche ?

le générateur est rejouable au bit près ; le validateur de 009 accepte les fichiers produits.
