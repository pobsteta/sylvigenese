"""Paramètres synthétiques du banc (bench/SPEC.md §4). Aucune valeur écologique."""

S = 8                 # essences
CELL = 25.0           # m
FEC = 100.0
ALPHA = 50.0          # m
RMAX_M = 400.0        # m
R = 16                # cellules (rayon de troncature)
K_EXT = 0.05          # « k » de la spec
EST = 0.01
H_REC = 3.0
G = 0.0001
DMAX = 1.0e6

TOL = [0.5 + 0.25 * s for s in range(S)]
RGROW = [0.3 + 0.05 * s for s in range(S)]
MORT = [0.05 + 0.01 * s for s in range(S)]
