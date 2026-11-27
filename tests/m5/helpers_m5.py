"""Outils communs des tests d'acceptation de M5a (mission 061).

Ces tests partent du plan docs/plans/m5a.md (mission C, T1 à T10), des décisions de Pascal Q1 à Q5 du 26/11/2026
(pilotage/journal.md), des contrats de la mission 060 (config, params/regeneration, cohorts_init, sim.cohorts,
sim.cells, sim.flags, run) et du projet d'ADR 0006. Ils ne lisent pas simulate/src. Une sortie absente est un
échec, jamais un « skip » (la CI refuse tout test sauté).

Les aides de M3a (tests/m3/helpers_m3.py : lancement de `make simulate` sans réseau, relecture des splines du contrat
dynamics_params, lecture des partitions) sont IMPORTÉES, pas recopiées (un lien plutôt qu'une copie).

CONVENTIONS QUE LES CONTRATS LAISSENT OUVERTES (une seule déclaration ici ; un test qui échoue en dit la variante) :
  - flux de recrues au niveau SER : exp(η) tiges/ha/an (contrat dynamics_params, recruitment_gam), ajouté en
    espérance (T4) ; au niveau massif, exp(η) × 0,0625 ha par cellule, arrondi aléatoire (M3a) ;
  - ordre mort / recrutement dans l'année : les deux lectures sont admises, S' = S (1 − p) + R ou S' = (S + R)(1 − p),
    pourvu qu'UNE seule vaille pour toute l'exécution ;
  - précision : l'état des classes est en f32 (ADR 0006, choix 3) ; la tolérance d'un écart est donc
    1e-9 × flux + 16 × 2^-24 × (somme des tiges en jeu), jamais plus large ;
  - « ensemencée » : semis/ha > 1e-6 (le stock « en régime » d'un flux de recrutement fabriqué quasi nul, exp(−40),
    reste en dessous) ;
  - noyau tronqué : la fenêtre est le carré de demi-largeur K cellules ; une cellule à moins de K cellules en distance
    euclidienne y est toujours. Les tests n'exigent rien entre le disque et le carré (la troncature, ronde ou carrée,
    n'est pas dite par le contrat)."""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq
import yaml

HERE = Path(__file__).resolve().parent
M3 = HERE.parent / "m3"
for p in (HERE, M3):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import helpers_m3 as H3  # noqa: E402
import ser_fictive as G  # noqa: E402

ROOT = H3.ROOT
VALIDATE = H3.VALIDATE
ENTREES_M3 = H3.ENTREES_FIGEES
FIXTURE = H3.FIXTURE
BINAIRE = ROOT / "simulate" / "target" / "release" / "simulate"
T0 = G.T0_DEFAUT
K_CLASSES = G.CLASSES_DEFAUT
LARGEUR_CLASSE = 5.0
TRONCATURE = 3
# Massif : K = 1 cellule (25 m) ; kernel_scale_m = 3,7 m (forme 1) donne d99 = 24,6 m, couvert (mission 080 : simulate
# refuse un K qui ne couvre pas d99). À cette échelle, une cellule voisine ne reçoit plus que 1e-3 du poids de la
# source (0,43 à 30 m) : la fécondité d'essai est multipliée par 300 pour que le flux de graines entre cellules voisines
# reste de l'ordre d'avant (réglage d'essai, sans valeur écologique). Écrasables par `regeneration` de zone_massif.
ECHELLE_NOYAU_MASSIF = 3.7
FECONDITE_MASSIF = 300_000.0
SEUIL_ZERO = 1e-9
EPS32 = 2.0 ** -24
AIRE_CELLULE_HA = H3.AIRE_CELLULE_HA
SEUIL_SEMIS = 1e-6
SOURCE_EST, SOURCE_NORD = 700_012.5, 6_500_987.5     # point connu (plan m5a, mission D ; EPSG:2154)

queue = H3.queue
offline_env = H3.offline_env
zone_dir = H3.zone_dir
remove_zone = H3.remove_zone
read_run_json = H3.read_run_json
partitions = H3.partitions
Tab = H3.Tab
RE_RECRUE = H3.RE_RECRUE

