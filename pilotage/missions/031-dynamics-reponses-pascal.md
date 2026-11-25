# Mission 031 — dynamics : réponses de Pascal (chablis, revisites)

## Mission

**En une phrase (quoi, et pourquoi) :** Appliquer dans `dynamics` les deux décisions de Pascal du 25/11/2026 (journal) : les chablis (code A de VEGET5, 2010-2018) comptent comme morts dans la mortalité, et le recrutement ne s'ajuste que sur les revisites de 2015 et après (les revisites 2010-2014 servent à la mortalité seulement), pour que les paramètres suivent les règles retenues.

**Redite par l'agent :** _à compléter par l'agent avant d'agir._

## Les trois questions

| Question | Réponse | Conséquence |
|---|---|---|
| Redire la mission ? | oui | |
| Sait-il faire ? | oui : R/dynamics.R, spec §6, journal | |
| A-t-il les moyens ? | oui : jeu fictif (revisites 2020-2025 ; une variante doit porter des revisites 2010-2014 et des chablis A) | |

**Temps de la main :** donner. **Degré de la main :** le chef tranche (orchestrateur, par délégation).

## L'Homme

- **Agent :** `dev` — **Modèle :** sonnet
- **Ce qui ne lui est pas demandé :** recaler le houppier (M2b) ; Tichý (M2b).

## Harnais

- **Peut (périmètre) :** `R/dynamics.R`, `R/tests/testthat/test-dynamics.R`, `docs/spec.md` §6 (deux lignes « Données d'ajustement »).
- **Câblé :** pas de `main`, pas de « terminé » sans tests verts, journal en ajout seul ; aucune commande git qui écrit.
- **Ne doit pas :** toucher au générateur ni à prepare.
- **Sources autorisées :** docs/spec.md §6, docs/referentiels/ifn-dynamique.md, journal du 25/11/2026 (questions 1 et 2 de M2b).

## Valeur provisoire

- aucune nouvelle.

## Dépend de / rouge attendu jusqu'à

- aucune ; 039 (testeur) écrit les tests d'acceptation correspondants en parallèle.

## Tests

- testthat : variante synthétique avec chablis A 2010-2018 (comptés morts) et revisites 2012 (dans la mortalité, hors du recrutement) ; rapport qui le dit.

## Terrain

- **Échantillon que Pascal vérifiera :** `rapport_dynamics.html` : ligne « chablis comptés comme morts », et la plage de campagnes du recrutement.

## Qui veille, qui tranche

- **Relecteur :** `relecteur`, puis Claude par délégation. **Arrêt :** 3 allers-retours.
