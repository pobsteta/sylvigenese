"""stand_map.tif et stand_map.csv (spec §2 révisée, décision du 24/11/2026) : prepare écrit la
carte des polygones nemeton ; biomes la lit à la place de inputs/nemeton_stands.gpkg."""
import numpy as np

import helpers as H
from conftest import need


def test_make_validate_conforme_et_cite_stand_map(runs):
    p = H.validate("--zone", str(H.ZONE))
    assert p.returncode == 0, p.stderr[-1500:]
    assert "stand_map" in p.stdout, "contracts/validate ne contrôle pas stand_map (catalogue)"


def test_make_validate_target(runs):
    import subprocess
    p = subprocess.run(["make", "validate", "ZONE=zone_fictive"], cwd=H.ROOT, capture_output=True,
                       text=True, env=H.offline_env())
    assert p.returncode == 0, p.stderr[-1500:]
    assert "stand_map" in p.stdout


def test_stand_map_csv_nomme_les_cinq_polygones_par_leur_stand_id(runs):
    cats = H.read_csv_map(need("stand_map.csv"))
    assert sorted(cats.values()) == ["S01", "S02", "S03", "S04", "S05"], cats


def test_stand_map_tif_pose_chaque_polygone_a_sa_place(grid):
    cats = H.read_csv_map(need("stand_map.csv"))
    arr, nodata, *_ = H.read_raster(need("stand_map.tif"))
    arr = arr[0]
    assert arr.shape == grid.shape
    par_nom = {n: v for v, n in cats.items()}
    for s in H.read_stands():
        x0, x1, y0, y1 = (s["bbox"][0] - H.X0, s["bbox"][1] - H.X0,
                          s["bbox"][2] - H.Y0, s["bbox"][3] - H.Y0)
        m = grid.fully_in((x0, x1, y0, y1)) & grid.forest()
        assert m.sum() >= 100, s["stand_id"]
        assert set(np.unique(arr[m]).tolist()) == {par_nom[s["stand_id"]]}, s["stand_id"]
    hors = grid.fully_in(H.NO_POLYGON) & grid.forest()
    v = arr[hors]
    assert not np.isin(v, list(cats)).any(), "cellules hors polygone rattachées à un polygone"
