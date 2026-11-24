"""Ligne de commande de `contracts/validate` : arguments, messages, codes de sortie.

Codes de sortie (contracts/README.md ; bench/SPEC.md AM3) :
- 0 : tout est conforme ;
- 2 : le contrôle n'a pas pu se faire (arguments invalides, contrat inconnu, fichier absent) ;
- 3 : au moins un fichier est non conforme, y compris illisible ou d'un autre format.
"""
import sys
from pathlib import Path

from . import catalog, csv_files, geopackage, geotiff, gltf, json_docs, parquet_files
from .report import NONCONFORM, OK, REFUSED, Findings, Refused

PROG = "contracts/validate"
USAGE = f"""usage :
  {PROG} <contrat> <chemin> [<chemin>...]       contrôle des fichiers contre un contrat
  {PROG} --contract <contrat> <chemin>...       même chose
  {PROG} --zone <dossier> [--require-outputs]   tous les fichiers du catalogue sous <dossier>
  {PROG} --list                                 liste des contrats
options :
  --grid <grid.tif>     grille de référence pour l'alignement (variante grille)
  --max-errors <N>      nombre d'écarts affichés par fichier (50 par défaut)
  --require-outputs     avec --zone : les sorties des modules deviennent obligatoires
codes de sortie : 0 conforme, 2 contrôle impossible, 3 non conforme"""


class UsageError(Refused):
    """Arguments invalides : code 2, avec l'aide d'utilisation."""


class Args:
    def __init__(self):
        self.contract = None
        self.paths = []
        self.zone = None
        self.grid = None
        self.list = False
        self.require_outputs = False
        self.help = False
        self.max_errors = 50


def parse(argv):
    """Arguments ; Refused (code 2) avec un message français s'ils sont invalides."""
    args = Args()
    rest = list(argv)
    positional = []

    def value(option):
        if not rest:
            raise UsageError(f"argument invalide : {option} attend une valeur")
        return rest.pop(0)

    while rest:
        item = rest.pop(0)
        if item in ("-h", "--help", "--aide"):
            args.help = True
        elif item == "--require-outputs":
            args.require_outputs = True
        elif item == "--list":
            args.list = True
        elif item == "--contract":
            args.contract = value(item)
        elif item == "--zone":
            args.zone = Path(value(item))
        elif item == "--grid":
            args.grid = Path(value(item))
        elif item == "--max-errors":
            text = value(item)
            if not text.isdigit() or int(text) < 1:
                raise UsageError(f"argument invalide : --max-errors attend un entier positif, "
                              f"trouvé {text}")
            args.max_errors = int(text)
        elif item.startswith("--"):
            raise UsageError(f"argument invalide : option inconnue {item}")
        else:
            positional.append(item)
    if args.help or args.list:
        return args
    if args.zone is not None:
        if positional or args.contract:
            raise UsageError("argument invalide : --zone ne se combine pas avec un contrat")
        return args
    if args.require_outputs:
        raise UsageError("argument invalide : --require-outputs ne s'emploie qu'avec --zone")
    if args.contract is None:
        if not positional:
            raise UsageError("arguments manquants : un contrat et au moins un fichier sont "
                          "obligatoires")
        args.contract = positional.pop(0)
    if not positional:
        raise UsageError(f"argument manquant : fichier à contrôler contre le contrat "
                      f"{args.contract}")
    args.paths = [Path(p) for p in positional]
    return args


def check_path(name, path, grid=None):
    """Écarts d'un fichier (ou dossier Parquet) au contrat `name` : [(fichier, Findings)]."""
    spec = catalog.get(name)
    kind = spec["kind"]
    options = spec.get("options", {})
    if not path.exists():
        raise Refused(f"fichier absent : {path}")
    if path.is_dir() and kind != "parquet":
        findings = Findings()
        findings.error("fichier attendu, dossier trouvé")
        return [(path, findings)]
    if kind == "parquet":
        return parquet_files.check(path, catalog.load_schema(spec["schema"]), options)
    if kind == "csv":
        return csv_files.check(path, catalog.load_schema(spec["schema"]), options)
    if kind == "geopackage":
        return geopackage.check(path, [catalog.load_schema(s) for s in spec["schemas"]])
    if kind in ("yaml", "json"):
        return json_docs.check(path, spec["schema"], kind)
    if kind == "geotiff":
        return geotiff.check(path, options, grid_path=grid)
    if kind == "glb":
        return gltf.check(path, options)
    raise Refused(f"contrat invalide : couche {kind} inconnue")


