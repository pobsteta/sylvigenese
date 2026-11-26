# Mission 051 — contrats de post (volume et carbone)

## Mission

**En une phrase :** Fixer les formats de `post` avant le code : `params/tarif` (modèle NEMETON v5 lu depuis `parametres_tarif_v5.csv`, domaine), `sim/summary` 0.2 (volume aérien total, biomasse, carbone aérien, carbone des racines à part et provisoire, tiges et part de G non calculées), `post.summary_zone`, `post.run` (`sim/post.json`, provenance et commit du tarif), fiche de cellule v3 (« volume partiel », sol et bois mort hors v1), pour que 052 à 054 visent la même cible (plan `docs/plans/post-volume-carbone.md` §4 ; décisions Q1 à Q6 du 26/11/2026).

## L'Homme

- **Agent :** `dev` — **Modèle :** sonnet — **Temps de la main :** donner.

## Harnais

- **Peut :** `contracts/` (schémas, catalogue, README, tests), le `params/tarif.parquet` synthétique du jeu fictif (`tools/fixtures/`) s'il doit suivre le nouveau contrat, un projet d'ADR `docs/adr/0005-tarif-dans-params.md` (statut « proposé »).
- **Ne doit pas :** toucher `python/sylvigenese/`, `viewer-web/`, `simulate/` ; affaiblir la fiche v1 ou v2 ; écrire une valeur écologique réelle.
- **Câblé :** aucune commande git qui écrit.

## Tests

- Un cas conforme et un cas fautif par règle nouvelle ; `make validate` vert.
