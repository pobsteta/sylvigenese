"""h_dom_m dans sim/cells (décision de Pascal Q1 du 25/11/2026 ; mission 046 ; contrat sim.cells précisé le 25/11) :
  - une ligne n'existe que pour un couple (cellule, essence) qui a au moins un arbre vivant à la fin de l'année ;
    une cellule sans arbre vivant n'a donc AUCUNE ligne (aucune n'est exigée) ;
  - h_dom_m est présent sur chaque ligne, identique entre les essences d'une même cellule et d'une même année,
    et non null quand la cellule a des arbres vivants (donc sur toute ligne) ;
  - h_dom_m n'est jamais corrigé au plafond : la valeur d'un signalement hdom_au_dessus_du_plafond est la sienne.
Rejoue la chaîne de 100 ans de conftest (fixture `chaine`), sans simulation de plus."""
import math

import numpy as np
import pyarrow.parquet as pq
import pytest

import helpers_m3 as H

T0 = H.SIM_NOMINAL["t0"]
ANNEES = H.SIM_NOMINAL["years"]


@pytest.fixture(scope="module")
def cellules(chaine):
    t = H.dataset(chaine["dir"], "cells").to_table()
    assert t.num_rows > 0, "sim/cells vide"
    return H.Tab.from_arrow(t)


def test_chaque_fichier_de_sim_cells_porte_la_colonne_h_dom_m(chaine):
    parts = H.partitions(chaine["dir"], "cells")
    assert sorted(parts) == list(range(T0, T0 + ANNEES + 1))
    sans = [str(f.relative_to(chaine["dir"])) for fs in parts.values() for f in fs if "h_dom_m" not in pq.read_schema(f).names]
    assert not sans, f"{len(sans)} fichiers de sim/cells sans h_dom_m, ex. {sans[:3]}"


def test_h_dom_m_n_est_jamais_null_ni_negatif_sur_une_ligne(cellules):
    assert "h_dom_m" in cellules.names
    v = cellules["h_dom_m"].astype("float64")
    assert not np.isnan(v).any(), f"{int(np.isnan(v).sum())} lignes à h_dom_m null alors que la cellule a des arbres vivants"
    assert np.isfinite(v).all() and (v >= 0).all()


def test_h_dom_m_est_le_meme_pour_toutes_les_essences_d_une_cellule_et_d_une_annee(cellules):
    t = cellules.order("year", "cell_id")
    cle = t["year"].astype(np.int64) * 10_000_000 + t["cell_id"].astype(np.int64)
    v = t["h_dom_m"].astype("float64")
    _, debut, inv = np.unique(cle, return_index=True, return_inverse=True)
    ecart = np.abs(v - v[debut][inv])
    assert (ecart == 0).all(), f"{int((ecart > 0).sum())} lignes dont h_dom_m diffère de celui de leur cellule et année"
    assert (np.bincount(inv) > 1).any(), "aucune cellule à plusieurs essences : test sans pouvoir"


@pytest.mark.parametrize("annee", [T0, T0 + 1, T0 + 50, T0 + ANNEES])
def test_une_ligne_par_cellule_et_essence_qui_a_un_arbre_vivant_et_seulement_celles_la(chaine, arbres, grid, cellules, annee):
    a = arbres.where((arbres["year"] == annee) & (arbres["status"] == "alive"))
    cid = grid.cell_id(a["x"], a["y"])
    attendu = {(int(c), str(s)) for c, s in zip(cid, a["species"])}
    c = cellules.where(cellules["year"] == annee)
    lu = {(int(i), str(s)) for i, s in zip(c["cell_id"], c["species"])}
    assert lu - attendu == set(), f"{annee} : {len(lu - attendu)} lignes sans arbre vivant, ex. {sorted(lu - attendu)[:3]}"
    assert attendu - lu == set(), f"{annee} : {len(attendu - lu)} couples (cellule, essence) vivants sans ligne"


def test_une_cellule_sans_arbre_vivant_n_a_pas_de_ligne(chaine, arbres, grid, cellules):
    # Une trouée sans recrue (décision de Pascal) n'a aucun arbre : elle ne doit avoir aucune ligne, et pas de h_dom_m inventé.
    fl = H.Tab.from_arrow(pq.read_table(chaine["dir"] / "sim" / "flags.parquet"))
    tr = fl.where(fl["kind"] == "trouee_sans_recrue")
    assert len(tr) > 0, "aucune trouée signalée : test sans pouvoir"
    annee = int(tr["year"][0])
    vides = {int(e) for e, y in zip(tr["entity"], tr["year"]) if int(y) == annee}
    a = arbres.where((arbres["year"] == annee) & (arbres["status"] == "alive"))
    avec = set(map(int, grid.cell_id(a["x"], a["y"])))
    vides -= avec
    assert vides, "trouées signalées toutes peuplées : test sans pouvoir"
    lignes = set(map(int, cellules.where(cellules["year"] == annee)["cell_id"]))
    assert not (vides & lignes), f"{annee} : cellules sans arbre vivant avec une ligne : {sorted(vides & lignes)[:5]}"


def test_h_dom_m_n_est_pas_corrige_au_plafond(chaine, grid, cellules):
    """Une cellule signalée hdom_au_dessus_du_plafond (flags.parquet) garde un h_dom_m au-dessus du plafond de sa station
    (site_potential.tif) : la hauteur est signalée, jamais ramenée au plafond (CLAUDE.md). On ne compare pas h_dom_m à la
    valeur du signalement : l'instant où simulate la relève (avant ou après le pas) n'est pas fixé par le contrat."""
    fl = H.Tab.from_arrow(pq.read_table(chaine["dir"] / "sim" / "flags.parquet"))
    f = fl.where(fl["kind"] == "hdom_au_dessus_du_plafond")
    assert len(f) > 0
    plafond = grid.raster("site_potential")
    hd = {(int(y), int(c)): float(h) for y, c, h in zip(cellules["year"], cellules["cell_id"], cellules["h_dom_m"])}
    faux, vus = [], 0
    for y, e in zip(f["year"], f["entity"]):
        k = (int(y), int(e))
        if k not in hd:
            continue
        vus += 1
        p = float(plafond[divmod(k[1], grid.ncols)])
        if not hd[k] > p:
            faux.append((k, hd[k], p))
    assert vus > 0, "aucune cellule signalée n'a de ligne dans sim/cells"
    assert not faux, f"{len(faux)} cellules signalées au-dessus du plafond dont h_dom_m <= plafond, ex. {faux[:3]}"
