"""Outils des tests d'acceptation de `post` : volume, biomasse et carbone (mission 052).

Sources : docs/plans/post-volume-carbone.md (§2, §4, T5 à T10, mission C), décisions de Pascal Q1 à Q6 du 26/11/2026
(pilotage/journal.md), contrats de la mission 051 (contracts/tables/params/tarif.schema.json,
contracts/tables/sim/summary.schema.json 0.2, contracts/tables/sim/summary_zone.schema.json, contracts/json/post.schema.json,
contracts/json/cell_sheet.schema.json v3, contracts/README.md), précision de l'orchestrateur du 26/11/2026 (part = 1 :
null dans la fiche, 0 dans le summary ; terme de domaine absent = grandeur non bornée), et le tarif synthétique du jeu
fictif (tests/fixtures/zone_fictive/params/tarif.parquet, tools/fixtures/make_zone_fictive.py).
Ces tests NE LISENT PAS python/sylvigenese/post.py, import_tarif.py ni assets_lib/ : l'oracle est écrit ici, depuis les
formules des contrats.

ORACLE (une seule déclaration des conventions ; ce qui n'est pas dans un contrat est dit « convention ») :
  - D = d130 de sim/trees, en cm ; H = h, en m (plan §1 ; unités du domaine : dbh en cm, h en m).
  - Feuillus, volume aérien total (contrat params/tarif, modèle volume_feuillus ; README de tarif-nemeton l. 18) :
        ln V = ln(π/4 · D² · H) + a + b · ln(D/30) + c · ln(H/25),
    avec D en MÈTRES dans le cylindre π/4·D²·H (pour des m³) et en CENTIMÈTRES dans D/30 (diamètre de référence de
    30 cm ; resultats/tarif_v5/LISEZMOI.md de tarif-nemeton : V = π/4 · (D/100)² · H · exp(…), D en cm). Le tarif
    synthétique n'a ni sigma_log ni facteur de biais : aucune correction n'est appliquée (rien n'est inventé).
  - Résineux : quand ces tests ont été écrits (mission 052), le contrat ne nommait aucun terme du profil de tige ni de
    E(D). Depuis la mission 053, le contrat params/tarif écrit les deux formes, NEMETON v5 et synthétique du jeu
    fictif (tige = π/4 · (D/100)² · H · (synth_p1 + synth_p2 / 2), V aérien = tige × synth_E ; ADR 0005). L'oracle de
    052 NE RECALCULE PAS le volume d'un résineux : il vérifie ce que le contrat fixe (V aérien = V tige × E, donc
    proportionnel à E ; biomasse, carbone et racines déduits du volume ; domaine ; comptes). Le test exact du sapin
    est confié au testeur (mission 057).
  - Biomasse aérienne (t) = V (m³) × infradensité (kg/m³) / 1000 ; infradensité de l'essence si elle a une ligne, sinon
    celle de son groupe (contracts/species.csv, colonne groupe).
  - Carbone aérien (tC) = biomasse × fraction_carbone du groupe (aérien total, feuillus comme résineux).
  - Racines (tC) = carbone aérien × rapport `racines` du groupe ; colonne à part, jamais ajoutée au carbone aérien.
  - Domaine : bornes fermées [min ; max] ; H/D = h / (d130 / 100) ; un terme absent ne borne pas. Première raison dans
    l'ordre dbh_below, dbh_above, h_below, h_above, hd_below, hd_above (contrat post.run).
  - Essence sans tarif : aucune ligne de volume (volume_feuillus ni profil_tige_resineux) à son code espar. Pas
    d'emprunt : ni par le groupe, ni par tarif_nemeton_code de species.csv (02 et 03 y partagent Quercus_spec).
  - Surface d'une cellule = grid.resolution_m² de config.yml (T5), lue ici dans config.yml.
  - Cellule d'un arbre : cell_id = ligne × 40 + colonne de grid.tif, ligne 0 au nord (helpers_m4.cell_of).
  - Arbre-année : une ligne de sim/trees (vivant à la fin de l'année, ou mort dans l'année, écrit une fois).
  - Type de végétation d'une cellule : vegetation_map.tif et .csv (état initial) ; surface forestière d'un type =
    nombre de cellules du type × surface d'une cellule (contrat summary_zone). Un arbre d'une cellule SANS type (le
    jeu fictif simulé a des recrues en cellule 1423) n'est rangé dans aucun type par l'oracle : rien n'est inventé.
    La règle de post pour ce cas, ouverte au rendu de 052, est écrite depuis la mission 053 (décision de
    l'orchestrateur du 26/11/2026) aux contrats post.run (without_vegetation_type) et summary_zone : la cellule est
    dans sim/summary.parquet, pas dans sim/summary_zone.parquet, et rapport_post.html la liste.
  - rapport_post.html à la racine de la zone, comme les autres rapports de module (convention, plan T10).
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
M4 = HERE.parent / "m4"
if str(M4) not in sys.path:
    sys.path.insert(0, str(M4))

import helpers_m4 as H  # noqa: E402
import helpers_m4_temps as T  # noqa: E402

ROOT = H.ROOT
T0 = 2022
YEARS = 5                 # horizon court (durée de la CI) : 2022 à 2027
STEP = 10                 # assets.year_step du dépôt : années retenues 2022 et 2027
TOL = 1e-9                # recalcul exact (relatif)
POINT_CONNU = (700_012.5, 6_500_987.5)    # EPSG:2154, x est puis y nord : cellule 0 (plan, échantillon terrain n° 1)
REASONS = ("dbh_below", "dbh_above", "h_below", "h_above", "hd_below", "hd_above")
POST_OUTPUTS = ("sim/summary.parquet", "sim/summary_zone.parquet", "sim/post.json")
VOLUME_MODELS = ("volume_feuillus", "profil_tige_resineux")
MENTION_ECO = "non validée écologiquement"
MENTION_VOLUME = "volume aérien total"
MENTION_CARBONE = "carbone aérien"
MENTION_SOL = "sol et bois mort"
MENTION_PARTIEL = "volume partiel"
MENTION_RACINES = "racines"
MENTION_V2 = "volume et carbone non calculés"
D_REF_CM, H_REF_M = 30.0, 25.0   # contrat params/tarif, forme de volume_feuillus


# ------------------------------------------------------------------ processus
def run_post(config: Path, timeout: int = 1800) -> subprocess.CompletedProcess:
    """Le module comme la cible `post` du Makefile, sans réseau, pour lire son code de sortie exact."""
    env = H.offline_env()
    env["PYTHONPATH"] = "python"
    return subprocess.run([sys.executable, "-m", "sylvigenese.post", "--config", str(config)], cwd=ROOT,
                          capture_output=True, text=True, env=env, timeout=timeout)


def queue(p) -> str:
    return T.queue(p)


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def hashes(zone_dir: Path, rels=("sim", "params")) -> dict[str, str]:
    """Empreinte des fichiers sous `rels`, hors sorties de post (ce que post doit lire sans le changer)."""
    out = {}
    for rel in rels:
        base = zone_dir / rel
        for p in (sorted(base.rglob("*")) if base.is_dir() else []):
            r = str(p.relative_to(zone_dir))
            if p.is_file() and r not in POST_OUTPUTS and ".post_en_cours" not in r:
                out[r] = sha256_file(p)
    return out


def post_outputs(zone_dir: Path) -> dict[str, bytes | None]:
    out = {r: ((zone_dir / r).read_bytes() if (zone_dir / r).is_file() else None) for r in POST_OUTPUTS}
    rp = zone_dir / "rapport_post.html"
    out["rapport_post.html"] = rp.read_bytes() if rp.is_file() else None
    return out


# ------------------------------------------------------------------ zones (sous data/, hors dépôt)
IGNORE = (*H.ASSET_DIRS, "sim", ".sim_en_cours", ".post_en_cours", "rapport_post.html", "config_post*.yml",
          "config_m4*.yml", "__pycache__")


def copy_zone(src: Path, dst: Path, link: bool = False) -> None:
    """Copie d'une zone sans sim/ ni sorties de post et d'assets. `link` : liens physiques, sauf params/ (copié pour de
    vrai, car les variantes le réécrivent)."""
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*IGNORE),
                    copy_function=os.link if link else shutil.copy2)
    if link and (dst / "params").is_dir():
        shutil.rmtree(dst / "params")
        shutil.copytree(src / "params", dst / "params")


def remove_zone(name: str) -> None:
    H.remove_zone_copy(name)


def write_config(zone_dir: Path, name: str, years: int = YEARS, **sim) -> Path:
    return T.write_config(zone_dir, name, T.sim_block(years=years, threads=1, **sim), {"year_step": STEP},
                          "config_post.yml")


def cell_area_ha(config: Path) -> float:
    m = re.search(r"(?m)^grid:\s*\n(?:[ \t]+.*\n)*?[ \t]+resolution_m:\s*([0-9.]+)", config.read_text(encoding="utf-8"))
    assert m, f"grid.resolution_m introuvable dans {config}"
    return float(m.group(1)) ** 2 / 10_000.0


# ------------------------------------------------------------------ tarif (contrat params/tarif)
def species_groups() -> dict[str, str]:
    return H.species_group()


class Tarif:
    """params/tarif.parquet relu en dictionnaires : par essence et par groupe, modèle -> terme -> (valeur, unité)."""

    def __init__(self, path: Path):
        assert path.is_file(), f"{path} absent"
        rows = pq.read_table(path).to_pylist()
        self.rows = rows
        self.sp: dict = defaultdict(lambda: defaultdict(dict))
        self.gr: dict = defaultdict(lambda: defaultdict(dict))
        for r in rows:
            target = self.sp[r["essence"]] if r["essence"] else self.gr[r["groupe"]]
            target[r["modele"]][r["terme"]] = (float(r["valeur"]), r["unite"])
        self.groups = species_groups()
        self.commits = {r["source_commit"] for r in rows}
        self.models = {r["modele"] for r in rows}

    def has_volume(self, sp: str) -> bool:
        return sp in self.sp and any(m in self.sp[sp] for m in VOLUME_MODELS)

    def group(self, sp: str) -> str:
        assert sp in self.groups, f"essence {sp} hors de contracts/species.csv"
        return self.groups[sp]

    def is_feuillu_model(self, sp: str) -> bool:
        return "volume_feuillus" in self.sp.get(sp, {})

    def domain(self, sp: str) -> dict[str, float]:
        return {k: v for k, (v, _) in self.sp.get(sp, {}).get("domaine", {}).items()}

    def _value(self, sp: str, model: str, term: str, unit: str | None = None) -> float | None:
        for src in (self.sp.get(sp, {}), self.gr.get(self.group(sp), {})):
            if model in src and term in src[model]:
                v, u = src[model][term]
                if unit is not None:
                    assert u == unit, f"{model}.{term} de {sp} : unité {u}, attendu {unit}"
                return v
        return None

    def density_t_m3(self, sp: str) -> float:
        v = self._value(sp, "infradensite", "infradensite", "kg/m3")
        assert v is not None, f"pas d'infradensité pour {sp}"
        return v / 1000.0

    def carbon_fraction(self, sp: str) -> float:
        v = self._value(sp, "fraction_carbone", "fraction")
        assert v is not None, f"pas de fraction de carbone pour {sp}"
        return v

    def roots_ratio(self, sp: str) -> float | None:
        return self._value(sp, "racines", "ratio")

    def reason(self, sp: str, d: float, h: float) -> str | None:
        """None : arbre calculé ; sinon 'without_tarif' ou la première raison hors domaine."""
        if not self.has_volume(sp):
            return "without_tarif"
        dom = self.domain(sp)
        hd = h / (d / 100.0)
        for name, val, lo, hi in (("dbh", d, "dbh_min", "dbh_max"), ("h", h, "h_min", "h_max"),
                                  ("hd", hd, "hd_min", "hd_max")):
            if lo in dom and val < dom[lo]:
                return f"{name}_below"
            if hi in dom and val > dom[hi]:
                return f"{name}_above"
        return None

    def volume_feuillus(self, sp: str, d: float, h: float) -> float:
        """Volume aérien total d'un feuillu, m³ (formule du contrat ; D en cm, H en m)."""
        m = self.sp[sp]["volume_feuillus"]
        a, b, c = m["a"][0], m["b"][0], m["c"][0]
        return math.pi / 4.0 * (d / 100.0) ** 2 * h * math.exp(a + b * math.log(d / D_REF_CM) + c * math.log(h / H_REF_M))


