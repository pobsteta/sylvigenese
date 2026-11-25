"""Tests d'acceptation de `contracts/validate` (mission 010, pour la mission 009).

Écrits d'après docs/spec.md §2, §3, §8, §9, l'ADR 0002 et la consigne de l'orchestrateur,
sans lire `contracts/`.

Interface :  python3 contracts/validate <contrat> <fichier>
Codes de sortie : 0 conforme, 2 entrée refusée (contrat inconnu, fichier absent),
3 non conforme. Messages en français.

Chaque fichier fautif ne diffère du fichier conforme correspondant que par UN défaut,
et le conforme est lui aussi testé : un test rouge dit donc quel défaut n'est pas vu.
"""
import os
import re
import subprocess
from pathlib import Path

import pytest

import builders as b

ROOT = Path(__file__).resolve().parents[2]
VALIDATE = ROOT / "contracts" / "validate"

OK, REFUSED, NONCONFORM = 0, 2, 3
FRENCH = re.compile(
    r"fichier|contrat|conforme|colonne|manquant|absent|inconnu|refus|invalide|attendu|"
    r"erreur|obligatoire|profil|doublon|valeur", re.I)


@pytest.fixture(autouse=True)
def validator_exists():
    # Sans ce garde, python3 renverrait lui-même le code 2 (script introuvable) et
    # les tests « entrée refusée » passeraient pour de mauvaises raisons.
    assert VALIDATE.is_file(), f"{VALIDATE} n'existe pas : mission 009 non intégrée"


def run(contract, path, env=None):
    return subprocess.run(
        ["python3", "contracts/validate", contract, str(path)],
        cwd=ROOT, capture_output=True, text=True, timeout=120, env=env)


def out(r):
    return r.stdout + r.stderr


def assert_ok(r):
    assert r.returncode == OK, f"attendu 0, reçu {r.returncode} : {out(r)}"


def assert_nonconform(r, mentions):
    """Code 3 exact, message en français sans trace Python, qui cite le défaut."""
    assert r.returncode == NONCONFORM, f"attendu 3, reçu {r.returncode} : {out(r)}"
    text = out(r)
    assert "Traceback" not in text, text
    assert FRENCH.search(text), f"message non français ou vide : {text!r}"
    assert re.search(mentions, text, re.I), f"le défaut ({mentions}) n'est pas nommé : {text!r}"


# ------------------------------------------------------------------ entrée refusée (2)

def test_unknown_contract_is_refused(tmp_path):
    f = b.write_config(tmp_path / "c.yml", b.valid_config())
    r = run("contrat_qui_nexiste_pas", f)
    assert r.returncode == REFUSED, out(r)
    assert "contrat_qui_nexiste_pas" in out(r)
    assert "Traceback" not in out(r)


@pytest.mark.parametrize("contract", ["nemeton_stands", "trees_init", "species", "config",
                                      "grid", "geotiff_profile"])
def test_missing_file_is_refused(contract, tmp_path):
    ghost = tmp_path / "absent.xyz"
    r = run(contract, ghost)
    assert r.returncode == REFUSED, out(r)
    assert "absent.xyz" in out(r)
    assert "Traceback" not in out(r)


def test_missing_arguments_are_refused():
    r = subprocess.run(["python3", "contracts/validate"], cwd=ROOT, capture_output=True,
                       text=True, timeout=60)
    assert r.returncode == REFUSED, out(r)
    assert "Traceback" not in out(r)


# Tranché : un fichier présent mais illisible donne le code 3 (le 2 est réservé au contrat
# inconnu, au fichier absent et aux arguments manquants).
@pytest.mark.parametrize("contract,name", [("trees_init", "t.parquet"), ("grid", "g.tif"),
                                           ("nemeton_stands", "s.gpkg")])
def test_garbage_file_is_rejected_cleanly(contract, name, tmp_path):
    f = tmp_path / name
    f.write_bytes(b"ceci n'est pas le bon format\x00\x01\x02" * 10)
    r = run(contract, f)
    assert r.returncode == NONCONFORM, out(r)
    assert "Traceback" not in out(r)
    assert FRENCH.search(out(r))


