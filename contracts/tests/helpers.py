"""Fabrique de fichiers d'essai pour les tests unitaires du validateur (mission 009).

Les GeoTIFF sont écrits par rasterio (GDAL), comme le feront les modules Python ; les
GeoPackage par sqlite3 ; le Parquet par pyarrow. Coordonnées en EPSG:2154, x = est,
y = nord. Le point de référence est Paris, Notre-Dame : x = 652 000, y = 6 862 000 (environ),
qui tombe dans l'emprise ; inversé, il en sort.
"""
import json
import sqlite3
import struct
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq
import rasterio
import yaml
from rasterio.transform import from_origin

PARIS_X, PARIS_Y = 652000.0, 6862000.0
ORIGIN = (900000.0, 6500000.0)


# --------------------------------------------------------------------------- GeoTIFF

def tif(path, *, dtype="float32", bands=1, size=300, pixel=25.0, origin=ORIGIN,
        crs="EPSG:2154", nodata=-9999, tiled=True, block=256, compress="deflate",
        interleave="band", bigtiff=False, driver="GTiff"):
    path = Path(path)
    options = {"compress": compress} if compress else {}
    if driver == "GTiff":
        options.update(interleave=interleave, BIGTIFF="YES" if bigtiff else "NO")
        if tiled:
            options.update(tiled=True, blockxsize=block, blockysize=block)
    else:
        options.update(blocksize=block)
    if dtype == "uint16" and nodata == -9999:
        nodata = 0
    with rasterio.open(path, "w", driver=driver, width=size, height=size, count=bands,
                       dtype=dtype, crs=crs, nodata=nodata,
                       transform=from_origin(origin[0], origin[1], pixel, pixel),
                       **options) as dst:
        dst.write(np.ones((bands, size, size), dtype=dtype))
    return path


# ------------------------------------------------------------------------ GeoPackage

def _blob(srs_id, geometry):
    kind, coords = geometry
    if kind == "POINT":
        wkb = struct.pack("<BI", 1, 1) + struct.pack("<dd", *coords)
    else:
        x, y = coords
        ring = [(x, y), (x + 100, y), (x + 100, y + 100), (x, y + 100), (x, y)]
        wkb = struct.pack("<BII", 1, 3, 1) + struct.pack("<I", len(ring))
        wkb += b"".join(struct.pack("<dd", *p) for p in ring)
    return b"GP" + bytes([0, 1]) + struct.pack("<i", srs_id) + wkb


def gpkg(path, layers, *, srs_id=2154):
    """layers : {nom: (type de géométrie, [(colonne, type SQL)], [lignes], [positions])}."""
    path = Path(path)
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    con.execute("PRAGMA application_id = 1196444487")
    con.executescript("""
        CREATE TABLE gpkg_spatial_ref_sys (srs_name TEXT, srs_id INTEGER PRIMARY KEY,
            organization TEXT, organization_coordsys_id INTEGER, definition TEXT);
        CREATE TABLE gpkg_contents (table_name TEXT PRIMARY KEY, data_type TEXT,
            identifier TEXT, srs_id INTEGER);
        CREATE TABLE gpkg_geometry_columns (table_name TEXT, column_name TEXT,
            geometry_type_name TEXT, srs_id INTEGER, z TINYINT, m TINYINT);
        INSERT INTO gpkg_spatial_ref_sys VALUES ('Lambert-93', 2154, 'EPSG', 2154, ''),
            ('WGS 84', 4326, 'EPSG', 4326, '');
    """)
    for layer, (geom_type, columns, rows, positions) in layers.items():
        con.execute("INSERT INTO gpkg_contents VALUES (?, 'features', ?, ?)",
                    (layer, layer, srs_id))
        con.execute("INSERT INTO gpkg_geometry_columns VALUES (?, 'geom', ?, ?, 0, 0)",
                    (layer, geom_type, srs_id))
        coldef = "".join(f", {n} {t}" for n, t in columns)
        con.execute(f"CREATE TABLE {layer} (fid INTEGER PRIMARY KEY, geom BLOB{coldef})")
        names = [n for n, _ in columns]
        for row, xy in zip(rows, positions):
            blob = _blob(srs_id, (geom_type, xy))
            con.execute(f"INSERT INTO {layer} (geom{''.join(', ' + n for n in names)}) "
                        f"VALUES (?{', ?' * len(names)})", [blob] + [row.get(n) for n in names])
    con.commit()
    con.close()
    return path


