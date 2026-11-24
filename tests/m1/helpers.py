"""Outils communs des tests d'acceptation M1a (mission 021).

Ces tests partent de la spec (docs/spec.md), de contracts/README.md et du README du jeu
fictif ; ils ne lisent pas le code de prepare ni de biomes. Rien ici ne saute un test :
une sortie absente est un échec, jamais un « skip » (le script de CI refuse tout test sauté).
"""
from __future__ import annotations

import datetime
import math
import os
import re
import shutil
import sqlite3
import struct
import subprocess
from pathlib import Path

import numpy as np
import pyarrow.dataset as pds
import rasterio

ROOT = Path(__file__).resolve().parents[2]
ZONE = ROOT / "tests" / "fixtures" / "zone_fictive"
INPUTS = ZONE / "inputs"
VALIDATE = ROOT / "contracts" / "validate"

# Massif fictif (tests/fixtures/zone_fictive/README.md) : carré de 1 000 m, coin sud-ouest.
X0, Y0, SIDE = 700_000.0, 6_500_000.0, 1_000.0
# Trouée non forestière, en mètres locaux (README du jeu fictif).
GAP = (400.0, 600.0, 100.0, 300.0)  # x0, x1, y0, y1
# Zone sans polygone nemeton, en mètres locaux (README) : x 350-650, y 0-500.
NO_POLYGON = (350.0, 650.0, 0.0, 500.0)

# R_LOAD du Makefile (cible prepare/biomes) : même appel, pour lire le vrai code de sortie.
R_LOAD = 'for (f in list.files("R", pattern = "[.]R$", full.names = TRUE)) source(f)'

# Sorties de M1a, aux chemins de contracts/catalog.yml (sous tests/fixtures/zone_fictive/).
OUTPUT_FILES = [
    "grid.tif", "dtm.tif", "forest_mask.tif", "ser.tif", "ser.csv", "h0.tif", "chm_date.tif",
    "station_gradients.tif", "station_type.tif", "station_type.csv", "site_potential.tif",
    "site_potential.csv", "stands.parquet", "vegetation_map.tif", "vegetation_map.csv",
    "rapport_biomes.html", "rapport_prepare.html", "rapport_arbres.html",
    "stand_map.tif", "stand_map.csv", "ifn/plots.parquet", "ifn/trees.parquet", "ifn/flora.parquet",
]
OUTPUT_DIRS = ["trees_init"]

L_CODE = re.compile(r"^L[1-5]$")


def offline_env() -> dict:
    """Environnement sans réseau : proxys morts (cas terrain « absence de réseau »)."""
    env = dict(os.environ)
    dead = "http://127.0.0.1:9"
    for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "all_proxy"):
        env[k] = dead
    env.pop("NO_PROXY", None)
    env.pop("no_proxy", None)
    return env


def clean_outputs(zone_dir: Path) -> None:
    """Efface les sorties attendues (jamais les entrées) pour qu'aucune sortie périmée ne passe."""
    for rel in OUTPUT_FILES:
        p = zone_dir / rel
        if p.is_file():
            p.unlink()
    for rel in OUTPUT_DIRS:
        p = zone_dir / rel
        if p.is_dir():
            shutil.rmtree(p)
        elif p.is_file():
            p.unlink()
    pq = zone_dir / "trees_init.parquet"
    if pq.is_file():
        pq.unlink()


def run_make(target: str, zone: str = "zone_fictive", config: Path | None = None,
             timeout: int = 1800, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    cmd = ["make", target, f"ZONE={zone}"]
    if config is not None:
        cmd.append(f"CONFIG={config}")
    env = offline_env()
    env.update(env_extra or {})
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, env=env,
                          timeout=timeout)


def run_module_status(module: str, config: Path, timeout: int = 1800) -> subprocess.CompletedProcess:
    """Appelle run_<module>() comme le Makefile, pour lire son code de sortie exact
    (make renvoie toujours 2 en cas d'échec : il masque les codes 2, 3 et 4 de la spec §6)."""
    expr = f'{R_LOAD}; quit(status = run_{module}("{config}"))'
    return subprocess.run(["Rscript", "-e", expr], cwd=ROOT, capture_output=True, text=True,
                          env=offline_env(), timeout=timeout)


