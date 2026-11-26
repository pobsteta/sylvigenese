# Mission 060 — Contrats de M5a et projet d'ADR 0006 (niveau SER)

## Mission

**En une phrase :** Contrats de M5a et projet d'ADR 0006 (niveau SER), pour fixer les formats avant le code, comme 033 pour M3a (§3). (plan `docs/plans/m5a.md`, mission B ; décisions de Pascal Q1 à Q5 du 26/11/2026).

## L'Homme

- **Agent :** `dev` — **Modèle :** sonnet — **Temps de la main :** donner.

## Harnais

- **Peut :** `contracts/` (schémas, `catalog.yml`, `README.md`, `tests/`), `config.yml`, `docs/adr/0006-niveau-ser.md` (statut « proposée »)
- **Ne doit pas :** toucher `simulate/`, `python/`, `R/` ; affaiblir un contrat existant ; mettre une valeur écologique dans un schéma
- **Câblé :** aucune commande git qui écrit ; tests vérifiés sur une copie `git archive HEAD`.

## Tests

- un cas conforme et un cas fautif par règle nouvelle ; `make validate` vert
