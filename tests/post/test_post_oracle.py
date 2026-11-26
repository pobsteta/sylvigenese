"""Garde-fous de l'oracle (mission 052) : l'outil qui juge post est lui-même vérifié, à la calculette, sur le tarif
synthétique versionné. Ces tests ne lancent rien : ils sont verts avant comme après la mission 053."""
import math

import numpy as np

import helpers_post as P

H = P.H
TARIF = P.Tarif(H.ZONE / "params" / "tarif.parquet")


def test_le_tarif_synthetique_est_conforme_au_contrat():
    p = H.validate("import_tarif.tarif", str(H.ZONE / "params" / "tarif.parquet"))
    assert p.returncode == 0, p.stdout + p.stderr


def test_le_tarif_synthetique_porte_les_sept_modeles_et_un_seul_commit():
    assert TARIF.models == {"volume_feuillus", "profil_tige_resineux", "expansion_resineux", "infradensite",
                            "fraction_carbone", "racines", "domaine"}
    assert TARIF.commits == {"0000000"}
    assert all(r["provisoire"] is True for r in TARIF.rows)


def test_volume_d_un_hetre_de_40_cm_et_20_m_a_la_calculette():
    # π/4 · 0,40² · 20 = 2,513274 m³ ; exposant -0,30 + 0,05 ln(40/30) + 0,10 ln(20/25) = -0,307930 ; exp = 0,734964
    v = TARIF.volume_feuillus("09", 40.0, 20.0)
    assert math.isclose(v, 2.5132741228718345 * math.exp(-0.30 + 0.05 * math.log(4 / 3) + 0.10 * math.log(0.8)), rel_tol=1e-12)
    assert math.isclose(v, 1.847172, rel_tol=1e-6)


def test_volume_au_diametre_et_a_la_hauteur_de_reference_vaut_le_cylindre_fois_exp_a():
    v = TARIF.volume_feuillus("03", 30.0, 25.0)
    assert math.isclose(v, math.pi / 4 * 0.09 * 25 * math.exp(-0.25), rel_tol=1e-12)


def test_biomasse_carbone_et_racines_par_groupe():
    assert TARIF.density_t_m3("09") == 0.3 and TARIF.density_t_m3("61") == 0.35
    assert TARIF.carbon_fraction("03") == 0.30 and TARIF.carbon_fraction("64") == 0.35
    assert TARIF.roots_ratio("09") == 0.10 and TARIF.roots_ratio("62") == 0.15


def test_raisons_hors_domaine_dans_l_ordre_du_contrat():
    assert TARIF.reason("09", 40.0, 20.0) is None
    assert TARIF.reason("09", 7.5, 12.0) == "dbh_below"            # recrue
    assert TARIF.reason("09", 10.0, 3.0) is None                   # bornes fermées
    assert TARIF.reason("03", 12.0, 14.0) == "dbh_below"           # chêne sous 12,5 cm
    assert TARIF.reason("03", 12.5, 14.0) is None
    assert TARIF.reason("03", 105.0, 30.0) == "dbh_above"
    assert TARIF.reason("61", 10.0, 21.0) == "hd_above"            # H/D = 210
    assert TARIF.reason("64", 10.5, 2.9) == "h_below"              # avant hd_below
    assert TARIF.reason("62", 20.0, 55.0) == "h_above"             # avant hd_above
    assert TARIF.reason("09", 10.0, 21.0) is None                  # feuillus : H/D non borné (terme absent)
    assert TARIF.reason("02", 30.0, 25.0) == "without_tarif"       # pas d'emprunt de Quercus_spec (03)
    assert TARIF.reason("05", 30.0, 25.0) == "without_tarif"


def test_le_point_connu_tombe_dans_la_cellule_0_et_pas_ailleurs():
    x, y = P.POINT_CONNU
    assert H.cell_of(x, y) == (0, 0)
    assert int(P.cell_ids(np.array([x]), np.array([y]))[0]) == 0
    # latitude et longitude inversées : le point sort de la grille de 40 x 40 cellules
    r, c = H.cell_of(y, x)
    assert not (0 <= r < H.NROWS and 0 <= c < H.NCOLS)


def test_le_point_connu_est_en_france_et_pas_en_somalie():
    # EPSG:2154 relu en Lambert-93 : environ 3,2° E, 45,6° N ; pris pour des degrés (ou inversé), on tomberait ailleurs
    lon, lat = H.lambert93_inverse(np.array([P.POINT_CONNU[0]]), np.array([P.POINT_CONNU[1]]))
    lon, lat = float(np.ravel(lon)[0]), float(np.ravel(lat)[0])
    assert -5.5 < lon < 10.0 and 41.0 < lat < 51.5, (lon, lat)
    assert not (40.0 < lon < 52.0 and -2.0 < lat < 12.0), "Somalie"


def test_la_surface_d_une_cellule_vient_de_config():
    assert P.cell_area_ha(H.ROOT / "config.yml") == 0.0625


def test_l_echantillon_a_un_arbre_au_point_connu_et_des_codes_du_referentiel():
    sp = H.species_group()
    assert all(t[1] in sp for t in P.MINI_TREES), "essence hors de contracts/species.csv dans l'échantillon"
    assert P.MINI_TREES[0][4] == 0 and P.MINI_TREES[0][5] == 0.0
    assert len({t[0] for t in P.MINI_TREES}) == len(P.MINI_TREES)
