# Mission 092 — mineurs des relectures des PR 19 et 23

## Mission

**En une phrase :** Solder les mineurs relevés par le relecteur sur les PR 19 (087) et 23 (090,
091), sans changer un résultat de la chaîne (délégation de Pascal du 28/11/2026).

## L'Homme

- **Agent :** `dev` — **Temps de la main :** donner.

## Ce qui est attendu

1. **Clavier AZERTY** (`viewer-massif/README.md:12`) : dire les touches selon la disposition
   (Godot lit des touches physiques : sur AZERTY, monter/descendre et gauche se lisent autrement
   que sur QWERTY) ; vérifier dans `camera_fly.gd` ce qui est lu (code physique ou caractère) et
   écrire la vérité pour les deux dispositions. Pascal utilise un clavier AZERTY.
2. **Taille du générique des semis** (`viewer-massif/scripts/seedlings.gd:37`) : vérifier la
   taille du générique comme le font les arbres (`massif_view.gd`, `GENERIC_SIZE_M`), refus nommé
   si elle n'est pas celle attendue ; test GUT.
3. **« sans source » à l'écran** : la note des semis génériques dit aussi « sans source », comme
   `config.yml` ; test.
4. **`build.rs` de simulate** (relecture de la PR 19) : la marque `-dirty` imprécise hors de
   `simulate/` — la dire dans la documentation en tête de `build.rs` si la corriger demande plus
   qu'une ligne ; ajouter un test automatique de la recompilation quand une étiquette change, si
   c'est faisable sans écrire dans le dépôt (dépôt git temporaire) ; sinon le dire.

## Harnais

- **Peut :** `viewer-massif/` (README, scripts `seedlings.gd`, `massif_view.gd`, `camera_fly.gd`,
  tests), `simulate/build.rs`, `simulate/tests/release.rs`, `simulate/src/release.rs` (doc
  seulement).
- **Ne doit pas :** changer une sortie de `simulate` (octets identiques, `run.json` compris) ;
  toucher `config.yml`, `.github/`, `viewer-web/`, `bench/` ; commiter ; pousser ; toucher à
  `pilotage/journal.md`, `.claude/`, `main`.

## Tests

- GUT de `viewer-massif` vert, 0 sauté ; `cargo test --locked` dans `simulate` vert ;
  `bash tools/ci/run_tests.sh m6` vert.

## Dépend de / rouge attendu jusqu'à

- Rien. Aucun rouge attendu.

## Échantillon terrain

- Pascal, sur son clavier AZERTY, monte et descend dans la vue Godot avec les touches que le
  README lui indique.