def validate(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["python3", str(VALIDATE), *args], cwd=ROOT, capture_output=True,
                          text=True)


# ------------------------------------------------------------------ GeoPackage sans GDAL
def _rect_blob(minx, maxx, miny, maxy, srid=2154) -> bytes:
    header = b"GP" + bytes([0, 0b00000011]) + struct.pack("<i", srid)
    header += struct.pack("<4d", minx, maxx, miny, maxy)
    pts = [(minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy), (minx, miny)]
    wkb = struct.pack("<BII", 1, 3, 1) + struct.pack("<I", 5)
    for x, y in pts:
        wkb += struct.pack("<2d", x, y)
    return header + wkb


def gpkg_bbox(blob: bytes) -> tuple[float, float, float, float]:
    """(xmin, xmax, ymin, ymax) lu dans l'enveloppe d'un blob GeoPackage (polygones rectangulaires
    du jeu fictif)."""
    return struct.unpack("<4d", blob[8:40])


def read_stands() -> list[dict]:
    c = sqlite3.connect(INPUTS / "nemeton_stands.gpkg")
    rows = []
    for sid, esp, dbh, h, dens, age, src, sid_src, geom in c.execute(
            "select stand_id, species_espar, dbh_cm, height_m, density_ha, age_yr, source, "
            "stand_id_source, geom from stands order by stand_id"):
        rows.append(dict(stand_id=sid, species=esp, dbh_cm=dbh, height_m=h, density_ha=dens,
                         age_yr=age, source=src, stand_id_source=sid_src, bbox=gpkg_bbox(geom)))
    c.close()
    return rows


def read_lidar_tiles() -> list[dict]:
    c = sqlite3.connect(INPUTS / "lidar_tiles.gpkg")
    rows = [dict(flight_date=d, bbox=gpkg_bbox(g))
            for d, g in c.execute("select flight_date, geom from lidar_tiles")]
    c.close()
    return rows


def days_since_epoch(iso: str) -> int:
    return (datetime.date.fromisoformat(iso) - datetime.date(1970, 1, 1)).days


def write_ser_gpkg(path: Path, polygons: list[tuple[str, tuple]]) -> None:
    """Réécrit inputs/ser.gpkg à la forme BRUTE de l'IGN : un polygone d'alluvions porte
    ser_code = "L3" (spec §3, §7) ; les autres colonnes éventuelles restent NULL."""
    c = sqlite3.connect(path)
    c.execute("delete from ser")
    for code, (x0, x1, y0, y1) in polygons:
        c.execute("insert into ser (geom, ser_code) values (?, ?)",
                  (_rect_blob(X0 + x0, X0 + x1, Y0 + y0, Y0 + y1), code))
    c.execute("update gpkg_contents set min_x=?, min_y=?, max_x=?, max_y=? where table_name='ser'",
              (X0, Y0, X0 + SIDE, Y0 + SIDE))
    c.commit()
    c.close()


# ------------------------------------------------------------------ zones variantes
def make_zone_copy(name: str, mutate=None) -> tuple[Path, Path]:
    """Copie inputs/ et params/ du jeu fictif sous data/<name>/ (hors dépôt, ignoré par git),
    applique `mutate(zone_dir)`, écrit une config pointant sur <name>. Renvoie (zone_dir, config)."""
    zone_dir = ROOT / "data" / name
    if zone_dir.exists():
        shutil.rmtree(zone_dir)
    zone_dir.mkdir(parents=True)
    shutil.copytree(INPUTS, zone_dir / "inputs")
    shutil.copytree(ZONE / "params", zone_dir / "params")
    if mutate is not None:
        mutate(zone_dir)
    text = (ROOT / "config.yml").read_text(encoding="utf-8")
    text = re.sub(r"(?m)^zone:\s*\S+", f"zone: {name}", text)
    cfg = zone_dir / "config_m1.yml"
    cfg.write_text(text, encoding="utf-8")
    return zone_dir, cfg