# ------------------------------------------------------------------- nemeton_stands

def test_stands_conform(tmp_path):
    assert_ok(run("nemeton_stands", b.write_stands_gpkg(tmp_path / "nemeton_stands.gpkg")))


@pytest.mark.parametrize("column", ["stand_id", "species_espar", "dbh_cm", "height_m",
                                    "density_ha", "age_yr", "source", "stand_id_source"])
def test_stands_missing_column(column, tmp_path):
    f = b.write_stands_gpkg(tmp_path / "s.gpkg", drop_column=column)
    assert_nonconform(run("nemeton_stands", f), column)


def test_stands_wrong_layer_name(tmp_path):
    f = b.write_stands_gpkg(tmp_path / "s.gpkg", layer="peuplements")
    assert_nonconform(run("nemeton_stands", f), r"stands|couche")


def test_stands_wrong_crs_wgs84(tmp_path):
    f = b.write_stands_gpkg(tmp_path / "s.gpkg", srs_id=4326, xy=(5.7, 45.2))
    assert_nonconform(run("nemeton_stands", f), r"2154|EPSG|projection")


def test_stands_espar_not_a_string(tmp_path):
    rows = b.good_stand_rows()
    rows[0]["species_espar"] = 9
    rows[1]["species_espar"] = 2
    f = b.write_stands_gpkg(tmp_path / "s.gpkg", rows=rows, espar_type="INTEGER")
    assert_nonconform(run("nemeton_stands", f), r"species_espar|espar")


def test_stands_espar_leading_zero_lost(tmp_path):
    # espar « 9 » au lieu de « 09 » : zéro de tête perdu (spec §8)
    rows = b.good_stand_rows()
    rows[0]["species_espar"] = "9"
    f = b.write_stands_gpkg(tmp_path / "s.gpkg", rows=rows)
    assert_nonconform(run("nemeton_stands", f), r"species_espar|espar")


def test_stands_empty_species(tmp_path):
    rows = b.good_stand_rows()
    rows[0]["species_espar"] = None
    f = b.write_stands_gpkg(tmp_path / "s.gpkg", rows=rows)
    assert_nonconform(run("nemeton_stands", f), r"species_espar|espar")


def test_stands_empty_source(tmp_path):
    # `source` est libre (dépôt externe) mais non vide
    rows = b.good_stand_rows()
    rows[0]["source"] = ""
    f = b.write_stands_gpkg(tmp_path / "s.gpkg", rows=rows)
    assert_nonconform(run("nemeton_stands", f), "source")


def test_stands_free_source_value_is_accepted(tmp_path):
    rows = b.good_stand_rows()
    rows[0]["source"] = "une_source_externe_quelconque"
    assert_ok(run("nemeton_stands", b.write_stands_gpkg(tmp_path / "s.gpkg", rows=rows)))


def test_stands_duplicate_stand_id(tmp_path):
    rows = b.good_stand_rows()
    rows[1]["stand_id"] = rows[0]["stand_id"]
    f = b.write_stands_gpkg(tmp_path / "s.gpkg", rows=rows)
    assert_nonconform(run("nemeton_stands", f), r"stand_id|doublon")


@pytest.mark.parametrize("column,value", [("dbh_cm", -5.0), ("height_m", -1.0),
                                          ("density_ha", -10.0), ("age_yr", -3)])
def test_stands_negative_value(column, value, tmp_path):
    rows = b.good_stand_rows()
    rows[0][column] = value
    f = b.write_stands_gpkg(tmp_path / "s.gpkg", rows=rows)
    assert_nonconform(run("nemeton_stands", f), column)


def test_stands_swapped_xy_does_not_land_in_france(tmp_path):
    # Piège de la Somalie : x et y inversés placent le polygone hors de l'emprise
    # du Lambert-93. Emprise tranchée par l'orchestrateur (x 100000..1300000, y 6000000..7200000).
    f = b.write_stands_gpkg(tmp_path / "s.gpkg", xy=(6500000.0, 900000.0))
    assert_nonconform(run("nemeton_stands", f), r"emprise|hors|coordonn|2154")


