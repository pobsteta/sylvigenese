"""Outils communs des tests d'acceptation M3a (mission 039).

Ces tests partent de la spec (docs/spec.md §2, §5, §6, §8, §11), du plan docs/plans/m3a-simulate.md, des
contrats (contracts/, dont dynamics_params et son algorithme de relecture, sim.trees, sim.cells, sim.flags,
run.json), de l'ADR 0004 et des décisions du journal du 25/11/2026 (Q1 à Q4, T1 à T10). Ils ne lisent ni
simulate/src, ni R/, ni python/. Une sortie absente est un échec, jamais un « skip » (la CI refuse tout
test sauté).

Principe de l'oracle : tout ce que `simulate` doit produire (accroissement, mortalité, hauteur, cellules,
comptes) est recalculé ICI, en Python, depuis les entrées de la zone (trees_init, rasters de prepare,
params/*.parquet) et le seul texte des contrats et du plan. Rien n'est lu dans le code du moteur.

CONVENTIONS QUE LE PLAN LAISSE OUVERTES (une seule déclaration ici ; un test qui échoue en dit la variante
qui concorde, pour que l'orchestrateur tranche) :
  - AIRE_DISQUE = 706,858 : la constante écrite dans le plan (π × 15² vaut 706,8583...) ;
  - u : mix = la finalisation SplitMix64 de bench/SPEC.md §2 (avec l'ajout du gamma) ; essence packée
    en u64 = octets ASCII du code, le premier octet de poids fort ; année = l'année simulée (celle de
    la partition qui reçoit l'état) ; numéro d'arbre = rang 0 dans les arbres initiaux triés par tree_id ;
  - la cellule d'un point : colonne = floor((x - x0) / 25), ligne = floor((y0 - y) / 25), cell_id =
    ligne × largeur + colonne (contrat sim.cells).
"""
from __future__ import annotations

import csv
import hashlib
import itertools
import json
import math
import os
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import rasterio
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "zone_fictive"
VALIDATE = ROOT / "contracts" / "validate"
SPECIES_CSV = ROOT / "contracts" / "species.csv"
MASK64 = (1 << 64) - 1

CHAIN_TARGETS = ("prepare", "biomes", "trees", "dynamics", "simulate")
DYNAMICS_OUT = ("params/growth.parquet", "params/mortality.parquet", "params/recruitment.parquet",
                "params/height_curve.parquet", "rapport_dynamics.html")
GAMMA = 0x9E3779B97F4A7C15
AIRE_DISQUE = 706.858          # m2, plan M3a §1 (le texte, pas pi x 225)
AIRE_DISQUE_EXACTE = math.pi * 15.0 ** 2
RAYON = 15.0
AIRE_CELLULE_HA = 0.0625       # plan M3a §5 : 25 m x 25 m
D130_RECRUE = 7.48             # plan M3a §5 (cm)
SEUIL_TIGE = 7.5               # contrat sim.cells : « tiges de 7,5 cm et plus »
SORTES = {"MORT": 1, "NB_RECRUES": 2, "RECRUE_X": 3, "RECRUE_Y": 4}   # plan M3a, aléa
BANDES = ("trophic", "coarse_hydric_700m", "coarse_bioclim_700m")      # bandes 1, 2, 3 de station_gradients.tif
TOL_D130 = 1e-9
RE_RECRUE = re.compile(r"^r(\d+)_(\d{4})_(\d+)$")

def _annee_du_dernier_vol() -> int:
    """Année de la date de vol la plus tardive de chm_date.tif du jeu fictif (jours depuis 1970-01-01)."""
    import datetime
    with rasterio.open(FIXTURE / "chm_date.tif") as r:
        a = r.read(1)
        jours = int(a[a != r.nodata].max())
    return (datetime.date(1970, 1, 1) + datetime.timedelta(days=jours)).year