def remove_zone_copy(name: str) -> None:
    shutil.rmtree(ROOT / "data" / name, ignore_errors=True)
    data = ROOT / "data"
    if data.is_dir() and not any(data.iterdir()):
        data.rmdir()


# ------------------------------------------------------------------ rasters et grille
class Grid:
    """grid.tif lue : géotransformation et centres de cellules, en mètres locaux (x - X0, y - Y0)."""

    def __init__(self, path: Path):
        with rasterio.open(path) as r:
            self.transform, self.shape, self.crs = r.transform, (r.height, r.width), r.crs
            self.res = (r.res[0], r.res[1])
            self.bounds = r.bounds
        h, w = self.shape
        cols, rows = np.meshgrid(np.arange(w), np.arange(h))
        self.cx = self.transform.c + (cols + 0.5) * self.transform.a
        self.cy = self.transform.f + (rows + 0.5) * self.transform.e
        self.lx, self.ly = self.cx - X0, self.cy - Y0
        self.cell_id = rows * w + cols  # spec contracts/README : ligne x largeur + colonne, NO

    def half(self):
        return self.res[0] / 2.0

    def inside_massif(self):
        return (self.lx > 0) & (self.lx < SIDE) & (self.ly > 0) & (self.ly < SIDE)

    def in_gap(self):
        x0, x1, y0, y1 = GAP
        return (self.lx > x0) & (self.lx < x1) & (self.ly > y0) & (self.ly < y1)

    def forest(self):
        return self.inside_massif() & ~self.in_gap()

    def in_rect(self, rect):
        x0, x1, y0, y1 = rect
        return (self.lx > x0) & (self.lx < x1) & (self.ly > y0) & (self.ly < y1)

    def fully_in(self, rect):
        """Cellules dont le carré entier tombe dans le rectangle (en mètres locaux)."""
        h = self.half()
        x0, x1, y0, y1 = rect
        return ((self.lx - h >= x0 - 1e-6) & (self.lx + h <= x1 + 1e-6)
                & (self.ly - h >= y0 - 1e-6) & (self.ly + h <= y1 + 1e-6))


def read_raster(path: Path):
    with rasterio.open(path) as r:
        return r.read(), r.nodata, r.dtypes, r.transform, r.crs


def valid_mask(arr, nodata):
    m = np.isfinite(arr) if arr.dtype.kind == "f" else np.ones(arr.shape, bool)
    if nodata is not None:
        m &= (arr != nodata)
    return m


def read_csv_map(path: Path) -> dict[int, str]:
    """Table de catégories (spec §8) : colonnes value,name. ser.csv porte en plus alluvium_code
    (spec §3) : voir read_ser_table."""
    import csv
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    head = [h.strip() for h in rows[0]]
    attendu = ["value", "name", "alluvium_code"] if path.name == "ser.csv" else ["value", "name"]
    assert head == attendu, f"{path.name} : en-tête {head}, attendu {attendu}"
    return {int(r[0]): r[1].strip() for r in rows[1:] if r}


NULL_TOKENS = {"", "NA", "NULL", "null", "NaN"}


def read_ser_table(path: Path) -> dict[int, tuple[str, str | None]]:
    """ser.csv : value -> (ser_code, alluvium_code ou None)."""
    import csv
    read_csv_map(path)  # contrôle l'en-tête
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    out = {}
    for r in rows:
        a = r["alluvium_code"].strip()
        out[int(r["value"])] = (r["name"].strip(), None if a in NULL_TOKENS else a)
    return out


