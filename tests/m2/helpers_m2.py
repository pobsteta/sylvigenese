"""Outils communs des tests d'acceptation M2a (mission 026).

Ces tests partent de la spec (docs/spec.md §6 et §11), de docs/referentiels/ifn-dynamique.md, des
contrats (contracts/) et du README du jeu fictif ; ils ne lisent ni R/ ni python/. Rien ici ne saute
un test : une sortie absente est un échec, jamais un « skip » (le script de CI refuse tout test sauté).

Le principe de l'oracle : les comptes attendus (arbres coupés, non retrouvés, perdus, placettes
écartées, recrues, effectif à risque par essence) sont recalculés ICI, depuis les fichiers d'entrée
IFN bruts (inputs/ifn/*.csv, aux noms de colonnes de l'export), avec les règles écrites dans la spec
§6 « Données d'ajustement ». Ils ne sont jamais lus dans le code du module.
"""
from __future__ import annotations

import csv
import math
import os
import re
import shutil
import subprocess
import unicodedata
from collections import defaultdict
from pathlib import Path

import pyarrow.dataset as pds

ROOT = Path(__file__).resolve().parents[2]
ZONE = ROOT / "tests" / "fixtures" / "zone_fictive"
VALIDATE = ROOT / "contracts" / "validate"
SPECIES_CSV = ROOT / "contracts" / "species.csv"

R_LOAD = 'for (f in list.files("R", pattern = "[.]R$", full.names = TRUE)) source(f)'

PARAMS = ("growth", "mortality", "recruitment", "height_curve")
RAPPORT = "rapport_dynamics.html"

# Codes de VEGET5 pour une 2e visite de campagne >= 2019 (VEGET59, metadonnees.csv l. 6092-6099 ;
# docs/referentiels/ifn-dynamique.md §4). Le jeu fictif n'a que des 2e visites de 2020 à 2025.
VIVANT = {"0", "1"}
MORT_NATURELLE = {"M", "2"}
COUPE = {"6", "7"}
NON_RETROUVE = {"N"}
PERDU = {"T"}
ESSENCE_CIBLE = "09"       # la plus fréquente du jeu fictif : les retraits y pèsent
ESSENCE_DOMAINE = "62"     # celle de l'arbre exceptionnel de la zone « domaine »
NOUVELLES_RECRUES = 6      # C13 = 0,236 m : recensables
SOUS_LE_SEUIL = 3          # C13 = 0,234 m : non recensables, pas des recrues
RECRUES_SANS_POIDS = 2     # parmi les nouvelles : W manquant
PLEIN_FILE = ("C13", "IR5", "HTOT", "V", "W")  # colonnes vidées sur un arbre coupé ou non retrouvé


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


def run_make(*targets: str, zone: str = "zone_fictive", config: Path | None = None,
             timeout: int = 1800) -> subprocess.CompletedProcess:
    cmd = ["make", *targets, f"ZONE={zone}"]
    if config is not None:
        cmd.append(f"CONFIG={config}")
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, env=offline_env(),
                          timeout=timeout)


def run_module_status(module: str, config: Path, timeout: int = 1800) -> subprocess.CompletedProcess:
    """Appelle run_<module>() comme le Makefile, pour lire son code de sortie exact (make renvoie
    toujours 2 en cas d'échec : il masque les codes 2 et 3 de la spec §6)."""
    expr = f'{R_LOAD}; quit(status = run_{module}("{config}"))'
    return subprocess.run(["Rscript", "-e", expr], cwd=ROOT, capture_output=True, text=True,
                          env=offline_env(), timeout=timeout)


def validate(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["python3", str(VALIDATE), *args], cwd=ROOT, capture_output=True, text=True)


def rscript(expr: str) -> subprocess.CompletedProcess:
    return subprocess.run(["Rscript", "-e", R_LOAD + "; " + expr], cwd=ROOT, capture_output=True,
                          text=True, env=offline_env())


