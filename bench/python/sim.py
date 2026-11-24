#!/usr/bin/env python3
"""Banc d'essai (bench/SPEC.md) : simulation synthétique, variantes py-numpy / py-numba.

Exemple : python3 bench/python/sim.py --variant py-numpy --n 500 --years 100 \
              --seed 42 --threads 1 --out /tmp/x
Codes de sortie : 0 ok ; 2 entrée invalide ; 3 contrôle §6.8 déclenché.
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402

import params as P  # noqa: E402

EXIT_INPUT = 2
EXIT_CONTROL = 3


def parse(argv):
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("--variant", choices=["py-numpy", "py-numba"], default="py-numpy")
    a.add_argument("--n", type=int, required=True)
    a.add_argument("--years", type=int, required=True)
    a.add_argument("--seed", type=int, default=42)
    a.add_argument("--threads", type=int, default=1)
    a.add_argument("--out", required=True)
    a.add_argument("--inject-nan", type=int, default=None, metavar="YEAR")
    a.add_argument("--hmax-zero", action="store_true")
    return a.parse_args(argv)


def fail(code, msg):
    print(msg, file=sys.stderr)
    sys.exit(code)


def main(argv=None):
    args = parse(sys.argv[1:] if argv is None else argv)
    if args.n < 1 or args.years < 0 or args.threads < 1 or args.seed < 0:
        fail(EXIT_INPUT, "Erreur : --n et --threads doivent être >= 1, --years et --seed >= 0.")
    if args.inject_nan is not None and not (1 <= args.inject_nan <= args.years):
        fail(EXIT_INPUT, f"Erreur : --inject-nan {args.inject_nan} hors de 1 … {args.years}.")
    T = args.threads
    # Fils : fixés avant l'import de numba / de scipy.fft (workers=T plus loin).
    os.environ["NUMBA_NUM_THREADS"] = str(T)
    for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[v] = str(T)
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
