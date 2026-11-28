# Mission 088 — mesurer les images par seconde de la vue web sur la carte graphique, par script

## Mission

**En une phrase :** Rendre rejouable, par un script, la mesure des images par seconde de la vue web
sur la vraie carte graphique de la machine (la Quadro K5100M du PC de Pascal), pour remplir le
critère b de M4 (BRIEF §11 : « 100 000 instances affichées, images par seconde mesurées par
script, sur la machine et le navigateur de Pascal ») ; décision de Pascal du 28/11/2026
(« rends-le rejouable »).

**Pourquoi :** `viewer-web/scripts/capture.cjs` et les tests de m4 forcent le rendu logiciel
(`--use-angle=swiftshader`, sans écran) pour tourner pareil en CI. Sur le PC de Pascal, ils
relèvent 0,2 à 1,8 image par seconde (`data/releves_m4/*.json`, journal du 28/11) : ce n'est pas
la carte, c'est le processeur.

## L'Homme

- **Agent :** `dev` — **Temps de la main :** donner.

## Ce qui est attendu

1. **Un mode « carte graphique »** du relevé, à côté du mode actuel qui ne change pas (la CI et
   les tests de m4 gardent SwiftShader) : Chromium de Playwright ouvert à l'écran, sans les
   options SwiftShader, accélération matérielle demandée. Forme au choix du dev (option de
   `capture.cjs` ou script voisin dans `viewer-web/scripts/`), dite dans le rendu.
2. **Choix de la carte sur un portable à deux cartes (PRIME)** : le mode doit pouvoir demander la
   carte NVIDIA (variables `__NV_PRIME_RENDER_OFFLOAD=1`, `__GLX_VENDOR_LIBRARY_NAME=nvidia`, et
   ce qu'il faut pour EGL si Chromium passe par EGL) ou la carte intégrée, pour comparer.
3. **Signaler plutôt que deviner** : le relevé lit et écrit le nom du moteur de rendu réellement
   utilisé (`WEBGL_debug_renderer_info`, `UNMASKED_RENDERER_WEBGL`) et le fabricant. En mode
   « carte graphique », si le moteur est logiciel (SwiftShader, llvmpipe, « software ») ou
   illisible : **échec nommé**, pas de chiffre écrit. Même chose si la carte demandée n'est pas
   celle obtenue.
4. **La mesure** : sur la zone de charge des tests de m4 (`m4_charge`, 100 013 puis 100 000
   instances ; `tests/m4/helpers_m4_temps.py`), pour chaque année, par
   `window.sylvigenese.mesurerFps` déjà présent. Dire si la mesure est bornée par la
   synchronisation verticale (60 images par seconde) ; si oui, relever aussi sans la borne
   (options de Chromium), les deux chiffres étiquetés.
5. **Sortie** : un JSON hors dépôt sous `data/releves_m4/` (date, machine, navigateur et sa
   version, moteur de rendu, carte demandée, résolution, instances et images par seconde par
   année) ; la commande pour le rejouer écrite dans `bench/results/LANCER_CHEZ_SOI.md` (section
   M4b, en français, comme la section M6b existante).
6. **Mesure faite sur le PC de Pascal** (cette machine, qui a un écran) : Quadro et carte
   intégrée, chiffres dans le rendu.

## Harnais

- **Peut :** `viewer-web/scripts/`, `viewer-web/test/` (tests du nouveau mode), `viewer-web/package.json`
  si un script npm est ajouté (sans nouvelle dépendance), `bench/results/LANCER_CHEZ_SOI.md`,
  `Makefile` (une cible, si utile), `data/` (hors dépôt).
- **Ne doit pas :** changer le mode par défaut de `capture.cjs` ni les tests de m4 ; changer la
  page (`viewer-web/src/`) ; ajouter une dépendance ; pousser ; toucher à `main`, à `.claude/`,
  à `pilotage/journal.md` ; installer un paquet système (sudo) : s'il en manque un, le dire.
- **Câblé :** l'environnement de la CI est reconstitué dans le dossier temporaire de la session
  de l'orchestrateur (Python 3.13.14 : `…/scratchpad/venv313` ; cargo 1.97 : `~/.cargo/bin`) ;
  `viewer-web/node_modules` et Chromium de Playwright sont installés.

## Tests

- Tests unitaires (node, `viewer-web/test/`) du garde-fou : un moteur logiciel ou illisible en
  mode « carte graphique » fait échouer, un moteur matériel passe ; choix de la carte → variables
  d'environnement posées. Ils tournent en CI sans carte graphique.
- `bash tools/ci/run_tests.sh web m4` vert, 0 sauté (le mode par défaut ne bouge pas).

## Dépend de / rouge attendu jusqu'à

- Rien. Aucun rouge attendu.

## Échantillon terrain

- Pascal relance la commande de `LANCER_CHEZ_SOI.md` (section M4b) et retrouve le nom
  « Quadro K5100M » et ses images par seconde dans le JSON.
