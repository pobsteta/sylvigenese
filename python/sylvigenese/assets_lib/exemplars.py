"""Exemplaires du générateur d'arbres (lus par fichiers) et dimensions de référence demandées à l'export.

Étape du BRIEF codée : §4 (arbres, un `.glb` par essence et stade) et §9 (arbres synthétiques) ; plan
`docs/plans/m6a.md` §4 et §5 (T6, T12), décisions de Pascal Q1 (le générateur de tarif-nemeton entre par
fichiers), Q3 (pas d'emprunt) et Q6 (dimensions de référence). Mission 070.

Ce module ne contient AUCUN code du générateur : il lit des fichiers Parquet écrits par ailleurs
(contrat `assets.exemplars`, `contracts/tables/assets/exemplars.schema.json`) :
- une ligne par segment (tronc de cône) `x0 y0 z0 x1 y1 z1 r0_m r1_m niveau axe`, en mètres, REPÈRE z-up du
  générateur (x est, y nord, z haut), dit par la métadonnée `frame` ;
- métadonnées `frame`, `units`, `essence`, `stage`, `D_cm`, `H_m`, `hbh_m`, `Rh_m`, `seed`, `source_commit`,
  `synthetic`, `calage` (« calé » ou « non calé », toujours écrit par l'export, mission 071) ; `b_cible` (absente
  seulement si `calage` vaut « non calé ») ; `calage_raisons` (facultatif).
Un fichier qui ne tient pas le contrat est refusé avec la cause : aucune valeur n'est complétée ; en particulier
`calage` absent est un refus (rien n'est déduit de `b_cible` ni de l'essence).

Il porte aussi la table des modèles par code espar (`contracts/species.csv`) : deux codes de la même
essence du générateur (02 et 03, 12P et 12V) partagent un fichier (alias, pas un emprunt) ; un code sans
`tarif_nemeton_code` n'a pas de modèle propre (modèle générique, Q3).

Dimensions de référence (Q6) : `dimensions_request` calcule D et H en quantiles des arbres de `sim/trees`,
par essence du générateur et par stade, et les écrit au format du contrat `params.model_dimensions`
comme fichier de DEMANDE pour l'export de tarif-nemeton. hbh, Rh et b_cible n'y sont pas : ils viennent de la
calibration du générateur.
"""

from __future__ import annotations

import csv
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

from sylvigenese.common import ModuleError
from sylvigenese.assets_lib import initial_state, sim_state, stages

SEGMENT_FLOATS = ("x0", "y0", "z0", "x1", "y1", "z1", "r0_m", "r1_m")
SEGMENT_INTS = ("niveau", "axe")
REQUIRED_META = ("frame", "units", "essence", "stage", "D_cm", "H_m", "hbh_m", "Rh_m", "seed", "source_commit",
                 "synthetic", "calage")
COMMIT = re.compile(r"^[0-9a-f]{7,40}$")
ESSENCE = re.compile(r"^[A-Z][a-z]+_[a-z]+$")
CALAGE = ("calé", "non calé")


@dataclass(frozen=True)
class SpeciesModel:
    """Un code espar de `contracts/species.csv` : son essence du générateur (None sans modèle propre), le code
    qui porte le fichier de cette essence (le premier de species.csv) et son groupe."""
    code: str
    essence: str | None
    owner: str | None
    group: str


def species_models(path: Path | None = None) -> dict[str, SpeciesModel]:
    """Code espar -> SpeciesModel, lu dans contracts/species.csv (colonnes `tarif_nemeton_code` et `groupe`)."""
    path = path or initial_state.ROOT / "contracts" / "species.csv"
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    owner: dict[str, str] = {}
    for row in rows:
        if row["tarif_nemeton_code"]:
            owner.setdefault(row["tarif_nemeton_code"], row["espar"])
    return {row["espar"]: SpeciesModel(row["espar"], row["tarif_nemeton_code"] or None,
                                       owner.get(row["tarif_nemeton_code"]), row["groupe"]) for row in rows}


