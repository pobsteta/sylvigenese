# Mission 009 — contrats

## Mission

**En une phrase (quoi, et pourquoi) :** Écrire `contracts/` en trois couches (Table Schema figé pour Parquet et CSV, JSON Schema pour YAML et JSON avec les schémas 3D Tiles de CesiumGS, profil GeoTIFF) et le validateur en ligne de commande `contracts/validate`, pour que chaque module de la spec §2 vérifie ses entrées et sorties (ADR 0002).

**Redite par l'agent :** _à compléter par l'agent avant d'agir._

## Les trois questions (règle de staffing)

| Question | Réponse | Conséquence |
|---|---|---|
| Peut-il redire la mission en une phrase, avec son but ? | oui | |
| Sait-il comment faire ? | oui | sources nommées ci-dessous |
| A-t-il les moyens ? | oui | outils du conteneur (R 4.3, Rust 1.97, Python 3.13, réseau limité) |

**Temps de la main :** prendre. **Degré de la main :** le chef tranche.

## Ma réponse d'abord

_Rempli par Pascal seul._

## L'Homme

- **Agent :** `dev` — **Modèle :** opus

## Harnais

- **Peut (périmètre) :** `contracts/` (sauf `contracts/species.csv`).
- **Câblé (ne peut pas) :** pas de `main` ; pas de « terminé » sans tests verts ; journal en ajout seul.
- **Ne doit pas (écrit) :** inventer une colonne absente de la spec §2-§9 ; mettre une valeur écologique dans un schéma ; faire un commit git (l'orchestrateur intègre).
- **Sources autorisées :** docs/spec.md §2-§10, docs/adr/0002-contrats-et-formats.md, docs/referentiels/entrees-externes.{md,csv}, bench/SPEC.md (codes de sortie).

## Journal

- **Ce que l'agent inscrit :** une ligne proposée à l'orchestrateur, dans son rendu.

## Valeur provisoire (chiffre, réglage)

- version de Table Schema (v1 ou v2) : choisie et figée par l'agent, dite dans le rendu

## Dépend de / rouge attendu jusqu'à

- 010 (tests écrits en parallèle) ; ordre de fusion : 010 puis 009 ; rouge attendu : les tests de 010 tant que 009 n'est pas intégré

## Tests

- les tests d'acceptation de la mission 010 passent ; un fichier conforme et un fichier fautif par contrat

## Terrain

- **Échantillon que Pascal vérifiera :** au jalon M0, `make validate ZONE=zone_fictive` vert.

## Qui veille, qui tranche

- **Relecteur :** `relecteur`, puis Claude (orchestrateur, par délégation de Pascal).
- **Critère d'arrêt de la relecture :** 3 allers-retours ; au-delà, la décision remonte à Pascal.
- **Qui tranche :** Claude par délégation (pilotage/equipe.md), Pascal peut défaire.

## Comment saura-t-on que ça marche ?

les tests d'acceptation de la mission 010 passent ; un fichier conforme et un fichier fautif par contrat.
