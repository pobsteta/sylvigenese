"""Règles ajoutées à la relecture 1/3 de la mission 009, et alignement sur le lecteur Rust.

- NaN et infini refusés dans les YAML et JSON (B1) ; clé YAML non chaîne refusée (B2) ;
- LZW admis en entrée seulement (I1) ; partitions Hive (I2) ; chaînes en dictionnaire ou
  string_view (I3) ; variante grille sans --grid : code 2 (I4) ; --require-outputs et
  mode --zone qui continue (I5) ; W facultative (I7) ; alluvium_code (I8) ;
- refus communs avec `simulate/src/geotiff.rs` (mission 015) : pixel « point »,
  géoréférencement par matrice, bandes de types mixtes ; et verdicts identiques sur les
  fichiers d'essai de `simulate/tests/fixtures/`.
"""
import math
import shutil
import struct
from pathlib import Path

import numpy as np
import pyarrow as pa
import pytest
import rasterio
from rasterio.transform import Affine, from_origin

import helpers as h
import test_real_files
from validator import cli

ROOT = Path(__file__).resolve().parents[2]
RUST_FIXTURES = ROOT / "simulate" / "tests" / "fixtures"


def run(capsys, argv):
    code = cli.main(argv)
    out = capsys.readouterr()
    return code, out.out + out.err


# ------------------------------------------------------------------ B1 : NaN, infini

def nan_cases(tmp):
    run_json = tmp / "run.json"
    run_json.write_text(h.write_json(tmp / "r0.json", h.run_json()).read_text()
                        .replace('"provisional_share": 0.8', '"provisional_share": NaN'))
    sheet = h.cell_sheet()
    sheet["cells"][0]["years"][0]["volume_m3_ha"] = math.nan
    block = h.massif_block()
    block["trees"][0]["h"] = math.inf
    biome_nan = h.write_yaml(tmp / "b_nan.yml", h.biome())
    biome_nan.write_text(biome_nan.read_text().replace("couvert: 0.15", "couvert: .nan"))
    biome_inf = h.write_yaml(tmp / "b_inf.yml", h.biome())
    biome_inf.write_text(biome_inf.read_text().replace("tiges_ha: 320", "tiges_ha: .inf"))
    config = h.write_yaml(tmp / "config.yml", h.config())
    config.write_text(config.read_text().replace("seed: 42", "seed: -.inf"))
    return [("run", run_json), ("cell_sheet", h.write_json(tmp / "c.json", sheet)),
            ("massif_block", h.write_json(tmp / "m.json", block)), ("biome", biome_nan),
            ("biome", biome_inf), ("config", config)]


@pytest.mark.parametrize("index", range(6))
def test_nan_and_infinity_are_refused_in_documents(index, tmp_path, capsys):
    name, path = nan_cases(tmp_path)[index]
    code, out = run(capsys, [name, str(path)])
    assert code == 3, out
    assert "NaN ou infinie" in out


# ------------------------------------------------------------ B2 : clés YAML espar

def test_unquoted_espar_keys_are_refused(tmp_path, capsys):
    path = h.write_yaml(tmp_path / "b.yml", h.biome())
    text = path.read_text(encoding="utf-8")
    start = text.index("    composition:\n", text.index("arboree"))
    end = text.index("    tiges_ha")
    path.write_text(text[:start] + "    composition: {02: 0.5, 9: 0.5}\n" + text[end:],
                    encoding="utf-8")
    code, out = run(capsys, ["biome", str(path)])
    assert code == 3, out
    assert "guillemets" in out and "02" in out


def test_quoted_espar_keys_are_accepted(tmp_path, capsys):
    path = h.write_yaml(tmp_path / "b.yml", h.biome())
    text = path.read_text(encoding="utf-8")
    start = text.index("    composition:\n", text.index("arboree"))
    end = text.index("    tiges_ha")
    path.write_text(text[:start] + '    composition: {"02": 0.5, "09": 0.5}\n' + text[end:],
                    encoding="utf-8")
    assert run(capsys, ["biome", str(path)])[0] == 0


