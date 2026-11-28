# Mission 087 — le numéro de la release dans les manifestes et dans run.json

## Mission

**En une phrase :** Que chaque sortie de simulate et chaque paquet dise de quelle release
calendaire il vient (`vAAAA.MM.N`, étiquette git posée par `.github/workflows/release.yml`),
au lieu du `0.0.1` provisoire de M0 (décision de Pascal du 27/11/2026, journal).

## L'Homme

- **Agent :** `dev` — **Temps de la main :** donner.

## Ce qui est attendu

1. **run.json** : simulate inscrit la release dont il vient, lue à la compilation par un
   `build.rs` (`git describe --tags --match 'v*' --dirty`, exact entre deux releases, par
   exemple `v2026.11.17-3-gabc1234`). Si git ou les étiquettes manquent (copie `git archive`,
   archive de release), la valeur est dite (`inconnue` ou une variable d'environnement
   `SYLVIGENESE_RELEASE` posée par la CI ou par l'utilisateur) et signalée, jamais remplacée en
   silence par le numéro du manifeste. Champ ajouté au schéma `contracts/json/run.schema.json`,
   avec son test. `simulate --version` affiche la même chose.
2. **Manifestes** : `simulate/Cargo.toml`, `python/pyproject.toml` et `DESCRIPTION` portent
   `AAAA.MM.N` (sans le `v` ; semver, PEP 440 et R l'acceptent). Un script
   `.github/scripts/aligner-version.sh` les met au numéro de la prochaine release, celui que
   donne `.github/scripts/version-calendaire.sh` ; `Cargo.lock` suit. Les manifestes des bancs
   (`bench/`) ne sont pas concernés.
3. **Garde de release** : dans `release.yml`, avant de poser le tag, une étape refuse (échec
   nommé, aucun tag posé) si les trois manifestes ne portent pas le numéro calculé. Le cas
   « pas de release nécessaire » reste inchangé. Le script est testé comme
   `test-version-calendaire.sh` (dépôt temporaire, étiquettes synthétiques).
4. **README** §102 et suivants : dire les deux sources (étiquette et manifestes), le geste à
   faire dans la PR (lancer le script) et ce que dit run.json.

## Harnais

- **Peut :** `simulate/build.rs`, `simulate/src/` (inscription de la release seulement),
  `simulate/Cargo.toml`, `Cargo.lock`, `python/pyproject.toml`, `DESCRIPTION`,
  `contracts/json/run.schema.json` et le validateur, leurs tests, `.github/scripts/`,
  `.github/workflows/release.yml`, `README.md`.
- **Ne doit pas :** changer un résultat de simulation (octets des sorties inchangés hors
  `run.json`) ; pousser ; poser une étiquette ; toucher à `main`.
- **Câblé :** aucune commande git qui écrit (pas de commit, pas de tag réel dans le dépôt) ;
  vérification sur une copie `git archive HEAD`.

## Tests

- Test du `build.rs` (valeur avec et sans git, variable d'environnement) ; `run.json` valide au
  schéma avec le champ ; test du script d'alignement et de la garde (manifestes alignés :
  passe ; un manifeste en retard : refus nommé) ; `bash tools/ci/run_tests.sh` vert, 0 sauté.
