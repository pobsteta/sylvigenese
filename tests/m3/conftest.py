"""Pytest M3a (mission 039) : lance `make prepare biomes trees dynamics simulate` sur une copie du jeu fictif
(data/m3_chaine, supprimée ensuite), une fois par session, sans réseau ; puis des copies déjà préparées
rejouent seulement `simulate` avec UNE chose changée (fils, graine, entrée cassée, arbres fabriqués).

Aucune fixture ne saute un test (la CI refuse tout test sauté) : si make échoue, les tests d'exécution
échouent, et ceux qui lisent les sorties échouent sur « sortie absente ».

Ce que ces tests attendent de la fiche 038 (à confirmer par le dev) :
  - la cible `make simulate ZONE=<zone> CONFIG=<config>` lance le moteur ; la commande est lue par
    `make -n simulate` et les options de test y sont ajoutées à la fin ;
  - options de test : `--memoire-disponible <valeur>` (toute valeur trop petite, ici 1, doit donner le code 4)
    et `--inject-nan` (sans argument ; code 3) ;
  - le nombre de fils vient de `simulate.threads` de config.yml ; la graine, t0, years, level du même bloc ;
  - sorties : sim/trees/year=AAAA/, sim/cells/year=AAAA/, sim/run.json, sim/flags.parquet.
"""
import shutil
import sys
from pathlib import Path

import numpy as np
import pytest
import rasterio

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import helpers_m3 as H  # noqa: E402

CHAINE = "m3_chaine"
ESSENCES = ["09", "61", "62", "03", "64"]
JOUR_T0 = None  # jours depuis 1970-01-01 du 1er janvier de t0, calculé à l'usage


def jours_du_31_decembre(annee: int) -> int:
    """Jours depuis 1970-01-01 du 31 décembre de `annee` : l'état initial est la fin de l'année t0 (journal du
    25/11/2026), donc une date de vol au 31 décembre de t0 n'a rien à avancer."""
    import datetime
    return (datetime.date(annee, 12, 31) - datetime.date(1970, 1, 1)).days


# ------------------------------------------------------------------ chaîne nominale
@pytest.fixture(scope="session", autouse=True)
def nettoyage_final():
    """Toute copie data/m3_* est supprimée à la fin de la session, même après un échec."""
    yield
    base = H.ROOT / "data"
    for d in list(base.glob("m3_*")) if base.is_dir() else []:
        shutil.rmtree(d, ignore_errors=True)
    try:
        if base.is_dir() and not any(base.iterdir()):
            base.rmdir()
    except OSError:
        pass


@pytest.fixture(scope="session")
def chaine(nettoyage_final):
    """make prepare biomes trees dynamics simulate sur data/m3_chaine : 100 ans, 1 fil, graine 42."""
    H.remove_zone(CHAINE)
    zdir, cfg = H.make_input_zone(CHAINE, sim=H.SIM_NOMINAL)
    res = {"dir": zdir, "config": cfg, "name": CHAINE}
    res["make"] = H.run_make(*H.CHAIN_TARGETS, zone=CHAINE, config=cfg)
    yield res


@pytest.fixture(scope="session")
def grid(chaine):
    return H.Grid(chaine["dir"])


@pytest.fixture(scope="session")
def params(chaine):
    return H.Params(chaine["dir"])


@pytest.fixture(scope="session")
def arbres(chaine):
    """Toutes les lignes de sim/trees (pandas), colonne part_year = la partition."""
    return H.read_all_trees(chaine["dir"])


@pytest.fixture(scope="session")
def init(chaine):
    """trees_init de la zone de la chaîne, trié par tree_id (numéro stable d'arbre, plan M3a)."""
    return H.read_trees_init(chaine["dir"]).sort_values("tree_id", kind="stable").reset_index(drop=True)


# ------------------------------------------------------------------ rejeux de simulate seul
def _rejouer(nom, sim, mutate=None, extra=()):
    H.remove_zone(nom)
    zdir, cfg = H.clone_zone(CHAINE, nom, sim, mutate)
    proc = H.run_simulate(nom, cfg, *extra)
    return {"dir": zdir, "config": cfg, "name": nom, "proc": proc}


