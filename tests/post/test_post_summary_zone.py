"""sim/summary_zone.parquet sur la zone simulée : par (année, type de végétation, essence), totaux égaux à la somme des
cellules de summary, moyennes par hectare de surface forestière, flux de mortalité de l'année, part non calculée
(contrat post.summary_zone ; plan §2 et §4 ; BRIEF §4 « summary par biome et année »)."""
import math
from collections import defaultdict

import pytest

import helpers_post as P


@pytest.fixture(scope="module")
def zone(base_dir):
    return P.read_summary_zone(base_dir)


@pytest.fixture(scope="module")
def attendu(oracle):
    return oracle.zone()


@pytest.fixture(scope="module")
def sommes_cellules(base_dir, oracle):
    """Somme de summary × surface de la cellule, par (année, type, essence)."""
    out = defaultdict(lambda: defaultdict(float))
    for (c, y, sp), r in P.read_summary(base_dir).items():
        if c not in oracle.veg_of_cell:
            continue                      # cellule sans type de végétation : à part (voir helpers_post)
        k = (y, oracle.veg_of_cell[c], sp)
        for col in ("volume_m3_ha", "biomass_t_ha", "carbon_t_ha", "carbon_roots_t_ha"):
            if col in r:
                out[k][col] += r[col] * oracle.area
    return out


def proche(a, b, rel=P.TOL):
    return a is not None and b is not None and (math.isclose(float(a), float(b), rel_tol=rel, abs_tol=1e-9))


def test_une_ligne_par_annee_type_essence_vivante_ou_morte_dans_l_annee(zone, attendu):
    assert set(zone) == set(attendu), (f"en trop {sorted(set(zone) - set(attendu))[:5]}, "
                                       f"manquantes {sorted(set(attendu) - set(zone))[:5]}")


def test_aucun_type_de_vegetation_invente(zone, oracle):
    types = set(oracle.veg_of_cell.values())
    assert {k[1] for k in zone} <= types, sorted({k[1] for k in zone} - types)


def test_surface_forestiere_du_type(zone, attendu):
    faux = [(k, r["forest_area_ha"], attendu[k]["forest_area_ha"]) for k, r in zone.items()
            if k in attendu and not proche(r["forest_area_ha"], attendu[k]["forest_area_ha"])]
    assert not faux, faux[:3]


def test_totaux_egaux_a_la_somme_des_cellules(zone, sommes_cellules):
    faux = []
    for k, r in zone.items():
        s = sommes_cellules.get(k, {})
        for tot, col in (("volume_m3", "volume_m3_ha"), ("biomass_t", "biomass_t_ha"), ("carbon_t", "carbon_t_ha"),
                         ("carbon_roots_t", "carbon_roots_t_ha")):
            assert tot in r, f"colonne {tot} absente (le tarif porte les racines)" if tot == "carbon_roots_t" else tot
            if not proche(r[tot], s.get(col, 0.0)):
                faux.append((k, tot, r[tot], s.get(col, 0.0)))
    assert not faux, f"{len(faux)} écarts, ex. {faux[:3]}"


def test_volume_des_feuillus_recalcule_depuis_les_arbres(zone, attendu):
    faux = [(k, zone[k]["volume_m3"], e["volume_m3"]) for k, e in attendu.items()
            if e["volume_m3"] is not None and k in zone and not proche(zone[k]["volume_m3"], e["volume_m3"])]
    assert not faux, faux[:3]


def test_moyennes_par_hectare_de_surface_forestiere(zone):
    faux = []
    for k, r in zone.items():
        for tot, moy in (("volume_m3", "volume_m3_ha"), ("biomass_t", "biomass_t_ha"), ("carbon_t", "carbon_t_ha"),
                         ("carbon_roots_t", "carbon_roots_t_ha")):
            if tot in r and not proche(r[moy], r[tot] / r["forest_area_ha"]):
                faux.append((k, moy))
    assert not faux, faux[:5]


def test_flux_de_mortalite_de_l_annee(zone, attendu, oracle):
    assert any(e["dead_c"] + e["dead_nc"] for e in attendu.values()), "garde-fou : aucune mort en 5 ans"
    faux = []
    for k, e in attendu.items():
        r = zone.get(k)
        if r is None:
            continue
        dens, frac, _ = oracle.factors(k[2])
        if r["dead_stems_not_computed"] != e["dead_nc"]:
            faux.append((k, "dead_stems_not_computed", r["dead_stems_not_computed"], e["dead_nc"]))
        if e["dead_volume_m3"] is not None and not proche(r["dead_volume_m3"], e["dead_volume_m3"]):
            faux.append((k, "dead_volume_m3", r["dead_volume_m3"], e["dead_volume_m3"]))
        if (r["dead_volume_m3"] > 0) != (e["dead_c"] > 0):
            faux.append((k, "dead_volume_m3 > 0", r["dead_volume_m3"], e["dead_c"]))
        if not proche(r["dead_carbon_t"], r["dead_volume_m3"] * dens * frac):
            faux.append((k, "dead_carbon_t", r["dead_carbon_t"], r["dead_volume_m3"] * dens * frac))
    assert not faux, f"{len(faux)} écarts, ex. {faux[:3]}"


def test_les_morts_ne_sont_pas_dans_le_stock(zone, attendu):
    # une ligne qui n'a que des morts (aucun vivant) a un stock nul
    seuls_morts = [k for k, e in attendu.items() if e["n_alive"] == 0]
    for k in seuls_morts:
        r = zone[k]
        assert r["volume_m3"] == 0 and r["carbon_t"] == 0 and r["basal_area_not_computed_share"] == 0, k


def test_tiges_et_part_non_calculees(zone, attendu):
    faux = []
    for k, e in attendu.items():
        r = zone.get(k)
        if r is None:
            continue
        if r["stems_not_computed"] != e["stems_nc"]:
            faux.append((k, "stems_not_computed", r["stems_not_computed"], e["stems_nc"]))
        if abs(r["basal_area_not_computed_share"] - e["share"]) > 1e-9:
            faux.append((k, "part", r["basal_area_not_computed_share"], e["share"]))
    assert not faux, f"{len(faux)} écarts, ex. {faux[:3]}"


def test_provisoire_partout(zone):
    assert zone and all(r["provisoire"] is True for r in zone.values())
