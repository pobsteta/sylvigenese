#!/usr/bin/env python3
"""Générateur de SER fictive (mission 061, plan docs/plans/m5a.md, mission C et choix T9).

Pour toute taille N, il écrit sous un dossier de zone des sorties de `prepare` SYNTHÉTIQUES, conformes aux
contrats (contracts/catalog.yml), sur une grille de N × N cellules de 25 m en EPSG:2154 :

    zone.yml                    fictive: true (contrat zone_marker) ; la raison nomme les deux SER
    grid.tif                    grille (UInt16, 1 partout)
    forest_mask.tif             toutes les cellules forestières (UInt16, 1)
    h0.tif, chm_date.tif        hauteur à t0 (Float32) et date de vol (UInt16, jours depuis 1970-01-01) au
                                1er janvier de t0 + 1, « fin de l'année t0 » : la hauteur n'a rien à avancer
    site_potential.tif          plafond de hauteur (Float32), toujours au-dessus de h0
    station_gradients.tif       trois bandes Float32 : trophic, hydric, bioclim
    ser.tif, ser.csv            DEUX SER : la moitié ouest vaut 1 (H10), la moitié est vaut 2 (H21) ; codes pris
                                dans docs/referentiels/surfaces-ser.csv
    cohorts_init.parquet        adultes par cellule, essence et classe de diamètre (contrat prepare.cohorts_init)
    params/growth, mortality, recruitment, height_curve .parquet   (contrat dynamics_params)
    params/regeneration.parquet (contrat dynamics.regeneration), les 10 termes pour chaque essence
    params/allometry.parquet    copie de tests/fixtures/zone_fictive/params/allometry.parquet

AUCUNE VALEUR ÉCOLOGIQUE. Toutes les valeurs écrites ici sont des réglages d'essai, choisis pour que les tests
d'acceptation aient un oracle exact (modèles qui ne dépendent que de la station, par exemple). Elles portent
toutes `provisoire = vrai` et la source « synthétique (tests/m5/ser_fictive.py) ; aucune valeur écologique ».
Elles ne disent rien d'une forêt réelle et ne doivent servir à rien d'autre qu'aux tests.

Déterminisme : même N, même graine et mêmes options donnent les mêmes octets (tirages numpy PCG64 à graine
fixée, GeoTIFF sans date, Parquet sans horodatage, YAML trié). Ce que le générateur écrit est hors dépôt
(data/<zone>/, ignoré par git).

Ligne de commande :
    python3 tests/m5/ser_fictive.py --n 1000 --graine 1 --sortie data/ser_fictive_1000
"""
from __future__ import annotations

import argparse
import csv
import datetime
import shutil
import sys
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import rasterio
from rasterio.transform import from_origin

ROOT = Path(__file__).resolve().parents[2]
ALLOMETRY_SRC = ROOT / "tests" / "fixtures" / "zone_fictive" / "params" / "allometry.parquet"

RES = 25.0
X0_DEFAUT, Y0_DEFAUT = 700_000.0, 6_501_000.0     # coin nord-ouest : (700 012,5 ; 6 500 987,5) est le centre de cell_id 0
T0_DEFAUT = 2022
ESSENCES_DEFAUT = ("03", "61")                    # contracts/species.csv : 03 feuillu, 61 résineux
ESSENCES_AJOUTEES = ("09", "62", "02", "64", "11", "51", "10", "52", "04", "53S", "05", "54", "06", "55")
# Essences ajoutées par --essences S (S > 2), dans l'ordre, feuillus et résineux en alternance (codes de
# contracts/species.csv). Ce sont des COPIES SYNTHÉTIQUES des deux essences de base : mêmes valeurs d'essai que 03
# (feuillu) ou 61 (résineux), provisoires, sans aucune valeur écologique ; le code ne sert qu'à exister au référentiel.
SER_CODES = ("H10", "H21")                        # docs/referentiels/surfaces-ser.csv
CLASSES_DEFAUT = 6                                # K : doit égaler simulate.ser.diameter_classes de la config
CLASSES_REMPLIES = 4                              # classes 0 à 3 garnies à t0
SOURCE = "synthétique (tests/m5/ser_fictive.py) ; aucune valeur écologique"
SOURCE_COPIE = "synthétique (copie d'une essence de base, tests/m5/ser_fictive.py) ; aucune valeur écologique"
SEUIL_OCTETS_CHAINE = 2**31 - 1                   # capacité d'une colonne pa.string() (offsets int32)
LIGNES_PAR_MORCEAU = 2**20                        # taille d'un groupe de lignes Parquet par défaut de pyarrow
NODATA_F = -9999.0
NODATA_U = 65535

