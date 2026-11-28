# Mission 090 — un numéro de version que Cargo et semver acceptent toute l'année, et les mineurs de 088 et 089

## Mission

**En une phrase :** Que les manifestes portent un numéro accepté par Cargo, npm (semver strict),
PEP 440 et R de janvier à décembre, en gardant l'étiquette `vAAAA.MM.N`. Le mois sur deux
chiffres (`2027.01.1`) est refusé par Cargo (« invalid leading zero ») : relecture de la PR 22,
le 28/11/2026.

**Décision (orchestrateur, par délégation de Pascal du 28/11/2026, journal) :** l'étiquette
git ne change pas (`v2026.11.19`, `v2027.01.1`) ; les manifestes portent le même numéro **sans
zéro en tête du mois** (`2026.11.19`, `2027.1.1`). Les deux formes se déduisent l'une de
l'autre sans ambiguïté. `run.json` garde la sortie de `git describe` (étiquette).

## L'Homme

- **Agent :** `dev` — **Temps de la main :** donner.

## Ce qui est attendu

1. **Conversion étiquette → numéro des manifestes** en un seul endroit des scripts
   (`.github/scripts/`), utilisée par `aligner-version.sh`, `verifier-version.sh` et
   `controler-version-pr.sh` ; refus nommé d'une étiquette mal formée. Test des mois 01 à 12,
   dont janvier et octobre.
2. **Preuve que les quatre outils acceptent le numéro** pour un mois à un chiffre et un mois à
   deux chiffres : Cargo (`cargo metadata` ou `cargo check` sur un crate jetable, ou sur
   `simulate` dans une copie), npm (`semver` du dépôt s'il est déjà présent dans `node_modules`,
   sinon la règle semver écrite), PEP 440 (`packaging` du venv de tests s'il y est), R
   (`package_version` ou la règle de `DESCRIPTION`). Ce qui n'est pas vérifiable sans réseau est
   dit.
3. **Textes** : `README.md` (section version, ligne qui dit la forme admise par semver) corrigé ;
   la phrase des lignes ~162-164 sur la « relance » dit qu'il faut relancer la CI ou mettre la
   branche à jour à la main (rien ne la déclenche) ; commentaire de l'étape « Garde » de
   `release.yml` (8 manifestes, pas 4 ; seul ce commentaire change dans `release.yml`).
4. **Mineurs de 089** : message trompeur de `controler-version-pr.sh` (~l. 39) si
   `verifier-version.sh` sort en code 2 : message propre à ce cas.
5. **Mineurs de 088** : en-tête de `viewer-web/scripts/releve_gpu.cjs` (~l. 8 : la zone est
   refaite à chaque relevé) ; SIGTERM sort en 143, SIGINT en 130, test à l'appui.
6. **Protection de branche** (relecture de la PR 22, point 2) : ne rien régler sur GitHub. Écrire
   dans le rendu la proposition exacte (réglage « Require branches to be up to date before
   merging » ou file de fusion, ce qu'elle change pour le flux du projet), pour Pascal.

## Harnais

- **Peut :** `.github/scripts/` (scripts et tests), le commentaire de l'étape « Garde » de
  `.github/workflows/release.yml`, `README.md`, `viewer-web/scripts/releve_gpu.cjs`,
  `viewer-web/test/gpu.test.ts`.
- **Ne doit pas :** changer les étiquettes, la logique de `release.yml`, `run.json`,
  `simulate/` (sauf si la preuve n° 2 montre que `build.rs` doit changer : alors remonter) ;
  commiter ; pousser ; toucher à `pilotage/journal.md`, `.claude/`, `main`, aux réglages GitHub.
- **Câblé :** essais git dans des dépôts temporaires ; aucun numéro des manifestes réels changé
  (l'alignement réel est fait par l'orchestrateur).

## Tests

- `bash .github/scripts/test-version-calendaire.sh` (lance les autres) et
  `test-controler-version-pr.sh` verts, cas janvier et octobre compris ;
  `bash tools/ci/run_tests.sh web` vert (1 sauté déjà connu).

## Dépend de / rouge attendu jusqu'à

- PR n° 22 fusionnée. Aucun rouge attendu.

## Échantillon terrain

- Un crate jetable à `2027.1.1` passe `cargo check`, à `2027.01.1` est refusé ; le script
  convertit `v2027.01.1` en `2027.1.1`.