# ---------------------------------------------------------------- Parquet, CSV, texte

def parquet(path, columns, types=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    types = types or {}
    table = pa.table({k: pa.array(v, type=types.get(k)) for k, v in columns.items()})
    pq.write_table(table, path)
    return path


def hive(root, columns):
    """Dossier partitionné year=AAAA, convention Hive : year n'est pas dans les fichiers."""
    ds.write_dataset(pa.table(columns), root, format="parquet", partitioning=["year"],
                     partitioning_flavor="hive")
    return Path(root)


def csv(path, header, rows, sep=","):
    lines = [sep.join(header)] + [sep.join(str(v) for v in r) for r in rows]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return Path(path)


class QuotingDumper(yaml.SafeDumper):
    """PyYAML écrit `09` sans guillemets (chaîne en YAML 1.1, entier en YAML 1.2) : on
    quote toute chaîne que le contrat jugerait ambiguë."""


def _quote_ambiguous(dumper, text):
    from validator.json_docs import ambiguity
    style = '"' if ambiguity(text) else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", text, style=style)


QuotingDumper.add_representer(str, _quote_ambiguous)


def write_yaml(path, data):
    text = yaml.dump(data, Dumper=QuotingDumper, sort_keys=False, allow_unicode=True)
    Path(path).write_text(text, encoding="utf-8")
    return Path(path)


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return Path(path)


def glb(path, *, version=2, asset_version="2.0"):
    body = json.dumps({"asset": {"version": asset_version}}).encode()
    body += b" " * (-len(body) % 4)
    data = struct.pack("<III", 0x46546C67, version, 12 + 8 + len(body))
    data += struct.pack("<II", len(body), 0x4E4F534A) + body
    Path(path).write_bytes(data)
    return Path(path)


# --------------------------------------------------------------- contenus conformes

def stands_rows():
    return [
        {"stand_id": "P1", "species_espar": "09", "dbh_cm": 32.5, "height_m": 24.0,
         "density_ha": 310.0, "age_yr": 80, "source": "inventaire", "stand_id_source": "A1"},
        {"stand_id": "P2", "species_espar": "02", "dbh_cm": 41.0, "height_m": 27.5,
         "density_ha": 180.0, "age_yr": None, "source": "synthetic_ml", "stand_id_source": "A2"},
    ]


STANDS_COLUMNS = [("stand_id", "TEXT"), ("species_espar", "TEXT"), ("dbh_cm", "REAL"),
                  ("height_m", "REAL"), ("density_ha", "REAL"), ("age_yr", "INTEGER"),
                  ("source", "TEXT"), ("stand_id_source", "TEXT")]


def trees_init():
    return {"tree_id": ["T1", "T2"], "x": [PARIS_X, PARIS_X + 5],
            "y": [PARIS_Y, PARIS_Y + 5], "species": ["09", "02"], "d130": [28.0, 35.5],
            "h": [22.1, 25.4], "crown_area": [14.5, 22.0], "species_source": ["nemeton", "vegetation_type"],
            "d130_source": ["tarif_etage_b", "nemeton"]}


def parameters():
    return {"species": ["09", None], "species_group": [None, "feuillus"],
            "model": ["chapman_richards", "chapman_richards"], "term": ["a", "a"],
            "value": [1.5, 1.2], "provisoire": [True, True],
            "source": ["jeu fictif, synthétique", "jeu fictif, synthétique"]}


def dynamics_params():
    """Params de dynamics (contrat dynamics_params, mission 025) : un intercept, deux valeurs aux
    nœuds, un niveau de SER, et un groupe."""
    src = "ajusté par dynamics sur le jeu fictif, synthétique"
    return {"species": ["09", "09", "09", "09", None],
            "species_group": [None, None, None, None, "resineux"],
            "model": ["growth_gam"] * 4 + ["mortality_gam"],
            "term": ["intercept", "s(d130)[01]", "s(d130)[02]", "ser_code=H10", "intercept"],
            "variable": [None, "d130", "d130", "ser_code", None],
            "x": [None, 7.5, 60.0, None, None],
            "value": [-1.2, -0.3, 0.4, 0.05, -4.0],
            "provisoire": [True] * 5,
            "source": [src] * 5}


def sim_trees(year=2030):
    return {"tree_id": ["T1", "T2"], "year": [year, year], "species": ["09", "02"],
            "x": [PARIS_X, PARIS_X + 3], "y": [PARIS_Y, PARIS_Y + 3], "d130": [30.0, 12.0],
            "h": [25.0, 11.0], "hcb": [12.0, 4.0], "cw": [6.0, 3.0],
            "status": ["alive", "dead"]}


def sim_cells(year=2030):
    return {"cell_id": [0, 0, 1], "year": [year] * 3, "species": ["09", "02", "09"],
            "stems_ha": [300.0, 0.0, 120.0], "basal_area_m2_ha": [25.0, 0.0, 10.0],
            "d130_mean": [32.0, None, 30.0], "seedlings_ha": [1000.0, 50.0, 0.0],
            "seedling_h_mean": [0.6, 0.3, None]}


def sim_flags():
    return {"year": [2026, 2027], "entity": ["T1", "cell:12"],
            "kind": ["height_above_ceiling", "domain_output"],
            "message": ["hauteur au-dessus du plafond de la station",
                        "d130 au-dessus du dernier nœud de la spline"],
            "value": [31.2, None]}


def summary():
    """sim/summary.parquet version 0.2 : volume aérien total, carbone aérien, parts non calculées.
    Valeurs d'essai, sans sens écologique ; la colonne des racines (facultative) n'y est pas."""
    return {"cell_id": [0, 1], "year": [2030, 2030], "species": ["09", "09"],
            "volume_m3_ha": [300.0, 120.0], "biomass_t_ha": [200.0, 80.0],
            "carbon_t_ha": [100.0, 40.0], "stems_not_computed_ha": [0.0, 16.0],
            "basal_area_not_computed_share": [0.0, 0.25], "provisoire": [True, True]}


def summary_with_roots():
    """La même table avec la colonne facultative et provisoire du carbone des racines (Q4)."""
    data = summary()
    data["carbon_roots_t_ha"] = [20.0, 8.0]
    return data


def tarif():
    """params/tarif.parquet : une ligne par terme, valeurs d'essai SYNTHÉTIQUES (aucune n'est celle
    de tarif-nemeton). Une essence feuillue (volume_feuillus), une résineuse (profil_tige_resineux),
    des lignes par groupe (fraction_carbone) et le domaine (dbh_min, hd_max)."""
    rows = [
        ("09", None, "volume_feuillus", "a", 0.1, "sans_unite"),
        ("09", None, "volume_feuillus", "b", 0.2, "sans_unite"),
        ("09", None, "domaine", "dbh_min", 10.0, "cm"),
        ("62", None, "profil_tige_resineux", "synth_p1", 0.3, "sans_unite"),
        ("62", None, "domaine", "hd_max", 200.0, "sans_unite"),
        (None, "feuillu", "fraction_carbone", "fraction", 0.4, "sans_unite"),
        (None, "resineux", "fraction_carbone", "fraction", 0.45, "sans_unite"),
        (None, "resineux", "racines", "ratio", 0.2, "sans_unite"),
    ]
    return {"essence": [r[0] for r in rows], "groupe": [r[1] for r in rows],
            "modele": [r[2] for r in rows], "terme": [r[3] for r in rows],
            "valeur": [r[4] for r in rows], "unite": [r[5] for r in rows],
            "source_code": ["synthetique_jeu_fictif"] * len(rows),
            "source_biblio": ["synthetique_jeu_fictif"] * len(rows),
            "source_commit": ["0000000"] * len(rows), "provisoire": [True] * len(rows)}


TARIF_TYPES = {"essence": pa.string(), "groupe": pa.string()}


def summary_zone():
    """sim/summary_zone.parquet : deux essences d'un type de végétation, une année ; valeurs d'essai.
    forest_area_ha = 40 cellules × 0,0625 ha = 2,5 ha ; moyennes = totaux / 2,5."""
    return {"year": [2030, 2030], "vegetation_type": ["hetraie", "hetraie"],
            "species": ["09", "02"], "forest_area_ha": [2.5, 2.5],
            "volume_m3": [500.0, 50.0], "biomass_t": [300.0, 30.0], "carbon_t": [150.0, 15.0],
            "volume_m3_ha": [200.0, 20.0], "biomass_t_ha": [120.0, 12.0],
            "carbon_t_ha": [60.0, 6.0], "dead_volume_m3": [4.0, 0.0], "dead_carbon_t": [1.2, 0.0],
            "dead_stems_not_computed": [0, 3], "stems_not_computed": [10, 40],
            "basal_area_not_computed_share": [0.02, 0.5], "provisoire": [True, True]}


def post_run_json():
    """sim/post.json : provenance et comptes ; empreintes et commit d'essai."""
    return {"schema_version": 1, "run_config_sha256": "0123456789abcdef" * 4,
            "inputs_sha256": {"sim_run": "1" * 64, "sim_trees": "2" * 64,
                              "params_tarif": "3" * 64},
            "tarif_commit": "0000000",
            "models": [{"model": "volume_feuillus", "source": "synthetique_jeu_fictif",
                        "commit": "0000000", "provisoire": True},
                       {"model": "domaine", "source": "synthetique_jeu_fictif",
                        "commit": "0000000", "provisoire": True}],
            "tree_years_computed": 90000, "tree_years_not_computed": 1200,
            "out_of_domain": {"09": {"dbh_below": 800, "dbh_above": 0, "h_below": 0,
                                     "h_above": 0, "hd_below": 0, "hd_above": 300}},
            "without_tarif": {"02": 100},
            "without_vegetation_type": {"cells": [1423], "tree_years": 7},
            "provisional_share": 1.0, "duration_s": 42.5}


def config():
    return {"schema_version": 1, "zone": "zone_fictive", "crs": "EPSG:2154",
            "grid": {"resolution_m": 25}, "management": "none",
            "external": {"tarif_nemeton_dir": "/hors/depot/tarif-nemeton"},
            "simulate": {"level": "massif", "seed": 42, "t0": 2025, "years": 100,
                         "threads": 4}}


def biome():
    """Exemple du BRIEF §5, avec les essences arborées en espar et un stade de l'énumération."""
    return {"id": "hetraie_sapiniere_fraiche_acide", "provisoire": True,
            "condition": {"station": "fraiche_acide", "typopeuplement": "futaie_irreguliere",
                          "stade": "mature"},
            "strates": {"arboree": {"composition": {"61": 0.5, "09": 0.4, "62": 0.1},
                                    "tiges_ha": 320},
                        "arbustive": {"composition": {"sorbier": 0.6, "houx": 0.4},
                                      "couvert": 0.15},
                        "herbacee": {"composition": {"myrtille": 0.5, "canche": 0.3,
                                                     "fougere_aigle": 0.2}},
                        "sol": {"litiere": "aiguilles", "bois_mort_m3_ha": 25}},
            "sources": ["jeu fictif"]}


def run_json():
    return {"schema_version": 1, "level": "massif", "seed": 42, "t0": 2025, "years": 100,
            "threads": 4, "memory_estimate_bytes": 123456789, "duration_s": 12.5,
            "config_sha256": "0123456789abcdef" * 4, "zeroed_values": 0,
            "provisional_share": 0.8,
            "domain_outputs": {"d130": {"below": 0, "above": 3},
                               "ba_plot": {"below": 0, "above": 0}},
            "cells_at_height_ceiling": 7, "edge_disks": 120, "mixed_cells": 15,
            "recruits": 40, "deaths": 25}


def tileset():
    return {"asset": {"version": "1.1"}, "geometricError": 100.0,
            "root": {"boundingVolume": {"region": [0.04, 0.8, 0.05, 0.81, 0.0, 300.0]},
                     "geometricError": 0.0, "refine": "ADD",
                     "content": {"uri": "trees.glb"}}}


def gltf_json():
    """glTF 2.0 en JSON (.gltf + .bin externe), minimal et conforme au contrat assets.gltf."""
    return {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}],
            "nodes": [{"mesh": 0}], "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
            "buffers": [{"uri": "feuillu.bin", "byteLength": 36}],
            "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 36}],
            "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3"}],
            "extras": {"generique": True, "provisoire": True}}