# ------------------------------------------------------------------- I1 : LZW

def test_lzw_is_accepted_for_inputs_only(tmp_path, capsys):
    path = h.tif(tmp_path / "dtm.tif", compress="lzw", tiled=False, interleave="pixel")
    assert run(capsys, ["inputs.dtm", str(path)])[0] == 0
    code, out = run(capsys, ["geotiff_profile", str(path)])
    assert code == 3 and "LZW" in out


@pytest.mark.skipif(not test_real_files.terra_available(), reason="R ou terra absent")
def test_terra_default_settings_are_accepted_as_input(tmp_path, capsys):
    import subprocess
    script = tmp_path / "w.R"
    script.write_text("library(terra)\n"
                      "r <- rast(nrows=300, ncols=300, xmin=900000, xmax=907500, "
                      "ymin=6492500, ymax=6500000, crs='EPSG:2154')\n"
                      "values(r) <- runif(90000)\n"
                      "writeRaster(r, commandArgs(TRUE)[1], overwrite=TRUE)\n")
    path = tmp_path / "dtm.tif"
    subprocess.run(["Rscript", str(script), str(path)], check=True, capture_output=True,
                   timeout=300)
    code, out = run(capsys, ["inputs.dtm", str(path)])
    assert code == 0, out
    assert run(capsys, ["geotiff_profile", str(path)])[0] == 3


# ------------------------------------------------------------------ I2 : Hive

def test_hive_dataset_written_by_pyarrow_is_conform(tmp_path, capsys):
    data = h.sim_trees(2030)
    later = h.sim_trees(2035)
    both = {k: data[k] + later[k] for k in data}
    root = h.hive(tmp_path / "trees", both)
    assert sorted(p.name for p in root.iterdir()) == ["year=2030", "year=2035"]
    code, out = run(capsys, ["sim_trees", str(root)])
    assert code == 0, out
    assert out.count("conforme :") == 2


def test_year_repeated_in_the_file_is_refused(tmp_path, capsys):
    h.parquet(tmp_path / "cells" / "year=2030" / "p.parquet", h.sim_cells())
    code, out = run(capsys, ["sim_cells", str(tmp_path / "cells")])
    assert code == 3 and "colonne year présente" in out


# ------------------------------------------------------- I3 : types de chaînes Arrow

@pytest.mark.parametrize("kind", ["dictionary", "string_view", "large_string"])
def test_string_encodings_are_accepted(kind, tmp_path, capsys):
    data = h.trees_init()
    table = pa.table(data)
    column = table["species"].combine_chunks()
    encoded = {"dictionary": column.dictionary_encode(),
               "string_view": column.cast(pa.string_view()),
               "large_string": column.cast(pa.large_string())}[kind]
    table = table.set_column(table.column_names.index("species"), "species", encoded)
    import pyarrow.parquet as pq
    pq.write_table(table, tmp_path / "t.parquet")
    assert run(capsys, ["trees_init", str(tmp_path / "t.parquet")])[0] == 0


def test_dictionary_strings_are_still_checked(tmp_path, capsys):
    data = h.trees_init()
    data["species"] = ["9", "02"]
    table = pa.table(data)
    table = table.set_column(table.column_names.index("species"), "species",
                             table["species"].combine_chunks().dictionary_encode())
    import pyarrow.parquet as pq
    pq.write_table(table, tmp_path / "t.parquet")
    code, out = run(capsys, ["trees_init", str(tmp_path / "t.parquet")])
    assert code == 3 and "species" in out


# ---------------------------------------------------------------- I4 : --grid

def test_grille_without_grid_gives_code_2(tmp_path, capsys):
    path = h.tif(tmp_path / "h0.tif")
    code, out = run(capsys, ["h0", str(path)])
    assert code == 2 and "--grid" in out