# ------------------------------------------------------------------ zones
def clean_outputs(zone_dir: Path) -> None:
    """Efface les sorties de prepare (IFN) et de dynamics, jamais les entrées ni allometry/tarif."""
    for rel in ("ifn/plots.parquet", "ifn/trees.parquet", "ifn/flora.parquet", RAPPORT,
                *[f"params/{p}.parquet" for p in PARAMS]):
        f = zone_dir / rel
        if f.is_file():
            f.unlink()


def _write_config(zone_dir: Path, name: str) -> Path:
    text = (ROOT / "config.yml").read_text(encoding="utf-8")
    text = re.sub(r"(?m)^zone:\s*\S+", f"zone: {name}", text)
    cfg = zone_dir / "config_m2.yml"
    cfg.write_text(text, encoding="utf-8")
    return cfg


def make_zone_copy(name: str, mutate=None) -> tuple[Path, Path]:
    """Copie inputs/ et params/ du jeu fictif sous data/<name>/ (hors dépôt, ignoré par git),
    applique `mutate(zone_dir)`, écrit une config pointant sur <name>. Renvoie (zone_dir, config)."""
    zone_dir = ROOT / "data" / name
    if zone_dir.exists():
        shutil.rmtree(zone_dir)
    zone_dir.mkdir(parents=True)
    shutil.copytree(ZONE / "inputs", zone_dir / "inputs")
    shutil.copytree(ZONE / "params", zone_dir / "params")
    for p in PARAMS:  # jamais de sortie périmée venue du jeu fictif
        (zone_dir / "params" / f"{p}.parquet").unlink(missing_ok=True)
    if mutate is not None:
        mutate(zone_dir)
    return zone_dir, _write_config(zone_dir, name)


def clone_zone(src_name: str, name: str, mutate=None) -> tuple[Path, Path]:
    """Copie complète d'une zone déjà préparée (sorties comprises), sans relancer prepare."""
    src = ROOT / "data" / src_name
    zone_dir = ROOT / "data" / name
    if zone_dir.exists():
        shutil.rmtree(zone_dir)
    shutil.copytree(src, zone_dir)
    clean_outputs_dynamics(zone_dir)
    if mutate is not None:
        mutate(zone_dir)
    return zone_dir, _write_config(zone_dir, name)


def clean_outputs_dynamics(zone_dir: Path) -> None:
    for rel in (RAPPORT, *[f"params/{p}.parquet" for p in PARAMS]):
        (zone_dir / rel).unlink(missing_ok=True)


def remove_zone_copy(name: str) -> None:
    shutil.rmtree(ROOT / "data" / name, ignore_errors=True)
    data = ROOT / "data"
    if data.is_dir() and not any(data.iterdir()):
        data.rmdir()


def dynamics_outputs(zone_dir: Path) -> list[str]:
    """Sorties de dynamics présentes sous zone_dir (une sortie à moitié = au moins une présente)."""
    return [r for r in (RAPPORT, *[f"params/{p}.parquet" for p in PARAMS]) if (zone_dir / r).exists()]


# ------------------------------------------------------------------ CSV IFN (export brut)
def read_csv(path: Path) -> tuple[list[str], list[dict]]:
    with open(path, encoding="utf-8", newline="") as f:
        r = csv.DictReader(f, delimiter=";")
        rows = list(r)
        return list(r.fieldnames), rows


def write_csv(path: Path, header: list[str], rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header, delimiter=";", lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in header})


def edit_ifn(zone_dir: Path, fn) -> None:
    """fn(plots_header, plots, trees_header, trees, flora_header, flora) modifie les listes en place."""
    d = zone_dir / "inputs" / "ifn"
    ph, plots = read_csv(d / "PLACETTE.csv")
    ah, trees = read_csv(d / "ARBRE.csv")
    fh, flora = read_csv(d / "FLORE.csv")
    out = fn(ph, plots, ah, trees, fh, flora)
    ph, plots, ah, trees, fh, flora = out if out else (ph, plots, ah, trees, fh, flora)
    write_csv(d / "PLACETTE.csv", ph, plots)
    write_csv(d / "ARBRE.csv", ah, trees)
    write_csv(d / "FLORE.csv", fh, flora)


def mm(texte: str) -> int:
    """C13 de l'export en mètres, ramené à des millimètres entiers (seuils sans bruit flottant)."""
    return round(float(texte.replace(",", ".")) * 1000)