# Entrées de simulate du massif fictif, figées par M3a (lues, jamais modifiées : tests/m3/reference/ est intouchable).
FICHIERS_MASSIF = ("grid.tif", "h0.tif", "chm_date.tif", "site_potential.tif", "station_gradients.tif", "ser.tif",
                   "ser.csv", "trees_init/trees.parquet", "params/growth.parquet", "params/mortality.parquet",
                   "params/recruitment.parquet", "params/height_curve.parquet")
ESSENCES_MASSIF = ("03", "09", "61", "62", "64")


def sortie(p) -> str:
    return (p.stdout + "\n" + p.stderr).lower()


# ------------------------------------------------------------------ configurations
def sim_ser(years: int, write_step: int = 1, threads: int = 1, **extra) -> dict:
    """Bloc simulate du niveau SER, mode cohorts. Réglages numériques (non écologiques) des tests."""
    s = {"level": "ser", "seed": 42, "t0": T0, "years": years, "threads": threads, "recruitment": "cohorts",
         "regeneration": {"kernel_truncation_cells": TRONCATURE, "zero_threshold": SEUIL_ZERO},
         "ser": {"diameter_class_width_cm": LARGEUR_CLASSE, "diameter_classes": K_CLASSES, "write_step": write_step}}
    s.update(extra)
    return s


def sim_massif(years: int, recruitment: str | None = "cohorts", threads: int = 1, troncature: int = 1, **extra) -> dict:
    s = {"level": "massif", "seed": 42, "t0": H3.SIM_NOMINAL["t0"], "years": years, "threads": threads}
    if recruitment is not None:
        s["recruitment"] = recruitment
    if recruitment == "cohorts":
        s["regeneration"] = {"kernel_truncation_cells": troncature, "zero_threshold": SEUIL_ZERO}
    s.update(extra)
    return s


def write_config(zdir: Path, name: str, sim: dict | None) -> Path:
    """config.yml du dépôt, zone changée, bloc `simulate` remplacé par `sim` (None : aucun bloc), en YAML imbriqué."""
    text = (ROOT / "config.yml").read_text(encoding="utf-8")
    text = re.sub(r"(?m)^zone:\s*\S+", f"zone: {name}", text)
    text = re.sub(r"(?m)^simulate:\n(?:[ \t#][^\n]*\n?|\n(?=[ \t]))*", "", text)
    if sim is not None:
        text = text.rstrip("\n") + "\n\n" + yaml.safe_dump({"simulate": sim}, sort_keys=False, allow_unicode=True)
    cfg = zdir / "config_m5.yml"
    cfg.write_text(text, encoding="utf-8")
    return cfg


# ------------------------------------------------------------------ zones
def zone_ser(name: str, n: int, sim: dict | None, mutate=None, **gen) -> tuple[Path, Path]:
    """SER fictive de N × N sous data/<name>/ (générateur de tests/m5), puis config."""
    zdir = zone_dir(name)
    G.generer(zdir, n, gen.pop("graine", 1), **gen)
    if mutate is not None:
        mutate(zdir)
    return zdir, write_config(zdir, name, sim)


def zone_massif(name: str, sim: dict | None, mutate=None, regeneration: dict | None = None,
                regeneration_rows: list[dict] | None = None) -> tuple[Path, Path]:
    """Massif fictif bâti des entrées figées de M3a (copiées), plus params/allometry.parquet et zone.yml du jeu
    fictif, plus un params/regeneration.parquet synthétique `toutes_essences` (repli du contrat)."""
    remove_zone(name)
    zdir = zone_dir(name)
    zdir.mkdir(parents=True)
    for rel in FICHIERS_MASSIF:
        (zdir / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ENTREES_M3 / rel, zdir / rel)
    shutil.copy(FIXTURE / "params" / "allometry.parquet", zdir / "params" / "allometry.parquet")
    shutil.copy(FIXTURE / "zone.yml", zdir / "zone.yml")
    rows = regeneration_rows if regeneration_rows is not None else \
        G.regeneration_rows(ESSENCES_MASSIF, {"kernel_scale_m": ECHELLE_NOYAU_MASSIF, "fecundity_seeds_per_m2_ba_yr": FECONDITE_MASSIF,
                                **(regeneration or {})},
                            par_essence=False)
    G.write_regeneration(zdir, rows)
    if mutate is not None:
        mutate(zdir)
    return zdir, write_config(zdir, name, sim)


