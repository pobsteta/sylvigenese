# Mission 016 — referentiels-m0

## Mission

**En une phrase (quoi, et pourquoi) :** Établir trois points pour la suite : la documentation des données brutes IFN (cercles de placette, unité de c13), l'instanciation glTF dans le code d'iTowns (OGC3DTilesLayer), la disponibilité de la grille RAF20 derrière le réseau de la session, pour lever les hypothèses de la spec §12.

**Redite par l'agent :** _à compléter par l'agent avant d'agir._

## Les trois questions (règle de staffing)

| Question | Réponse | Conséquence |
|---|---|---|
| Peut-il redire la mission en une phrase, avec son but ? | oui | |
| Sait-il comment faire ? | oui | sources nommées ci-dessous |
| A-t-il les moyens ? | oui | outils du conteneur (R 4.3, Rust 1.97, Python 3.13, réseau limité) |

**Temps de la main :** donner. **Degré de la main :** sollicitation d'avis.

## Ma réponse d'abord

_Rempli par Pascal seul._

## L'Homme

- **Agent :** `acquereur` — **Modèle :** sonnet

## Harnais

- **Peut (périmètre) :** `docs/referentiels/ifn-placettes.md`, `docs/referentiels/itowns-instancing.md`, `docs/referentiels/raf20.md`.
- **Câblé (ne peut pas) :** pas de `main` ; pas de « terminé » sans tests verts ; journal en ajout seul.
- **Ne doit pas (écrit) :** deviner un contenu bloqué par le réseau ; faire un commit git (l'orchestrateur intègre).
- **Sources autorisées :** sources publiques IGN, dépôt iTowns sur GitHub (clonable), data.geopf.fr.

## Journal

- **Ce que l'agent inscrit :** une ligne proposée à l'orchestrateur, dans son rendu.

## Valeur provisoire (chiffre, réglage)

- aucune

## Dépend de / rouge attendu jusqu'à

- aucune

## Tests

- chaque point a sa source lue, ou est dit non vérifiable avec la raison

## Terrain

- **Échantillon que Pascal vérifiera :** au jalon M0, `make validate ZONE=zone_fictive` vert.

## Qui veille, qui tranche

- **Relecteur :** `relecteur`, puis Claude (orchestrateur, par délégation de Pascal).
- **Critère d'arrêt de la relecture :** 3 allers-retours ; au-delà, la décision remonte à Pascal.
- **Qui tranche :** Claude par délégation (pilotage/equipe.md), Pascal peut défaire.

## Comment saura-t-on que ça marche ?

chaque point a sa source lue, ou est dit non vérifiable avec la raison.