def d130_cm(c13_m: float) -> float:
    return c13_m * 100 / math.pi


def species_referentiel() -> set[str]:
    with open(SPECIES_CSV, encoding="utf-8", newline="") as f:
        return {r["espar"] for r in csv.DictReader(f)}


# ------------------------------------------------------------------ l'oracle
class Ifn:
    """Lecture des entrées IFN d'une zone et comptes attendus selon spec §6 (Données d'ajustement)."""

    def __init__(self, zone_dir: Path, sans_station: set[str] | None = None):
        self.sans_station = set(sans_station or ())
        d = Path(zone_dir) / "inputs" / "ifn"
        self.plots_header, self.plots = read_csv(d / "PLACETTE.csv")
        self.trees_header, self.trees = read_csv(d / "ARBRE.csv")
        self.flora_header, self.flora = read_csv(d / "FLORE.csv")
        self.visit = {(p["CAMPAGNE"], p["IDP"]): int(p["VISITE"]) for p in self.plots}
        self.by_tree: dict[tuple[str, str], dict[int, dict]] = defaultdict(dict)
        for t in self.trees:
            self.by_tree[(t["IDP"], t["A"])][self.visit[(t["CAMPAGNE"], t["IDP"])]] = t
        self.plot_rows: dict[str, dict[int, dict]] = defaultdict(dict)
        for p in self.plots:
            self.plot_rows[p["IDP"]][int(p["VISITE"])] = p

    # --- placettes
    def revisited_plots(self) -> set[str]:
        return {i for i, v in self.plot_rows.items() if 1 in v and 2 in v}

    def _flag(self, idp: str, cols: tuple[str, ...], pred) -> bool:
        return any(pred(p.get(c, "")) for p in self.plot_rows[idp].values() for c in cols)

    def incident_plots(self) -> set[str]:
        """Placettes à incident signalé (NINCID différent de 0 ; spec §6)."""
        return {i for i in self.plot_rows if self._flag(i, ("NINCID",), lambda v: v not in ("", "0"))}

    def treated_plots(self) -> set[str]:
        """Placettes à défrichement (DEF5 >= 1) ou installation de peuplement (INSTP5 = 1) entre les
        deux visites. La spec dit « incident ou prélèvement » : ranger ces deux colonnes dans les
        placettes écartées (arbitrage du 25/11/2026)."""
        return {i for i in self.plot_rows
                if self._flag(i, ("DEF5", "INSTP5"), lambda v: v not in ("", "0"))}

    def travaux_ou_incident(self) -> set[str]:
        """Placettes écartées pour incident (NINCID != 0), défrichement (DEF5 >= 1) ou plantation
        (INSTP5 = 1) : arbitrage du 25/11/2026, spec §6. PRELEV5 est gardée et signalée, pas écartée."""
        return self.incident_plots() | self.treated_plots()

    def definitions(self) -> dict[str, set[str]]:
        """Placettes exclues de l'ajustement : celles ci-dessus, et celles sans aucune valeur de
        station (disque de 700 m hors du raster), exclues et comptées (arbitrage du 25/11/2026)."""
        return {"ecartees": self.travaux_ou_incident() | self.sans_station}

    # --- mortalité
    def at_risk(self, excluded: set[str]) -> list[tuple[dict, dict]]:
        """Arbres vivants (VEGET = 0) à la 1re visite, revus, hors placettes écartées : (ligne 1re
        visite, ligne 2e visite)."""
        out = []
        for (idp, _a), v in self.by_tree.items():
            if 1 in v and 2 in v and v[1]["VEGET"] == "0" and idp not in excluded:
                out.append((v[1], v[2]))
        return out

    def mortality_counts(self, excluded: set[str]) -> dict[str, dict[str, int]]:
        """Par essence : effectif à risque (vivants + morts naturels), morts, et arbres retirés."""
        res: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for t1, t2 in self.at_risk(excluded):
            c = res[t1["ESPAR"]]
            s = t2["VEGET5"]
            if s in VIVANT:
                c["n"] += 1
            elif s in MORT_NATURELLE:
                c["n"] += 1
                c["morts"] += 1
            elif s in COUPE:
                c["coupes"] += 1
            elif s in NON_RETROUVE:
                c["non_retrouves"] += 1
            elif s in PERDU:
                c["perdus"] += 1
        return res

    def removed_totals(self, excluded: set[str]) -> dict[str, int]:
        tot: dict[str, int] = defaultdict(int)
        for c in self.mortality_counts(excluded).values():
            for k in ("coupes", "non_retrouves", "perdus"):
                tot[k] += c.get(k, 0)
        return dict(tot)

    # --- recrutement
    def recruits(self, excluded: set[str]) -> list[dict]:
        """Arbres de 2e visite sans 1re visite, recensables (C13 >= 0,235 m), hors placettes écartées."""
        return [v[2] for (idp, _a), v in self.by_tree.items()
                if 2 in v and 1 not in v and idp not in excluded
                and v[2]["C13"].strip() and mm(v[2]["C13"]) >= 235]

    def recruits_sans_poids(self, excluded: set[str]) -> int:
        return sum(1 for t in self.recruits(excluded) if not t["W"].strip())


