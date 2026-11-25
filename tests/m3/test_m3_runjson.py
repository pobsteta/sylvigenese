"""M3a, sim/run.json (spec §6, §10 ; contrat run.json amendé par la mission 033) : graine, horizon, fils, empreinte
de config.yml, part provisoire, valeurs mises à zéro, et les comptes que le moteur doit rendre."""
import hashlib
import math

import numpy as np
import pytest

import helpers_m3 as H
from conftest import CHAINE, _rejouer
from test_m3_chaine import T0

SIM = H.SIM_NOMINAL
queue = H.queue


@pytest.fixture(scope="module")
def run(chaine):
    return H.read_run_json(chaine["dir"])


def test_run_json_redit_la_config(chaine, run):
    assert (run["level"], run["seed"], run["t0"], run["years"], run["threads"]) == \
        (SIM["level"], SIM["seed"], SIM["t0"], SIM["years"], SIM["threads"])
    assert run["schema_version"] == 1


def test_config_sha256_est_celui_des_octets_de_config_yml(chaine, run):
    attendu = hashlib.sha256(chaine["config"].read_bytes()).hexdigest()
    assert run["config_sha256"] == attendu


def test_l_empreinte_change_avec_la_config(chaine, run_graine):
    """Deux configs différentes (la graine), deux empreintes : l'empreinte est bien celle du fichier lu."""
    a = H.read_run_json(chaine["dir"])["config_sha256"]
    b = H.read_run_json(run_graine["dir"])["config_sha256"]
    assert a != b
    assert b == hashlib.sha256(run_graine["config"].read_bytes()).hexdigest()


def test_tout_est_provisoire_dans_le_jeu_fictif(chaine, run, params):
    """Spec §10 : toutes les lignes de paramètres du jeu fictif sont `provisoire: true` ; la part vaut 1."""
    assert params.df["provisoire"].all(), "précondition : le jeu fictif ne doit porter que des paramètres provisoires"
    assert run["provisional_share"] == 1


def test_rien_n_est_mis_a_zero_en_m3a(run):
    """La règle |Q| < 1e-9 × max(Q) est codée et testée en T10, mais sans objet en M3a : aucune FFT."""
    assert run["zeroed_values"] == 0


@pytest.fixture(scope="module")
def zone_definitive(chaine):
    """Mêmes paramètres, tous marqués provisoire = False : la part provisoire doit tomber à 0."""
    def mut(zdir):
        H.rewrite_params(zdir, lambda n, df: df.assign(provisoire=False))
    res = _rejouer("m3_definitive", {**SIM, "years": 2}, mut)
    yield res
    H.remove_zone(res["name"])


@pytest.fixture(scope="module")
def zone_partielle(chaine):
    """Seule la croissance est marquée définitive : la part est strictement entre 0 et 1."""
    def mut(zdir):
        H.rewrite_params(zdir, lambda n, df: df.assign(provisoire=False) if n == "growth" else df)
    res = _rejouer("m3_partielle", {**SIM, "years": 2}, mut)
    yield res
    H.remove_zone(res["name"])


def test_la_part_provisoire_vaut_0_quand_rien_n_est_provisoire(zone_definitive):
    assert zone_definitive["proc"].returncode == 0, queue(zone_definitive["proc"])
    assert H.read_run_json(zone_definitive["dir"])["provisional_share"] == 0


def test_la_part_provisoire_est_fractionnaire_si_une_partie_l_est(zone_partielle):
    assert zone_partielle["proc"].returncode == 0, queue(zone_partielle["proc"])
    s = H.read_run_json(zone_partielle["dir"])["provisional_share"]
    assert 0 < s < 1, s


def test_deaths_et_recruits_sont_comptes_sur_toute_la_simulation(chaine, run, arbres):
    nr = arbres[arbres["tree_id"].str.startswith("r")]["tree_id"].nunique()
    assert run["recruits"] == nr and run["deaths"] == int((arbres["status"] == "dead").sum())
    assert run["recruits"] > 0 and run["deaths"] > 0


def test_les_disques_de_bord_sont_comptes(chaine, run, arbres, grid):
    """edge_disks : couples (arbre, année) dont le disque de 15 m déborde de la grille ; les arbres de l'état de
    début de chaque pas (partitions t0 à t0 + years − 1, arbres vivants). Borne basse : disque strictement
    sorti ; borne haute : disque tangent compris."""
    a = arbres[(arbres["year"] < T0 + SIM["years"]) & (arbres["status"] == "alive")]
    d = np.minimum.reduce([a["x"] - grid.x0, grid.x1 - a["x"], a["y"] - grid.y1, grid.y0 - a["y"]])
    bas, haut = int((d < H.RAYON - 1e-9).sum()), int((d <= H.RAYON + 1e-9).sum())
    assert bas > 0
    assert bas <= run["edge_disks"] <= haut, (bas, run["edge_disks"], haut)


def test_les_sorties_de_domaine_couvrent_toutes_les_variables_lues(run, params):
    """Toutes les variables des termes lisses des quatre modèles lus sont présentes, à 0 si aucune sortie."""
    lues = set()
    for m in ("growth_gam", "mortality_gam", "recruitment_gam", "relative_height_gam"):
        lues |= set(params.df[(params.df["model"] == m) & params.df["term"].str.startswith("s(")]["variable"])
    assert lues <= set(run["domain_outputs"]), f"variables absentes de domain_outputs : {lues - set(run['domain_outputs'])}"
    for v, c in run["domain_outputs"].items():
        assert isinstance(c["below"], int) and isinstance(c["above"], int) and c["below"] >= 0 and c["above"] >= 0, (v, c)


def test_les_sorties_de_domaine_depassent_le_compte_du_premier_pas(run, grid, params, init):
    """Borne basse indépendante : au premier pas, l'accroissement relit d130 (arbres de plus de 81 cm), trophic
    (valeurs au-dessus de 6,375) : chaque valeur hors nœuds est comptée au moins une fois (la mortalité les relit)."""
    p = H.predict_step(grid, params, init)
    x, y, d, sp = (init[c].to_numpy() for c in ("x", "y", "d130", "species"))
    st = grid.station(x, y)
    bas, haut = {}, {}
    for s in sorted(set(sp)):
        m = sp == s
        v = {"d130": d[m], "ba_plot": p["ba_plot"][m], "bal": p["bal"][m], **{k: a[m] for k, a in st.items()}}
        for var, (b, h) in params.out_of_domain("growth_gam", s, v).items():
            bas[var] = bas.get(var, 0) + b
            haut[var] = haut.get(var, 0) + h
    assert sum(haut.values()) + sum(bas.values()) > 100, "précondition : le jeu fictif doit sortir du domaine"
    for var in bas:
        assert run["domain_outputs"][var]["below"] >= bas[var], (var, "below", run["domain_outputs"][var], bas[var])
        assert run["domain_outputs"][var]["above"] >= haut[var], (var, "above", run["domain_outputs"][var], haut[var])


def test_les_cellules_melees_et_le_plafond_sont_comptes(run):
    assert isinstance(run["mixed_cells"], int) and run["mixed_cells"] >= 0
    assert run["cells_at_height_ceiling"] > 0, "le jeu fictif a des cellules au-dessus du plafond (S03, spec §5)"


def test_la_duree_et_les_fils_sont_ecrits(run):
    assert run["duration_s"] > 0 and run["threads"] == 1