def cell_sheet():
    return {"schema_version": 1, "tile": "t_0_0",
            "cells": [{"cell_id": 0, "x": PARIS_X, "y": PARIS_Y,
                       "station_type": "fraiche_acide", "vegetation_type": "hetraie",
                       "years": [{"year": 2030, "provisoire": True, "volume_m3_ha": 300.0,
                                  "carbon_t_ha": 100.0,
                                  "composition": [{"species": "09", "share": 1.0}]}]}]}


def massif_block():
    return {"schema_version": 1, "block_id": "b_0_0", "year": 2030, "crs": "EPSG:2154",
            "vertical_datum": "NGF-IGN69", "origin": {"x": PARIS_X, "y": PARIS_Y, "z": 35.0},
            "trees": [{"tree_id": "T1", "species": "09", "stage": "mature", "x": 1.0,
                       "y": 2.0, "z": 0.5, "h": 25.0, "d130": 30.0, "hcb": 12.0, "cw": 6.0}]}


def cell_sheet_v2():
    """Fiche de cellule v2 (mission 044) : deux années retenues, lues dans sim/, h_dom_m, flags,
    volume et carbone non calculés. Les valeurs sont celles d'un essai, sans sens écologique."""
    def year(y, stems, g, d, h_dom, flags):
        return {"year": y, "provisoire": True, "stems_ha": stems, "basal_area_m2_ha": g,
                "d130_mean_cm": d, "h_dom_m": h_dom,
                "composition": [{"species": "09", "stems_ha": stems * 0.75,
                                 "basal_area_m2_ha": g * 0.5, "share": 0.75},
                                {"species": "02", "stems_ha": stems * 0.25,
                                 "basal_area_m2_ha": g * 0.5, "share": 0.25}],
                "flags": flags, "volume_m3_ha": None, "carbon_t_ha": None}
    first = year(2022, 120.0, 20.0, 31.5, 22.0, [])
    first["h0_m"] = 21.4
    return {"schema_version": 2, "tile": "t_0_0", "source": "sim",
            "notes": ["trajectoire technique, non validée écologiquement (décision du 25/11/2026)",
                      "volume et carbone non calculés (post)", "semis non simulés"],
            "cells": [{"cell_id": 0, "x": PARIS_X, "y": PARIS_Y,
                       "station_type": "fraiche_acide", "vegetation_type": "hetraie",
                       "h_ceiling_m": 30.0,
                       "years": [first,
                                 year(2032, 200.0, 25.0, 28.0, 31.2,
                                      [{"kind": "hdom_au_dessus_du_plafond",
                                        "message": "hauteur dominante au-dessus du plafond",
                                        "value": 31.2},
                                       {"kind": "trouee_sans_recrue",
                                        "message": "trouée sans recrue", "value": None}])]}]}


