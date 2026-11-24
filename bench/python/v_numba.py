"""Variante py-numba : boucles cellule à cellule en numba (prange), FFT scipy.

NUMBA_NUM_THREADS doit être fixé avant l'import (fait par sim.py).
"""
import numpy as np
from numba import njit, prange, get_num_threads, set_num_threads

import params as P
from kernel import Disperser, make_kernel
from rng import C1, C2, C3

NAME = "py-numba"

_C1, _C2, _C3 = np.uint64(C1), np.uint64(C2), np.uint64(C3)
_S11, _S27, _S30, _S31 = np.uint64(11), np.uint64(27), np.uint64(30), np.uint64(31)
_SCALE = 2.0 ** -53


@njit(cache=True, inline="always")
def u_nb(seed, year, cell, sp):
    """Tous les arguments en uint64 : l'arithmétique est modulo 2^64."""
    x = seed ^ (year * _C1) ^ (cell * _C2) ^ (sp * _C3)
    x = x + _C1
    z = (x ^ (x >> _S30)) * _C2
    z = (z ^ (z >> _S27)) * _C3
    z = z ^ (z >> _S31)
    return np.float64(z >> _S11) * _SCALE


@njit(cache=True)
def u_test(seed, year, cell, sp):
    """Point d'entrée de test (arguments entiers quelconques, convertis en uint64)."""
    return u_nb(np.uint64(seed), np.uint64(year), np.uint64(cell), np.uint64(sp))


@njit(parallel=True, cache=True)
def k_init(seed, n, forest, Hmax, B):
    S = B.shape[0]
    z = np.uint64(0)
    for i in prange(n):
        for j in range(n):
            c = np.uint64(i * n + j)
            f = 1.0 if u_nb(seed, z, c, np.uint64(100)) < 0.7 else 0.0
            forest[i, j] = np.uint8(f)
            for s in range(S):
                Hmax[s, i, j] = np.float32(10 + 30 * u_nb(seed, z, c, np.uint64(200 + s)))
                B[s, i, j] = np.float32(f * 5 * u_nb(seed, z, c, np.uint64(300 + s)))


@njit(parallel=True, cache=True)
def k_btot(B, btot):
    S, n, _ = B.shape
    for i in prange(n):
        for j in range(n):
            bt = 0.0
            for s in range(S):
                bt += B[s, i, j]
            btot[i, j] = bt


@njit(parallel=True, cache=True)
def k_light(btot, k, L):
    n = btot.shape[0]
    for i in prange(n):
        for j in range(n):
            acc = 0.0
            cnt = 0
            for di in range(-1, 2):
                ii = i + di
                if ii < 0 or ii >= n:
                    continue
                for dj in range(-1, 2):
                    jj = j + dj
                    if jj < 0 or jj >= n:
                        continue
                    acc += btot[ii, jj]
                    cnt += 1
            L[i, j] = np.exp(-k * (acc / cnt))


@njit(parallel=True, cache=True)
def k_seeds(Bs, fec, buf):
    n = Bs.shape[0]
    for i in prange(n):
        for j in range(n):
            buf[i, j] = fec * Bs[i, j]


@njit(parallel=True, cache=True)
def k_update(Bs, Ds, Hs, Hm, Q, L, forest, tol, est, r, m, h_rec, g, seed, year, s):
    n = Bs.shape[0]
    su = np.uint64(s)
    for i in prange(n):
        for j in range(n):
            c = np.uint64(i * n + j)
            Lv = L[i, j]
            # 4. installation
            Dv = np.float64(Ds[i, j]) + forest[i, j] * est * Q[i, j] * Lv ** tol
            Ds[i, j] = np.float32(Dv)
            Dv = np.float64(Ds[i, j])
            # 5. croissance
            Hv = np.float64(Hs[i, j])
            hm = np.float64(Hm[i, j])
            if Dv > 0.0:
                Hv = Hv + r * Lv * (1.0 - Hv / hm)
            if Hv > hm:
                Hv = hm
            Hs[i, j] = np.float32(Hv)
            Hv = np.float64(Hs[i, j])
            # 6. mortalité
            u = u_nb(seed, year, c, su)
            Dv = Dv * (1.0 - m * (0.8 + 0.4 * u))
            Ds[i, j] = np.float32(Dv)
            Dv = np.float64(Ds[i, j])
            # 7. recrutement
            if Hv >= h_rec:
                Bs[i, j] = np.float32(np.float64(Bs[i, j]) + g * Dv)
                Ds[i, j] = np.float32(0.0)
                Hs[i, j] = np.float32(0.0)


