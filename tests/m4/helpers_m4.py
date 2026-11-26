"""Outils communs des tests d'acceptation M4a, tranche « état initial » (mission 030).

Ces tests partent de la spec (docs/spec.md §1, §2, §9, §10, §11), des contrats (contracts/), des
fiches 028 et 029 et de docs/referentiels/itowns-instancing.md ; ils ne lisent ni python/ ni
viewer-web/src. Une sortie absente est un échec, jamais un « skip » (la CI refuse tout test sauté).

Principe de l'oracle : les arbres, les cellules, les types, les stations et la composition attendus sont
recalculés ICI, depuis les sorties de prepare/biomes/trees (trees_init, grid, vegetation_map, stand_map,
station_type, h0, stands) et contracts/species.csv. Rien n'est lu dans le code du module `assets`.

REPÈRE DES TUILES (point que la spec laisse ouvert, §9 : « glTF 2.0, 3D Tiles 1.1 avec instanciation ») :
la position monde d'une instance est
    M_tuiles(chaîne des `transform` de la racine à la tuile) · R · N_noeud · translation
avec N_noeud la matrice du noeud glTF, et R le passage glTF Y-haut vers Z-haut de 3D Tiles
(x, y, z) -> (x, -z, y). Le résultat doit être JUSTE dans l'un des deux repères suivants (le test ne
tranche pas entre eux, il vérifie que celui qui est choisi est cohérent) :
  - ECEF (EPSG:4978) : `transform` de la racine = repère local est-nord-haut -> ECEF ;
  - EPSG:2154 absolu : le monde est (x Lambert-93, y Lambert-93, altitude), `transform` éventuel inclus.
La hauteur (altitude, RAF20) n'est PAS testée : seule la position horizontale l'est (limite déclarée).
"""
from __future__ import annotations

import base64
import csv
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import rasterio

ROOT = Path(__file__).resolve().parents[2]
# Zone testée. Par défaut le jeu fictif versionné. SYLVIGENESE_M4_ZONE=<nom> (confort du développeur, jamais en
# CI) la remplace par data/<nom>/, copie du jeu fictif déjà préparée : on teste sans toucher au dépôt.
ZONE_NAME = os.environ.get("SYLVIGENESE_M4_ZONE", "zone_fictive")
ZONE = ROOT / "tests" / "fixtures" / "zone_fictive" if ZONE_NAME == "zone_fictive" else ROOT / "data" / ZONE_NAME
VALIDATE = ROOT / "contracts" / "validate"
SPECIES_CSV = ROOT / "contracts" / "species.csv"
HERE = Path(__file__).resolve().parent

X0, Y0, RES, NCOLS, NROWS = 700_000.0, 6_501_000.0, 25.0, 40, 40   # grid.tif (coin nord-ouest, 25 m)
POS_TOL = 0.15          # m : erreur horizontale admise entre un arbre et son instance
CHAIN = ("prepare", "biomes", "trees", "assets")
ASSET_DIRS = ("tiles", "web", "assets", "massif")      # ce que `assets` a le droit d'écrire
EXT = "EXT_mesh_gpu_instancing"
SIGNAL_VIDE = ("non calcul", "vide", "absent", "indisponible", "non disponible", "post", "m3", "non renseign")


# ------------------------------------------------------------------ processus
def offline_env() -> dict:
    """Environnement sans réseau : proxys morts (cas terrain « absence de réseau »)."""
    env = dict(os.environ)
    dead = "http://127.0.0.1:9"
    for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "all_proxy"):
        env[k] = dead
    env.pop("NO_PROXY", None)
    env.pop("no_proxy", None)
    return env


def run_make(*targets: str, zone: str | None = None, config: Path | None = None,
             timeout: int = 1800) -> subprocess.CompletedProcess:
    zone = zone or ZONE_NAME
    if config is None and zone != "zone_fictive":
        config = write_config(ROOT / "data" / zone, zone)
    cmd = ["make", *targets, f"ZONE={zone}"]
    if config is not None:
        cmd.append(f"CONFIG={config}")
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, env=offline_env(), timeout=timeout)


