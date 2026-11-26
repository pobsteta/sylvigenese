"""Module `post` (spec §2 ; BRIEF §6, « volume et carbone » ; plan `docs/plans/post-volume-carbone.md`).

Étape du BRIEF codée : §6 (volume par arbre avec le tarif NEMETON, puis biomasse et carbone), §4
(« summary par biome et année ») et §10 (statut provisoire). Décisions de Pascal Q1 à Q5 du 26/11/2026 :
- Q1 : le tarif NEMETON v5, figé à un commit de tarif-nemeton, provisoire, fait foi seul ;
- Q2 : les constantes sont lues dans `params/tarif.parquet` (écrit par `import_tarif`) ; les formules
  sont réécrites ici, en les citant ; aucun code de tarif-nemeton n'est repris ;
- Q3 : un seul volume, le volume AÉRIEN TOTAL (tige et branches, sur écorce) ;
- Q4 : carbone aérien = biomasse aérienne × fraction de carbone ; carbone des racines à part, seulement
  si le modèle `racines` existe (sinon aucune colonne, et le rapport dit pourquoi) ;
- Q5 : un arbre hors du domaine du tarif, ou d'une essence sans tarif, N'EST PAS CALCULÉ : ni
  extrapolation ni emprunt ; il est compté (post.json, summary, rapport).

Entrées : `sim/trees/year=AAAA/*.parquet` (arbres vivants à la fin de l'année, ou morts dans l'année),
`sim/run.json`, `params/tarif.parquet`, `grid.tif`, `vegetation_map.tif` et `.csv`, `config.yml`,
`contracts/species.csv`.
Sorties : `sim/summary.parquet`, `sim/summary_zone.parquet`, `sim/post.json` (contrats `post.summary`,
`post.summary_zone`, `post.run`) et `rapport_post.html` à la racine de la zone. Tout est écrit dans
`sim/.post_en_cours/`, contrôlé par le validateur, puis seulement mis en place ; un refus (code 2, cause
nommée) ne publie rien et laisse les sorties précédentes intactes. Le rejeu rend les mêmes octets (hors
`duration_s` de post.json et la durée écrite dans le rapport).

FORMULES (D = d130 en cm, H = h en m ; formes décrites dans le contrat `import_tarif.tarif`) :
- feuillus (`volume_feuillus`), README de tarif-nemeton l. 18 :
  V = π/4 · (D/100)² · H · exp(a + b ln(D/30) + c ln(H/25) [+ facteur_biais_sigma2 · sigma_log²]) ;
- résineux, forme NEMETON v5 (`profil_tige_resineux` k0, k1, beta, lam, a, x0, sx ; h_ref, D_ref, n_points,
  marge_sommet, u_min) : tige = cylindre de 0 à h_ref, puis profil intégré par la règle des trapèzes de h_ref
  à H − marge_sommet sur n_points ; V aérien = tige × E(D), E(D) = exp(a + b ln(min(D, D_plafond)/D_ref)) ;
- résineux, forme synthétique du jeu fictif (`synth_p1`, `synth_p2`, `synth_E`, sans sens écologique) :
  tige = π/4 · (D/100)² · H · (synth_p1 + synth_p2 / 2), V aérien = tige × synth_E ;
- biomasse aérienne (t) = V aérien × infradensité (kg/m³) / 1000, infradensité constante (`infradensite`)
  ou rho(D) = (rho_moyenne + rho_pente_10cm · (D − D_ref)/pas_D) × facteur_arbre_entier ;
- carbone aérien (tC) = biomasse aérienne × fraction de carbone du groupe (feuillu ou résineux) ;
- racines (tC) = carbone aérien × rapport `racines` du groupe (colonne à part, jamais additionnée).
`post` n'importe ni `simulate` ni `assets` : il ne lit que leurs fichiers.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import os
import re
import shutil
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
import rasterio

from sylvigenese.common import EXIT_IMPOSSIBLE, EXIT_OK, ModuleError, call_validator, read_config

NAME = "post"
STAGING = ".post_en_cours"
MODELS = ("volume_feuillus", "profil_tige_resineux", "expansion_resineux", "infradensite", "fraction_carbone",
          "racines", "domaine")
VOLUME_MODELS = ("volume_feuillus", "profil_tige_resineux")
REASONS = ("dbh_below", "dbh_above", "h_below", "h_above", "hd_below", "hd_above")
DOMAIN_TERMS = {"dbh": ("dbh_min", "dbh_max", "cm"), "h": ("h_min", "h_max", "m"), "hd": ("hd_min", "hd_max", "sans_unite")}
# Forme du contrat volume_feuillus : diamètre et hauteur de référence (README de tarif-nemeton l. 18 ;
# import_tarif vérifie que D_ref = 30 cm et H_ref = 25 m dans parametres_tarif_v5.csv)
D_REF_CM, H_REF_M = 30.0, 25.0
KG_PER_T = 1000.0
PARTITION = re.compile(r"^year=(\d{4})$")
TREE_COLUMNS = ["tree_id", "species", "x", "y", "d130", "h", "status"]
MENTION_ECO = "valeurs techniques : trajectoire non validée écologiquement (M3a)"
NEMETON_PROFILE = ("k0", "k1", "beta", "lam", "a", "x0", "sx")
NEMETON_PROFILE_SHARED = {"h_ref": "m", "D_ref": "cm", "n_points": None, "marge_sommet": "m", "u_min": "sans_unite"}
SYNTH_PROFILE = ("synth_p1", "synth_p2")


def say(message: str) -> None:
    print(f"[{NAME}] {message}", file=sys.stderr)


def root() -> Path:
    return Path(os.environ.get("SYLVIGENESE_ROOT", "."))


def zone_dir(config: dict) -> Path:
    """Même règle que les autres modules : jeu fictif versionné, sinon data/<zone>."""
    zone = config.get("zone")
    if not zone:
        raise ModuleError("config.yml : `zone` manquante")
    if zone == "zone_fictive":
        return root() / "tests" / "fixtures" / "zone_fictive"
    return root() / "data" / zone


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_species_groups(path: Path) -> dict[str, str]:
    """espar -> groupe (feuillu, resineux) de contracts/species.csv."""
    if not path.is_file():
        raise ModuleError(f"contracts/species.csv introuvable : {path}")
    with path.open(encoding="utf-8", newline="") as stream:
        return {row["espar"]: row["groupe"] for row in csv.DictReader(stream)}


# ------------------------------------------------------------------ tarif (contrat import_tarif.tarif)
class Tarif:
    """params/tarif.parquet relu, puis rangé essence par essence. Toute lacune ou forme inconnue est un refus
    (code 2, cause nommée) : aucune valeur n'est prise par défaut, aucun tarif n'est emprunté."""

    def __init__(self, path: Path, groups: dict[str, str]):
        self.path = path
        self.groups = groups
        rows = pq.read_table(path).to_pylist()
        if not rows:
            raise ModuleError(f"{path} : aucune ligne de tarif")
        self.rows = rows
        self.by_species: dict[tuple[str, str], dict[str, tuple[float, str]]] = defaultdict(dict)
        self.by_group: dict[tuple[str, str], dict[str, tuple[float, str]]] = defaultdict(dict)
        for r in rows:
            if r["modele"] not in MODELS:
                raise ModuleError(f"{path} : modèle inconnu « {r['modele']} »")
            if r["essence"]:
                if r["essence"] not in groups:
                    raise ModuleError(f"{path} : essence {r['essence']} absente de contracts/species.csv")
                self.by_species[(r["essence"], r["modele"])][r["terme"]] = (float(r["valeur"]), r["unite"])
            else:
                self.by_group[(r["groupe"], r["modele"])][r["terme"]] = (float(r["valeur"]), r["unite"])
        commits = sorted({r["source_commit"] for r in rows})
        if len(commits) != 1:
            raise ModuleError(f"{path} : plusieurs commits de tarif-nemeton mêlés ({', '.join(commits)}) ; "
                              "un seul tarif fait foi (décision Q1)")
        self.commit = commits[0]
        self.models = [m for m in MODELS if any(r["modele"] == m for r in rows)]
        self.has_roots = "racines" in self.models
        self.provisoire = any(bool(r["provisoire"]) for r in rows)
        self.provisional_share = sum(1 for r in rows if r["provisoire"]) / len(rows)
        if "infradensite" not in self.models:
            raise ModuleError(f"{path} : modèle infradensite absent : la biomasse ne peut pas être calculée "
                              "(rien n'est pris par défaut)")
        if "fraction_carbone" not in self.models:
            raise ModuleError(f"{path} : modèle fraction_carbone absent : le carbone ne peut pas être calculé")
        with_volume = sorted({sp for (sp, m) in self.by_species if m in VOLUME_MODELS})
        self.species = {sp: self._species_model(sp) for sp in with_volume}

    # --- lecture d'un terme : l'essence d'abord, puis son groupe (contracts/species.csv)
    def term(self, sp: str, model: str, term: str, unit: str | None = None, required: bool = True) -> float | None:
        for source in (self.by_species.get((sp, model), {}), self.by_group.get((self.groups[sp], model), {})):
            if term in source:
                value, found_unit = source[term]
                if unit is not None and found_unit != unit:
                    raise ModuleError(f"{self.path} : {model}.{term} de l'essence {sp} en « {found_unit} », "
                                      f"« {unit} » attendu (unité douteuse : rien n'est converti)")
                return value
        if required:
            raise ModuleError(f"{self.path} : terme {term} du modèle {model} absent pour l'essence {sp} "
                              f"(ni à l'essence ni au groupe {self.groups[sp]}) : rien n'est pris par défaut")
        return None

    def terms_of(self, sp: str, model: str) -> set[str]:
        return set(self.by_species.get((sp, model), {})) | set(self.by_group.get((self.groups[sp], model), {}))

    def _check_known(self, sp: str, model: str, known: set[str]) -> None:
        unknown = sorted(self.terms_of(sp, model) - known)
        if unknown:
            raise ModuleError(f"{self.path} : terme(s) {', '.join(unknown)} du modèle {model} (essence {sp}) inconnus "
                              "de la forme écrite au contrat import_tarif.tarif : rien n'est deviné")

    def _expansion_term(self, sp: str, term: str, unit: str) -> float:
        if not self.terms_of(sp, "expansion_resineux"):
            raise ModuleError(f"{self.path} : modèle expansion_resineux absent pour le résineux {sp} : le volume aérien "
                              "total (tige × E) ne peut pas être calculé")
        return self.term(sp, "expansion_resineux", term, unit)

    def _species_model(self, sp: str) -> dict:
        has_hw = (sp, "volume_feuillus") in self.by_species
        has_sw = (sp, "profil_tige_resineux") in self.by_species
        if has_hw and has_sw:
            raise ModuleError(f"{self.path} : l'essence {sp} a deux modèles de volume (volume_feuillus et "
                              "profil_tige_resineux) : on ne choisit pas")
        m: dict = {"group": self.groups[sp]}
        if has_hw:
            self._check_known(sp, "volume_feuillus", {"a", "b", "c", "sigma_log", "facteur_biais_sigma2"})
            m["form"] = "feuillus"
            m["a"], m["b"], m["c"] = (self.term(sp, "volume_feuillus", t) for t in ("a", "b", "c"))
            sigma = self.term(sp, "volume_feuillus", "sigma_log", required=False)
            bias = self.term(sp, "volume_feuillus", "facteur_biais_sigma2", required=False)
            if (sigma is None) != (bias is None):
                raise ModuleError(f"{self.path} : volume_feuillus de l'essence {sp} : sigma_log et facteur_biais_sigma2 "
                                  "vont ensemble (correction de biais du log) ; un seul des deux est donné")
            m["log_bias"] = 0.0 if sigma is None else bias * sigma ** 2
        else:
            synth = self.terms_of(sp, "profil_tige_resineux") & set(SYNTH_PROFILE)
            if synth:
                self._check_known(sp, "profil_tige_resineux", set(SYNTH_PROFILE))
                self._check_known(sp, "expansion_resineux", {"synth_E"})
                m["form"] = "resineux_synthetique"
                m["p1"], m["p2"] = (self.term(sp, "profil_tige_resineux", t, "sans_unite") for t in SYNTH_PROFILE)
                m["E"] = self._expansion_term(sp, "synth_E", "sans_unite")
            else:
                self._check_known(sp, "profil_tige_resineux", set(NEMETON_PROFILE) | set(NEMETON_PROFILE_SHARED))
                self._check_known(sp, "expansion_resineux", {"a", "b", "D_plafond", "D_ref"})
                m["form"] = "resineux_nemeton"
                for t in NEMETON_PROFILE:
                    m[t] = self.term(sp, "profil_tige_resineux", t, "m" if t == "lam" else None)
                for t, unit in NEMETON_PROFILE_SHARED.items():
                    m[t] = self.term(sp, "profil_tige_resineux", t, unit)
                n = m["n_points"]
                if n != int(n) or n < 2:
                    raise ModuleError(f"{self.path} : n_points = {n} pour l'essence {sp} : un entier d'au moins 2 est attendu")
                m["n_points"] = int(n)
                m["E_a"] = self._expansion_term(sp, "a", "sans_unite")
                m["E_b"] = self._expansion_term(sp, "b", "sans_unite")
                m["E_D_plafond"] = self._expansion_term(sp, "D_plafond", "cm")
                m["E_D_ref"] = self._expansion_term(sp, "D_ref", "cm")
        # infradensité : constante, ou fonction de D (tarif NEMETON v5)
        self._check_known(sp, "infradensite", {"infradensite", "rho_moyenne", "rho_pente_10cm", "D_ref", "pas_D",
                                               "facteur_arbre_entier"})
        if not self.terms_of(sp, "infradensite"):
            raise ModuleError(f"{self.path} : modèle infradensite absent pour l'essence {sp} (groupe {self.groups[sp]}) : "
                              "la biomasse ne peut pas être calculée")
        constant = self.term(sp, "infradensite", "infradensite", "kg/m3", required=False)
        if constant is not None:
            m["rho"] = ("constante", constant)
        else:
            m["rho"] = ("nemeton", self.term(sp, "infradensite", "rho_moyenne", "kg/m3"),
                        self.term(sp, "infradensite", "rho_pente_10cm", "kg/m3 par 10 cm"),
                        self.term(sp, "infradensite", "D_ref", "cm"), self.term(sp, "infradensite", "pas_D", "cm"),
                        self.term(sp, "infradensite", "facteur_arbre_entier", "sans_unite"))
        self._check_known(sp, "fraction_carbone", {"fraction"})
        if not self.terms_of(sp, "fraction_carbone"):
            raise ModuleError(f"{self.path} : modèle fraction_carbone absent pour le groupe {self.groups[sp]} "
                              f"(essence {sp}) : le carbone ne peut pas être calculé")
        m["fraction"] = self.term(sp, "fraction_carbone", "fraction", "sans_unite")
        if not 0.0 < m["fraction"] <= 1.0:
            raise ModuleError(f"{self.path} : fraction de carbone {m['fraction']} pour {sp} hors de ]0 ; 1]")
        if self.has_roots:
            self._check_known(sp, "racines", {"ratio"})
            if not self.terms_of(sp, "racines"):
                raise ModuleError(f"{self.path} : le modèle racines existe mais n'a pas de rapport pour le groupe "
                                  f"{self.groups[sp]} (essence {sp}) : la colonne carbon_roots serait en partie vide")
            m["roots"] = self.term(sp, "racines", "ratio", "sans_unite")
        self._check_known(sp, "domaine", {t for lo, hi, _ in DOMAIN_TERMS.values() for t in (lo, hi)})
        m["domain"] = {}
        for name, (lo, hi, unit) in DOMAIN_TERMS.items():
            m["domain"][name] = (self.term(sp, "domaine", lo, unit, required=False),
                                 self.term(sp, "domaine", hi, unit, required=False))
        return m


# ------------------------------------------------------------------ calcul par arbre
def stem_volume_nemeton(m: dict, d: np.ndarray, h: np.ndarray, chunk: int = 20000) -> np.ndarray:
    """Volume de tige entière sur écorce des résineux, m³ (forme NEMETON v5, contrat import_tarif.tarif) :
    cylindre de 0 à h_ref au diamètre D, puis profil intégré par la règle des trapèzes de h_ref à H − marge_sommet
    sur n_points hauteurs. Calcul par paquets d'arbres (mémoire bornée)."""
    h0, eps, umin, n = m["h_ref"], m["marge_sommet"], m["u_min"], m["n_points"]
    if (h <= h0 + eps).any():
        raise ModuleError(f"résineux de hauteur inférieure à h_ref + marge_sommet ({h0 + eps} m) dans le domaine : "
                          "le profil de tige ne s'intègre pas ; rien n'est deviné")
    t = np.linspace(0.0, 1.0, n)
    out = np.empty(len(d))
    for start in range(0, len(d), chunk):
        dd, hh = d[start:start + chunk, None], h[start:start + chunk, None]
        hg = h0 + t[None, :] * (hh - h0 - eps)
        x = np.clip((hg - h0) / (hh - h0), 0.0, 1.0)
        u = np.clip(1.0 - x, umin, None)
        kk = np.maximum(m["k0"] + (m["k1"] - m["k0"]) / (1.0 + np.exp(-(x - m["x0"]) / m["sx"]))
                        + m["a"] * np.log(dd / m["D_ref"]), 0.0)
        dg = dd / 100.0 * np.exp(0.5 * kk * np.log(u) + m["beta"] * (np.exp(-(hg - h0) / m["lam"]) - 1.0))
        area = np.pi * dg ** 2 / 4.0
        integral = ((area[:, 1:] + area[:, :-1]) / 2.0 * np.diff(hg, axis=1)).sum(axis=1)
        out[start:start + chunk] = integral + h0 * np.pi * (dd[:, 0] / 100.0) ** 2 / 4.0
    return out


