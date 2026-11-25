# Mission 044 — contrats de la suite de M4a (vue dans le temps)

## Mission

**En une phrase :** Fixer les formats avant le code : fiche de cellule v2 (évolution par année : tiges/ha, G, d moyen, composition, h_dom_m, signalements de `flags.parquet` ; « volume et carbone non calculés »), `tiles/index.json`, raster `web/rasters/g_<année>.tif`, bloc `assets` de `config.yml` (`year_step`, une année sur 10 par défaut), et `h_dom_m` dans `sim.cells`, pour que 045 à 048 visent la même cible (plan `docs/plans/m4a-suite-temps.md` §2 mission A et §3 ; décisions de Pascal Q1 à Q3 du 25/11/2026).

## L'Homme

- **Agent :** `dev` — **Modèle :** sonnet — **Temps de la main :** donner.

## Harnais

- **Peut :** `contracts/json/{cell_sheet,tiles_index,config}.schema.json`, `contracts/tables/sim/cells.schema.json`, le contrat des rasters web, `contracts/catalog.yml`, `contracts/tests/`, `contracts/README.md`.
- **Ne doit pas :** toucher `python/`, `viewer-web/`, `simulate/` ; affaiblir un contrat existant.
- **Câblé :** aucune commande git qui écrit.

## Tests

- Un cas conforme et un cas fautif par règle nouvelle ; `make validate` vert.
