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
