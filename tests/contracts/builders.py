"""Fabrique de fichiers d'essai, conformes ou fautifs, pour `contracts/validate`.

Tout est écrit en Python pur (struct, sqlite3, pyarrow, numpy) : ni GDAL, ni rasterio,
ni terra. Source des formats : docs/spec.md §3 (entrées), §8 (espar en chaîne), §9
(profil GeoTIFF), BRIEF §4 (colonnes de trees_init).

Colonnes de `species.csv` : fixées par la mission 011. Clés de `config.yml` : proposition
retenue par l'orchestrateur (valid_config()).
"""
import sqlite3
import struct
import zlib
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

# --------------------------------------------------------------------------- GeoTIFF

ORIGIN_X, ORIGIN_Y = 900000.0, 6500000.0  # Lambert-93, en France métropolitaine


def write_tiff(
    path,
    *,
    dtype="float32",
    size=512,
    bigtiff=False,
    tiled=True,
    tile=256,
    planar=2,
    compression=8,  # 1 aucune, 8 Deflate, 7 JPEG, 50000 ZSTD
    predictor=1,
    epsg=2154,
    nodata="-9999",
    geokeys=True,
    pixel=25.0,
):
    """Écrit un GeoTIFF mono-bande minimal. Chaque option fautive est isolée.

    Pour JPEG et ZSTD seule la balise est posée (les octets ne sont pas compressés) :
    le validateur lit les balises, pas les pixels.
    """
    path = Path(path)
    if dtype == "float32":
        arr = (np.arange(size * size, dtype="<f4").reshape(size, size) % 97).astype("<f4")
        bps, fmt = 32, 3
    elif dtype == "uint16":
        arr = (np.arange(size * size, dtype=np.uint32).reshape(size, size) % 251).astype("<u2")
        bps, fmt = 16, 1
    elif dtype == "float64":
        arr = (np.arange(size * size, dtype="<f8").reshape(size, size) % 97).astype("<f8")
        bps, fmt = 64, 3
    else:
        raise ValueError(dtype)

    def pack(a):
        if predictor == 2 and dtype == "uint16":
            d = a.copy()
            d[:, 1:] = (a[:, 1:] - a[:, :-1]).astype("<u2")
            a = d
        raw = a.tobytes()
        return zlib.compress(raw) if compression == 8 else raw

    blocks = []
    if tiled:
        for ty in range(0, size, tile):
            for tx in range(0, size, tile):
                sub = np.zeros((tile, tile), dtype=arr.dtype)
                piece = arr[ty:ty + tile, tx:tx + tile]
                sub[: piece.shape[0], : piece.shape[1]] = piece
                blocks.append(pack(sub))
    else:
        for ty in range(0, size, 64):
            blocks.append(pack(arr[ty:ty + 64, :]))

    big = bigtiff
    off_fmt, off_type = ("<Q", 16) if big else ("<I", 4)
    inline = 8 if big else 4
    buf = bytearray()
    if big:
        buf += b"II" + struct.pack("<HHHQ", 43, 8, 0, 0)
    else:
        buf += b"II" + struct.pack("<HI", 42, 0)
    offsets, counts = [], []
    for b in blocks:
        offsets.append(len(buf))
        counts.append(len(b))
        buf += b

    entries = []  # (tag, type, count, bytes)
    fmts = {1: "B", 3: "H", 4: "I", 12: "d", 16: "Q"}

    def add(tag, typ, values):
        if typ == 2:
            data = values.encode("ascii") + b"\0"
            entries.append((tag, typ, len(data), data))
        else:
            data = struct.pack("<" + fmts[typ] * len(values), *values)
            entries.append((tag, typ, len(values), data))

    add(256, 4, [size])
    add(257, 4, [size])
    add(258, 3, [bps])
    add(259, 3, [compression])
    add(262, 3, [1])
    add(277, 3, [1])
    add(284, 3, [planar])
    add(317, 3, [predictor])
    if tiled:
        add(322, 4, [tile])
        add(323, 4, [tile])
        add(324, off_type, offsets)
        add(325, off_type, counts)
    else:
        add(273, off_type, offsets)
        add(278, 4, [64])
        add(279, off_type, counts)
    add(339, 3, [fmt])
    add(33550, 12, [pixel, pixel, 0.0])
    add(33922, 12, [0.0, 0.0, 0.0, ORIGIN_X, ORIGIN_Y, 0.0])
    if geokeys:
        add(34735, 3, [1, 1, 0, 3, 1024, 0, 1, 1, 1025, 0, 1, 1, 3072, 0, 1, epsg])
    if nodata is not None:
        add(42113, 2, nodata)
    entries.sort(key=lambda e: e[0])

    packed = []
    for tag, typ, count, data in entries:
        if len(data) <= inline:
            packed.append((tag, typ, count, data.ljust(inline, b"\0")))
        else:
            if len(buf) % 2:
                buf += b"\0"
            packed.append((tag, typ, count, struct.pack(off_fmt, len(buf))))
            buf += data
    if len(buf) % 2:
        buf += b"\0"
    ifd_pos = len(buf)
    if big:
        buf += struct.pack("<Q", len(packed))
        for tag, typ, count, val in packed:
            buf += struct.pack("<HHQ", tag, typ, count) + val
        buf += struct.pack("<Q", 0)
        buf[8:16] = struct.pack("<Q", ifd_pos)
    else:
        buf += struct.pack("<H", len(packed))
        for tag, typ, count, val in packed:
            buf += struct.pack("<HHI", tag, typ, count) + val
        buf += struct.pack("<I", 0)
        buf[4:8] = struct.pack("<I", ifd_pos)
    path.write_bytes(bytes(buf))
    return path