def test_grid_option_pointing_to_nothing_gives_code_2(tmp_path, capsys):
    path = h.tif(tmp_path / "h0.tif")
    code, out = run(capsys, ["h0", str(path), "--grid", str(tmp_path / "rien.tif")])
    assert code == 2 and "absent" in out


# --------------------------------------------------------------- I5 : mode zone

def inputs_zone(tmp_path):
    import test_cli
    return test_cli.write_inputs(tmp_path / "zone")


def test_require_outputs_makes_outputs_mandatory(tmp_path, capsys):
    zone = inputs_zone(tmp_path)
    assert run(capsys, ["--zone", str(zone)])[0] == 0
    code, out = run(capsys, ["--zone", str(zone), "--require-outputs"])
    assert code == 2
    assert "grid.tif" in out and "trees_init" in out and "obligatoire absent" in out
    assert "inventaire_video" not in out  # entrée facultative, elle le reste


def test_require_outputs_needs_zone(capsys):
    assert run(capsys, ["--require-outputs", "trees_init", "x"])[0] == 2


def test_zone_goes_on_after_a_refused_file_and_3_wins(tmp_path, capsys):
    zone = inputs_zone(tmp_path)
    h.tif(zone / "h0.tif")  # grille sans grid.tif dans la zone : contrôle impossible (2)
    bad = h.trees_init()
    bad["species"] = ["9", "02"]
    h.parquet(zone / "trees_init.parquet", bad)  # non conforme (3)
    code, out = run(capsys, ["--zone", str(zone)])
    assert code == 3
    assert "h0.tif" in out and "--grid" in out and "trees_init.parquet" in out
    assert "1 impossible(s) à contrôler" in out


def test_zone_with_only_a_refused_file_gives_2(tmp_path, capsys):
    zone = inputs_zone(tmp_path)
    h.tif(zone / "h0.tif")
    assert run(capsys, ["--zone", str(zone)])[0] == 2


# ---------------------------------------------------------- I7, I8 : colonnes IFN, SER

def test_ifn_arbre_without_w_is_conform(tmp_path, capsys):
    path = h.csv(tmp_path / "ARBRE.csv", ["IDP", "ESPAR", "C13", "HTOT", "V"],
                 [["1001", "09", 950, 22.5, 0.8]], sep=";")
    assert run(capsys, ["ifn_arbre", str(path)])[0] == 0


def test_ifn_arbre_w_is_checked_when_present(tmp_path, capsys):
    path = h.csv(tmp_path / "ARBRE.csv", ["IDP", "ESPAR", "C13", "HTOT", "V", "W"],
                 [["1001", "09", 950, 22.5, 0.8, -3]], sep=";")
    code, out = run(capsys, ["ifn_arbre", str(path)])
    assert code == 3 and "W" in out


def test_alluvium_code_empty_string_is_refused(tmp_path, capsys):
    rows = [{"ser_code": "L3", "alluvium_code": ""}]
    layer = ("POLYGON", [("ser_code", "TEXT"), ("alluvium_code", "TEXT")], rows,
             [(h.PARIS_X, h.PARIS_Y)])
    path = h.gpkg(tmp_path / "ser.gpkg", {"ser": layer})
    code, out = run(capsys, ["inputs.ser", str(path)])
    assert code == 3 and "alluvium_code" in out


def test_old_alluvium_flag_is_refused(tmp_path, capsys):
    rows = [{"ser_code": "B10", "alluvium_flag": 0}]
    layer = ("POLYGON", [("ser_code", "TEXT"), ("alluvium_flag", "BOOLEAN")], rows,
             [(h.PARIS_X, h.PARIS_Y)])
    path = h.gpkg(tmp_path / "ser.gpkg", {"ser": layer})
    code, out = run(capsys, ["inputs.ser", str(path)])
    assert code == 3 and "alluvium_code" in out


# ------------------------------------------------- mêmes refus que le lecteur Rust

