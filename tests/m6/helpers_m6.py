"""Outils communs des tests d'acceptation de M6a (mission 069).

Ces tests partent de docs/plans/m6a.md (§3 ligne C, §4, §5, §6, §7), de docs/adr/0007, de docs/spec.md et
des contrats de la mission 068 ; ils ne lisent ni python/sylvigenese/assets_lib ni viewer-massif/scripts.
Une sortie absente est un échec, jamais un « skip » (la CI refuse tout test sauté).

Interface exigée de `assets` (celle de la config, déjà au contrat, et des sorties du plan) :
  - config : `assets.models.exemplars_dir` = dossier de fichiers Parquet `<essence>_<stade>.parquet` ;
  - sorties sous le dossier de la zone : `assets/trees/<espar>_<stade>.glb` (code espar PROPRE de l'essence :
    le premier de species.csv ; jamais le code alias), `assets/trees/generique_<groupe>.glb`,
    `tiles/<année>/*.gltf` (+ .bin), `tiles/index.json`, `massif/index.json`, `massif/<année>/<bloc>.json` ;
  - un refus : code de sortie non nul, message en français qui nomme la cause.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import rasterio
import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tests" / "m4"))
sys.path.insert(0, str(HERE))

import helpers_m4 as H  # noqa: E402
from glb import vertex_hash  # noqa: E402

EXEMPLARS = ROOT / "tests" / "fixtures" / "exemplars_m6"
STAGES = ("young", "pole", "mature", "old")
FIXTURE_ESSENCES = ("Fagus_sylvatica", "Quercus_spec", "Abies_alba")
CONFIG = ROOT / "config.yml"
STAGE_BREAKS = ROOT / "biomes" / "stades" / "stage_breaks.yml"


# ------------------------------------------------------------------ config et exécution
def repo_config() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def write_config(zone_dir: Path, name: str, exemplars_dir: Path | None = EXEMPLARS, fname="config_m6.yml",
                 base: Path | None = None, simulate: dict | None = None, year_step: int | None = None) -> Path:
    """config.yml du dépôt (ou d'un autre fichier), zone changée, exemplars_dir posé (absolu)."""
    cfg = yaml.safe_load((base or CONFIG).read_text(encoding="utf-8"))
    cfg["zone"] = name
    cfg.setdefault("assets", {})
    if "models" not in cfg["assets"]:
        cfg["assets"]["models"] = dict(repo_config()["assets"]["models"])
    if exemplars_dir is None:
        cfg["assets"]["models"].pop("exemplars_dir", None)
    else:
        cfg["assets"]["models"]["exemplars_dir"] = str(exemplars_dir)
    if simulate is not None:
        cfg["simulate"] = simulate
    if year_step is not None:
        cfg["assets"]["year_step"] = year_step
    out = zone_dir / fname
    out.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return out


def exige(zone: dict) -> Path:
    """Dossier d'une zone dont `assets` a réussi ; sinon l'échec dit la sortie du module."""
    p = zone["proc"]
    assert p.returncode == 0, f"assets en échec (code {p.returncode}) :\n{(p.stdout + p.stderr)[-2000:]}"
    return zone["dir"]


def build_zone(name: str, mutate=None, exemplars_dir: Path | None = EXEMPLARS) -> dict:
    zdir, _ = H.clone_zone(name, mutate)
    cfg = write_config(zdir, name, exemplars_dir)
    return {"dir": zdir, "name": name, "config": cfg, "proc": H.run_assets(cfg)}


# ------------------------------------------------------------------ référentiels
def species_rows() -> list[dict]:
    with open(H.SPECIES_CSV, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def owner_of(espar: str) -> tuple[str | None, str | None, str]:
    """(essence du générateur, code espar qui porte le fichier, groupe) d'un code ; (None, None, groupe) sans modèle."""
    rows = species_rows()
    mine = next((r for r in rows if r["espar"] == espar), None)
    assert mine is not None, f"code {espar} absent de contracts/species.csv"
    if not mine["tarif_nemeton_code"]:
        return None, None, mine["groupe"]
    owner = next(r["espar"] for r in rows if r["tarif_nemeton_code"] == mine["tarif_nemeton_code"])
    return mine["tarif_nemeton_code"], owner, mine["groupe"]


def exemplars_available(directory: Path = EXEMPLARS) -> set[tuple[str, str]]:
    out = set()
    for p in sorted(Path(directory).glob("*.parquet")):
        meta = {k.decode(): v.decode() for k, v in (pq.read_schema(p).metadata or {}).items()}
        out.add((meta["essence"], meta["stage"]))
    return out


def exemplar_meta(essence: str, stage: str, directory: Path = EXEMPLARS) -> dict:
    p = Path(directory) / f"{essence}_{stage}.parquet"
    return {k.decode(): v.decode() for k, v in pq.read_schema(p).metadata.items()}


def exemplar_segments(essence: str, stage: str, directory: Path = EXEMPLARS) -> dict[str, np.ndarray]:
    return {k: np.array(v) for k, v in pq.read_table(Path(directory) / f"{essence}_{stage}.parquet").to_pydict().items()}


def expected_model(species: str, stage: str, available=None) -> tuple[str, str]:
    """(nom du modèle sans .glb, genre own|alias|generic) attendu d'un arbre, d'après species.csv et les exemplaires
    disponibles. Pas d'emprunt : sans exemplaire de l'essence, le générique du groupe (Q3)."""
    available = exemplars_available() if available is None else available
    essence, owner, groupe = owner_of(species)
    if essence is None or (essence, stage) not in available:
        return f"generique_{groupe}", "generic"
    return f"{owner}_{stage}", ("own" if owner == species else "alias")


def stage_breaks() -> list[float]:
    d = yaml.safe_load(STAGE_BREAKS.read_text(encoding="utf-8"))
    assert d["stages"] == list(STAGES)
    return list(map(float, d["breaks"]))


def stage_of(ratio: float, breaks=None) -> str:
    """h / h_pot -> stade ; borne basse incluse (contrat biomes.stage_breaks)."""
    b = breaks or stage_breaks()
    return STAGES[sum(ratio >= v for v in b)]


def hpot_of_trees(zone_dir: Path, trees: dict) -> np.ndarray:
    with rasterio.open(zone_dir / "site_potential.tif") as r:
        hp = r.read(1)
    rc = np.array([H.cell_of(x, y) for x, y in zip(trees["x"], trees["y"])])
    return hp[rc[:, 0], rc[:, 1]].astype(float)


def near_break(ratio: np.ndarray, tol=0.003) -> np.ndarray:
    return np.any(np.abs(ratio[:, None] - np.array(stage_breaks())[None, :]) < tol, axis=1)


# ------------------------------------------------------------------ lecture des sorties
def read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def glb_files(zone_dir: Path) -> dict[str, Path]:
    d = zone_dir / "assets" / "trees"
    return {p.stem: p for p in sorted(d.glob("*.glb"))} if d.is_dir() else {}


def tile_instances(zone_dir: Path, year: int | None = None) -> dict:
    """Instances de la zone (ou d'une année), repère monde de la tuile, avec l'empreinte des sommets du
    maillage de chaque instance (float32) et l'ensemble des empreintes de maillage des contenus."""
    worlds, hashes, mesh_hashes = [], [], set()
    sets = [p for p in H.find_tilesets(zone_dir) if year is None or p.parent.name == str(year)]
    for ts in sets:
        for c in H.walk_tileset(ts):
            gltf = H.read_gltf(c["path"])
            cache: dict = {}
            for i, nm in H.instance_nodes(gltf):
                node = gltf["nodes"][i]
                attrs = node["extensions"][H.EXT]["attributes"]
                tr = H.read_accessor(gltf, attrs["TRANSLATION"], c["path"].parent, cache)
                pos = np.vstack([H.read_accessor(gltf, p["attributes"]["POSITION"], c["path"].parent, cache)
                                 for p in gltf["meshes"][node["mesh"]]["primitives"]])
                key = vertex_hash(pos.astype("<f4"))
                mesh_hashes.add(key)
                p = np.c_[tr, np.ones(len(tr))] @ nm.T
                p = p @ H.Y_UP_TO_Z_UP.T
                rtc = gltf.get("extensions", {}).get("CESIUM_RTC", {}).get("center")
                if rtc:
                    p[:, :3] += np.array(rtc)
                p = p @ c["matrix"].T
                worlds.append(p[:, :3])
                hashes.extend([key] * len(tr))
    world = np.vstack(worlds) if worlds else np.zeros((0, 3))
    return {"world": world, "model_hash": np.array(hashes), "mesh_hashes": mesh_hashes}


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dtm_bilinear(zone_dir: Path, x: float, y: float) -> float:
    """Altitude du MNT de la grille (25 m) en (x, y), interpolation bilinéaire entre centres de cellules (plan §8) ;
    undulation 0 sur une zone fictive (zone.yml)."""
    with rasterio.open(zone_dir / "dtm.tif") as r:
        a = r.read(1).astype(float)
        t = r.transform
    fx = (x - t.c) / t.a - 0.5
    fy = (t.f - y) / -t.e - 0.5
    x0, y0 = int(np.floor(fx)), int(np.floor(fy))
    x0, y0 = min(max(x0, 0), a.shape[1] - 2), min(max(y0, 0), a.shape[0] - 2)
    ax, ay = min(max(fx - x0, 0.0), 1.0), min(max(fy - y0, 0.0), 1.0)
    return float((1 - ax) * (1 - ay) * a[y0, x0] + ax * (1 - ay) * a[y0, x0 + 1]
                 + (1 - ax) * ay * a[y0 + 1, x0] + ax * ay * a[y0 + 1, x0 + 1])


def validate(contract: str, path: Path):
    return H.validate(contract, str(path))


NAME_RE = re.compile(r"^(?P<espar>[0-9]{2}[A-Z0-9]{0,3})_(?P<stage>young|pole|mature|old)$")