# --------------------------------------------------------------------- trees_init

def test_trees_conform(tmp_path):
    assert_ok(run("trees_init", b.write_trees_parquet(tmp_path / "trees_init.parquet")))


@pytest.mark.parametrize("column", ["tree_id", "x", "y", "species", "d130", "h", "crown_area",
                                    "species_source", "d130_source"])
def test_trees_missing_column(column, tmp_path):
    f = b.write_trees_parquet(tmp_path / "t.parquet", drop=[column])
    assert_nonconform(run("trees_init", f), column)


def test_trees_species_as_integer(tmp_path):
    d = b.good_trees()
    d["species"] = [9, 2, 9]
    assert_nonconform(run("trees_init", b.write_trees_parquet(tmp_path / "t.parquet", d)),
                      "species")


def test_trees_species_leading_zero_lost(tmp_path):
    d = b.good_trees()
    d["species"] = ["9", "02", "09"]
    assert_nonconform(run("trees_init", b.write_trees_parquet(tmp_path / "t.parquet", d)),
                      "species")


def test_trees_duplicate_tree_id(tmp_path):
    d = b.good_trees()
    d["tree_id"] = ["T0", "T0", "T2"]
    assert_nonconform(run("trees_init", b.write_trees_parquet(tmp_path / "t.parquet", d)),
                      r"tree_id|doublon")


@pytest.mark.parametrize("column,bad", [("d130", [28.0, -1.0, 41.2]),
                                        ("h", [22.1, 0.0 - 4.0, 27.0]),
                                        ("d130", [28.0, float("nan"), 41.2]),
                                        ("h", [22.1, None, 27.0]),
                                        ("crown_area", [14.5, 0.0, 31.25]),
                                        ("crown_area", [14.5, -3.0, 31.25]),
                                        ("crown_area", [14.5, float("nan"), 31.25]),
                                        ("crown_area", [14.5, None, 31.25])])
def test_trees_invalid_measure(column, bad, tmp_path):
    d = b.good_trees()
    d[column] = bad
    assert_nonconform(run("trees_init", b.write_trees_parquet(tmp_path / "t.parquet", d)),
                      column)


@pytest.mark.parametrize("value", ["estime", "BD_Foret", "", "NEMETON"])
def test_trees_species_source_out_of_list(value, tmp_path):
    d = b.good_trees()
    d["species_source"] = [value, "nemeton", "vegetation_type"]
    assert_nonconform(run("trees_init", b.write_trees_parquet(tmp_path / "t.parquet", d)),
                      "species_source")


@pytest.mark.parametrize("value", ["estime", "mesure", "", "TARIF_ETAGE_B"])
def test_trees_d130_source_out_of_list(value, tmp_path):
    d = b.good_trees()
    d["d130_source"] = [value, "inventaire_video", "nemeton"]
    assert_nonconform(run("trees_init", b.write_trees_parquet(tmp_path / "t.parquet", d)),
                      "d130_source")


def test_trees_all_closed_list_values_are_accepted(tmp_path):
    d = b.good_trees()
    d["species_source"] = ["nemeton", "vegetation_type", "inventaire_video"]
    d["d130_source"] = ["tarif_etage_b", "inventaire_video", "nemeton"]
    assert_ok(run("trees_init", b.write_trees_parquet(tmp_path / "t.parquet", d)))


def test_trees_d130_source_sans_coefficient_c_est_acceptee(tmp_path):
    # spec §4.3 : « tarif_etage_b » = avec houppier, « tarif_etage_b_ifn » = sans coefficient c
    d = b.good_trees()
    d["d130_source"] = ["tarif_etage_b", "tarif_etage_b_ifn", "tarif_etage_b_ifn"]
    assert_ok(run("trees_init", b.write_trees_parquet(tmp_path / "t.parquet", d)))