@pytest.fixture(scope="session")
def run_t1_bis(chaine):
    """Même config que la chaîne (1 fil), rejouée : mêmes graine, mêmes octets."""
    res = _rejouer("m3_t1bis", dict(H.SIM_NOMINAL))
    yield res
    H.remove_zone(res["name"])


@pytest.fixture(scope="session", params=[2, 7])
def run_fils(request, chaine):
    """100 ans avec 2 puis 7 fils (7 : nombre premier, découpages inégaux) ; identité attendue avec 1 fil."""
    res = _rejouer(f"m3_t{request.param}", {**H.SIM_NOMINAL, "threads": request.param})
    res["threads"] = request.param
    yield res
    H.remove_zone(res["name"])


@pytest.fixture(scope="session")
def run_graine(chaine):
    """Autre graine (celle de la config + 1), 3 ans : autres morts, mêmes accroissements (sans bruit, Q4)."""
    res = _rejouer("m3_graine43", {**H.SIM_NOMINAL, "seed": H.SIM_NOMINAL["seed"] + 1, "years": 3})
    yield res
    H.remove_zone(res["name"])


@pytest.fixture(scope="session")
def run_graine42_court(chaine):
    """Graine de la config sur 3 ans, pour comparer à la graine 43 sur le même horizon."""
    res = _rejouer("m3_graine42c", {**H.SIM_NOMINAL, "years": 3})
    yield res
    H.remove_zone(res["name"])


# ------------------------------------------------------------------ zone d'arbres fabriqués
def _construire_arbres(grid, params):
    """Arbres isolés (un par cellule d'un réseau tous les 4 mailles), deux grappes pour le disque de 15 m,
    quatre arbres de coin pour le piège de la Somalie. Aucun arbre d'un groupe n'est à moins de 15 m d'un
    autre groupe. Renvoie (lignes pour trees_init, méta)."""
    h0, A = grid.raster("h0"), grid.raster("site_potential")
    rows, meta = [], {"isoles": [], "plafond": [], "grappes": [], "coins": [], "hors_domaine": None}
    n = 0

    def ajout(prefix, cid, x, y, sp, d, h):
        nonlocal n
        n += 1
        tid = f"{prefix}{n:04d}"
        rows.append({"tree_id": tid, "x": float(x), "y": float(y), "species": sp, "d130": float(d), "h": float(h)})
        return tid

    k = 0
    for cid in range(grid.ncols * grid.nrows):
        row, col = divmod(cid, grid.ncols)
        if row % 4 or col % 4 or (row, col) == (0, 0) or h0[row, col] <= 8:
            continue
        cx, cy = grid.cell_center(cid)
        if h0[row, col] < A[row, col] - 3:
            sp = ESSENCES[k % 5]
            if meta["hors_domaine"] is None and sp == "61" and k >= 5:
                d, meta["hors_domaine"] = 400.0, cid          # bien au-delà du dernier nœud de d130
            else:
                d = 20.0 + (7 * k) % 90
            tid = ajout("I", cid, cx, cy, sp, d, h0[row, col] - 1.0)
            meta["isoles"].append({"tree_id": tid, "cell_id": cid, "species": sp, "h0": float(h0[row, col]),
                                   "A": float(A[row, col])})
            k += 1
        elif h0[row, col] >= A[row, col] + 0.5:
            sp = ESSENCES[1 + len(meta["plafond"]) % 4]      # hors hêtre : Korf au plafond, le plan ne le dit pas
            tid = ajout("P", cid, cx, cy, sp, 60.0, h0[row, col])
            meta["plafond"].append({"tree_id": tid, "cell_id": cid, "species": sp, "h0": float(h0[row, col]),
                                    "A": float(A[row, col])})
    # grappes : arbre focal au centre d'une cellule ; un voisin à 14,9 m (compte), un autre à 15,1 m (ne compte pas)
    libres = [c for c in range(grid.ncols * grid.nrows)
              if divmod(c, grid.ncols)[0] % 4 == 2 and divmod(c, grid.ncols)[1] % 4 == 2
              and 8 < h0[divmod(c, grid.ncols)] < A[divmod(c, grid.ncols)] - 3]
    assert len(libres) >= 4, "jeu fictif sans cellules libres pour les grappes"
    for nom, (dx, dy), c in (("dedans", (14.9, 0.0), libres[0]), ("dehors", (0.0, 15.1), libres[1]),
                             ("bord_dedans", (-14.9, 0.0), libres[2]), ("bord_dehors", (0.0, -15.1), libres[3])):
        cx, cy = grid.cell_center(c)
        h = float(h0[divmod(c, grid.ncols)])
        f = ajout("G", c, cx, cy, "61", 50.0, h - 1.0)
        v = ajout("V", c, cx + dx, cy + dy, "03", 70.0, h - 1.0)
        meta["grappes"].append({"nom": nom, "focal": f, "voisin": v, "cell_id": c})
    # coins : les quatre cellules d'angle, au centre (la fiche 036 : (700 012,5 ; 6 500 987,5) tombe dans cell_id 0)
    for cid in (0, grid.ncols - 1, grid.ncols * (grid.nrows - 1), grid.ncols * grid.nrows - 1):
        cx, cy = grid.cell_center(cid)
        tid = ajout("C", cid, cx, cy, "61", 45.0, float(h0[divmod(cid, grid.ncols)]) - 1.0)
        meta["coins"].append({"tree_id": tid, "cell_id": cid, "x": cx, "y": cy})
    return rows, meta


