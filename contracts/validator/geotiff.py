"""Profil GeoTIFF : lecture des balises TIFF en Python pur (spec §9, ADR 0002).

On lit les en-têtes avec `struct`, sans GDAL ni rasterio : on contrôle exactement ce que lit
le lecteur Rust sans GDAL de `simulate` (mission 015). Les pixels ne sont pas lus à M0.

Les règles et leurs variantes (`complet`, `grille`, `entree`, `cog`) sont dans
`contracts/geotiff_profile.json`. Ordre des axes : x = est, y = nord, EPSG:2154.
"""
import json
import struct
from functools import lru_cache
from pathlib import Path

from . import extent
from .report import Findings, Refused

CONTRACTS_DIR = Path(__file__).resolve().parent.parent
TYPE_SIZES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8,
              13: 4, 16: 8, 17: 8, 18: 8}
TYPE_FORMATS = {1: "B", 3: "H", 4: "I", 6: "b", 8: "h", 9: "i", 11: "f", 12: "d", 13: "I",
                16: "Q", 17: "q", 18: "Q"}

TAG = {"width": 256, "height": 257, "bits": 258, "compression": 259, "subfile": 254,
       "samples": 277, "strip_offsets": 273, "planar": 284, "predictor": 317,
       "tile_width": 322, "tile_height": 323, "tile_offsets": 324, "tile_counts": 325,
       "sample_format": 339, "pixel_scale": 33550, "tiepoint": 33922,
       "transformation": 34264, "geokeys": 34735, "nodata": 42113}
GEOKEY_PROJECTED = 3072
GEOKEY_GEOGRAPHIC = 2048
GEOKEY_RASTER_TYPE = 1025


@lru_cache(maxsize=1)
def load_profile():
    with open(CONTRACTS_DIR / "geotiff_profile.json", encoding="utf-8") as f:
        return json.load(f)


class Tiff:
    """Les IFD d'un TIFF classique : liste de dictionnaires {balise: valeurs}."""

    def __init__(self, path):
        self.data = Path(path).read_bytes()
        self.ifds = []
        self.bigtiff = False
        self._parse()

    def _parse(self):
        d = self.data
        if len(d) < 8 or d[:2] not in (b"II", b"MM"):
            raise ValueError("fichier non TIFF : en-tête II ou MM absent")
        self.order = "<" if d[:2] == b"II" else ">"
        (magic,) = struct.unpack_from(self.order + "H", d, 2)
        if magic == 43:
            self.bigtiff = True
            return
        if magic != 42:
            raise ValueError(f"fichier non TIFF : nombre magique {magic}")
        (offset,) = struct.unpack_from(self.order + "I", d, 4)
        seen = set()
        while offset and offset not in seen and len(self.ifds) < 64:
            seen.add(offset)
            ifd, offset = self._read_ifd(offset)
            self.ifds.append(ifd)
        if not self.ifds:
            raise ValueError("fichier TIFF sans image (aucun IFD)")

    def _read_ifd(self, offset):
        d, o = self.data, self.order
        (count,) = struct.unpack_from(o + "H", d, offset)
        ifd = {}
        for i in range(count):
            tag, typ, n = struct.unpack_from(o + "HHI", d, offset + 2 + 12 * i)
            size = TYPE_SIZES.get(typ)
            if size is None:
                continue
            raw_pos = offset + 2 + 12 * i + 8
            if size * n > 4:
                (raw_pos,) = struct.unpack_from(o + "I", d, raw_pos)
            raw = d[raw_pos: raw_pos + size * n]
            if len(raw) < size * n:
                raise ValueError(f"fichier TIFF tronqué (balise {tag})")
            if typ == 2:
                ifd[tag] = raw.split(b"\0")[0].decode("ascii", "replace")
            elif typ in (5, 10):
                ints = struct.unpack(o + ("I" if typ == 5 else "i") * (2 * n), raw)
                ifd[tag] = [ints[k] / ints[k + 1] if ints[k + 1] else 0 for k in range(0, 2 * n, 2)]
            elif typ in (7,):
                ifd[tag] = raw
            else:
                ifd[tag] = list(struct.unpack(o + TYPE_FORMATS[typ] * n, raw))
        (next_offset,) = struct.unpack_from(o + "I", d, offset + 2 + 12 * count)
        return ifd, next_offset


def first(ifd, name, default=None):
    value = ifd.get(TAG[name])
    if value is None:
        return default
    return value[0] if isinstance(value, list) else value


def geokeys(ifd):
    """{clé: valeur} des GeoKeys courtes (balise 34735)."""
    raw = ifd.get(TAG["geokeys"])
    if not raw or len(raw) < 4:
        return None
    keys = {}
    for k in range(raw[3]):
        key_id, location, _count, value = raw[4 + 4 * k: 8 + 4 * k]
        if location == 0:
            keys[key_id] = value
    return keys