def run_assets(config: Path, timeout: int = 900) -> subprocess.CompletedProcess:
    """Appelle le module comme le Makefile (cible assets), pour lire son code de sortie exact
    (make renvoie toujours 2 en cas d'échec)."""
    env = offline_env()
    env["PYTHONPATH"] = "python"
    return subprocess.run(["python3", "-m", "sylvigenese.assets", "--config", str(config)], cwd=ROOT,
                          capture_output=True, text=True, env=env, timeout=timeout)


def validate(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["python3", str(VALIDATE), *args], cwd=ROOT, capture_output=True, text=True)


# ------------------------------------------------------------------ zones
def clean_asset_outputs(zone_dir: Path) -> None:
    for d in ASSET_DIRS:
        shutil.rmtree(zone_dir / d, ignore_errors=True)


def remove_sim(zone_dir: Path) -> None:
    """Efface sim/ (et une écriture interrompue de simulate) : les tests de l'état initial (mission 030) tournent sur
    une zone SANS sim/ (plan m4a-suite-temps §6, « sim/ périmé ») ; sinon, sur un poste où `make simulate` a tourné,
    `assets` lirait le futur et ces tests jugeraient autre chose que l'état initial (mission 045)."""
    for d in ("sim", ".sim_en_cours"):
        shutil.rmtree(zone_dir / d, ignore_errors=True)


def clean_chain_outputs(zone_dir: Path) -> None:
    """Efface les sorties de prepare, biomes, trees et assets (jamais les entrées ni params/)."""
    for rel in ("grid.tif", "dtm.tif", "forest_mask.tif", "ser.tif", "ser.csv", "h0.tif", "chm_date.tif",
                "station_gradients.tif", "station_type.tif", "station_type.csv", "site_potential.tif",
                "site_potential.csv", "stands.parquet", "vegetation_map.tif", "vegetation_map.csv",
                "rapport_biomes.html", "rapport_biomes_hors_polygone.csv", "rapport_prepare.html",
                "rapport_arbres.html", "stand_map.tif", "stand_map.csv", "ifn/plots.parquet",
                "ifn/trees.parquet", "ifn/flora.parquet"):
        (zone_dir / rel).unlink(missing_ok=True)
    shutil.rmtree(zone_dir / "trees_init", ignore_errors=True)
    clean_asset_outputs(zone_dir)
    remove_sim(zone_dir)


def write_config(zone_dir: Path, name: str, t0: int | None = None) -> Path:
    text = (ROOT / "config.yml").read_text(encoding="utf-8")
    text = re.sub(r"(?m)^zone:\s*\S+", f"zone: {name}", text)
    if t0 is not None:
        # config.yml porte déjà un bloc `simulate:` (mission 034) : on remplace sa valeur de t0, sans second bloc.
        if re.search(r"(?m)^  t0:\s*\S+", text):
            text = re.sub(r"(?m)^(  t0:)\s*\d+", rf"\g<1> {t0}", text)
        elif re.search(r"(?m)^simulate:", text):
            text = re.sub(r"(?m)^simulate:[ \t]*\n", f"simulate:\n  t0: {t0}\n", text, count=1)
        else:
            text += f"\nsimulate:\n  t0: {t0}\n"
    cfg = zone_dir / "config_m4.yml"
    cfg.write_text(text, encoding="utf-8")
    return cfg


def clone_zone(name: str, mutate=None, t0: int | None = None) -> tuple[Path, Path]:
    """Copie de la zone fictive APRÈS la chaîne (entrées, params, sorties de prepare/biomes/trees), sans
    les sorties de `assets`, sous data/<name>/ (hors dépôt, ignoré par git). `mutate(zone_dir)` modifie
    la copie ; une config pointant sur <name> est écrite."""
    zone_dir = ROOT / "data" / name
    if zone_dir.exists():
        shutil.rmtree(zone_dir)
    shutil.copytree(ZONE, zone_dir, ignore=shutil.ignore_patterns(*ASSET_DIRS, "sim", ".sim_en_cours", "config_m4*.yml",
                                                             "__pycache__"))
    assert zone_dir != ZONE
    if mutate is not None:
        mutate(zone_dir)
    return zone_dir, write_config(zone_dir, name, t0)


def remove_zone_copy(name: str) -> None:
    shutil.rmtree(ROOT / "data" / name, ignore_errors=True)
    data = ROOT / "data"
    if data.is_dir() and not any(data.iterdir()):
        data.rmdir()


