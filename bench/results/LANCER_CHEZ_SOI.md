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
