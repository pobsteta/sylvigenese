#!/usr/bin/env python3
"""Coût du noyau de dispersion de simulate : K = kernel_truncation_cells (mission 082, 27/11/2026).

Rejouable depuis la racine du dépôt par ce seul script (après `cargo build --release --locked` de simulate) :
    python3 bench/m5/mesurer_noyau.py            # toute la matrice de M5_noyau.md
    python3 bench/m5/mesurer_noyau.py --petit    # essai rapide (N = 200)
Il écrit bench/results/m5_noyau_{reglages,mesures,pas,fft}.csv (voir M5_noyau.md pour le renvoi aux lignes).

RÉGLAGE D'ESSAI, SANS VALEUR ÉCOLOGIQUE. Le contrôle de la mission 080 refuse un K dont K x 25 m est sous le d99
de l'essence. Pour que chaque K passe, kernel_scale_m est réécrit (forme 1, toutes essences) pour que
d99 = 0,99 x K x 25 m : d99 = a x x99, où x99 est la solution de P(2, x) = 0,99 (même formule que
simulate/src/dispersion.rs). Le reste vient du générateur tests/m5/ser_fictive.py, inchangé.

Ce que le script mesure (une ligne par exécution, aucune répétition) : mémoire résidente (/usr/bin/time -v et
VmHWM de run.json), temps de calcul et d'écriture par année (lignes de stderr), durée de run.json. La FFT de
dispersion n'est pas séparée par simulate ; elle est mesurée à part par bench/m5/noyau_fft (appel de
simulate::dispersion, sans le modifier) : convolution seule, médiane de REP répétitions, aux mêmes N, K, fils.
Le disque est borné : sim/ est effacé après chaque exécution, la zone après chaque série.
"""
import argparse, datetime, json, os, re, shutil, subprocess, sys
from pathlib import Path

import pyarrow.parquet as pq
import pyarrow as pa
import yaml
from scipy.special import gammaincinv

RACINE = Path(__file__).resolve().parents[2]
RES = RACINE / "bench" / "results"
BIN = RACINE / "simulate" / "target" / "release" / "simulate"
TGT = os.environ.get("NOYAU_FFT_TARGET", str(RACINE / "data" / "bench_noyau_target"))  # hors dépôt
X99 = float(gammaincinv(2.0, 0.99))  # forme 1 : (d99 / a) = x99 ; P(2/b, x) = 0,99


def commit():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=RACINE, capture_output=True,
                              text=True).stdout.strip() or "inconnu"
    except Exception:
        return "inconnu"


def ecrire(chemin, entete, ligne):
    if not chemin.exists():
        chemin.write_text(entete + "\n", encoding="utf-8")
    with chemin.open("a", encoding="utf-8") as f:
        f.write(",".join(str(v) for v in ligne) + "\n")


def echelle_pour(k):
    return 0.99 * k * 25.0 / X99


def preparer_zone(zone, n, s, c, echelle):
    d = RACINE / "data" / zone
    if d.exists():
        shutil.rmtree(d)
    cmd = [sys.executable, str(RACINE / "tests/m5/ser_fictive.py"), "--n", str(n), "--graine", "1",
           "--essences", str(s), "--classes", str(c), "--sortie", str(d)]
    subprocess.run(cmd, check=True, cwd=RACINE, stdout=subprocess.DEVNULL)
    return d


def regler_noyau(d, echelle):
    chemin = d / "params" / "regeneration.parquet"
    t = pq.read_table(chemin)
    termes = t.column("term").to_pylist()
    valeurs = [echelle if x == "kernel_scale_m" else v for x, v in zip(termes, t.column("value").to_pylist())]
    t = t.set_column(t.schema.get_field_index("value"), "value", pa.array(valeurs, type=pa.float64()))
    pq.write_table(t, chemin)


def ecrire_config(d, zone, annees, fils, c, k):
    texte = (RACINE / "config.yml").read_text(encoding="utf-8")
    texte = re.sub(r"(?m)^zone:\s*\S+", f"zone: {zone}", texte)
    texte = re.sub(r"(?m)^simulate:\n(?:[ \t#][^\n]*\n?|\n(?=[ \t]))*", "", texte)
    bloc = {"level": "ser", "seed": 42, "t0": 2022, "years": annees, "threads": fils, "recruitment": "cohorts",
            "regeneration": {"kernel_truncation_cells": k, "zero_threshold": 1e-9},
            "ser": {"diameter_class_width_cm": 5.0, "diameter_classes": c, "write_step": annees}}
    texte = texte.rstrip("\n") + "\n\n" + yaml.safe_dump({"simulate": bloc}, sort_keys=False)
    cfg = d / "config_mesure.yml"
    cfg.write_text(texte, encoding="utf-8")
    return cfg


