#!/usr/bin/env python3
"""Générateur du jeu d'essai fictif `tests/fixtures/zone_fictive/` (mission 013).

TOUT EST SYNTHÉTIQUE : aucune valeur n'est présentée comme écologique. Les formats, les noms
de colonnes et les mailles sont ceux des sources réelles (docs/spec.md §3 ; contrats de
`contracts/catalog.yml`) ; les valeurs sortent d'un générateur à compteur à graine fixée.

Usage :
    python3 tools/fixtures/make_zone_fictive.py [--out tests/fixtures/zone_fictive] [--seed 42]

Rejouable au bit près : la même graine redonne les mêmes octets (test :
`tools/fixtures/tests/test_make_zone_fictive.py`).

Coordonnées : EPSG:2154, x vers l'est, y vers le nord, en mètres. Le massif fictif est le
carré de 1 000 m de côté dont le coin sud-ouest est (X0, Y0). Les rasters partent tous du coin
nord-ouest (X0, Y0 + 1000) et couvrent au moins le massif.

Mailles (spec §3) : MNH 0,5 m ; gradients et type de station 20 m ; MNT 25 m ; h_pot 26,6 m.
"""
import argparse
import datetime
import math
import sqlite3
import struct
import sys
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import rasterio
from rasterio.crs import CRS
from rasterio.transform import Affine

# ---------------------------------------------------------------- emprise du massif fictif
X0, Y0, SIDE = 700000.0, 6500000.0, 1000.0   # coin sud-ouest et côté (provisoire)
YTOP = Y0 + SIDE
EPSG = 2154
SOURCE_PARAMS = "synthetique_jeu_fictif"
RASTER_OPTIONS = dict(driver="GTiff", INTERLEAVE="BAND", TILED="YES", BLOCKXSIZE=256,
                      BLOCKYSIZE=256, COMPRESS="DEFLATE")
FLOAT_NODATA = -9999.0
UINT_NODATA = 65535

# ---------------------------------------------------------------- aléa : générateur à compteur
# bench/SPEC.md §2 : u(seed, year, cell, sp), arithmétique modulo 2^64.
_G, _B, _D = (np.uint64(0x9E3779B97F4A7C15), np.uint64(0xBF58476D1CE4E5B9),
              np.uint64(0x94D049BB133111EB))


def u(seed, year, cell, sp):
    """Nombre dans [0, 1) ; ne dépend que de (seed, year, cell, sp), jamais de l'ordre."""
    year, cell, sp = (np.asarray(a, dtype=np.uint64) for a in (year, cell, sp))
    with np.errstate(over="ignore"):
        x = np.uint64(seed) ^ (year * _G) ^ (cell * _B) ^ (sp * _D)
        x = x + _G
        z = (x ^ (x >> np.uint64(30))) * _B
        z = (z ^ (z >> np.uint64(27))) * _D
        z = z ^ (z >> np.uint64(31))
    return (z >> np.uint64(11)).astype(np.float64) * 2.0 ** -53


# Dans ce générateur, `year` désigne le flux de tirage (une valeur par usage), `cell` l'indice
# de l'objet tiré (arbre, placette...) et `sp` le rang du tirage pour cet objet.
S_TREE_X, S_TREE_Y, S_TREE_H, S_FIELD, S_NOISE = 1, 2, 3, 4, 5
S_IFN_POS, S_IFN_BLUR, S_IFN_TREE, S_IFN_FLORA, S_PLOT = 6, 7, 8, 9, 10

# ---------------------------------------------------------------- peuplements fictifs
# (stand_id, espar, x_min, x_max, y_min, y_max en m locaux, dbh_cm, height_m, density_ha,
#  age_yr, source). Valeurs inventées pour l'essai, non écologiques.
STANDS = [
    ("S01", "09", 0, 350, 0, 500, 38.0, 27.0, 280.0, 90, "inventaire"),
    ("S02", "61", 0, 350, 500, 1000, 34.0, 28.0, 320.0, 70, "inventaire"),
    ("S03", "62", 350, 650, 500, 1000, 48.0, 36.0, 220.0, 95, "inventaire"),   # au-dessus de h_pot
    ("S04", "03", 650, 1000, 0, 500, 30.0, 22.0, 350.0, 80, "synthetic_ml"),   # MNH déjà compté
    ("S05", "64", 650, 1000, 500, 1000, 40.0, 32.0, 260.0, 55, "inventaire"),
]
# Rectangle forestier SANS polygone nemeton (spec §4.2) : x 350-650, y 0-500, 18 m, 250 /ha.
NO_STAND_RECT = (350, 650, 0, 500, 18.0, 250.0)
CLEARING = (400, 600, 100, 300)   # trouée non forestière (trou du masque forestier)
SPECIES_USED = ["09", "61", "62", "03", "64"]
TYPES = ["type_sec", "type_frais", "type_humide", "type_riche"]
CHENE_VIDEO = "chene_sessile"     # code libre nemeton cité dans entrees-externes.csv

# Paramètres synthétiques (provisoire: true, source synthetique_jeu_fictif).
# Étage B : ln D = a + b ln H + c ln CPA (D en cm, H en m, CPA = surface projetée du houppier en
# m², spec §4.3). Les trois coefficients de chaque essence sont SYNTHÉTIQUES et provisoires :
# ils ne viennent d'aucune source écologique, seulement de quoi exercer le code.
ALLOMETRY = {"09": (0.10, 1.12, 0.20), "61": (0.15, 1.10, 0.17), "62": (0.20, 1.08, 0.15),
             "03": (0.05, 1.14, 0.22), "64": (0.12, 1.10, 0.18)}
