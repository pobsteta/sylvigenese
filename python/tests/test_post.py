"""Tests unitaires de `post` (mission 053) : formules du tarif, domaine, refus, et une mini-zone de bout en bout.

Les valeurs du tarif sont celles du jeu fictif (synthétiques, tests/fixtures/zone_fictive/params/tarif.parquet) ou des
valeurs d'essai écrites ici : aucune ne vient de tarif-nemeton. Le validateur appelé est le vrai (contracts/validate).
La racine du projet (SYLVIGENESE_ROOT) est un dossier temporaire : le jeu fictif versionné n'est jamais écrit.
Coordonnées : EPSG:2154, x vers l'est puis y vers le nord, en mètres.
"""

import hashlib
import json
import math
import shutil
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import rasterio
import yaml
from rasterio.transform import from_origin

from sylvigenese import post
from sylvigenese.common import ModuleError

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_TARIF = ROOT / "tests" / "fixtures" / "zone_fictive" / "params" / "tarif.parquet"
GROUPS = post.read_species_groups(ROOT / "contracts" / "species.csv")
X0, Y0, RES = 700_000.0, 6_501_000.0, 25.0      # coin nord-ouest de la mini-grille, EPSG:2154
AREA = RES * RES / 10_000.0


def fixture_tarif(tmp_path, change=None) -> post.Tarif:
    rows = pq.read_table(FIXTURE_TARIF).to_pylist()
    if change:
        rows = change(rows)
    path = tmp_path / "tarif.parquet"
    pq.write_table(pa.Table.from_pylist(rows, schema=pq.read_schema(FIXTURE_TARIF)), path)
    return post.Tarif(path, GROUPS)


def one(value):
    return np.array([float(value)])


# ------------------------------------------------------------------ formules
def test_volume_d_un_hetre_de_40_cm_et_20_m_a_la_calculette(tmp_path):
    m = fixture_tarif(tmp_path).species["09"]
    v = post.aerial_volume(m, one(40), one(20))[0]
    # π/4 · 0,40² · 20 · exp(−0,30 + 0,05 ln(40/30) + 0,10 ln(20/25)), tarif synthétique sans correction de biais
    assert math.isclose(v, math.pi / 4 * 0.16 * 20 * math.exp(-0.30 + 0.05 * math.log(4 / 3) + 0.10 * math.log(0.8)),
                        rel_tol=1e-12)
    assert math.isclose(v, 1.8471724842550155, rel_tol=1e-12)


def test_correction_de_biais_du_log_quand_sigma_et_facteur_sont_donnes(tmp_path):
    def add(rows):
        base = dict(rows[0])
        return rows + [{**base, "terme": "sigma_log", "valeur": 0.2, "unite": "ln(m3)"},
                       {**base, "essence": "03", "terme": "sigma_log", "valeur": 0.1, "unite": "ln(m3)"},
                       {**base, "essence": None, "groupe": "feuillu", "terme": "facteur_biais_sigma2", "valeur": 0.5}]
    plain = post.aerial_volume(fixture_tarif(tmp_path).species["09"], one(40), one(20))[0]
    biased = post.aerial_volume(fixture_tarif(tmp_path, add).species["09"], one(40), one(20))[0]
    assert math.isclose(biased, plain * math.exp(0.5 * 0.2 ** 2), rel_tol=1e-12)


def test_sigma_sans_facteur_de_biais_est_refuse(tmp_path):
    def add(rows):
        return rows + [{**rows[0], "terme": "sigma_log", "valeur": 0.2, "unite": "ln(m3)"}]
    with pytest.raises(ModuleError, match="vont ensemble"):
        fixture_tarif(tmp_path, add)


def test_forme_synthetique_des_resineux_du_jeu_fictif(tmp_path):
    # contrat params/tarif : tige = π/4 (D/100)² H (synth_p1 + synth_p2/2), V aérien = tige × synth_E
    m = fixture_tarif(tmp_path).species["61"]
    assert m["form"] == "resineux_synthetique"
    v = post.aerial_volume(m, one(30), one(25))[0]
    assert math.isclose(v, math.pi / 4 * 0.09 * 25 * (0.40 + 0.60 / 2) * 1.10, rel_tol=1e-12)
    assert math.isclose(v, 1.360702318086079, rel_tol=1e-12)