def _simulate_du_depot() -> dict:
    """Le bloc `simulate` du config.yml versionné (level, seed, t0, years), tel quel."""
    import yaml
    bloc = yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8")).get("simulate") or {}
    manque = {"level", "seed", "t0", "years"} - set(bloc)
    assert not manque, f"config.yml sans bloc simulate complet (mission 034) : manque {sorted(manque)}"
    return {"level": bloc["level"], "seed": bloc["seed"], "t0": bloc["t0"], "years": bloc["years"]}


DEPOT = _simulate_du_depot()
# Configuration nominale des tests : level, graine et horizon du dépôt ; t0 = l'année du dernier vol du jeu fictif.
# Pourquoi pas le t0 du dépôt : « la hauteur ne se recule pas » (le moteur refuse un t0 antérieur à une date de vol, journal
# du 25/11/2026) et le jeu fictif a des dalles de 2022, alors que config.yml dit t0 = 2021 : ce désaccord est un test
# à part (test_la_config_du_depot_tourne_sur_le_jeu_fictif), pas une raison de fausser les 100 ans.
SIM_NOMINAL = {"level": DEPOT["level"], "seed": DEPOT["seed"], "t0": max(DEPOT["t0"], _annee_du_dernier_vol()),
               "years": DEPOT["years"], "threads": 1}



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


def zone_dir(name: str) -> Path:
    return ROOT / "data" / name


def run_make(*targets: str, zone: str, config: Path, timeout: int = 3600) -> subprocess.CompletedProcess:
    cmd = ["make", *targets, f"ZONE={zone}", f"CONFIG={config}"]
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, env=offline_env(), timeout=timeout)


def simulate_command(zone: str, config: Path, extra: tuple[str, ...] = ()) -> str:
    """La ligne que `make simulate` exécute (lue par `make -n`, donc fidèle à la règle de la fiche 038),
    suivie des options de test données. make renvoie toujours 2 quand une règle échoue : il masque les
    codes 2, 3 et 4 de la spec §6 ; on appelle donc la commande elle-même, comme le Makefile."""
    dry = subprocess.run(["make", "-n", "simulate", f"ZONE={zone}", f"CONFIG={config}"], cwd=ROOT,
                         capture_output=True, text=True, env=offline_env())
    lignes = [l for l in dry.stdout.splitlines() if l.strip() and not l.startswith("make")]
    if dry.returncode != 0 or not lignes:
        raise AssertionError(f"`make -n simulate` ne donne aucune commande (code {dry.returncode}) : {dry.stderr[:300]}")
    return " && ".join(lignes) + (" " + " ".join(extra) if extra else "")


def run_simulate(zone: str, config: Path, *extra: str, timeout: int = 3600) -> subprocess.CompletedProcess:
    return subprocess.run(["sh", "-c", simulate_command(zone, config, extra)], cwd=ROOT, capture_output=True,
                          text=True, env=offline_env(), timeout=timeout)


def queue(p, n=1500) -> str:
    return f"code {p.returncode}\nSTDOUT: {p.stdout[-n:]}\nSTDERR: {p.stderr[-n:]}"


def run_validate(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["python3", str(VALIDATE), *args], cwd=ROOT, capture_output=True, text=True)


# ------------------------------------------------------------------ zones
def write_config(zdir: Path, name: str, sim: dict | None) -> Path:
    """config.yml du dépôt, zone changée, bloc `simulate` ajouté (None : aucun bloc)."""
    text = (ROOT / "config.yml").read_text(encoding="utf-8")
    text = re.sub(r"(?m)^zone:\s*\S+", f"zone: {name}", text)
    # le config.yml du dépôt porte déjà un bloc `simulate:` : on le retire (lignes indentées ou commentées qui le suivent)
    text = re.sub(r"(?m)^simulate:\n(?:[ \t#][^\n]*\n?|\n(?=[ \t]))*", "", text)
    if sim is not None:
        text = text.rstrip("\n") + "\n\nsimulate:\n" + "".join(f"  {k}: {v}\n" for k, v in sim.items())
    cfg = zdir / "config_m3.yml"
    cfg.write_text(text, encoding="utf-8")
    return cfg