def cell_sheet_v3():
    """Fiche de cellule v3 (mission 051) : deux années ; la première est complète, la seconde est
    un volume partiel (part de G non calculée) avec le carbone des racines. Valeurs d'essai."""
    def year(y, stems, g, d, h_dom, volume, carbon, share, roots=None):
        out = {"year": y, "provisoire": True, "stems_ha": stems, "basal_area_m2_ha": g,
               "d130_mean_cm": d, "h_dom_m": h_dom,
               "composition": [{"species": "09", "stems_ha": stems * 0.75,
                                "basal_area_m2_ha": g * 0.5, "share": 0.75,
                                "volume_m3_ha": volume * 0.6, "carbon_t_ha": carbon * 0.6,
                                "basal_area_not_computed_share": share},
                               {"species": "02", "stems_ha": stems * 0.25,
                                "basal_area_m2_ha": g * 0.5, "share": 0.25,
                                "volume_m3_ha": volume * 0.4, "carbon_t_ha": carbon * 0.4,
                                "basal_area_not_computed_share": 0.0}],
               "flags": [], "volume_m3_ha": volume, "carbon_t_ha": carbon,
               "stems_not_computed_ha": stems * share,
               "basal_area_not_computed_share": share, "volume_partiel": share > 0}
        if roots is not None:
            out["root_carbon_t_ha"] = roots
        return out
    return {"schema_version": 3, "tile": "t_0_0", "source": "sim",
            "tarif": {"name": "tarif NEMETON v5", "commit": "0000000", "provisoire": True},
            "notes": ["trajectoire technique, non validée écologiquement (décision du 25/11/2026)",
                      "volume aérien total (tige et branches), même définition pour toutes les essences",
                      "carbone aérien (biomasse aérienne × fraction de carbone) ; carbone des racines "
                      "à part, provisoire (racines)",
                      "sol et bois mort : non modélisés, hors v1",
                      "volume partiel : des tiges hors du domaine du tarif ne sont pas calculées"],
            "cells": [{"cell_id": 0, "x": PARIS_X, "y": PARIS_Y,
                       "station_type": "fraiche_acide", "vegetation_type": "hetraie",
                       "h_ceiling_m": 30.0,
                       "years": [year(2022, 120.0, 20.0, 31.5, 22.0, 300.0, 100.0, 0.0, 20.0),
                                 year(2032, 200.0, 25.0, 28.0, 31.2, 280.0, 90.0, 0.25, 18.0)]}]}