# Allométries de houppier (mission 034, contrat params/allometry, modèles hcb et cw), SYNTHÉTIQUES
# et provisoires, sans lien avec une mesure : de quoi exercer simulate, rien de plus. d130 en cm,
# comme les vraies (tarif-nemeton, vérifié par import_tarif).
#   hcb : CR = CR_a + CR_b ln(d130), borné à [CR_min ; CR_max] ; hcb = h (1 − CR).
#   cw  : cw = 2 E, ln(E) = R_a + R_b ln(d130).
# Valeurs (CR_a, CR_b, CR_min, CR_max) et (R_a, R_b) par essence du jeu fictif.
HCB = {"09": (1.10, -0.15, 0.20, 0.90), "61": (0.95, -0.08, 0.20, 0.90), "62": (0.95, -0.08, 0.20, 0.90),
       "03": (1.05, -0.13, 0.20, 0.90), "64": (0.90, -0.06, 0.20, 0.90)}
CROWN_WIDTH = {"09": (-0.30, 0.55), "61": (-0.90, 0.60), "62": (-0.90, 0.60),
               "03": (-0.60, 0.62), "64": (-0.80, 0.58)}
# Tarif (mission 051, contrat params/tarif : modèle NEMETON v5 et son domaine, colonnes essence/groupe,
# modele, terme, valeur, unite…). Toutes les valeurs sont SYNTHÉTIQUES et provisoires : inventées pour
# exercer post (recalcul exact à la main), elles ne viennent ni de tarif-nemeton ni d'aucune source.
#   volume_feuillus (feuillus 09 et 03) : ln V = ln(pi/4 D² H) + a + b ln(D/30) + c ln(H/25).
#   profil_tige_resineux et expansion_resineux (61, 62, 64) : les termes du vrai profil de tige et de
#     E(D) sont fixés par la mission 050 ; les termes synth_p1, synth_p2 et synth_E sont des
#     PLACEHOLDERS synthétiques, à remplacer quand parametres_tarif_v5.csv existera.
#   infradensite, fraction_carbone et racines : par groupe (feuillu, resineux).
#   domaine : dbh_min, dbh_max (cm), h_min, h_max (m), et hd_min, hd_max (H/D) pour les résineux.
#     Les bornes basses laissent hors domaine les recrues de 7,5 cm (comptées, non calculées).
TARIF_GROUP = {"09": "feuillu", "03": "feuillu", "61": "resineux", "62": "resineux", "64": "resineux"}
TARIF_FEUILLUS = {"09": (-0.30, 0.05, 0.10), "03": (-0.25, 0.04, 0.08)}            # a, b, c
TARIF_PROFIL = {"61": (0.40, 0.60), "62": (0.42, 0.58), "64": (0.38, 0.62)}          # synth_p1, synth_p2
TARIF_EXPANSION = {"61": 1.10, "62": 1.12, "64": 1.08}                               # synth_E
TARIF_GROUP_VALUES = {                                                              # par groupe
    "infradensite": ("kg/m3", {"feuillu": 300.0, "resineux": 350.0}),
    "fraction_carbone": ("sans_unite", {"feuillu": 0.30, "resineux": 0.35}),
    "racines": ("sans_unite", {"feuillu": 0.10, "resineux": 0.15})}
TARIF_DOMAIN = {"09": (10.0, 100.0, 3.0, 50.0), "03": (12.5, 100.0, 3.0, 50.0),
                "61": (10.0, 100.0, 3.0, 50.0), "62": (10.0, 100.0, 3.0, 50.0),
                "64": (10.0, 100.0, 3.0, 50.0)}                                     # dbh_min, dbh_max, h_min, h_max
TARIF_HD = (30.0, 200.0)                                                            # hd_min, hd_max (résineux)
TARIF_COMMIT = "0000000"    # commit synthétique : le jeu fictif ne lit aucun dépôt tarif-nemeton


# ---------------------------------------------------------------- outils d'écriture
def rect_xy(x_min, x_max, y_min, y_max):
    """Rectangle en m locaux -> (x_min, x_max, y_min, y_max) absolus."""
    return X0 + x_min, X0 + x_max, Y0 + y_min, Y0 + y_max


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def write_raster(path, bands, res, nodata, dtype, descriptions=None):
    """GeoTIFF au profil de spec §9 : EPSG:2154, tuilé 256, DEFLATE, nodata déclaré."""
    bands = [np.asarray(b) for b in bands]
    height, width = bands[0].shape
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", height=height, width=width, count=len(bands), dtype=dtype,
                       crs=CRS.from_epsg(EPSG), transform=Affine(res, 0.0, X0, 0.0, -res, YTOP),
                       nodata=nodata, **RASTER_OPTIONS) as dst:
        for i, band in enumerate(bands, start=1):
            dst.write(band.astype(dtype), i)
            if descriptions:
                dst.set_band_description(i, descriptions[i - 1])


def pixel_centres(res, size):
    """Abscisses et ordonnées (m) des centres de pixels, `size` pixels de `res` mètres."""
    cols = X0 + (np.arange(size) + 0.5) * res
    rows = YTOP - (np.arange(size) + 0.5) * res
    return np.meshgrid(cols, rows)


def smooth_field(seed, field_id, x, y, amplitude, mean):
    """Champ lisse (trois sinus à phases tirées) plus un léger bruit, en x, y absolus."""
    out = np.full(x.shape, mean, dtype=np.float64)
    for k in range(3):
        fx = 0.5 + 1.5 * float(u(seed, S_FIELD, field_id, 3 * k))
        fy = 0.5 + 1.5 * float(u(seed, S_FIELD, field_id, 3 * k + 1))
        ph = 2 * math.pi * float(u(seed, S_FIELD, field_id, 3 * k + 2))
        out += amplitude / 3 * np.sin(2 * math.pi * (fx * (x - X0) + fy * (y - Y0)) / SIDE + ph)
    idx = np.arange(x.size).reshape(x.shape)
    out += 0.02 * amplitude * (u(seed, S_NOISE, idx, field_id) - 0.5)
    return out


