"""Rasters web en COG (spec §9 : « COG avec aperçus » ; contrat assets.web_raster, variante cog)."""
import numpy as np
import pytest
import rasterio

import helpers_m4 as H


@pytest.fixture(scope="module")
def tifs(chaine):
    t = sorted((H.ZONE / "web" / "rasters").glob("*.tif"))
    assert t, "aucun raster web/rasters/*.tif"
    return t


def test_la_carte_des_types_de_vegetation_est_en_web_rasters(chaine):
    assert (H.ZONE / "web" / "rasters" / "vegetation_map.tif").is_file(), "web/rasters/vegetation_map.tif absent"


def test_chaque_raster_a_des_apercus_est_en_tuiles_et_en_2154(tifs):
    for p in tifs:
        with rasterio.open(p) as r:
            assert r.driver == "GTiff"
            assert r.crs is not None and r.crs.to_epsg() == 2154, f"{p.name} : crs {r.crs}"
            assert r.profile.get("tiled"), f"{p.name} : pas organisé en tuiles"
            assert r.overviews(1), f"{p.name} : aucun aperçu (COG avec aperçus, spec §9)"
            assert r.nodata is not None, f"{p.name} : nodata absent"


def test_les_cellules_sont_alignees_sur_grid_tif(tifs):
    with rasterio.open(H.ZONE / "grid.tif") as g:
        for p in tifs:
            with rasterio.open(p) as r:
                assert abs(r.transform.a - g.transform.a) < 1e-9, f"{p.name} : maille {r.transform.a} m"
                assert abs(r.transform.c - g.transform.c) < 1e-6 and abs(r.transform.f - g.transform.f) < 1e-6, \
                    f"{p.name} : origine ({r.transform.c}, {r.transform.f}) != grid.tif"
                assert (r.width, r.height) == (g.width, g.height)


def test_vegetation_map_en_cog_a_les_memes_valeurs_que_vegetation_map_tif(chaine):
    # Pas de ré-échantillonnage ni de décalage : une catégorie reste une catégorie (spec §7, mode, pas bilinéaire).
    a, nd_a, _, _ = H.read_raster(H.ZONE / "vegetation_map.tif")
    b, nd_b, _, _ = H.read_raster(H.ZONE / "web" / "rasters" / "vegetation_map.tif")
    assert nd_a == nd_b
    assert np.array_equal(a, b), f"{int((a != b).sum())} cellules différentes de vegetation_map.tif"


def test_un_raster_web_ne_fabrique_pas_de_categorie(tifs, oracle):
    p = H.ZONE / "web" / "rasters" / "vegetation_map.tif"
    a, nd, _, _ = H.read_raster(p)
    assert {int(v) for v in np.unique(a) if v != nd} <= set(oracle.veg_names), "code de type de végétation hors vegetation_map.csv"