# Valeurs synthétiques des modèles de dynamique (format long du contrat dynamics_params). Chaque modèle ne dépend
# que de la station (trophic) et de la SER : l'oracle des tests est exact sans connaître la surface terrière que le
# moteur calcule au niveau SER. Ce sont des réglages d'essai, pas des valeurs écologiques.
DYNAMIQUE_DEFAUT = {
    # modèle : (intercept, (valeur au nœud trophic = 0, valeur au nœud trophic = 10), effet de la SER H21)
    "growth_gam": (-1.6, (-0.1, 0.1), 0.05),
    "mortality_gam": (-4.6, (0.1, -0.1), 0.1),
    "recruitment_gam": (1.6, (-0.5, 0.5), -0.1),
}

ECART_RESINEUX = 0.3                              # intercept du recrutement des résineux = celui des feuillus + 0,3

# Termes de params/regeneration (liste fermée du contrat), unités du contrat ; valeurs synthétiques d'essai.
REGENERATION_DEFAUT = {
    "kernel_scale_m": (30.0, "m"),
    "kernel_shape": (1.0, "1"),
    "maturity_height_m": (10.0, "m"),
    "fecundity_seeds_per_m2_ba_yr": (1000.0, "graines/m2/an"),
    "establishment_share": (0.5, "1"),
    "seedling_height_growth_m_yr": (0.4, "m/an"),
    "shade_tolerance": (3.0, "1"),
    "light_extinction_coef": (0.5, "1"),
    "seedling_survival_full_light_yr": (0.9, "1"),
    "passage_height_m": (1.3, "m"),
}
TERMES_REGENERATION = tuple(REGENERATION_DEFAUT)

DYN_SCHEMA = pa.schema([
    ("species", pa.string()), ("species_group", pa.string()), ("model", pa.string()), ("term", pa.string()),
    ("variable", pa.string()), ("x", pa.float64()), ("value", pa.float64()), ("provisoire", pa.bool_()),
    ("source", pa.string()),
])
REGEN_SCHEMA = pa.schema([
    ("species", pa.string()), ("species_group", pa.string()), ("term", pa.string()), ("value", pa.float64()),
    ("unit", pa.string()), ("provisoire", pa.bool_()), ("source", pa.string()),
])


def schema_cohortes(nlignes: int) -> pa.Schema:
    """Schéma de cohorts_init pour `nlignes` lignes : la colonne `source` passe en large_string quand ses octets
    dépasseraient la capacité d'un pa.string() (2^31 − 1, soit N ≈ 2 016 à 2 essences et 4 classes) ; le contrat
    accepte les deux types (contracts/validator/tables.py : is_text). En dessous, pa.string() : mêmes octets qu'avant."""
    return pa.schema([("cell_id", pa.int64()), ("species", pa.string()), ("d_class", pa.int64()),
                      ("stems_ha", pa.float64()), ("source", type_colonne_source(nlignes))])


def type_colonne_source(nlignes: int) -> pa.DataType:
    return pa.large_string() if nlignes * len(SOURCE.encode("utf-8")) >= SEUIL_OCTETS_CHAINE else pa.string()


def colonne_source(nlignes: int, type_: pa.DataType | None = None) -> pa.Array:
    """La colonne `source` (la même chaîne partout) de `nlignes` lignes, du type demandé (par défaut celui que
    type_colonne_source donne pour ce nombre de lignes)."""
    type_ = type_ or type_colonne_source(nlignes)
    # pa.repeat, pas un dictionnaire casté : le cast d'un dictionnaire vers large_string déborde aussi (« Take operation
    # overflowed binary array capacity ») quand les octets dépassent 2^31.
    return pa.repeat(pa.scalar(SOURCE, type_), nlignes)


COHORTS_SCHEMA = schema_cohortes(0)