def print_results(name, results, max_errors):
    """Affiche le verdict de chaque fichier ; rend le nombre de fichiers non conformes."""
    bad = 0
    for file, findings in results:
        for warning in findings.warnings:
            print(f"{PROG} : {file} : contrat {name} : avertissement : {warning}",
                  file=sys.stderr)
        if findings.errors:
            bad += 1
            for message in findings.errors[:max_errors]:
                print(f"{PROG} : {file} : contrat {name} : {message}", file=sys.stderr)
            extra = len(findings.errors) - max_errors
            if extra > 0:
                print(f"{PROG} : {file} : contrat {name} : … et {extra} autre(s) écart(s)",
                      file=sys.stderr)
            print(f"non conforme : {file} (contrat {name}, {len(findings.errors)} écart(s))",
                  file=sys.stderr)
        else:
            print(f"conforme : {file} (contrat {name})")
    return bad


def run_contract(args):
    name = catalog.resolve(args.contract)
    bad = 0
    for path in args.paths:
        bad += print_results(name, check_path(name, path, args.grid), args.max_errors)
    return NONCONFORM if bad else OK


def zone_required(name, spec, require_outputs):
    """Obligatoire en mode --zone : les entrées, et les sorties avec --require-outputs."""
    if name.startswith("inputs."):
        return bool(spec.get("required"))
    return require_outputs or bool(spec.get("required"))


def run_zone(args):
    """Contrôle de toute une zone. Un fichier en écart ou impossible à contrôler n'arrête
    pas la suite. Code final : 3 s'il y a un fichier non conforme, sinon 2 s'il y a un
    fichier absent ou impossible à contrôler, sinon 0."""
    zone = args.zone
    if not zone.is_dir():
        raise Refused(f"dossier de zone absent : {zone}")
    grid = zone / "grid.tif"
    grid = grid if grid.is_file() else args.grid
    bad = checked = refused = 0
    missing = []
    for name, spec in catalog.load().items():
        found = []
        for pattern in spec.get("paths", []):
            found.extend(sorted(zone.glob(pattern)))
        if not found and spec.get("paths") and zone_required(name, spec, args.require_outputs):
            missing.append((name, spec["paths"][0]))
        for path in found:
            checked += 1
            try:
                results = check_path(name, path, grid)
            except Refused as exc:
                refused += 1
                print(f"{PROG} : {path} : contrat {name} : {exc}", file=sys.stderr)
                continue
            except Exception as exc:  # défaut du validateur : on le dit, on continue
                refused += 1
                print(f"{PROG} : {path} : contrat {name} : erreur interne du validateur, "
                      f"contrôle impossible ({exc.__class__.__name__} : {exc})",
                      file=sys.stderr)
                continue
            bad += print_results(name, results, args.max_errors)
    for name, relative in missing:
        print(f"{PROG} : {zone / relative} : contrat {name} : fichier obligatoire absent",
              file=sys.stderr)
    print(f"zone {zone} : {checked} fichier(s) contrôlé(s), {bad} non conforme(s), "
          f"{refused} impossible(s) à contrôler, {len(missing)} obligatoire(s) absent(s)")
    if bad:
        return NONCONFORM
    return REFUSED if missing or refused else OK


def run_list():
    for name, spec in catalog.load().items():
        aliases = spec.get("aliases", [])
        short = f" (aussi : {', '.join(aliases)})" if aliases else ""
        paths = ", ".join(spec.get("paths", [])) or "hors zone"
        print(f"{name}{short} : {spec['kind']} ; {paths}")
    return OK


def main(argv):
    try:
        args = parse(argv)
        if args.help:
            print(USAGE)
            return OK
        if args.list:
            return run_list()
        if args.zone is not None:
            return run_zone(args)
        return run_contract(args)
    except UsageError as exc:
        print(f"{PROG} : {exc}", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return REFUSED
    except Refused as exc:
        print(f"{PROG} : {exc}", file=sys.stderr)
        return REFUSED
    except Exception as exc:  # défaut du validateur lui-même : jamais un faux verdict
        print(f"{PROG} : erreur interne du validateur, contrôle impossible "
              f"({exc.__class__.__name__} : {exc})", file=sys.stderr)
        return REFUSED