def tree_files(zone_dir: Path, exclude=ASSET_DIRS) -> dict[str, str]:
    """Empreinte (sha256) de tous les fichiers de la zone hors dossiers de `assets`."""
    out = {}
    for p in sorted(zone_dir.rglob("*")):
        rel = p.relative_to(zone_dir)
        if p.is_file() and rel.parts[0] not in exclude and rel.name != "config_m4.yml":
            out[str(rel)] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


# ------------------------------------------------------------------ référentiels et oracle de la zone
def species_group() -> dict[str, str]:
    with open(SPECIES_CSV, encoding="utf-8", newline="") as f:
        return {r["espar"]: r["groupe"] for r in csv.DictReader(f)}


def read_trees_init(zone_dir: Path) -> dict[str, np.ndarray]:
    d = pq.read_table(zone_dir / "trees_init" / "trees.parquet").to_pydict()
    return {k: np.array(v) for k, v in d.items()}


def write_trees_init(zone_dir: Path, cols: dict) -> None:
    tab = pq.read_table(zone_dir / "trees_init" / "trees.parquet")
    for k, v in cols.items():
        i = tab.schema.get_field_index(k)
        tab = tab.set_column(i, tab.schema.field(i), [list(map(_py, v))])
    pq.write_table(tab, zone_dir / "trees_init" / "trees.parquet")


def _py(v):
    return v.item() if hasattr(v, "item") else v


def drop_tree_row(zone_dir: Path, index: int) -> None:
    tab = pq.read_table(zone_dir / "trees_init" / "trees.parquet")
    keep = [i for i in range(tab.num_rows) if i != index]
    pq.write_table(tab.take(keep), zone_dir / "trees_init" / "trees.parquet")


def read_raster(path: Path):
    with rasterio.open(path) as r:
        return r.read(1), r.nodata, r.transform, r.crs


def read_names(path: Path) -> dict[int, str]:
    with open(path, encoding="utf-8", newline="") as f:
        return {int(r["value"]): r["name"] for r in csv.DictReader(f)}


def cell_of(x, y):
    """(ligne, colonne) de la cellule de 25 m de grid.tif qui contient (x, y) ; ligne 0 = nord."""
    return (int(math.floor((Y0 - y) / RES)), int(math.floor((x - X0) / RES)))


def cell_centre(cell_id: int) -> tuple[float, float]:
    r, c = divmod(cell_id, NCOLS)
    return X0 + (c + 0.5) * RES, Y0 - (r + 0.5) * RES


class Oracle:
    """Faits attendus d'une zone, recalculés depuis ses sorties de prepare/biomes/trees."""

    def __init__(self, zone_dir: Path):
        self.dir = zone_dir
        self.trees = read_trees_init(zone_dir)
        self.veg, self.veg_nd, _, _ = read_raster(zone_dir / "vegetation_map.tif")
        self.stand, self.stand_nd, _, _ = read_raster(zone_dir / "stand_map.tif")
        self.station, self.station_nd, _, _ = read_raster(zone_dir / "station_type.tif")
        self.h0, self.h0_nd, _, _ = read_raster(zone_dir / "h0.tif")
        self.veg_names = read_names(zone_dir / "vegetation_map.csv")
        self.stand_names = read_names(zone_dir / "stand_map.csv")
        self.station_names = read_names(zone_dir / "station_type.csv")
        st = pq.read_table(zone_dir / "stands.parquet").to_pydict()
        self.stand_species = dict(zip(st["stand_id"], st["species"]))
        n = len(self.trees["x"])
        cells = [cell_of(x, y) for x, y in zip(self.trees["x"], self.trees["y"])]
        self.tree_cell = np.array([r * NCOLS + c for r, c in cells])
        self.n_trees = n

    def forest_cells(self) -> set[int]:
        """Cellules forestières : un type de végétation (spec §11, M1 : aucune cellule forestière sans type)."""
        rr, cc = np.nonzero(self.veg != self.veg_nd)
        return {int(r * NCOLS + c) for r, c in zip(rr, cc)}

    def cell_values(self, cid: int) -> dict:
        r, c = divmod(cid, NCOLS)
        sv, tv, kv = int(self.stand[r, c]), int(self.veg[r, c]), int(self.station[r, c])
        return {
            "stand": None if sv == self.stand_nd else self.stand_names[sv],
            "vegetation_type": self.veg_names[tv],
            "station_type": self.station_names[kv],
            "h0": float(self.h0[r, c]),
        }

    def species_in_cell(self, cid: int) -> set[str]:
        return {str(s) for s in self.trees["species"][self.tree_cell == cid]}


