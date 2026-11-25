"""Garde-fous de l'oracle de tests (helpers_m3) : ces tests passent dès maintenant, car ils ne lancent pas le moteur.
Un oracle faux ferait échouer un moteur juste : on le prouve contre des références indépendantes."""
import math
import re
from pathlib import Path

import numpy as np
import pytest

import helpers_m3 as H


@pytest.mark.parametrize("seed,year,cell,sp,attendu", [
    (42, 0, 0, 0, 0.7415648787718233), (42, 1, 0, 0, 0.1599103928769201), (42, 0, 1, 0, 0.14994666025136738),
    (42, 0, 0, 1, 0.5322551776720237), (42, 99, 999999, 7, 0.8685522737309959), (7, 3, 123456, 2, 0.3924761688504701)])
def test_la_finalisation_splitmix_reproduit_la_table_du_banc(seed, year, cell, sp, attendu):
    """bench/SPEC.md §2 : table de référence du générateur à compteur."""
    assert H.u_bench(seed, year, cell, sp) == attendu


def test_u_chaine_est_dans_0_1_et_depend_de_chaque_argument():
    base = H.u_chained(42, 2027, 5, H.pack_species("09"), 1)
    assert 0 <= base < 1
    for autre in (H.u_chained(43, 2027, 5, H.pack_species("09"), 1), H.u_chained(42, 2028, 5, H.pack_species("09"), 1),
                  H.u_chained(42, 2027, 6, H.pack_species("09"), 1), H.u_chained(42, 2027, 5, H.pack_species("61"), 1),
                  H.u_chained(42, 2027, 5, H.pack_species("09"), 2)):
        assert autre != base


def test_u_chaine_est_uniforme():
    u = np.array([H.u_chained(42, 2027, i, H.pack_species("09"), 1) for i in range(20000)])
    assert abs(u.mean() - 0.5) < 0.01 and abs((u < 0.1).mean() - 0.1) < 0.01


def test_la_spline_naturelle_redonne_scipy():
    from scipy.interpolate import CubicSpline
    rng = np.random.default_rng(1)
    x = np.sort(rng.uniform(0, 80, 9))
    y = rng.normal(size=9)
    f = H.natural_spline(x, y)
    xs = np.linspace(x[0], x[-1], 200)
    ref = CubicSpline(x, y, bc_type="natural")(xs)
    assert np.abs(f(xs) - ref).max() < 1e-10
    assert np.allclose(f(x), y, atol=1e-12)                        # passe par les nœuds
    assert f(x[-1] + 50) == pytest.approx(y[-1], abs=1e-12)       # tenue au bord
    assert f(x[0] - 50) == pytest.approx(y[0], abs=1e-12)


def test_la_spline_a_deux_noeuds_est_une_droite():
    f = H.natural_spline([0.0, 2.0], [1.0, 5.0])
    assert f(1.0) == pytest.approx(3.0)


def test_chapman_richards_un_pas_est_exact():
    """H(t) = A (1 − exp(−k t))^p : le pas d'un an depuis H(t) vaut H(t+1), calculé directement."""
    A, k, p = 30.0, 0.04, 1.3
    for t in (5.0, 20.0, 60.0):
        h = A * (1 - math.exp(-k * t)) ** p
        assert float(H.chapman_richards_step(h, A, k, p)) == pytest.approx(A * (1 - math.exp(-k * (t + 1))) ** p, abs=1e-12)
    assert float(H.chapman_richards_step(31.0, A, k, p)) == 31.0       # au-dessus du plafond : dH = 0


def test_korf_un_pas_avance_la_hauteur_sous_l_asymptote():
    a, b, c = 40.0, 0.05, 1.2
    h = 20.0
    for pf in (4.0, 3.0, 2.0):
        n = float(H.korf_step(h, a, b, c, pf))
        assert h < n < a


def test_la_concurrence_compte_14_9_et_pas_15_1():
    x = np.array([0.0, 14.9, 0.0, 0.0, -15.1]); y = np.array([0.0, 0.0, 15.1, -14.9, 0.0])
    d = np.array([50.0, 70.0, 70.0, 60.0, 80.0])
    ba, bal, amb = H.competition(x, y, d)
    g = lambda dd: np.pi * (dd / 200) ** 2 * 10000 / H.AIRE_DISQUE
    assert ba[0] == pytest.approx(g(50) + g(70) + g(60))
    assert bal[0] == pytest.approx(g(70) + g(60))
    assert not amb[0]


def test_la_cellule_d_un_point_suit_la_formule(tmp_path):
    g = H.Grid.__new__(H.Grid)
    g.x0, g.y0, g.res, g.ncols, g.nrows = 700000.0, 6501000.0, 25.0, 40, 40
    assert int(g.cell_id(700012.5, 6500987.5)) == 0
    assert int(g.cell_id(700987.5, 6500987.5)) == 39
    assert int(g.cell_id(700012.5, 6500012.5)) == 1560
    assert int(g.cell_id(700987.5, 6500012.5)) == 1599


def test_ma_fonction_u_redonne_la_table_de_reference_publiee_par_la_mission_035():
    """tests/m3/reference/u_table.csv : les 21 lignes (graine, année, entité, essence, sorte, u) de la table de
    référence de l'aléa chaîné publiée dans la documentation de l'aléa (mission 035), calculée là en Python avec des
    entiers exacts ; l'oracle de ces tests les redonne au bit près (essence packée gros-boutiste : « 09 » = 0x3039)."""
    import csv
    with open(Path(__file__).parent / "reference" / "u_table.csv", encoding="utf-8", newline="") as f:
        lignes = list(csv.DictReader(f))
    assert len(lignes) == 21
    for r in lignes:
        u = H.u_chained(int(r["seed"]), int(r["year"]), int(r["entity"]), H.pack_species(r["species"]), int(r["kind"]))
        assert u == float(r["u"]), r
