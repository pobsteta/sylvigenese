# Mission 068 — contrats m6a (M6a, mission B du plan)

## Mission

**En une phrase :** Contrats de M6a et projet d'ADR 0007 (arbres du générateur et vue massif), avant tout code, comme 033 et 060. Contenu : `massif_block` v2 (§4) ; `massif/index.json` ; règle de nom des `.glb` et de leurs extras ; validateur de `.glb` renforcé ; seuils des stades sortis de `R/biomes.R` vers un fichier unique lu par R et par Python (T11) ; accord de la spec §9 (« un fichier par niveau de détail ») avec le BRIEF §4 (T2) ; contrat des exemplaires (Parquet, repère z-up, voir §4) ; fichier de paramètres des dimensions de référence (selon Q6).

Référence : [`docs/plans/m6a.md`](../../docs/plans/m6a.md) §3 (ligne B), avec les réponses de Pascal Q1 à Q8 du 26/11/2026 (journal) et la critique du contradicteur intégrée au plan.

## L'Homme

- **Agent :** `dev` — **Temps de la main :** donner.

## Harnais

- **Peut :** `contracts/` (schémas, `catalog.yml`, `README.md`, `validator/`, `tests/`), `config.yml`, `docs/adr/0007-arbres-generateur-vue-massif.md` (« proposée »), `docs/spec.md` (§2, §9, §10 : mise en accord seulement), `biomes/` (fichier des seuils de stade)
- **Ne doit pas :** toucher `python/`, `R/`, `simulate/`, `viewer-*` ; affaiblir un contrat ; mettre une valeur écologique dans un schéma ; inventer une valeur écologique ; trancher une question de sens (la poser dans le compte rendu).
- **Câblé :** aucune commande git qui écrit dans sylvigenese ; disque juste (quelques Go), nettoyer ce qui est créé.

## Tests

- un cas conforme et un cas fautif par règle nouvelle ; un `.glb` tronqué, sans nœud LOD2, ou sans `extras.source_commit`, refusé ; `make validate` vert