# ------------------------------------------------------------------ géodésie (sans pyproj)
_A = 6378137.0
_F = 1 / 298.257222101
_E2 = _F * (2 - _F)
_E = math.sqrt(_E2)
_PHI0, _LAM0, _PHI1, _PHI2, _FE, _FN = map(math.radians, (46.5, 3.0, 44.0, 49.0, 0, 0))
_FE, _FN = 700000.0, 6600000.0


def _m(phi):
    return np.cos(phi) / np.sqrt(1 - _E2 * np.sin(phi) ** 2)


def _t(phi):
    s = _E * np.sin(phi)
    return np.tan(math.pi / 4 - phi / 2) / ((1 - s) / (1 + s)) ** (_E / 2)


_N = (math.log(_m(_PHI1)) - math.log(_m(_PHI2))) / (math.log(_t(_PHI1)) - math.log(_t(_PHI2)))
_FF = _m(_PHI1) / (_N * _t(_PHI1) ** _N)
_RHO0 = _A * _FF * _t(_PHI0) ** _N


def lambert93_forward(lon_deg, lat_deg):
    phi, lam = np.radians(lat_deg), np.radians(lon_deg)
    rho = _A * _FF * _t(phi) ** _N
    th = _N * (lam - _LAM0)
    return _FE + rho * np.sin(th), _FN + _RHO0 - rho * np.cos(th)


def lambert93_inverse(x, y):
    xp, yp = np.asarray(x) - _FE, _RHO0 - (np.asarray(y) - _FN)
    rho = np.hypot(xp, yp)
    th = np.arctan2(xp, yp)
    t = (rho / (_A * _FF)) ** (1 / _N)
    phi = math.pi / 2 - 2 * np.arctan(t)
    for _ in range(8):
        s = _E * np.sin(phi)
        phi = math.pi / 2 - 2 * np.arctan(t * ((1 - s) / (1 + s)) ** (_E / 2))
    return np.degrees(th / _N + _LAM0), np.degrees(phi)


def ecef_to_lonlat(p):
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    lon = np.arctan2(y, x)
    q = np.hypot(x, y)
    lat = np.arctan2(z, q * (1 - _E2))
    for _ in range(8):
        n = _A / np.sqrt(1 - _E2 * np.sin(lat) ** 2)
        h = q / np.cos(lat) - n
        lat = np.arctan2(z, q * (1 - _E2 * n / (n + h)))
    return np.degrees(lon), np.degrees(lat)


def lonlat_to_ecef(lon_deg, lat_deg, h=0.0):
    lon, lat = np.radians(lon_deg), np.radians(lat_deg)
    n = _A / np.sqrt(1 - _E2 * np.sin(lat) ** 2)
    return np.stack([(n + h) * np.cos(lat) * np.cos(lon), (n + h) * np.cos(lat) * np.sin(lon),
                     (n * (1 - _E2) + h) * np.sin(lat)], axis=-1)


# ------------------------------------------------------------------ 3D Tiles et glTF
Y_UP_TO_Z_UP = np.array([[1, 0, 0, 0], [0, 0, -1, 0], [0, 1, 0, 0], [0, 0, 0, 1]], dtype=float)


def mat(values) -> np.ndarray:
    """Matrice 4x4 écrite en colonnes (3D Tiles et glTF)."""
    return np.array(values, dtype=float).reshape(4, 4).T


def find_tilesets(zone_dir: Path) -> list[Path]:
    return sorted((zone_dir / "tiles").glob("*/tileset.json"))


def walk_tileset(path: Path, parent=np.eye(4), seen=None) -> list[dict]:
    """Contenus d'un tileset explicite (racine, enfants, tilesets externes) : uri, chemin, matrice
    cumulée, volume englobant de la tuile. Le pavage implicite n'est pas géré (déclaré)."""
    ts = json.loads(path.read_text(encoding="utf-8"))
    out = []

    def rec(tile, m_parent):
        m = m_parent @ (mat(tile["transform"]) if "transform" in tile else np.eye(4))
        contents = ([tile["content"]] if "content" in tile else []) + list(tile.get("contents", []))
        for c in contents:
            p = (path.parent / c["uri"]).resolve()
            if c["uri"].lower().endswith(".json"):
                out.extend(walk_tileset(p, m))
            else:
                out.append({"uri": c["uri"], "path": p, "matrix": m,
                            "volume": c.get("boundingVolume", tile.get("boundingVolume"))})
        for ch in tile.get("children", []):
            rec(ch, m)

    rec(ts["root"], parent)
    return out


