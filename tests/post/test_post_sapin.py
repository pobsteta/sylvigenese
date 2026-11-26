"""Le sapin calculé exactement (mission 057, reprise de la relecture de la PR n° 10 : « volume des résineux non tenu
par les tests, 2 mutations non détectées »).

Oracle : helpers_post.resineux_synthetique, écrit depuis la SEULE formule du contrat params/tarif (forme synthétique
du jeu fictif, mission 053) : tige = π/4 · (D/100)² · H · (synth_p1 + synth_p2 / 2), V aérien = tige × synth_E,
biomasse = V × infradensité / 1000, carbone = biomasse × fraction, racines = carbone × rapport. Les termes sont lus
dans params/tarif.parquet, jamais recopiés ici, sauf les valeurs « à la calculette » qui contrôlent l'oracle lui-même.

Zones :
  - `post_sapin` : la zone échantillon (helpers_post.MINI_TREES, 2022 et 2023), où l'arbre du point connu
    (est 700 012,5 ; nord 6 500 987,5, EPSG:2154, cellule 0) est un sapin (61) de 40 cm et 20 m au lieu d'un hêtre ;
    rien d'autre ne change. Aucune année simulée : sim/ est écrit par l'aide de test.
  - `post_base` (zone simulée de 5 ans de conftest.py) : chaque ligne de résineux du summary est refaite arbre par arbre.
Ce test échoue si la forme est faussée (synth_p2/3 au lieu de /2, p1 et p2 échangés, E oublié…) : voir
test_l_oracle_distingue_chaque_forme_fausse, qui le prouve sans toucher au code de post."""
import math

import numpy as np
import pytest

import helpers_post as P
from conftest import build_ech, exige

H = P.H
AIRE = 0.0625
ANNEES = P.MINI_YEARS
SAPIN = ("61", 40.0, 20.0)       # essence, d130 cm, h m : H/D = 50, dans le domaine [30 ; 200] du tarif synthétique
TARIF_VERSIONNE = P.Tarif(H.ZONE / "params" / "tarif.parquet")
REL = 1e-9


def proche(a, b, rel=REL):
    return a is not None and b is not None and math.isclose(float(a), float(b), rel_tol=rel, abs_tol=1e-12)


def _sapin_au_point(year, rows):
    out = []
    for r in rows:
        r = dict(r)
        if r["tree_id"] == "TPA":
            r["species"], r["d130"], r["h"] = SAPIN
        out.append(r)
    assert (out[0]["x"], out[0]["y"]) == P.POINT_CONNU and out[0]["species"] == "61"
    return out


@pytest.fixture(scope="module")
def sapin(ech):
    exige(ech, "post")
    try:
        yield build_ech("post_sapin", rows=_sapin_au_point)
    finally:
        P.remove_zone("post_sapin")


@pytest.fixture(scope="module")
def sapin_summary(sapin):
    exige(sapin, "post")
    return P.read_summary(sapin["dir"])


@pytest.fixture(scope="module")
def attendu():
    t = P.Tarif(H.ZONE / "params" / "tarif.parquet")
    return P.resineux_synthetique(t, *SAPIN)


# ------------------------------------------------------------------ l'oracle, contrôlé à la calculette (vert sans post)
def test_l_oracle_refait_l_exemple_du_contrat():
    # contrat params/tarif : sapin de 30 cm et 25 m, p1 0,40, p2 0,60, E 1,10 : tige 1,23700 m³, aérien 1,36070 m³
    v = P.resineux_synthetique(TARIF_VERSIONNE, "61", 30.0, 25.0)["volume_m3"]
    assert math.isclose(v / 1.10, 1.23700, abs_tol=5e-6), v / 1.10
    assert math.isclose(v, 1.36070, abs_tol=5e-6), v


