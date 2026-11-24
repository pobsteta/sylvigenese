"""Tests du banc Python (bench/SPEC.md §8)."""
import math
import os
import subprocess
import sys

import numpy as np
import pytest
import scipy.signal

import params as P
from kernel import Disperser, make_kernel
from rng import cell_hash, u_array, u_scalar

PYDIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIM = os.path.join(PYDIR, "sim.py")
VARIANTS = ["py-numpy", "py-numba"]

# SPEC §2 : (seed, year, cell, sp, u)
REF = [
    (42, 0, 0, 0, 0.7415648787718233),
    (42, 1, 0, 0, 0.1599103928769201),
    (42, 0, 1, 0, 0.14994666025136738),
    (42, 0, 0, 1, 0.5322551776720237),
    (42, 99, 999999, 7, 0.8685522737309959),
    (7, 3, 123456, 2, 0.3924761688504701),
]


def run_sim(variant, n, years, threads, out, *extra):
    cmd = [sys.executable, SIM, "--variant", variant, "--n", str(n), "--years", str(years),
           "--seed", "42", "--threads", str(threads), "--out", str(out), *extra]
    return subprocess.run(cmd, capture_output=True, text=True)


def read_state(path, n):
    return np.fromfile(path, dtype="<f4").reshape(3, P.S, n, n)  # B, D, H ; [s][i][j]


# ---------------------------------------------------------------- aléa
@pytest.mark.parametrize("seed,year,cell,sp,expected", REF)
def test_rng_scalar(seed, year, cell, sp, expected):
    assert u_scalar(seed, year, cell, sp) == expected


@pytest.mark.parametrize("seed,year,cell,sp,expected", REF)
def test_rng_numpy_array(seed, year, cell, sp, expected):
    cm = cell_hash(cell + 1)
    got = u_array(seed, year, sp, cm)[cell]
    assert got == expected


@pytest.mark.parametrize("seed,year,cell,sp,expected", REF)
def test_rng_numba(seed, year, cell, sp, expected):
    import v_numba
    assert v_numba.u_test(seed, year, cell, sp) == expected


def test_rng_no_overflow_warning():
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        u_array(2 ** 63 + 5, 10 ** 6, 7, cell_hash(1000))


# ---------------------------------------------------------------- noyau et FFT
def test_kernel_normalised_and_truncated():
    K = make_kernel()
    assert K.dtype == np.float64 and K.shape == (33, 33)
    assert abs(K.sum() - 1.0) < 1e-12
    assert K[16, 16] == K.max()
    assert K[0, 0] == 0.0                      # coin : d = 25*sqrt(512) > 400
    assert K[16, 0] > 0 and K[0, 16] > 0       # d = 400 exactement : inclus
    assert np.array_equal(K, K.T) and np.array_equal(K, K[::-1, ::-1])


@pytest.mark.parametrize("n", [40, 7])         # 7 : grille plus petite que le noyau
@pytest.mark.parametrize("workers", [1, 4])
def test_fft_matches_direct_convolution(n, workers):
    rng = np.random.default_rng(1)
    Pm = rng.random((n, n)) * 100
    K = make_kernel()
    d = Disperser(n, K, workers=workers)
    d.buf[:n, :n] = Pm
    Q = d.disperse()[:n, :n]
    ref = scipy.signal.convolve2d(Pm, K, mode="same", boundary="fill", fillvalue=0.0)
    assert np.max(np.abs(Q - ref)) / np.max(np.abs(ref)) < 1e-9
    # le bord est bien à zéro : un seul point source ne se replie pas de l'autre côté
    d.buf[:] = 0
    d.buf[0, 0] = 1.0
    Q = d.disperse()[:n, :n]
    ref = scipy.signal.convolve2d(_dirac(n), K, mode="same", boundary="fill")
    assert np.max(np.abs(Q - ref)) < 1e-12


def _dirac(n):
    a = np.zeros((n, n))
    a[0, 0] = 1.0
    return a


