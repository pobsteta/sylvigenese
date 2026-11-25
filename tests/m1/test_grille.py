"""Grille de 25 m, alignement des rasters (spec §7, §9 ; BRIEF §4)."""
import numpy as np
import pytest

import helpers as H
from conftest import need

GRID_ALIGNED = ["dtm.tif", "forest_mask.tif", "ser.tif", "h0.tif", "chm_date.tif",
                "station_gradients.tif", "station_type.tif", "site_potential.tif",
                "vegetation_map.tif"]


def test_grille_a_25_m_en_2154(grid):
    assert grid.res == (25.0, 25.0), f"maille {grid.res}, attendu (25.0, 25.0) (ADR 0001)"
    assert grid.crs is not None and grid.crs.to_epsg() == 2154


def test_grille_ancree_sur_des_multiples_de_25_m_et_couvre_le_massif(grid):
    b = grid.bounds
    assert b.left % 25 == 0 and b.top % 25 == 0, f"coin nord-ouest ({b.left}, {b.top}) non aligné"
    assert b.left <= H.X0 and b.bottom <= H.Y0
    assert b.right >= H.X0 + H.SIDE and b.top >= H.Y0 + H.SIDE


@pytest.mark.parametrize("name", GRID_ALIGNED)
def test_raster_aligne_sur_grid_tif(grid, name):
    arr, nodata, dtypes, transform, crs = H.read_raster(need(name))
    assert arr.shape[1:] == grid.shape, f"{name} : forme {arr.shape[1:]} != grille {grid.shape}"
    assert tuple(transform)[:6] == pytest.approx(tuple(grid.transform)[:6], abs=1e-9), \
        f"{name} : géotransformation différente de grid.tif"
    assert crs.to_epsg() == 2154


def test_types_des_rasters(grid):
    attendu = {"h0.tif": "float32", "dtm.tif": "float32", "station_gradients.tif": "float32",
               "site_potential.tif": "float32", "ser.tif": "uint16", "forest_mask.tif": "uint16",
               "chm_date.tif": "uint16", "station_type.tif": "uint16",
               "vegetation_map.tif": "uint16"}
    for name, dt in attendu.items():
        _, _, dtypes, _, _ = H.read_raster(need(name))
        assert set(dtypes) == {dt}, f"{name} : types {dtypes}, attendu {dt}"


def test_station_gradients_a_trois_bandes_et_station_type_a_une(grid):
    arr, *_ = H.read_raster(need("station_gradients.tif"))
    assert arr.shape[0] == 3
    arr, *_ = H.read_raster(need("station_type.tif"))
    assert arr.shape[0] == 1


def test_mnt_rapporte_sans_deformation_sur_la_grille(grid):
    # Entrée MNT déjà à 25 m sur la même maille : les valeurs doivent rester les mêmes (spec §7).
    import rasterio
    out, nodata, *_ = H.read_raster(need("dtm.tif"))
    with rasterio.open(H.INPUTS / "dtm.tif") as r:
        src = r.read(1)
        t = r.transform
    cols = np.rint((grid.cx - t.c) / t.a - 0.5).astype(int)
    rows = np.rint((grid.cy - t.f) / t.e - 0.5).astype(int)
    ok = (rows >= 0) & (rows < src.shape[0]) & (cols >= 0) & (cols < src.shape[1])
    assert ok.sum() >= 1500
    assert np.allclose(out[0][ok], src[rows[ok], cols[ok]], atol=1e-3)


def test_station_gradients_restent_dans_l_intervalle_des_entrees(grid):
    # Bilinéaire (spec §7) : une valeur interpolée ne sort pas de l'intervalle de la source.
    import rasterio
    out, nodata, *_ = H.read_raster(need("station_gradients.tif"))
    with rasterio.open(H.INPUTS / "station_gradients.tif") as r:
        src = r.read()
    inside = grid.inside_massif()
    for b in range(3):
        v = out[b][inside]
        v = v[np.isfinite(v) & (v != nodata)]
        assert v.size >= 1500, f"bande {b + 1} : trop peu de cellules valides"
        assert v.min() >= src[b].min() - 1e-4 and v.max() <= src[b].max() + 1e-4, f"bande {b + 1}"


def test_station_type_par_nom_jamais_par_indice(grid):
    # spec §8 : catégories codées par leur nom ; légende = inputs/types.csv (colonne `type`).
    legend = {}
    lines = (H.INPUTS / "types.csv").read_text(encoding="utf-8").strip().splitlines()
    head = lines[0].split(";")
    for ln in lines[1:]:
        row = dict(zip(head, ln.split(";")))
        legend[int(row["id"])] = row["type"]
    cats = H.read_csv_map(need("station_type.csv"))
    assert set(cats.values()) <= set(legend.values()), \
        f"noms hors légende types.csv : {set(cats.values()) - set(legend.values())}"
    out, nodata, *_ = H.read_raster(need("station_type.tif"))
    out = out[0]
    vals = np.unique(out[(out != nodata) if nodata is not None else slice(None)])
    assert set(int(v) for v in vals) <= set(cats), "valeur du raster absente de station_type.csv"
    # Sur une cellule dont tous les pixels de 20 m recouverts sont du même type, le nom est celui-là.
    import rasterio
    with rasterio.open(H.INPUTS / "station_type.tif") as r:
        src, t = r.read(1), r.transform
    h = 0
    for (ri, ci) in zip(*np.nonzero(grid.inside_massif())):
        x0, x1 = grid.cx[ri, ci] - 12.5, grid.cx[ri, ci] + 12.5
        y0, y1 = grid.cy[ri, ci] - 12.5, grid.cy[ri, ci] + 12.5
        # pixels de 20 m qui recouvrent la cellule (surface non nulle) : si tous sont du même type,
        # n'importe quelle règle (plus proche, mode, majorité en surface) doit rendre ce type.
        i = np.arange(50)
        cs = i[(t.c + i * 20 < x1 - 1e-6) & (t.c + (i + 1) * 20 > x0 + 1e-6)]
        rs = i[(t.f - i * 20 > y0 + 1e-6) & (t.f - (i + 1) * 20 < y1 - 1e-6)]
        if cs.size == 0 or rs.size == 0:
            continue
        sub = src[np.ix_(rs, cs)]
        u = np.unique(sub)
        if u.size == 1:
            h += 1
            assert cats.get(int(out[ri, ci])) == legend[int(u[0])], \
                f"cellule ({ri},{ci}) : attendu {legend[int(u[0])]}"
    assert h >= 500, f"seulement {h} cellules homogènes contrôlées"


def test_site_potential_une_bande_par_ligne_de_table(grid):
    arr, nodata, *_ = H.read_raster(need("site_potential.tif"))
    cats = H.read_csv_map(need("site_potential.csv"))
    assert sorted(cats) == list(range(1, arr.shape[0] + 1)), \
        f"site_potential.csv {sorted(cats)} != bandes 1..{arr.shape[0]}"


def test_site_potential_dans_l_intervalle_de_h_pot(grid):
    import rasterio
    arr, nodata, *_ = H.read_raster(need("site_potential.tif"))
    with rasterio.open(H.INPUTS / "h_pot.tif") as r:
        src = r.read(1)
    v = arr[0][grid.inside_massif()]
    v = v[np.isfinite(v) & (v != nodata)]
    assert v.size >= 1500
    assert v.min() >= src.min() - 1e-3 and v.max() <= src.max() + 1e-3