# ---------------------------------------------------------------- GeoPackage sans GDAL
def _wkb_polygon(rings):
    out = struct.pack("<BII", 1, 3, len(rings))
    for ring in rings:
        out += struct.pack("<I", len(ring)) + b"".join(struct.pack("<dd", x, y) for x, y in ring)
    return out


def _wkb_point(x, y):
    return struct.pack("<BIdd", 1, 1, x, y)


def _gpkg_geom(wkb, bounds):
    """En-tête GeoPackage (version 0, little-endian, enveloppe xy) + WKB."""
    x_min, y_min, x_max, y_max = bounds
    return (b"GP" + bytes([0, 0b00000011]) + struct.pack("<i", EPSG)
            + struct.pack("<dddd", x_min, x_max, y_min, y_max) + wkb)


def box_ring(x_min, x_max, y_min, y_max, hole=False):
    pts = [(x_min, y_min), (x_max, y_min), (x_max, y_max), (x_min, y_max), (x_min, y_min)]
    return pts[::-1] if hole else pts


def write_gpkg(path, layers):
    """Écrit un GeoPackage. `layers` : liste de dicts
    {name, geom_type, columns [(nom, type SQL)], rows [(wkb, bornes, valeurs...)]}."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    con.execute("PRAGMA application_id = %d" % 0x47504B47)
    con.execute("PRAGMA user_version = 10300")
    con.execute("CREATE TABLE gpkg_spatial_ref_sys (srs_name TEXT NOT NULL, srs_id INTEGER "
                "PRIMARY KEY, organization TEXT NOT NULL, organization_coordsys_id INTEGER NOT "
                "NULL, definition TEXT NOT NULL, description TEXT)")
    con.executemany("INSERT INTO gpkg_spatial_ref_sys VALUES (?,?,?,?,?,?)", [
        ("Undefined cartesian SRS", -1, "NONE", -1, "undefined", None),
        ("Undefined geographic SRS", 0, "NONE", 0, "undefined", None),
        ("RGF93 v1 / Lambert-93", EPSG, "EPSG", EPSG, CRS.from_epsg(EPSG).to_wkt(), None)])
    con.execute("CREATE TABLE gpkg_contents (table_name TEXT NOT NULL PRIMARY KEY, data_type "
                "TEXT NOT NULL, identifier TEXT UNIQUE, description TEXT DEFAULT '', "
                "last_change DATETIME NOT NULL, min_x DOUBLE, min_y DOUBLE, max_x DOUBLE, "
                "max_y DOUBLE, srs_id INTEGER)")
    con.execute("CREATE TABLE gpkg_geometry_columns (table_name TEXT NOT NULL, column_name "
                "TEXT NOT NULL, geometry_type_name TEXT NOT NULL, srs_id INTEGER NOT NULL, z "
                "TINYINT NOT NULL, m TINYINT NOT NULL, PRIMARY KEY (table_name, column_name))")
    for layer in layers:
        cols = "".join(f', "{n}" {t}' for n, t in layer["columns"])
        con.execute(f'CREATE TABLE "{layer["name"]}" (fid INTEGER PRIMARY KEY AUTOINCREMENT, '
                    f'geom BLOB{cols})')
        marks = ",".join("?" * (1 + len(layer["columns"])))
        for wkb, bounds, *values in layer["rows"]:
            con.execute(f'INSERT INTO "{layer["name"]}" VALUES (NULL,{marks})',
                        [_gpkg_geom(wkb, bounds)] + list(values))
        allb = [r[1] for r in layer["rows"]]
        con.execute("INSERT INTO gpkg_contents VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (layer["name"], "features", layer["name"], "", "2026-11-24T00:00:00.000Z",
                     min(b[0] for b in allb), min(b[1] for b in allb),
                     max(b[2] for b in allb), max(b[3] for b in allb), EPSG))
        con.execute("INSERT INTO gpkg_geometry_columns VALUES (?,?,?,?,?,?)",
                    (layer["name"], "geom", layer["geom_type"], EPSG, 0, 0))
    con.commit()
    con.close()


def polygon_row(rings, *values):
    xs = [p[0] for p in rings[0]]
    ys = [p[1] for p in rings[0]]
    return (_wkb_polygon(rings), (min(xs), min(ys), max(xs), max(ys)), *values)


def point_row(x, y, *values):
    return (_wkb_point(x, y), (x, y, x, y), *values)


# ---------------------------------------------------------------- arbres du massif (MNH)
def build_trees(seed):
    """Arbres fictifs du massif : tableau structuré (x, y absolus ; h ; rayon de houppier ;
    stand_id ; espar). Position et hauteur ne dépendent que de (seed, indice)."""
    zones = [(s[0], s[1], s[2], s[3], s[4], s[5], s[7], s[8]) for s in STANDS]
    zones.append(("R00", "", *NO_STAND_RECT))
    rows = []
    index = 0
    for stand_id, espar, xa, xb, ya, yb, height, density in zones:
        n = int(round((xb - xa) * (yb - ya) / 10000.0 * density))
        idx = np.arange(index, index + n)
        x = X0 + xa + (xb - xa) * u(seed, S_TREE_X, idx, 0)
        y = Y0 + ya + (yb - ya) * u(seed, S_TREE_Y, idx, 0)
        h = height * (0.85 + 0.30 * u(seed, S_TREE_H, idx, 0))
        keep = np.ones(n, dtype=bool)
        if stand_id == "R00":   # pas d'arbre dans la trouée
            cx0, cx1, cy0, cy1 = rect_xy(*CLEARING)
            keep = ~((x >= cx0) & (x < cx1) & (y >= cy0) & (y < cy1))
        for i in np.nonzero(keep)[0]:
            rows.append((idx[i], x[i], y[i], h[i], 0.12 * h[i] + 0.8, stand_id, espar))
        index += n
    dtype = [("id", "i8"), ("x", "f8"), ("y", "f8"), ("h", "f8"), ("r", "f8"),
             ("stand_id", "U3"), ("espar", "U5")]
    return np.array(rows, dtype=dtype)


def render_chm(trees, res=0.5):
    """MNH à `res` m : cône parabolique par arbre (maximum des houppiers), 0 hors couvert.
    Valeurs arrondies au cm."""
    size = int(SIDE / res)
    chm = np.zeros((size, size), dtype=np.float32)
    for t in trees:
        c = (t["x"] - X0) / res          # colonne fractionnaire
        r = (YTOP - t["y"]) / res        # ligne fractionnaire
        rad = t["r"] / res
        c0, c1 = max(int(c - rad) - 1, 0), min(int(c + rad) + 2, size)
        r0, r1 = max(int(r - rad) - 1, 0), min(int(r + rad) + 2, size)
        if c0 >= c1 or r0 >= r1:
            continue
        cc, rr = np.meshgrid(np.arange(c0, c1) + 0.5, np.arange(r0, r1) + 0.5)
        d2 = ((cc - c) ** 2 + (rr - r) ** 2) / rad ** 2
        crown = np.where(d2 < 1.0, t["h"] * (1.0 - d2), 0.0)
        chm[r0:r1, c0:c1] = np.maximum(chm[r0:r1, c0:c1], crown.astype(np.float32))
    return np.round(chm, 2).astype(np.float32)


# ---------------------------------------------------------------- étapes
def write_rasters(inputs, seed, trees):
    write_raster(inputs / "chm.tif", [render_chm(trees)], 0.5, FLOAT_NODATA, "float32",
                 ["chm_m"])
    # MNT 25 m (altitude NGF-IGN69, fictive)
    x, y = pixel_centres(25.0, int(SIDE / 25))
    dtm = 320.0 + 0.03 * (x - X0) + 0.02 * (y - Y0) + smooth_field(seed, 1, x, y, 20.0, 0.0)
    write_raster(inputs / "dtm.tif", [np.round(dtm, 2)], 25.0, FLOAT_NODATA, "float32",
                 ["altitude_m"])
    # gradients de station 20 m : trophic, hydric, bioclim
    x, y = pixel_centres(20.0, int(SIDE / 20))
    trophic = np.round(smooth_field(seed, 2, x, y, 2.0, 5.0), 3)
    hydric = np.round(smooth_field(seed, 3, x, y, 1.5, -1.0), 3)
    bioclim = np.round(smooth_field(seed, 4, x, y, 1.5, 0.0), 3)
    write_raster(inputs / "station_gradients.tif", [trophic, hydric, bioclim], 20.0,
                 FLOAT_NODATA, "float32", ["trophic", "hydric", "bioclim"])
    # type de station 20 m : 4 types tirés des deux premiers gradients (codes 1 à 4)
    code = 1 + (trophic > 5.0).astype(int) + 2 * (hydric > -1.0).astype(int)
    write_raster(inputs / "station_type.tif", [code], 20.0, UINT_NODATA, "uint16", ["type_id"])
    rows = []
    for i, name in enumerate(TYPES, start=1):
        m = code == i
        rows.append(f"{i};{name};{m.sum() * 0.04:.2f};{m.mean():.4f};{trophic[m].mean():.3f};"
                    f"{hydric[m].mean():.3f};{bioclim[m].mean():.3f};{int(m.sum() // 10)}")
    write_text(inputs / "types.csv",
               "id;type;area_ha;part_surface;trophic;hydric;bioclim;n_placettes\n"
               + "\n".join(rows) + "\n")
    # h_pot 26,6 m : 38 pixels couvrent 1 010,8 m, soit tout le massif
    res = 26.6
    x, y = pixel_centres(res, int(math.ceil(SIDE / res)))
    hpot = np.round(smooth_field(seed, 5, x, y, 5.0, 31.0), 2)
    write_raster(inputs / "h_pot.tif", [hpot], res, FLOAT_NODATA, "float32", ["h_pot_m"])


def write_vectors(inputs):
    stand_rows = []
    for sid, espar, xa, xb, ya, yb, dbh, h, dens, age, src in STANDS:
        ring = box_ring(*rect_xy(xa, xb, ya, yb))
        stand_rows.append(polygon_row([ring], sid, espar, dbh, h, dens, age, src, "SRC-" + sid))
    write_gpkg(inputs / "nemeton_stands.gpkg", [dict(
        name="stands", geom_type="POLYGON",
        columns=[("stand_id", "TEXT"), ("species_espar", "TEXT"), ("dbh_cm", "REAL"),
                 ("height_m", "REAL"), ("density_ha", "REAL"), ("age_yr", "INTEGER"),
                 ("source", "TEXT"), ("stand_id_source", "TEXT")], rows=stand_rows)])
    # dalles LiDAR : 2 x 2 dalles de 500 m, deux dates de vol
    tiles = []
    for xa, ya in [(0, 0), (500, 0), (0, 500), (500, 500)]:
        date = "2021-08-03" if xa == 0 else "2022-06-21"
        tiles.append(polygon_row([box_ring(*rect_xy(xa, xa + 500, ya, ya + 500))], date))
    write_gpkg(inputs / "lidar_tiles.gpkg", [dict(
        name="lidar_tiles", geom_type="POLYGON", columns=[("flight_date", "DATE")], rows=tiles)])
    # masque forestier : tout le massif sauf la trouée (trou)
    outer = box_ring(*rect_xy(0, 1000, 0, 1000))
    hole = box_ring(*rect_xy(*CLEARING), hole=True)
    write_gpkg(inputs / "forest_mask.gpkg", [dict(
        name="forest_mask", geom_type="POLYGON", columns=[],
        rows=[polygon_row([outer, hole])])])
    # SER, forme brute de l'IGN (spec §3) : H10 (code du référentiel surfaces-ser.csv) et un
    # couloir d'alluvions qui est une SER à part, L3. `prepare` lui attribue la SER voisine de
    # plus longue frontière (ici H10, des deux côtés ; spec §7). Trois polygones sans recouvrement.
    write_gpkg(inputs / "ser.gpkg", [dict(
        name="ser", geom_type="POLYGON",
        columns=[("ser_code", "TEXT")],
        rows=[polygon_row([box_ring(*rect_xy(0, 1000, 0, 420))], "H10"),
              polygon_row([box_ring(*rect_xy(0, 1000, 420, 520))], "L3"),
              polygon_row([box_ring(*rect_xy(0, 1000, 520, 1000))], "H10")])])


def d130_from_height(h, espar):
    """Étage B synthétique sans houppier : ln D = a + b ln H, coefficients a et b de ALLOMETRY
    (le d130 de l'inventaire vidéo fictif ; le terme c ln CPA n'y a pas de surface de houppier)."""
    a, b, _c = ALLOMETRY[espar]
    return math.exp(a + b * math.log(h))


def write_video(inputs, trees):
    """Inventaire vidéo (facultatif) : 3 placettes de 15 m dans le peuplement chêne S04."""
    plots, arbres = [], []
    sel = trees[trees["stand_id"] == "S04"]
    sel = sel[np.argsort(sel["id"])]
    for k, (cx, cy) in enumerate([(780.0, 100.0), (850.0, 250.0), (920.0, 400.0)], start=1):
        pid = f"P{k:02d}"
        x, y = X0 + cx, Y0 + cy
        plots.append(point_row(x, y, pid, 15.0, 7.5))
        n = 0
        for t in sel:
            if math.hypot(t["x"] - x, t["y"] - y) > 15.0:
                continue
            dbh = d130_from_height(t["h"], t["espar"])
            if dbh < 7.5:
                continue
            n += 1
            arbres.append(point_row(t["x"], t["y"], pid, f"{pid}_{n:03d}", CHENE_VIDEO,
                                    round(dbh, 1), "estime", round(float(t["h"]), 1),
                                    "mnh", "vivant"))
    write_gpkg(inputs / "inventaire_video.gpkg", [
        dict(name="placettes", geom_type="POINT",
             columns=[("plot_id", "TEXT"), ("rayon_m", "REAL"), ("seuil_diam_cm", "REAL")],
             rows=plots),
        dict(name="arbres", geom_type="POINT",
             columns=[("plot_id", "TEXT"), ("tree_id", "TEXT"), ("essence_arbre", "TEXT"),
                      ("dbh_cm", "REAL"), ("dbh_source", "TEXT"), ("h_m", "REAL"),
                      ("h_source", "TEXT"), ("statut", "TEXT")], rows=arbres)])


def write_fertilite(inputs):
    base = {"09": 24.0, "61": 25.0, "62": 24.5, "03": 20.0, "64": 28.0}
    delta = {"type_sec": -3.0, "type_frais": 0.0, "type_humide": 1.0, "type_riche": 3.0}
    lines = ["species;type;n_plots;fertilite_moy;fertilite_med;fertilite_sd;age_ref"]
    for i, sp in enumerate(SPECIES_USED):
        for j, t in enumerate(TYPES):
            moy = base[sp] + delta[t]
            lines.append(f"{sp};{t};{6 + 3 * i + j};{moy:.2f};{moy - 0.2:.2f};1.50;50")
    write_text(inputs / "fertilite.csv", "\n".join(lines) + "\n")


# --- IFN fictif : visite 1, revisite 5 ans après, valeurs SYNTHÉTIQUES et PROVISOIRES ---------
# Rien de ce qui suit n'est écologique : taux de mortalité, de coupe, croissances et recrues sont
# inventés pour que `dynamics` ait de quoi ajuster un modèle simple par essence (mission 023) ;
# ils seront remplacés par l'IFN réel en M2b. Les noms de colonnes et les codes sont ceux de
# docs/referentiels/ifn-dynamique-colonnes.csv ; C13 et IR5 sont en MÈTRES comme dans l'export.
S_IFN_FATE, S_IFN_GROW, S_IFN_RECRUIT, S_IFN_DATE, S_IFN_INDIC = 11, 12, 13, 14, 15
IFN_N_PLOTS = 120                # 120 placettes de 1re visite ; une sur dix n'est pas revisitée
IFN_MORT_5Y = {"09": 0.10, "61": 0.10, "62": 0.12, "03": 0.10, "64": 0.08}      # provisoire
IFN_GROWTH_5Y_M = {"09": 0.022, "61": 0.026, "62": 0.020, "03": 0.018, "64": 0.028}  # provisoire


# Flore fictive : 8 CD_REF d'essences de contracts/species.csv (v18) puis 10 taxons du sous-bois forestier,
# CD_REF réels de TAXREF v18 (extrait taxref_v18_extrait.csv de sylvostation, colonnes CD_REF et LB_NOM) :
IFN_UNDERSTORY = [(100787, "Hedera helix"), (128345, "Vaccinium myrtillus"), (108361, "Mercurialis perennis"),
                  (111859, "Oxalis acetosella"), (106863, "Luzula sylvatica"), (116265, "Pteridium aquilinum"),
                  (82637, "Anemone nemorosa"), (119097, "Rubus fruticosus"), (99488, "Galium odoratum"),
                  (88905, "Carex sylvatica")]
IFN_FLORA_TAXA = [97947, 79319, 113432, 116216, 89304, 125816, 116759, 139584] + [c for c, _ in IFN_UNDERSTORY]
IFN_TAXON_WITHOUT_VALUE = 125816   # reste sans valeur indicatrice : cas du comptage de prepare


def write_indicator_values(zone, seed):
    """params/indicator_values.csv (contrat params.indicator_values) : valeurs de réaction et de nutriments
    SYNTHÉTIQUES (tirées, 1 à 9), `synthetic = true`, `provisoire = true` ; aucun sens écologique. Un taxon
    reste sans valeur (vide), pour que prepare le compte."""
    lines = ["cd_ref;taxref_version;reaction;nutrients;source;synthetic;provisoire"]
    for i, cd in enumerate(sorted(IFN_FLORA_TAXA)):
        if cd == IFN_TAXON_WITHOUT_VALUE:
            continue
        rea = 1 + int(9 * float(u(seed, S_IFN_INDIC, cd, 0)))
        nut = 1 + int(9 * float(u(seed, S_IFN_INDIC, cd, 1)))
        lines.append(f"{cd};13;{rea};{nut};{SOURCE_PARAMS};true;true")
    write_text(zone / "params" / "indicator_values.csv", "\n".join(lines) + "\n")


def ifn_true_positions(seed, n_plots=IFN_N_PLOTS):
    """Positions vraies (avant flou) des placettes IFN fictives : DANS le massif (marge de 20 m), de sorte que
    le point flouté (écart <= 700 m) soit à moins de 700 m d'une maille de station et que son disque de
    700 m en recouvre (coarse_*_700m et ser_code toujours renseignés, mission 023 aller-retour 1)."""
    return [(X0 + 20 + 960 * float(u(seed, S_IFN_POS, p, 0)),
             Y0 + 20 + 960 * float(u(seed, S_IFN_POS, p, 1))) for p in range(n_plots)]


def _ifn_date(seed, camp, stream_key):
    """Date (JJ/MM/AAAA) dans la campagne `camp` : de novembre camp-1 à octobre camp."""
    day = int(364 * float(u(seed, S_IFN_DATE, stream_key, 0)))
    return (datetime.date(camp - 1, 11, 1) + datetime.timedelta(days=day)).strftime("%d/%m/%Y")


def _ifn_veget5_code(kind):
    """Code VEGET5 (unité VEGET59, campagnes 2019 et après ; toutes les 2es visites du jeu)."""
    return {"alive": "0", "cut_cleared": "6", "cut": "7", "dead": "M", "dead_windthrow": "2",
            "not_found": "N", "broken": "T"}[kind]


def _fmt(v, nd):
    return "" if v is None else f"{v:.{nd}f}"


def write_ifn(inputs, seed):
    """IFN brut fictif : 120 placettes de 1re visite (coordonnées floutées, disque de 700 m), 108
    revisitées 5 ans après (CAMPAGNE + 5), arbres revus vivants, morts, coupés, non retrouvés,
    recrues ; C13 et IR5 en mètres comme l'export réel. Poids selon le cercle de la classe de C13
    (docs/referentiels/ifn-placettes.md, bornes 0,235 / 0,705 / 1,175 m)."""
    n_plots, blur_m = IFN_N_PLOTS, 700.0
    # CD_REF : ceux de contracts/species.csv (taxref_cd_ref non vides)
    taxa = IFN_FLORA_TAXA
    plot_lines = ["CAMPAGNE;IDP;XL;YL;VISITE;DATEPOINT;NINCID;INCID;PRELEV5;DEF5;INSTP5"]
    tree_lines = ["CAMPAGNE;IDP;ESPAR;C13;A;VEGET;VEGET5;IR5;HTOT;V;W"]
    flora_lines = ["CAMPAGNE;IDP;CD_REF;ABOND"]

    def weight(c13_m):
        radius = 6.0 if c13_m < 0.705 else (9.0 if c13_m < 1.175 else 15.0)
        return 10000.0 / (math.pi * radius ** 2)

    for p, (tx, ty) in enumerate(ifn_true_positions(seed, n_plots)):
        idp = f"{9000001 + p}"
        camp = 2015 + p % 6                       # 2015 à 2020 : la 2e visite tombe de 2020 à 2025
        revisited = p % 10 != 9
        incident = p % 10 == 4                    # incident (tempête) dans les 5 ans avant la 1re visite
        clearing = p % 10 == 6                    # défrichement partiel entre les deux visites
        rho = blur_m * math.sqrt(float(u(seed, S_IFN_BLUR, p, 0)))
        ang = 2 * math.pi * float(u(seed, S_IFN_BLUR, p, 1))
        xl, yl = tx + rho * math.cos(ang), ty + rho * math.sin(ang)
        plot_lines.append(f"{camp};{idp};{xl:.1f};{yl:.1f};1;{_ifn_date(seed, camp, 2 * p)};"
                          f"{4 if incident else 0};{2 if incident else 0};;;")
        main = SPECIES_USED[int(5 * float(u(seed, S_PLOT, p, 0))) % 5]
        rows1, rows2 = [], []
        n_trees = 5 + int(10 * float(u(seed, S_PLOT, p, 1)))
        for t in range(n_trees):
            k = p * 100 + t
            sp = main if float(u(seed, S_IFN_TREE, k, 0)) < 0.75 else \
                SPECIES_USED[int(5 * float(u(seed, S_IFN_TREE, k, 1))) % 5]
            d = min(7.5 - 18.0 * math.log(1.0 - float(u(seed, S_IFN_TREE, k, 2))), 80.0)
            h = 1.3 + 32.0 * (1.0 - math.exp(-0.045 * d)) ** 1.1 * \
                (0.9 + 0.2 * float(u(seed, S_IFN_TREE, k, 3)))
            vol = 0.45 * math.pi / 4.0 * (d / 100.0) ** 2 * h        # coefficient de forme fictif
            c13 = int(round(math.pi * d * 10)) / 1000.0   # circonférence en MÈTRES (export réel)
            a = t + 1
            # état à la 1re visite : 4 % morts sur pied (5), 2 % chablis vivants (A avant 2019, 1 après)
            r_state = float(u(seed, S_IFN_FATE, k, 0))
            veget = "5" if r_state < 0.04 else (("A" if camp < 2019 else "1") if r_state < 0.06 else "0")
            # IR5 de la 1re visite (5 cernes avant la visite) sur la moitié des vivants seulement
            g_true = IFN_GROWTH_5Y_M[sp] * max(0.15, 1.0 - d / 120.0)
            ir1 = None
            if veget in ("0", "1", "A") and float(u(seed, S_IFN_GROW, k, 0)) < 0.5:
                ir1 = g_true * (0.7 + 0.6 * float(u(seed, S_IFN_GROW, k, 1)))
            rows1.append(f"{camp};{idp};{sp};{c13:.3f};{a};{veget};;{_fmt(ir1, 4)};{h:.1f};"
                         f"{vol:.4f};{weight(c13):.2f}")
            if not revisited:
                continue
            # sort à la 2e visite
            if veget != "0":
                kind = "dead" if veget == "5" else "dead_windthrow"
            else:
                p_mort = IFN_MORT_5Y[sp] * (1.0 + 2.0 * math.exp(-d / 10.0)) * (3.0 if incident else 1.0)
                p_cut = (0.06 if d >= 20.0 else 0.01) * (5.0 if clearing else 1.0)
                p_nf, p_br = 0.02, (0.08 if incident else 0.0)
                r = float(u(seed, S_IFN_FATE, k, 1))
                if r < p_mort:
                    kind = "dead"
                elif r < p_mort + p_cut:
                    kind = "cut_cleared" if float(u(seed, S_IFN_FATE, k, 2)) < 0.5 else "cut"
                elif r < p_mort + p_cut + p_nf:
                    kind = "not_found"
                elif r < p_mort + p_cut + p_nf + p_br:
                    kind = "broken"
                else:
                    kind = "alive"
            code = _ifn_veget5_code(kind)
            if kind == "alive":
                noise = 0.97 + 0.06 * float(u(seed, S_IFN_GROW, k, 2))
                c13_2 = c13 + 2.0 * math.pi * g_true * noise + \
                    0.004 * (float(u(seed, S_IFN_GROW, k, 3)) - 0.5)          # bruit de mesure
                ir2 = g_true * noise if float(u(seed, S_IFN_GROW, k, 4)) < 0.55 else None
                c13_txt = f"{c13_2:.3f}"
                w2 = weight(round(c13_2, 3))
            elif kind in ("dead", "dead_windthrow"):
                c13_txt, ir2, w2 = f"{c13:.3f}", None, weight(c13)
            else:                                 # coupé, non retrouvé, cassé : plus de C13 mesuré
                c13_txt, ir2, w2 = "", None, None
            rows2.append(f"{camp + 5};{idp};{sp};{c13_txt};{a};;{code};{_fmt(ir2, 4)};;;{_fmt(w2, 2)}")
        if revisited:
            # recrues : 2e visite sans 1re (C13 juste au-dessus du seuil 0,235 m), numéros après les anciens
            for r_i in range(int(4 * float(u(seed, S_IFN_RECRUIT, p, 0)))):
                k = p * 100 + 50 + r_i
                sp = main if float(u(seed, S_IFN_RECRUIT, k, 1)) < 0.75 else \
                    SPECIES_USED[int(5 * float(u(seed, S_IFN_RECRUIT, k, 2))) % 5]
                c13_r = 0.235 + 0.08 * float(u(seed, S_IFN_RECRUIT, k, 3)) ** 2
                ir_r = IFN_GROWTH_5Y_M[sp] * 0.8 * (0.7 + 0.6 * float(u(seed, S_IFN_RECRUIT, k, 4))) \
                    if float(u(seed, S_IFN_RECRUIT, k, 5)) < 0.5 else None
                # W de la recrue : 6 m, sauf 8 % laissées vides (poids non documenté, à signaler)
                w_r = weight(c13_r) if float(u(seed, S_IFN_RECRUIT, k, 6)) >= 0.08 else None
                rows2.append(f"{camp + 5};{idp};{sp};{c13_r:.3f};{n_trees + 1 + r_i};;0;"
                             f"{_fmt(ir_r, 4)};;;{_fmt(w_r, 2)}")
            def_5 = 2 if clearing else 0
            plot_lines.append(f"{camp + 5};{idp};{xl:.1f};{yl:.1f};2;{_ifn_date(seed, camp + 5, 2 * p + 1)};"
                              f";;;{def_5};0")
        tree_lines.extend(rows1)
        tree_lines.extend(rows2)
        seen = set()
        for j in range(4 + int(5 * float(u(seed, S_IFN_FLORA, p, 0)))):
            cd = taxa[int(len(taxa) * float(u(seed, S_IFN_FLORA, p * 100 + j, 1))) % len(taxa)]
            ab = 1 + int(3 * float(u(seed, S_IFN_FLORA, p * 100 + j, 2)))
            if cd not in seen:      # un taxon une seule fois par placette ; flore de 1re visite seule
                seen.add(cd)
                flora_lines.append(f"{camp};{idp};{cd};{ab}")
    write_text(inputs / "ifn" / "PLACETTE.csv", "\n".join(plot_lines) + "\n")
    write_text(inputs / "ifn" / "ARBRE.csv", "\n".join(tree_lines) + "\n")
    write_text(inputs / "ifn" / "FLORE.csv", "\n".join(flora_lines) + "\n")


def tarif_rows():
    """Lignes de params/tarif.parquet (contrat import_tarif.tarif), ordre fixe, valeurs synthétiques."""
    rows = []

    def add(essence, groupe, modele, terme, valeur, unite):
        rows.append(dict(essence=essence, groupe=groupe, modele=modele, terme=terme,
                         valeur=float(valeur), unite=unite, source_code=SOURCE_PARAMS,
                         source_biblio=SOURCE_PARAMS, source_commit=TARIF_COMMIT, provisoire=True))
    for sp in SPECIES_USED:
        if sp in TARIF_FEUILLUS:
            for term, v in zip(("a", "b", "c"), TARIF_FEUILLUS[sp]):
                add(sp, None, "volume_feuillus", term, v, "sans_unite")
        else:
            for term, v in zip(("synth_p1", "synth_p2"), TARIF_PROFIL[sp]):
                add(sp, None, "profil_tige_resineux", term, v, "sans_unite")
            add(sp, None, "expansion_resineux", "synth_E", TARIF_EXPANSION[sp], "sans_unite")
        terms = [("dbh_min", "cm"), ("dbh_max", "cm"), ("h_min", "m"), ("h_max", "m")]
        for (term, unit), v in zip(terms, TARIF_DOMAIN[sp]):
            add(sp, None, "domaine", term, v, unit)
        if sp not in TARIF_FEUILLUS:
            add(sp, None, "domaine", "hd_min", TARIF_HD[0], "sans_unite")
            add(sp, None, "domaine", "hd_max", TARIF_HD[1], "sans_unite")
    for modele, (unit, by_group) in TARIF_GROUP_VALUES.items():
        term = {"infradensite": "infradensite", "fraction_carbone": "fraction", "racines": "ratio"}[modele]
        for groupe in ("feuillu", "resineux"):
            add(None, groupe, modele, term, by_group[groupe], unit)
    return rows


def write_params(zone):
    """Paramètres de tarif et d'allométrie (étage B, houppier hcb et cw) : format long, provisoire: true, source synthétique."""
    schema = pa.schema([("species", pa.string()), ("species_group", pa.string()),
                        ("model", pa.string()), ("term", pa.string()), ("value", pa.float64()),
                        ("provisoire", pa.bool_()), ("source", pa.string())])
    tarif_schema = pa.schema([("essence", pa.string()), ("groupe", pa.string()),
                              ("modele", pa.string()), ("terme", pa.string()),
                              ("valeur", pa.float64()), ("unite", pa.string()),
                              ("source_code", pa.string()), ("source_biblio", pa.string()),
                              ("source_commit", pa.string()), ("provisoire", pa.bool_())])

    def table(model, coefficients, terms):
        rows = [dict(species=sp, species_group=None, model=model, term=term, value=float(v),
                     provisoire=True, source=SOURCE_PARAMS)
                for sp in SPECIES_USED for term, v in zip(terms, coefficients[sp])]
        return pa.Table.from_pylist(rows, schema=schema)

    (zone / "params").mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(tarif_rows(), schema=tarif_schema), zone / "params" / "tarif.parquet")
    # allometry.parquet : étage B, puis houppier (hcb, cw) ; un seul fichier au contrat params/allometry
    allometry = pa.concat_tables([
        table("etage_b", ALLOMETRY, ("a", "b", "c")),
        table("hcb", HCB, ("CR_a", "CR_b", "CR_min", "CR_max")),
        table("cw", CROWN_WIDTH, ("R_a", "R_b")),
    ])
    pq.write_table(allometry, zone / "params" / "allometry.parquet")


def write_zone_marker(zone):
    """Marqueur versionné (contrat zone_marker) : le jeu est fictif, ses copies le restent.

    Lu par `assets` : seule une zone marquée fictive peut se passer de la grille RAF20.
    """
    write_text(zone / "zone.yml",
               "schema_version: 1\nfictive: true\n"
               "reason: jeu d'essai synthétique (coordonnées et valeurs inventées, aucune source réelle)\n")


def generate(out_dir, seed=42):
    zone = Path(out_dir)
    inputs = zone / "inputs"
    trees = build_trees(seed)
    write_rasters(inputs, seed, trees)
    write_vectors(inputs)
    write_video(inputs, trees)
    write_fertilite(inputs)
    write_ifn(inputs, seed)
    write_params(zone)
    write_indicator_values(zone, seed)
    write_zone_marker(zone)
    return zone


def main(argv=None):
    p = argparse.ArgumentParser(description="Génère le jeu d'essai fictif (tout est synthétique).")
    p.add_argument("--out", default="tests/fixtures/zone_fictive")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args(argv)
    zone = generate(args.out, args.seed)
    print(f"jeu fictif écrit sous {zone} (graine {args.seed})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