# ---------------------------------------------------------------- arrêts
@pytest.mark.parametrize("variant", VARIANTS)
def test_inject_nan_stops_with_french_message(variant, tmp_path):
    r = run_sim(variant, 20, 6, 1, tmp_path, "--inject-nan", "3")
    assert r.returncode != 0
    assert "année 3" in r.stderr and "cellule 0" in r.stderr and "essence 0" in r.stderr
    assert "NaN" in r.stderr.upper() or "nan" in r.stderr
    assert not (tmp_path / "state_final.f32").exists()


@pytest.mark.parametrize("variant", VARIANTS)
def test_inject_nan_out_of_range_refused(variant, tmp_path):
    for y in ("9", "0"):
        r = run_sim(variant, 20, 2, 1, tmp_path, "--inject-nan", y)
        assert r.returncode != 0 and "hors de" in r.stderr


@pytest.mark.parametrize("variant", VARIANTS)
def test_hmax_zero_refused_before_first_step(variant, tmp_path):
    r = run_sim(variant, 20, 6, 1, tmp_path, "--hmax-zero")
    assert r.returncode != 0
    assert "avant le premier pas" in r.stderr and "Hmax" in r.stderr
    assert "cellule 0" in r.stderr and "essence 0" in r.stderr
    assert not (tmp_path / "summary.csv").exists()   # aucun pas n'a été fait


# ---------------------------------------------------------------- disposition des données
@pytest.mark.parametrize("variant", VARIANTS)
def test_initial_state_layout_s_i_j(variant, tmp_path):
    """Un point du terrain tombe au bon endroit : B[s][i][j] avec c = i*N + j (années = 0)."""
    n = 13
    r = run_sim(variant, n, 0, 1, tmp_path)
    assert r.returncode == 0, r.stderr
    B, D, H = read_state(tmp_path / "state_final.f32", n)
    for (s, i, j) in [(0, 0, 0), (3, 7, 11), (7, 12, 0), (5, 0, 12)]:
        c = i * n + j
        forest = 1.0 if u_scalar(42, 0, c, 100) < 0.7 else 0.0
        expected = np.float32(forest * 5 * u_scalar(42, 0, c, 300 + s))
        assert B[s, i, j] == expected
    assert not D.any() and not H.any()


# ---------------------------------------------------------------- référence scalaire complète
def reference_run(n, years, seed):
    """Implémentation naïve de la spec (§3 à §6), boucles Python, convolution directe."""
    S, R = P.S, P.R
    f32 = np.float32
    K = make_kernel()
    forest = [[1.0 if u_scalar(seed, 0, i * n + j, 100) < 0.7 else 0.0 for j in range(n)] for i in range(n)]
    Hmax = np.zeros((S, n, n), np.float32)
    B = np.zeros((S, n, n), np.float32)
    D = np.zeros((S, n, n), np.float32)
    H = np.zeros((S, n, n), np.float32)
    for s in range(S):
        for i in range(n):
            for j in range(n):
                c = i * n + j
                Hmax[s, i, j] = f32(10 + 30 * u_scalar(seed, 0, c, 200 + s))
                B[s, i, j] = f32(forest[i][j] * 5 * u_scalar(seed, 0, c, 300 + s))
    for year in range(1, years + 1):
        Q = np.zeros((S, n, n))
        for s in range(S):
            Pm = P.FEC * B[s].astype(np.float64)
            for i in range(n):
                for j in range(n):
                    acc = 0.0
                    for di in range(-R, R + 1):
                        for dj in range(-R, R + 1):
                            ii, jj = i + di, j + dj
                            if 0 <= ii < n and 0 <= jj < n:
                                acc += Pm[ii, jj] * K[di + R, dj + R]
                    Q[s, i, j] = acc
        Bt = B.astype(np.float64).sum(axis=0)
        L = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                vals = [Bt[a, b] for a in range(max(0, i - 1), min(n, i + 2))
                        for b in range(max(0, j - 1), min(n, j + 2))]
                L[i, j] = math.exp(-P.K_EXT * (sum(vals) / len(vals)))
        for s in range(S):
            for i in range(n):
                for j in range(n):
                    c = i * n + j
                    d = float(D[s, i, j]) + forest[i][j] * P.EST * Q[s, i, j] * L[i, j] ** P.TOL[s]
                    D[s, i, j] = f32(d)
                    h = float(H[s, i, j])
                    hm = float(Hmax[s, i, j])
                    if D[s, i, j] > 0:
                        h = h + P.RGROW[s] * L[i, j] * (1 - h / hm)
                    h = min(h, hm)
                    H[s, i, j] = f32(h)
                    u = u_scalar(seed, year, c, s)
                    D[s, i, j] = f32(float(D[s, i, j]) * (1 - P.MORT[s] * (0.8 + 0.4 * u)))
                    if H[s, i, j] >= P.H_REC:
                        B[s, i, j] = f32(float(B[s, i, j]) + P.G * float(D[s, i, j]))
                        D[s, i, j] = 0
                        H[s, i, j] = 0
    return B, D, H