def aerial_volume(m: dict, d: np.ndarray, h: np.ndarray) -> np.ndarray:
    """Volume aérien total sur écorce (tige et branches), m³, des arbres calculés d'une essence."""
    cylinder = np.pi / 4.0 * (d / 100.0) ** 2 * h
    if m["form"] == "feuillus":
        return cylinder * np.exp(m["a"] + m["b"] * np.log(d / D_REF_CM) + m["c"] * np.log(h / H_REF_M) + m["log_bias"])
    if m["form"] == "resineux_synthetique":
        return cylinder * (m["p1"] + m["p2"] / 2.0) * m["E"]
    expansion = np.exp(m["E_a"] + m["E_b"] * np.log(np.minimum(d, m["E_D_plafond"]) / m["E_D_ref"]))
    return stem_volume_nemeton(m, d, h) * expansion


def density_t_m3(m: dict, d: np.ndarray) -> np.ndarray:
    if m["rho"][0] == "constante":
        rho = np.full(len(d), m["rho"][1])
    else:
        _, mean, slope, d_ref, step, factor = m["rho"]
        rho = (mean + slope * (d - d_ref) / step) * factor
    if (rho <= 0).any():
        raise ModuleError(f"infradensité négative ou nulle pour un diamètre de {float(d[rho <= 0][0]):g} cm : "
                          "la forme rho(D) sort de son sens ; rien n'est corrigé")
    return rho / KG_PER_T


