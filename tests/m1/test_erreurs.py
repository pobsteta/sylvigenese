"""Cas du terrain : entrée absente, hors référentiel, doublon, date incohérente, x/y inversés.

Chaque cas travaille sur une copie du jeu fictif sous data/m1_<cas>/ (hors dépôt, supprimée
ensuite). prepare est appelé comme le Makefile pour lire son vrai code de sortie (make renvoie
toujours 2) : spec §3 et §6, « entrée refusée » = code 2, message en français, aucune sortie
produite à moitié (signaler plutôt que deviner).
"""
import sqlite3
import struct

import pytest

import helpers as H


def _sql(path, req, *args):
    c = sqlite3.connect(path)
    c.execute(req, args)
    c.commit()
    c.close()


def _sans_h_pot(d):
    (d / "inputs" / "h_pot.tif").unlink()


def _essence_entier(d):
    _sql(d / "inputs" / "nemeton_stands.gpkg", "update stands set species_espar='9' where stand_id='S01'")


def _essence_hors_referentiel(d):
    _sql(d / "inputs" / "nemeton_stands.gpkg", "update stands set species_espar='ZZZ99' where stand_id='S01'")


def _date_impossible(d):
    _sql(d / "inputs" / "lidar_tiles.gpkg", "update lidar_tiles set flight_date='2022-02-30' where fid=1")


def _doublon(d):
    c = sqlite3.connect(d / "inputs" / "nemeton_stands.gpkg")
    c.execute("insert into stands (geom, stand_id, species_espar, dbh_cm, height_m, density_ha, age_yr, "
              "source, stand_id_source) select geom, stand_id, species_espar, dbh_cm, height_m, "
              "density_ha, age_yr, source, stand_id_source from stands where stand_id='S02'")
    c.commit()
    c.close()


def _saisie_incomplete(d):
    _sql(d / "inputs" / "nemeton_stands.gpkg", "update stands set species_espar=NULL where stand_id='S03'")


def _xy_inverses(d):
    c = sqlite3.connect(d / "inputs" / "nemeton_stands.gpkg")
    (blob,) = c.execute("select geom from stands where stand_id='S01'").fetchone()
    x0, x1, y0, y1 = struct.unpack("<4d", blob[8:40])
    neuf = H._rect_blob(y0, y1, x0, x1)  # x et y échangés : Somalie
    c.execute("update stands set geom=? where stand_id='S01'", (neuf,))
    c.commit()
    c.close()


CAS = {
    "h_pot_absent": _sans_h_pot,                    # spec §3 : « S'il manque : erreur, code 2 »
    "essence_entier_sans_zero": _essence_entier,    # "9" au lieu de "09"
    "essence_hors_referentiel": _essence_hors_referentiel,
    "date_de_vol_impossible": _date_impossible,
    "stand_id_en_double": _doublon,
    "essence_manquante": _saisie_incomplete,
    "x_y_inverses_somalie": _xy_inverses,
}


@pytest.fixture(scope="module", params=list(CAS))
def refus(request):
    nom = "m1_" + request.param
    try:
        d, cfg = H.make_zone_copy(nom, CAS[request.param])
        p = H.run_module_status("prepare", cfg)
        yield request.param, d, p
    finally:
        H.remove_zone_copy(nom)


FICHIER_CITE = {"h_pot_absent": "h_pot", "date_de_vol_impossible": "lidar_tiles"}


def test_entree_refusee_donne_le_code_2_et_un_message_qui_nomme_le_fichier(refus):
    nom, d, p = refus
    assert p.returncode == 2, f"{nom} : code {p.returncode} (attendu 2)\n{p.stderr[-1200:]}"
    assert p.stderr.strip(), f"{nom} : aucun message d'erreur"
    fichier = FICHIER_CITE.get(nom, "nemeton_stands")
    assert fichier in p.stderr, f"{nom} : le message ne nomme pas {fichier}\n{p.stderr[-800:]}"


def test_entree_refusee_ne_laisse_aucune_sortie_a_moitie(refus):
    nom, d, p = refus
    produits = [f for f in ("grid.tif", "h0.tif", "ser.tif", "stands.parquet", "trees_init")
                if (d / f).exists()]
    assert not produits, f"{nom} : sorties écrites malgré le refus : {produits}"