def test_pixel_is_point_is_refused(tmp_path, capsys):
    path = h.tif(tmp_path / "a.tif")
    with rasterio.open(path, "r+") as dst:
        dst.update_tags(AREA_OR_POINT="Point")
    for contract in ("geotiff_profile", "grid"):
        code, out = run(capsys, [contract, str(path)])
        assert code == 3 and "RasterPixelIsPoint" in out, out


def test_matrix_georeferencing_is_refused(tmp_path, capsys):
    path = tmp_path / "a.tif"
    rotated = from_origin(*h.ORIGIN, 25, 25) @ Affine.rotation(10)
    with rasterio.open(path, "w", driver="GTiff", width=300, height=300, count=1,
                       dtype="float32", crs="EPSG:2154", nodata=-9999, transform=rotated,
                       tiled=True, blockxsize=256, blockysize=256, compress="deflate",
                       interleave="band") as dst:
        dst.write(np.ones((1, 300, 300), dtype="float32"))
    code, out = run(capsys, ["geotiff_profile", str(path)])
    assert code == 3 and "34264" in out, out


def set_sample_formats(path, values):
    """Réécrit en place la balise SampleFormat (339) du premier IFD."""
    data = bytearray(Path(path).read_bytes())
    (ifd,) = struct.unpack_from("<I", data, 4)
    (count,) = struct.unpack_from("<H", data, ifd)
    for i in range(count):
        pos = ifd + 2 + 12 * i
        tag, typ, n = struct.unpack_from("<HHI", data, pos)
        if tag == 339:
            assert typ == 3 and n == len(values) and n * 2 <= 4
            struct.pack_into("<" + "H" * n, data, pos + 8, *values)
            Path(path).write_bytes(bytes(data))
            return
    raise AssertionError("balise 339 absente")


def test_mixed_band_types_are_refused(tmp_path, capsys):
    path = h.tif(tmp_path / "a.tif", bands=2)
    assert run(capsys, ["geotiff_profile", str(path)])[0] == 0
    set_sample_formats(path, [3, 1])  # Float32 puis UInt32 : types mixtes
    code, out = run(capsys, ["geotiff_profile", str(path)])
    assert code == 3 and "types différents" in out, out


RUST_FILES = sorted(RUST_FIXTURES.glob("*.tif"))


def test_rust_fixtures_are_present():
    assert RUST_FILES, f"fichiers d'essai du lecteur Rust absents de {RUST_FIXTURES}"


@pytest.mark.parametrize("path", RUST_FILES, ids=lambda p: p.name)
def test_same_verdict_as_the_rust_reader(path, tmp_path, capsys):
    """Les fichiers `refus_*` sont refusés par simulate ; les autres sont lus."""
    local = tmp_path / path.name
    shutil.copy(path, local)
    code, out = run(capsys, ["geotiff_profile", str(local)])
    assert code == (3 if path.name.startswith("refus_") else 0), out


def test_null_passes_enum_when_field_is_not_required():
    """Un champ non requis à NULL passe enum, comme les autres contraintes ; requis, non."""
    from validator import tables
    from validator.report import Findings
    field = {"name": "alluvium_code", "type": "string", "constraints": {"enum": ["L1", "L3"]}}
    schema = {"fields": [field], "fieldsMatch": "equal"}
    ok = Findings()
    tables.check_table(schema, pa.table({"alluvium_code": pa.array([None, "L3"], pa.string())}), ok)
    assert not ok, ok.errors
    field["constraints"]["required"] = True
    bad = Findings()
    tables.check_table(schema, pa.table({"alluvium_code": pa.array([None, "L3"], pa.string())}), bad)
    assert len(bad.errors) == 1 and "manquante" in bad.errors[0]


def test_regenerated_fictive_ser_is_conform(capsys):
    """Le ser.gpkg du jeu fictif (mission 013) : L3 sur le couloir d'alluvions, NULL ailleurs."""
    path = ROOT / "tests" / "fixtures" / "zone_fictive" / "inputs" / "ser.gpkg"
    code, out = run(capsys, ["inputs.ser", str(path)])
    assert code == 0, out
