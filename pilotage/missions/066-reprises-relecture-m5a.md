# Mission 066 — reprises de la relecture de la PR n° 11 (M5a)

## Mission

**En une phrase :** Reprendre les points « à reprendre » de la relecture de la PR n° 11 (journal du 26/11/2026) : la constante 0,184 devient le terme `stress_mortality` de `params/regeneration` (décision de Pascal du 26/11/2026), la note d'index dit l'état réel des semis selon le mode, l'ADR 0006 rattrape les décisions du 26/11 et les mineurs CI sont corrigés.

## L'Homme

- **Agent :** `dev` — **Modèle :** opus — **Temps de la main :** donner.

## Harnais

- **Peut :** `contracts/` (contrat `params/regeneration`, passage en version mineure), `simulate/src/`, `tests/m5/`, `python/sylvigenese/assets.py` et ses tests, `docs/adr/0006-*.md`, `bench/results/M5.md`, `.github/workflows/ci.yml`, `tools/ci/`.
- **Ne doit pas :** inventer une valeur ; laisser une valeur écologique en dur dans le code ; changer un résultat en mode `ifn_direct` ; trancher une question de sens (la poser dans le compte rendu).
- **Câblé :** aucune commande git qui écrit ; vérification sur une copie `git archive HEAD` après commit par l'orchestrateur, ou sur l'arbre de travail avec la commande de `.claude/test-command`.

## Contenu

1. `stress_mortality` (par essence ou global, au choix le plus simple cohérent avec le contrat), source TreeMig éq. 40 p. 16, `provisoire: true` ; le générateur de `tests/m5` l'écrit à 0,184 ; `semis.rs` le lit, absent → code 2 ; résultats `cohorts` identiques à ceux d'avant (test).
2. `assets.py` : la note d'index ne dit « semis non simulés » qu'en `ifn_direct` ; en `cohorts`, elle dit les semis simulés (techniques, non validés) ; tests de `seedling_note` et `notes_v2_for`.
3. Rapport de simulation : mentions Q2 (stock initial en régime) et Q3 (lumière et ombre seules) en mode `cohorts`.
4. ADR 0006 : Lososová d50/d99, maturité en hauteur, survie TreeMig, refus de `ifn_direct` au niveau SER, candidates prises dans `cohorts_init`, validateur sobre, `malloc_trim` ; corriger la phrase sur le taux de boisement de C20 (38 % dans surfaces-ser.csv). Statut laissé « proposée » (l'orchestrateur l'accepte par délégation).
5. Mineurs : délai du job m5 ramené à 20 min si la mesure le permet (sinon le dire), `apt-get update` avant `apt-get install time`, M5.md §4.4 « la plus boisée en surface ».

## Tests

- Commande de `.claude/test-command` verte, aucun test sauté.