# Profil NEMETON v5 d'essai : valeurs choisies pour les tests (aucune n'est celle de tarif-nemeton, sauf h_ref = 1,30 m,
# hauteur de mesure du d130 qui définit la forme). Mission 056 : n_points, marge_sommet et u_min d'essai.
NEMETON = {"form": "resineux_nemeton", "k0": 0.0, "k1": 0.0, "beta": 0.0, "lam": 2.0, "a": 0.0, "x0": 0.9, "sx": 0.1,
           "h_ref": 1.3, "D_ref": 30.0, "n_points": 301, "marge_sommet": 0.002, "u_min": 1e-6,
           "E_a": 0.0, "E_b": 0.0, "E_D_plafond": 20.0, "E_D_ref": 30.0}


def test_profil_nemeton_a_exposant_nul_est_un_cylindre_exact():
    v = post.stem_volume_nemeton(NEMETON, one(30), one(20))[0]
    assert math.isclose(v, math.pi / 4 * 0.09 * (20 - 0.002), rel_tol=1e-12)


def test_profil_nemeton_lineaire_par_le_terme_a_valeur_analytique_exacte():
    # k = k0 + (k1 − k0) σ + a ln(D/D_ref) = 0 + 0 + (1/ln 2) ln(60/30) = 1 : d² = D² (1 − x), section linéaire en
    # hauteur, que la règle des trapèzes intègre EXACTEMENT. Avec x = (hg − h_ref)/(H − h_ref) et la borne haute
    # H − marge_sommet : tige = π/4 (D/100)² [h_ref + (H − h_ref)(X − X²/2)], X = (H − marge − h_ref)/(H − h_ref).
    m = {**NEMETON, "a": 1.0 / math.log(2.0)}
    d, h = 60.0, 22.0
    big_x = (h - 0.002 - 1.3) / (h - 1.3)
    expected = math.pi / 4 * 0.36 * (1.3 + (h - 1.3) * (big_x - big_x ** 2 / 2))
    assert math.isclose(post.stem_volume_nemeton(m, one(d), one(h))[0], expected, rel_tol=1e-12)
    # D_ref compte : au diamètre de référence, ln(D/D_ref) = 0, k = 0, cylindre jusqu'à H − marge
    assert math.isclose(post.stem_volume_nemeton(m, one(30), one(h))[0], math.pi / 4 * 0.09 * (h - 0.002), rel_tol=1e-12)


def reference_stem_volume(m: dict, d: float, h: float, nodes: int = 400) -> float:
    """Oracle indépendant du profil NEMETON v5 (contrat import_tarif.tarif, éq. 5b) : l'intégrale CONTINUE de π d(hg)²/4
    de h_ref à H − marge_sommet, par quadrature de Gauss-Legendre (numpy), plus le cylindre de 0 à h_ref. Elle ne
    reprend pas la règle des trapèzes de post : l'écart attendu est l'erreur des trapèzes (moins de 1e-4 en relatif
    sur ces profils lisses), alors qu'un terme faussé du profil déplace le volume de plusieurs pour cent."""
    h0, eps = m["h_ref"], m["marge_sommet"]
    top = (h - eps - h0) / (h - h0)
    t, w = np.polynomial.legendre.leggauss(nodes)
    x = (t + 1.0) / 2.0 * top
    w = w * top / 2.0
    hg = h0 + x * (h - h0)
    u = np.maximum(1.0 - x, m["u_min"])
    k = np.maximum(m["k0"] + (m["k1"] - m["k0"]) / (1.0 + np.exp(-(x - m["x0"]) / m["sx"]))
                   + m["a"] * np.log(d / m["D_ref"]), 0.0)
    dg = d / 100.0 * np.exp(k / 2.0 * np.log(u) + m["beta"] * (np.exp(-(hg - h0) / m["lam"]) - 1.0))
    return float((h - h0) * np.sum(w * np.pi * dg ** 2 / 4.0) + h0 * np.pi / 4.0 * (d / 100.0) ** 2)


