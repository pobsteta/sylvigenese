"""Pytest M5a (mission 061) : chaque fixture bâtit une zone sous data/m5_* (SER fictive du générateur, ou massif
fictif rebâti des entrées figées de M3a), lance `simulate` UNE fois par session, sans réseau, puis la supprime.

Aucune fixture ne saute un test (la CI refuse tout test sauté) : si simulate échoue, les tests échouent sur son code
de sortie ou sur « sortie absente ». Les horizons sont courts (1 à 8 ans), sauf la non-régression de M3a (100 ans,
comme tests/m3)."""
import math
import shutil
import sys
from pathlib import Path

import pyarrow.parquet as pq
import pytest

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import helpers_m5 as H  # noqa: E402
import ser_fictive as G  # noqa: E402

# Réglages d'essai des cas fabriqués (aucune valeur écologique : ils fabriquent un oracle exact).
LUMIERE_UNIFORME = {"light_extinction_coef": 0.0, "seedling_survival_full_light_yr": 1.0}
FLUX_NUL = {"recruitment_gam": {"intercept": -40.0, "trophic": (0.0, 0.0), "ser": 0.0}}


@pytest.fixture(scope="session", autouse=True)
def nettoyage_final():
    yield
    base = H.ROOT / "data"
    for d in list(base.glob("m5_*")) if base.is_dir() else []:
        shutil.rmtree(d, ignore_errors=True)
    try:
        if base.is_dir() and not any(base.iterdir()):
            base.rmdir()
    except OSError:
        pass


def _run_ser(nom, n, sim, mutate=None, **gen):
    H.remove_zone(nom)
    zdir, cfg = H.zone_ser(nom, n, sim, mutate, **gen)
    return {"dir": zdir, "config": cfg, "name": nom, "n": n, "sim": sim, "proc": H.run_simulate(nom, cfg)}


# ------------------------------------------------------------------ niveau SER
@pytest.fixture(scope="session")
def ser_nominale():
    """SER fictive de 32 × 32, 5 ans, une année écrite sur 2 : t0, t0 + 2, t0 + 4 et la dernière, t0 + 5."""
    res = _run_ser("m5_ser_nominale", 32, H.sim_ser(5, write_step=2))
    yield res
    H.remove_zone(res["name"])


@pytest.fixture(scope="session")
def ser_calage():
    """Q1, stock ample : semis abondants, lumière uniforme ; 3 ans, toutes les années écrites."""
    res = _run_ser("m5_ser_calage", 20, H.sim_ser(3), regeneration=LUMIERE_UNIFORME)
    yield res
    H.remove_zone(res["name"])


@pytest.fixture(scope="session")
def ser_stock_rare():
    """Q1 et Q2, stock rare : fécondité quasi nulle ; le stock « en régime » de t0 s'épuise en quelques années."""
    regen = {**LUMIERE_UNIFORME, "fecundity_seeds_per_m2_ba_yr": 1e-6}
    res = _run_ser("m5_ser_stock_rare", 20, H.sim_ser(6), regeneration=regen)
    yield res
    H.remove_zone(res["name"])


@pytest.fixture(scope="session")
def ser_transfert():
    """Conservation dans les transferts entre classes : ni mort ni recrue (exp(−40)), forte croissance."""
    dyn = {"mortality_gam": {"intercept": -40.0, "trophic": (0.0, 0.0), "ser": 0.0}, **FLUX_NUL,
           "growth_gam": {"intercept": math.log(2.0), "trophic": (0.0, 0.0), "ser": 0.0}}
    res = _run_ser("m5_ser_transfert", 12, H.sim_ser(4), dynamique=dyn)
    yield res
    H.remove_zone(res["name"])


SOURCES = {
    # nom : (N, ligne, colonne) de la cellule dont le centre est le point connu (700 012,5 ; 6 500 987,5)
    "diagonale": (26, 12, 12),
    "asymetrique": (26, 7, 16),
}


@pytest.fixture(scope="session", params=list(SOURCES))
def ser_source(request):
    """Une seule cellule semencière (essence 03, classe 5, 50 tiges/ha), au point connu ; toutes les autres sont
    forestières et vides ; flux IFN quasi nul ; lumière uniforme ; un an."""
    n, row, col = SOURCES[request.param]
    x0, y0 = H.origine_pour(row, col)
    cid = row * n + col
    res = _run_ser(f"m5_source_{request.param}", n, H.sim_ser(1), x0=x0, y0=y0,
                   cohortes=[(cid, "03", 5, 50.0)], dynamique=FLUX_NUL, regeneration=LUMIERE_UNIFORME)
    res.update(cas=request.param, row=row, col=col, cell=cid)
    yield res
    H.remove_zone(res["name"])


