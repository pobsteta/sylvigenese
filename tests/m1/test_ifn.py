"""Tables IFN de prepare (spec §6, §8 ; docs/referentiels/ifn-placettes.md)."""
import csv
import math
from collections import defaultdict

import pytest

import helpers as H


def _csv(name):
    with open(H.INPUTS / "ifn" / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


@pytest.fixture(scope="module")
def plots(runs):
    return H.read_parquet(H.ZONE / "ifn" / "plots.parquet")


def test_plots_une_ligne_par_placette_aux_coordonnees_floutees_inchangees(plots):
    src = _csv("PLACETTE.csv")
    assert len(plots) == len(src) == 40
    par_id = {str(r["plot_id"]): r for r in plots}
    for s in src:
        p = par_id[s["IDP"]]
        # Coordonnées recopiées telles quelles : jamais recalées sur un raster (garde IFN).
        assert p["x"] == pytest.approx(float(s["XL"]), abs=1e-6)
        assert p["y"] == pytest.approx(float(s["YL"]), abs=1e-6)
        assert p["campaign"] == int(s["CAMPAGNE"])


def test_plots_precision_de_localisation_jamais_fine(plots):
    # Floutage IFN d'environ 700 m ; seuil de la garde : 25 m.
    for p in plots:
        assert p["loc_precision_m"] is not None and p["loc_precision_m"] > 25, p["plot_id"]
        assert p["source"] == "ifn", (p["plot_id"], p["source"])


def test_plots_ser_code_est_null_en_m1a_et_jamais_une_alluvion(plots):
    # Règle attendue en M1a (à relire si elle change) : la placette IFN est floutée (~700 m) et ne
    # se croise pas avec ser.tif, raster fin (garde IFN, CLAUDE.md) : ser_code est donc NULL pour
    # toutes les placettes. S'il était renseigné, il ne serait jamais un code L1-L5 (spec §3).
    # Ce test vérifie la règle NULL ; il n'est pas une preuve de rattachement des alluvions.
    non_null = [(p["plot_id"], p["ser_code"]) for p in plots if p["ser_code"] is not None]
    assert not non_null, f"ser_code renseigné pour des placettes IFN floutées : {non_null[:5]}"


def test_jeu_fictif_contient_des_arbres_exactement_a_705_et_1175_mm():
    c13 = {int(s["C13"]) for s in _csv("ARBRE.csv")}
    assert 705 in c13 and 1175 in c13, "le jeu fictif n'a pas d'arbre aux seuils 705 et 1175 mm"


def _rayon(c13_mm):
    """IMOT 2025 p. 61 (tableau DIMESS), sur C13 en mm : < 705 -> 6 m ; 705 à < 1175 -> 9 m ;
    >= 1175 -> 15 m. 705 et 1175 passent à la classe supérieure."""
    return 6 if c13_mm < 705 else 9 if c13_mm < 1175 else 15


def test_rayon_aux_seuils_705_et_1175():
    assert [_rayon(x) for x in (704, 705, 1174, 1175)] == [6, 9, 9, 15]


def test_arbres_d130_depuis_c13_en_mm_et_poids_par_cercle():
    # d130 = c13 / (10 pi) cm ; cercles selon C13 en mm (IMOT 2025 p. 61, tableau DIMESS) ;
    # weight_ha = 10000 / (pi R^2). La colonne W du CSV n'est pas la référence (l'IMOT fait foi).
    rows = H.read_parquet(H.ZONE / "ifn" / "trees.parquet")
    src = _csv("ARBRE.csv")
    assert len(rows) == len(src) == 386
    attendu = defaultdict(list)
    for s in src:
        c13 = float(s["C13"])
        w = round(1e4 / (math.pi * _rayon(c13) ** 2), 2)
        attendu[s["IDP"]].append((s["ESPAR"], round(c13 / (10 * math.pi), 3), w))
    obtenu = defaultdict(list)
    for r in rows:
        obtenu[str(r["plot_id"])].append((r["species"], round(r["d130"], 3), round(r["weight_ha"], 2)))
    assert set(obtenu) == set(attendu)
    for k in attendu:
        a, o = sorted(attendu[k], key=lambda t: t[:2]), sorted(obtenu[k], key=lambda t: t[:2])
        assert len(a) == len(o), k
        for (ea, da, wa), (eo, do, wo) in zip(a, o):
            assert ea == eo and isinstance(eo, str)
            assert do == pytest.approx(da, abs=0.01)
            assert wo == pytest.approx(wa, rel=0.005), (k, eo, do, wo, wa)


def test_poids_exacts_aux_seuils_705_et_1175_mm():
    rows = H.read_parquet(H.ZONE / "ifn" / "trees.parquet")
    for c13, poids in ((705, 39.30), (1175, 14.15)):
        d = c13 / (10 * math.pi)
        r = [x for x in rows if abs(x["d130"] - d) < 0.01]
        assert r, f"aucun arbre à C13 = {c13} mm dans ifn/trees.parquet"
        for x in r:
            assert x["weight_ha"] == pytest.approx(poids, abs=0.01), (c13, x["weight_ha"])


def test_flore_une_ligne_par_releve():
    rows = H.read_parquet(H.ZONE / "ifn" / "flora.parquet")
    src = _csv("FLORE.csv")
    assert len(rows) == len(src) == 174
    a = sorted((s["IDP"], int(s["CD_REF"]), int(s["ABOND"])) for s in src)
    o = sorted((str(r["plot_id"]), int(r["cd_ref"]), int(r["abundance"])) for r in rows)
    assert a == o