@pytest.mark.parametrize("terms", [
    {"k0": 1.0, "k1": 3.0, "x0": 0.5, "sx": 0.1},                                   # transition de k : x0 et sx
    {"k0": 1.0, "k1": 3.0, "x0": 0.5, "sx": 0.1, "beta": 0.3, "lam": 3.0},          # plus l'empattement : beta, lam
    {"k0": 1.0, "k1": 3.0, "x0": 0.5, "sx": 0.1, "beta": 0.3, "lam": 3.0, "a": 0.4},  # plus l'effet du diamètre : a
])
def test_profil_nemeton_complet_egal_a_l_integrale_continue(terms):
    # Discriminant (mission 056) : doubler sx, décaler x0 de 0,05 ou doubler lam déplace ces volumes de 2,6 à 9 %,
    # quand la règle des trapèzes reste à moins de 2e-5 de l'intégrale continue.
    m = {**NEMETON, **terms}
    d, h = np.array([36.0, 18.0, 55.0]), np.array([24.0, 14.0, 33.0])
    got = post.stem_volume_nemeton(m, d, h)
    for i in range(len(d)):
        assert math.isclose(got[i], reference_stem_volume(m, d[i], h[i]), rel_tol=1e-4), (terms, d[i], h[i])


def test_expansion_nemeton_valeurs_analytiques_sous_et_au_dessus_du_plafond():
    # E(D) = exp(a + b ln(min(D, D_plafond)/D_ref)) = e^a (min(D, D_plafond)/D_ref)^b ; a = ln 2, b = 1, D_ref = 20,
    # D_plafond = 40 : E(30) = 2 × 1,5 = 3 ; E(40) = 4 ; E(50) = 4 (constant au-delà du plafond). Tige cylindrique
    # (k = 0) : tige = π/4 (D/100)² (H − marge), connue exactement.
    m = {**NEMETON, "E_a": math.log(2.0), "E_b": 1.0, "E_D_ref": 20.0, "E_D_plafond": 40.0}
    d, h = np.array([30.0, 40.0, 50.0]), np.array([20.0, 20.0, 20.0])
    stem = np.pi / 4 * (d / 100.0) ** 2 * (20.0 - 0.002)
    assert np.allclose(post.aerial_volume(m, d, h), stem * np.array([3.0, 4.0, 4.0]), rtol=1e-12, atol=0.0)
    # b compte : avec b = 2, E(30) = 2 × 1,5² = 4,5
    m2 = {**m, "E_b": 2.0}
    assert math.isclose(post.aerial_volume(m2, one(30), one(20))[0], stem[0] * 4.5, rel_tol=1e-12)


def test_profil_nemeton_a_exposant_2_est_un_cone_au_dessus_de_h_ref():
    m = {**NEMETON, "k0": 2.0, "k1": 2.0}          # d = D (1 − x) : cône de h_ref au sommet
    v = post.stem_volume_nemeton(m, one(30), one(20))[0]
    expected = math.pi / 4 * 0.09 * (1.3 + (20 - 1.3) / 3)
    assert math.isclose(v, expected, rel_tol=1e-4)


def test_profil_nemeton_par_paquets_egal_au_calcul_d_un_coup():
    d = np.linspace(8, 90, 57)
    h = np.linspace(6, 45, 57)
    m = {**NEMETON, "k0": 0.7, "k1": 1.6, "beta": 0.08, "a": 0.2}
    assert np.array_equal(post.stem_volume_nemeton(m, d, h, chunk=7), post.stem_volume_nemeton(m, d, h))


def test_expansion_constante_au_dela_du_plafond():
    m = {**NEMETON, "E_a": 0.05, "E_b": -0.2}
    stem = post.stem_volume_nemeton(m, np.array([25.0, 40.0]), np.array([20.0, 20.0]))
    v = post.aerial_volume(m, np.array([25.0, 40.0]), np.array([20.0, 20.0]))
    e = math.exp(0.05 - 0.2 * math.log(20 / 30))
    assert np.allclose(v / stem, [e, e], rtol=1e-12)


def nemeton_fir(rows: list[dict]) -> list[dict]:
    """Tarif du jeu fictif où le sapin (61) prend la forme NEMETON v5, avec des valeurs d'essai (aucune de tarif-nemeton),
    et un domaine borné en H/D seulement, comme les résineux du tarif réel : un petit sapin peut y être DANS le domaine.
    Les termes partagés sont écrits à l'essence, pour laisser 62 et 64 sous la forme synthétique."""
    base = next(r for r in rows if r["essence"] == "61")
    kept = [r for r in rows if not (r["essence"] == "61" and (r["modele"] in ("profil_tige_resineux", "expansion_resineux")
                                                              or r["terme"] in ("dbh_min", "dbh_max", "h_min", "h_max")))]
    terms = [("profil_tige_resineux", t, v, u) for t, v, u in (
        ("k0", 1.0, "sans_unite"), ("k1", 3.0, "sans_unite"), ("beta", 0.3, "sans_unite"), ("lam", 3.0, "m"),
        ("a", 0.4, "sans_unite"), ("x0", 0.5, "sans_unite"), ("sx", 0.1, "sans_unite"), ("h_ref", 1.3, "m"),
        ("D_ref", 30.0, "cm"), ("n_points", 301.0, "points"), ("marge_sommet", 0.002, "m"), ("u_min", 1e-6, "sans_unite"))]
    terms += [("expansion_resineux", t, v, u) for t, v, u in (
        ("a", math.log(2.0), "sans_unite"), ("b", 1.0, "sans_unite"), ("D_plafond", 40.0, "cm"), ("D_ref", 20.0, "cm"))]
    return kept + [{**base, "modele": m, "terme": t, "valeur": v, "unite": u} for m, t, v, u in terms]