@dataclass
class Exemplar:
    """Un arbre du générateur : segments (repère z-up) et métadonnées du fichier."""
    essence: str
    stage: str
    meta: dict[str, str]
    segments: dict[str, np.ndarray]
    path: Path | None = None
    sizes: dict = field(default_factory=dict)

    @property
    def seed(self) -> int:
        return int(self.meta["seed"])

    @property
    def count(self) -> int:
        return len(self.segments["x0"])


def read_exemplar(path: Path) -> Exemplar:
    """Lit et contrôle un fichier `<essence>_<stade>.parquet` ; toute entorse au contrat est un refus nommé."""
    path = Path(path)
    name = path.name

    def refuse(reason: str):
        raise ModuleError(f"exemplaire {name} refusé : {reason}")

    try:
        table = pq.read_table(path)
    except Exception as error:   # pyarrow lève plusieurs types (fichier tronqué, pas du Parquet)
        refuse(f"Parquet illisible ({error})")
    meta = {k.decode("utf-8"): v.decode("utf-8") for k, v in (table.schema.metadata or {}).items()}
    missing = [k for k in REQUIRED_META if k not in meta]
    if missing:
        refuse(f"métadonnée(s) absente(s) : {', '.join(missing)}")
    if meta["frame"] != "z-up":
        refuse(f"repère « {meta['frame']} » : le générateur est z-up, la conversion y-up se fait ici une fois (T6)")
    if meta["units"] != "m":
        refuse(f"unités « {meta['units']} » : des mètres sont attendus")
    if meta["synthetic"] != "true":
        refuse("`synthetic` doit valoir true (arbre synthétique, BRIEF §9)")
    if meta["stage"] not in stages.STAGES:
        refuse(f"stade « {meta['stage']} » hors de {', '.join(stages.STAGES)}")
    if not ESSENCE.match(meta["essence"]):
        refuse(f"essence « {meta['essence']} » : forme Genre_espece attendue")
    if path.stem != f"{meta['essence']}_{meta['stage']}":
        refuse(f"le nom doit être {meta['essence']}_{meta['stage']}.parquet d'après les métadonnées")
    if not COMMIT.match(meta["source_commit"]):
        refuse(f"source_commit « {meta['source_commit']} » : un commit (7 à 40 caractères hexadécimaux) est attendu")
    numbers = {}
    for key in ("D_cm", "H_m", "hbh_m", "Rh_m"):
        try:
            numbers[key] = float(meta[key])
        except ValueError:
            refuse(f"{key} = « {meta[key]} » n'est pas un nombre")
        if not math.isfinite(numbers[key]) or numbers[key] <= 0:
            refuse(f"{key} = {meta[key]} : un nombre strictement positif est attendu")
    try:
        int(meta["seed"])
    except ValueError:
        refuse(f"seed = « {meta['seed']} » n'est pas un entier")
    if "b_cible" in meta:
        try:
            b = float(meta["b_cible"])
        except ValueError:
            refuse(f"b_cible = « {meta['b_cible']} » n'est pas un nombre")
        if not math.isfinite(b):
            refuse("b_cible n'est pas fini")
    elif meta.get("calage") != "non calé":
        refuse("b_cible absent alors que calage n'est pas « non calé » : jamais de valeur inventée")
    if meta["calage"] not in CALAGE:
        refuse(f"calage « {meta['calage']} » hors de {', '.join(CALAGE)}")
    columns = set(table.column_names)
    absent = [c for c in SEGMENT_FLOATS + SEGMENT_INTS if c not in columns]
    if absent:
        refuse(f"colonne(s) absente(s) : {', '.join(absent)}")
    if table.num_rows == 0:
        refuse("aucun segment")
    segments = {}
    for column in SEGMENT_FLOATS:
        values = table.column(column).to_numpy(zero_copy_only=False).astype("float64")
        if not np.isfinite(values).all():
            refuse(f"colonne {column} : valeur non finie (NaN ou infini)")
        segments[column] = values
    for column in SEGMENT_INTS:
        segments[column] = table.column(column).to_numpy(zero_copy_only=False).astype("int64")
    if (segments["r0_m"] < 0).any() or (segments["r1_m"] < 0).any():
        refuse("rayon négatif")
    if (segments["niveau"] < -1).any() or (segments["axe"] < 0).any():
        refuse("niveau < -1 ou axe < 0")
    return Exemplar(meta["essence"], meta["stage"], meta, segments, path)