# Emprise du Lambert-93 métropolitain (valeurs provisoires) : x 100000..1300000,
# y 6000000..7200000.
@pytest.mark.parametrize("x,y", [(50000.0, 6500000.0), (1400000.0, 6500000.0),
                                 (900000.0, 5900000.0), (900000.0, 7300000.0)])
def test_trees_outside_lambert93_extent(x, y, tmp_path):
    d = b.good_trees()
    d["x"][0], d["y"][0] = x, y
    assert_nonconform(run("trees_init", b.write_trees_parquet(tmp_path / "t.parquet", d)),
                      r"emprise|hors|coordonn|\bx\b|\by\b")


def test_trees_swapped_xy_does_not_land_in_france(tmp_path):
    # Piège de la Somalie, version arbres. Emprise tranchée par l'orchestrateur.
    d = b.good_trees()
    d["x"], d["y"] = d["y"], d["x"]
    assert_nonconform(run("trees_init", b.write_trees_parquet(tmp_path / "t.parquet", d)),
                      r"emprise|hors|coordonn|\bx\b|\by\b")


def test_trees_file_under_wrong_contract_is_not_conform(tmp_path):
    f = b.write_trees_parquet(tmp_path / "t.parquet")
    assert run("species", f).returncode == NONCONFORM


# ----------------------------------------------------------------------- species

def test_species_conform(tmp_path):
    assert_ok(run("species", b.write_species_csv(tmp_path / "species.csv")))


def test_species_missing_espar_column(tmp_path):
    header = ["code"] + b.SPECIES_COLUMNS[1:]
    f = b.write_species_csv(tmp_path / "species.csv", header=header)
    assert_nonconform(run("species", f), "espar")


@pytest.mark.parametrize("column", b.SPECIES_COLUMNS[1:])
def test_species_missing_other_column(column, tmp_path):
    cols = [c for c in b.SPECIES_COLUMNS if c != column]
    rows = [[v for c, v in zip(b.SPECIES_COLUMNS, r) if c != column]
            for r in (b.species_row("09"), b.species_row("02", ""))]
    f = b.write_species_csv(tmp_path / "species.csv", rows=rows, header=cols)
    assert_nonconform(run("species", f), column)


def test_species_duplicate_espar(tmp_path):
    f = b.write_species_csv(tmp_path / "species.csv",
                            rows=[b.species_row("09"), b.species_row("09", "100003")])
    assert_nonconform(run("species", f), r"espar|doublon")


def test_species_espar_leading_zero_lost(tmp_path):
    f = b.write_species_csv(tmp_path / "species.csv",
                            rows=[b.species_row("9"), b.species_row("02", "100002")])
    assert_nonconform(run("species", f), "espar")


def test_species_cd_ref_not_integer(tmp_path):
    f = b.write_species_csv(tmp_path / "species.csv",
                            rows=[b.species_row("09", "pas_un_code")])
    assert_nonconform(run("species", f), r"taxref_cd_ref|cd_ref")


def test_species_cd_ref_decimal_is_refused(tmp_path):
    f = b.write_species_csv(tmp_path / "species.csv", rows=[b.species_row("09", "100001.5")])
    assert_nonconform(run("species", f), r"taxref_cd_ref|cd_ref")


def test_species_empty_table(tmp_path):
    f = b.write_species_csv(tmp_path / "species.csv", rows=[])
    assert_nonconform(run("species", f), r"vide|aucune|species|espar")


# ------------------------------------------------------------------------- config

def test_config_conform(tmp_path):
    assert_ok(run("config", b.write_config(tmp_path / "config.yml", b.valid_config())))


def test_config_yaml_syntax_error(tmp_path):
    f = tmp_path / "config.yml"
    f.write_text("grid: [25\nzone: : :\n", encoding="utf-8")
    r = run("config", f)
    assert r.returncode == NONCONFORM, out(r)
    assert "Traceback" not in out(r)
    assert FRENCH.search(out(r))


