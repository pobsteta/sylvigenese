# Mission 085 — troncs, bandeau et nord de la vue massif

## Mission

**En une phrase :** Corriger trois défauts vus sur les captures du 27/11/2026 (demande de Pascal) : les troncs prennent la couleur du feuillage, la ligne « non calés » du bandeau est coupée à droite, et rien n'indique le nord.

## L'Homme

- **Agent :** `afficheur` — **Temps de la main :** donner.

## Harnais

- **Peut :** `viewer-massif/scripts/`, `viewer-massif/tests/` (ajouts), `python/sylvigenese/assets_lib/` (si le `.glb` doit séparer bois et feuillage) et ses tests, bloc `viewer` de `config.yml` et `contracts/json/config.schema.json` (relire le fichier juste avant de l'écrire : une autre mission peut y toucher).
- **Ne doit pas :** mettre une valeur écologique ; changer un décompte ; casser l'identité à l'octet des `.glb` sans le dire et sans relever la référence.
- **Câblé :** aucune commande git qui écrit ; vérification sur une copie `git archive HEAD` (Godot 4.6.3 headless, GUT, selftest) et nouvelles captures.

## Tests

- GUT : bois et feuillage de couleurs distinctes ; bandeau sans ligne plus large que l'écran ; flèche du nord orientée selon le repère (x = est, z = −nord) ; nouvelles captures avant/après.