@pytest.fixture(scope="session")
def zone_unitaire(chaine, grid, params):
    """Copie préparée où trees_init est REMPLACÉ par les arbres fabriqués, et où la date de vol de chm_date est
    le 31 décembre de t0, fin de l'année t0 (la hauteur n'a alors rien à avancer de la date de vol à t0 : H_dom(t0) = h0)."""
    rows, meta = _construire_arbres(grid, params)
    t0 = H.SIM_NOMINAL["t0"]

    def mutate(zdir):
        H.write_trees_init(zdir, [dict(r) for r in rows])
        H.add_ser_effect(zdir)
        with rasterio.open(zdir / "chm_date.tif", "r+") as r:
            a = r.read(1)
            a[a != r.nodata] = jours_du_31_decembre(t0)
            r.write(a, 1)

    res = _rejouer("m3_unitaire", {**H.SIM_NOMINAL, "years": 3}, mutate)
    res["rows"] = rows
    res["meta"] = meta
    res["grid"] = H.Grid(res["dir"])
    yield res
    H.remove_zone(res["name"])


# ------------------------------------------------------------------ refus : codes 2, 3, 4
def _retirer_fichier(nom):
    def f(zdir):
        (zdir / nom).unlink(missing_ok=True)
    return f


def _arbre_hors_grille(zdir):
    rows = H.read_trees_init(zdir).to_dict("records")
    rows[0].update(x=702_000.0, y=6_500_500.0)       # 1 km à l'est du massif
    H.write_trees_init(zdir, rows)


def _doublon(zdir):
    rows = H.read_trees_init(zdir).to_dict("records")
    rows.append(dict(rows[0]))
    H.write_trees_init(zdir, rows)


def _colonne_d130_absente(zdir):
    import pyarrow.parquet as pq
    p = zdir / "trees_init" / "trees.parquet"
    t = pq.read_table(p)
    pq.write_table(t.drop_columns(["d130"]), p)


def _sans_essence(code):
    """Retire l'essence `code` des paramètres de croissance, et toute ligne de groupe ou de toutes_essences de ce
    modèle qui la rattraperait : pour `code`, la recherche essence, groupe, toutes_essences n'a plus rien à trouver
    en croissance. Les autres essences gardent leurs paramètres et leurs groupes."""
    def f(zdir):
        def fn(nom, df):
            if nom != "growth":
                return df
            return df[df["species"].notna() & (df["species"] != code)]
        H.rewrite_params(zdir, fn)
    return f


