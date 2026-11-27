#!/usr/bin/env python3
"""Extrapolation (E) du coût du noyau à C20 (mission 082). Lit bench/results/m5_noyau_{mesures,fft}.csv et
écrit bench/results/m5_noyau_extrapolation.csv. Tout ce qu'il écrit est une EXTRAPOLATION, pas une mesure.

Mémoire : la formule de simulate/src/memoire.rs (estimer_ser), portée ici sans la borne d'écriture ni de lecture
(elles ne dominent pas à ces tailles) ; vérifiée d'abord contre les estimations des 22 exécutions mesurées.
Temps : bornes tirées des rapports mesurés (voir M5_noyau.md), appliquées à ceux de M5.md §4.1."""
import csv
from pathlib import Path

RES = Path(__file__).resolve().parents[1] / "results"
PART_FIXE = 10436 * 1024


def rapide(n):
    while True:
        r = n
        for f in (2, 3, 5, 7):
            while r % f == 0:
                r //= f
        if r == 1:
            return n
        n += 1


def estimer(cellules, foret, S, C, sigmaA, cand, N, K):
    cf, lf = rapide(N + 2 * K), rapide(N + 2 * K)
    vfft, vspec = cf * lf, (cf // 2 + 1) * lf
    durable = 33 * cellules + foret * (4 + 8 + 4 * S * C + 8 * sigmaA) + 16 * vspec * cand
    pas = foret * (16 + 8 * cand) + cellules * 17 + 16 * vspec + 8 * vfft
    return PART_FIXE + durable + pas, durable, pas, vfft, vspec


def main():
    # 1. contrôle de la formule contre les estimations mesurées (mêmes entrées : toutes cellules forestières)
    ecarts = []
    for x in csv.DictReader(open(RES / "m5_noyau_mesures.csv")):
        n, s, c, k = int(x["n"]), int(x["essences"]), int(x["classes"]), int(x["k"])
        sa, cand = (8, 2) if s == 2 else (32, 8)   # Σ A et candidates du générateur (M5.md, en-tête)
        e = estimer(n * n, n * n, s, c, sa, cand, n, k)[0]
        ecarts.append((e - int(x["memory_estimate_max_bytes"])) / int(x["memory_estimate_max_bytes"]))
    sortie = RES / "m5_noyau_extrapolation.csv"
    lignes = ["cas,k,valeurs_fft,valeurs_spectre,memoire_octets_E,ecart_formule_max_sur_les_mesures"]
    # 2. C20 : carré 6 926 x 6 926 (H1 de M5.md), 18,304 M cellules forestières, S = 8, 15 classes, Σ A = 32, 8 candidates
    N = 6926
    cas = {"reference_foret_seule_S8_C15": (N * N, 18_304_000, 8, 15, 32, 8),
           "rectangle_deux_fois_plus_grand": (2 * N * N, 18_304_000, 8, 15, 32, 8),
           "S12_SigmaA48": (N * N, 18_304_000, 12, 15, 48, 12)}
    for nom, (c_, f_, S, C, sa, cand) in cas.items():
        for k in (3, 20, 60):
            e, d, p, vf, vs = estimer(c_, f_, S, C, sa, cand, N if nom != "rectangle_deux_fois_plus_grand" else int(N * 2 ** 0.5), k)
            lignes.append(f"{nom},{k},{vf},{vs},{e},{max(abs(v) for v in ecarts):.5f}")
    # 3. rapports mesurés (K / K = 3, même N, S, fils) et temps de C20 (E) : M5.md §4.1, calcul seul majoré du plus
    # grand rapport observé (bruit compris, pas un effet établi) ; l'écriture et le validateur ne dépendent pas de K.
    m = {}
    for x in csv.DictReader(open(RES / "m5_noyau_mesures.csv")):
        m[(int(x["n"]), int(x["essences"]), int(x["threads"]), int(x["k"]))] = (float(x["calcul_s"]), int(x["rss_time_bytes"]))
    rap = ["n,essences,threads,k,rapport_calcul_a_k3,rapport_memoire_a_k3"]
    maxi = 1.0
    for (n, s, t, k), (c, r) in sorted(m.items()):
        if k != 3:
            c3, r3 = m[(n, s, t, 3)]
            rap.append(f"{n},{s},{t},{k},{c / c3:.4f},{r / r3:.4f}")
            maxi = max(maxi, c / c3)
    (RES / "m5_noyau_rapports.csv").write_text("\n".join(rap) + "\n", encoding="utf-8")
    t = ["fils,calcul_k3_s_E,total_k3_s_E,facteur_calcul_borne,calcul_borne_s_E,total_borne_s_E,total_borne_h_E,marge_sur_432000_E"]
    for fils, calcul3, total3 in ((1, 116087, 137488), (4, 37798, 58702)):
        calcul = calcul3 * maxi
        tot = total3 + calcul - calcul3
        t.append(f"{fils},{calcul3},{total3},{maxi:.4f},{calcul:.0f},{tot:.0f},{tot / 3600:.1f},{432000 / tot:.2f}")
    (RES / "m5_noyau_temps_c20.csv").write_text("\n".join(t) + "\n", encoding="utf-8")
    sortie.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    print("\n".join(lignes + rap + t))


if __name__ == "__main__":
    main()