def station_disc_pixels(raster: Path, x: float, y: float, rayon: float = 700.0):
    """Valeurs (par bande) des mailles dont le centre est à moins de `rayon` du point (x, y), nodata
    écarté : le disque de la spec §6 (coarse_*_700m), recalculé ici sans le code du module."""
    import numpy as np
    import rasterio
    with rasterio.open(raster) as r:
        arr, nd, t = r.read().astype("float64"), r.nodata, r.transform
        noms = list(r.descriptions)
    cols, rows = np.meshgrid(np.arange(arr.shape[2]), np.arange(arr.shape[1]))
    cx, cy = t.c + (cols + 0.5) * t.a, t.f + (rows + 0.5) * t.e
    m = (cx - x) ** 2 + (cy - y) ** 2 <= rayon ** 2
    out = {}
    for i, nom in enumerate(noms):
        ok = m & np.isfinite(arr[i]) & (arr[i] != nd if nd is not None else True)
        out[nom] = arr[i][ok]
    return out


def plots_sans_station(zone_dir: Path) -> set[str]:
    """IDP des placettes dont le disque de 700 m ne touche aucune maille de station_gradients.tif."""
    _h, plots = read_csv(Path(zone_dir) / "inputs" / "ifn" / "PLACETTE.csv")
    raster = Path(zone_dir) / "inputs" / "station_gradients.tif"
    return {p["IDP"] for p in plots
            if not station_disc_pixels(raster, float(p["XL"]), float(p["YL"]))["hydric"].size}


def ifn_de(zone_dir: Path) -> "Ifn":
    return Ifn(zone_dir, plots_sans_station(zone_dir))


# ------------------------------------------------------------------ rapport HTML
MOJIBAKE = re.compile(r"Ã[\u0080-¿]|Â[\u0080-¿]|<U\+[0-9A-Fa-f]{4}>|\\u[0-9a-fA-F]{4}|�")