# ------------------------------------------------------------------ tables de paramètres
def dynamique_rows(overrides: dict | None = None, ser_effect_code: str = SER_CODES[1]) -> dict[str, list[dict]]:
    """Lignes des quatre fichiers de dynamique, en `toutes_essences`, sauf le recrutement, écrit par groupe (feuillu,
    puis résineux avec un intercept plus grand de ECART_RESINEUX) : deux essences de groupes différents ont ainsi des
    flux différents, et un flux attribué à la mauvaise essence se voit. `overrides` : {modèle: {"intercept": v,
    "trophic": (y0, y1), "ser": v}} remplace des valeurs (les tests s'en servent pour fabriquer un cas)."""
    overrides = overrides or {}
    out: dict[str, list[dict]] = {"growth": [], "mortality": [], "recruitment": [], "height_curve": []}
    fichier = {"growth_gam": "growth", "mortality_gam": "mortality", "recruitment_gam": "recruitment"}

    def ligne(model, term, value, variable=None, x=None, groupe="toutes_essences"):
        return {"species": None, "species_group": groupe, "model": model, "term": term,
                "variable": variable, "x": x, "value": float(value), "provisoire": True, "source": SOURCE}

    for model, (inter, (y0, y1), ser) in DYNAMIQUE_DEFAUT.items():
        o = overrides.get(model, {})
        inter = o.get("intercept", inter)
        y0, y1 = o.get("trophic", (y0, y1))
        ser = o.get("ser", ser)
        groupes = ((("feuillu", 0.0), ("resineux", ECART_RESINEUX)) if model == "recruitment_gam"
                   else (("toutes_essences", 0.0),))
        rows = []
        for g, d in groupes:
            rows += [ligne(model, "intercept", inter + d, groupe=g),
                     ligne(model, "s(trophic)[01]", y0, "trophic", 0.0, g),
                     ligne(model, "s(trophic)[02]", y1, "trophic", 10.0, g),
                     ligne(model, f"ser_code={ser_effect_code}", ser, "ser_code", groupe=g)]
            if model != "mortality_gam":
                rows += [ligne(model, "scale", 1.0, groupe=g), ligne(model, "tweedie_p", 1.5, groupe=g)]
            else:
                rows += [ligne(model, "scale", 1.0, groupe=g)]
        out[fichier[model]] = rows
    # Courbes de hauteur : Chapman-Richards et hauteur relative constante (h = H_dom), toutes essences.
    hc = [ligne("chapman_richards", f"A_class{i}", a) for i, a in enumerate((40.0, 36.0, 32.0, 28.0, 24.0), 1)]
    hc += [ligne("chapman_richards", "k", 0.02), ligne("chapman_richards", "p", 1.2)]
    hc += [ligne("relative_height_gam", "intercept", 1.0),
           ligne("relative_height_gam", "s(rel_d)[01]", 0.0, "rel_d", 0.0),
           ligne("relative_height_gam", "s(rel_d)[02]", 0.0, "rel_d", 3.0),
           ligne("relative_height_gam", "scale", 1.0)]
    out["height_curve"] = hc
    return out


def regeneration_rows(species=ESSENCES_DEFAUT, overrides: dict | None = None, par_essence: bool = True,
                      omis: tuple = ()) -> list[dict]:
    """Lignes de params/regeneration. `overrides` : {terme: valeur} (toutes essences) ou {(essence, terme): valeur}.
    `par_essence` faux : une seule série `toutes_essences` (repli du contrat). `omis` : couples (essence, terme) à ne
    pas écrire (cas « paramètre de semis manquant »)."""
    overrides = overrides or {}
    rows = []
    porteurs = [(s, None) for s in species] if par_essence else [(None, "toutes_essences")]
    for sp, grp in porteurs:
        for term, (val, unit) in REGENERATION_DEFAUT.items():
            if (sp, term) in omis:
                continue
            v = overrides.get((sp, term), overrides.get(term, val))
            rows.append({"species": sp, "species_group": grp, "term": term, "value": float(v), "unit": unit,
                         "provisoire": True, "source": SOURCE})
    return rows


