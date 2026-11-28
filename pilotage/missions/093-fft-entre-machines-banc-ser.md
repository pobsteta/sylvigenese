# Mission 093 — identité de la FFT entre machines, et banc du niveau SER à N = 2 000

## Mission

**En une phrase :** Établir si les sorties de `simulate` en mode `cohorts` (dispersion par FFT,
`rustfft` 6.4.1) sont identiques à l'octet quelle que soit l'instruction vectorielle choisie par
`rustfft` (AVX, SSE ou scalaire), et compléter le banc du niveau SER (forêt seule ; S × K à
N = 2 000), pour fermer deux cartes du bac à sable sans données réelles (délégation de Pascal du
28/11/2026).

## L'Homme

- **Agent :** `dev` — **Temps de la main :** donner.

## Ce qui est attendu

1. **FFT entre machines.** `rustfft` choisit AVX, SSE ou un code scalaire à l'exécution selon le
   processeur. Construire `simulate` avec et sans ces chemins (options de compilation de
   `rustfft` : `default-features`, ou ce que sa documentation permet), dans une copie, sans
   changer le `Cargo.toml` du dépôt ; faire tourner le massif fictif en `cohorts` ; comparer les
   SHA-256 des sorties. Dire : identiques, ou l'écart (taille, fichiers, ordre de grandeur), et ce
   que ça implique pour la promesse « identité au bit près ». Si l'identité tient, le dire avec la
   preuve ; si elle ne tient pas, proposer (sans le faire) la parade et ses coûts.
2. **Banc SER** (`bench/results/M5.md`, `bench/m5/`, `bench/m5b/`) : mesurer « la forêt seule »
   (option de part forestière, si elle existe déjà dans le générateur de SER fictive ; sinon le
   dire) et S × K à N = 2 000 comme c'est fait à N = 1 000 (§3.4). Écrire les résultats dans
   `bench/results/M5.md` (section nouvelle, datée, machine dite : PC de Pascal) ; CSV à côté des
   autres.

## Harnais

- **Peut :** `bench/` (scripts et résultats), une copie du dépôt dans le dossier temporaire de
  la session pour les constructions de `simulate` aux options différentes, `data/` (hors dépôt).
- **Ne doit pas :** changer `simulate/` ni `Cargo.toml`/`Cargo.lock` du dépôt ; changer un
  résultat de la chaîne ; commiter ; pousser ; toucher à `pilotage/journal.md`, `.claude/`,
  `main`, `viewer-massif/`.
- **Câblé :** cette machine a 8 fils et 31 Go ; un autre dev travaille en même temps sur
  `viewer-massif/` et `simulate/build.rs` (mission 092) : ne pas lancer de banc pendant ses
  `cargo test` si c'est évitable, et dire la charge de la machine à côté des temps.

## Tests

- Les scripts de banc ajoutés ou changés ont leur test (au style des tests existants de
  `bench/`) ; les SHA-256 comparés sont écrits dans le rendu.

## Dépend de / rouge attendu jusqu'à

- Rien. Aucun rouge attendu.

## Échantillon terrain

- La ligne de `bench/results/M5.md` qui dit si l'identité au bit près tient entre AVX et le code
  scalaire.
