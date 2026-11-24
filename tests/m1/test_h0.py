"""H0 à partir du MNH, chm_date (spec §4.4, §5 ; CLAUDE.md : hauteur, signaler sans corriger)."""
import numpy as np
import pytest
import rasterio

import helpers as H
from conftest import need

TOL_M = 0.5  # écart toléré au percentile 95 du MNH (provisoire, spec §5) selon la méthode de quantile


@pytest.fixture(scope="module")
def chm_blocks(grid):
    """Pour chaque cellule de la grille, les pixels du MNH à 50 cm qu'elle contient."""
    with rasterio.open(H.INPUTS / "chm.tif") as r:
        a = r.read(1)
        t = r.transform
    out = {}
    n = int(round(25 / t.a))
    for (ri, ci) in zip(*np.nonzero(grid.inside_massif())):
        x0 = grid.cx[ri, ci] - 12.5
        y1 = grid.cy[ri, ci] + 12.5
        c0 = int(round((x0 - t.c) / t.a))
        r0 = int(round((t.f - y1) / -t.e))
        out[(ri, ci)] = a[r0:r0 + n, c0:c0 + n].ravel()
    return out


def test_h0_est_le_percentile_95_du_mnh_de_la_cellule(grid, chm_blocks):
    arr, nodata, *_ = H.read_raster(need("h0.tif"))
    h0 = arr[0]
    ecarts = []
    for (ri, ci), px in chm_blocks.items():
        px = px[px != -9999]
        if px.size == 0:
            continue
        v = h0[ri, ci]
        assert np.isfinite(v) and v != nodata, f"h0 invalide en ({ri},{ci}) : valeur par défaut interdite"
        ecarts.append(abs(float(v) - float(np.percentile(px, 95))))
    assert len(ecarts) >= 1500
    assert max(ecarts) <= TOL_M, f"écart maximal au P95 du MNH : {max(ecarts):.3f} m (tolérance {TOL_M})"


def test_h0_non_corrige_au_dessus_du_plafond_dans_s03(grid):
    # S03 : épicéa de 36 m, au-dessus de h_pot. H0 reste la hauteur du MNH, jamais plafonnée.
    arr, *_ = H.read_raster(need("h0.tif"))
    s03 = grid.fully_in((350, 650, 500, 1000))
    assert s03.sum() >= 200
    assert np.median(arr[0][s03]) > 33.0, f"médiane H0 en S03 : {np.median(arr[0][s03]):.1f} m"
    sp, *_ = H.read_raster(need("site_potential.tif"))
    part = float((arr[0][s03] > sp[0][s03]).mean())
    assert part >= 0.9, f"seulement {part:.0%} des cellules S03 ont H0 au-dessus du plafond"


def test_h0_dans_la_trouee_est_nul_ou_absent_et_pas_invente(grid):
    arr, nodata, *_ = H.read_raster(need("h0.tif"))
    # Cœur de la trouée (marge d'une cellule : les houppiers des bords débordent dans le MNH).
    gap = grid.fully_in((H.GAP[0] + 25, H.GAP[1] - 25, H.GAP[2] + 25, H.GAP[3] - 25))
    assert gap.sum() >= 20
    v = arr[0][gap]
    ok = (v == nodata) | ~np.isfinite(v) | (v <= TOL_M)
    assert ok.all(), f"h0 > {TOL_M} m dans la trouée (MNH nul) : {v[~ok][:5]}"


def test_h0_ne_depasse_pas_le_maximum_du_mnh(grid):
    arr, nodata, *_ = H.read_raster(need("h0.tif"))
    with rasterio.open(H.INPUTS / "chm.tif") as r:
        mx = float(r.read(1).max())
    v = arr[0][np.isfinite(arr[0]) & (arr[0] != nodata)]
    assert v.max() <= mx + 1e-3


def test_chm_date_est_la_date_de_vol_de_la_dalle_en_jours_depuis_1970(grid):
    arr, nodata, dtypes, *_ = H.read_raster(need("chm_date.tif"))
    assert dtypes[0] == "uint16"
    tuiles = H.read_lidar_tiles()
    assert len(tuiles) == 4
    for t in tuiles:
        x0, x1, y0, y1 = (t["bbox"][0] - H.X0, t["bbox"][1] - H.X0,
                          t["bbox"][2] - H.Y0, t["bbox"][3] - H.Y0)
        cells = grid.fully_in((x0, x1, y0, y1)) & grid.forest()
        assert cells.sum() >= 100
        attendu = H.days_since_epoch(t["flight_date"])
        assert set(int(x) for x in np.unique(arr[0][cells])) == {attendu}, \
            f"dalle du {t['flight_date']} : attendu {attendu} jours"