_DIGESTS_40: dict = {}
_DIGESTS_1000: dict = {}


@pytest.fixture(scope="session", params=[1, 2, 7])
def ser_fils(request):
    """SER fictive de 40 × 40, 3 ans, avec 1, 2 puis 7 fils (7 : premier, découpages inégaux). L'empreinte de chaque
    exécution réussie est gardée (la paramétrisation commence par 1 fil : c'est la référence)."""
    t = request.param
    res = _run_ser(f"m5_ser_fils{t}", 40, H.sim_ser(3, threads=t))
    res["threads"] = t
    if res["proc"].returncode == 0:
        _DIGESTS_40[t] = H.sim_digest(res["dir"])
    res["digests"] = _DIGESTS_40
    yield res
    H.remove_zone(res["name"])


@pytest.fixture(scope="session", params=[1, 4])
def ser_1000(request):
    """N = 1 000 (un million de cellules), 3 ans, années écrites t0 et t0 + 3, à 1 puis 4 fils ; mémoire résidente
    lue hors du moteur (wait4). Seule taille de la CI (T10)."""
    t = request.param
    nom = f"m5_ser1000_t{t}"
    H.remove_zone(nom)
    zdir, cfg = H.zone_ser(nom, 1000, H.sim_ser(3, write_step=3, threads=t))
    mes = H.run_mesure(cfg)
    res = {"dir": zdir, "config": cfg, "name": nom, "threads": t, **mes}
    if mes["proc"].returncode == 0:
        _DIGESTS_1000[t] = H.sim_digest(zdir)
    res["digests"] = _DIGESTS_1000
    yield res
    H.remove_zone(nom)


# ------------------------------------------------------------------ niveau massif
def _recrutement_de_station(zdir):
    """Le recrutement du massif ne dépend plus que de la station (oracle exact) ; λ ≈ 2,5 recrues par cellule et par
    an, pour que l'arrondi aléatoire ait deux valeurs possibles non triviales."""
    rows = G.dynamique_rows({"recruitment_gam": {"intercept": math.log(40.0)}})["recruitment"]
    G.write_table(rows, G.DYN_SCHEMA, zdir / "params" / "recruitment.parquet")


@pytest.fixture(scope="session")
def massif_cohorts():
    """Massif fictif (entrées figées de M3a), mode cohorts, 8 ans, noyau tronqué à 1 cellule ; semenciers dès 30 cm
    (tous les arbres initiaux le sont, aucune recrue ne le devient en 8 ans)."""
    nom = "m5_massif_cohorts"
    zdir, cfg = H.zone_massif(nom, H.sim_massif(8, troncature=1), _recrutement_de_station,
                              regeneration={"maturity_d130_cm": 30.0})
    res = {"dir": zdir, "config": cfg, "name": nom, "proc": H.run_simulate(nom, cfg), "troncature": 1}
    yield res
    H.remove_zone(nom)


@pytest.fixture(scope="session")
def massif_ifn_direct():
    """Massif fictif (entrées figées de M3a, sans params/regeneration), mode ifn_direct dit dans la config, avec
    la configuration nominale de M3a (graine 42, 100 ans, 1 fil) : doit redonner tests/m3/reference/nominal.json."""
    nom = "m5_massif_ifn_direct"
    zdir, cfg = H.zone_massif(nom, {**H.H3.SIM_NOMINAL, "recruitment": "ifn_direct"},
                              mutate=lambda z: (z / "params" / "regeneration.parquet").unlink())
    res = {"dir": zdir, "config": cfg, "name": nom, "proc": H.run_simulate(nom, cfg)}
    yield res
    H.remove_zone(nom)


# ------------------------------------------------------------------ refus (code 2), code 3, code 4
def _sans(cle):
    def f(sim):
        return {k: v for k, v in sim.items() if k != cle}
    return f


def _retirer(rel):
    def f(zdir):
        (zdir / rel).unlink()
    return f


def _cohorts_init(fn):
    def f(zdir):
        p = zdir / "cohorts_init.parquet"
        rows = pq.read_table(p).to_pylist()
        rows = fn(rows)
        G.write_table(rows, G.COHORTS_SCHEMA, p)
    return f


def _classe_hors(rows):
    rows[0]["d_class"] = H.K_CLASSES          # rangs admis : 0 à K − 1
    return rows


def _doublon(rows):
    return rows + [dict(rows[0])]


def _cellule_hors_grille(rows):
    rows[0]["cell_id"] = 12 * 12 + 5
    return rows


def _essence_hors_referentiel(rows):
    rows[0]["species"] = "99"
    return rows