# ------------------------------------------------------------------ arbres de sim/ et oracle
def read_sim_trees(zone_dir: Path) -> dict[str, np.ndarray]:
    t = T.sim_dataset(zone_dir, "trees").to_table(columns=["tree_id", "year", "species", "x", "y", "d130", "h", "status"])
    return {"tree_id": np.array(t.column("tree_id").to_pylist(), dtype=object),
            "year": t.column("year").to_numpy().astype(int),
            "species": np.array(t.column("species").to_pylist(), dtype=object),
            "x": t.column("x").to_numpy(), "y": t.column("y").to_numpy(),
            "d130": t.column("d130").to_numpy().astype(float), "h": t.column("h").to_numpy().astype(float),
            "status": np.array(t.column("status").to_pylist(), dtype=object)}


def cell_ids(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    return (H.NCOLS * np.floor((H.Y0 - y) / H.RES).astype(int) + np.floor((x - H.X0) / H.RES).astype(int))


class Oracle:
    """Ce que post doit écrire, recalculé depuis sim/trees, params/tarif.parquet, config.yml et les rasters."""

    def __init__(self, zone_dir: Path, config: Path):
        self.dir = zone_dir
        self.area = cell_area_ha(config)
        self.tarif = Tarif(zone_dir / "params" / "tarif.parquet")
        tr = read_sim_trees(zone_dir)
        self.trees = tr
        n = len(tr["year"])
        self.cell = cell_ids(tr["x"], tr["y"])
        self.g = math.pi * (tr["d130"] / 200.0) ** 2
        self.reason = np.array([self.tarif.reason(s, d, h) for s, d, h in zip(tr["species"], tr["d130"], tr["h"])],
                               dtype=object)
        self.computed = np.array([r is None for r in self.reason])
        # volume des seuls feuillus calculés (résineux : NaN, non recalculé, voir l'en-tête)
        vol = np.full(n, np.nan)
        for i in np.nonzero(self.computed)[0]:
            s = tr["species"][i]
            if self.tarif.is_feuillu_model(s):
                vol[i] = self.tarif.volume_feuillus(s, tr["d130"][i], tr["h"][i])
        self.volume = vol
        self.alive = tr["status"] == "alive"
        self.dead = tr["status"] == "dead"
        veg, nd, _, _ = H.read_raster(zone_dir / "vegetation_map.tif")
        names = H.read_names(zone_dir / "vegetation_map.csv")
        self.veg_of_cell = {int(r * H.NCOLS + c): names[int(veg[r, c])]
                            for r, c in zip(*np.nonzero(veg != nd))}
        self.forest_area = defaultdict(float)
        for v in self.veg_of_cell.values():
            self.forest_area[v] += self.area
        self.years = sorted(set(tr["year"].tolist()))

    # --- par (cellule, année, essence), arbres vivants
    def summary(self) -> dict[tuple[int, int, str], dict]:
        out: dict = {}
        tr = self.trees
        for i in np.nonzero(self.alive)[0]:
            k = (int(self.cell[i]), int(tr["year"][i]), str(tr["species"][i]))
            e = out.setdefault(k, {"n": 0, "n_nc": 0, "g": 0.0, "g_nc": 0.0, "v": 0.0, "n_c": 0, "feuillu": True})
            e["n"] += 1
            e["g"] += self.g[i]
            if self.computed[i]:
                e["n_c"] += 1
                if math.isnan(self.volume[i]):
                    e["feuillu"] = False
                else:
                    e["v"] += self.volume[i]
            else:
                e["n_nc"] += 1
                e["g_nc"] += self.g[i]
        for k, e in out.items():
            sp = k[2]
            e["volume_m3_ha"] = e["v"] / self.area if e["feuillu"] else None
            e["stems_not_computed_ha"] = e["n_nc"] / self.area
            e["share"] = e["g_nc"] / e["g"] if e["g"] > 0 else 0.0
            e["species"] = sp
        return out

    # --- par (année, type de végétation, essence)
    def zone(self) -> dict[tuple[int, str, str], dict]:
        out: dict = {}
        self.untyped: set[int] = set()
        tr = self.trees
        for i in range(len(tr["year"])):
            if not (self.alive[i] or self.dead[i]):
                continue
            c = int(self.cell[i])
            if c not in self.veg_of_cell:
                # cellule sans type de végétation (le jeu fictif y a des recrues, cellule 1423) : aucun contrat ne dit
                # où post les range ; l'oracle n'invente pas de type et les met à part (question posée au rendu)
                self.untyped.add(c)
                continue
            k = (int(tr["year"][i]), self.veg_of_cell[c], str(tr["species"][i]))
            e = out.setdefault(k, {"n_alive": 0, "stems_nc": 0, "g": 0.0, "g_nc": 0.0, "v": 0.0, "dead_v": 0.0,
                                   "dead_nc": 0, "dead_c": 0, "feuillu": True})
            vol = self.volume[i]
            if self.computed[i] and math.isnan(vol):
                e["feuillu"] = False
            if self.alive[i]:
                e["n_alive"] += 1
                e["g"] += self.g[i]
                if self.computed[i]:
                    e["v"] += 0.0 if math.isnan(vol) else vol
                else:
                    e["stems_nc"] += 1
                    e["g_nc"] += self.g[i]
            else:
                if self.computed[i]:
                    e["dead_c"] += 1
                    e["dead_v"] += 0.0 if math.isnan(vol) else vol
                else:
                    e["dead_nc"] += 1
        for (y, veg, sp), e in out.items():
            e["forest_area_ha"] = self.forest_area[veg]
            e["share"] = e["g_nc"] / e["g"] if e["g"] > 0 else 0.0
            e["volume_m3"] = e["v"] if e["feuillu"] else None
            e["dead_volume_m3"] = e["dead_v"] if e["feuillu"] else None
        return out

    # --- comptes de post.json
    def counts(self) -> dict:
        tr = self.trees
        ood: dict = defaultdict(lambda: dict.fromkeys(REASONS, 0))
        wt: dict = defaultdict(int)
        for s, r in zip(tr["species"], self.reason):
            if r is None:
                continue
            if r == "without_tarif":
                wt[str(s)] += 1
            else:
                ood[str(s)][r] += 1
        nc = int((~self.computed).sum())
        return {"tree_years_computed": int(self.computed.sum()), "tree_years_not_computed": nc,
                "out_of_domain": {k: dict(v) for k, v in ood.items()}, "without_tarif": dict(wt)}

    def factors(self, sp: str) -> tuple[float, float, float | None]:
        """(t/m³, fraction de carbone, rapport des racines) d'une essence."""
        return self.tarif.density_t_m3(sp), self.tarif.carbon_fraction(sp), self.tarif.roots_ratio(sp)


# ------------------------------------------------------------------ lecture des sorties de post
def read_parquet_rows(path: Path) -> list[dict]:
    assert path.is_file(), f"{path.relative_to(ROOT) if path.is_relative_to(ROOT) else path} absent"
    return pq.read_table(path).to_pylist()


def read_summary(zone_dir: Path) -> dict[tuple[int, int, str], dict]:
    rows = read_parquet_rows(zone_dir / "sim" / "summary.parquet")
    out = {}
    for r in rows:
        k = (int(r["cell_id"]), int(r["year"]), str(r["species"]))
        assert k not in out, f"clé en double dans summary : {k}"
        out[k] = r
    return out


def read_summary_zone(zone_dir: Path) -> dict[tuple[int, str, str], dict]:
    rows = read_parquet_rows(zone_dir / "sim" / "summary_zone.parquet")
    out = {}
    for r in rows:
        k = (int(r["year"]), str(r["vegetation_type"]), str(r["species"]))
        assert k not in out, f"clé en double dans summary_zone : {k}"
        out[k] = r
    return out


def read_post_json(zone_dir: Path) -> dict:
    p = zone_dir / "sim" / "post.json"
    assert p.is_file(), "sim/post.json absent"
    return json.loads(p.read_text(encoding="utf-8"))


def close(a, b, tol=TOL) -> bool:
    return T.close(a, b, tol)


def sans_accent(s: str) -> str:
    return H.sans_accent(s)


# ------------------------------------------------------------------ zone « échantillon » : sim/ écrit à la main
# Quelques arbres de dimensions choisies, à des places connues, pour des valeurs recalculables à la calculette.
# Aucune valeur écologique : zone marquée fictive. (code, essence, d130 cm, h m, cellule (rang dans les cellules
# forestières retenues), décalage est en m, état en 2023). Le premier arbre est AU point connu.
MINI_TREES = [
    ("PA", "09", 40.0, 20.0, 0, 0.0, "alive"),    # A : hêtre calculé, au point (700 012,5 ; 6 500 987,5)
    ("PB", "09", 7.5, 12.0, 0, 2.0, "alive"),     # B : recrue de 7,5 cm, dbh_below
    ("PC", "03", 12.0, 14.0, 1, 0.0, "alive"),    # C : chêne de 12 cm, sous dbh_min 12,5 : dbh_below
    ("PD", "03", 105.0, 30.0, 1, 2.0, "alive"),   # D : chêne de 105 cm : dbh_above
    ("PE", "61", 30.0, 25.0, 2, 0.0, "alive"),    # E : sapin calculé
    ("PF", "61", 10.0, 21.0, 2, 2.0, "alive"),    # F : H/D = 210 > 200 : hd_above
    ("PG", "64", 10.5, 2.9, 2, 4.0, "alive"),     # G : h < 3 (H/D aussi sous 30) : première raison h_below
    ("PH", "62", 20.0, 55.0, 2, 6.0, "alive"),    # H : h > 50 (H/D aussi au-dessus) : première raison h_above
    ("PI", "09", 50.0, 26.0, 3, 0.0, "dead"),     # I : hêtre calculé, mort en 2023 : flux de mortalité
    ("PJ", "09", 7.5, 8.0, 3, 2.0, "dead"),       # J : recrue morte en 2023 : morte non calculée
    ("PK", "09", 10.0, 3.0, 4, 0.0, "alive"),     # K : aux bornes basses exactes (fermées) : calculé
    ("PL", "03", 12.5, 14.0, 4, 2.0, "alive"),    # L : chêne à 12,5 cm exactement : calculé
    ("PM", "02", 30.0, 25.0, 4, 4.0, "alive"),    # M : chêne pédonculé, AUCUNE ligne de tarif : sans tarif
]
MINI_YEARS = (2022, 2023)
MINI_SEED = 42


def mini_cells(zone_dir: Path) -> list[int]:
    """La cellule 0 (point connu), puis les quatre cellules forestières suivantes, par rang."""
    veg, nd, _, _ = H.read_raster(zone_dir / "vegetation_map.tif")
    forest = sorted(int(r * H.NCOLS + c) for r, c in zip(*np.nonzero(veg != nd)))
    assert forest and forest[0] == 0, "la cellule 0 (point connu) doit être forestière"
    return forest[:5]


def mini_rows(zone_dir: Path, year: int) -> list[dict]:
    cells = mini_cells(zone_dir)
    out = []
    for code, sp, d, h, k, dx, etat in MINI_TREES:
        cx, cy = H.cell_centre(cells[k])
        status = "alive" if year == MINI_YEARS[0] else etat
        out.append({"tree_id": f"T{code}", "species": sp, "x": cx + dx, "y": cy, "d130": d, "h": h,
                    "hcb": 0.3 * h, "cw": 2.0, "status": status})
    assert (out[0]["x"], out[0]["y"]) == POINT_CONNU
    return out


def write_mini_sim(zone_dir: Path, config: Path, mutate_rows=None) -> None:
    """sim/ de la zone échantillon (deux années), cohérent : trees, cells (vivants), flags vide, run.json."""
    sim = zone_dir / "sim"
    shutil.rmtree(sim, ignore_errors=True)
    area = cell_area_ha(config)
    for year in MINI_YEARS:
        rows = mini_rows(zone_dir, year)
        if mutate_rows is not None:
            rows = mutate_rows(year, rows)
        d = sim / "trees" / f"year={year}"
        d.mkdir(parents=True)
        cols = ("tree_id", "species", "x", "y", "d130", "h", "hcb", "cw", "status")
        pq.write_table(pa.table({c: pa.array([r[c] for r in rows]) for c in cols}), d / "part-00000.parquet")
        agg: dict = {}
        hdom: dict = {}
        for r in rows:
            if r["status"] != "alive":
                continue
            c = int(cell_ids(np.array([r["x"]]), np.array([r["y"]]))[0])
            e = agg.setdefault((c, r["species"]), [0, 0.0, 0.0])
            e[0] += 1
            e[1] += math.pi * (r["d130"] / 200.0) ** 2
            e[2] += r["d130"]
            hdom[c] = max(hdom.get(c, 0.0), r["h"])
        keys = sorted(agg)
        d = sim / "cells" / f"year={year}"
        d.mkdir(parents=True)
        pq.write_table(pa.table({
            "cell_id": pa.array([k[0] for k in keys], pa.int64()), "species": pa.array([k[1] for k in keys]),
            "stems_ha": pa.array([agg[k][0] / area for k in keys]),
            "basal_area_m2_ha": pa.array([agg[k][1] / area for k in keys]),
            "d130_mean": pa.array([agg[k][2] / agg[k][0] for k in keys]),
            "h_dom_m": pa.array([hdom[k[0]] for k in keys])}), d / "part-00000.parquet")
    pq.write_table(pa.table({"year": pa.array([], pa.int64()), "entity": pa.array([], pa.string()),
                             "kind": pa.array([], pa.string()), "message": pa.array([], pa.string()),
                             "value": pa.array([], pa.float64())}), sim / "flags.parquet")
    run = {"schema_version": 1, "level": "massif", "seed": MINI_SEED, "t0": MINI_YEARS[0],
           "years": len(MINI_YEARS) - 1, "threads": 1, "memory_estimate_bytes": 0, "duration_s": 0.0,
           "config_sha256": sha256_file(config), "zeroed_values": 0, "provisional_share": 1.0,
           "domain_outputs": {"d130": {"below": 0, "above": 0}}, "cells_at_height_ceiling": 0, "edge_disks": 0,
           "mixed_cells": 0, "recruits": 0, "deaths": sum(1 for t in MINI_TREES if t[6] == "dead")}
    (sim / "run.json").write_text(json.dumps(run, indent=1, sort_keys=True), encoding="utf-8")
    (zone_dir / "zone.yml").write_text(
        "schema_version: 1\nfictive: true\nreason: zone échantillon des tests de post (mission 052) ; sim/ écrit par "
        "l'aide de test, aucune valeur écologique\n", encoding="utf-8")


def rewrite_tarif(zone_dir: Path, fn) -> None:
    """Réécrit params/tarif.parquet (copie réelle, jamais un lien) : fn(liste de lignes) -> liste de lignes."""
    p = zone_dir / "params" / "tarif.parquet"
    t = pq.read_table(p)
    rows = fn(t.to_pylist())
    p.unlink()
    pq.write_table(pa.Table.from_pylist(rows, schema=t.schema), p)


# ------------------------------------------------------------------ oracle exact des résineux (mission 057)
# Forme SYNTHÉTIQUE du jeu fictif, écrite au contrat params/tarif (modèles profil_tige_resineux et
# expansion_resineux, mission 053) : tige = π/4 · (D/100)² · H · (synth_p1 + synth_p2 / 2), V aérien = tige × synth_E.
# Exemple du contrat : sapin (61) de 30 cm et 25 m : tige 1,23700 m³, V aérien 1,36070 m³.
# Biomasse, carbone et racines comme en tête de ce fichier. Les « formes » autres que « contrat » sont des formes
# FAUSSES, gardées ici pour prouver que le test exact les distingue (mutations du relecteur de la PR n° 10).
FORMES_RESINEUX = {
    "contrat": lambda p1, p2, e, d, h: math.pi / 4.0 * (d / 100.0) ** 2 * h * (p1 + p2 / 2.0) * e,
    "synth_p2/3": lambda p1, p2, e, d, h: math.pi / 4.0 * (d / 100.0) ** 2 * h * (p1 + p2 / 3.0) * e,
    "p1 et p2 échangés": lambda p1, p2, e, d, h: math.pi / 4.0 * (d / 100.0) ** 2 * h * (p2 + p1 / 2.0) * e,
    "cylindre seul (p1 + p2)": lambda p1, p2, e, d, h: math.pi / 4.0 * (d / 100.0) ** 2 * h * (p1 + p2) * e,
    "(p1 + p2) / 2": lambda p1, p2, e, d, h: math.pi / 4.0 * (d / 100.0) ** 2 * h * (p1 + p2) / 2.0 * e,
    "sans E (volume de tige)": lambda p1, p2, e, d, h: math.pi / 4.0 * (d / 100.0) ** 2 * h * (p1 + p2 / 2.0),
    "E divisé": lambda p1, p2, e, d, h: math.pi / 4.0 * (d / 100.0) ** 2 * h * (p1 + p2 / 2.0) / e,
    "π sans le quart": lambda p1, p2, e, d, h: math.pi * (d / 100.0) ** 2 * h * (p1 + p2 / 2.0) * e,
    "H − 1,30": lambda p1, p2, e, d, h: math.pi / 4.0 * (d / 100.0) ** 2 * (h - 1.3) * (p1 + p2 / 2.0) * e,
    "E au carré": lambda p1, p2, e, d, h: math.pi / 4.0 * (d / 100.0) ** 2 * h * (p1 + p2 / 2.0) * e * e,
}


def resineux_synthetique(tarif: Tarif, sp: str, d: float, h: float, forme: str = "contrat") -> dict[str, float | None]:
    """Volume aérien total (m³), biomasse aérienne (t), carbone aérien (tC) et carbone des racines (tC, None sans
    modèle racines) d'UN résineux du tarif synthétique, recalculés depuis la seule formule du contrat params/tarif
    et les lignes de params/tarif.parquet (terme d'essence d'abord, puis de groupe). Refuse un résineux qui n'a pas
    la forme synthétique : rien n'est pris par défaut."""
    assert tarif.group(sp) == "resineux", f"{sp} n'est pas un résineux (contracts/species.csv)"
    prof = tarif.sp.get(sp, {}).get("profil_tige_resineux", {})
    exp_ = tarif.sp.get(sp, {}).get("expansion_resineux", {})
    assert {"synth_p1", "synth_p2"} <= set(prof) and "synth_E" in exp_, \
        f"{sp} : forme synthétique absente du tarif (termes {sorted(prof)} / {sorted(exp_)})"
    for k, (_, u) in (*prof.items(), *exp_.items()):
        assert u == "sans_unite", f"{sp} : {k} en {u}, sans_unite attendu"
    p1, p2, e = prof["synth_p1"][0], prof["synth_p2"][0], exp_["synth_E"][0]
    v = FORMES_RESINEUX[forme](p1, p2, e, d, h)
    b = v * tarif.density_t_m3(sp)
    c = b * tarif.carbon_fraction(sp)
    r = tarif.roots_ratio(sp)
    return {"volume_m3": v, "biomass_t": b, "carbon_t": c, "carbon_roots_t": None if r is None else c * r}