@njit(parallel=True, cache=True)
def k_bad_rows(A, dmax, use_dmax, flags):
    S, n, _ = A.shape
    for t in prange(S * n):
        s = t // n
        i = t % n
        bad = -1
        for j in range(n):
            v = A[s, i, j]
            if v != v or v < 0.0 or (use_dmax and v > dmax):
                bad = j
                break
        flags[t] = bad


@njit(parallel=True, cache=True)
def k_summary(B, D, H, out):
    S, n, _ = B.shape
    rb = np.zeros((S, n))
    rd = np.zeros((S, n))
    rh = np.zeros((S, n))
    rc = np.zeros((S, n), np.int64)
    for t in prange(S * n):
        s = t // n
        i = t % n
        ab = 0.0
        ad = 0.0
        ah = 0.0
        c = 0
        for j in range(n):
            ab += B[s, i, j]
            ad += D[s, i, j]
            if D[s, i, j] > 0:
                ah += H[s, i, j]
                c += 1
        rb[s, i] = ab
        rd[s, i] = ad
        rh[s, i] = ah
        rc[s, i] = c
    for s in range(S):          # réduction séquentielle, dans l'ordre des lignes
        sb = 0.0
        sd = 0.0
        sh = 0.0
        sc = 0
        for i in range(n):
            sb += rb[s, i]
            sd += rd[s, i]
            sh += rh[s, i]
            sc += rc[s, i]
        out[s, 0] = sb
        out[s, 1] = sd
        out[s, 2] = sh / sc if sc > 0 else 0.0


class Engine:
    name = NAME

    def __init__(self, n, seed, threads):
        self.n, self.seed, self.threads = n, seed, threads
        set_num_threads(threads)
        assert get_num_threads() == threads, "nombre de fils numba non appliqué"
        self.useed = np.uint64(seed)

    def init(self):
        n, S = self.n, P.S
        self.forest = np.empty((n, n), np.uint8)
        self.Hmax = np.empty((S, n, n), np.float32)
        self.B = np.empty((S, n, n), np.float32)
        k_init(self.useed, n, self.forest, self.Hmax, self.B)
        self.D = np.zeros((S, n, n), np.float32)
        self.H = np.zeros((S, n, n), np.float32)
        self.btot = np.empty((n, n))
        self.L = np.empty((n, n))
        self.disp = Disperser(n, make_kernel(), workers=self.threads)
        self.tol = np.array(P.TOL)
        self.r = np.array(P.RGROW)
        self.m = np.array(P.MORT)
        self.flags = np.empty(S * n, np.int64)
        self.sum_out = np.zeros((S, 3))

    def step(self, year):
        n, S = self.n, P.S
        k_btot(self.B, self.btot)
        k_light(self.btot, P.K_EXT, self.L)
        uyear = np.uint64(year)
        for s in range(S):
            k_seeds(self.B[s], P.FEC, self.disp.buf)
            Q = self.disp.disperse()
            k_update(self.B[s], self.D[s], self.H[s], self.Hmax[s], Q, self.L,
                     self.forest, float(self.tol[s]), P.EST, float(self.r[s]),
                     float(self.m[s]), P.H_REC, P.G, self.useed, uyear, s)

    def violation(self, dmax):
        """Premier défaut (nom, s, i, j) : ordre essence, ligne, colonne, puis B, D, H (P7)."""
        n = self.n
        best = None
        for name, A in (("B", self.B), ("D", self.D), ("H", self.H)):
            k_bad_rows(A, dmax, name == "D", self.flags)
            nz = np.flatnonzero(self.flags >= 0)
            if nz.size:
                t = int(nz[0])
                flat = t * n + int(self.flags[t])
                if best is None or flat < best[0]:
                    best = (flat, name)
        if best is None:
            return None
        t, j = divmod(best[0], n)
        return best[1], t // n, t % n, j

    def summary(self):
        k_summary(self.B, self.D, self.H, self.sum_out)
        return self.sum_out.copy()


def warmup():
    """Compile (ou charge du cache) tous les noyaux sur une petite grille."""
    e = Engine(20, 1, get_num_threads())
    e.init()
    e.step(1)
    e.violation(P.DMAX)
    e.summary()