def _essence_hors_referentiel(zdir):
    """Une essence « 99 », absente de contracts/species.csv : ni essence propre ni groupe ; en croissance, plus de
    ligne de groupe ni de toutes_essences pour la rattraper."""
    rows = H.read_trees_init(zdir).to_dict("records")
    rows[0].update(species="99")
    H.write_trees_init(zdir, rows)
    H.rewrite_params(zdir, lambda nom, df: df[df["species"].notna()] if nom == "growth" else df)


REFUS = {
    # nom : (sim, mutate, mots attendus dans le message)
    "sans_t0": ({k: v for k, v in H.SIM_NOMINAL.items() if k != "t0"}, None, ("t0",)),
    "sans_bloc_simulate": (None, None, ("simulate", "t0")),
    "years_zero": ({**H.SIM_NOMINAL, "years": 0}, None, ("years",)),
    "graine_negative": ({**H.SIM_NOMINAL, "seed": -1}, None, ("seed", "graine")),
    "fils_zero": ({**H.SIM_NOMINAL, "threads": 0}, None, ("threads", "fils")),
    "niveau_inconnu": ({**H.SIM_NOMINAL, "level": "france"}, None, ("level", "niveau")),
    "h0_absent": (dict(H.SIM_NOMINAL), _retirer_fichier("h0.tif"), ("h0.tif", "h0")),
    "gradients_absents": (dict(H.SIM_NOMINAL), _retirer_fichier("station_gradients.tif"), ("station_gradients",)),
    "site_potential_absent": (dict(H.SIM_NOMINAL), _retirer_fichier("site_potential.tif"), ("site_potential",)),
    "ser_absent": (dict(H.SIM_NOMINAL), _retirer_fichier("ser.tif"), ("ser.tif", "ser")),
    "grille_absente": (dict(H.SIM_NOMINAL), _retirer_fichier("grid.tif"), ("grid.tif", "grid")),
    "trees_init_absent": (dict(H.SIM_NOMINAL), lambda z: shutil.rmtree(z / "trees_init", ignore_errors=True), ("trees_init",)),
    "arbre_hors_grille": (dict(H.SIM_NOMINAL), _arbre_hors_grille, ("hors", "grille")),
    "doublon_tree_id": (dict(H.SIM_NOMINAL), _doublon, ("tree_id", "doublon", "double")),
    "colonne_d130_absente": (dict(H.SIM_NOMINAL), _colonne_d130_absente, ("d130",)),
    "essence_sans_parametres": (dict(H.SIM_NOMINAL), _sans_essence("64"), ("64",)),
    "essence_hors_referentiel": (dict(H.SIM_NOMINAL), _essence_hors_referentiel, ("99",)),
}


@pytest.fixture(scope="session", params=list(REFUS))
def refus(request, chaine):
    nom_cas = request.param
    sim, mutate, mots = REFUS[nom_cas]
    nom = "m3_refus_" + nom_cas
    res = _rejouer(nom, sim, mutate)
    res.update(cas=nom_cas, mots=mots)
    yield res
    H.remove_zone(nom)


@pytest.fixture(scope="session")
def run_nan(chaine):
    res = _rejouer("m3_nan", {**H.SIM_NOMINAL, "years": 3}, extra=("--inject-nan",))
    yield res
    H.remove_zone(res["name"])


@pytest.fixture(scope="session")
def run_memoire(chaine):
    res = _rejouer("m3_memoire", {**H.SIM_NOMINAL, "years": 3}, extra=("--memoire-disponible", "1"))
    yield res
    H.remove_zone(res["name"])


@pytest.fixture(scope="session")
def run_date_incoherente(chaine):
    """t0 = 2015 : avant les dates de vol du jeu fictif (2021-08-03 et 2022-06-21)."""
    res = _rejouer("m3_date", {**H.SIM_NOMINAL, "t0": 2015, "years": 3})
    yield res
    H.remove_zone(res["name"])


@pytest.fixture(scope="session")
def run_depot(chaine):
    """La config du dépôt (t0 de config.yml, 034) sur le jeu fictif, 3 ans : `make simulate` doit y tourner."""
    res = _rejouer("m3_depot", {**H.DEPOT, "threads": 1, "years": 3})
    yield res
    H.remove_zone(res["name"])