def write_allometry(path: Path, coefs: dict[str, dict[str, float]]) -> None:
    """Réécrit params/allometry.parquet (format long, modèle etage_b) : coefs[espar][terme]."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    rows = [dict(species=sp, species_group=None, model="etage_b", term=t, value=float(v),
                 provisoire=True, source="synthetique_jeu_fictif")
            for sp, d in coefs.items() for t, v in d.items()]
    schema = pa.schema([("species", pa.string()), ("species_group", pa.string()),
                        ("model", pa.string()), ("term", pa.string()), ("value", pa.float64()),
                        ("provisoire", pa.bool_()), ("source", pa.string())])
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), path)


def read_parquet(path: Path):
    assert Path(path).exists(), f"sortie absente : {path}"
    return pds.dataset(str(path)).to_table().to_pylist()


def trees_init_path(zone_dir: Path = ZONE) -> Path:
    for rel in ("trees_init", "trees_init.parquet"):
        if (zone_dir / rel).exists():
            return zone_dir / rel
    raise AssertionError(f"trees_init absent de {zone_dir} (ni trees_init/ ni trees_init.parquet)")


# ------------------------------------------------------------------ rapports HTML
MOJIBAKE = re.compile(r"Ã[\u0080-\u00bf]|Â[\u0080-\u00bf]|<U\+[0-9A-Fa-f]{4}>|\\u[0-9a-fA-F]{4}|\ufffd")


def decode_report(path: Path) -> str:
    """Lit un rapport HTML en UTF-8 STRICT et refuse les accents mal encodés (octets invalides,
    double encodage « Ã© », échappements « <U+00E9> », caractère de remplacement)."""
    raw = Path(path).read_bytes()
    try:
        txt = raw.decode("utf-8")  # strict : une erreur d'octet fait échouer le test
    except UnicodeDecodeError as e:  # pragma: no cover - échec attendu en cas de défaut
        raise AssertionError(f"{Path(path).name} n'est pas de l'UTF-8 valide : {e}") from e
    m = MOJIBAKE.search(txt)
    assert not m, f"{Path(path).name} : accent mal encodé près de « {txt[max(m.start()-20,0):m.end()+20]} »"
    return txt


def html_sections(path: Path) -> list[tuple[str, str]]:
    """Sections d'un rapport : (titre h1-h6, texte jusqu'au titre suivant)."""
    raw = decode_report(path)
    parts = re.split(r"(?is)(<h[1-6]\b[^>]*>.*?</h[1-6]>)", raw)
    out = [("", _strip(parts[0]))]
    for i in range(1, len(parts), 2):
        out.append((_strip(parts[i]), _strip(parts[i + 1]) if i + 1 < len(parts) else ""))
    return out


def _strip(fragment: str) -> str:
    t = re.sub(r"(?s)<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", t).strip()


def sans_accent(s: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn").lower()


def section_text(path: Path, needle: str) -> str:
    """Texte des sections dont le TITRE contient `needle` (sans accent ni casse), plus les blocs
    (lignes, items) qui contiennent `needle`. Chaîne vide si rien ne s'y rapporte."""
    n = sans_accent(needle)
    textes = [t for h, t in html_sections(path) if n in sans_accent(h)]
    textes += [b for b in html_blocks(path) if n in sans_accent(b)]
    return " ".join(textes)


def html_blocks(path: Path) -> list[str]:
    """Texte d'un rapport HTML découpé en blocs (ligne de tableau, item, paragraphe, titre)."""
    raw = decode_report(path)
    parts = re.split(r"(?is)</?(?:tr|li|p|div|br|h[1-6]|table|ul|ol|section)\b[^>]*>", raw)
    out = []
    for p in parts:
        t = re.sub(r"(?s)<[^>]+>", " ", p)
        t = re.sub(r"\s+", " ", t).strip()
        if t:
            out.append(t)
    return out


def zone_reports(zone_dir: Path = ZONE) -> list[Path]:
    return sorted(zone_dir.glob("rapport_*.html"))


def all_report_blocks(zone_dir: Path = ZONE) -> list[str]:
    blocks = []
    for p in zone_reports(zone_dir):
        blocks += html_blocks(p)
    return blocks


def stands_in(x, y, stands):
    """Polygone nemeton qui contient (x, y) (coordonnées absolues), ou None."""
    for s in stands:
        x0, x1, y0, y1 = s["bbox"]
        if x0 <= x < x1 and y0 <= y < y1:
            return s
    return None


def report_blocks(name: str, zone_dir: Path = ZONE) -> list[str]:
    """Blocs d'un rapport précis (rapport_prepare.html ou rapport_biomes.html) ; échec s'il manque."""
    p = zone_dir / name
    assert p.is_file(), f"rapport absent : {p}"
    return html_blocks(p)