def test_l_oracle_du_sapin_du_point_connu_a_la_calculette(attendu):
    # π/4 · 0,40² · 20 = 2,5132741 m³ ; × (0,40 + 0,60 / 2) = 1,7592919 ; × 1,10 = 1,9352211 m³
    v = math.pi / 4 * 0.16 * 20 * 0.70 * 1.10
    assert math.isclose(attendu["volume_m3"], v, rel_tol=1e-12) and math.isclose(v, 1.9352211, rel_tol=1e-7)
    assert math.isclose(attendu["biomass_t"], v * 0.350, rel_tol=1e-12)          # infradensité des résineux
    assert math.isclose(attendu["carbon_t"], v * 0.350 * 0.35, rel_tol=1e-12)    # fraction des résineux
    assert math.isclose(attendu["carbon_roots_t"], v * 0.350 * 0.35 * 0.15, rel_tol=1e-12)


@pytest.mark.parametrize("forme", sorted(set(P.FORMES_RESINEUX) - {"contrat"}))
def test_l_oracle_distingue_chaque_forme_fausse(attendu, forme):
    """Preuve de détection sans toucher à post : une forme fausse donne un volume, une biomasse et un carbone qui
    sortent de la tolérance du test exact (1e-9 relatif) d'au moins 1 %."""
    faux = P.resineux_synthetique(TARIF_VERSIONNE, *SAPIN, forme=forme)
    for k in ("volume_m3", "biomass_t", "carbon_t"):
        assert not proche(faux[k], attendu[k]), f"{forme} : {k} non distingué"
        assert abs(faux[k] / attendu[k] - 1) > 0.01, f"{forme} : {k} trop proche ({faux[k]} contre {attendu[k]})"


def test_l_oracle_refuse_un_feuillu_et_une_essence_sans_forme():
    with pytest.raises(AssertionError):
        P.resineux_synthetique(TARIF_VERSIONNE, "09", 40.0, 20.0)       # hêtre : feuillu
    with pytest.raises(AssertionError):
        P.resineux_synthetique(TARIF_VERSIONNE, "52", 40.0, 20.0)       # pin sylvestre : pas de ligne de tarif


# ------------------------------------------------------------------ le sapin du point connu, dans le summary de post
def test_le_sapin_est_dans_le_domaine_du_tarif():
    assert TARIF_VERSIONNE.reason(*SAPIN) is None


def test_post_aboutit_sur_la_zone_du_sapin(sapin):
    assert sapin["post"].returncode == 0, P.queue(sapin["post"])


@pytest.mark.parametrize("annee", ANNEES)
def test_sapin_du_point_connu_volume_biomasse_carbone_exacts(sapin_summary, attendu, annee):
    k = (0, annee, "61")
    assert k in sapin_summary, f"pas de ligne {k} dans sim/summary.parquet ; lignes : {sorted(sapin_summary)}"
    r = sapin_summary[k]
    assert proche(r["volume_m3_ha"], attendu["volume_m3"] / AIRE), \
        f"volume {r['volume_m3_ha']} ; attendu {attendu['volume_m3'] / AIRE} m³/ha (30,96354)"
    assert proche(r["biomass_t_ha"], attendu["biomass_t"] / AIRE), (r["biomass_t_ha"], attendu["biomass_t"] / AIRE)
    assert proche(r["carbon_t_ha"], attendu["carbon_t"] / AIRE), (r["carbon_t_ha"], attendu["carbon_t"] / AIRE)


@pytest.mark.parametrize("annee", ANNEES)
def test_sapin_du_point_connu_racines_a_part_et_exactes(sapin_summary, attendu, annee):
    r = sapin_summary.get((0, annee, "61"))
    assert r is not None, "ligne du sapin absente"
    assert "carbon_roots_t_ha" in r, "le tarif porte le modèle racines : carbon_roots_t_ha attendu"
    assert proche(r["carbon_roots_t_ha"], attendu["carbon_roots_t"] / AIRE), r["carbon_roots_t_ha"]
    assert proche(r["carbon_t_ha"], attendu["carbon_t"] / AIRE), "racines ajoutées au carbone aérien"
    assert r["provisoire"] is True


@pytest.mark.parametrize("annee", ANNEES)
def test_sapin_du_point_connu_entierement_calcule(sapin_summary, annee):
    r = sapin_summary.get((0, annee, "61"))
    assert r is not None, "ligne du sapin absente"
    assert r["basal_area_not_computed_share"] == 0 and r["stems_not_computed_ha"] == 0, r