def _buffer_bytes(gltf, idx, base: Path, cache) -> bytes:
    if idx in cache:
        return cache[idx]
    uri = gltf["buffers"][idx].get("uri")
    if uri is None:
        raise AssertionError("buffer sans uri (conteneur GLB : le contenu doit être un .gltf)")
    if uri.startswith("data:"):
        data = base64.b64decode(uri.split(",", 1)[1])
    else:
        data = (base / uri).read_bytes()
    cache[idx] = data
    return data


_COMP = {5120: "i1", 5121: "u1", 5122: "<i2", 5123: "<u2", 5125: "<u4", 5126: "<f4"}
_NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def read_accessor(gltf, idx, base: Path, cache) -> np.ndarray:
    acc = gltf["accessors"][idx]
    view = gltf["bufferViews"][acc["bufferView"]]
    buf = _buffer_bytes(gltf, view["buffer"], base, cache)
    dt = np.dtype(_COMP[acc["componentType"]])
    nc = _NCOMP[acc["type"]]
    start = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = view.get("byteStride") or dt.itemsize * nc
    n = acc["count"]
    need = start + (n - 1) * stride + dt.itemsize * nc if n else start
    assert need <= len(buf), f"accessor {idx} hors du tampon ({need} > {len(buf)})"
    raw = np.frombuffer(buf, dtype="u1")
    rows = np.lib.stride_tricks.as_strided(raw[start:], shape=(n, dt.itemsize * nc), strides=(stride, 1))
    return np.frombuffer(np.ascontiguousarray(rows).tobytes(), dtype=dt).reshape(n, nc).astype(float)