def groupe_de(code: str) -> str:
    """Groupe (feuillu ou resineux) d'un code de contracts/species.csv."""
    with open(ROOT / "contracts" / "species.csv", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["espar"] == code:
                return r["groupe"]
    raise ValueError(f"essence {code} absente de contracts/species.csv")


def write_allometry(path: Path, species) -> None:
    """params/allometry : la copie du jeu fictif versionné, telle quelle (octets inchangés) si elle couvre toutes les
    essences ; sinon, ses lignes plus, pour chaque essence absente, une COPIE SYNTHÉTIQUE des lignes de 03 (feuillu)
    ou de 61 (résineux), provisoire, qui ne porte aucune valeur écologique."""
    src = pq.read_table(ALLOMETRY_SRC)
    connues = set(src.column("species").to_pylist())
    manquantes = [s for s in species if s not in connues]
    if not manquantes:
        shutil.copy(ALLOMETRY_SRC, path)
        return
    rows = src.to_pylist()
    for sp in manquantes:
        base = "03" if groupe_de(sp) == "feuillu" else "61"
        for r in src.to_pylist():
            if r["species"] == base:
                rows.append({**r, "species": sp, "provisoire": True, "source": SOURCE_COPIE})
    write_table(rows, src.schema, path)


def write_table(rows: list[dict], schema: pa.Schema, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    t = pa.Table.from_pylist(rows, schema=schema) if rows else schema.empty_table()
    pq.write_table(t, path, compression="snappy")


def write_regeneration(zdir: Path, rows: list[dict]) -> None:
    write_table(rows, REGEN_SCHEMA, zdir / "params" / "regeneration.parquet")


def write_dynamique(zdir: Path, overrides: dict | None = None) -> None:
    for nom, rows in dynamique_rows(overrides).items():
        write_table(rows, DYN_SCHEMA, zdir / "params" / f"{nom}.parquet")


# ------------------------------------------------------------------ rasters
def _profil(n: int, x0: float, y0: float, dtype: str, count: int = 1) -> dict:
    return {"driver": "GTiff", "dtype": dtype, "width": n, "height": n, "count": count, "crs": "EPSG:2154",
            "transform": from_origin(x0, y0, RES, RES), "nodata": NODATA_U if dtype == "uint16" else NODATA_F,
            "tiled": True, "blockxsize": 256, "blockysize": 256, "compress": "deflate", "interleave": "band"}


def write_raster(path: Path, bands: list[np.ndarray], x0: float, y0: float, dtype: str, names: list[str]) -> None:
    n = bands[0].shape[0]
    with rasterio.open(path, "w", **_profil(n, x0, y0, dtype, len(bands))) as r:
        for i, (b, name) in enumerate(zip(bands, names), 1):
            r.write(b.astype(dtype), i)
            r.set_band_description(i, name)
        r.update_tags(AREA_OR_POINT="Area")


def jours_fin_annee(t0: int) -> int:
    return (datetime.date(t0 + 1, 1, 1) - datetime.date(1970, 1, 1)).days


# ------------------------------------------------------------------ cohortes initiales
def classes_remplies_pour(k: int) -> int:
    """Classes garnies à t0 pour K classes : 4 sur 6 par défaut, soit ⌈2K/3⌉ (K = 15 : 10), au moins 1."""
    return CLASSES_REMPLIES if k == CLASSES_DEFAUT else max(1, (2 * k + 2) // 3)


def essences_pour(s_essences: int) -> tuple:
    """Les S essences de la SER fictive : 03 et 61, puis des copies synthétiques (ESSENCES_AJOUTEES)."""
    if s_essences < 1 or s_essences > len(ESSENCES_DEFAUT) + len(ESSENCES_AJOUTEES):
        raise ValueError(f"S doit être entre 1 et {len(ESSENCES_DEFAUT) + len(ESSENCES_AJOUTEES)}")
    return (ESSENCES_DEFAUT + ESSENCES_AJOUTEES)[:s_essences]


def cohortes_morceaux(n: int, rng: np.random.Generator, species, classes_remplies: int, type_source=None):
    """Les cohortes tirées, par morceaux d'environ 2^20 lignes (cellules entières) : mémoire bornée à toute taille.
    Les tirages se suivent dans le même ordre qu'en un seul bloc, donc mêmes valeurs. Chaque cellule porte toutes
    les essences, classes 0 à classes_remplies − 1, densités tirées (tiges/ha)."""
    ncell, ns, nk = n * n, len(species), classes_remplies
    par_cellule = ns * nk
    cellules = max(1, LIGNES_PAR_MORCEAU // par_cellule)
    type_source = type_source or type_colonne_source(ncell * par_cellule)
    schema = pa.schema([("cell_id", pa.int64()), ("species", pa.string()), ("d_class", pa.int64()),
                        ("stems_ha", pa.float64()), ("source", type_source)])
    sp_dict = pa.array(list(species))
    for debut in range(0, ncell, cellules):
        c = min(cellules, ncell - debut)
        stems = np.round(rng.uniform(5.0, 60.0, size=(c, ns, nk)), 3)   # trois décimales : valeurs lisibles
        cell = np.repeat(np.arange(debut, debut + c, dtype=np.int64), par_cellule)
        sp_idx = np.tile(np.repeat(np.arange(ns, dtype=np.int32), nk), c)
        dcl = np.tile(np.arange(nk, dtype=np.int64), c * ns)
        sp = pa.DictionaryArray.from_arrays(pa.array(sp_idx), sp_dict).cast(pa.string())
        yield pa.table([pa.array(cell), sp, pa.array(dcl), pa.array(stems.reshape(-1)),
                        colonne_source(len(cell), type_source)], schema=schema)


def cohortes_generiques(n: int, rng: np.random.Generator, species, classes_remplies: int) -> pa.Table:
    """Les mêmes cohortes en une seule table (petites tailles) ; au-delà, passer par cohortes_morceaux."""
    return pa.concat_tables(list(cohortes_morceaux(n, rng, species, classes_remplies)))


def cohortes_explicites(n: int, lignes: list[tuple], species) -> pa.Table:
    """`lignes` : (cell_id, essence, d_class, tiges/ha). Toute autre cellule reste forestière, sans adulte : une ligne
    à 0 tige (contrat : « une classe sans tige peut être omise ou écrite à 0 »)."""
    pleines = {(c, s, k): v for c, s, k, v in lignes}
    avec = {c for c, _s, _k, _v in lignes}
    rows = [(c, s, k, v) for (c, s, k), v in pleines.items()]
    rows += [(c, species[0], 0, 0.0) for c in range(n * n) if c not in avec]
    rows.sort(key=lambda r: (r[0], r[1], r[2]))
    return pa.table({"cell_id": pa.array([r[0] for r in rows], pa.int64()),
                     "species": pa.array([r[1] for r in rows], pa.string()),
                     "d_class": pa.array([r[2] for r in rows], pa.int64()),
                     "stems_ha": pa.array([float(r[3]) for r in rows], pa.float64()),
                     "source": pa.array([SOURCE] * len(rows), pa.string())}, schema=COHORTS_SCHEMA)


# ------------------------------------------------------------------ zone complète
def generer(dest: Path, n: int, graine: int = 1, *, species=ESSENCES_DEFAUT, t0: int = T0_DEFAUT,
            x0: float = X0_DEFAUT, y0: float = Y0_DEFAUT, classes: int = CLASSES_DEFAUT,
            classes_remplies: int | None = None,
            cohortes: list[tuple] | None = None, dynamique: dict | None = None, regeneration: dict | None = None,
            regeneration_par_essence: bool = True, regeneration_omis: tuple = ()) -> Path:
    """Écrit la SER fictive de N × N cellules sous `dest` (vidé d'abord). Renvoie `dest`.

    `cohortes` : liste explicite (cell_id, essence, d_class, tiges/ha) à la place des cohortes tirées ;
    `species` : les essences (voir essences_pour pour S essences) ; `classes` : K, nombre de classes de diamètre
    (les classes garnies à t0 en découlent, sauf `classes_remplies` donné) ;
    `dynamique`, `regeneration` : remplacements de valeurs synthétiques (voir dynamique_rows, regeneration_rows)."""
    if n < 1:
        raise ValueError("N doit être au moins 1")
    if classes < 1:
        raise ValueError("K doit être au moins 1")
    species = tuple(species)
    if classes_remplies is None:
        classes_remplies = classes_remplies_pour(classes)
    dest = Path(dest)
    if dest.exists():
        shutil.rmtree(dest)
    (dest / "params").mkdir(parents=True)
    rng = np.random.Generator(np.random.PCG64(graine))
    ii, jj = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")    # ii : ligne (0 au nord), jj : colonne
    denom = max(n - 1, 1)

    ones = np.ones((n, n), dtype=np.uint16)
    write_raster(dest / "grid.tif", [ones], x0, y0, "uint16", ["lyr.1"])
    write_raster(dest / "forest_mask.tif", [ones], x0, y0, "uint16", ["value"])
    h0 = np.round(15.0 + 10.0 * rng.random((n, n)), 3)
    write_raster(dest / "h0.tif", [h0], x0, y0, "float32", ["chm_m"])
    write_raster(dest / "chm_date.tif", [np.full((n, n), jours_fin_annee(t0), dtype=np.uint16)], x0, y0, "uint16",
                 ["value"])
    write_raster(dest / "site_potential.tif", [np.round(h0 + 8.0 + 4.0 * rng.random((n, n)), 3)], x0, y0, "float32",
                 ["h_pot_m"])
    trophic = 3.0 + 3.0 * jj / denom + 0.2 * rng.random((n, n))
    hydric = -1.0 + 1.0 * ii / denom + 0.1 * rng.random((n, n))
    bioclim = 0.5 * rng.random((n, n)) - 0.25
    write_raster(dest / "station_gradients.tif", [trophic, hydric, bioclim], x0, y0, "float32",
                 ["trophic", "hydric", "bioclim"])
    ser = np.where(jj < (n + 1) // 2, 1, 2).astype(np.uint16) if n > 1 else ones
    write_raster(dest / "ser.tif", [ser], x0, y0, "uint16", ["value"])
    (dest / "ser.csv").write_text('"value","name","alluvium_code"\n' + f'1,"{SER_CODES[0]}",\n2,"{SER_CODES[1]}",\n',
                                  encoding="utf-8")

    if cohortes is not None:
        morceaux, schema = [cohortes_explicites(n, cohortes, species)], COHORTS_SCHEMA
    else:
        schema = schema_cohortes(n * n * len(species) * classes_remplies)
        morceaux = cohortes_morceaux(n, rng, species, classes_remplies, schema.field("source").type)
    with pq.ParquetWriter(dest / "cohorts_init.parquet", schema, compression="snappy") as w:
        for morceau in morceaux:
            w.write_table(morceau)

    write_dynamique(dest, dynamique)
    write_regeneration(dest, regeneration_rows(species, regeneration, regeneration_par_essence, regeneration_omis))
    write_allometry(dest / "params" / "allometry.parquet", species)

    raison = (f"SER fictive synthétique (tests/m5/ser_fictive.py, N = {n}, graine {graine}) : deux SER, "
              f"{SER_CODES[0]} (moitié ouest, valeur 1 de ser.tif) et {SER_CODES[1]} (moitié est, valeur 2) ; "
              "coordonnées et valeurs inventées, aucune source réelle")
    if tuple(species) != ESSENCES_DEFAUT or classes != CLASSES_DEFAUT:
        raison += (f" ; {len(species)} essence(s) ({', '.join(species)}), {classes} classe(s) de diamètre : les "
                   "essences au-delà de 03 et 61 sont des copies synthétiques provisoires, sans valeur écologique")
    (dest / "zone.yml").write_text(f"schema_version: 1\nfictive: true\nreason: \"{raison}\"\n", encoding="utf-8")
    return dest


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Écrit une SER fictive de N × N cellules de 25 m (sorties de prepare "
                                            "synthétiques, conformes aux contrats ; aucune valeur écologique).")
    p.add_argument("--n", type=int, required=True, help="côté de la grille, en cellules")
    p.add_argument("--graine", type=int, default=1, help="graine des tirages (mêmes octets à graine égale)")
    p.add_argument("--sortie", type=Path, required=True, help="dossier de zone à écrire (vidé d'abord)")
    p.add_argument("--t0", type=int, default=T0_DEFAUT, help="année de départ (date de vol = fin de t0)")
    p.add_argument("--essences", type=int, default=len(ESSENCES_DEFAUT),
                   help="nombre S d'essences (défaut 2 : 03 et 61 ; au-delà, copies synthétiques provisoires de "
                        f"codes de contracts/species.csv, jusqu'à {len(ESSENCES_DEFAUT) + len(ESSENCES_AJOUTEES)})")
    p.add_argument("--classes", type=int, default=CLASSES_DEFAUT,
                   help="nombre K de classes de diamètre (défaut 6 : doit égaler simulate.ser.diameter_classes)")
    a = p.parse_args(argv)
    if a.n < 1:
        print("ser_fictive : N doit être au moins 1", file=sys.stderr)
        return 2
    if a.classes < 1:
        print("ser_fictive : K (--classes) doit être au moins 1", file=sys.stderr)
        return 2
    try:
        especes = essences_pour(a.essences)
    except ValueError as e:
        print(f"ser_fictive : S (--essences) invalide : {e}", file=sys.stderr)
        return 2
    generer(a.sortie, a.n, a.graine, species=especes, t0=a.t0, classes=a.classes)
    print(f"SER fictive de {a.n} × {a.n} cellules, {a.essences} essence(s), {a.classes} classe(s), "
          f"écrite sous {a.sortie}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