# ------------------------------------------------------------------ GeoPackage (stands)

STANDS_COLUMNS = [
    ("stand_id", "TEXT"),
    ("species_espar", "TEXT"),
    ("dbh_cm", "REAL"),
    ("height_m", "REAL"),
    ("density_ha", "REAL"),
    ("age_yr", "INTEGER"),
    ("source", "TEXT"),
    ("stand_id_source", "TEXT"),
]


def _polygon_blob(srs_id, x0, y0, size=100.0):
    ring = [(x0, y0), (x0 + size, y0), (x0 + size, y0 + size), (x0, y0 + size), (x0, y0)]
    wkb = struct.pack("<BII", 1, 3, 1) + struct.pack("<I", len(ring))
    for x, y in ring:
        wkb += struct.pack("<dd", x, y)
    return b"GP" + bytes([0, 1]) + struct.pack("<i", srs_id) + wkb


def good_stand_rows():
    return [
        {"stand_id": "P1", "species_espar": "09", "dbh_cm": 32.5, "height_m": 24.0,
         "density_ha": 310.0, "age_yr": 80, "source": "inventaire", "stand_id_source": "A-1"},
        {"stand_id": "P2", "species_espar": "02", "dbh_cm": 41.0, "height_m": 27.5,
         "density_ha": 180.0, "age_yr": 110, "source": "synthetic_ml", "stand_id_source": "A-2"},
    ]