def make_input_zone(name: str, sim: dict | None = None, mutate=None) -> tuple[Path, Path]:
    """Copie des entrées du jeu fictif (inputs/, params/ sans les sorties de dynamics, zone.yml) sous
    data/<name>/ : la chaîne y repart de zéro. Renvoie (zone_dir, config)."""
    zdir = zone_dir(name)
    if zdir.exists():
        shutil.rmtree(zdir)
    zdir.mkdir(parents=True)
    shutil.copytree(FIXTURE / "inputs", zdir / "inputs")
    shutil.copytree(FIXTURE / "params", zdir / "params")
    shutil.copy(FIXTURE / "zone.yml", zdir / "zone.yml")
    for rel in DYNAMICS_OUT:
        (zdir / rel).unlink(missing_ok=True)
    if mutate is not None:
        mutate(zdir)
    return zdir, write_config(zdir, name, sim)


def clone_zone(src: str, name: str, sim: dict | None, mutate=None) -> tuple[Path, Path]:
    """Copie d'une zone déjà préparée, SANS sim/ : seule `simulate` est à rejouer."""
    zdir = zone_dir(name)
    if zdir.exists():
        shutil.rmtree(zdir)
    shutil.copytree(zone_dir(src), zdir, ignore=shutil.ignore_patterns("sim", "config_m3.yml"))
    if mutate is not None:
        mutate(zdir)
    return zdir, write_config(zdir, name, sim)


def remove_zone(name: str) -> None:
    shutil.rmtree(zone_dir(name), ignore_errors=True)
    data = ROOT / "data"
    try:
        if data.is_dir() and not any(data.iterdir()):
            data.rmdir()
    except OSError:
        pass


def rewrite_params(zdir: Path, fn) -> None:
    """fn(nom_modele_fichier, table pandas) -> table pandas, pour growth, mortality, recruitment, height_curve."""
    for n in ("growth", "mortality", "recruitment", "height_curve"):
        p = zdir / "params" / f"{n}.parquet"
        df = pq.read_table(p).to_pandas()
        out = fn(n, df)
        pq.write_table(pa.Table.from_pandas(out, preserve_index=False, schema=pq.read_schema(p)), p)


def add_ser_effect(zdir: Path, code: str = "H10", growth: float = 0.15, mortality: float = 0.4) -> None:
    """Ajoute le niveau `ser_code=<code>` aux modèles de croissance et de mortalité (le jeu fictif n'en a
    aucun) : sans lui, la lecture de b_ser (ser.tif + ser.csv, contrat dynamics_params) ne serait pas testée."""
    import pandas as pd

    def fn(nom, df):
        val = {"growth": growth, "mortality": mortality}.get(nom)
        if val is None:
            return df
        base = df[df["term"] == "intercept"][["species", "species_group", "model"]].copy()
        base["term"], base["variable"], base["x"] = f"ser_code={code}", "ser_code", np.nan
        base["value"], base["provisoire"], base["source"] = val, True, "essai tests/m3 (niveau de SER fabriqué)"
        return pd.concat([df, base], ignore_index=True)

    rewrite_params(zdir, fn)


# ------------------------------------------------------------------ sorties de sim/
def sim_dir(zdir: Path) -> Path:
    return zdir / "sim"


def partitions(zdir: Path, kind: str) -> dict[int, list[Path]]:
    base = sim_dir(zdir) / kind
    out: dict[int, list[Path]] = {}
    if base.is_dir():
        for d in sorted(base.iterdir()):
            m = re.fullmatch(r"year=(\d{4})", d.name)
            if m and d.is_dir():
                out[int(m.group(1))] = sorted(d.glob("*.parquet"))
    return out


