# Lancer le banc chez soi (machine de référence de Pascal)

Le banc mesure cinq variantes (`r-base`, `r-rcpp`, `py-numpy`, `py-numba`, `rust`) selon `bench/SPEC.md` §9.
Les mesures déjà faites (`RESULTATS.md`) viennent d'un conteneur à 4 cœurs et 16 Go : elles sont préliminaires.
Ce guide permet de les refaire sur le PC Linux de Pascal (i7-4940MX, 4 cœurs physiques, 8 logiques, 31 Go).

## Prérequis (Ubuntu ou Debian ; équivalents ailleurs)

    sudo apt-get install -y r-base-core r-cran-rcpp r-cran-rcppparallel r-cran-testthat r-cran-jsonlite g++ \
         python3 python3-pip python3-venv time util-linux cargo
    python3 -m venv ~/venv-banc && . ~/venv-banc/bin/activate
    pip install -r bench/python/requirements.txt        # versions exactes (numpy, scipy, numba, pytest)
    (cd bench/rust && cargo build --release)           # binaire bench/rust/target/release/bench-sim

Si `cargo` d'apt est trop ancien (édition 2024 demandée, rustc 1.97 au banc), installer Rust par `rustup`.
`/usr/bin/time` doit être le GNU time (option `-v`). Place libre : prévoir 15 Go dans le dossier temporaire.

## Commande unique

    cd <dépôt sylvigenese>
    bench/results/run_bench.sh            # équivaut à : ALL

Le script vérifie d'abord les outils (il dit en français ce qui manque et s'arrête), écrit `bench/results/machine.json`
(cœurs `nproc`, cœurs physiques, mémoire, modèle du processeur, versions), puis enchaîne : N = 500 et 1000 (100 ans), N = 2000,
4000, 8000 (10 ans, extrapolés), la robustesse, l'écart entre variantes. T prend les valeurs 1, cœurs physiques et `nproc`
(ici 1, 4, 8). Un essai à la fois ; plafond de 45 min par essai ; une variante qui échoue (hors mémoire, hors temps) saute
ses tailles supérieures. Le CSV est mis à jour après chaque essai : on peut interrompre.

Variables facultatives : `BENCH_TMP` (sorties lourdes, défaut `/tmp/sylvigenese-banc`), `BENCH_LIMIT_S` (plafond par essai, 2700),
`BENCH_RSS_PCT` (seuil du garde mémoire, 85 % de la mémoire totale). Sous-commandes : `CHECK`, `A`, `B`, `ROB`, `CMP`.
Ne rien lancer d'autre pendant les mesures (elles se gêneraient).

## Durée estimée (extrapolation, à ne pas prendre pour une mesure)

Dans le conteneur, la somme des temps réels des essais a été de **1 h 27 min** (T = 1 et 4, plusieurs tailles tombant hors
mémoire). Sur le PC de Pascal, j'estime **de 3 h 30 à 4 h 30**, parce que : (a) un troisième T (8) s'ajoute (≈ +45 min) ;
(b) avec 31 Go, rust et py-numpy iront probablement jusqu'à N = 8000 (≈ +1 h 15 min en tout, py-numpy étant le plus lent : ≈ 20 min
par essai) ; (c) `r-base` ira à N = 4000 (≈ 8 min par essai) et `r-rcpp` tentera N = 8000 jusqu'à l'arrêt par le garde mémoire (quelques minutes).
Le processeur du banc (Xeon 2,1 GHz) est différent du sien (3,1 GHz) : le temps réel peut s'écarter de ±40 % de cette fourchette.

## Ce qu'il faut renvoyer

Le dossier `bench/results/` : `machine.json`, `mesures.csv`, `identite.csv`, `ecarts.csv`, `robustesse.csv`, plus la sortie
du terminal si le script s'est arrêté sur un message. Si un essai paraît anormal (code de sortie inattendu, mémoire), joindre le
fichier `stderr.txt` du dossier temporaire de l'essai (`$BENCH_TMP/out_<variante>_<N>_<T>/`).

