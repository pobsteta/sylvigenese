#!/usr/bin/env python3
"""Banc d'essai (bench/SPEC.md) : simulation synthétique, variantes py-numpy / py-numba.

Exemple : python3 bench/python/sim.py --variant py-numpy --n 500 --years 100 \
              --seed 42 --threads 1 --out /tmp/x
Codes de sortie : 0 ok ; 2 entrée refusée ; 3 contrôle §6.8 déclenché ; 4 mémoire insuffisante.
"""
import argparse
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import params as P  # noqa: E402  (n'importe pas numpy)

EXIT_INPUT = 2
EXIT_CONTROL = 3
EXIT_MEMORY = 4
SEED_MAX = 2 ** 53
DIGITS = re.compile(r"[0-9]+", re.ASCII)


class FrArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        fail(EXIT_INPUT, f"Erreur de ligne de commande : {message}. Voir --help.")


def parse(argv):
    a = FrArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("--variant", default="py-numpy", help="py-numpy ou py-numba")
    for opt in ("n", "years", "seed", "threads", "inject-nan"):
        a.add_argument("--" + opt, default=None, metavar="ENTIER")
    a.add_argument("--out", default=None)
    a.add_argument("--hmax-zero", action="store_true")
    args = a.parse_args(argv)
    if args.variant not in ("py-numpy", "py-numba"):
        fail(EXIT_INPUT, f"Erreur : --variant doit valoir py-numpy ou py-numba (reçu « {args.variant} »).")
    for req in ("n", "years", "out"):
        if getattr(args, req) is None:
            fail(EXIT_INPUT, f"Erreur : --{req} est obligatoire.")
    for opt, default in (("seed", "42"), ("threads", "1")):
        if getattr(args, opt) is None:
            setattr(args, opt, default)
    # AM2 : entiers écrits en chiffres décimaux, jamais tronqués ni ignorés
    for opt in ("n", "years", "seed", "threads", "inject_nan"):
        v = getattr(args, opt)
        if v is None:
            continue
        if not DIGITS.fullmatch(v):
            fail(EXIT_INPUT, f"Erreur : --{opt.replace('_', '-')} doit être un entier écrit en chiffres "
                             f"(reçu « {v} »).")
        setattr(args, opt, int(v))
    if args.seed >= SEED_MAX:
        fail(EXIT_INPUT, f"Erreur : --seed doit être dans [0, 2^53) (reçu {args.seed}).")
    if args.n < 1 or args.threads < 1:
        fail(EXIT_INPUT, "Erreur : --n et --threads doivent être >= 1.")
    if args.inject_nan is not None and not (1 <= args.inject_nan <= args.years):
        fail(EXIT_INPUT, f"Erreur : --inject-nan {args.inject_nan} hors de 1 … {args.years}.")
    return args


def fail(code, msg):
    print(msg, file=sys.stderr)
    sys.exit(code)


def main(argv=None):
    args = parse(sys.argv[1:] if argv is None else argv)
    T = args.threads
    # Fils : variables d'environnement fixées AVANT tout import de numpy / numba.
    os.environ["NUMBA_NUM_THREADS"] = str(T)
    for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[v] = str(T)
    try:
        return run(args)
    except MemoryError:
        n = args.n
        est = 5 * P.S * n * n * 4 + 3 * n * n * 8      # B, D, H, Hmax (f32) + tampons f64, approximatif
        fail(EXIT_MEMORY, f"Mémoire insuffisante : allocation impossible pour N = {n} "
                          f"(état estimé à au moins {est / 1e6:.0f} Mo, sans compter la FFT).")


def run(args):
    import numpy as np
    T = args.threads
    if args.variant == "py-numba":
        import v_numba as V
        tc = time.perf_counter()
        V.warmup()
        print(f"[py-numba] compilation/chargement du cache : {time.perf_counter() - tc:.2f} s "
              f"(hors init_s)", file=sys.stderr)
    else:
        import v_numpy as V

    # --- initialisation et lecture des entrées
    t0 = time.perf_counter()
    eng = V.Engine(args.n, args.seed, T)
    eng.init()
    if args.hmax_zero:
        eng.Hmax[0, 0, 0] = 0.0
    with np.errstate(invalid="ignore"):
        bad = ~(eng.Hmax > 0) | ~np.isfinite(eng.Hmax)
    if bad.any():
        s, i, j = np.unravel_index(int(np.argmax(bad)), bad.shape)
        fail(EXIT_INPUT, f"Entrée refusée avant le premier pas : Hmax doit être fini et strictement positif ; "
                         f"valeur {float(eng.Hmax[s, i, j])} à la cellule {i * args.n + j} "
                         f"(ligne {i}, colonne {j}), essence {s}.")
    init_s = time.perf_counter() - t0

    # --- pas annuels
    rows, step_times = [], []
    for year in range(1, args.years + 1):
        ts = time.perf_counter()
        if args.inject_nan == year:
            eng.H[0, 0, 0] = np.nan
        eng.step(year)
        viol = eng.violation(P.DMAX)
        if viol is not None:
            name, s, i, j = viol
            v = float(getattr(eng, name)[s, i, j])
            fail(EXIT_CONTROL, f"Arrêt au contrôle : valeur invalide de {name} ({v}) à l'année {year}, "
                               f"cellule {i * args.n + j} (ligne {i}, colonne {j}), essence {s}. "
                               f"Aucune correction n'est faite.")
        rows.append((year, eng.summary()))
        step_times.append(time.perf_counter() - ts)

    # --- sorties
    tw = time.perf_counter()
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "summary.csv"), "w", newline="\n") as f:
        f.write("year,species,sum_B,sum_D,mean_H\n")
        for year, tab in rows:
            for s in range(P.S):
                f.write(f"{year},{s},{tab[s, 0]:.16e},{tab[s, 1]:.16e},{tab[s, 2]:.16e}\n")
    with open(os.path.join(args.out, "state_final.f32"), "wb") as f:
        for A in (eng.B, eng.D, eng.H):
            np.ascontiguousarray(A, dtype="<f4").tofile(f)
    write_s = time.perf_counter() - tw
    total_s = init_s + sum(step_times)
    timing = {"lang": args.variant, "n": args.n, "years": args.years, "threads": T,
              "init_s": init_s,
              "step_mean_s": (sum(step_times) / len(step_times)) if step_times else 0.0,
              "total_s": total_s, "write_s": write_s}
    with open(os.path.join(args.out, "timing.json"), "w") as f:
        json.dump(timing, f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