def read_year(zdir: Path, kind: str, year: int):
    """Table pandas d'une partition (toutes les parties) ; `year` vient du nom du dossier year=AAAA si le fichier ne la porte pas (le validateur la refuse dans le fichier, convention Hive)."""
    files = partitions(zdir, kind).get(year, [])
    assert files, f"partition sim/{kind}/year={year} absente"
    import pandas as pd
    frames = []
    for f in files:
        df = pq.read_table(f).to_pandas()
        if "year" in df.columns:
            assert (df["year"] == year).all(), f"{f} : year différent de la partition"
        else:                       # convention Hive du validateur : l'année n'est que dans le nom du dossier
            df["year"] = year
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def read_all_trees(zdir: Path):
    import pandas as pd
    frames = []
    for y, files in sorted(partitions(zdir, "trees").items()):
        for f in files:
            df = pq.read_table(f).to_pandas()
            df["year_dans_fichier"] = df["year"] if "year" in df.columns else np.nan
            df["year"] = y
            df["part_year"] = y
            frames.append(df)
    assert frames, "aucune partition sim/trees"
    return pd.concat(frames, ignore_index=True)


def read_run_json(zdir: Path) -> dict:
    p = sim_dir(zdir) / "run.json"
    assert p.is_file(), "sim/run.json absent"
    return json.loads(p.read_text(encoding="utf-8"))


def sim_digest(zdir: Path, ignore_run_keys=("threads", "duration_s", "memory_estimate_bytes", "config_sha256")) -> dict:
    """Empreinte de tout sim/ : SHA-256 des octets de chaque fichier ; run.json compare ses valeurs, sans les
    champs qui disent le calcul (fils, durée, mémoire estimée, empreinte de la config) et non le résultat."""
    out = {}
    base = sim_dir(zdir)
    for p in sorted(base.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(base))
        if rel == "run.json":
            j = json.loads(p.read_text(encoding="utf-8"))
            out[rel] = json.dumps({k: v for k, v in j.items() if k not in ignore_run_keys}, sort_keys=True)
        else:
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def sim_text_corpus(zdir: Path) -> str:
    """Tout le texte de sim/ (chaînes des Parquet, json, csv, html) : pour chercher une mention."""
    chunks: list[str] = []
    base = sim_dir(zdir)
    for p in sorted(base.rglob("*")) if base.is_dir() else []:
        if p.suffix == ".parquet":
            t = pq.read_table(p)
            for col in t.schema.names:
                if pa.types.is_string(t.schema.field(col).type) or pa.types.is_large_string(t.schema.field(col).type):
                    chunks.extend(str(v) for v in t.column(col).to_pylist() if v is not None)
        elif p.suffix in (".json", ".csv", ".html", ".txt", ".md"):
            chunks.append(p.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)


# ------------------------------------------------------------------ référentiels
def species_groups() -> dict[str, str]:
    with open(SPECIES_CSV, encoding="utf-8", newline="") as f:
        return {r["espar"]: r["groupe"] for r in csv.DictReader(f)}