## M5 : mesure du niveau SER (mission 064)

Cette section refait sur votre PC les mesures de `M5.md`, faites dans le conteneur. Elle couvre les SER
fictives N = 1 000, 2 000 et 4 000 à 2 essences et 6 classes, et N = 1 000 à 8 essences et 15 classes, sur
10 ans, à 1, 4 et 8 fils. Il faut `cargo` (comme ci-dessus), `python3` avec `numpy`, `pyarrow`, `rasterio` et
`pyyaml`, et le GNU time (`/usr/bin/time`). Aucun réseau n'est nécessaire une fois simulate compilé.

### Commandes

Lancez les commandes une à une, depuis la racine du dépôt, et effacez chaque zone sitôt mesurée (le disque
est la ressource qui manque en premier, voir plus bas) :

    cd <dépôt sylvigenese>
    S=bench/results/m5_mesures_pc.csv
    for n in 1000 2000 4000; do for t in 1 4 8; do
      bash bench/m5/mesurer.sh --n "$n" --fils "$t" --annees 10 --sortie "$S"
      rm -rf "data/ser_fictive_$n/sim"
    done; rm -rf "data/ser_fictive_$n"; done
    for t in 1 4 8; do
      bash bench/m5/mesurer.sh --n 1000 --fils "$t" --annees 10 --essences 8 --classes 15 --sortie "$S"
      rm -rf data/ser_fictive_1000_s8_k15/sim
    done; rm -rf data/ser_fictive_1000_s8_k15

Le script compile simulate et génère chaque SER fictive sous `data/ser_fictive_<N>/`, ou sous
`data/ser_fictive_<N>_s<S>_k<K>/` hors du défaut (hors dépôt). Il ajoute ensuite au CSV une ligne par exécution.
Chaque ligne donne le temps de calcul et le temps d'écriture, la mémoire estimée, la mémoire résidente, leur écart,
puis le nombre d'essences et de classes. Pour garder aussi le temps de chaque année, copiez
`data/<zone>/mesure_stderr.txt` avant l'exécution suivante.

### À savoir avant de lancer

- **Nouveau format du CSV.** Il a deux colonnes de plus en fin de ligne, `essences` et `classes`. Le script
  refuse d'écrire dans un CSV qui a l'ancien en-tête. Si un `m5_mesures_pc.csv` d'une version antérieure existe,
  renommez-le ou choisissez une autre `--sortie`.
- **Options.** `--essences S` (de 1 à 16) et `--classes K` (au moins 1) changent la composition de la SER
  fictive. Par défaut, S = 2 et K = 6. Le script écrit toujours `write_step` = Y, si bien que seules t0 et la
  dernière année sont écrites.
- **Place libre.** Il faut environ 6 Go pour N = 4 000 : 0,7 Go d'entrées et 5,2 Go de `sim/` (mesuré dans le
  conteneur). simulate garde l'ancien `sim/` pendant qu'il écrit le nouveau. Sans le `rm -rf .../sim` des
  commandes ci-dessus, il en faudrait environ 11 Go. Pour N = 1 000 à 8 essences et 15 classes, il faut environ
  2 Go. Le validateur demande en plus environ 8 octets de disque temporaire par ligne pour les grandes tables.
- **Mémoire** (mesurée dans le conteneur, elle dépend peu de la machine) : 0,97 Go pour N = 2 000 ; **3,83 Go
  pour N = 4 000** ; 0,97 Go pour N = 1 000 à 8 essences et 15 classes.