def une_execution(zone, d, n, s, c, k, fils, annees, sortie, cm):
    cfg = ecrire_config(d, zone, annees, fils, c, k)
    shutil.rmtree(d / "sim", ignore_errors=True)
    journal = d / "mesure_stderr.txt"
    with journal.open("w", encoding="utf-8") as f:
        r = subprocess.run(["/usr/bin/time", "-v", str(BIN), "--config", str(cfg)], cwd=RACINE, stderr=f)
    texte = journal.read_text(encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(texte[-1500:], file=sys.stderr)
        raise SystemExit(f"simulate a échoué (N={n} S={s} C={c} K={k} fils={fils}, code {r.returncode})")
    pas = [(float(a), float(b)) for a, b in re.findall(r"calcul ([0-9.]+) s ; écriture ([0-9.]+) s", texte)]
    calcul = sum(a for a, _ in pas)
    ecriture = sum(b for _, b in pas)
    m = re.search(r"Maximum resident set size \(kbytes\): (\d+)", texte)
    rss = int(m.group(1)) * 1024
    ec = re.search(r"Elapsed \(wall clock\) time.*: ([0-9:.]+)", texte).group(1)
    sec = sum(float(x) * 60 ** i for i, x in enumerate(reversed(ec.split(":"))))
    j = json.loads((d / "sim" / "run.json").read_text(encoding="utf-8"))
    ligne = [datetime.date.today().isoformat(), cm, n, s, c, k, fils, annees, f"{calcul:.3f}", f"{ecriture:.3f}",
             f"{j['duration_s']:.3f}", f"{sec:.3f}", rss, j["memory_peak_rss_bytes"], j["memory_estimate_max_bytes"],
             j.get("buffer_cells", "")]
    ecrire(sortie["mesures"], "date,commit,n,essences,classes,k,threads,years,calcul_s,ecriture_s,duration_s,"
           "ecoule_s,rss_time_bytes,memory_peak_rss_bytes,memory_estimate_max_bytes,buffer_cells", ligne)
    for rang, (a, b) in enumerate(pas):
        ecrire(sortie["pas"], "date,commit,n,essences,classes,k,threads,rang,calcul_s,ecriture_s",
               [datetime.date.today().isoformat(), cm, n, s, c, k, fils, rang, a, b])
    print(f"N={n} S={s} C={c} K={k} fils={fils} : calcul {calcul:.1f} s, rss {rss / 1e6:.0f} Mo", flush=True)
    shutil.rmtree(d / "sim", ignore_errors=True)


def fft(n, k, fils, rep, echelle, sortie, cm):
    exe = Path(TGT) / "release" / "noyau_fft"
    env = dict(os.environ, RAYON_NUM_THREADS=str(fils))
    out = subprocess.run([str(exe), str(n), str(k), str(rep), str(echelle)], capture_output=True, text=True,
                         env=env, check=True).stdout.strip()
    ecrire(sortie["fft"], "date,commit,n,k,threads,colonnes_fft,lignes_fft,tampon_cellules,plan_s,spectre_s,"
           "convolution_mediane_s,repetitions", [datetime.date.today().isoformat(), cm] + out.split(","))
    print("fft", out, flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--n", default="1000 2000")
    p.add_argument("--k", default="3 20 60")
    p.add_argument("--fils", default="1 4")
    p.add_argument("--annees", type=int, default=10)
    p.add_argument("--s8-n", default="1000", help="tailles à S = 8, classes = 15 (vide : aucune)")
    p.add_argument("--n4000-fils", default="4", help="fils à N = 4000, S = 2 (vide : aucun)")
    p.add_argument("--rep", type=int, default=5)
    p.add_argument("--prefixe", default="m5_noyau")
    p.add_argument("--petit", action="store_true")
    a = p.parse_args()
    if a.petit:
        a.n, a.s8_n, a.n4000_fils, a.annees, a.rep, a.prefixe = "200", "", "", 2, 3, "m5_noyau_petit"
    RES.mkdir(parents=True, exist_ok=True)
    subprocess.run(["cargo", "build", "--release", "--locked", "--quiet", "--manifest-path", "simulate/Cargo.toml"],
                   cwd=RACINE, check=True)
    subprocess.run(["cargo", "build", "--release", "--quiet", "--manifest-path", "bench/m5/noyau_fft/Cargo.toml"],
                   cwd=RACINE, check=True, env=dict(os.environ, CARGO_TARGET_DIR=TGT))
    sortie = {x: RES / f"{a.prefixe}_{x}.csv" for x in ("reglages", "mesures", "pas", "fft")}
    cm = commit()
    ks = [int(x) for x in a.k.split()]
    for k in ks:
        ecrire(sortie["reglages"], "k,portee_m,kernel_scale_m,kernel_shape,x99,d99_m",
               [k, k * 25, f"{echelle_pour(k):.4f}", 1.0, f"{X99:.6f}", f"{echelle_pour(k) * X99:.3f}"])
    series = [(int(n), 2, 6, [int(x) for x in a.fils.split()]) for n in a.n.split()]
    series += [(int(n), 8, 15, [int(x) for x in a.fils.split()]) for n in a.s8_n.split()]
    series += [(4000, 2, 6, [int(x) for x in a.n4000_fils.split()])] if a.n4000_fils.strip() else []
    for n, s, c, fils in series:
        zone = f"ser_noyau_{n}_s{s}_k{c}"
        d = None
        for k in ks:
            e = echelle_pour(k)
            d = preparer_zone(zone, n, s, c, e) if d is None else d
            regler_noyau(d, e)
            for t in fils:
                une_execution(zone, d, n, s, c, k, t, a.annees, sortie, cm)
        shutil.rmtree(d, ignore_errors=True)
    for n in sorted({sr[0] for sr in series}):
        for k in ks:
            for t in [int(x) for x in a.fils.split()]:
                fft(n, k, t, a.rep, echelle_pour(k), sortie, cm)


if __name__ == "__main__":
    main()