@pytest.mark.parametrize("variant", VARIANTS)
def test_matches_naive_reference(variant, tmp_path):
    n, years = 11, 4
    r = run_sim(variant, n, years, 1, tmp_path)
    assert r.returncode == 0, r.stderr
    got = read_state(tmp_path / "state_final.f32", n)
    ref = reference_run(n, years, 42)
    for k, name in enumerate("BDH"):
        np.testing.assert_allclose(got[k], ref[k], rtol=2e-6, atol=1e-7, err_msg=name)
    assert got[0].max() > 0 and got[1].max() > 0     # le test n'est pas vide
    # le pas n'est pas trivial : H a poussé, D non nul
    assert got[2].max() > 0


# ---------------------------------------------------------------- fils et variantes
@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    out = {}
    for v in VARIANTS:
        for t in (1, 4):
            d = tmp_path_factory.mktemp(f"{v}-t{t}")
            r = run_sim(v, 200, 5, t, d)
            assert r.returncode == 0, r.stderr
            out[(v, t)] = d
    return out


@pytest.mark.parametrize("variant", VARIANTS)
def test_bit_identical_between_1_and_4_threads(variant, runs):
    for name in ("summary.csv", "state_final.f32"):
        a = (runs[(variant, 1)] / name).read_bytes()
        b = (runs[(variant, 4)] / name).read_bytes()
        assert a == b, f"{variant} : {name} diffère entre 1 et 4 fils"


@pytest.mark.parametrize("variant", VARIANTS)
def test_threads_recorded_and_outputs_present(variant, runs):
    import json
    for t in (1, 4):
        tm = json.loads((runs[(variant, t)] / "timing.json").read_text())
        assert tm["lang"] == variant and tm["n"] == 200 and tm["years"] == 5 and tm["threads"] == t
        for k in ("init_s", "step_mean_s", "total_s", "write_s"):
            assert tm[k] >= 0
        size = (runs[(variant, t)] / "state_final.f32").stat().st_size
        assert size == 3 * P.S * 200 * 200 * 4


def _read_summary(path):
    lines = path.read_text().splitlines()
    assert lines[0] == "year,species,sum_B,sum_D,mean_H"
    return np.array([[float(x) for x in ln.split(",")] for ln in lines[1:]])


def test_variants_agree_on_summary(runs):
    a = _read_summary(runs[("py-numpy", 1)] / "summary.csv")
    b = _read_summary(runs[("py-numba", 1)] / "summary.csv")
    assert a.shape == b.shape == (5 * P.S, 5)
    assert np.array_equal(a[:, :2], b[:, :2])
    np.testing.assert_allclose(a[:, 2:], b[:, 2:], rtol=1e-9, atol=0)