def first_reason(m: dict, d: np.ndarray, h: np.ndarray) -> np.ndarray:
    """Indice de la première raison hors domaine (ordre de REASONS), -1 si l'arbre est dans le domaine.
    Bornes fermées ; un terme absent ne borne pas (la source ne borne pas cette grandeur)."""
    reason = np.full(len(d), -1, dtype=np.int64)
    values = {"dbh": d, "h": h, "hd": h / (d / 100.0)}
    k = 0
    for name in ("dbh", "h", "hd"):
        lo, hi = m["domain"][name]
        for bound, test in ((lo, lambda v, b: v < b), (hi, lambda v, b: v > b)):
            if bound is not None:
                hit = (reason < 0) & test(values[name], bound)
                reason[hit] = k
            k += 1
    return reason


# ------------------------------------------------------------------ lecture de sim/ et des rasters
def check_run(zone: Path, config_path: Path) -> tuple[dict, list[int]]:
    sim = zone / "sim"
    if not sim.is_dir():
        raise ModuleError(f"{sim} absent : post vient après simulate (relancer make simulate)")
    run_path = sim / "run.json"
    if not run_path.is_file():
        raise ModuleError(f"{run_path} absent : sim/ sans run.json vient d'un run interrompu ; relancer simulate")
    try:
        run = json.loads(run_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ModuleError(f"{run_path} illisible : {error}") from error
    expected = sha256_file(config_path)
    if run.get("config_sha256") != expected:
        raise ModuleError(f"l'empreinte sha256 de config.yml ({expected[:12]}…) diffère de config_sha256 de sim/run.json "
                          f"({str(run.get('config_sha256'))[:12]}…) : sim/ vient d'un autre réglage ; relancer simulate")
    base = sim / "trees"
    years = sorted(int(m.group(1)) for d in (base.iterdir() if base.is_dir() else []) if (m := PARTITION.match(d.name)))
    t0, horizon = run.get("t0"), run.get("years")
    if not isinstance(t0, int) or not isinstance(horizon, int):
        raise ModuleError(f"{run_path} : t0 et years attendus (entiers)")
    if years != list(range(t0, t0 + horizon + 1)):
        raise ModuleError(f"sim/trees : années {years[:3]}…{years[-3:] if years else ''} ; attendu toutes les années de "
                          f"{t0} à {t0 + horizon} (run.json) : sim/ incomplet ou mêlé")
    return run, years


def read_grid(zone: Path) -> dict:
    """Transformation de grid.tif, type de végétation de chaque cellule (état initial) et surface d'une cellule."""
    for name in ("grid.tif", "vegetation_map.tif", "vegetation_map.csv"):
        if not (zone / name).is_file():
            raise ModuleError(f"{zone / name} introuvable (sortie de prepare ou de biomes)")
    with rasterio.open(zone / "grid.tif") as src:
        width, height, transform = src.width, src.height, src.transform
    with rasterio.open(zone / "vegetation_map.tif") as src:
        if (src.width, src.height, src.transform) != (width, height, transform):
            raise ModuleError("vegetation_map.tif n'est pas aligné sur grid.tif")
        veg, nodata = src.read(1), src.nodata
    with open(zone / "vegetation_map.csv", encoding="utf-8", newline="") as stream:
        names = {int(r["value"]): r["name"] for r in csv.DictReader(stream)}
    veg_of_cell = np.full(width * height, -1, dtype=np.int64)
    flat = veg.ravel()
    valid = flat != nodata if nodata is not None else np.ones(len(flat), bool)
    unknown = sorted({int(v) for v in flat[valid]} - set(names))
    if unknown:
        raise ModuleError(f"vegetation_map.tif : valeur(s) {unknown[:5]} absente(s) de vegetation_map.csv")
    type_names = sorted({names[int(v)] for v in flat[valid]})
    index = {name: i for i, name in enumerate(type_names)}
    veg_of_cell[valid] = [index[names[int(v)]] for v in flat[valid]]
    return {"width": width, "height": height, "transform": transform, "veg_of_cell": veg_of_cell,
            "type_names": type_names}


def read_year(zone: Path, year: int, groups: dict[str, str]) -> dict[str, np.ndarray]:
    """Arbres d'une année ; tree_id unique, status connu, essence du référentiel, d130 et h positifs et finis."""
    files = sorted((zone / "sim" / "trees" / f"year={year}").glob("*.parquet"))
    if not files:
        raise ModuleError(f"sim/trees/year={year} vide")
    parts = []
    for f in files:
        names = pq.read_schema(f).names
        missing = [c for c in TREE_COLUMNS if c not in names]
        if missing:
            raise ModuleError(f"{f} : colonne(s) {', '.join(missing)} absente(s) (contrat simulate.trees)")
        parts.append(pq.ParquetFile(f).read(columns=TREE_COLUMNS))
    table = pa.concat_tables(parts)
    if pc.count_distinct(table.column("tree_id")).as_py() != table.num_rows:
        ids, counts = np.unique(np.array(table.column("tree_id").to_pylist(), dtype=object), return_counts=True)
        raise ModuleError(f"sim/trees/year={year} : tree_id en double ({int((counts > 1).sum())}, par exemple "
                          f"{ids[counts > 1][0]}) ; un tree_id doit être unique dans une année")
    species = np.array(table.column("species").to_pylist(), dtype=object)
    unknown = sorted(set(species.tolist()) - set(groups))
    if unknown:
        raise ModuleError(f"sim/trees/year={year} : essence(s) {', '.join(map(str, unknown))} absente(s) de "
                          "contracts/species.csv (codes espar) : rien n'est rattaché par ressemblance")
    status = np.array(table.column("status").to_pylist(), dtype=object)
    bad = sorted(set(status.tolist()) - {"alive", "dead"})
    if bad:
        raise ModuleError(f"sim/trees/year={year} : status inconnu {bad} (alive ou dead attendus)")
    out = {"species": species, "alive": status == "alive"}
    for name in ("x", "y", "d130", "h"):
        out[name] = table.column(name).to_numpy().astype("float64")
    for name in ("d130", "h"):
        v = out[name]
        if not np.isfinite(v).all() or (v <= 0).any():
            raise ModuleError(f"sim/trees/year={year} : {name} nul, négatif ou non fini : rien n'est calculé à sa place")
    if len(out["d130"]) and out["d130"].max() < 3.0:
        raise ModuleError(f"sim/trees/year={year} : tous les d130 sont sous 3 : ils semblent en mètres, le tarif les "
                          "attend en centimètres ; rien n'est converti")
    return out


# ------------------------------------------------------------------ calcul d'une année
def compute_year(trees: dict, tarif: Tarif, grid: dict) -> dict:
    """Par arbre : raison hors domaine (ou sans tarif), volume, biomasse, carbone ; puis cellule et type."""
    n = len(trees["d130"])
    tr = grid["transform"]
    col = np.floor((trees["x"] - tr.c) / tr.a).astype(np.int64)
    row = np.floor((trees["y"] - tr.f) / tr.e).astype(np.int64)
    outside = (col < 0) | (col >= grid["width"]) | (row < 0) | (row >= grid["height"])
    if outside.any():
        raise ModuleError(f"{int(outside.sum())} arbre(s) hors de grid.tif (x est, y nord, EPSG:2154)")
    cell = row * grid["width"] + col
    reason = np.full(n, -1, dtype=np.int64)            # -1 calculé ; 0..5 hors domaine ; 6 sans tarif
    volume = np.zeros(n)
    biomass = np.zeros(n)
    carbon = np.zeros(n)
    roots = np.zeros(n)
    codes, inverse = np.unique(trees["species"], return_inverse=True)
    for k, sp in enumerate(codes.tolist()):
        idx = np.nonzero(inverse == k)[0]
        m = tarif.species.get(sp)
        if m is None:
            reason[idx] = len(REASONS)
            continue
        d, h = trees["d130"][idx], trees["h"][idx]
        r = first_reason(m, d, h)
        reason[idx] = r
        ok = idx[r < 0]
        if len(ok):
            v = aerial_volume(m, trees["d130"][ok], trees["h"][ok])
            b = v * density_t_m3(m, trees["d130"][ok])
            c = b * m["fraction"]
            volume[ok], biomass[ok], carbon[ok] = v, b, c
            if tarif.has_roots:
                roots[ok] = c * m["roots"]
    if not (np.isfinite(volume).all() and (volume >= 0).all()):
        raise ModuleError("volume non fini ou négatif calculé : arrêt plutôt qu'une valeur fausse")
    return {"species": trees["species"], "cell": cell, "veg": grid["veg_of_cell"][cell], "alive": trees["alive"],
            "g": np.pi * (trees["d130"] / 200.0) ** 2, "reason": reason, "volume": volume, "biomass": biomass,
            "carbon": carbon, "roots": roots}


def group_sums(keys: list[np.ndarray], mask: np.ndarray, values: dict[str, np.ndarray]) -> tuple[list[np.ndarray], dict]:
    """Sommes des `values` (sur `mask`) par clé composée, dans l'ordre croissant des clés ; ordre de sommation
    fixe (np.bincount), donc rejeu identique à l'octet près."""
    sel = np.nonzero(mask)[0]
    if not len(sel):
        return [k[:0] for k in keys], {name: np.zeros(0) for name in values}
    stacked = np.rec.fromarrays([k[sel] for k in keys])
    uniq, inverse = np.unique(stacked, return_inverse=True)
    out = {name: np.bincount(inverse, weights=v[sel], minlength=len(uniq)) for name, v in values.items()}
    return [np.asarray(uniq[f]) for f in uniq.dtype.names], out


# ------------------------------------------------------------------ exécution
class Accumulator:
    """Lignes de summary et de summary_zone, comptes de post.json et éléments du rapport, année par année."""

    def __init__(self, tarif: Tarif, grid: dict, area_ha: float):
        self.tarif, self.grid, self.area = tarif, grid, area_ha
        self.summary: dict[str, list] = defaultdict(list)
        self.zone: dict[str, list] = defaultdict(list)
        self.ood: dict[str, list[int]] = defaultdict(lambda: [0] * len(REASONS))
        self.without: dict[str, int] = defaultdict(int)
        self.computed = 0
        self.not_computed = 0
        self.untyped_cells: set[int] = set()
        self.untyped_tree_years = 0
        self.untyped_rows: list[tuple] = []
        self.by_year: list[tuple] = []
        forest = grid["veg_of_cell"][grid["veg_of_cell"] >= 0]
        self.forest_area = np.bincount(forest, minlength=len(grid["type_names"])) * area_ha

    def add(self, year: int, t: dict) -> None:
        computed = t["reason"] < 0
        alive, dead = t["alive"], ~t["alive"]
        self.computed += int(computed.sum())
        self.not_computed += int((~computed).sum())
        codes, inverse = np.unique(t["species"], return_inverse=True)
        for k, sp in enumerate(codes.tolist()):
            r = t["reason"][inverse == k]
            if sp in self.tarif.species:
                counts = np.bincount(r[r >= 0], minlength=len(REASONS))
                if counts.any():
                    self.ood[sp] = [a + int(b) for a, b in zip(self.ood[sp], counts)]
            else:
                self.without[sp] += len(r)
        sp_index = inverse.astype(np.int64)
        nc = ~computed
        one = np.ones(len(computed))
        values = {"n": one, "n_nc": nc * 1.0, "n_c": computed * 1.0, "g": t["g"], "g_nc": t["g"] * nc,
                  "v": t["volume"], "b": t["biomass"], "c": t["carbon"], "r": t["roots"]}
        # par (cellule, essence), arbres vivants
        (cells, sps), s = group_sums([t["cell"], sp_index], alive, values)
        share = np.where(s["n_c"] == 0, 1.0, np.where(s["n_nc"] == 0, 0.0, s["g_nc"] / np.where(s["g"] > 0, s["g"], 1.0)))
        a = self.area
        self.summary["cell_id"].extend(cells.tolist())
        self.summary["year"].extend([year] * len(cells))
        self.summary["species"].extend(codes[sps].tolist())
        self.summary["volume_m3_ha"].extend((s["v"] / a).tolist())
        self.summary["biomass_t_ha"].extend((s["b"] / a).tolist())
        self.summary["carbon_t_ha"].extend((s["c"] / a).tolist())
        if self.tarif.has_roots:
            self.summary["carbon_roots_t_ha"].extend((s["r"] / a).tolist())
        self.summary["stems_not_computed_ha"].extend((s["n_nc"] / a).tolist())
        self.summary["basal_area_not_computed_share"].extend(share.tolist())
        # par (type de végétation, essence) : vivants et morts de l'année ; cellules sans type à part
        typed = t["veg"] >= 0
        live_values = {k: values[k] for k in ("n", "n_nc", "n_c", "g", "g_nc", "v", "b", "c", "r")}
        dead_values = {"dv": t["volume"], "dc": t["carbon"], "dnc": nc * 1.0, "dn": one}
        (zv, zs), zl = group_sums([t["veg"], sp_index], typed & alive, live_values)
        (dv_, ds_), zd = group_sums([t["veg"], sp_index], typed & dead, dead_values)
        rows: dict[tuple[int, int], dict] = {}
        for i, key in enumerate(zip(zv.tolist(), zs.tolist())):
            rows.setdefault(key, {})["live"] = {k: float(v[i]) for k, v in zl.items()}
        for i, key in enumerate(zip(dv_.tolist(), ds_.tolist())):
            rows.setdefault(key, {})["dead"] = {k: float(v[i]) for k, v in zd.items()}
        for (veg, spi) in sorted(rows):
            live = rows[(veg, spi)].get("live", dict.fromkeys(live_values, 0.0))
            dd = rows[(veg, spi)].get("dead", dict.fromkeys(dead_values, 0.0))
            area = float(self.forest_area[veg])
            if live["n"] == 0:
                zshare = 0.0
            elif live["n_c"] == 0:
                zshare = 1.0
            elif live["n_nc"] == 0:
                zshare = 0.0
            else:
                zshare = live["g_nc"] / live["g"]
            z = self.zone
            z["year"].append(year)
            z["vegetation_type"].append(self.grid["type_names"][veg])
            z["species"].append(str(codes[spi]))
            z["forest_area_ha"].append(area)
            z["volume_m3"].append(live["v"])
            z["biomass_t"].append(live["b"])
            z["carbon_t"].append(live["c"])
            if self.tarif.has_roots:
                z["carbon_roots_t"].append(live["r"])
            z["volume_m3_ha"].append(live["v"] / area)
            z["biomass_t_ha"].append(live["b"] / area)
            z["carbon_t_ha"].append(live["c"] / area)
            if self.tarif.has_roots:
                z["carbon_roots_t_ha"].append(live["r"] / area)
            z["dead_volume_m3"].append(dd["dv"])
            z["dead_carbon_t"].append(dd["dc"])
            z["dead_stems_not_computed"].append(int(round(dd["dnc"])))
            z["stems_not_computed"].append(int(round(live["n_nc"])))
            z["basal_area_not_computed_share"].append(zshare)
        # cellules sans type de végétation (décision de l'orchestrateur du 26/11/2026) : comptées, listées
        if (~typed).any():
            (uc,), us = group_sums([t["cell"]], ~typed, {"alive": alive * 1.0, "dead": dead * 1.0,
                                                          "nc": (alive & nc) * 1.0, "v": t["volume"] * alive,
                                                          "c": t["carbon"] * alive})
            self.untyped_cells.update(uc.tolist())
            self.untyped_tree_years += int((~typed).sum())
            for i, c in enumerate(uc.tolist()):
                self.untyped_rows.append((c, year, int(us["alive"][i]), int(us["nc"][i]), float(us["v"][i]),
                                          float(us["c"][i]), int(us["dead"][i])))
        g_alive = float(t["g"][alive].sum())
        g_nc = float(t["g"][alive & nc].sum())
        self.by_year.append((year, int(alive.sum()), int((alive & nc).sum()), g_nc / g_alive if g_alive else 0.0,
                             float(t["volume"][alive].sum()), float(t["carbon"][alive].sum()), int(dead.sum())))


def summary_schema(has_roots: bool) -> pa.Schema:
    fields = [("cell_id", pa.int64()), ("year", pa.int64()), ("species", pa.string()), ("volume_m3_ha", pa.float64()),
              ("biomass_t_ha", pa.float64()), ("carbon_t_ha", pa.float64())]
    if has_roots:
        fields.append(("carbon_roots_t_ha", pa.float64()))
    fields += [("stems_not_computed_ha", pa.float64()), ("basal_area_not_computed_share", pa.float64()),
               ("provisoire", pa.bool_())]
    return pa.schema(fields)


def zone_schema(has_roots: bool) -> pa.Schema:
    fields = [("year", pa.int64()), ("vegetation_type", pa.string()), ("species", pa.string()),
              ("forest_area_ha", pa.float64()), ("volume_m3", pa.float64()), ("biomass_t", pa.float64()),
              ("carbon_t", pa.float64())]
    if has_roots:
        fields.append(("carbon_roots_t", pa.float64()))
    fields += [("volume_m3_ha", pa.float64()), ("biomass_t_ha", pa.float64()), ("carbon_t_ha", pa.float64())]
    if has_roots:
        fields.append(("carbon_roots_t_ha", pa.float64()))
    fields += [("dead_volume_m3", pa.float64()), ("dead_carbon_t", pa.float64()), ("dead_stems_not_computed", pa.int64()),
               ("stems_not_computed", pa.int64()), ("basal_area_not_computed_share", pa.float64()),
               ("provisoire", pa.bool_())]
    return pa.schema(fields)


def write_table(columns: dict[str, list], schema: pa.Schema, provisoire: bool, path: Path) -> None:
    n = len(columns[schema.names[0]])
    data = {name: (columns[name] if name != "provisoire" else [provisoire] * n) for name in schema.names}
    pq.write_table(pa.table(data, schema=schema), path)


def trees_fingerprint(zone: Path) -> str:
    """Empreinte de la liste triée (chemin relatif, empreinte du fichier) des partitions de sim/trees."""
    base = zone / "sim" / "trees"
    lines = [f"{p.relative_to(base).as_posix()} {sha256_file(p)}" for p in sorted(base.rglob("*.parquet"))]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def model_sources(tarif: Tarif) -> list[dict]:
    out = []
    for model in tarif.models:
        rows = [r for r in tarif.rows if r["modele"] == model]
        biblio = sorted({r["source_biblio"] for r in rows})
        code = sorted({r["source_code"] for r in rows})
        out.append({"model": model, "source": f"{' ; '.join(biblio)} (source_code : {' ; '.join(code)})",
                    "commit": tarif.commit, "provisoire": any(bool(r["provisoire"]) for r in rows)})
    return out


def fmt(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}f}"