# ------------------------------------------------------------------ grille et rasters d'une zone
class Grid:
    """grid.tif et rasters de prepare d'une zone, lus avec rasterio (aucun code du projet)."""

    def __init__(self, zdir: Path):
        self.zdir = zdir
        with rasterio.open(zdir / "grid.tif") as r:
            t = r.transform
            self.x0, self.y0, self.res = t.c, t.f, t.a
            self.ncols, self.nrows = r.width, r.height
        self._cache: dict[str, np.ndarray] = {}

    def raster(self, name: str, band: int = 1) -> np.ndarray:
        key = f"{name}:{band}"
        if key not in self._cache:
            with rasterio.open(self.zdir / f"{name}.tif") as r:
                a = r.read(band).astype("float64")
                if r.nodata is not None:
                    a[a == r.nodata] = np.nan
            self._cache[key] = a
        return self._cache[key]

    @property
    def x1(self) -> float:
        return self.x0 + self.ncols * self.res

    @property
    def y1(self) -> float:
        return self.y0 - self.nrows * self.res

    def col_row(self, x, y):
        col = np.floor((np.asarray(x) - self.x0) / self.res).astype(int)
        row = np.floor((self.y0 - np.asarray(y)) / self.res).astype(int)
        return col, row

    def cell_id(self, x, y):
        col, row = self.col_row(x, y)
        return row * self.ncols + col

    def inside(self, x, y):
        col, row = self.col_row(x, y)
        return (col >= 0) & (col < self.ncols) & (row >= 0) & (row < self.nrows)

    def cell_bounds(self, cid: int):
        row, col = divmod(int(cid), self.ncols)
        return (self.x0 + col * self.res, self.x0 + (col + 1) * self.res,
                self.y0 - (row + 1) * self.res, self.y0 - row * self.res)

    def cell_center(self, cid: int):
        xa, xb, ya, yb = self.cell_bounds(cid)
        return (xa + xb) / 2, (ya + yb) / 2

    def sample(self, name: str, x, y, band: int = 1) -> np.ndarray:
        col, row = self.col_row(x, y)
        a = self.raster(name, band)
        return a[row, col]

    def ser_names(self) -> dict[int, str]:
        with open(self.zdir / "ser.csv", encoding="utf-8", newline="") as f:
            return {int(r["value"]): r["name"] for r in csv.DictReader(f)}

    def station(self, x, y) -> dict[str, np.ndarray]:
        """Variables de station de la cellule du point (plan M3a §2) : bandes trophic, hydric, bioclim."""
        return {"trophic": self.sample("station_gradients", x, y, 1),
                "coarse_hydric_700m": self.sample("station_gradients", x, y, 2),
                "coarse_bioclim_700m": self.sample("station_gradients", x, y, 3)}

    def ser_code(self, x, y) -> np.ndarray:
        names = self.ser_names()
        v = self.sample("ser", x, y)
        return np.array([names.get(int(i), "") if np.isfinite(i) else "" for i in v], dtype=object)


# ------------------------------------------------------------------ paramètres : relecture du contrat
def natural_spline(xs, ys):
    """Spline cubique naturelle par les nœuds, selon la description de contracts/tables/params/
    dynamics_params.schema.json (système tridiagonal, algorithme de Thomas). Renvoie f(x) vectorisée."""
    order = np.argsort(xs)
    x = np.asarray(xs, dtype="float64")[order]
    y = np.asarray(ys, dtype="float64")[order]
    n = len(x)
    assert n >= 2 and np.all(np.diff(x) > 0), "nœuds non strictement croissants"
    h = np.diff(x)
    M = np.zeros(n)
    if n > 2:
        a = h[:-1].copy()                      # sous-diagonale  h_{i-1}
        b = 2.0 * (h[:-1] + h[1:])             # diagonale
        c = h[1:].copy()                       # sur-diagonale   h_i
        d = 6.0 * ((y[2:] - y[1:-1]) / h[1:] - (y[1:-1] - y[:-2]) / h[:-1])
        m = n - 2
        for i in range(1, m):                  # Thomas, balayage avant
            w = a[i] / b[i - 1]
            b[i] -= w * c[i - 1]
            d[i] -= w * d[i - 1]
        sol = np.zeros(m)
        sol[-1] = d[-1] / b[-1]
        for i in range(m - 2, -1, -1):
            sol[i] = (d[i] - c[i] * sol[i + 1]) / b[i]
        M[1:-1] = sol

    def f(v):
        v = np.clip(np.asarray(v, dtype="float64"), x[0], x[-1])
        i = np.clip(np.searchsorted(x, v, side="right") - 1, 0, n - 2)
        hi = h[i]
        aa = x[i + 1] - v
        bb = v - x[i]
        return ((M[i] * aa ** 3 + M[i + 1] * bb ** 3) / (6 * hi)
                + (y[i] / hi - M[i] * hi / 6) * aa + (y[i + 1] / hi - M[i + 1] * hi / 6) * bb)

    f.knots = (x[0], x[-1])
    return f