def test_sapin_nemeton_sous_h_ref_compte_non_calcule_en_h_below(tmp_path):
    # mission 056 : un résineux NEMETON dans son domaine (H/D = 125 dans [30 ; 200]) mais de 1,25 m, ou de h_ref +
    # marge_sommet tout juste, n'a pas de profil intégrable : non calculé (h_below), sans refus de tout le run
    t = fixture_tarif(tmp_path, nemeton_fir)
    m = t.species["61"]
    assert m["form"] == "resineux_nemeton" and m["domain"]["dbh"] == (None, None) and m["domain"]["h"] == (None, None)
    d = np.array([1.0, 1.0416, 30.0])
    h = np.array([1.25, 1.302, 25.0])
    assert post.first_reason(m, d, h).tolist() == [-1, -1, -1], "les trois sapins sont dans le domaine du tarif"
    assert post.profile_too_short(m, h).tolist() == [True, True, False]
    trees = {"species": np.array(["61"] * 3, dtype=object), "alive": np.ones(3, bool), "d130": d, "h": h,
             "x": np.full(3, X0 + 1.0), "y": np.full(3, Y0 - 1.0)}
    grid = {"transform": from_origin(X0, Y0, RES, RES), "width": 1, "height": 1, "veg_of_cell": np.array([0])}
    out = post.compute_year(trees, t, grid)
    assert out["reason"].tolist() == [2, 2, -1] and out["too_short"].tolist() == [True, True, False]
    assert out["volume"][0] == 0 and out["volume"][1] == 0
    assert math.isclose(out["volume"][2], reference_stem_volume(m, 30.0, 25.0) * 2.0 * 1.5, rel_tol=1e-4)
    with pytest.raises(ModuleError, match="aurait dû être compté non calculé"):
        post.stem_volume_nemeton(m, one(1.0), one(1.25))


def test_infradensite_fonction_du_diametre():
    m = {"rho": ("nemeton", 600.0, -4.0, 30.0, 10.0, 0.92)}
    assert np.allclose(post.density_t_m3(m, np.array([30.0, 50.0])), [0.6 * 0.92, (600 - 8) * 0.92 / 1000], rtol=1e-12)


def test_raisons_hors_domaine_bornes_fermees_et_premiere_raison(tmp_path):
    t = fixture_tarif(tmp_path)
    d = np.array([40.0, 7.5, 10.0, 105.0])
    h = np.array([20.0, 12.0, 3.0, 30.0])
    assert post.first_reason(t.species["09"], d, h).tolist() == [-1, 0, -1, 1]
    # 64 : h = 2,9 < 3 et H/D = 27,6 < 30 : la première raison est h_below (indice 2)
    assert post.first_reason(t.species["64"], one(10.5), one(2.9)).tolist() == [2]
    assert post.first_reason(t.species["61"], one(10), one(21)).tolist() == [5]          # H/D = 210 > 200
    assert post.first_reason(t.species["09"], one(10), one(21)).tolist() == [-1]         # feuillu : H/D non borné


def test_essence_sans_tarif_n_emprunte_pas_celui_du_groupe_ni_de_quercus_spec(tmp_path):
    t = fixture_tarif(tmp_path)
    assert "02" not in t.species and "03" in t.species