- **Durée dans le conteneur**, écoulé avec le validateur, génération à part (moins d'une minute) :
  - N = 4 000 : 520 s à 1 fil et 292 s à 4 fils ;
  - N = 1 000 à 8 essences et 15 classes : 282 s et 153 s.

  Ce ne sont **pas** des mesures de votre PC.
- Ne lancez rien d'autre pendant la mesure.

### Ce qu'il faut renvoyer

Renvoyez `bench/results/m5_mesures_pc.csv` et les `mesure_stderr.txt` copiés. Si le script s'arrête, joignez la
sortie du terminal et le fichier `data/<zone>/mesure_stderr.txt`.

## M6 : refaire les mesures de la vue massif et la lancer sur votre PC (mission 074)

Cette section a deux usages, à ne pas confondre. **A** : refaire sur votre PC les mesures sans carte graphique de
`M6.md` (6 minutes dans le conteneur ; sur le PC, **estimation** de 4 à 8 minutes, non mesurée). **B** : lancer la
vue Godot **pour de vrai**, avec l'écran, c'est le début de M6b. Seul B donne des images par seconde ; A n'en donne
aucune (Godot y tourne sans rendu).

Machine visée : PC Linux, i7-4940MX, 31 Go, **Vulkan incertain** (la vue a un repli, voir B.3).

### Prérequis (en plus de ceux du banc)

- `R` (`Rscript`), `cargo`, `make`, `python3` avec `numpy`, `pyarrow`, `pyyaml` et `rasterio` : ce sont ceux de la
  chaîne du dépôt (`make prepare … assets`).
- **Godot 4.6.3**, version Linux 64 bits, **pas la version « mono »** :

      mkdir -p ~/godot && cd ~/godot
      curl -LO https://github.com/godotengine/godot-builds/releases/download/4.6.3-stable/Godot_v4.6.3-stable_linux.x86_64.zip
      echo "a035258da32b77f966a5376f9fa29c30a6adde826a85ba918e1605bd1fc9823eba7d85f1dd5e748956bd2ba72827c0025ffa11bb82aec91128c407a2e723c99c  Godot_v4.6.3-stable_linux.x86_64.zip" | sha512sum -c -
      unzip Godot_v4.6.3-stable_linux.x86_64.zip && chmod +x Godot_v4.6.3-stable_linux.x86_64

  `sha512sum -c` doit répondre `OK` ; sinon n'ouvrez pas le binaire et renvoyez-moi la ligne. Godot ne demande aucune
  installation : le binaire se lance de là.
- **Pour le jeu de contrôle réel seulement** : le dépôt `tarif-nemeton` sur la branche `claude/export-exemplaires` (PR
  n° 7, **à fusionner par vous** ; tant qu'elle ne l'est pas, se placer sur cette branche) : les vrais arbres sont
  produits chez vous ou ici, jamais dans le dépôt public (Q1). Sans lui, le script s'arrête en le disant.
- Place libre : **moins de 0,5 Go** (zones d'essai de 60 à 81 Mo chacune dans le conteneur, plus 140 Mo pour Godot).

### A. Refaire les mesures sans carte graphique

    cd <dépôt sylvigenese>
    python3 bench/m6/mesurer.py --godot ~/godot/Godot_v4.6.3-stable_linux.x86_64 \
        --tarif-nemeton <dépôt tarif-nemeton> --sortie bench/results/m6_pc --garder

- `--sortie bench/results/m6_pc` écrit les 13 CSV `m6_*.csv` à part et **n'écrase pas** ceux du conteneur.
- `--garder` laisse sous `data/` les zones `m6_essai`, `m6_cohorts` et `m6_reel_zone`, dont B a besoin.
- Un seul script ; le code de sortie est 0 si tout est mesuré, 2 s'il manque un prérequis (la cause est dite), 3 si un
  contrôle échoue (voir `m6_reel_controle.csv`). Ne lancez rien d'autre pendant la mesure.
- **Renvoyez** le dossier `bench/results/m6_pc/` et la sortie du terminal si le script s'est arrêté sur un message.

### B. Lancer la vue, avec l'écran

**B.1 La commande.** C'est celle que donne la fiche web d'une cellule (décision Q7) ; ici pour le point d'essai. Depuis
la racine du dépôt :

    GODOT=~/godot/Godot_v4.6.3-stable_linux.x86_64 tools/viewer-massif -- --zone data/m6_cohorts --x 700250 --y 6500250 --year 2037

- `data/m6_cohorts` : jeu fictif avec **semis** (réglages synthétiques) et exemplaires de la fixture.
  `data/m6_reel_zone` : jeu fictif dessiné avec les **vrais exemplaires** (sans semis, `ifn_direct`).
  `data/m6_essai` : jeu fictif, fixture, sans semis. Années disponibles : 2022, 2032 et 2037.
- Commandes : clic pour capturer la souris, Échap pour la rendre, W A S D (Z Q S D) pour avancer, Q et E pour monter et
  descendre, Maj pour aller vite.
- Si la vue refuse de partir, elle dit pourquoi en français et sort avec un code : 2 arguments, 3 `config.yml`
  introuvable, 4 zone, année ou point, 5 modèles ou blocs.

**B.2 Le test des dix secondes (afficheur).** Lancez la commande, **regardez l'écran dix secondes sans toucher à rien**,
puis répondez de mémoire :

1. **Où suis-je ?** La zone, l'année et le bloc sont écrits en bas à gauche (« Zone m6_cohorts, année 2037, bloc
   t_700000_6500000 »).
2. **Est-ce prouvé ?** La première ligne en jaune, en haut, dit « PROVISOIRE : trajectoire non validée écologiquement » ;
   en bas, la mention dit que l'apparence de l'herbe, du feuillage et des niveaux de détail est une illustration.
3. **Qu'est-ce qui manque ou qui est approximatif ?** Les lignes du bandeau : « Semis non simulés » (en `ifn_direct`
   seulement), « N arbres dessinés par un modèle générique », « N arbre(s) non calé(s) », le sol à 25 m.
