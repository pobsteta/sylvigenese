"""trees_init/ et stands.parquet (spec §4 ; contrats prepare.trees_init et prepare.stands)."""
import math
import re

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


def _coef(rows):
    coef = {}
    for r in rows:
        if r["model"] == "etage_b":
            coef.setdefault(r["species"], {})[r["term"]] = r["value"]
    return coef


def _d130_attendu(t, c):
    """ln D = a + b ln H (+ c ln CPA si l'essence a un coefficient c), spec §4.3."""
    ln = c["a"] + c["b"] * math.log(t["h"])
    if "c" in c:
        ln += c["c"] * math.log(t["crown_area"])
    return math.exp(ln)


def test_chaque_arbre_detecte_porte_une_surface_de_houppier_positive(trees):
    # spec §4.3 : crown_area (m²) segmentée sur le MNH, pour les arbres détectés.
    detectes = [t for t in trees if t["d130_source"] not in ("inventaire_video",)]
    assert len(detectes) >= 100
    for t in detectes:
        assert "crown_area" in t, f"colonne crown_area absente : {sorted(t)}"
        assert t["crown_area"] is not None and math.isfinite(t["crown_area"]) and t["crown_area"] > 0, t
        assert t["crown_area"] < 400.0, f"houppier de {t['crown_area']} m² : segmentation douteuse"


def test_d130_par_etage_b_avec_les_coefficients_du_fichier(trees):
    # ln D = a + b ln H + c ln CPA, coefficients lus dans params/allometry.parquet (jamais inventés).
    coef = _coef(H.read_parquet(H.ZONE / "params" / "allometry.parquet"))
    verifies = 0
    for t in trees:
        if t["d130_source"].startswith("tarif_etage_b") and t["species"] in coef:
            attendu = _d130_attendu(t, coef[t["species"]])
            assert t["d130"] == pytest.approx(attendu, rel=0.02), (t["tree_id"], t["d130"], attendu)
            verifies += 1
    assert verifies >= 100


def test_variante_houppier_d130_source_distingue_avec_et_sans_coefficient_c(houppier_zone):
    # Variante : c connu pour 09, 62, 64, 03 ; l'essence 61 n'a que a et b (spec §4.3).
    from conftest import COEF_HOUPPIER, SANS_C
    for k in ("prepare", "biomes", "trees"):
        p = houppier_zone[k]
        assert p.returncode == 0, f"{k} : code {p.returncode}\n{p.stderr[-1500:]}"
    rows = H.read_parquet(H.trees_init_path(houppier_zone["dir"]))
    det = [t for t in rows if t["d130_source"] != "inventaire_video"]
    avec = [t for t in det if t["species"] != SANS_C]
    sans = [t for t in det if t["species"] == SANS_C]
    assert len(avec) >= 100 and len(sans) >= 10, (len(avec), len(sans))
    src_avec, src_sans = {t["d130_source"] for t in avec}, {t["d130_source"] for t in sans}
    assert src_avec.isdisjoint(src_sans), \
        f"d130_source ne distingue pas le modèle avec houppier ({src_avec}) du modèle sans c ({src_sans})"
    for t in det:
        assert t["crown_area"] > 0, t
        attendu = _d130_attendu(t, COEF_HOUPPIER[t["species"]])
        assert t["d130"] == pytest.approx(attendu, rel=0.02), (t["tree_id"], t["species"], t["d130"], attendu)


def test_variante_essence_sans_aucun_coefficient_erreur_explicite(sans_coefficient_zone):
    # spec §4.3 : « une essence sans aucun coefficient est une erreur explicite ».
    d = sans_coefficient_zone["dir"]
    assert sans_coefficient_zone["prepare"].returncode == 0
    assert sans_coefficient_zone["biomes"].returncode == 0
    p = sans_coefficient_zone["trees"]
    assert p.returncode != 0, "trees réussit alors que l'essence 09 n'a aucun coefficient"
    err = p.stderr
    assert err.strip(), "aucun message d'erreur"
    assert "09" in err, f"le message ne nomme pas l'essence 09 : {err[-600:]}"
    assert re.search(r"(?i)coefficient", err) and re.search(r"(?i)essence|allom", err), err[-600:]
    assert re.search(r"(?i)\b(aucun|aucune|manque|absent|sans)\b", err), \
        f"message pas en français ? {err[-600:]}"
    assert not (d / "trees_init").exists() and not (d / "trees_init.parquet").exists()


def test_rapport_arbres_dit_que_la_hauteur_n_est_pas_avancee_jusqu_a_t0(runs):
    # spec §4.4 : hauteur MNH avancée jusqu'à t0 par la courbe de dynamics (M2) ; en M1a, le rapport
    # dit qu'elle ne l'est pas encore.
    blocs = H.report_blocks("rapport_arbres.html")
    ok = [b for b in blocs if re.search(r"(?i)hauteur", b) and re.search(r"\bt0\b", b)
          and re.search(r"(?i)dynamics", b)
          and re.search(r"(?i)pas encore|n'est pas|non avanc|en attente|attend", b)]
    assert ok, "rapport_arbres.html ne dit pas que la hauteur n'est pas avancée jusqu'à t0 (attente de dynamics)"


def test_inventaire_video_lu_mais_absent_de_trees_init_en_m1a(trees, runs):
    # Arbitrage de l'orchestrateur (24/11/2026) : en M1a, inventaire_video.gpkg est lu et validé à
    # l'entrée, mais n'entre pas dans trees_init ; le rapport des arbres le dit.
    video = [t["tree_id"] for t in trees
             if "inventaire_video" in (t["d130_source"], t["species_source"])]
    assert not video, f"{len(video)} arbres issus de l'inventaire vidéo : {video[:5]}"
    blocs = H.report_blocks("rapport_arbres.html")
    assert any(re.search(r"(?i)inventaire[ _]vid[ée]o", b)
               and re.search(r"(?i)pas utilis|non utilis|n'est pas (?:encore )?(?:utilis|pris)", b)
               for b in blocs), "rapport_arbres.html ne dit pas que l'inventaire vidéo n'est pas utilisé en M1a"


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
