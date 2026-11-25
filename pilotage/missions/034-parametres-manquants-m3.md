# Mission 034 — parametres-manquants-m3

## Mission

**En une phrase (quoi, et pourquoi) :** Apporter les paramètres qui manquent au moteur : courbe de Korf du hêtre reprise de nemeton (citée, provisoire) dans dynamics, allométries hcb et cw (synthétiques et provisoires dans le jeu fictif, import_tarif depuis tarif-nemeton pour le réel), table essence → bande de site_potential, et le bloc simulate de config.yml.

**Redite par l'agent :** _à compléter par l'agent avant d'agir._

## Les trois questions

| Question | Réponse | Conséquence |
|---|---|---|
| Redire la mission ? | oui | |
| Sait-il faire ? | oui : docs/plans/m3a-simulate.md, spec, contrats | |
| A-t-il les moyens ? | oui, après 031 (R/dynamics.R) et 033 (contrats) | |

**Temps de la main :** donner. **Degré de la main :** le chef tranche (orchestrateur, par délégation).

## L'Homme

- **Agent :** `dev` — **Modèle :** sonnet

## Harnais

- **Peut (périmètre) :** `R/dynamics.R` et son test, `python/sylvigenese/import_tarif.py` et ses tests, `tools/fixtures/make_zone_fictive.py` (paramètres), `tests/fixtures/zone_fictive/params/`, `config.yml` (bloc simulate), `contracts/json/config.schema.json`
- **Câblé :** pas de `main`, pas de « terminé » sans tests verts, journal en ajout seul ; aucune commande git qui écrit ; tests vérifiés sur une copie `git archive HEAD` (aucune dépendance aux sorties ignorées par git).
- **Ne doit pas :** inventer une valeur écologique ; sortir du périmètre ; macros maison ou génériques avancés dans le cœur de `simulate` (CLAUDE.md, lisibilité du Rust).
- **Sources autorisées :** docs/plans/m3a-simulate.md ; docs/spec.md §2, §4 à §6, §9 à §11 ; docs/adr/0001, 0002, 0004 ; contracts/ ; journal du 25/11/2026 (Q1 à Q4, T1 à T10).

## Dépend de / rouge attendu jusqu'à

- dépend de 031 et 033

## Tests

- testthat et pytest ; make dynamics et make validate verts

## Qui veille, qui tranche

- **Relecteur :** `relecteur`, puis Claude par délégation. **Arrêt :** 3 allers-retours.
