"""Suite de M4a (mission 045) : carte au sol de la surface terrière, web/rasters/g_<année>.tif, une par année
retenue, à échelle fixe sur toutes les années simulées (décision de Pascal Q3 du 25/11/2026 ; contrat
assets.basal_area_raster ; basal_area_map de tiles/index.json)."""
import numpy as np
import pytest
import rasterio

import helpers_m4 as H
import helpers_m4_temps as T

ANNEES = T.retained_years(T.T0, T.YEARS, T.STEP)


def _g_attendu(temps_cells, forest, year):
    g = np.full((H.NROWS, H.NCOLS), np.nan)
    for cid in forest:
        g[divmod(cid, H.NCOLS)] = 0.0
    for (cid, y), rows in temps_cells.items():
        if y == year:
            g[divmod(cid, H.NCOLS)] = sum(float(r["basal_area_m2_ha"]) for r in rows)
    return g


def test_un_raster_g_par_annee_retenue_conforme_au_contrat(temps):
    zdir = T.exige_temps(temps)
    tifs = [zdir / "web" / "rasters" / f"g_{y}.tif" for y in ANNEES]
    manque = [p.name for p in tifs if not p.is_file()]
    assert not manque, f"absents : {manque}"
    p = H.validate("basal_area_raster", "--grid", str(zdir / "grid.tif"), *map(str, tifs))
    assert p.returncode == 0, p.stdout[-1500:] + p.stderr[-800:]


@pytest.mark.parametrize("annee", ANNEES)
def test_g_est_un_cog_float32_aligne_sur_la_grille(temps, annee):
    zdir = T.exige_temps(temps)
    with rasterio.open(zdir / "grid.tif") as g, rasterio.open(zdir / "web" / "rasters" / f"g_{annee}.tif") as r:
        assert r.crs.to_epsg() == 2154 and r.count == 1 and r.dtypes[0] == "float32"
        assert r.profile.get("tiled") and r.overviews(1), "COG avec aperçus attendu (spec §9)"
        assert r.transform.almost_equals(g.transform) and (r.width, r.height) == (g.width, g.height)
        assert r.nodata is not None


@pytest.mark.parametrize("annee", ANNEES)
def test_g_de_chaque_cellule_est_la_somme_de_sim_cells(temps, temps_cells, annee):
    zdir = T.exige_temps(temps)
    forest = H.Oracle(zdir).forest_cells()
    att = _g_attendu(temps_cells, forest, annee)
    a, nd, _, _ = H.read_raster(zdir / "web" / "rasters" / f"g_{annee}.tif")
    a = a.astype("float64")
    vide = a == nd
    assert np.array_equal(vide, np.isnan(att)), \
        f"{annee} : nodata sur {int(vide.sum())} cellules, {int(np.isnan(att).sum())} cellules hors forêt et sans arbre"
    ok = ~vide
    err = np.abs(a[ok] - att[ok]) / np.maximum(1.0, att[ok])
    assert err.max() <= 1e-6, f"{annee} : écart relatif maximal {err.max():.2e} à sim/cells (float32)"


def test_x_et_y_ne_sont_pas_inverses_dans_la_carte(temps, temps_cells):
    # Piège de la Somalie : la carte transposée ne doit pas concorder avec sim/cells.
    zdir = T.exige_temps(temps)
    att = _g_attendu(temps_cells, H.Oracle(zdir).forest_cells(), ANNEES[-1])
    a, nd, _, _ = H.read_raster(zdir / "web" / "rasters" / f"g_{ANNEES[-1]}.tif")
    ok = (a != nd) & np.isfinite(att)
    assert not np.allclose(att[ok], att.T[ok], rtol=1e-3), "carte symétrique : test sans pouvoir"
    assert np.allclose(a[ok], att[ok], rtol=1e-6)


def test_l_echelle_est_fixe_et_couvre_toutes_les_annees_simulees(temps, temps_index, temps_cells):
    m = temps_index["basal_area_map"]
    assert m["unit"] == "m2/ha" and T.MENTION_ECO in m["mention"]
    par = {}
    for (cid, y), rows in temps_cells.items():
        par.setdefault(y, []).append(sum(float(r["basal_area_m2_ha"]) for r in rows))
    lo = min(min(v) for v in par.values())
    hi = max(max(v) for v in par.values())
    assert m["scale_min_m2_ha"] <= lo + 1e-9 and m["scale_max_m2_ha"] >= hi - 1e-9, \
        f"échelle [{m['scale_min_m2_ha']}, {m['scale_max_m2_ha']}] ne couvre pas [{lo}, {hi}] (toutes les années de sim/cells)"
    assert m["scale_max_m2_ha"] > m["scale_min_m2_ha"]


def test_l_echelle_ne_depend_pas_des_annees_retenues(temps, temps_index):
    # Même sim/, pas de 5 puis pas de 10 : l'échelle est celle de toutes les années simulées, donc la même.
    T.exige_temps(temps)
    a, b = temps["apres_5"]["index"]["basal_area_map"], temps_index["basal_area_map"]
    assert (a["scale_min_m2_ha"], a["scale_max_m2_ha"]) == (b["scale_min_m2_ha"], b["scale_max_m2_ha"]), (a, b)