class Params:
    """params/{growth,mortality,recruitment,height_curve}.parquet d'une zone, relus selon le contrat."""

    def __init__(self, zdir: Path):
        import pandas as pd
        frames = []
        for n in ("growth", "mortality", "recruitment", "height_curve"):
            frames.append(pq.read_table(zdir / "params" / f"{n}.parquet").to_pandas())
        self.df = pd.concat(frames, ignore_index=True)
        self.groups = species_groups()
        self._eta_cache: dict = {}
        self._rows_cache: dict = {}
        self._scalar_cache: dict = {}

    def rows(self, model: str, species: str):
        """Lignes du modèle : essence, sinon son groupe, sinon toutes_essences (contrat) ; None si rien."""
        if (model, species) not in self._rows_cache:
            self._rows_cache[(model, species)] = self._rows(model, species)
        return self._rows_cache[(model, species)]

    def _rows(self, model: str, species: str):
        d = self.df[self.df["model"] == model]
        sp = d[d["species"] == species]
        if len(sp):
            return sp
        grp = self.groups.get(species)
        if grp is not None:
            g = d[(d["species"].isna()) & (d["species_group"] == grp)]
            if len(g):
                return g
        t = d[(d["species"].isna()) & (d["species_group"] == "toutes_essences")]
        return t if len(t) else None

    def scalar(self, model: str, species: str, term: str) -> float:
        key = (model, species, term)
        if key not in self._scalar_cache:
            self._scalar_cache[key] = self._scalar(model, species, term)
        return self._scalar_cache[key]

    def _scalar(self, model: str, species: str, term: str) -> float:
        r = self.rows(model, species)
        assert r is not None, f"aucun paramètre {model} pour l'essence {species}"
        v = r[r["term"] == term]["value"]
        assert len(v) == 1, f"terme {term} de {model} ({species}) : {len(v)} lignes"
        return float(v.iloc[0])

    def variables(self, model: str, species: str) -> list[str]:
        r = self.rows(model, species)
        return sorted(set(r["variable"].dropna()) - {"ser_code"}) if r is not None else []

    def eta(self, model: str, species: str, variables: dict[str, np.ndarray], ser_code) -> np.ndarray:
        """η = intercept + Σ f_v(x_v) + b_ser (contrat, §1 de sa description)."""
        r = self.rows(model, species)
        assert r is not None, f"aucun paramètre {model} pour l'essence {species}"
        key = (model, species)
        if key not in self._eta_cache:
            inter = r[r["term"] == "intercept"]["value"]
            assert len(inter) == 1, f"{model}/{species} : intercept absent ou double"
            splines = {}
            for v in sorted(set(r["variable"].dropna()) - {"ser_code"}):
                k = r[(r["variable"] == v) & r["term"].str.startswith("s(")]
                if len(k):
                    splines[v] = natural_spline(k["x"].to_numpy(), k["value"].to_numpy())
            ser = {t.split("=", 1)[1]: float(val) for t, val in zip(r["term"], r["value"]) if t.startswith("ser_code=")}
            self._eta_cache[key] = (float(inter.iloc[0]), splines, ser)
        inter, splines, ser = self._eta_cache[key]
        n = len(next(iter(variables.values())))
        eta = np.full(n, inter, dtype="float64")
        for v, f in splines.items():
            eta += f(variables[v])
        eta += np.array([ser.get(c, 0.0) for c in ser_code], dtype="float64")
        return eta

    def out_of_domain(self, model: str, species: str, variables: dict[str, np.ndarray]) -> dict[str, tuple[int, int]]:
        """Par variable lisse : (sous x_1, au-dessus de x_n), en nombre de valeurs."""
        self.eta(model, species, variables, [""] * len(next(iter(variables.values()))))
        _i, splines, _s = self._eta_cache[(model, species)]
        return {v: (int((variables[v] < f.knots[0]).sum()), int((variables[v] > f.knots[1]).sum()))
                for v, f in splines.items()}