@pytest.mark.parametrize("change,message", [
    (lambda rows: [r for r in rows if r["modele"] != "infradensite"], "infradensite"),
    (lambda rows: [r for r in rows if not (r["modele"] == "fraction_carbone" and r["groupe"] == "resineux")],
     "fraction_carbone"),
    (lambda rows: [r for r in rows if not (r["modele"] == "expansion_resineux" and r["essence"] == "62")],
     "expansion_resineux"),
    (lambda rows: [r for r in rows if not (r["modele"] == "racines" and r["groupe"] == "feuillu")], "racines"),
    (lambda rows: [{**r, "terme": "b_logD"} if r["terme"] == "b" else r for r in rows], "inconnus"),
    (lambda rows: [{**r, "unite": "g/cm3"} if r["modele"] == "infradensite" else r for r in rows], "unité douteuse"),
    (lambda rows: rows + [{**rows[0], "modele": "profil_tige_resineux", "terme": "synth_p1"}], "deux modèles"),
    (lambda rows: [{**r, "source_commit": "abcdef1"} if r["essence"] == "61" else r for r in rows], "commits"),
])
def test_tarif_incomplet_ou_inconnu_refuse(tmp_path, change, message):
    with pytest.raises(ModuleError, match=message):
        fixture_tarif(tmp_path, change)


# ------------------------------------------------------------------ mini-zone de bout en bout
# grille de 3 colonnes × 2 lignes, coin nord-ouest (700 000 ; 6 501 000) ; cellule 4 (ligne 1, colonne 1) sans type
VEG = np.array([[1, 1, 2], [2, 255, 1]], dtype=np.uint8)


def centre(cell: int) -> tuple[float, float]:
    r, c = divmod(cell, 3)
    return X0 + (c + 0.5) * RES, Y0 - (r + 0.5) * RES


# (tree_id, essence, d130 cm, h m, cellule, état en 2023)
TREES = [("A", "09", 40.0, 20.0, 0, "alive"),     # hêtre au point (700 012,5 ; 6 500 987,5) : cellule 0
         ("B", "61", 30.0, 25.0, 1, "alive"),     # sapin calculé
         ("C", "02", 30.0, 25.0, 2, "alive"),     # sans tarif
         ("D", "09", 7.5, 12.0, 4, "alive"),      # recrue d'une cellule sans type : dbh_below
         ("E", "09", 50.0, 26.0, 5, "dead")]      # meurt en 2023


@pytest.fixture
def mini(tmp_path, monkeypatch):
    root = tmp_path / "racine"
    zone = root / "data" / "zone_essai"
    (root / "contracts").mkdir(parents=True)
    shutil.copy(ROOT / "contracts" / "species.csv", root / "contracts" / "species.csv")
    (zone / "params").mkdir(parents=True)
    shutil.copy(FIXTURE_TARIF, zone / "params" / "tarif.parquet")
    profile = {"driver": "GTiff", "width": 3, "height": 2, "count": 1, "crs": "EPSG:2154",
               "transform": from_origin(X0, Y0, RES, RES)}
    with rasterio.open(zone / "grid.tif", "w", dtype="int32", **profile) as dst:
        dst.write(np.arange(6, dtype=np.int32).reshape(2, 3), 1)
    with rasterio.open(zone / "vegetation_map.tif", "w", dtype="uint8", nodata=255, **profile) as dst:
        dst.write(VEG, 1)
    (zone / "vegetation_map.csv").write_text("value,name\n1,hetraie\n2,sapiniere\n", encoding="utf-8")
    config = tmp_path / "config.yml"
    content = yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8"))
    content["zone"] = "zone_essai"
    content["simulate"] = {"level": "massif", "seed": 1, "t0": 2022, "years": 1}
    config.write_text(yaml.safe_dump(content), encoding="utf-8")
    monkeypatch.chdir(ROOT)
    monkeypatch.setenv("SYLVIGENESE_ROOT", str(root))
    monkeypatch.delenv("SYLVIGENESE_VALIDATE", raising=False)
    write_sim(zone, config)
    return {"zone": zone, "config": config}


