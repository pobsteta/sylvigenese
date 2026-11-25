# Mission 049 — reprises de la relecture de la suite de M4a

## Mission

**En une phrase :** Reprendre les points M1, M2, I1 à I4 et I8 de la relecture de la PR n° 9 (journal du 25/11/2026), pour fermer la suite de M4a sans dette connue.

## L'Homme

- **Agent :** `dev` — **Modèle :** sonnet — **Temps de la main :** donner.

## Harnais

- **Peut :**
  - M1 : `viewer-web/src/page/page.ts` (`loadYear` : retirer la couche abandonnée avant d'en ajouter une ; jamais plus de deux couches d'arbres) et un test node qui le prouve, si la logique se sort dans `temps.ts` ;
  - M2 : `.github/workflows/ci.yml` et `tools/ci/run_tests.sh` (la section `validate` tourne aussi après `m4`, là où les sorties d'`assets` existent) ; un relevé des comptes de tests avant/après 043 (`pytest --collect-only -q` sur e6e20ed et sur HEAD, par suite ; cargo et node) écrit dans `docs/plans/m4a-suite-temps.md` §6 ;
  - I1 : description de `h_dom_m` dans `contracts/tables/sim/cells.schema.json` (fin d'année, écrite par simulate depuis 046) ;
  - I2 : `python/sylvigenese/assets_lib/` : une ligne avec des tiges et un `h_dom_m` null est signalée (refus code 2, cause nommée), jamais affichée « aucun arbre vivant » ; son test ;
  - I3 : un cas conforme « h_dom_m null » dans `contracts/tests` ;
  - I4 : la description de `tree_id` (contrat `trees` ou `simulate.flags`) dit qu'un tree_id n'est jamais fait de chiffres seuls, et un cas fautif ;
  - I8 : un renvoi en spec §9 vers les contrats de la fiche v2, de `tiles/index.json` et de `assets.year_step`.
- **Ne doit pas :** modifier un test de `tests/m4` ou `tests/m3` ; sauter un test ; changer une sortie existante.
- **Câblé :** aucune commande git qui écrit.

## Tests

- `npm test`, typage, `pytest python/tests contracts/tests`, `make validate` verts sur une copie `git archive HEAD` + fichiers.