4. **Où est le nord ?** Devant vous au départ (le point d'essai est au coin de quatre cellules).

Le test est **réussi** si vous donnez de mémoire les points 1, 2 et 3 en dix secondes. Sinon, notez ce que vous avez
regardé en premier et ce que vous n'avez pas vu : c'est l'écran qui est à reprendre, pas vous. Les repères de lecture
(échantillon terrain : 4 arbres aux quatre bords du bloc, une cellule sans herbe, une cellule à semis) sont au plan,
`docs/plans/m6a.md` §9.

**B.3 Si Vulkan manque ou si la fenêtre ne s'ouvre pas.** Le projet demande le rendu `forward_plus` (Vulkan) et
retombe sur OpenGL 3 si le pilote n'a pas Vulkan. Pour **forcer** le repli Compatibility, appelez Godot directement ; le
lanceur met tout ce qui suit `--` du côté de la vue, donc `--rendering-method` va **avant** `--` :

    ~/godot/Godot_v4.6.3-stable_linux.x86_64 --path viewer-massif --rendering-method gl_compatibility \
        -- --zone "$PWD/data/m6_cohorts" --x 700250 --y 6500250 --year 2037

Depuis la racine du dépôt (la zone en chemin absolu). Pour savoir quelle carte et quel pilote Godot a pris, ajoutez
`--verbose` et gardez les lignes qui parlent du renderer et du GPU. **Dans le conteneur, seul le passage des arguments
a été éprouvé** (le `--selftest` sort à 0 avec ce drapeau, sans rendu) ; **le rendu Compatibility lui-même est à
prouver chez vous** : c'est un des critères de M6b.

**B.4 Les images par seconde (M6b).** Godot sait les afficher dans le terminal : ajoutez `--print-fps` (et
`--disable-vsync` pour ne pas être plafonné à l'écran). Relevez, pour chaque zone et à trois endroits (au point d'essai,
en vous éloignant de 200 m, en regardant le sol), la valeur stable au bout de 30 secondes. Ces drapeaux sont ceux de
Godot (`godot --help`) ; ils n'ont pas été lancés avec un écran. **Le BRIEF ne fixe aucun seuil de fluidité pour la
vue massif** : sans lui, on relève, on ne juge pas.

À savoir avant de juger : dans le conteneur, les **semis** (zone `m6_cohorts`) sont dessinés sans niveau de détail ni
plafond, et leur effectif vient de réglages synthétiques (283 428 dans le rayon, `M6.md` §4 et §6). Une lenteur sur
`m6_cohorts` et pas sur `m6_reel_zone` est donc attendue ; **elle ne dit rien d'une forêt réelle**.

### Ce qu'il faut renvoyer (B)

Pour chacune des trois zones : les images par seconde relevées, une capture d'écran au point d'essai, le résultat du test
des dix secondes (réussi ou non, et ce qui a manqué), la ligne du renderer donnée par `--verbose`, et la mention si
vous avez dû passer au repli Compatibility.

## M4b : images par seconde de la vue web sur la carte graphique (mission 088)

Critère b de M4 (BRIEF §11) : 100 000 instances affichées, images par seconde mesurées **par script**, sur votre
machine et votre navigateur. Les tests de m4 et `capture.cjs` forcent le rendu logiciel (SwiftShader, sans écran) pour
tourner pareil en CI : sur votre PC ils donnent 0,2 à 1,8 image par seconde, ce qui mesure le processeur et non la
carte. Ce relevé-ci ouvre Chromium de Playwright **à l'écran**, avec l'accélération matérielle.

### Prérequis

- Les dépendances du dépôt (Node 22.18 ou plus, `npm ci` dans `viewer-web`, Chromium de Playwright, `python3` de la
  chaîne) et une session graphique (variable `DISPLAY`).
- Les sorties de `make prepare biomes trees` sur le jeu fictif (elles y sont après `bash tools/ci/run_tests.sh m4`).
  La zone de charge `data/m4_charge/` (100 013 puis 100 000 arbres, synthétique, hors dépôt) est préparée par le
  script s'il ne la trouve pas (`viewer-web/scripts/preparer_charge.py`, mêmes aides que les tests de m4).

### Commande

    cd <dépôt sylvigenese>
    node viewer-web/scripts/releve_gpu.cjs --carte nvidia          # la Quadro
    node viewer-web/scripts/releve_gpu.cjs --carte integree        # la carte Intel, pour comparer

Une fenêtre Chromium s'ouvre, parcourt les deux années, puis se ferme (environ une minute). Ne la cachez pas pendant
la mesure. Options : `--zone`, `--duree <ms>` (5000 par défaut), `--sortie <fichier.json>`, `--sans-borne` (relever
aussi sans synchronisation verticale, même si la première série n'est pas près de 60 images par seconde ; sinon la
série sans borne n'est faite que si une valeur tombe entre 55 et 62).

Le choix de la carte pose les variables PRIME (`__NV_PRIME_RENDER_OFFLOAD`, `__GLX_VENDOR_LIBRARY_NAME`) et le fichier
EGL du fabricant (`__EGL_VENDOR_LIBRARY_FILENAMES`, dossier `/usr/share/glvnd/egl_vendor.d/`). Chromium est lancé avec
`--use-angle=gl-egl` : sans cette option, avec la Quadro, il retombe **en silence** sur SwiftShader.

### Ce que le script refuse (code 2, aucun chiffre écrit)

Il lit le moteur de rendu réel (`WEBGL_debug_renderer_info`) avant et après la mesure. Il s'arrête en le nommant si le
moteur est logiciel (SwiftShader, llvmpipe, « software »…), illisible, différent de la carte demandée, ou s'il a changé
pendant la mesure ; de même sans écran, ou si le fichier EGL de la carte demandée est introuvable.

### Ce qu'il faut renvoyer

Le fichier `data/releves_m4/gpu_<carte>_<date>.json` (moteur de rendu, carte demandée, résolution, instances et images
par seconde pour chaque année, avec et sans synchronisation verticale). Vous devez y retrouver `Quadro K5100M`. Le
BRIEF ne fixe aucun seuil d'images par seconde : on relève, on ne juge pas.