def read_directory(directory: Path, species: dict[str, SpeciesModel] | None = None) -> dict[tuple[str, str], Exemplar]:
    """Tous les `*.parquet` d'un dossier : {(essence, stade): Exemplar}, dans l'ordre des noms.

    Une essence qui n'est pas dans `contracts/species.csv` (colonne tarif_nemeton_code) est refusée : aucun code
    n'est inventé. Un dossier absent ou sans exemplaire est refusé aussi (config.yml le désigne)."""
    directory = Path(directory)
    if not directory.is_dir():
        raise ModuleError(f"assets.models.exemplars_dir : {directory} n'est pas un dossier")
    files = sorted(directory.glob("*.parquet"))
    if not files:
        raise ModuleError(f"assets.models.exemplars_dir : aucun fichier .parquet dans {directory}")
    declared: dict[tuple[str, str], str] = {}
    for file in files:                                     # doublon (essence, stade) : deux fichiers pour un même modèle
        try:
            meta = {k.decode("utf-8"): v.decode("utf-8") for k, v in (pq.read_schema(file).metadata or {}).items()}
        except Exception:                                  # illisible : refusé plus bas, avec sa cause
            continue
        key = (meta.get("essence", ""), meta.get("stage", ""))
        if key[0] and key in declared:
            raise ModuleError(f"doublon : {file.name} et {declared[key]} déclarent le même exemplaire "
                              f"(essence {key[0]}, stade {key[1]}) ; un seul fichier par essence et stade")
        declared[key] = file.name
    known = {m.essence for m in (species or species_models()).values() if m.essence}
    found: dict[tuple[str, str], Exemplar] = {}
    for file in files:
        exemplar = read_exemplar(file)
        if exemplar.essence not in known:
            raise ModuleError(f"exemplaire {file.name} refusé : l'essence {exemplar.essence} n'est pas une essence du "
                              "générateur de contracts/species.csv (tarif_nemeton_code)")
        found[(exemplar.essence, exemplar.stage)] = exemplar
    return found


# ------------------------------------------------------------------ dimensions de référence (Q6)
REQUEST_COLUMNS = ["essence", "stage", "term", "value", "unit", "provisoire", "source"]
TERMS = (("D_cm", "d130", "cm"), ("H_m", "h", "m"))


