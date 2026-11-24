# Mission 011 — table-essences

## Mission

**En une phrase (quoi, et pourquoi) :** Établir `contracts/species.csv` (espar en chaîne avec zéro de tête ↔ codes nemeton ↔ codes tarif-nemeton ↔ CD_REF TAXREF v18), avec la source de chaque ligne et la règle de `Quercus_spec`, pour que tous les modules parlent la même nomenclature (spec §8).

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

- **Peut (périmètre) :** `contracts/species.csv` et `docs/referentiels/species.md`.
- **Câblé (ne peut pas) :** pas de `main` ; pas de « terminé » sans tests verts ; journal en ajout seul.
- **Ne doit pas (écrit) :** inventer un code ; recopier une nomenclature sans la citer ; faire un commit git (l'orchestrateur intègre).
- **Sources autorisées :** docs/referentiels/entrees-externes.{md,csv}, clones /tmp/claude-0/repos/{nemeton,sylvostation}, /home/user/tarif-nemeton (lecture seule), sources IFN et TAXREF publiques.

## Journal

- **Ce que l'agent inscrit :** une ligne proposée à l'orchestrateur, dans son rendu.

## Valeur provisoire (chiffre, réglage)

- aucune

## Dépend de / rouge attendu jusqu'à

- aucune (le schéma de 009 validera la table après coup)

## Tests

- une ligne par essence connue des trois dépôts ; chaque ligne sourcée ; colonnes validées par le schéma de 009 une fois intégré

## Terrain

- **Échantillon que Pascal vérifiera :** au jalon M0, `make validate ZONE=zone_fictive` vert.

## Qui veille, qui tranche

- **Relecteur :** `relecteur`, puis Claude (orchestrateur, par délégation de Pascal).
- **Critère d'arrêt de la relecture :** 3 allers-retours ; au-delà, la décision remonte à Pascal.
- **Qui tranche :** Claude par délégation (pilotage/equipe.md), Pascal peut défaire.

## Comment saura-t-on que ça marche ?

une ligne par essence connue des trois dépôts ; chaque ligne sourcée ; colonnes validées par le schéma de 009 une fois intégré.