# ------------------------------------------------------------------ concurrence (plan M3a, pas annuel §1)
def competition(x, y, d130, alive=None, aire=AIRE_DISQUE, rayon=RAYON):
    """ba_plot et bal (m²/ha) de chaque arbre : Σ π (d/200)² × 10 000 / aire sur les arbres vivants du
    disque de `rayon` (lui compris) ; bal sur les seuls arbres STRICTEMENT plus gros. Somme en ordre
    de tableau (la tolérance des tests absorbe l'ordre). Renvoie aussi `ambigu` : un arbre dont un voisin
    est à 1e-6 m du rayon, ou de diamètre égal à 1e-12 près (la spec ne tranche pas) n'est pas jugé."""
    x, y, d = map(lambda a: np.asarray(a, dtype="float64"), (x, y, d130))
    vivant = np.ones(len(x), bool) if alive is None else np.asarray(alive, bool)
    g = np.pi * (d / 200.0) ** 2 * 10_000.0 / aire
    g = np.where(vivant, g, 0.0)
    pts = np.column_stack([x, y])
    tree = cKDTree(pts)
    voisins = tree.query_ball_point(pts, r=rayon + 1e-6)
    ba = np.zeros(len(x))
    bal = np.zeros(len(x))
    ambigu = np.zeros(len(x), bool)
    for i, nb in enumerate(voisins):
        nb = np.array(sorted(nb))
        nb = nb[vivant[nb]]
        dist = np.hypot(x[nb] - x[i], y[nb] - y[i])
        if np.any(np.abs(dist - rayon) <= 1e-6):
            ambigu[i] = True
        nb = nb[dist < rayon + 1e-12]
        ba[i] = g[nb].sum()
        autres = nb[nb != i]
        if np.any(np.abs(d[autres] - d[i]) <= 1e-12):
            ambigu[i] = True
        bal[i] = g[nb[d[nb] > d[i]]].sum()
    return ba, bal, ambigu


def predict_step(grid: Grid, params: Params, trees, aire=AIRE_DISQUE):
    """État de début de pas (`trees` : tree_id, species, x, y, d130, vivants) -> d130 après un an, risque
    de mort et variables lues. Accroissement : d130 += 2 exp(η), en moyenne, sans bruit (Q4)."""
    x, y, d, sp = (trees[c].to_numpy() for c in ("x", "y", "d130", "species"))
    ba, bal, ambigu = competition(x, y, d, aire=aire)
    st = grid.station(x, y)
    ser = grid.ser_code(x, y)
    d_new = np.full(len(x), np.nan)
    p_mort = np.full(len(x), np.nan)
    for s in sorted(set(sp)):
        m = sp == s
        v = {"d130": d[m], "ba_plot": ba[m], "bal": bal[m], **{k: a[m] for k, a in st.items()}}
        d_new[m] = d[m] + 2.0 * np.exp(params.eta("growth_gam", s, v, ser[m]))
        p_mort[m] = 1.0 - np.exp(-np.exp(params.eta("mortality_gam", s, v, ser[m])))
    ok = ~ambigu & np.isfinite(d_new) & np.isfinite(p_mort)
    return {"d130": d_new, "p_mort": p_mort, "ba_plot": ba, "bal": bal, "ok": ok, "ambigu": ambigu}


