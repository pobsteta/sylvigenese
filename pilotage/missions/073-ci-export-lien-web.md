# Mission 073 — ci export lien web (M6a, mission G du plan)

## Mission

**En une phrase :** CI, export et lien web : job `m6` (Godot 4.6.3 et GUT figés, empreintes vérifiées, import, GUT, export Linux seul (Q5), exécution de `--selftest` sur le binaire exporté ; extraction du seul gabarit `linux_release` du `.tpz`) ; section `m6` de `run_tests.sh` ; la commande de la fiche dit la zone (T7) ; versions dans le README.

Référence : [`docs/plans/m6a.md`](../../docs/plans/m6a.md) §3 (ligne G), avec les réponses de Pascal Q1 à Q8 du 26/11/2026 (journal) et la critique du contradicteur intégrée au plan.

## L'Homme

- **Agent :** `dev` — **Temps de la main :** donner.

## Harnais

- **Peut :** `.github/workflows/ci.yml` (job `m6`), `tools/ci/run_tests.sh`, `tools/viewer-massif*` (lanceur), `viewer-web/src/sheet.ts` et ses tests, `README.md`
- **Ne doit pas :** élargir le réseau de l'exécuteur au-delà de github.com ; relever un délai sans le dire au journal ; changer `tests/m4` hors de la ligne de commande ; inventer une valeur écologique ; trancher une question de sens (la poser dans le compte rendu).
- **Câblé :** aucune commande git qui écrit dans sylvigenese ; disque juste (quelques Go), nettoyer ce qui est créé.

## Tests

- job `m6` **mesuré à froid** (cache purgé après 7 jours) et à chaud, délai relevé au journal ; la commande de la fiche est celle que le viewer accepte (test croisé), forme selon Q7