def run_simulate(name: str, cfg: Path, *extra: str, timeout: int = 3600):
    return H3.run_simulate(name, cfg, *extra, timeout=timeout)


TIME_BIN = "/usr/bin/time"
RE_MAXRSS = re.compile(r"Maximum resident set size \(kbytes\):\s*(\d+)")


def mesurer_rss(argv: list, cwd: Path, stdout, stderr, env=None) -> tuple[int, int]:
    """Lance `argv` à travers `/usr/bin/time -v` et renvoie (code de retour, mémoire résidente maximale en octets),
    lue dans « Maximum resident set size ». Pourquoi pas ru_maxrss de wait4 depuis pytest : sous Linux, le pic de
    mémoire du parent (ici la zone N = 1 000 que pytest vient de générer) est hérité par l'enfant à l'exec, et la
    mesure donnerait pytest, non simulate. /usr/bin/time fait son propre fork : l'enfant y repart d'un pic neuf.
    Le rapport de time va dans un fichier (-o), pour ne pas se mêler à la sortie du moteur."""
    assert os.access(TIME_BIN, os.X_OK), f"{TIME_BIN} absent : installer le paquet « time » (apt-get install time)"
    with tempfile.TemporaryDirectory() as td:
        rapport = Path(td) / "time.txt"
        proc = subprocess.run([TIME_BIN, "-v", "-o", str(rapport), *map(str, argv)], cwd=cwd, stdout=stdout,
                              stderr=stderr, env=env)
        texte = rapport.read_text(errors="replace") if rapport.is_file() else ""
    m = RE_MAXRSS.search(texte)
    assert m, f"« Maximum resident set size » introuvable dans le rapport de time :\n{texte}"
    return proc.returncode, int(m.group(1)) * 1024


def run_mesure(cfg: Path, *extra: str, timeout: int = 3600) -> dict:
    """Lance le binaire compilé de simulate (la commande de `make simulate`, sans cargo, qui fausserait la mesure)
    à travers `/usr/bin/time -v` et lit « Maximum resident set size » : la mesure est faite hors du moteur, sur un
    processus neuf (voir mesurer_rss)."""
    ligne = H3.simulate_command(cfg.parent.name, cfg, extra)
    assert " -- " in ligne, f"commande de make simulate inattendue : {ligne}"
    args = ligne.split(" -- ", 1)[1].split()
    assert BINAIRE.is_file(), f"{BINAIRE} absent : compiler simulate en release (tools/ci/run_tests.sh le fait)"
    out_p, err_p = cfg.parent / "m5_stdout.txt", cfg.parent / "m5_stderr.txt"
    with open(out_p, "w") as o, open(err_p, "w") as e:
        code, rss = mesurer_rss([BINAIRE, *args], ROOT, o, e, env=offline_env())
    res = subprocess.CompletedProcess([str(BINAIRE), *args], code, out_p.read_text(errors="replace"),
                                      err_p.read_text(errors="replace"))
    out_p.unlink(missing_ok=True)
    err_p.unlink(missing_ok=True)
    return {"proc": res, "rss_bytes": rss}


def run_validate(*args: str):
    return subprocess.run(["python3", str(VALIDATE), *args], cwd=ROOT, capture_output=True, text=True)


# ------------------------------------------------------------------ lecture des sorties
def read_kind(zdir: Path, kind: str) -> Tab:
    """Toutes les années de sim/<kind> (year = la partition)."""
    base = zdir / "sim" / kind
    assert base.is_dir(), f"sim/{kind} absent"
    t = ds.dataset(base, format="parquet", partitioning="hive").to_table()
    return Tab.from_arrow(t)


def read_flags(zdir: Path) -> Tab:
    p = zdir / "sim" / "flags.parquet"
    assert p.is_file(), "sim/flags.parquet absent"
    return Tab.from_arrow(pq.read_table(p))


def flags_kinds(zdir: Path) -> set:
    t = pq.read_table(zdir / "sim" / "flags.parquet")
    return set(t.column("kind").to_pylist())