@pytest.mark.parametrize("annee", ANNEES)
def test_sapin_mesure_contre_chaque_forme_fausse(sapin_summary, annee):
    """Le volume lu ne correspond à AUCUNE forme fausse : si post en codait une, ce test et le test exact rougiraient."""
    r = sapin_summary.get((0, annee, "61"))
    assert r is not None, "ligne du sapin absente"
    for forme in sorted(set(P.FORMES_RESINEUX) - {"contrat"}):
        faux = P.resineux_synthetique(TARIF_VERSIONNE, *SAPIN, forme=forme)["volume_m3"] / AIRE
        assert not proche(r["volume_m3_ha"], faux), f"post semble coder la forme fausse « {forme} »"


def test_le_sapin_tombe_dans_la_cellule_0_et_pas_ailleurs(sapin_summary, sapin):
    # latitude et longitude inversées, ou ligne et colonne échangées : le sapin du point quitterait la cellule 0
    cells = P.mini_cells(sapin["dir"])
    assert {c for (c, _, sp) in sapin_summary if sp == "61"} == {0, cells[2]}, sorted(sapin_summary)
    assert {c for (c, _, _) in sapin_summary} <= set(cells), "ligne pour une cellule sans arbre"
    lon, lat = H.lambert93_inverse(np.array([P.POINT_CONNU[0]]), np.array([P.POINT_CONNU[1]]))
    lon, lat = float(np.ravel(lon)[0]), float(np.ravel(lat)[0])
    assert -5.5 < lon < 10.0 and 41.0 < lat < 51.5 and not (40.0 < lon < 52.0 and -2.0 < lat < 12.0), (lon, lat)


def test_le_reste_de_la_cellule_0_est_inchange(sapin_summary):
    # la recrue de 7,5 cm (09) reste hors domaine, seule de son essence : part 1, rien de calculé
    for annee in ANNEES:
        r = sapin_summary.get((0, annee, "09"))
        assert r is not None, (0, annee, "09")
        assert r["volume_m3_ha"] == 0 and r["basal_area_not_computed_share"] == 1.0, r


def test_les_codes_du_summary_du_sapin_sont_au_referentiel(sapin_summary):
    sp = H.species_group()
    assert {k[2] for k in sapin_summary} <= set(sp), "essence hors de contracts/species.csv"


# ------------------------------------------------------------------ zone simulée : chaque résineux refait arbre par arbre
def test_chaque_ligne_de_resineux_de_la_zone_simulee_est_exacte(base_dir, oracle):
    tr, t = oracle.trees, oracle.tarif
    att: dict = {}
    for i in np.nonzero(oracle.alive & oracle.computed)[0]:
        sp = str(tr["species"][i])
        if t.group(sp) != "resineux":
            continue
        v = P.resineux_synthetique(t, sp, float(tr["d130"][i]), float(tr["h"][i]))
        e = att.setdefault((int(oracle.cell[i]), int(tr["year"][i]), sp), dict.fromkeys(("v", "b", "c"), 0.0))
        e["v"] += v["volume_m3"]
        e["b"] += v["biomass_t"]
        e["c"] += v["carbon_t"]
    assert att, "garde-fou : la zone simulée doit avoir des résineux calculés"
    lu = P.read_summary(base_dir)
    faux = []
    for k, e in att.items():
        r = lu.get(k)
        if r is None:
            faux.append((k, "ligne absente"))
            continue
        for col, x in (("volume_m3_ha", e["v"]), ("biomass_t_ha", e["b"]), ("carbon_t_ha", e["c"])):
            if not proche(r[col], x / oracle.area):
                faux.append((k, col, r[col], x / oracle.area))
    # une ligne de résineux sans arbre calculé vaut 0
    for k, r in lu.items():
        if t.group(k[2]) == "resineux" and k not in att and r["volume_m3_ha"] != 0:
            faux.append((k, "aucun arbre calculé, volume non nul", r["volume_m3_ha"]))
    assert not faux, f"{len(faux)} écarts sur {len(att)} lignes de résineux, ex. {faux[:4]}"

