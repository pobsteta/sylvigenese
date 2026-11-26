"""Module `import_tarif` (spec §2, §3, §4.3) : import de l'allométrie de tarif-nemeton.

Étape visée : état initial, arbres détectés (spec §4.3, BRIEF §12) : le d130 d'un arbre vient de
`ln D = a + b ln H + c ln CPA` (étage B de tarif-nemeton), ou de `ln D = a + b ln H` pour une
essence sans coefficient c. Ce module lit les CSV de résultats de tarif-nemeton (dossier
`external.tarif_nemeton_dir` de config.yml ; rien n'est copié dans le dépôt, aucun code de
tarif-nemeton n'est repris) et écrit `params/allometry.parquet` (modèle `etage_b`, format long
du contrat `import_tarif.allometry`, `provisoire: true`, source citée).

Fichiers lus, sous `<dossier>/resultats/etage_b/` :
- `allometrie_D.csv` : colonnes `essence, a, b_lnH, c_lnCPA, ...` (modèle avec houppier) ;
- `allometrie_D_ifn.csv` : mêmes colonnes, `c_lnCPA` = 0 (modèle sans houppier, calé sur l'IFN).

Règles, dites plutôt que devinées :
- `c_lnCPA` = 0, vide ou absent : pas de terme `c` (le module `trees` prend alors ln D = a + b ln H) ;
- une essence présente dans les deux fichiers garde le jeu de `allometrie_D.csv` (un seul jeu
  a, b, c par essence : mélanger les deux fabriquerait un modèle qu'aucun des deux n'a calé) ;
  le fichier IFN ne sert que pour une essence absente du premier, et le rapport le dit ;
- le code espar vient de `contracts/species.csv`, colonne `tarif_nemeton_code` ; un nom latin
  sans ligne correspondante est signalé et sauté, jamais rattaché à un code par ressemblance ;
- `Quercus_spec` = espar 02 + 03 et rien d'autre (docs/referentiels/species.md, « Règle de
  Quercus_spec ») : les mêmes coefficients sont écrits pour 02 et pour 03, les autres chênes
  n'ont aucun coefficient ; `Betula_spec` = 12P + 12V, de la même façon, comme le fichier le dit.

Houppier (mission 034, contrat params/allometry, modèles `hcb` et `cw`) : les coefficients de
`CR = CR_a + CR_b ln(d130)` (rapport de houppier, hcb = h (1 − CR)) et de `ln E = R_a + R_b ln(d130)`
(E : étendue maximale du houppier, cw = 2 E) sont lus dans `resultats/synth_arbres/bornes_dimensions.csv`
(colonnes `CR_a, CR_b, R_a, R_b`, sortie de `code/synth_calage.py`) ; les bornes `CR_min` et `CR_max`
sont lues dans `code/synth_calage.py` (l'écrêtage de CR de la fonction `forme`). L'unité de d130 est
VÉRIFIÉE avant toute écriture (centimètres : relations de `synth_calage.py` sur `dTLS`, quantiles
D_obs du fichier) ; une unité douteuse, ou un fichier de bornes présent mais illisible, arrête le
module (code 2) ; un fichier absent est signalé et rien n'est inventé (simulate refusera alors les
essences sans coefficients). Écrits dans le même `params/allometry.parquet`, `provisoire: true`.

Tarif de volume, biomasse et carbone (mission 053, contrat `import_tarif.tarif`, décisions de Pascal
Q1 à Q5 du 26/11/2026) : `resultats/tarif_v5/parametres_tarif_v5.csv` (mission 050) est lu, avec ses
renvois (une ligne sans valeur renvoie à « fichier:ligne#colonne », par exemple
`coefficients_feuillus_v5.csv`, qui reste la source unique de la valeur ; la ligne visée doit être
celle de l'essence), et écrit dans `params/tarif.parquet`, une ligne par terme, avec `source_commit`
(commit lu dans `.git`, obligatoire) et `provisoire` (toujours vrai : « coefficients non stabilisés »).
La correspondance des noms est écrite dans la description du contrat (CORRESPONDANCE) ; un modèle ou
un terme du CSV qu'elle ne connaît pas arrête le module (code 2) au lieu d'être deviné. Le domaine
des feuillus est celui qu'applique tarif-nemeton à sa table (bornes de calage × facteurs, ± marge).
Le modèle `racines` n'existe pas dans le CSV (GIEC 2006, tableau 4.4, pas encore lu) : aucune ligne
n'est écrite et `post` n'aura pas de carbone des racines. Fichier absent : signalé, rien n'est
écrit (un `params/tarif.parquet` existant est laissé tel quel).

Source des CSV : https://github.com/pobsteta/tarif-nemeton (dépôt sans licence : seuls des
résultats sont lus ; le commit lu est cité dans la colonne `source`).
Sortie : `data/<zone>/params/allometry.parquet` (jeu fictif : `tests/fixtures/zone_fictive`),
sous la racine `SYLVIGENESE_ROOT` (défaut : dossier courant), et `params/tarif.parquet`. Chaque
fichier écrit est validé par `contracts/validate` (contrats `import_tarif.allometry` et
`import_tarif.tarif`) avant le code de sortie 0.
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from sylvigenese.common import (
    EXIT_IMPOSSIBLE,
    EXIT_OK,
    ModuleError,
    call_validator,
    read_config,
)

NAME = "import_tarif"
MODEL = "etage_b"
REPO_URL = "https://github.com/pobsteta/tarif-nemeton"
RESULTS_DIR = Path("resultats") / "etage_b"
CROWN_FILE = "allometrie_D.csv"
IFN_FILE = "allometrie_D_ifn.csv"
CSV_COLUMNS = ("essence", "a", "b_lnH", "c_lnCPA")
BORNES_FILE = Path("resultats") / "synth_arbres" / "bornes_dimensions.csv"
CALAGE_SCRIPT = Path("code") / "synth_calage.py"
BORNES_COLUMNS = ("essence", "n_arbres", "source", "D_obs_q05", "D_obs_q95", "CR_a", "CR_b", "R_a", "R_b")
D130_CM_RANGE = (5.0, 250.0)   # un diamètre d'arbre adulte en cm ; en mètres, il serait sous 3
# Écrêtage du rapport de houppier dans synth_calage.py (fonction forme) : np.clip(CR_a + CR_b * ln D, bas, haut)
CLIP_PATTERN = re.compile(r'np\.clip\(\s*par\["CR_a"\]\s*\+\s*par\["CR_b"\]\s*\*\s*np\.log\(D\)\s*,'
                          r'\s*([0-9]*\.?[0-9]+)\s*,\s*([0-9]*\.?[0-9]+)\s*\)')
# Relations de ajuster() : D = d.dTLS (cm) ; CR et ln E régressés sur ln D ; E = crown_extent_max_m
CALAGE_PATTERNS = {
    "D = d.dTLS": re.compile(r"D\s*=\s*d\.dTLS\.values"),
    "régression sur ln D": re.compile(r"np\.c_\[\s*np\.ones\(len\(d\)\)\s*,\s*np\.log\(D\)\s*\]"),
    "ln E": re.compile(r"lnE\s*=\s*np\.log\(d\.crown_extent_max_m"),
}
CROWN_MODELS = ("hcb", "cw")

SCHEMA = pa.schema([
    ("species", pa.string()),
    ("species_group", pa.string()),
    ("model", pa.string()),
    ("term", pa.string()),
    ("value", pa.float64()),
    ("provisoire", pa.bool_()),
    ("source", pa.string()),
])


def root() -> Path:
    return Path(os.environ.get("SYLVIGENESE_ROOT", "."))


def zone_dir(config: dict) -> Path:
    """Même règle que `prepare_zone_dir` (R) : jeu fictif versionné, sinon data/<zone>."""
    zone = config.get("zone")
    if not zone:
        raise ModuleError("config.yml : `zone` manquante")
    if zone == "zone_fictive":
        return root() / "tests" / "fixtures" / "zone_fictive"
    return root() / "data" / zone


def read_commit(directory: Path) -> str | None:
    """Commit (7 caractères) du dépôt tarif-nemeton lu, ou None si `.git` ne le dit pas."""
    git = directory / ".git"
    try:
        head = (git / "HEAD").read_text(encoding="utf-8").strip()
        if head.startswith("ref:"):
            ref = head.split(":", 1)[1].strip()
            file = git / ref
            if file.is_file():
                head = file.read_text(encoding="utf-8").strip()
            else:
                head = next((row.split()[0] for row in
                             (git / "packed-refs").read_text(encoding="utf-8").splitlines()
                             if row.endswith(" " + ref)), "")
    except OSError:
        return None
    return head[:7] if head else None


def read_espar_mapping(path: Path) -> dict[str, list[str]]:
    """`tarif_nemeton_code` -> liste des codes espar (contracts/species.csv), ordre du fichier."""
    if not path.is_file():
        raise ModuleError(f"contracts/species.csv introuvable : {path}")
    result: dict[str, list[str]] = {}
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not {"espar", "tarif_nemeton_code"} <= set(reader.fieldnames):
            raise ModuleError(f"{path} : colonnes espar et tarif_nemeton_code attendues")
        for row in reader:
            name = (row["tarif_nemeton_code"] or "").strip()
            if name:
                result.setdefault(name, []).append(row["espar"])
    return result


def _number(text: str | None, file: str, line_number: int, column: str) -> float | None:
    """Nombre lu, None si la case est vide ; une case illisible est une erreur, pas un zéro."""
    text = (text or "").strip()
    if text == "":
        return None
    try:
        value = float(text)
    except ValueError:
        raise ModuleError(f"{file} ligne {line_number} : {column} = « {text} » n'est pas un nombre") from None
    if math.isnan(value):
        return None
    if math.isinf(value):
        raise ModuleError(f"{file} ligne {line_number} : {column} = « {text} » n'est pas fini")
    return value


def read_coefficients(path: Path) -> dict[str, dict[str, float | None]]:
    """essence -> {a, b, c} ; c vaut None quand `c_lnCPA` est 0, vide, NA ou la colonne absente."""
    if not path.is_file():
        raise ModuleError(f"fichier de tarif-nemeton introuvable : {path}")
    result: dict[str, dict[str, float | None]] = {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = [c for c in CSV_COLUMNS[:3] if c not in (reader.fieldnames or [])]
        if missing:
            raise ModuleError(f"{path.name} : colonne(s) {', '.join(missing)} absente(s)")
        for line_number, row in enumerate(reader, start=2):
            species_name = (row["essence"] or "").strip()
            if not species_name:
                raise ModuleError(f"{path.name} ligne {line_number} : essence vide")
            if species_name in result:
                raise ModuleError(f"{path.name} ligne {line_number} : essence {species_name} en double")
            a = _number(row["a"], path.name, line_number, "a")
            b = _number(row["b_lnH"], path.name, line_number, "b_lnH")
            c = _number(row.get("c_lnCPA"), path.name, line_number, "c_lnCPA")
            result[species_name] = {"a": a, "b": b, "c": None if (c is None or c == 0.0) else c}
    return result


def build_rows(directory: Path, espar_mapping: dict[str, list[str]]) -> tuple[list[dict], list[str]]:
    """Lignes du format long, et lignes de rapport (signalements)."""
    results_dir = directory / RESULTS_DIR
    with_crown = read_coefficients(results_dir / CROWN_FILE)
    ifn = read_coefficients(results_dir / IFN_FILE)
    commit = read_commit(directory)
    version = f"commit {commit}" if commit else "commit non lu (dossier sans .git)"
    report: list[str] = []
    rows: list[dict] = []

    coefficient_sets: list[tuple[str, str, dict]] = []   # (essence, fichier, coefficients)
    for species_name, coef in with_crown.items():
        coefficient_sets.append((species_name, CROWN_FILE, coef))
    for species_name, coef in ifn.items():
        if species_name in with_crown:
            report.append(f"{species_name} : présente dans {CROWN_FILE} et {IFN_FILE} ; "
                           f"le jeu de {CROWN_FILE} est gardé, celui de l'IFN est ignoré")
        else:
            coefficient_sets.append((species_name, IFN_FILE, coef))

    for species_name, file, coef in coefficient_sets:
        if coef["a"] is None or coef["b"] is None:
            report.append(f"{species_name} ({file}) : a ou b manquant, essence sautée (rien n'est deviné)")
            continue
        codes = espar_mapping.get(species_name)
        if not codes:
            report.append(f"{species_name} ({file}) : aucun code espar dans contracts/species.csv "
                           f"(colonne tarif_nemeton_code), essence sautée (rien n'est deviné)")
            continue
        if len(codes) > 1:
            report.append(f"{species_name} : coefficients écrits pour les espar {', '.join(codes)} "
                           f"(docs/referentiels/species.md : {species_name} = ces codes et rien d'autre)")
        if coef["c"] is None:
            report.append(f"{species_name} ({file}) : pas de terme c (c_lnCPA = 0 ou absent) ; "
                           f"ln D = a + b ln H")
        elif coef["c"] < 0:
            report.append(f"{species_name} ({file}) : c = {coef['c']} est négatif (un houppier plus "
                           f"large donnerait un d130 plus petit) ; repris tel quel, à vérifier")
        source = f"tarif-nemeton {RESULTS_DIR.as_posix()}/{file} ({REPO_URL}, {version})"
        terms = [("a", coef["a"]), ("b", coef["b"])]
        if coef["c"] is not None:
            terms.append(("c", coef["c"]))
        for espar in codes:
            for term, value in terms:
                rows.append({"species": espar, "species_group": None, "model": MODEL,
                               "term": term, "value": float(value), "provisoire": True,
                               "source": source})
    if not rows:
        raise ModuleError("aucune essence de tarif-nemeton n'a de code espar : rien à écrire")
    crown_rows, crown_report = build_crown_rows(directory, espar_mapping, version)
    report.extend(crown_report)
    rows.extend(crown_rows)
    stage_b = {r["species"] for r in rows if r["model"] == MODEL}
    with_crown = {r["species"] for r in rows if r["model"] == "hcb"} & {r["species"] for r in rows if r["model"] == "cw"}
    if crown_rows:
        lacking = sorted(stage_b - with_crown)
        if lacking:
            report.append(f"essence(s) {', '.join(lacking)} avec l'étage B mais sans hcb ni cw : simulate les refusera")
    rows.sort(key=lambda r: (r["species"].encode(), r["model"], r["term"]))
    return rows, report


def read_calage_script(directory: Path) -> tuple[float, float, str]:
    """Bornes (CR_min, CR_max) et référence de ligne, lues dans code/synth_calage.py ; erreur si la
    forme des relations n'est pas celle qu'on suppose (rien n'est deviné)."""
    path = directory / CALAGE_SCRIPT
    if not path.is_file():
        raise ModuleError(f"{CALAGE_SCRIPT.as_posix()} introuvable dans {directory} : l'unité de d130 et les "
                          f"bornes de CR ne peuvent pas être vérifiées")
    text = path.read_text(encoding="utf-8")
    for label, pattern in CALAGE_PATTERNS.items():
        if not pattern.search(text):
            raise ModuleError(f"{path.name} : relation « {label} » introuvable ; la forme de hcb et cw "
                              f"n'est plus celle du contrat (CR = CR_a + CR_b ln d130, ln E = R_a + R_b ln d130)")
    match = CLIP_PATTERN.search(text)
    if not match:
        raise ModuleError(f"{path.name} : écrêtage np.clip(CR_a + CR_b ln D, bas, haut) introuvable ; "
                          f"CR_min et CR_max ne sont pas devinés")
    low, high = float(match.group(1)), float(match.group(2))
    if not 0.0 <= low < high <= 1.0:
        raise ModuleError(f"{path.name} : bornes de CR illisibles ({low} ; {high}), attendu 0 <= bas < haut <= 1")
    line = text.count("\n", 0, match.start()) + 1
    return low, high, f"{CALAGE_SCRIPT.as_posix()} ligne {line}"


def check_d130_unit(bornes: list[dict]) -> None:
    """d130 en centimètres : les quantiles D_obs des essences calées sur leurs propres arbres doivent
    tomber dans [5 ; 250]. Des mètres (< 3) ou des millimètres (> 250) arrêtent le module."""
    own = [row for row in bornes if row["source"] == "essence"]
    if not own:
        raise ModuleError(f"{BORNES_FILE.as_posix()} : aucune essence calée sur ses propres arbres, "
                          f"l'unité de d130 ne peut pas être vérifiée")
    low, high = D130_CM_RANGE
    for row in own:
        for column in ("D_obs_q05", "D_obs_q95"):
            value = row[column]
            if value is None or not low <= value <= high:
                raise ModuleError(
                    f"{BORNES_FILE.as_posix()} : {row['essence']}, {column} = {value} hors de [{low:g} ; {high:g}] : "
                    f"d130 n'est pas en centimètres (unité attendue par hcb et cw) ; rien n'est converti ni écrit")


def read_crown_bounds_table(path: Path) -> list[dict]:
    """Lignes de bornes_dimensions.csv (nombres lus, case vide = None, texte illisible = erreur)."""
    if not path.is_file():
        raise ModuleError(f"fichier de tarif-nemeton introuvable : {path}")
    rows = []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = [c for c in BORNES_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ModuleError(f"{path.name} : colonne(s) {', '.join(missing)} absente(s)")
        seen = set()
        for line_number, row in enumerate(reader, start=2):
            name = (row["essence"] or "").strip()
            if not name:
                raise ModuleError(f"{path.name} ligne {line_number} : essence vide")
            if name in seen:
                raise ModuleError(f"{path.name} ligne {line_number} : essence {name} en double")
            seen.add(name)
            item = {"essence": name, "source": (row["source"] or "").strip(), "line": line_number}
            for column in ("n_arbres", "D_obs_q05", "D_obs_q95", "CR_a", "CR_b", "R_a", "R_b"):
                item[column] = _number(row[column], path.name, line_number, column)
            rows.append(item)
    return rows


def build_crown_rows(directory: Path, espar_mapping: dict[str, list[str]], version: str) -> tuple[list[dict], list[str]]:
    """Lignes hcb et cw (format long) et signalements. Absence des fichiers : signalée, aucune ligne."""
    report: list[str] = []
    bornes_path = directory / BORNES_FILE
    if not bornes_path.is_file() or not (directory / CALAGE_SCRIPT).is_file():
        report.append(f"hcb et cw non importés : {BORNES_FILE.as_posix()} ou {CALAGE_SCRIPT.as_posix()} absent de "
                      f"{directory} ; rien n'est inventé (simulate refusera toute essence sans ces coefficients)")
        return [], report
    cr_min, cr_max, clip_ref = read_calage_script(directory)
    bornes = read_crown_bounds_table(bornes_path)
    check_d130_unit(bornes)
    rows: list[dict] = []
    file_ref = f"{REPO_URL}, {version}"
    for entry in bornes:
        name = entry["essence"]
        codes = espar_mapping.get(name)
        if not codes:
            report.append(f"{name} ({BORNES_FILE.name}) : aucun code espar dans contracts/species.csv "
                          f"(colonne tarif_nemeton_code), houppier sauté (rien n'est deviné)")
            continue
        values = {"CR_a": entry["CR_a"], "CR_b": entry["CR_b"], "R_a": entry["R_a"], "R_b": entry["R_b"]}
        absent = [term for term, value in values.items() if value is None]
        if absent:
            report.append(f"{name} ({BORNES_FILE.name}) : {', '.join(absent)} manquant, houppier sauté (rien n'est deviné)")
            continue
        n_trees = int(entry["n_arbres"]) if entry["n_arbres"] is not None else 0
        origin = (f"calé sur ses {n_trees} arbres" if entry["source"] == "essence" else entry["source"])
        if entry["source"] != "essence":
            report.append(f"{name} : coefficients de houppier empruntés ({entry['source']}), à vérifier")
        base = f"tarif-nemeton {BORNES_FILE.as_posix()} ({file_ref}), {origin} ; d130 en cm vérifié par import_tarif"
        for espar in codes:
            for term in ("CR_a", "CR_b"):
                rows.append({"species": espar, "species_group": None, "model": "hcb", "term": term,
                             "value": float(values[term]), "provisoire": True, "source": base})
            for term, value, ref in (("CR_min", cr_min, clip_ref), ("CR_max", cr_max, clip_ref)):
                rows.append({"species": espar, "species_group": None, "model": "hcb", "term": term,
                             "value": float(value), "provisoire": True,
                             "source": f"tarif-nemeton {ref} ({file_ref}) : écrêtage de CR dans la fonction forme ; "
                                       f"provisoire"})
            for term in ("R_a", "R_b"):
                rows.append({"species": espar, "species_group": None, "model": "cw", "term": term,
                             "value": float(values[term]), "provisoire": True, "source": base})
    return rows, report


# ------------------------------------------------------------------ tarif NEMETON v5 (mission 053)
TARIF_FILE = Path("resultats") / "tarif_v5" / "parametres_tarif_v5.csv"
TARIF_CSV_COLUMNS = ("essence_ou_groupe", "modele", "terme", "valeur", "unite", "source_code", "source_biblio")
CSV_GROUPS = {"feuillu": ("feuillu",), "conifere": ("resineux",), "tous": ("feuillu", "resineux")}
# (modèle, terme) du CSV -> (modèle, terme) du contrat import_tarif.tarif (description, CORRESPONDANCE)
TARIF_TERMS = {
    ("volume_feuillu", "a"): ("volume_feuillus", "a"),
    ("volume_feuillu", "b_logD"): ("volume_feuillus", "b"),
    ("volume_feuillu", "c_logH"): ("volume_feuillus", "c"),
    ("volume_feuillu", "sigma_log"): ("volume_feuillus", "sigma_log"),
    ("volume_feuillu", "facteur_biais_sigma2"): ("volume_feuillus", "facteur_biais_sigma2"),
    **{("profil_tige_resineux", t): ("profil_tige_resineux", t)
       for t in ("k0", "k1", "beta", "lam", "a", "x0", "sx", "h_ref", "D_ref")},
    **{("integration_tige_resineux", t): ("profil_tige_resineux", t) for t in ("n_points", "marge_sommet", "u_min")},
    **{("expansion_resineux", t): ("expansion_resineux", t) for t in ("a", "b", "D_plafond", "D_ref")},
    **{("infradensite", t): ("infradensite", t) for t in ("rho_moyenne", "rho_pente_10cm", "D_ref", "pas_D")},
    ("facteur_arbre_entier", "facteur"): ("infradensite", "facteur_arbre_entier"),
    ("carbone", "fraction_carbone"): ("fraction_carbone", "fraction"),
}
# constantes de la FORME du contrat volume_feuillus (ln(D/30), ln(H/25)) : vérifiées, non écrites
FORM_CONSTANTS = {("volume_feuillu", "D_ref"): (30.0, "cm"), ("volume_feuillu", "H_ref"): (25.0, "m")}
DOMAIN_HARDWOOD = ("D_min_calage", "D_max_calage", "H_min_calage", "H_max_calage")
DOMAIN_HARDWOOD_GROUP = ("facteur_D_min", "facteur_D_max", "marge_H")
DOMAIN_SOFTWOOD = ("HD_min", "HD_max")
# modèles du CSV qui ne servent pas à post : ni CO2 (plan T9), ni intervalle d'incertitude, ni grille de table
IGNORED_TARIF_MODELS = ("incertitude", "conversion", "grille_table")
TARIF_SCHEMA = pa.schema([
    ("essence", pa.string()), ("groupe", pa.string()), ("modele", pa.string()), ("terme", pa.string()),
    ("valeur", pa.float64()), ("unite", pa.string()), ("source_code", pa.string()), ("source_biblio", pa.string()),
    ("source_commit", pa.string()), ("provisoire", pa.bool_()),
])


def tarif_unit(text: str) -> str:
    """Unité du CSV dans la convention du contrat : « sans_unite » pour une grandeur sans dimension."""
    text = text.strip()
    if text.startswith("sans unité") or text in ("m/m", "t C / t matière sèche"):
        return "sans_unite"
    if not text:
        raise ModuleError("unité vide dans parametres_tarif_v5.csv : le contrat l'exige")
    return text


class Referral:
    """Lecture des renvois « fichier:ligne#colonne » d'une ligne sans valeur, sous le dossier tarif-nemeton."""

    def __init__(self, directory: Path):
        self.directory = directory.resolve()
        self.cache: dict[Path, list[dict]] = {}

    def value(self, reference: str, target: str, where: str) -> float:
        first = reference.split(" ; ")[0].strip()
        match = re.fullmatch(r"(.+):(\d+)#(\w+)", first)
        if not match:
            raise ModuleError(f"{where} : valeur vide et source_code « {reference} » n'est pas un renvoi fichier:ligne#colonne")
        path = (self.directory / match.group(1)).resolve()
        if not path.is_relative_to(self.directory) or not path.is_file():
            raise ModuleError(f"{where} : renvoi vers {match.group(1)}, fichier introuvable dans {self.directory}")
        if path not in self.cache:
            with path.open(encoding="utf-8-sig", newline="") as stream:
                self.cache[path] = list(csv.DictReader(stream))
        rows, line, column = self.cache[path], int(match.group(2)), match.group(3)
        if not 2 <= line <= len(rows) + 1:
            raise ModuleError(f"{where} : renvoi {first} hors du fichier")
        row = rows[line - 2]
        if row.get("essence") != target:
            raise ModuleError(f"{where} : renvoi {first} vise l'essence {row.get('essence')!r}, pas {target}")
        if column not in row:
            raise ModuleError(f"{where} : renvoi {first} : colonne {column} absente")
        value = _number(row[column], match.group(1), line, column)
        if value is None:
            raise ModuleError(f"{where} : renvoi {first} : case vide")
        return value


def read_tarif_csv(directory: Path) -> list[dict]:
    """Lignes de parametres_tarif_v5.csv, valeurs lues (renvois compris), numéro de ligne gardé."""
    path = directory / TARIF_FILE
    referral = Referral(directory)
    out, seen = [], set()
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = [c for c in TARIF_CSV_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ModuleError(f"{TARIF_FILE.as_posix()} : colonne(s) {', '.join(missing)} absente(s)")
        for row in reader:
            line = reader.line_num
            where = f"{TARIF_FILE.as_posix()} ligne {line}"
            target, model, term = (row[c].strip() for c in ("essence_ou_groupe", "modele", "terme"))
            if not target or not model or not term:
                raise ModuleError(f"{where} : essence_ou_groupe, modele et terme sont exigés")
            key = (target, model, term)
            if key in seen:
                raise ModuleError(f"{where} : {target} / {model} / {term} en double")
            seen.add(key)
            value = _number(row["valeur"], TARIF_FILE.name, line, "valeur")
            if value is None:
                value = referral.value(row["source_code"], target, where)
            out.append({"target": target, "model": model, "term": term, "value": value, "unit": row["unite"],
                        "source_code": row["source_code"].strip(), "source_biblio": row["source_biblio"].strip(),
                        "line": line})
    return out


def build_tarif_rows(directory: Path, espar_mapping: dict[str, list[str]]) -> tuple[list[dict], list[str]]:
    """Lignes de params/tarif.parquet (contrat import_tarif.tarif) et signalements."""
    commit = read_commit(directory)
    if not commit:
        raise ModuleError(f"commit de tarif-nemeton illisible dans {directory / '.git'} : source_commit est exigé "
                          "par le contrat (décision Q1 : un tarif figé à un commit cité)")
    csv_rows = read_tarif_csv(directory)
    report: list[str] = []
    file = TARIF_FILE.as_posix()

    def source(r: dict) -> str:
        return f"tarif-nemeton {file}:{r['line']} ({r['source_code']})"

    def targets(name: str) -> tuple[list[str], list[str]] | None:
        """(codes espar, groupes) d'une cible du CSV ; None : nom latin sans code espar (signalé, sauté)."""
        if name in CSV_GROUPS:
            return [], list(CSV_GROUPS[name])
        codes = espar_mapping.get(name)
        return (list(codes), []) if codes else None

    rows: dict[tuple, dict] = {}

    def add(essence, groupe, model, term, value, unit, code, biblio):
        key = (essence or "", groupe or "", model, term)
        if key in rows:
            raise ModuleError(f"{file} : deux valeurs pour {essence or groupe} / {model} / {term} après correspondance "
                              "des noms : on ne choisit pas")
        rows[key] = {"essence": essence, "groupe": groupe, "modele": model, "terme": term, "valeur": float(value),
                     "unite": unit, "source_code": code, "source_biblio": biblio or "non citée",
                     "source_commit": commit, "provisoire": True}

    skipped, ignored, domain_parts = set(), set(), defaultdict(dict)
    for r in csv_rows:
        key = (r["model"], r["term"])
        resolved = targets(r["target"])
        if resolved is None:
            skipped.add(r["target"])
            continue
        if r["model"] in IGNORED_TARIF_MODELS:
            ignored.add(r["model"])
            continue
        if key in FORM_CONSTANTS:
            expected, unit = FORM_CONSTANTS[key]
            if r["value"] != expected or tarif_unit(r["unit"]) != unit:
                raise ModuleError(f"{file} ligne {r['line']} : {r['term']} = {r['value']} {r['unit']} ; la forme du "
                                  f"contrat volume_feuillus suppose {expected:g} {unit} : la forme a changé, rien n'est écrit")
            report.append(f"{r['term']} = {expected:g} {unit} de volume_feuillus ({file}:{r['line']}) : conforme à la forme "
                          "du contrat, non écrit")
            continue
        if r["model"] in ("domaine_feuillu", "domaine_resineux"):
            known = DOMAIN_HARDWOOD + DOMAIN_HARDWOOD_GROUP + DOMAIN_SOFTWOOD
            if r["term"] not in known:
                raise ModuleError(f"{file} ligne {r['line']} : terme de domaine {r['term']} inconnu de la correspondance")
            domain_parts[r["target"]][r["term"]] = r
            continue
        if key not in TARIF_TERMS:
            raise ModuleError(f"{file} ligne {r['line']} : {r['model']} / {r['term']} n'a pas de correspondance dans le "
                              "contrat import_tarif.tarif : rien n'est deviné (adapter le contrat et import_tarif)")
        model, term = TARIF_TERMS[key]
        codes, groups = resolved
        for espar in codes:
            add(espar, None, model, term, r["value"], tarif_unit(r["unit"]), source(r), r["source_biblio"])
        for groupe in groups:
            add(None, groupe, model, term, r["value"], tarif_unit(r["unit"]), source(r), r["source_biblio"])

    # domaine : celui que tarif-nemeton applique à sa table (bornes de calage du v0, facteurs et marge)
    hw_group = domain_parts.get("feuillu", {})
    sw_group = domain_parts.get("conifere", {})
    for name, parts in sorted(domain_parts.items()):
        if name in CSV_GROUPS:
            continue
        codes = espar_mapping.get(name) or []
        have = [t for t in DOMAIN_HARDWOOD if t in parts]
        if not have:
            continue
        absent = [t for t in DOMAIN_HARDWOOD if t not in parts] + [t for t in DOMAIN_HARDWOOD_GROUP if t not in hw_group]
        if absent:
            raise ModuleError(f"{file} : domaine de {name} incomplet ({', '.join(absent)} absent) : rien n'est deviné")
        derived = (("dbh_min", parts["D_min_calage"], hw_group["facteur_D_min"], lambda v, f: v * f, "cm"),
                   ("dbh_max", parts["D_max_calage"], hw_group["facteur_D_max"], lambda v, f: v * f, "cm"),
                   ("h_min", parts["H_min_calage"], hw_group["marge_H"], lambda v, f: v - f, "m"),
                   ("h_max", parts["H_max_calage"], hw_group["marge_H"], lambda v, f: v + f, "m"))
        for term, base, factor, op, unit in derived:
            if tarif_unit(base["unit"]) != unit:
                raise ModuleError(f"{file} ligne {base['line']} : {base['term']} en « {base['unit']} », {unit} attendu")
            for espar in codes:
                add(espar, None, "domaine", term, op(base["value"], factor["value"]), unit,
                    f"{source(base)} ; {source(factor)} (domaine de la table de tarif-nemeton)",
                    f"{base['source_biblio']} ; {factor['source_biblio']}")
    softwood = sorted({r["essence"] for r in rows.values() if r["modele"] == "profil_tige_resineux" and r["essence"]})
    if softwood:
        absent = [t for t in DOMAIN_SOFTWOOD if t not in sw_group]
        if absent:
            raise ModuleError(f"{file} : domaine des résineux incomplet ({', '.join(absent)} absent) : rien n'est deviné")
        for term, csv_term in (("hd_min", "HD_min"), ("hd_max", "HD_max")):
            r = sw_group[csv_term]
            for espar in softwood:
                add(espar, None, "domaine", term, r["value"], tarif_unit(r["unit"]), source(r), r["source_biblio"])
        report.append(f"résineux {', '.join(softwood)} : domaine borné en H/D seulement (la source ne borne ni le "
                      "diamètre ni la hauteur)")
    for name in sorted(skipped):
        report.append(f"{name} ({file}) : aucun code espar dans contracts/species.csv (colonne tarif_nemeton_code), "
                      "tarif sauté (rien n'est deviné)")
    for name, codes in sorted(espar_mapping.items()):
        if len(codes) > 1 and any(r["essence"] in codes for r in rows.values()):
            report.append(f"{name} : tarif écrit pour les espar {', '.join(codes)} (docs/referentiels/species.md : "
                          f"{name} = ces codes et rien d'autre)")
    if ignored:
        report.append(f"modèle(s) {', '.join(sorted(ignored))} de {file} non importé(s) : post n'en a pas l'usage "
                      "(ni CO2, ni intervalle d'incertitude, ni grille de table)")
    report.append("modèle racines absent de la source (GIEC 2006, tableau 4.4, pas encore lu) : aucune ligne, post "
                  "n'écrira pas de carbone des racines")
    if not any(r["modele"] in ("volume_feuillus", "profil_tige_resineux") for r in rows.values()):
        raise ModuleError(f"{file} : aucun modèle de volume pour une essence du référentiel : rien à écrire")
    out = sorted(rows.values(), key=lambda r: ((r["essence"] or "").encode(), r["groupe"] or "", r["modele"], r["terme"]))
    return out, report


def write_tarif(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows, schema=TARIF_SCHEMA), path)


def import_tarif_v5(config: dict, directory: Path, espar_mapping: dict[str, list[str]]) -> Path | None:
    """params/tarif.parquet depuis parametres_tarif_v5.csv ; None si le fichier n'existe pas (signalé)."""
    output = zone_dir(config) / "params" / "tarif.parquet"
    if not (directory / TARIF_FILE).is_file():
        kept = f" ; {output} existant conservé tel quel" if output.is_file() else " ; post refusera sans params/tarif.parquet"
        print(f"[{NAME}] {TARIF_FILE.as_posix()} absent de {directory} (fichier de la mission 050, PR de tarif-nemeton) : "
              f"tarif non importé, rien n'est inventé{kept}", file=sys.stderr)
        return None
    rows, report = build_tarif_rows(directory, espar_mapping)
    staging = output.with_name(".tarif_en_cours.parquet")
    write_tarif(rows, staging)
    try:
        code = call_validator(["import_tarif.tarif", str(staging)])
        if code != 0:
            raise ModuleError(f"tarif non conforme au contrat import_tarif.tarif (validateur, code {code}) ; rien n'est écrit")
        os.replace(staging, output)
    finally:
        staging.unlink(missing_ok=True)
    for text in report:
        print(f"[{NAME}] {text}", file=sys.stderr)
    models = sorted({r["modele"] for r in rows})
    species_codes = sorted({r["essence"] for r in rows if r["essence"]})
    print(f"[{NAME}] {len(rows)} terme(s) de tarif ({', '.join(models)}) pour {len(species_codes)} essence(s) "
          f"({', '.join(species_codes)}), commit {rows[0]['source_commit']}, provisoire : {output}", file=sys.stderr)
    return output


def write_allometry(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = {name: [row[name] for row in rows] for name in SCHEMA.names}
    pq.write_table(pa.table(columns, schema=SCHEMA), path)


def run_import(config: dict) -> Path:
    """Lit tarif-nemeton, écrit params/allometry.parquet, le fait valider ; rend son chemin."""
    external_dir = (config.get("external") or {}).get("tarif_nemeton_dir")
    if not external_dir:
        # Rien à importer : aucun coefficient n'est inventé. Si params/allometry.parquet existe déjà
        # (jeu fictif versionné), il est laissé tel quel et le module le dit ; sinon, code 2.
        existing = zone_dir(config) / "params" / "allometry.parquet"
        if existing.is_file():
            print(f"[{NAME}] external.tarif_nemeton_dir absent de config.yml : rien à importer, "
                  f"{existing} existant conservé tel quel", file=sys.stderr)
            return existing
        raise ModuleError("config.yml : external.tarif_nemeton_dir absent et aucun "
                           f"params/allometry.parquet existant ({existing}) : rien n'est inventé")
    directory = Path(external_dir)
    if not directory.is_dir():
        raise ModuleError(f"external.tarif_nemeton_dir : dossier introuvable : {directory}")
    espar_mapping = read_espar_mapping(root() / "contracts" / "species.csv")
    rows, report = build_rows(directory, espar_mapping)
    # le tarif d'abord : un tarif refusé (code 2) ne laisse pas une allométrie neuve à côté d'un tarif ancien
    import_tarif_v5(config, directory, espar_mapping)
    output = zone_dir(config) / "params" / "allometry.parquet"
    write_allometry(rows, output)
    for text in report:
        print(f"[{NAME}] {text}", file=sys.stderr)
    code = call_validator(["import_tarif.allometry", str(output)])
    if code != 0:
        raise ModuleError(f"{output} non conforme au contrat import_tarif.allometry (validateur, code {code})")
    species_codes = sorted({row["species"] for row in rows})
    print(f"[{NAME}] {len(rows)} coefficient(s) (etage_b, hcb, cw) pour {len(species_codes)} essence(s) "
          f"({', '.join(species_codes)}), provisoire : {output}", file=sys.stderr)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=NAME, exit_on_error=False)
    parser.add_argument("--config", default="config.yml", help="chemin de config.yml")
    try:
        options = parser.parse_args(argv)
    except (argparse.ArgumentError, SystemExit):
        return EXIT_IMPOSSIBLE
    try:
        config = read_config(options.config)
        code = call_validator(["config", str(options.config)])
        if code != 0:
            raise ModuleError(f"config.yml non conforme (validateur, code {code})")
        run_import(config)
    except ModuleError as error:
        print(f"[{NAME}] erreur : {error}", file=sys.stderr)
        return EXIT_IMPOSSIBLE
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
