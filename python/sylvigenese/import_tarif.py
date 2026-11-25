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

Source des CSV : https://github.com/pobsteta/tarif-nemeton (dépôt sans licence : seuls des
résultats sont lus ; le commit lu est cité dans la colonne `source`).
Sortie : `data/<zone>/params/allometry.parquet` (jeu fictif : `tests/fixtures/zone_fictive`),
sous la racine `SYLVIGENESE_ROOT` (défaut : dossier courant). Le fichier écrit est validé par
`contracts/validate import_tarif.allometry` avant le code de sortie 0.
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import sys
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
    rows.sort(key=lambda r: (r["species"].encode(), r["term"]))
    return rows, report


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
    rows, report = build_rows(directory, read_espar_mapping(root() / "contracts" / "species.csv"))
    output = zone_dir(config) / "params" / "allometry.parquet"
    write_allometry(rows, output)
    for text in report:
        print(f"[{NAME}] {text}", file=sys.stderr)
    code = call_validator(["import_tarif.allometry", str(output)])
    if code != 0:
        raise ModuleError(f"{output} non conforme au contrat import_tarif.allometry (validateur, code {code})")
    species_codes = sorted({row["species"] for row in rows})
    print(f"[{NAME}] {len(rows)} coefficient(s) etage_b pour {len(species_codes)} essence(s) "
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
