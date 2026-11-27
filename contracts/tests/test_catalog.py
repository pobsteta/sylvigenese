"""Les contrats eux-mêmes sont bien formés (mission 009).

- chaque Table Schema est un Table Schema v2 valide pour frictionless, et reste dans le
  sous-ensemble que contrôle le validateur ;
- chaque JSON Schema est un schéma 2020-12 valide ;
- le profil GeoTIFF respecte son propre schéma ;
- la maille de la grille est la même dans config.schema.json et dans le profil ;
- les noms courts ne désignent qu'un contrat.
"""
import json
from pathlib import Path

import jsonschema
import pytest
from frictionless import Schema

from validator import catalog, tables
from validator.report import Refused

CONTRACTS = Path(__file__).resolve().parents[1]
TABLE_SCHEMAS = sorted((CONTRACTS / "tables").rglob("*.schema.json"))
# version du schéma par fichier quand elle n'est pas la 0.1 (summary : version 0.2, mission 051)
SCHEMA_VERSIONS = {"summary.schema.json": "0.2", "regeneration.schema.json": "0.3"}  # regeneration 0.2 : maturité en hauteur (062) ; 0.3 : stress_mortality (066)
# version du schéma JSON par fichier quand elle n'est pas la 0.1 (massif_index 0.2 : stage_models, mission 075)
JSON_SCHEMA_VERSIONS = {"massif_index.schema.json": "0.2"}
JSON_SCHEMAS = sorted((CONTRACTS / "json").glob("*.json")) + sorted(
    (CONTRACTS / "json" / "enums").glob("*.json"))


@pytest.mark.parametrize("path", TABLE_SCHEMAS, ids=lambda p: p.name)
def test_table_schema_is_valid_v2(path):
    descriptor = json.loads(path.read_text(encoding="utf-8"))
    assert descriptor["$schema"] == "https://datapackage.org/profiles/2.0/tableschema.json"
    assert descriptor["x-schema-version"] == SCHEMA_VERSIONS.get(path.name, "0.1")
    plain = {k: v for k, v in descriptor.items() if not k.startswith("x-")}
    report = Schema.validate_descriptor(plain)
    assert report.valid, [e.message for e in report.flatten(["message"])]
    tables.check_schema_supported(descriptor)


@pytest.mark.parametrize("path", JSON_SCHEMAS, ids=lambda p: p.name)
def test_json_schema_is_valid(path):
    schema = json.loads(path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    assert schema.get("x-schema-version") == JSON_SCHEMA_VERSIONS.get(path.name, "0.1")


def test_vendored_cesium_schemas_are_valid_and_licensed():
    vendor = CONTRACTS / "json" / "vendor" / "3d-tiles-1.1"
    files = sorted(vendor.rglob("*.schema.json"))
    assert len(files) == 23
    for file in files:
        jsonschema.Draft202012Validator.check_schema(json.loads(file.read_text()))
    assert "CC BY 4.0" in (vendor / "LICENCE.adoc").read_text(encoding="utf-8")
    assert (vendor / "SOURCE.md").is_file()


def test_geotiff_profile_matches_its_schema():
    profile = json.loads((CONTRACTS / "geotiff_profile.json").read_text(encoding="utf-8"))
    schema = json.loads((CONTRACTS / "geotiff_profile.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(profile, schema)


def test_grid_size_is_the_same_in_config_and_profile():
    """25 m (ADR 0001) est écrit à deux endroits : ils doivent dire la même chose."""
    config = json.loads((CONTRACTS / "json" / "config.schema.json").read_text(encoding="utf-8"))
    profile = json.loads((CONTRACTS / "geotiff_profile.json").read_text(encoding="utf-8"))
    resolution = config["properties"]["grid"]["properties"]["resolution_m"]["const"]
    assert resolution == profile["variants"]["grille"]["pixel_size_m"] == 25


def test_catalog_points_to_existing_schemas():
    for name, spec in catalog.load().items():
        assert spec["kind"] in catalog.KINDS, name
        for relative in [spec.get("schema")] + spec.get("schemas", []):
            if relative:
                assert (CONTRACTS / relative).is_file(), (name, relative)
        variant = spec.get("options", {}).get("variant")
        if spec["kind"] == "geotiff":
            assert variant in ("complet", "grille", "entree", "cog"), name


def test_aliases_are_unique_and_resolve():
    seen = {}
    for name, aliases in catalog.names().items():
        for alias in aliases:
            assert alias not in seen, f"{alias} : {seen.get(alias)} et {name}"
            assert alias not in catalog.load(), alias
            seen[alias] = name
            assert catalog.resolve(alias) == name
        assert catalog.resolve(name) == name


def test_names_of_mission_010_resolve():
    for short in ("nemeton_stands", "trees_init", "species", "config", "grid",
                  "geotiff_profile"):
        catalog.resolve(short)


def test_ambiguous_and_unknown_names_are_refused():
    with pytest.raises(Refused, match="ambigu"):
        catalog.resolve("dtm")
    with pytest.raises(Refused, match="inconnu"):
        catalog.resolve("nexiste_pas")


def test_unsupported_constraint_makes_the_contract_invalid():
    schema = {"fields": [{"name": "a", "type": "string", "constraints": {"maxLength": 3}}]}
    with pytest.raises(Refused, match="non prises en charge"):
        tables.check_schema_supported(schema)


def test_stage_enum_has_four_values():
    stage = json.loads((CONTRACTS / "json" / "enums" / "stage.json").read_text())
    assert len(stage["enum"]) == 4 and stage["provisoire"] is True