def sample_type(ifd, profile):
    bits = ifd.get(TAG["bits"], [1])
    fmt = ifd.get(TAG["sample_format"], [1])
    pair = [bits[0], fmt[0]]
    for name, want in profile["sample_types"].items():
        if want == pair:
            return name
    label = {1: "UInt", 2: "Int", 3: "Float"}.get(fmt[0], "?")
    return f"{label}{bits[0]}"


def georef(ifd):
    """(origine x, origine y, taille x, taille y) du pixel, ou None."""
    scale = ifd.get(TAG["pixel_scale"])
    tie = ifd.get(TAG["tiepoint"])
    if not scale or not tie or len(tie) < 6:
        return None
    i, j = tie[0], tie[1]
    return tie[3] - i * scale[0], tie[4] + j * scale[1], scale[0], scale[1]


def check(path, options, grid_path=None):
    """Écarts d'un GeoTIFF à la variante de profil demandée."""
    findings = Findings()
    profile = load_profile()
    variant_name = options.get("variant", "complet")
    variant = profile["variants"][variant_name]
    rules = set(variant["checks"])
    if options.get("is_grid"):
        rules.discard("alignment")  # grid.tif est la référence d'alignement
    if "alignment" in rules and grid_path is None:
        raise Refused(f"variante {variant_name} : l'alignement sur grid.tif ne peut pas être "
                      f"contrôlé sans --grid <grid.tif> (en mode --zone : grid.tif absent de "
                      f"la zone) ; contrôle impossible")
    if "alignment" in rules and not Path(grid_path).is_file():
        raise Refused(f"fichier absent : {grid_path} (grille de référence de --grid)")
    try:
        tiff = Tiff(path)
    except (ValueError, struct.error, OSError) as exc:
        findings.error(f"fichier GeoTIFF illisible : {exc}")
        return [(path, findings)]
    if tiff.bigtiff:
        findings.error("BigTIFF refusé par le profil : TIFF classique attendu")
        return [(path, findings)]
    ifd = tiff.ifds[0]
    check_ifd(ifd, tiff, rules, profile, variant, options, findings)
    pixel = options.get("pixel_size_m", variant.get("pixel_size_m"))
    ref = georef(ifd)
    if "georef" in rules:
        # Même règle que le lecteur Rust (simulate/src/geotiff.rs, georeference) : la
        # matrice 34264 est refusée quand elle tient lieu d'échelle et de point de liaison.
        if ref is None and TAG["transformation"] in ifd:
            findings.error("géoréférencement par matrice (balise 34264) refusé : "
                           "ModelPixelScale et ModelTiepoint attendus")
        elif ref is None:
            findings.error("géoréférencement absent : balises 33550 et 33922 attendues")
        elif ref[2] <= 0 or ref[3] <= 0:
            findings.error(f"taille de pixel nulle ou négative ({ref[2]:g} × {ref[3]:g})")
            ref = None
    if "pixel_is_area" in rules:
        keys = geokeys(ifd) or {}
        if keys.get(GEOKEY_RASTER_TYPE, 1) != 1:
            findings.error("pixel « point » (RasterPixelIsPoint, GeoKey 1025 = 2) refusé : "
                           "seul « surface » (RasterPixelIsArea) est accepté")
    if ref and pixel is not None and (abs(ref[2] - pixel) > 1e-9 or abs(ref[3] - pixel) > 1e-9):
        findings.error(f"maille de {ref[2]:g} × {ref[3]:g} m, {pixel:g} m attendue "
                       f"(résolution de la grille)")
    if ref and "extent" in rules:
        width, height = first(ifd, "width", 0), first(ifd, "height", 0)
        problem = extent.bounds_problem(ref[0], ref[1] - height * ref[3],
                                        ref[0] + width * ref[2], ref[1])
        if problem:
            findings.error(f"raster : {problem}")
    if "alignment" in rules:
        check_alignment(ifd, ref, grid_path, findings)
    if "overviews" in rules:
        overviews = [x for x in tiff.ifds[1:] if first(x, "subfile", 0) & 1]
        if not overviews:
            findings.error("COG sans aperçus : au moins un niveau réduit attendu")
    return [(path, findings)]