def dimensions_request(zone: Path, config: dict, quantile: float, min_trees: int,
                       breaks: tuple[float, float, float] | None = None) -> tuple[list[dict], list[dict]]:
    """Dimensions D et H des exemplaires à demander à l'export (Q6) : quantile de `sim/trees` par essence du
    générateur et par stade, sur les arbres vivants de toutes les années retenues.

    Rend (lignes au contrat `params.model_dimensions`, signalements). Un couple (essence, stade) qui a moins de
    `min_trees` arbres n'a pas de ligne : il est signalé (repli sur un fichier sourcé, ou modèle générique, Q3).
    Le stade d'un arbre est celui de `stages.stage_of` (h / h_pot, seuils du fichier unique) ; un code espar sans
    essence du générateur est compté dans les signalements. Le quantile et le minimum sont des arguments, pas des
    constantes : ils sont écrits dans la colonne `source`."""
    if not 0 < quantile < 1:
        raise ModuleError(f"quantile {quantile} : un nombre de ]0 ; 1[ est attendu")
    if min_trees < 1:
        raise ModuleError(f"nombre minimal d'arbres {min_trees} : un entier >= 1 est attendu")
    run = sim_state.read_run(zone, config)
    retained = sim_state.retained_years(int(run["t0"]), int(run["years"]), sim_state.year_step(config))
    species = species_models()
    breaks = breaks or stages.load_breaks()
    pools: dict[tuple[str, str], dict[str, list[np.ndarray]]] = {}
    without_model: dict[str, int] = {}
    for year in retained:
        trees = sim_state.read_trees(zone, year)
        alive = trees["status"] == "alive"
        if not alive.any():
            continue
        x, y, h, d = (trees[k][alive] for k in ("x", "y", "h", "d130"))
        codes = trees["species"][alive]
        unknown = sorted({c for c in set(codes.tolist()) if c not in species})
        if unknown:
            raise ModuleError(f"sim/trees year={year} : essence(s) absente(s) de contracts/species.csv : "
                              f"{', '.join(unknown)}")
        grade = stages.stage_of(h, stages.ceiling_at(zone, x, y), breaks)
        essences = np.array([species[c].essence or "" for c in codes.tolist()], dtype=object)
        for code in sorted(set(codes[essences == ""].tolist())):
            without_model[code] = without_model.get(code, 0) + int((codes == code).sum())
        for essence in sorted(set(essences.tolist()) - {""}):
            for stage in stages.STAGES:
                selected = (essences == essence) & (grade == stage)
                if selected.any():
                    pool = pools.setdefault((essence, stage), {"d130": [], "h": []})
                    pool["d130"].append(d[selected])
                    pool["h"].append(h[selected])
    rows, notes = [], []
    years_text = f"{retained[0]} à {retained[-1]}" if len(retained) > 1 else str(retained[0])
    for (essence, stage) in sorted(pools):
        values = {k: np.concatenate(v) for k, v in pools[(essence, stage)].items()}
        n = len(values["h"])
        if n < min_trees:
            notes.append({"essence": essence, "stage": stage, "trees": n, "reason":
                          f"{n} arbre(s) de sim/trees, moins que le minimum demandé ({min_trees}) : aucune dimension "
                          "demandée ; repli sur params/model_dimensions.csv sourcé, ou modèle générique (Q3, Q6)"})
            continue
        for term, column, unit in TERMS:
            rows.append({"essence": essence, "stage": stage, "term": term,
                         "value": float(round(float(np.quantile(values[column], quantile)), 3)), "unit": unit,
                         "provisoire": True,
                         "source": f"quantile {quantile:g} de {column} des {n} arbres vivants de sim/trees "
                                   f"(années {years_text}), essence {essence}, stade {stage} (h / h_pot, "
                                   f"seuils {breaks[0]:g} {breaks[1]:g} {breaks[2]:g}) ; demande d'export, Q6"})
    present = {(r["essence"], r["stage"]) for r in rows}
    for essence in sorted({e for e, _ in pools}):
        for stage in stages.STAGES:
            if (essence, stage) not in pools:
                notes.append({"essence": essence, "stage": stage, "trees": 0,
                              "reason": "aucun arbre vivant de ce stade dans sim/trees : aucune dimension demandée"})
    for code, n in sorted(without_model.items()):
        notes.append({"essence": f"code espar {code}", "stage": "", "trees": n,
                      "reason": "sans essence du générateur (contracts/species.csv) : modèle générique (Q3)"})
    if not present:
        raise ModuleError("aucun couple (essence, stade) n'a assez d'arbres dans sim/trees : rien à demander")
    return rows, notes


def write_request(path: Path, rows: list[dict]) -> Path:
    """Écrit les lignes au format du contrat `params.model_dimensions` (CSV UTF-8, en-tête, booléens true/false)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REQUEST_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "provisoire": "true" if row["provisoire"] else "false"})
    return path