def sans_accent(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn").lower()


def decode_report(path: Path) -> str:
    """UTF-8 STRICT, et refus des accents mal encodés (double encodage, <U+00E9>, remplacement)."""
    path = Path(path)
    assert path.is_file(), f"rapport absent : {path}"
    try:
        txt = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as e:
        raise AssertionError(f"{path.name} n'est pas de l'UTF-8 valide : {e}") from e
    m = MOJIBAKE.search(txt)
    assert not m, f"{path.name} : accent mal encodé près de « {txt[max(m.start() - 20, 0):m.end() + 20]} »"
    return txt


def html_blocks(path: Path) -> list[str]:
    """Texte d'un rapport découpé en blocs : ligne de tableau, item, paragraphe, titre."""
    raw = decode_report(path)
    parts = re.split(r"(?is)</?(?:tr|li|p|div|br|h[1-6]|table|ul|ol|section)\b[^>]*>", raw)
    out = []
    for p in parts:
        t = re.sub(r"(?s)<[^>]+>", " ", p)
        t = re.sub(r"\s+", " ", t).strip()
        if t:
            out.append(t)
    return out


def blocks_with(blocks: list[str], *needles: str) -> list[str]:
    """Blocs qui contiennent TOUS les termes (sans accent ni casse)."""
    ns = [sans_accent(n) for n in needles]
    return [b for b in blocks if all(n in sans_accent(b) for n in ns)]


def ints_in(text: str) -> set[int]:
    """Entiers isolés d'un texte : « 54, » compte, « 0,25 » et « 1.5 » non."""
    return {int(x) for x in re.findall(r"(?<![\d.,])\d+(?!\d|[.,]\d)", text)}


def decimals_in(text: str) -> list[float]:
    return [float(x.replace(",", ".")) for x in re.findall(r"(?<![\d.,])-?\d+[.,]\d+(?![\d])", text)]


def numbers_in(text: str) -> list[float]:
    return [float(x.replace(",", ".")) for x in re.findall(r"(?<![\w.,])-?\d+(?:[.,]\d+)?", text)]


def token(code: str) -> re.Pattern:
    """Code d'essence comme mot isolé (« 09 » mais pas « 2009 » ni « 0,9 »)."""
    return re.compile(r"(?<![\w.,])" + re.escape(code) + r"(?!\w)(?![.,]\d)")


def species_blocks(blocks: list[str], code: str) -> list[str]:
    t = token(code)
    return [b for b in blocks if t.search(b)]


def ints_in_blocks(blocks: list[str]) -> set[int]:
    out: set[int] = set()
    for b in blocks:
        out |= ints_in(b)
    return out


def matching_definitions(blocks: list[str], needles: tuple[str, ...], cands: dict[str, int]) -> set[str]:
    """Définitions (clés de cands) dont la valeur figure comme entier dans un bloc qui contient tous
    les termes `needles`."""
    ints = ints_in_blocks(blocks_with(blocks, *needles))
    return {k for k, v in cands.items() if v in ints}


# ------------------------------------------------------------------ Parquet
def read_parquet(path: Path) -> list[dict]:
    assert Path(path).exists(), f"sortie absente : {path}"
    return pds.dataset(str(path)).to_table().to_pylist()


def read_params(zone_dir: Path) -> dict[str, list[dict]]:
    return {p: read_parquet(zone_dir / "params" / f"{p}.parquet") for p in PARAMS}


def param_vector(rows: list[dict]) -> dict[tuple, float]:
    return {(r.get("species"), r.get("species_group"), r["model"], r["term"]): r["value"] for r in rows}


def species_group_of(code: str) -> str | None:
    with open(SPECIES_CSV, encoding="utf-8", newline="") as f:
        return next((r["groupe"] for r in csv.DictReader(f) if r["espar"] == code), None)


def reference_points(rows: list[dict]) -> dict[str, float]:
    """Abscisse de référence par covariable : médiane des nœuds de la table (contrat dynamics_params)."""
    import statistics
    xs: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        if r.get("variable") and r.get("x") is not None:
            xs[r["variable"]].append(r["x"])
    return {v: statistics.median(x) for v, x in xs.items()}


def linear_predictor(rows: list[dict], code: str, ref: dict[str, float]) -> float:
    """eta d'une essence au point `ref`, que la ligne qui la porte soit propre à l'essence ou celle de son
    groupe (feuillu, resineux, toutes_essences) : intercept + somme des termes lisses lus par
    interpolation linéaire entre nœuds (bornée aux nœuds extrêmes)."""
    import numpy as np
    propres = [r for r in rows if r.get("species") == code]
    if not propres:
        for g in (species_group_of(code), "toutes_essences"):
            propres = [r for r in rows if r.get("species_group") == g and not r.get("species")]
            if propres:
                break
    assert propres, f"aucune ligne (propre ou de groupe) ne porte l'essence {code}"
    eta = sum(r["value"] for r in propres if r["term"] == "intercept")
    noeuds: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for r in propres:
        if r.get("variable") and r.get("x") is not None:
            noeuds[r["variable"]].append((r["x"], r["value"]))
    for v, pts in noeuds.items():
        pts.sort()
        eta += float(np.interp(ref.get(v, pts[len(pts) // 2][0]), [x for x, _ in pts], [y for _, y in pts]))
    return eta