def tiles_index():
    """tiles/index.json en mode sim : trois années retenues (N = 10, dernière année 2045)."""
    def year(y, alive, dead):
        half = alive // 2
        return {"year": y, "instances": alive, "dead": dead, "tileset": f"{y}/tileset.json",
                "tiles": [{"tile": "t_700000_6500000", "instances": half},
                          {"tile": "t_700500_6500000", "instances": alive - half}]}
    return {"schema_version": 1, "source": "sim", "t0": 2022, "year_step": 10,
            "run_config_sha256": "0123456789abcdef" * 4, "provisoire": True,
            "notes": ["trajectoire technique, non validée écologiquement (décision du 25/11/2026)"],
            "basal_area_map": {"unit": "m2/ha", "scale_min_m2_ha": 0.0,
                               "scale_max_m2_ha": 400.0,
                               "mention": "surface terrière, non validée écologiquement"},
            "years": [year(2022, 100, 0), year(2032, 140, 12), year(2045, 160, 30)]}


def tiles_index_initial():
    """tiles/index.json sans sim/ : l'état initial seul, sans clé propre au mode sim."""
    return {"schema_version": 1, "source": "trees_init", "t0": 2022, "provisoire": True,
            "notes": ["état initial : arbres du générateur, sans simulation"],
            "years": [{"year": 2022, "instances": 100, "tileset": "2022/tileset.json",
                       "tiles": [{"tile": "t_700000_6500000", "instances": 100}]}]}


