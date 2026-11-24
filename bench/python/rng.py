"""Générateur à compteur de la spec (§2), arithmétique modulo 2^64.

Trois formes : `u_scalar` (entiers Python, référence), `u_array` (numpy uint64
vectorisé). La forme numba est dans `v_numba.py`.
"""
import numpy as np

MASK = (1 << 64) - 1
C1 = 0x9E3779B97F4A7C15
C2 = 0xBF58476D1CE4E5B9
C3 = 0x94D049BB133111EB
TWO_M53 = 2.0 ** -53


def check_seed(seed):
    if not (0 <= seed < 2 ** 53):
        raise ValueError(f"graine hors de [0, 2^53) : {seed}")


def u_scalar(seed, year, cell, sp):
    """Tirage dans [0, 1) pour (seed, year, cell, sp), entiers Python."""
    check_seed(seed)
    x = seed ^ ((year * C1) & MASK) ^ ((cell * C2) & MASK) ^ ((sp * C3) & MASK)
    x = (x + C1) & MASK
    z = ((x ^ (x >> 30)) * C2) & MASK
    z = ((z ^ (z >> 27)) * C3) & MASK
    z ^= z >> 31
    return (z >> 11) * TWO_M53


def cell_hash(n_cells):
    """cell * C2 (mod 2^64) pour toutes les cellules ; réutilisable à chaque année."""
    with np.errstate(over="ignore"):
        return np.arange(n_cells, dtype=np.uint64) * np.uint64(C2)


def u_array(seed, year, sp, cell_mul):
    """Tirages pour toutes les cellules (cell_mul = cell_hash(...)), un seul `sp`."""
    check_seed(seed)
    base = np.uint64(seed ^ ((year * C1) & MASK) ^ ((sp * C3) & MASK))
    with np.errstate(over="ignore"):
        x = cell_mul ^ base
        x = x + np.uint64(C1)
        z = (x ^ (x >> np.uint64(30))) * np.uint64(C2)
        z = (z ^ (z >> np.uint64(27))) * np.uint64(C3)
        z = z ^ (z >> np.uint64(31))
    return (z >> np.uint64(11)).astype(np.float64) * TWO_M53