def column_types(zdir: Path, kind: str) -> dict:
    fs = [f for fl in partitions(zdir, kind).values() for f in fl]
    assert fs, f"sim/{kind} sans fichier"
    return {f.name: f.type for f in pq.read_schema(fs[0])}


def stems_by_key(t: Tab, year: int, species: tuple, ncell: int) -> np.ndarray:
    """Tiges/ha par (cellule, essence) d'une année de sim/cohorts : tableau (ncell, ns), sommé sur les classes."""
    out = np.zeros((ncell, len(species)))
    m = t["year"] == year
    sp = t["species"][m]
    for j, s in enumerate(species):
        k = sp == s
        np.add.at(out[:, j], t["cell_id"][m][k].astype(np.int64), t["stems_ha"][m][k].astype("float64"))
    return out


# ------------------------------------------------------------------ oracle de la station (modèles synthétiques)
class Station:
    """Variables de station et SER par cellule d'une zone, lues avec rasterio, et relecture des modèles du contrat
    dynamics_params (helpers_m3.Params). Les modèles synthétiques du générateur ne dépendent que de trophic et de la
    SER : exp(η) est exact sans rien supposer de la surface terrière calculée par le moteur."""

    def __init__(self, zdir: Path):
        self.grid = H3.Grid(zdir)
        self.params = H3.Params(zdir)
        self.ncell = self.grid.ncols * self.grid.nrows
        self.trophic = self.grid.raster("station_gradients", 1).reshape(-1)
        names = self.grid.ser_names()
        v = self.grid.raster("ser").reshape(-1)
        self.ser = [names.get(int(x), "") if np.isfinite(x) else "" for x in v]

    def eta(self, model: str, species: str) -> np.ndarray:
        r = self.params.rows(model, species)
        assert r is not None, f"aucun paramètre {model} pour {species}"
        variables = set(v for v in r["variable"].tolist() if v is not None) - {"ser_code"}
        assert variables <= {"trophic"}, f"{model} dépend de {variables} : oracle de station impossible"
        return self.params.eta(model, species, {"trophic": self.trophic}, self.ser)

    def flux_recrues_ha(self, species: str) -> np.ndarray:
        return np.exp(self.eta("recruitment_gam", species))

    def p_mort(self, species: str) -> np.ndarray:
        return 1.0 - np.exp(-np.exp(self.eta("mortality_gam", species)))


def tol(flux, *stems):
    return 1e-9 * np.abs(flux) + 16 * EPS32 * sum(np.abs(s) for s in stems)


# ------------------------------------------------------------------ noyau
def noyau(r_m, scale: float, shape: float):
    return np.exp(-(np.asarray(r_m, dtype="float64") / scale) ** shape)


def cellule_du_point(grid, x: float, y: float) -> tuple[int, int]:
    col, row = grid.col_row(np.array([x]), np.array([y]))
    return int(row[0]), int(col[0])


def origine_pour(row: int, col: int) -> tuple[float, float]:
    """Origine (coin nord-ouest) d'une grille où le point connu est le centre de la cellule (row, col)."""
    return SOURCE_EST - 12.5 - 25.0 * col, SOURCE_NORD + 12.5 + 25.0 * row


def sha_tree(base: Path) -> dict:
    return {str(p.relative_to(base)): H3.sha256_file(p) for p in sorted(base.rglob("*")) if p.is_file()}


IGNORE_RUN = ("threads", "duration_s", "memory_estimate_bytes", "memory_estimate_max_bytes", "memory_peak_rss_bytes",
              "config_sha256")


def sim_digest(zdir: Path) -> dict:
    return H3.sim_digest(zdir, ignore_run_keys=IGNORE_RUN)


class Paresseux:
    """Valeur de fixture calculée au premier usage, DANS le test : une sortie absente fait échouer le test (FAILED,
    avec la cause), au lieu d'une erreur de fixture répétée sans contexte."""

    def __init__(self, f):
        self.f, self.fait, self.v, self.e = f, False, None, None

    def get(self):
        if not self.fait:
            self.fait = True
            try:
                self.v = self.f()
            except AssertionError as e:
                self.e = e
        if self.e is not None:
            raise AssertionError(str(self.e))
        return self.v