def node_matrix(node) -> np.ndarray:
    if "matrix" in node:
        return mat(node["matrix"])
    t, r, s = node.get("translation", [0, 0, 0]), node.get("rotation", [0, 0, 0, 1]), node.get("scale", [1, 1, 1])
    x, y, z, w = r
    rot = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                    [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                    [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    m = np.eye(4)
    m[:3, :3] = rot @ np.diag(s)
    m[:3, 3] = t
    return m


def read_gltf(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def mesh_key(gltf, mesh_idx, base, cache) -> str:
    """Empreinte de la géométrie d'un maillage (deux instances du même modèle ont la même)."""
    h = hashlib.sha1()
    for prim in gltf["meshes"][mesh_idx]["primitives"]:
        h.update(read_accessor(gltf, prim["attributes"]["POSITION"], base, cache).tobytes())
        if "indices" in prim:
            h.update(read_accessor(gltf, prim["indices"], base, cache).tobytes())
    return h.hexdigest()[:12]


def instance_nodes(gltf) -> list[tuple[int, np.ndarray]]:
    """(indice du noeud, matrice monde glTF) des noeuds de la scène qui portent EXT_mesh_gpu_instancing."""
    nodes = gltf.get("nodes", [])
    scene = gltf.get("scenes", [{"nodes": list(range(len(nodes)))}])[gltf.get("scene", 0)]
    out = []

    def rec(i, parent):
        m = parent @ node_matrix(nodes[i])
        if EXT in nodes[i].get("extensions", {}):
            out.append((i, m))
        for c in nodes[i].get("children", []):
            rec(c, m)

    for i in scene.get("nodes", []):
        rec(i, np.eye(4))
    return out


def collect_instances(zone_dir: Path) -> dict:
    """Toutes les instances de tous les contenus de tous les tilesets de la zone, en repère monde de la
    tuile (Z-haut, transform appliqué). Renvoie des tableaux alignés : world (N,3), scale (N,3), model (N,),
    et la liste des contenus."""
    worlds, scales, models, contents = [], [], [], []
    for ts in find_tilesets(zone_dir):
        for c in walk_tileset(ts):
            gltf = read_gltf(c["path"])
            cache: dict = {}
            contents.append(c)
            for i, nm in instance_nodes(gltf):
                node = gltf["nodes"][i]
                attrs = node["extensions"][EXT]["attributes"]
                tr = read_accessor(gltf, attrs["TRANSLATION"], c["path"].parent, cache)
                sc = read_accessor(gltf, attrs["SCALE"], c["path"].parent, cache) if "SCALE" in attrs \
                    else np.ones_like(tr)
                key = mesh_key(gltf, node["mesh"], c["path"].parent, cache)
                p = np.c_[tr, np.ones(len(tr))] @ nm.T
                p = p @ Y_UP_TO_Z_UP.T
                rtc = gltf.get("extensions", {}).get("CESIUM_RTC", {}).get("center")
                if rtc:
                    p[:, :3] += np.array(rtc)
                p = p @ c["matrix"].T
                worlds.append(p[:, :3])
                scales.append(sc)
                models.extend([key] * len(tr))
    if not worlds:
        return {"world": np.zeros((0, 3)), "scale": np.zeros((0, 3)), "model": np.array([]), "contents": contents}
    return {"world": np.vstack(worlds), "scale": np.vstack(scales), "model": np.array(models),
            "contents": contents}


def lattice_key(x, y):
    """Clé d'un point sur le réseau des centres de pixels du MNH (0,5 m, centres en .25 et .75)."""
    return (np.round((np.asarray(x) - 0.25) / 0.5).astype(np.int64),
            np.round((np.asarray(y) - 0.25) / 0.5).astype(np.int64))


def to_lambert(world: np.ndarray, frame: str) -> np.ndarray:
    if frame == "ECEF":
        lon, lat = ecef_to_lonlat(world)
        x, y = lambert93_forward(lon, lat)
        return np.c_[x, y]
    return world[:, :2].copy()


def match_instances(world: np.ndarray, tx: np.ndarray, ty: np.ndarray) -> dict:
    """Associe chaque instance à l'arbre dont le centre de pixel est à la clé arrondie de sa position,
    dans chacun des deux repères admis ; garde le repère qui apparie le plus d'instances."""
    kt = lattice_key(tx, ty)
    tree_by_key = {(a, b): i for i, (a, b) in enumerate(zip(*kt))}
    best = None
    for frame in ("ECEF", "EPSG:2154"):
        xy = to_lambert(world, frame)
        if not np.all(np.isfinite(xy)):
            continue
        ka, kb = lattice_key(xy[:, 0], xy[:, 1])
        tree_of = np.array([tree_by_key.get((a, b), -1) for a, b in zip(ka, kb)])
        ok = tree_of >= 0
        resid = np.full(len(xy), np.inf)
        resid[ok] = np.hypot(xy[ok, 0] - tx[tree_of[ok]], xy[ok, 1] - ty[tree_of[ok]])
        res = {"frame": frame, "xy": xy, "tree_of": tree_of, "resid": resid, "n_ok": int(ok.sum())}
        if best is None or res["n_ok"] > best["n_ok"]:
            best = res
    return best


def volume_contains(volume: dict, matrix: np.ndarray, world: np.ndarray, frame: str, tol: float = 5.0) -> np.ndarray:
    """Vrai pour les points du monde que le volume englobant (box, sphere, region) contient, à `tol` m près."""
    if "box" in volume:
        b = np.array(volume["box"], dtype=float)
        c, axes = b[:3], b[3:].reshape(3, 3).T          # colonnes = demi-axes
        local = np.linalg.solve(matrix[:3, :3], (world - matrix[:3, 3]).T).T - c
        u = np.linalg.solve(axes, local.T).T
        half = np.linalg.norm(axes, axis=0)
        return np.all(np.abs(u) * half <= half + tol, axis=1)
    if "sphere" in volume:
        s = np.array(volume["sphere"], dtype=float)
        local = np.linalg.solve(matrix[:3, :3], (world - matrix[:3, 3]).T).T
        scale = np.linalg.norm(matrix[:3, 0])
        return np.linalg.norm(local - s[:3], axis=1) * scale <= s[3] * scale + tol
    if "region" in volume:
        w, s, e, n = volume["region"][:4]
        lon, lat = ecef_to_lonlat(world) if frame == "ECEF" else lambert93_inverse(world[:, 0], world[:, 1])
        m = math.degrees(tol / _A)
        return ((np.radians(lon) >= w - math.radians(m)) & (np.radians(lon) <= e + math.radians(m)) &
                (np.radians(lat) >= s - math.radians(m)) & (np.radians(lat) <= n + math.radians(m)))
    raise AssertionError(f"volume englobant inconnu : {list(volume)}")


def per_tree_view(zone_dir: Path) -> dict:
    """Pour une zone construite : clé de réseau -> (échelle Y, modèle) de l'instance, dans le repère juste."""
    inst = collect_instances(zone_dir)
    tr = read_trees_init(zone_dir)
    m = match_instances(inst["world"], tr["x"], tr["y"])
    kx, ky = lattice_key(m["xy"][:, 0], m["xy"][:, 1])
    return {(int(a), int(b)): (float(s[1]), str(mo)) for a, b, s, mo in zip(kx, ky, inst["scale"], inst["model"])}, inst, m


# ------------------------------------------------------------------ fiches de cellule
def read_sheets(zone_dir: Path) -> dict[str, dict]:
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted((zone_dir / "web" / "cells").glob("*.json"))}


def sheet_cells(sheets: dict[str, dict]) -> dict[int, dict]:
    out = {}
    for sheet in sheets.values():
        for c in sheet["cells"]:
            out.setdefault(c["cell_id"], c)
    return out


def string_values(obj) -> list[str]:
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        return [s for v in obj.values() for s in string_values(v)]
    if isinstance(obj, list):
        return [s for v in obj for s in string_values(v)]
    return []


def sans_accent(s: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower()


# ------------------------------------------------------------------ classes de modèle (M6a, mission 069)
# Avant M6a, deux modèles génériques (feuillu, résineux). Avec M6a : un modèle par (essence, stade) quand un exemplaire
# existe (assets.models.exemplars_dir de config.yml), sinon le générique du groupe (décision Q3 de Pascal, sans emprunt) ;
# le stade d'un ARBRE est h / h_pot de l'arbre avec les seuils de biomes/stades/stage_breaks.yml (décision Q8).
# Ces fonctions donnent la CLASSE attendue de chaque arbre ; les tests exigent « une classe = un modèle, deux classes =
# deux modèles ». Sans exemplars_dir dans config.yml, il n'y a que deux classes (les deux génériques) : les tests passent
# alors comme avant, et ils épinglent (essence, stade) dès que le dossier d'exemplaires est configuré.
STAGES = ("young", "pole", "mature", "old")


def configured_exemplars() -> set[tuple[str, str]]:
    import yaml
    cfg = yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8"))
    d = (((cfg.get("assets") or {}).get("models")) or {}).get("exemplars_dir")
    if not d:
        return set()
    d = Path(d) if Path(d).is_absolute() else ROOT / d
    out = set()
    for p in sorted(d.glob("*.parquet")):
        meta = {k.decode(): v.decode() for k, v in (pq.read_schema(p).metadata or {}).items()}
        out.add((meta["essence"], meta["stage"]))
    return out


def stage_breaks() -> list[float]:
    import yaml
    d = yaml.safe_load((ROOT / "biomes" / "stades" / "stage_breaks.yml").read_text(encoding="utf-8"))
    return [float(v) for v in d["breaks"]]


def model_classes(zone_dir: Path, species, x, y, h) -> tuple[list, np.ndarray]:
    """(classe de chaque arbre, masque des arbres loin d'un seuil de stade). Classe : ('generique', groupe) ou
    (essence du générateur, stade)."""
    available = configured_exemplars()
    rows = list(csv.DictReader(open(SPECIES_CSV, encoding="utf-8", newline="")))
    by = {r["espar"]: r for r in rows}
    with rasterio.open(zone_dir / "site_potential.tif") as r:
        hp = r.read(1)
    rc = [cell_of(a, b) for a, b in zip(x, y)]
    ratio = np.array([float(v) / float(hp[i, j]) for v, (i, j) in zip(h, rc)])
    br = np.array(stage_breaks())
    stage = [STAGES[int((q >= br).sum())] for q in ratio]
    franc = ~np.any(np.abs(ratio[:, None] - br[None, :]) < 0.003, axis=1)
    classes = []
    for s, st in zip(species, stage):
        row = by[str(s)]
        ess = row["tarif_nemeton_code"]
        classes.append((ess, st) if ess and (ess, st) in available else ("generique", row["groupe"]))
    return classes, franc