# ------------------------------------------------------------------ aléa (plan M3a, « Aléa et identité entre fils »)
def splitmix_mix(x: int) -> int:
    x = (x + GAMMA) & MASK64
    z = ((x ^ (x >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
    return z ^ (z >> 31)


def u_bench(seed: int, year: int, cell: int, sp: int) -> float:
    """u du banc (bench/SPEC.md §2) : sert à vérifier la finalisation SplitMix64 de cet oracle."""
    x = seed ^ ((year * 0x9E3779B97F4A7C15) & MASK64) ^ ((cell * 0xBF58476D1CE4E5B9) & MASK64) \
        ^ ((sp * 0x94D049BB133111EB) & MASK64)
    return (splitmix_mix(x & MASK64) >> 11) * 2.0 ** -53


def pack_species(code: str, big_endian: bool = True) -> int:
    return int.from_bytes(code.encode("ascii"), "big" if big_endian else "little")


def u_chained(seed: int, year: int, entity: int, species_u64: int, kind: int) -> float:
    """u = mix(mix(mix(mix(mix(seed) ^ année) ^ entité) ^ essence) ^ sorte) >> 11 × 2^-53 (plan M3a, T1)."""
    z = splitmix_mix(seed & MASK64)
    for part in (year, entity, species_u64, kind):
        z = splitmix_mix(z ^ (part & MASK64))
    return (z >> 11) * 2.0 ** -53


# ------------------------------------------------------------------ hauteur (spec §5, plan M3a §3)
def chapman_richards_step(h, a, k, p):
    """Pas d'un an EXACT de H(t) = A (1 - exp(-k t))^p (forme autonome) : u = (H/A)^(1/p), puis
    H' = A (1 - (1 - u) exp(-k))^p. Au plafond (H >= A) : dH = 0, sans fonction min (spec §5)."""
    h = np.asarray(h, dtype="float64")
    a = np.asarray(a, dtype="float64")
    with np.errstate(invalid="ignore", divide="ignore"):
        u = np.clip(h / a, 0.0, 1.0) ** (1.0 / p)
        nouveau = a * (1.0 - (1.0 - u) * math.exp(-k)) ** p
    return np.where(h >= a, h, nouveau)


def korf_step(h, a, b, c, p_f):
    """Pas d'un an de la courbe de Korf du contrat dynamics_params :
    H = a exp(-(p_f b + [ln(a/H_prec)]^(-1/c))^(-c)), H_prec dans ]0, a[."""
    h = np.asarray(h, dtype="float64")
    inner = np.log(a / h) ** (-1.0 / c)
    return a * np.exp(-((p_f * b + inner) ** (-c)))


def korf_class_for(params: "Params", site_potential: float, essence: str = "09") -> int:
    """Classe de fertilité retenue par simulate (contrat dynamics_params, mission 040) : celle dont la hauteur à
    age_ref, obtenue en avançant la formule d'un an à la fois depuis h_ref0 à t_ref0, est la plus proche de
    site_potential ; à égalité, la plus petite classe (journal, 25/11/2026)."""
    a, b, c = (params.scalar("korf", essence, k) for k in "abc")
    t_ref0, h_ref0, age_ref = (params.scalar("korf", essence, k) for k in ("t_ref0", "h_ref0", "age_ref"))
    n = int(round(age_ref - t_ref0))
    assert abs((age_ref - t_ref0) - n) < 1e-12, "âge de référence non entier : règle à préciser"
    meilleur, ecart = None, math.inf
    for i in range(1, 6):
        pf = params.scalar("korf", essence, f"p_f_class{i}")
        hh = h_ref0
        for _ in range(n):
            hh = float(korf_step(hh, a, b, c, pf))
        e = abs(hh - site_potential)
        if e < ecart - 1e-12:
            meilleur, ecart = i, e
    return meilleur


# ------------------------------------------------------------------ jeux d'arbres fabriqués
TREES_COLUMNS = ["tree_id", "x", "y", "species", "d130", "h", "crown_area", "species_source", "d130_source"]


def write_trees_init(zdir: Path, rows: list[dict]) -> None:
    """Réécrit trees_init/trees.parquet avec le schéma de celui de la zone (les colonnes du jeu)."""
    p = zdir / "trees_init" / "trees.parquet"
    schema = pq.read_schema(p)
    for r in rows:
        r.setdefault("crown_area", 20.0)
        r.setdefault("species_source", "nemeton")
        r.setdefault("d130_source", "tarif_etage_b")
    cols = {f.name: [r.get(f.name) for r in rows] for f in schema}
    pq.write_table(pa.table(cols, schema=schema), p)


def read_trees_init(zdir: Path):
    df = pq.read_table(zdir / "trees_init" / "trees.parquet").to_pandas()
    return df


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def chunks(seq, n):
    it = iter(seq)
    while True:
        b = list(itertools.islice(it, n))
        if not b:
            return
        yield b