# --- contrats de M5a (mission 060)
TERMS = [("kernel_scale_m", "m"), ("kernel_shape", "1"), ("maturity_height_m", "m"),
         ("fecundity_seeds_per_m2_ba_yr", "graines/m2/an"), ("establishment_share", "1"),
         ("seedling_height_growth_m_yr", "m/an"), ("shade_tolerance", "1"),
         ("light_extinction_coef", "1"), ("seedling_survival_full_light_yr", "1"),
         ("passage_height_m", "m"), ("stress_mortality", "1/an")]


def regeneration_params():
    """Un terme par ligne pour le hêtre (09), plus un terme par groupe ; valeurs synthétiques."""
    n = len(TERMS)
    return {"species": ["09"] * n + [None],
            "species_group": [None] * n + ["toutes_essences"],
            "term": [t for t, _ in TERMS] + ["light_extinction_coef"],
            "value": [1.0] * (n + 1),
            "unit": [u for _, u in TERMS] + ["1"],
            "provisoire": [True] * (n + 1),
            "source": ["synthétique"] * (n + 1)}


REGENERATION_TYPES = {"species": pa.string(), "species_group": pa.string()}


def cohorts_init():
    return {"cell_id": [0, 0, 0, 1], "species": ["09", "09", "02", "09"], "d_class": [0, 1, 0, 0],
            "stems_ha": [120.0, 40.0, 0.0, 80.0], "source": ["synthétique"] * 4}


def sim_cohorts(year=2030):
    return {"cell_id": [0, 0, 1], "year": [year] * 3, "species": ["09", "09", "09"],
            "d_class": [0, 1, 0], "stems_ha": [120.0, 40.0, 80.0]}