def write_stands_gpkg(path, rows=None, *, layer="stands", srs_id=2154, drop_column=None,
                      espar_type="TEXT", xy=(900000.0, 6500000.0)):
    path = Path(path)
    if path.exists():
        path.unlink()
    rows = good_stand_rows() if rows is None else rows
    cols = [(n, espar_type if n == "species_espar" else t) for n, t in STANDS_COLUMNS
            if n != drop_column]
    con = sqlite3.connect(path)
    con.execute("PRAGMA application_id = 1196444487")
    con.execute("PRAGMA user_version = 10300")
    con.executescript("""
        CREATE TABLE gpkg_spatial_ref_sys (srs_name TEXT NOT NULL, srs_id INTEGER PRIMARY KEY,
            organization TEXT NOT NULL, organization_coordsys_id INTEGER NOT NULL,
            definition TEXT NOT NULL, description TEXT);
        CREATE TABLE gpkg_contents (table_name TEXT PRIMARY KEY, data_type TEXT NOT NULL,
            identifier TEXT, description TEXT DEFAULT '', last_change DATETIME NOT NULL
            DEFAULT '2026-11-24T00:00:00.000Z', min_x DOUBLE, min_y DOUBLE, max_x DOUBLE,
            max_y DOUBLE, srs_id INTEGER);
        CREATE TABLE gpkg_geometry_columns (table_name TEXT NOT NULL, column_name TEXT NOT NULL,
            geometry_type_name TEXT NOT NULL, srs_id INTEGER NOT NULL, z TINYINT NOT NULL,
            m TINYINT NOT NULL);
    """)
    con.execute("INSERT INTO gpkg_spatial_ref_sys VALUES "
                "('Undefined cartesian',-1,'NONE',-1,'undefined',NULL),"
                "('Undefined geographic',0,'NONE',0,'undefined',NULL),"
                "('WGS 84',4326,'EPSG',4326,'GEOGCS[\"WGS 84\"]',NULL),"
                "('RGF93 / Lambert-93',2154,'EPSG',2154,'PROJCS[\"RGF93 / Lambert-93\"]',NULL)")
    con.execute("INSERT INTO gpkg_contents (table_name,data_type,identifier,srs_id) "
                "VALUES (?, 'features', ?, ?)", (layer, layer, srs_id))
    con.execute("INSERT INTO gpkg_geometry_columns VALUES (?, 'geom', 'POLYGON', ?, 0, 0)",
                (layer, srs_id))
    coldef = ", ".join(f"{n} {t}" for n, t in cols)
    con.execute(f"CREATE TABLE {layer} (fid INTEGER PRIMARY KEY AUTOINCREMENT, geom BLOB, {coldef})")
    for i, r in enumerate(rows):
        vals = [r.get(n) for n, _ in cols]
        con.execute(
            f"INSERT INTO {layer} (geom,{','.join(n for n, _ in cols)}) "
            f"VALUES (?,{','.join('?' * len(cols))})",
            [_polygon_blob(srs_id, xy[0] + 200.0 * i, xy[1])] + vals)
    con.commit()
    con.close()
    return path


# ------------------------------------------------------------------------- trees_init

def good_trees():
    n = 3
    return {
        "tree_id": [f"T{i}" for i in range(n)],
        "x": [900010.0 + 5 * i for i in range(n)],
        "y": [6500010.0 + 5 * i for i in range(n)],
        "species": ["09", "02", "09"],
        "d130": [28.0, 35.5, 41.2],
        "h": [22.1, 25.4, 27.0],
        "species_source": ["vegetation_type"] * n,
        "d130_source": ["tarif_etage_b"] * n,
    }


def write_trees_parquet(path, data=None, *, drop=()):
    data = dict(good_trees() if data is None else data)
    for c in drop:
        data.pop(c)
    pq.write_table(pa.table({k: pa.array(v) for k, v in data.items()}), str(path))
    return Path(path)


# --------------------------------------------------------------------------- species

SPECIES_COLUMNS = ["espar", "latin", "taxref_cd_ref", "taxref_version", "nemeton_code",
                   "tarif_nemeton_code", "groupe", "source", "ecart"]  # mission 011


def species_row(espar="09", cd_ref="100001", **kw):
    row = {"espar": espar, "latin": "Fagus sylvatica", "taxref_cd_ref": cd_ref,
           "taxref_version": "18", "nemeton_code": "hetre", "tarif_nemeton_code": "hetre",
           "groupe": "feuillus", "source": "essai", "ecart": ""}
    row.update(kw)
    return [row[c] for c in SPECIES_COLUMNS]


def write_species_csv(path, rows=None, *, header=None):
    rows = rows if rows is not None else [
        species_row("09", "100001"),
        species_row("02", "", latin="Quercus petraea"),  # cd_ref vide : permis
    ]
    header = header or SPECIES_COLUMNS
    lines = [",".join(header)] + [",".join(r) for r in rows]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return Path(path)


# ---------------------------------------------------------------------------- config

def valid_config():
    """HYPOTHESE : seules les clés que la spec nomme (grille 25 m, EPSG:2154,
    management: none, external.tarif_nemeton_dir) sont utilisées."""
    return {
        "schema_version": 1,
        "zone": "zone_fictive",
        "crs": "EPSG:2154",
        "grid": {"resolution_m": 25},
        "management": "none",
        "external": {"tarif_nemeton_dir": "/chemin/hors/depot/tarif-nemeton"},
    }


def write_config(path, cfg):
    import yaml
    Path(path).write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True),
                          encoding="utf-8")
    return Path(path)