def write_sim(zone: Path, config: Path, trees=TREES, swap_xy=False) -> None:
    sim = zone / "sim"
    shutil.rmtree(sim, ignore_errors=True)
    for year in (2022, 2023):
        rows = []
        for tid, sp, d, h, cell, state in trees:
            x, y = centre(cell)
            rows.append({"tree_id": tid, "species": sp, "x": y if swap_xy else x, "y": x if swap_xy else y,
                         "d130": d, "h": h, "hcb": 0.3 * h, "cw": 2.0,
                         "status": "alive" if year == 2022 else state})
        (sim / "trees" / f"year={year}").mkdir(parents=True)
        pq.write_table(pa.Table.from_pylist(rows), sim / "trees" / f"year={year}" / "part-00000.parquet")
    run = {"config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(), "t0": 2022, "years": 1}
    (sim / "run.json").write_text(json.dumps(run), encoding="utf-8")


def outputs(zone: Path) -> dict:
    return {name: (zone / "sim" / name).read_bytes() for name in ("summary.parquet", "summary_zone.parquet")}


def test_mini_zone_summary_a_la_main(mini):
    assert post.main(["--config", str(mini["config"])]) == 0
    s = {(r["cell_id"], r["year"], r["species"]): r for r in pq.read_table(mini["zone"] / "sim" / "summary.parquet").to_pylist()}
    a = s[(0, 2022, "09")]                     # le point connu tombe dans la cellule 0
    assert math.isclose(a["volume_m3_ha"], 1.8471724842550155 / AREA, rel_tol=1e-12)
    assert math.isclose(a["carbon_t_ha"], 1.8471724842550155 * 0.3 * 0.3 / AREA, rel_tol=1e-12)
    assert math.isclose(a["carbon_roots_t_ha"], a["carbon_t_ha"] * 0.10, rel_tol=1e-12)
    assert math.isclose(s[(1, 2023, "61")]["volume_m3_ha"], 1.360702318086079 / AREA, rel_tol=1e-12)
    c = s[(2, 2022, "02")]
    assert c["volume_m3_ha"] == 0 and c["basal_area_not_computed_share"] == 1.0 and c["stems_not_computed_ha"] == 1 / AREA
    assert (5, 2023, "09") not in s, "cellule sans arbre vivant : aucune ligne"
    assert (4, 2022, "09") in s, "la cellule sans type reste dans summary"
    assert all(r["provisoire"] is True for r in s.values())


def test_mini_zone_cellule_sans_type_hors_de_summary_zone_et_comptee(mini):
    assert post.main(["--config", str(mini["config"])]) == 0
    z = pq.read_table(mini["zone"] / "sim" / "summary_zone.parquet").to_pylist()
    assert {r["vegetation_type"] for r in z} == {"hetraie", "sapiniere"}
    hetraie_09 = {r["year"]: r for r in z if r["vegetation_type"] == "hetraie" and r["species"] == "09"}
    assert hetraie_09[2022]["forest_area_ha"] == 3 * AREA
    assert hetraie_09[2022]["stems_not_computed"] == 0, "la recrue de la cellule 4 n'est rangée dans aucun type"
    assert math.isclose(hetraie_09[2023]["dead_volume_m3"], 3.895028724998727, rel_tol=1e-12)
    j = json.loads((mini["zone"] / "sim" / "post.json").read_text(encoding="utf-8"))
    assert j["without_vegetation_type"] == {"cells": [4], "tree_years": 2}
    assert j["without_tarif"] == {"02": 2}
    assert j["out_of_domain"]["09"]["dbh_below"] == 2
    assert j["tree_years_computed"] + j["tree_years_not_computed"] == 10
    report = (mini["zone"] / "rapport_post.html").read_text(encoding="utf-8")
    assert "Cellules sans type de végétation" in report and "<td>4</td>" in report


def test_mini_zone_rejeu_identique_a_l_octet_pres(mini):
    assert post.main(["--config", str(mini["config"])]) == 0
    first = outputs(mini["zone"])
    assert post.main(["--config", str(mini["config"])]) == 0
    assert outputs(mini["zone"]) == first


def test_mini_zone_sans_racines_pas_de_colonne(mini):
    rows = [r for r in pq.read_table(FIXTURE_TARIF).to_pylist() if r["modele"] != "racines"]
    pq.write_table(pa.Table.from_pylist(rows, schema=pq.read_schema(FIXTURE_TARIF)), mini["zone"] / "params" / "tarif.parquet")
    assert post.main(["--config", str(mini["config"])]) == 0
    assert "carbon_roots_t_ha" not in pq.read_schema(mini["zone"] / "sim" / "summary.parquet").names
    assert "non calculées" in (mini["zone"] / "rapport_post.html").read_text(encoding="utf-8")


def test_mini_zone_petit_sapin_nemeton_compte_et_le_run_passe(mini):
    # mission 056 : avant, un seul résineux NEMETON de 1,30 m ou moins dans le domaine faisait refuser tout le run
    rows = nemeton_fir(pq.read_table(FIXTURE_TARIF).to_pylist())
    pq.write_table(pa.Table.from_pylist(rows, schema=pq.read_schema(FIXTURE_TARIF)), mini["zone"] / "params" / "tarif.parquet")
    write_sim(mini["zone"], mini["config"], trees=[*TREES, ("F", "61", 1.0, 1.25, 1, "alive")])
    assert post.main(["--config", str(mini["config"])]) == 0
    j = json.loads((mini["zone"] / "sim" / "post.json").read_text(encoding="utf-8"))
    assert j["out_of_domain"]["61"] == {**dict.fromkeys(post.REASONS, 0), "h_below": 2}
    s = {(r["cell_id"], r["year"], r["species"]): r for r in pq.read_table(mini["zone"] / "sim" / "summary.parquet").to_pylist()}
    assert s[(1, 2022, "61")]["stems_not_computed_ha"] == 1 / AREA
    assert 0 < s[(1, 2022, "61")]["basal_area_not_computed_share"] < 1      # le grand sapin B reste calculé
    report = (mini["zone"] / "rapport_post.html").read_text(encoding="utf-8")
    assert "Limite du profil de tige NEMETON v5" in report and "61 : 2" in report


def test_rapport_ecrit_le_domaine_lu_dans_le_tarif(mini):
    # mission 056 : règle des feuillus (décision de Pascal du 26/11/2026), règle H/D des résineux, bornes par essence,
    # toutes lues dans params/tarif.parquet : on change une borne du tarif, le rapport change avec elle
    rows = pq.read_table(FIXTURE_TARIF).to_pylist()
    rows = [{**r, "valeur": 17.25} if (r["essence"] == "09" and r["terme"] == "dbh_min") else r for r in rows]
    pq.write_table(pa.Table.from_pylist(rows, schema=pq.read_schema(FIXTURE_TARIF)), mini["zone"] / "params" / "tarif.parquet")
    assert post.main(["--config", str(mini["config"])]) == 0
    report = (mini["zone"] / "rapport_post.html").read_text(encoding="utf-8")
    assert "décision de Pascal du 26/11/2026" in report
    assert "multipliées par 0,9 (minimum) et 1,1 (maximum) en diamètre" in report and "2 m en hauteur" in report
    assert "<tr><td>09</td><td>feuillu</td><td style='text-align:left'>feuillus</td><td>17.25</td><td>100</td>" in report
    assert "H/D de 30 à 200 pour 61, 62, 64" in report
    assert "« synthetique_jeu_fictif »" in report
    assert "tarif NEMETON v5" not in report, "le jeu fictif n'a pas le tarif NEMETON v5 (résineux synthétiques)"
    assert "forme synthétique du jeu fictif" in report


def test_x_et_y_inverses_sont_refuses_et_rien_n_est_publie(mini, capsys):
    write_sim(mini["zone"], mini["config"], swap_xy=True)
    assert post.main(["--config", str(mini["config"])]) == 2
    assert "hors de grid.tif" in capsys.readouterr().err
    assert not (mini["zone"] / "sim" / "summary.parquet").exists()
    assert not (mini["zone"] / "sim" / post.STAGING).exists()


@pytest.mark.parametrize("trees,message", [
    ([*TREES, ("A", "09", 20.0, 15.0, 0, "alive")], "tree_id en double"),
    ([*TREES, ("Z", "99", 20.0, 15.0, 0, "alive")], "99"),
    ([*TREES, ("Z", "09", 0.0, 15.0, 0, "alive")], "d130 nul"),
])
def test_arbres_fautifs_refuses(mini, capsys, trees, message):
    write_sim(mini["zone"], mini["config"], trees=trees)
    assert post.main(["--config", str(mini["config"])]) == 2
    assert message in capsys.readouterr().err
    assert not (mini["zone"] / "sim" / "summary.parquet").exists()


def test_run_json_d_un_autre_reglage_refuse(mini, capsys):
    p = mini["zone"] / "sim" / "run.json"
    p.write_text(json.dumps({**json.loads(p.read_text()), "config_sha256": "0" * 64}), encoding="utf-8")
    assert post.main(["--config", str(mini["config"])]) == 2
    assert "diffère" in capsys.readouterr().err


def test_annee_manquante_refusee(mini, capsys):
    shutil.rmtree(mini["zone"] / "sim" / "trees" / "year=2023")
    assert post.main(["--config", str(mini["config"])]) == 2
    assert "incomplet" in capsys.readouterr().err
