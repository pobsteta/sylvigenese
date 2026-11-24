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


def test_plots_ser_sous_jacente_jamais_une_alluvion(plots):
    for p in plots:
        assert p["ser_code"] is None or not H.L_CODE.match(p["ser_code"]), p


def test_arbres_d130_depuis_c13_en_mm_et_poids_par_cercle():
    # d130 = c13 / (10 pi) cm ; cercles 6, 9, 15 m selon la classe (IMOT 2025 p. 61) :
    # d130 < 22,5 cm -> 6 m ; 22,5 <= d130 < 37,5 -> 9 m ; >= 37,5 -> 15 m (l'IMOT fait foi, pas la colonne W). weight_ha = 10000 / (pi R^2).
    rows = H.read_parquet(H.ZONE / "ifn" / "trees.parquet")
    src = _csv("ARBRE.csv")
    assert len(rows) == len(src) == 386
    attendu = defaultdict(list)
    for s in src:
        c13 = float(s["C13"])
        d130 = c13 / (10 * math.pi)
        r = 6 if d130 < 22.5 else 9 if d130 < 37.5 else 15  # IMOT : 705 mm -> 6 m, 1175 mm -> 9 m
        w = round(1e4 / (math.pi * r * r), 2)
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


def test_flore_une_ligne_par_releve():
    rows = H.read_parquet(H.ZONE / "ifn" / "flora.parquet")
    src = _csv("FLORE.csv")
    assert len(rows) == len(src) == 174
    a = sorted((s["IDP"], int(s["CD_REF"]), int(s["ABOND"])) for s in src)
    o = sorted((str(r["plot_id"]), int(r["cd_ref"]), int(r["abundance"])) for r in rows)
    assert a == o
