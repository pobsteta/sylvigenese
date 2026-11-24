"""trees_init/ et stands.parquet (spec §4 ; contrats prepare.trees_init et prepare.stands)."""
import math

import numpy as np
import pytest
import rasterio

import helpers as H

SPECIES_CSV = H.ROOT / "contracts" / "species.csv"
SOURCES_ESSENCE = {"nemeton", "vegetation_type", "inventaire_video"}
SOURCES_D130 = {"tarif_etage_b", "inventaire_video", "nemeton"}


@pytest.fixture(scope="module")
def trees(runs):
    return H.read_parquet(H.trees_init_path())


@pytest.fixture(scope="module")
def known_species():
    lines = SPECIES_CSV.read_text(encoding="utf-8").splitlines()[1:]
    return {ln.split(",")[0] for ln in lines if ln}


@pytest.fixture(scope="module")
def chm():
    with rasterio.open(H.INPUTS / "chm.tif") as r:
        return r.read(1), r.transform


def _local(t):
    return t["x"] - H.X0, t["y"] - H.Y0


def _in(rect, t):
    lx, ly = _local(t)
    return rect[0] <= lx < rect[1] and rect[2] <= ly < rect[3]


def test_trees_init_non_vide_et_chaque_arbre_a_ses_deux_sources(trees):
    assert len(trees) >= 100
    for t in trees:
        assert t["species_source"] in SOURCES_ESSENCE, t
        assert t["d130_source"] in SOURCES_D130, t


def test_codes_essence_du_referentiel_et_en_chaine(trees, known_species):
    # Piège du zéro de tête : "09" et non 9.
    esp = {t["species"] for t in trees}
    assert all(isinstance(e, str) for e in esp)
    assert esp <= known_species, f"essences hors contracts/species.csv : {esp - known_species}"


def test_positions_dans_le_massif_pas_de_x_y_inverses(trees):
    # Piège de la Somalie : x vers l'est (~700 000), y vers le nord (~6 500 000).
    xs = np.array([t["x"] for t in trees])
    ys = np.array([t["y"] for t in trees])
    assert xs.min() >= H.X0 and xs.max() <= H.X0 + H.SIDE, (xs.min(), xs.max())
    assert ys.min() >= H.Y0 and ys.max() <= H.Y0 + H.SIDE, (ys.min(), ys.max())


def test_identifiants_uniques(trees):
    ids = [t["tree_id"] for t in trees]
    assert len(ids) == len(set(ids))


def test_chaque_arbre_est_sur_un_maximum_du_mnh_de_la_meme_hauteur(trees, chm):
    # Un arbre « détecté à sa place » : le MNH à 50 cm, autour de (x, y), atteint sa hauteur.
    a, t = chm
    mauvais = []
    for tr in trees:
        c = int((tr["x"] - t.c) / t.a)
        r = int((t.f - tr["y"]) / -t.e)
        win = a[max(r - 4, 0):r + 5, max(c - 4, 0):c + 5]
        if win.size == 0 or abs(float(win.max()) - tr["h"]) > 1.0:
            mauvais.append((tr["tree_id"], tr["h"], float(win.max()) if win.size else None))
    assert not mauvais, f"{len(mauvais)} arbres sans cime du MNH à ±1 m de leur hauteur : {mauvais[:3]}"


def test_essence_et_source_selon_le_polygone_nemeton(trees, stands):
    # spec §4.1 : essence du polygone qui contient l'arbre ; §4.2 : hors polygone, vegetation_type.
    n_hors = 0
    for t in trees:
        s = H.stands_in(t["x"], t["y"], stands)
        if s is None:
            n_hors += 1
            assert t["species_source"] == "vegetation_type", \
                f"arbre hors polygone {t['tree_id']} : species_source = {t['species_source']}"
        else:
            if t["species_source"] == "nemeton":
                assert t["species"] == s["species"], (t["tree_id"], t["species"], s["species"])
            if s["stand_id"] != "S04":  # S04 seule porte des placettes vidéo
                assert t["species_source"] == "nemeton", (t["tree_id"], t["species_source"])
    assert n_hors >= 10, "aucun arbre détecté dans la forêt sans polygone nemeton"


def test_chaque_polygone_a_des_arbres_et_la_trouee_n_en_a_pas(trees, stands):
    for s in stands:
        n = sum(1 for t in trees if H.stands_in(t["x"], t["y"], [s]) is not None)
        assert n >= 10, f"{s['stand_id']} : {n} arbres"
    x0, x1, y0, y1 = H.GAP
    dans = [t for t in trees if _in((x0, x1, y0, y1), t)]
    assert not dans, f"{len(dans)} arbres dans la trouée non forestière"


def test_arbre_de_s03_detecte_a_sa_place_au_dessus_du_plafond(trees):
    # S03 : épicéa (62) de 36 m, au-dessus de h_pot ; la hauteur n'est pas ramenée au plafond.
    s03 = [t for t in trees if _in((350, 650, 500, 1000), t)]
    assert len(s03) >= 10
    assert {t["species"] for t in s03} == {"62"}
    assert np.median([t["h"] for t in s03]) > 30.0


def test_d130_par_etage_b_avec_les_coefficients_du_fichier(trees):
    # ln D = a + b ln H, a et b lus dans params/allometry.parquet (jamais inventés).
    rows = H.read_parquet(H.ZONE / "params" / "allometry.parquet")
    coef = {}
    for r in rows:
        if r["model"] == "etage_b":
            coef.setdefault(r["species"], {})[r["term"]] = r["value"]
    verifies = 0
    for t in trees:
        if t["d130_source"] == "tarif_etage_b" and t["species"] in coef:
            c = coef[t["species"]]
            attendu = math.exp(c["a"] + c["b"] * math.log(t["h"]))
            assert t["d130"] == pytest.approx(attendu, rel=0.02), (t["tree_id"], t["d130"], attendu)
            verifies += 1
    assert verifies >= 100


def test_d130_inventaire_video_seulement_dans_s04(trees, stands):
    s04 = [s for s in stands if s["stand_id"] == "S04"]
    for t in trees:
        if t["d130_source"] == "inventaire_video" or t["species_source"] == "inventaire_video":
            assert H.stands_in(t["x"], t["y"], s04) is not None, t["tree_id"]


def test_stands_parquet_reprend_les_cinq_polygones(runs, stands):
    rows = {r["stand_id"]: r for r in H.read_parquet(H.ZONE / "stands.parquet")}
    assert set(rows) == {s["stand_id"] for s in stands} == {"S01", "S02", "S03", "S04", "S05"}
    for s in stands:
        r = rows[s["stand_id"]]
        assert r["species"] == s["species"] and isinstance(r["species"], str)
        assert r["d130"] == pytest.approx(s["dbh_cm"])
        assert r["h"] == pytest.approx(s["height_m"])
        assert r["density_ha"] == pytest.approx(s["density_ha"])
        assert r["age"] == s["age_yr"]
        assert r["source"] == s["source"]
        assert r["stand_id_source"] == s["stand_id_source"]
    assert rows["S04"]["source"] == "synthetic_ml"
