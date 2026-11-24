"""Règles de la relecture 3/3 de la mission 009.

- écritures YAML ambiguës en plus : séparateur `_` dans un nombre, préfixes `0b` et `0x` ;
- `ser_code` jamais L1 à L5 (les alluvions vont dans `alluvium_code`) ;
- alias YAML récursif : refusé clairement, code 3 ;
- parité avec le lecteur Rust : tuile creuse, nombre de valeurs des balises 258 et 339.
"""
import struct
from pathlib import Path

import pytest

import helpers as h
from validator import cli


def run(capsys, argv):
    code = cli.main(argv)
    out = capsys.readouterr()
    return code, out.out + out.err


def config_with(tmp_path, old, new):
    path = h.write_yaml(tmp_path / "config.yml", h.config())
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new), encoding="utf-8")
    return path


# ------------------------------------------------------------- YAML : _, 0b, 0x

@pytest.mark.parametrize("value,hint", [("1_000", "séparateur _"), ("1_000.5", "séparateur _"),
                                        ("0b101", "préfixé"), ("0x1F", "préfixé"),
                                        ("-0x1F", "préfixé")])
def test_underscore_and_prefixed_numbers_are_refused(value, hint, tmp_path, capsys):
    code, out = run(capsys, ["config", str(config_with(tmp_path, "seed: 42", f"seed: {value}"))])
    assert code == 3, out
    assert hint in out and "guillemets" in out


def test_quoted_or_word_with_underscore_is_accepted(tmp_path, capsys):
    path = config_with(tmp_path, "zone: zone_fictive", 'zone: "1_000"')
    assert run(capsys, ["config", str(path)])[0] == 0
    path = config_with(tmp_path, "zone: zone_fictive", "zone: massif_2024_b")
    assert run(capsys, ["config", str(path)])[0] == 0


# ------------------------------------------------------------- alias récursif

@pytest.mark.parametrize("text", ["a: &a [*a]\n", "a: &a {b: *a}\n"])
def test_recursive_alias_is_refused_clearly(text, tmp_path, capsys):
    path = tmp_path / "config.yml"
    path.write_text(text, encoding="utf-8")
    code, out = run(capsys, ["config", str(path)])
    assert code == 3, out
    assert "alias YAML récursif refusé" in out and "erreur interne" not in out


# ------------------------------------------------------------------ ser_code

def ser_gpkg(tmp_path, ser_code, alluvium=None):
    rows = [{"ser_code": ser_code, "alluvium_code": alluvium}]
    layer = ("POLYGON", [("ser_code", "TEXT"), ("alluvium_code", "TEXT")], rows,
             [(h.PARIS_X, h.PARIS_Y)])
    return h.gpkg(tmp_path / "ser.gpkg", {"ser": layer})


@pytest.mark.parametrize("code_ser", ["L1", "L3", "L5"])
def test_ser_code_is_never_an_alluvium_code(code_ser, tmp_path, capsys):
    code, out = run(capsys, ["inputs.ser", str(ser_gpkg(tmp_path, code_ser, code_ser))])
    assert code == 3 and "ser_code" in out and "jamais L1 à L5" in out


@pytest.mark.parametrize("code_ser", ["B10", "H10", "C20", "L6", "L10"])
def test_other_ser_codes_are_accepted(code_ser, tmp_path, capsys):
    assert run(capsys, ["inputs.ser", str(ser_gpkg(tmp_path, code_ser, "L3"))])[0] == 0


# --------------------------------------------------- parité avec le lecteur Rust

def ifd_entries(data):
    (ifd,) = struct.unpack_from("<I", data, 4)
    (count,) = struct.unpack_from("<H", data, ifd)
    for i in range(count):
        pos = ifd + 2 + 12 * i
        tag, typ, n = struct.unpack_from("<HHI", data, pos)
        yield tag, typ, n, pos


def zero_first_tile(path):
    """Début et taille de la première tuile mis à 0 : fichier « creux »."""
    data = bytearray(Path(path).read_bytes())
    for tag, typ, n, pos in ifd_entries(data):
        if tag in (324, 325):
            assert typ == 4
            target = pos + 8 if n == 1 else struct.unpack_from("<I", data, pos + 8)[0]
            struct.pack_into("<I", data, target, 0)
    Path(path).write_bytes(bytes(data))


def set_samples_per_pixel(path, value):
    data = bytearray(Path(path).read_bytes())
    for tag, typ, n, pos in ifd_entries(data):
        if tag == 277:
            struct.pack_into("<H", data, pos + 8, value)
    Path(path).write_bytes(bytes(data))


@pytest.mark.parametrize("contract", ["geotiff_profile", "grid"])
def test_sparse_tile_is_refused(contract, tmp_path, capsys):
    path = h.tif(tmp_path / "grid.tif", dtype="uint16")
    assert run(capsys, [contract, str(path)])[0] == 0
    zero_first_tile(path)
    code, out = run(capsys, [contract, str(path)])
    assert code == 3 and "creux" in out, out


@pytest.mark.parametrize("contract", ["geotiff_profile", "grid"])
def test_band_tag_counts_must_match_samples(contract, tmp_path, capsys):
    path = h.tif(tmp_path / "grid.tif", dtype="uint16")
    set_samples_per_pixel(path, 2)  # 2 bandes annoncées, une valeur dans 258 et 339
    code, out = run(capsys, [contract, str(path)])
    assert code == 3 and "balise 258" in out, out
