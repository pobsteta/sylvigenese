# Mission 091 — solder le bac à sable de la vue massif (M6b) faisable sans données réelles

## Mission

**En une phrase :** Reprendre une à une les cartes M6b du bac à sable du kanban, dire pour
chacune si elle est déjà faite, à faire ici, ou dépendante des données réelles ou de l'œil de
Pascal, et faire celles qui se font sur le jeu fictif (délégation de Pascal du 28/11/2026 :
« continue le dev … jusqu'à ce que tu sois bloqué par … les données tests »).

## L'Homme

- **Agent :** `dev` — **Temps de la main :** donner.

## Ce qui est attendu

1. **État de chaque carte M6b** de `pilotage/kanban.md` (bac à sable) : constantes d'affichage
   (beaucoup sont déjà dans le bloc `viewer` de `config.yml`) ; densité d'herbe, fondu entre
   niveaux, retour en Lambert-93 ; échelle des semis génériques (rayon = h, à mettre à (r, h, r)
   faute de cw) ; essence à semis sans modèle `young` non dite dans les notes de l'index ;
   scénario 2022 de `bench/m6/mesurer.py` (lignes écrites à la main dans `m6_selftest.csv`) ;
   défauts des captures du 27/11 (troncs, feuillage, perches, bandeau, nord, caméra sans
   clavier, résolution). Pour chacune : fait (où), à faire ici, ou réservé (données réelles,
   œil de Pascal, autre dépôt comme tarif-nemeton), avec la raison.
2. **Faire celles qui se font ici**, en priorité : échelle des semis ; essence à semis sans
   modèle `young` dite ; scénario 2022 du banc ; caméra au clavier si elle manque (déplacement
   et rotation, réglages déjà dans `viewer.camera`). Toute constante d'affichage nouvelle va
   dans le bloc `viewer` de `config.yml`, marquée « illustration, non mesurée ».
3. **Ne rien inventer d'écologique** : un rayon de semis sans source reste marqué provisoire et
   dit dans les notes.

## Harnais

- **Peut :** `viewer-massif/` (scripts, tests GUT, README), `config.yml` (bloc `viewer`
  seulement) et ses copies de tests/fixtures si le schéma l'exige, `contracts/` (schéma du bloc
  `viewer` et ses tests, si une clé s'ajoute), `python/sylvigenese/assets*` (notes de l'index
  seulement), `bench/m6/`, `tests/m6/`.
- **Ne doit pas :** changer un résultat de `simulate` ; toucher `.github/`, `viewer-web/`,
  `README.md` racine, `simulate/` ; commiter ; pousser ; toucher à `pilotage/journal.md`,
  `.claude/`, `main`.
- **Câblé :** Godot 4.6.3 et la Quadro sont disponibles sur cette machine ; captures et essais
  hors dépôt sous `data/`.

## Tests

- GUT de `viewer-massif` (`godot --headless --path viewer-massif -s addons/gut/gut_cmdln.gd
  -gdir=res://tests -gexit`) vert, 0 sauté ; `bash tools/ci/run_tests.sh m6 contrats` vert.
- Un test par changement visible (échelle des semis, note de l'essence sans `young`, clavier).

## Dépend de / rouge attendu jusqu'à

- Rien. Aucun rouge attendu.

## Échantillon terrain

- Captures avant et après (semis) sur la Quadro, au point 700 500 / 6 500 500 de `m6_essai`.
