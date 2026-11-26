"""La mesure externe de la mémoire (helpers_m5.mesurer_rss) n'hérite pas du pic du processus parent (mission 063).

Sous Linux, ru_maxrss lu par wait4 depuis un parent gros reprend le pic du parent (hérité à l'exec) : pytest, qui
génère la zone N = 1 000, était mesuré à la place de simulate. La mesure par /usr/bin/time -v repart d'un pic neuf."""
from __future__ import annotations

import resource

import numpy as np

import helpers_m5 as H

MIO = 1024 * 1024


def test_la_mesure_externe_n_herite_pas_du_pic_du_parent(tmp_path):
    bloc = np.ones(500 * MIO, dtype=np.uint8)          # 500 Mo réellement touchés : le pic du parent monte
    assert bloc.sum() == 500 * MIO
    pic_parent = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    assert pic_parent > 450 * MIO, "le parent d'essai n'a pas atteint 500 Mo : le test ne prouverait rien"
    with open(tmp_path / "o", "w") as o, open(tmp_path / "e", "w") as e:
        code, rss = H.mesurer_rss(["/bin/true"], tmp_path, o, e)
    assert code == 0
    assert 0 < rss < 20 * MIO, f"/bin/true mesuré à {rss / MIO:.1f} Mio : le pic du parent ({pic_parent / MIO:.0f} Mio) fuit"
    del bloc


def test_la_mesure_externe_transmet_le_code_de_retour(tmp_path):
    with open(tmp_path / "o", "w") as o, open(tmp_path / "e", "w") as e:
        code, rss = H.mesurer_rss(["/bin/false"], tmp_path, o, e)
    assert code == 1 and rss > 0
