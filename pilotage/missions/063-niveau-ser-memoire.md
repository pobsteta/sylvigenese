# Mission 063 — Niveau SER

## Mission

**En une phrase :** Niveau SER : des cohortes d'adultes par classe de diamètre, avec accroissement, mortalité et recrutement IFN appliqués par classe (T1, T4). S'y ajoutent les sorties du niveau, l'estimation de mémoire propre au niveau (T7), la mémoire résidente écrite dans `run.json`, le script de mesure et le job `m5` de la CI (T6), pour que `simulate --level ser` existe et se mesure. (plan `docs/plans/m5a.md`, mission E ; décisions de Pascal Q1 à Q5 du 26/11/2026).

## L'Homme

- **Agent :** `dev` (Rust) — **Modèle :** opus — **Temps de la main :** donner.

## Harnais

- **Peut :** `simulate/src` (nouveau `ser.rs` ; `memoire.rs`, `sorties.rs`, `lib.rs`, `entrees.rs`), `simulate/tests/`, `bench/m5/` (script), `tools/ci/run_tests.sh`, `.github/workflows/ci.yml` (job `m5`)
- **Ne doit pas :** écrire `sim/trees` au niveau SER ; interpoler ; borner une estimation de mémoire par une constante non mesurée ; mettre la mesure à N = 4 000 dans la CI
- **Câblé :** aucune commande git qui écrit ; tests vérifiés sur une copie `git archive HEAD`.

## Tests

- tests unitaires (conservation des tiges dans les transferts entre classes ; bal exact sur un cas à trois classes) ; estimation de mémoire à moins de 10 % de la mémoire résidente, à N = 1 000, dans la CI ; tests de C verts