def _tiges_negatives(rows):
    rows[0]["stems_ha"] = -3.0
    return rows


def _sans_terme(essence, terme):
    def f(zdir):
        G.write_regeneration(zdir, G.regeneration_rows(G.ESSENCES_DEFAUT, omis=((essence, terme),)))
    return f


REFUS_SER = {
    # nom : (transformation du bloc simulate, mutation de la zone, mots attendus dans le message (l'un d'eux))
    "sans_recruitment": (_sans("recruitment"), None, ("recruitment",)),
    "recruitment_inconnu": (lambda s: {**s, "recruitment": "semis_magiques"}, None, ("recruitment",)),
    "cohorts_sans_bloc_regeneration": (_sans("regeneration"), None, ("regeneration",)),
    "ser_sans_bloc_ser": (_sans("ser"), None, ("ser",)),
    "regeneration_parquet_absent": (None, _retirer("params/regeneration.parquet"), ("regeneration",)),
    "terme_de_semis_manquant": (None, _sans_terme("61", "kernel_scale_m"), ("kernel_scale_m",)),
    "terme_de_passage_manquant": (None, _sans_terme("03", "passage_height_m"), ("passage_height_m",)),
    "cohorts_init_absent": (None, _retirer("cohorts_init.parquet"), ("cohorts_init",)),
    "classe_hors_de_k": (None, _cohorts_init(_classe_hors), ("d_class", "classe")),
    "doublon_de_cohorte": (None, _cohorts_init(_doublon), ("doublon", "double", "dupliqu")),
    "cellule_hors_grille": (None, _cohorts_init(_cellule_hors_grille), ("cell_id", "grille")),
    "essence_hors_referentiel": (None, _cohorts_init(_essence_hors_referentiel), ("99",)),
    "tiges_negatives": (None, _cohorts_init(_tiges_negatives), ("stems_ha", "tiges")),
}


@pytest.fixture(scope="session", params=list(REFUS_SER))
def refus_ser(request):
    cas = request.param
    tsim, mutate, mots = REFUS_SER[cas]
    sim = H.sim_ser(1)
    sim = tsim(sim) if tsim else sim
    # nom de zone neutre : le chemin de la zone, écrit dans les messages, ne doit pas contenir les mots cherchés
    res = _run_ser(f"m5_refus_s{list(REFUS_SER).index(cas):02d}", 12, sim, mutate)
    res.update(cas=cas, mots=mots)
    yield res
    H.remove_zone(res["name"])


REFUS_MASSIF = {
    "sans_recruitment": (H.sim_massif(1, recruitment=None), None, ("recruitment",)),
    "cohorts_sans_bloc_regeneration": ({k: v for k, v in H.sim_massif(1).items() if k != "regeneration"}, None,
                                       ("regeneration",)),
    "regeneration_parquet_absent": (H.sim_massif(1), _retirer("params/regeneration.parquet"), ("regeneration",)),
    "terme_de_semis_manquant": (H.sim_massif(1), lambda z: G.write_regeneration(
        z, G.regeneration_rows(H.ESSENCES_MASSIF, par_essence=False, omis=((None, "fecundity_seeds_per_m2_ba_yr"),))),
        ("fecundity_seeds_per_m2_ba_yr",)),
}


@pytest.fixture(scope="session", params=list(REFUS_MASSIF))
def refus_massif(request):
    cas = request.param
    sim, mutate, mots = REFUS_MASSIF[cas]
    nom = f"m5_refus_m{list(REFUS_MASSIF).index(cas):02d}"      # nom neutre (voir refus_ser)
    zdir, cfg = H.zone_massif(nom, sim, mutate)
    res = {"dir": zdir, "config": cfg, "name": nom, "proc": H.run_simulate(nom, cfg), "cas": cas, "mots": mots}
    yield res
    H.remove_zone(nom)


@pytest.fixture(scope="session")
def ser_nan():
    H.remove_zone("m5_ser_nan")
    zdir, cfg = H.zone_ser("m5_ser_nan", 12, H.sim_ser(1))
    res = {"dir": zdir, "config": cfg, "name": "m5_ser_nan", "proc": H.run_simulate("m5_ser_nan", cfg, "--inject-nan")}
    yield res
    H.remove_zone(res["name"])


@pytest.fixture(scope="session")
def ser_memoire():
    H.remove_zone("m5_ser_memoire")
    zdir, cfg = H.zone_ser("m5_ser_memoire", 12, H.sim_ser(1))
    res = {"dir": zdir, "config": cfg, "name": "m5_ser_memoire",
           "proc": H.run_simulate("m5_ser_memoire", cfg, "--memoire-disponible", "1")}
    yield res
    H.remove_zone(res["name"])
