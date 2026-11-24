"""Variante py-numpy : numpy vectorisé, scipy.fft pour la dispersion."""
import numpy as np

import params as P
from kernel import Disperser, make_kernel
from rng import cell_hash, u_array

NAME = "py-numpy"


class Engine:
    name = NAME

    def __init__(self, n, seed, threads):
        self.n, self.seed, self.threads = n, seed, threads

    def init(self):
        n, S, seed = self.n, P.S, self.seed
        self.cm = cell_hash(n * n)
        forest = (u_array(seed, 0, 100, self.cm) < 0.7).astype(np.uint8)
        f = forest.astype(np.float64)
        self.forest = forest.reshape(n, n)
        self.Hmax = np.empty((S, n, n), np.float32)
        self.B = np.empty((S, n, n), np.float32)
        for s in range(S):
            self.Hmax[s] = (10 + 30 * u_array(seed, 0, 200 + s, self.cm)).reshape(n, n)
            self.B[s] = (f * 5 * u_array(seed, 0, 300 + s, self.cm)).reshape(n, n)
        self.D = np.zeros((S, n, n), np.float32)
        self.H = np.zeros((S, n, n), np.float32)
        # nombre de cellules présentes dans la fenêtre 3x3
        ones = np.zeros((n + 2, n + 2))
        ones[1:-1, 1:-1] = 1.0
        cnt = np.zeros((n, n))
        for di in range(3):
            for dj in range(3):
                cnt += ones[di:di + n, dj:dj + n]
        self.cnt = cnt
        self.disp = Disperser(n, make_kernel(), workers=1)  # FFT mono-fil : identité 1/T fils par construction

    def step(self, year):
        n, S = self.n, P.S
        B, D, H, Hmax = self.B, self.D, self.H, self.Hmax
        fo = self.forest.astype(np.float64)
        # 3. lumière (lit B avant toute modification)
        btot = np.zeros((n, n))
        for s in range(S):
            btot += B[s]
        pad = np.zeros((n + 2, n + 2))
        pad[1:-1, 1:-1] = btot
        acc = np.zeros((n, n))
        for di in range(3):
            for dj in range(3):
                acc += pad[di:di + n, dj:dj + n]
        L = np.exp(-P.K_EXT * (acc / self.cnt))
        with np.errstate(invalid="ignore", over="ignore"):
            for s in range(S):
                # 1-2. graines puis dispersion (FFT)
                self.disp.buf[:n, :n] = P.FEC * B[s].astype(np.float64)  # f64 explicite (pas de f32 faible)
                Q = self.disp.disperse()[:n, :n]
                # 4. installation
                Dv = D[s].astype(np.float64) + fo * P.EST * Q * np.power(L, P.TOL[s])
                D[s] = Dv
                # 5. croissance
                Hf = H[s].astype(np.float64)
                Hm = Hmax[s].astype(np.float64)
                Hf = np.where(D[s] > 0, Hf + P.RGROW[s] * L * (1.0 - Hf / Hm), Hf)
                Hf = np.where(Hf > Hm, Hm, Hf)
                H[s] = Hf
                # 6. mortalité
                u = u_array(self.seed, year, s, self.cm).reshape(n, n)
                D[s] = D[s].astype(np.float64) * (1.0 - P.MORT[s] * (0.8 + 0.4 * u))
                # 7. recrutement
                rec = H[s] >= P.H_REC
                Bn = B[s].astype(np.float64) + P.G * D[s].astype(np.float64)
                B[s] = np.where(rec, Bn, B[s])
                D[s] = np.where(rec, 0.0, D[s])
                H[s] = np.where(rec, 0.0, H[s])

    def violation(self, dmax):
        """Premier défaut (nom, s, i, j) : ordre essence, ligne, colonne, puis B, D, H (P7)."""
        best = None
        for k, (name, A) in enumerate((("B", self.B), ("D", self.D), ("H", self.H))):
            with np.errstate(invalid="ignore"):
                bad = np.isnan(A) | (A < 0)
                if name == "D":
                    bad |= A > dmax
            if bad.any():
                flat = int(np.argmax(bad))
                if best is None or flat < best[0]:
                    best = (flat, name)
        if best is None:
            return None
        s, i, j = np.unravel_index(best[0], self.B.shape)
        return best[1], int(s), int(i), int(j)

    def summary(self):
        """Tableau (S, 3) f64 : sum_B, sum_D, mean_H. Lignes sommées dans l'ordre."""
        out = np.zeros((P.S, 3))
        for s in range(P.S):
            rb = np.cumsum(self.B[s], axis=1, dtype=np.float64)[:, -1]   # ordre j, séquentiel (P2)
            rd = np.cumsum(self.D[s], axis=1, dtype=np.float64)[:, -1]
            pos = self.D[s] > 0
            rh = np.cumsum(np.where(pos, self.H[s], 0.0), axis=1, dtype=np.float64)[:, -1]
            cnt = int(np.count_nonzero(pos))
            out[s, 0] = np.cumsum(rb)[-1]
            out[s, 1] = np.cumsum(rd)[-1]
            out[s, 2] = np.cumsum(rh)[-1] / cnt if cnt > 0 else 0.0
        return out