def check_ifd(ifd, tiff, rules, profile, variant, options, findings):
    allowed = profile["allowed"]
    compressions = variant.get("compression", allowed["compression"])
    if "tiles" in rules:
        tw, th = first(ifd, "tile_width"), first(ifd, "tile_height")
        if tw is None or th is None:
            findings.error(f"fichier en bandes : tuiles de {allowed['tile_size'][0]} × "
                           f"{allowed['tile_size'][1]} attendues (balises 322 et 323)")
        elif [tw, th] != allowed["tile_size"]:
            findings.error(f"tuiles de {tw} × {th}, {allowed['tile_size'][0]} × "
                           f"{allowed['tile_size'][1]} attendues")
    if "planar" in rules:
        planar = first(ifd, "planar", 1)
        if planar != allowed["planar_config"]:
            findings.error(f"entrelacement PLANARCONFIG={planar}, PLANARCONFIG="
                           f"{allowed['planar_config']} attendu (bande par bande)")
    if "compression" in rules:
        comp = first(ifd, "compression", 1)
        if str(comp) not in compressions:
            name = profile["known_compressions"].get(str(comp), "inconnue")
            findings.error(f"compression {name} (code {comp}) refusée : "
                           f"{' ou '.join(sorted(set(compressions.values())))} attendue")
    if "predictor" in rules:
        pred = first(ifd, "predictor", 1)
        if pred not in allowed["predictor"]:
            findings.error(f"PREDICTOR={pred} refusé : prédicteur "
                           f"{' ou '.join(map(str, allowed['predictor']))} attendu")
    if "band_tags" in rules:
        # Comme le lecteur Rust : une valeur de 258 et de 339 par bande (339 absente = 1).
        samples = first(ifd, "samples", 1)
        bits = ifd.get(TAG["bits"], [])
        formats = ifd.get(TAG["sample_format"], [1] * samples)
        if len(bits) != samples or len(formats) != samples:
            findings.error(f"{samples} bande(s) mais {len(bits)} valeur(s) de bits (balise "
                           f"258) et {len(formats)} de format (balise 339) : une par bande "
                           f"attendue")
    if "sparse_tiles" in rules:
        offsets = ifd.get(TAG["tile_offsets"]) or []
        counts = ifd.get(TAG["tile_counts"]) or []
        empty = [i for i, (o, c) in enumerate(zip(offsets, counts)) if o == 0 and c == 0]
        if empty:
            findings.error(f"tuile absente (fichier creux) refusée : {len(empty)} tuile(s) "
                           f"de début et de taille nuls, la première au rang {empty[0]}")
    if "uniform_bands" in rules:
        samples = first(ifd, "samples", 1)
        for tag, label in ((TAG["bits"], "bits"), (TAG["sample_format"], "format")):
            values = ifd.get(tag, [])
            if len(set(values)) > 1:
                findings.error(f"bandes de types différents refusées ({label} : {values}, "
                               f"{samples} bandes)")
                break
    if "sample_type" in rules:
        found = sample_type(ifd, profile)
        wanted = options.get("sample_types", list(profile["sample_types"]))
        if found not in wanted:
            findings.error(f"type de valeur {found} refusé : {' ou '.join(wanted)} attendu")
    bands = options.get("bands")
    samples = first(ifd, "samples", 1)
    if bands is not None and samples != bands:
        findings.error(f"{samples} bande(s), {bands} attendue(s)")
    if "nodata" in rules:
        nodata = ifd.get(TAG["nodata"])
        if nodata is None:
            findings.error("nodata absent : balise 42113 (GDAL_NODATA) obligatoire")
        else:
            try:
                float(nodata)
            except ValueError:
                findings.error(f"nodata illisible dans la balise 42113 : {nodata!r}")
    if "crs" in rules:
        keys = geokeys(ifd)
        want = allowed["epsg"]
        if keys is None:
            findings.error(f"GeoKey absente (balise 34735) : fichier non géoréférencé, "
                           f"EPSG:{want} attendu")
        elif keys.get(GEOKEY_PROJECTED) != want:
            found = keys.get(GEOKEY_PROJECTED) or keys.get(GEOKEY_GEOGRAPHIC)
            findings.error(f"projection EPSG:{found}, EPSG:{want} attendu (GeoKey 3072)")
    if "integrity" in rules:
        offsets = ifd.get(TAG["tile_offsets"]) or ifd.get(TAG["strip_offsets"]) or []
        counts = ifd.get(TAG["tile_counts"]) or ifd.get(279) or []
        if offsets and counts and max(o + c for o, c in zip(offsets, counts)) > len(tiff.data):
            findings.error("fichier GeoTIFF tronqué : des tuiles dépassent la fin du fichier")


def check_alignment(ifd, ref, grid_path, findings):
    """Même origine, même maille, mêmes dimensions que `grid.tif`."""
    try:
        grid = Tiff(grid_path)
    except (ValueError, struct.error, OSError) as exc:
        findings.error(f"grid.tif illisible pour l'alignement : {exc}")
        return
    if grid.bigtiff or ref is None:
        return
    gref = georef(grid.ifds[0])
    gsize = (first(grid.ifds[0], "width"), first(grid.ifds[0], "height"))
    size = (first(ifd, "width"), first(ifd, "height"))
    if gref is None or any(abs(a - b) > 1e-6 for a, b in zip(ref, gref)) or size != gsize:
        findings.error(f"non aligné sur grid.tif : origine ({ref[0]:g}, {ref[1]:g}), maille "
                       f"{ref[2]:g} m, {size[0]} × {size[1]} pixels ; grid.tif : "
                       + (f"origine ({gref[0]:g}, {gref[1]:g}), maille {gref[2]:g} m, "
                          f"{gsize[0]} × {gsize[1]} pixels" if gref else "non géoréférencé"))