def write_report(path: Path, acc: Accumulator, tarif: Tarif, post: dict, zone: Path) -> None:
    """rapport_post.html : ce qui est calculé, ce qui ne l'est pas, et pourquoi (plan T10)."""
    e = html.escape
    total = acc.computed + acc.not_computed
    parts = ["<!doctype html>", '<html lang="fr"><head><meta charset="utf-8"><title>Rapport de post</title>',
             "<style>body{font-family:sans-serif;max-width:60em;margin:1em auto}table{border-collapse:collapse}"
             "td,th{border:1px solid #999;padding:2px 6px;text-align:right}</style></head><body>",
             "<h1>post : volume, biomasse et carbone</h1>",
             f"<p><strong>{e(MENTION_ECO)}</strong>. Tarif provisoire : tarif NEMETON v5 (tarif-nemeton, commit "
             f"{e(tarif.commit)}), « coefficients non stabilisés » (décision Q1). Zone : {e(zone.name)}.</p>",
             "<h2>Définitions</h2><ul>",
             "<li>Volume : volume aérien total (tige et branches, sur écorce), même définition pour toutes les essences "
             "(décision Q3) ; ni bois fort ni volume au-dessus de 7 cm.</li>",
             "<li>Biomasse : biomasse aérienne sèche = volume aérien total × infradensité.</li>",
             "<li>Carbone aérien = biomasse aérienne × fraction de carbone, pour les feuillus comme pour les résineux "
             "(l'écart n° 1 de tarif-nemeton, carbone des résineux sur la tige seule, n'est pas repris).</li>"]
    if tarif.has_roots:
        parts.append("<li>Racines : carbone des racines = carbone aérien × rapport racines/aérien du groupe ; colonne à "
                     "part, provisoire, jamais additionnée au carbone aérien (décision Q4).</li>")
    else:
        parts.append("<li>Racines : <strong>non calculées</strong>. params/tarif.parquet n'a pas de modèle racines : le "
                     "rapport racines/aérien du GIEC 2006 (tableau 4.4) n'est pas encore lu ni cité (décision Q4) ; "
                     "aucune valeur n'est prise à sa place, et summary n'a pas de colonne carbon_roots_t_ha.</li>")
    parts += ["<li>Sol et bois mort : non modélisés (hors v1). Les morts de l'année sont un flux (summary_zone), pas un "
              "stock.</li>", "</ul>",
              "<h2>Ce qui n'est pas calculé (décision Q5)</h2>",
              "<p>Un arbre hors du domaine du tarif (diamètre, hauteur, H/D) ou d'une essence sans tarif n'est pas "
              "calculé : ni extrapolation ni emprunt du tarif d'une autre essence. Il est compté ici, par essence, en "
              "arbres-années (un arbre vivant, ou mort dans l'année, compté une fois par année).</p>",
              f"<p>Arbres-années calculés : {acc.computed} ; non calculés : {acc.not_computed} "
              f"(part : {fmt(acc.not_computed / total if total else 0.0, 4)}).</p>",
              "<h3>Hors domaine, par essence et par première raison</h3>"]
    if acc.ood:
        parts.append("<table><tr><th>essence</th>" + "".join(f"<th>{r}</th>" for r in REASONS) + "<th>total</th></tr>")
        for sp in sorted(acc.ood):
            counts = acc.ood[sp]
            parts.append(f"<tr><td>{e(sp)}</td>" + "".join(f"<td>{c}</td>" for c in counts) + f"<td>{sum(counts)}</td></tr>")
        parts.append("</table>")
    else:
        parts.append("<p>Aucun arbre hors domaine.</p>")
    parts.append("<h3>Essences sans tarif (non calculées, sans emprunt)</h3>")
    if acc.without:
        parts.append("<table><tr><th>essence</th><th>arbres-années sans tarif</th></tr>")
        parts += [f"<tr><td>{e(sp)}</td><td>{n}</td></tr>" for sp, n in sorted(acc.without.items())]
        parts.append("</table>")
    else:
        parts.append("<p>Aucune essence sans tarif.</p>")
    parts += ["<h3>Part de la surface terrière non calculée, massif entier, par année</h3>",
              "<table><tr><th>année</th><th>arbres vivants</th><th>vivants non calculés</th><th>part de surface terrière "
              "non calculée</th><th>volume aérien total (m3)</th><th>carbone aérien (tC)</th><th>morts de l'année</th></tr>"]
    for year, n, n_nc, share, v, c, dead in acc.by_year:
        parts.append(f"<tr><td>{year}</td><td>{n}</td><td>{n_nc}</td><td>{fmt(share, 4)}</td><td>{fmt(v)}</td>"
                     f"<td>{fmt(c)}</td><td>{dead}</td></tr>")
    parts.append("</table>")
    parts.append("<h2>Cellules sans type de végétation</h2>")
    if acc.untyped_rows:
        parts.append(f"<p>{len(acc.untyped_cells)} cellule(s) portent des arbres mais n'ont pas de type de végétation "
                     "(vegetation_map.tif) : elles sont dans sim/summary.parquet, mais pas dans sim/summary_zone.parquet, "
                     "où aucun type n'est inventé pour elles (décision de l'orchestrateur du 26/11/2026). Leurs totaux :</p>"
                     "<table><tr><th>cellule</th><th>année</th><th>arbres vivants</th><th>vivants non calculés</th>"
                     "<th>volume aérien total (m3)</th><th>carbone aérien (tC)</th><th>morts de l'année</th></tr>")
        for c, year, n, n_nc, v, carbon, dead in sorted(acc.untyped_rows):
            parts.append(f"<tr><td>{c}</td><td>{year}</td><td>{n}</td><td>{n_nc}</td><td>{fmt(v)}</td>"
                         f"<td>{fmt(carbon)}</td><td>{dead}</td></tr>")
        parts.append("</table>")
    else:
        parts.append("<p>Aucune : tous les arbres sont dans une cellule typée.</p>")
    parts += ["<h2>Tarif et provenance</h2>", "<table><tr><th>modèle</th><th>source</th><th>provisoire</th></tr>"]
    for m in post["models"]:
        parts.append(f"<tr><td>{e(m['model'])}</td><td style='text-align:left'>{e(m['source'])}</td>"
                     f"<td>{'oui' if m['provisoire'] else 'non'}</td></tr>")
    parts += ["</table>", f"<p>Part des paramètres provisoires : {fmt(post['provisional_share'], 4)}. Empreinte de "
              f"config.yml (run.json) : {e(post['run_config_sha256'])}.</p>",
              "<h2>Limites connues</h2><ul>",
              "<li>Seuls les arbres détectés sont simulés : les dominés manquent (spec §4.6), le volume est sous-estimé ; "
              "post ne corrige pas ce biais.</li>",
              "<li>Le d130 de l'état initial vient de l'étage B de tarif-nemeton (provisoire).</li>",
              "<li>Chiffres techniques : la trajectoire de M3a n'est pas validée écologiquement.</li></ul>",
              f"<p>Durée de post : {post['duration_s']:.3f} s.</p>", "</body></html>"]
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def run_post(config_path: Path) -> None:
    started = time.monotonic()
    config = read_config(config_path)
    code = call_validator(["config", str(config_path)])
    if code != 0:
        raise ModuleError(f"config.yml non conforme (validateur, code {code})")
    zone = zone_dir(config)
    run, years = check_run(zone, config_path)
    tarif_path = zone / "params" / "tarif.parquet"
    if not tarif_path.is_file():
        raise ModuleError(f"{tarif_path} absent : le tarif s'écrit par import_tarif (rien n'est inventé)")
    code = call_validator(["import_tarif.tarif", str(tarif_path)])
    if code != 0:
        raise ModuleError(f"{tarif_path} non conforme au contrat import_tarif.tarif (validateur, code {code})")
    groups = read_species_groups(root() / "contracts" / "species.csv")
    tarif = Tarif(tarif_path, groups)
    resolution = (config.get("grid") or {}).get("resolution_m")
    if not isinstance(resolution, (int, float)) or resolution <= 0:
        raise ModuleError("config.yml : grid.resolution_m absent ou non positif")
    area_ha = float(resolution) ** 2 / 10_000.0
    grid = read_grid(zone)
    if not math.isclose(abs(grid["transform"].a), resolution) or not math.isclose(abs(grid["transform"].e), resolution):
        raise ModuleError(f"grid.tif a des cellules de {abs(grid['transform'].a)} m, config.yml dit {resolution} m")
    say(f"{len(years)} années ({years[0]} à {years[-1]}) ; tarif {tarif.commit}, modèles : {', '.join(tarif.models)} ; "
        f"essences avec tarif : {', '.join(sorted(tarif.species))}")
    if not tarif.has_roots:
        say("modèle racines absent de params/tarif.parquet (GIEC 2006, tableau 4.4, pas encore lu) : pas de colonne "
            "carbon_roots, rien n'est pris à sa place")

    acc = Accumulator(tarif, grid, area_ha)
    for year in years:
        acc.add(year, compute_year(read_year(zone, year, groups), tarif, grid))

    staging = zone / "sim" / STAGING
    if staging.exists():
        say(f"{staging} reste d'une exécution interrompue : effacé")
        shutil.rmtree(staging)
    staging.mkdir()
    try:
        write_table(acc.summary, summary_schema(tarif.has_roots), tarif.provisoire, staging / "summary.parquet")
        write_table(acc.zone, zone_schema(tarif.has_roots), tarif.provisoire, staging / "summary_zone.parquet")
        post = {"schema_version": 1, "run_config_sha256": run["config_sha256"],
                "inputs_sha256": {"sim_run": sha256_file(zone / "sim" / "run.json"), "sim_trees": trees_fingerprint(zone),
                                  "params_tarif": sha256_file(tarif_path)},
                "tarif_commit": tarif.commit, "models": model_sources(tarif),
                "tree_years_computed": acc.computed, "tree_years_not_computed": acc.not_computed,
                "out_of_domain": {sp: dict(zip(REASONS, c)) for sp, c in sorted(acc.ood.items())},
                "without_tarif": dict(sorted(acc.without.items())),
                "without_vegetation_type": {"cells": sorted(acc.untyped_cells), "tree_years": acc.untyped_tree_years},
                "provisional_share": tarif.provisional_share, "duration_s": 0.0}
        post["duration_s"] = round(time.monotonic() - started, 3)
        (staging / "post.json").write_text(json.dumps(post, indent=1, ensure_ascii=False, sort_keys=True) + "\n",
                                           encoding="utf-8")
        write_report(staging / "rapport_post.html", acc, tarif, post, zone)
        for contract, name in (("post.summary", "summary.parquet"), ("post.summary_zone", "summary_zone.parquet"),
                               ("post.run", "post.json")):
            code = call_validator([contract, str(staging / name)])
            if code != 0:
                raise ModuleError(f"{name} non conforme au contrat {contract} (validateur, code {code}) ; rien n'est publié")
        for name in ("summary.parquet", "summary_zone.parquet", "post.json"):
            os.replace(staging / name, zone / "sim" / name)
        os.replace(staging / "rapport_post.html", zone / "rapport_post.html")
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    total = acc.computed + acc.not_computed
    say(f"{acc.computed} arbres-années calculés, {acc.not_computed} non calculés ({acc.not_computed / total:.1%}) ; "
        f"{len(acc.summary['cell_id'])} lignes de summary, {len(acc.zone['year'])} de summary_zone ; "
        f"{len(acc.untyped_cells)} cellule(s) sans type de végétation ; {post['duration_s']:.1f} s ; {MENTION_ECO}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=NAME, exit_on_error=False)
    parser.add_argument("--config", default="config.yml", help="chemin de config.yml")
    try:
        options = parser.parse_args(argv)
    except (argparse.ArgumentError, SystemExit):
        return EXIT_IMPOSSIBLE
    try:
        run_post(Path(options.config))
    except ModuleError as error:
        print(f"[{NAME}] erreur : {error}", file=sys.stderr)
        return EXIT_IMPOSSIBLE
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