@pytest.mark.parametrize("mutate,mentions", [
    (lambda c: c["grid"].update(resolution_m=10), r"resolution_m|25|grille"),
    (lambda c: c.update(crs="EPSG:4326"), r"crs|2154"),
    (lambda c: c.update(management="thinning"), r"management|none"),
    (lambda c: c.pop("schema_version"), r"schema_version"),
    (lambda c: c.pop("grid"), r"grid"),
])
def test_config_invalid(mutate, mentions, tmp_path):
    cfg = b.valid_config()
    mutate(cfg)
    assert_nonconform(run("config", b.write_config(tmp_path / "config.yml", cfg)), mentions)


# ------------------------------------------------------------- GeoTIFF (grid, profil)

def test_geotiff_conform_float32_deflate(tmp_path):
    assert_ok(run("geotiff_profile", b.write_tiff(tmp_path / "a.tif")))


def test_geotiff_conform_uint16_predictor2(tmp_path):
    assert_ok(run("geotiff_profile", b.write_tiff(tmp_path / "a.tif", dtype="uint16", predictor=2)))


def test_geotiff_conform_uncompressed(tmp_path):
    assert_ok(run("geotiff_profile", b.write_tiff(tmp_path / "a.tif", compression=1)))


def test_grid_conform_25m(tmp_path):
    assert_ok(run("grid", b.write_tiff(tmp_path / "grid.tif", dtype="uint16")))


def test_grid_wrong_pixel_size_20m(tmp_path):
    assert_nonconform(run("grid", b.write_tiff(tmp_path / "grid.tif", pixel=20.0)),
                      r"25|maille|résolution|pixel")


@pytest.mark.parametrize("kwargs,mentions", [
    ({"predictor": 3}, r"predictor|prédicteur"),
    ({"bigtiff": True}, r"bigtiff"),
    ({"epsg": 4326}, r"2154|EPSG"),
    ({"epsg": 32631}, r"2154|EPSG"),
    ({"geokeys": False}, r"geokey|2154|EPSG|géoréf"),
    ({"nodata": None}, r"nodata|42113"),
    ({"tiled": False}, r"tuile|tile|256"),
    ({"tile": 128}, r"tuile|tile|256"),
    ({"planar": 1}, r"planar|entrelacement"),
    ({"compression": 50000}, r"compression|zstd"),
    ({"compression": 7}, r"compression|jpeg"),
    ({"dtype": "float64"}, r"float64|type|32|UInt16"),
], ids=["predictor3", "bigtiff", "epsg4326", "epsg32631", "no_geokeys", "no_nodata",
        "stripped", "tile128", "planar1", "zstd", "jpeg", "float64"])
def test_geotiff_profile_violation(kwargs, mentions, tmp_path):
    f = b.write_tiff(tmp_path / "a.tif", **kwargs)
    assert_nonconform(run("geotiff_profile", f), mentions)


@pytest.mark.parametrize("kwargs", [{"predictor": 3}, {"bigtiff": True}, {"epsg": 4326}])
def test_grid_also_enforces_profile(kwargs, tmp_path):
    # grid.tif est un GeoTIFF : le profil s'applique aussi sous le nom `grid`.
    f = b.write_tiff(tmp_path / "grid.tif", **kwargs)
    assert run("grid", f).returncode == NONCONFORM


# ----------------------------------------------------------------- hors réseau

def test_validator_works_without_network(tmp_path):
    env = dict(os.environ, HTTP_PROXY="http://127.0.0.1:9", HTTPS_PROXY="http://127.0.0.1:9",
               http_proxy="http://127.0.0.1:9", https_proxy="http://127.0.0.1:9",
               NO_PROXY="", no_proxy="")
    assert_ok(run("trees_init", b.write_trees_parquet(tmp_path / "t.parquet"), env=env))
    r = run("trees_init", b.write_trees_parquet(tmp_path / "bad.parquet",
                                               drop=["tree_id"]), env=env)
    assert r.returncode == NONCONFORM, out(r)
