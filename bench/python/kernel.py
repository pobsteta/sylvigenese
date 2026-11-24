"""Noyau de dispersion (§5) et convolution par FFT (§6.2)."""
import numpy as np
import scipy.fft as sfft

from params import ALPHA, CELL, R, RMAX_M


def make_kernel():
    """Noyau (2R+1, 2R+1) en f64, normalisé (somme = 1). Indice [di+R, dj+R]."""
    di = np.arange(-R, R + 1)
    DI, DJ = np.meshgrid(di, di, indexing="ij")
    d = CELL * np.sqrt((DI ** 2 + DJ ** 2).astype(np.float64))
    K = np.where(d <= RMAX_M, np.exp(-d / ALPHA), 0.0)
    return K / K.sum()


class Disperser:
    """Convolution 2D par FFT sur toute la grille, bord à zéro.

    Grille remplie à zéro jusqu'à L >= max(n + R, 2R + 1) (longueur « rapide »
    de scipy) : pas de repli torique sur la zone utile. `buf[:n, :n]` reçoit P ;
    `disperse()` renvoie Q dans un tableau (L, L) dont [:n, :n] est utile.
    """

    def __init__(self, n, K, workers=1):
        self.n = n
        self.workers = workers
        self.L = sfft.next_fast_len(max(n + R, 2 * R + 1), real=True)
        kp = np.zeros((self.L, self.L))
        idx = np.arange(-R, R + 1) % self.L
        kp[np.ix_(idx, idx)] = K          # noyau centré en (0, 0), par repli
        self.Kf = sfft.rfft2(kp, workers=workers)
        self.buf = np.zeros((self.L, self.L))

    def disperse(self):
        F = sfft.rfft2(self.buf, workers=self.workers)
        F *= self.Kf
        return sfft.irfft2(F, s=(self.L, self.L), workers=self.workers)
