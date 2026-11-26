"""Dispersion des graines (plan m5a, missions C et D ; spec §7 ; contrat params/regeneration, noyau
k(r) ∝ exp(−(r / kernel_scale_m)^kernel_shape), r entre centres de cellules, tronqué à kernel_truncation_cells).

Une source de coordonnées connues (est 700 012,5 ; nord 6 500 987,5 ; EPSG:2154) : la seule cellule semencière de la
SER fictive est celle qui contient ce point ; l'origine de la grille est choisie pour qu'il soit le centre de la
cellule (ligne, colonne). Deux cas :
  - « diagonale » : (12, 12) ; une transposition des axes y laisserait la source en place ;
  - « asymetrique » : (7, 16) ; transposée, la source passerait en (16, 7), loin de la fenêtre attendue : c'est ce
    cas qui détecte une FFT qui transpose la grille (risque du plan m5a §6). Ligne 0 au nord, x vers l'est.
Les deux fenêtres restent à plus de K cellules des bords (la zone tampon n'y joue pas).

Au bout d'un an (flux IFN quasi nul, donc aucun semis « en régime » notable ; lumière uniforme, survie 1) :
  - aucune cellule hors du carré de demi-largeur K autour de la source n'a de semis ;
  - toute cellule à moins de K cellules (distance euclidienne) de la source en a ;
  - le barycentre des semis est le centre de la cellule source ;
  - les semis sont proportionnels au noyau du contrat k(r), à 1e-6 près en relatif (lumière et installation
    uniformes : seule la distance change)."""
import numpy as np
import pytest

import helpers_m5 as H
import ser_fictive as G


def _ok(r):
    assert r["proc"].returncode == 0, H.queue(r["proc"])


@pytest.fixture(scope="module")
def semis(ser_source):
    return H.Paresseux(lambda: _semis(ser_source))


def _semis(ser_source):
    _ok(ser_source)
    r = ser_source
    g = H.H3.Grid(r["dir"])
    assert H.cellule_du_point(g, H.SOURCE_EST, H.SOURCE_NORD) == (r["row"], r["col"]), "précondition : point connu"
    c = H.read_kind(r["dir"], "cells")
    assert "seedlings_ha" in c.names, "sim/cells sans seedlings_ha en mode cohorts"
    y = H.T0 + 1
    m = (c["year"] == y) & (c["species"] == "03")
    a = np.zeros((g.nrows, g.ncols))
    ids = c["cell_id"][m].astype(int)
    a[ids // g.ncols, ids % g.ncols] = np.nan_to_num(c["seedlings_ha"][m].astype("float64"))
    return {**r, "grid": g, "semis": a}


def _distances(s):
    ii, jj = np.meshgrid(np.arange(s["grid"].nrows), np.arange(s["grid"].ncols), indexing="ij")
    return ii - s["row"], jj - s["col"]


def test_aucun_semis_hors_de_la_fenetre_du_noyau_tronque(semis):
    semis = semis.get()
    di, dj = _distances(semis)
    dehors = (np.abs(di) > H.TRONCATURE) | (np.abs(dj) > H.TRONCATURE)
    ens = semis["semis"] > H.SEUIL_SEMIS
    fautives = np.argwhere(ens & dehors)
    assert not len(fautives), (
        f"[{semis['cas']}] {len(fautives)} cellules ensemencées hors de la fenêtre de la source "
        f"({semis['row']}, {semis['col']}), par exemple (ligne, colonne) {fautives[:3].tolist()}")


def test_toute_cellule_a_portee_est_ensemencee(semis):
    semis = semis.get()
    di, dj = _distances(semis)
    dedans = np.hypot(di, dj) <= H.TRONCATURE + 1e-9
    manquent = np.argwhere(dedans & ~(semis["semis"] > H.SEUIL_SEMIS))
    assert not len(manquent), (
        f"[{semis['cas']}] {len(manquent)} cellules à portée sans semis, par exemple {manquent[:3].tolist()} ; "
        f"source attendue en (ligne {semis['row']}, colonne {semis['col']})")


def test_le_barycentre_des_semis_est_la_source(semis):
    semis = semis.get()
    a = semis["semis"] * (semis["semis"] > H.SEUIL_SEMIS)
    assert a.sum() > 0, f"[{semis['cas']}] aucun semis"
    ii, jj = np.meshgrid(np.arange(a.shape[0]), np.arange(a.shape[1]), indexing="ij")
    bi, bj = float((a * ii).sum() / a.sum()), float((a * jj).sum() / a.sum())
    assert abs(bi - semis["row"]) < 0.05 and abs(bj - semis["col"]) < 0.05, (
        f"[{semis['cas']}] barycentre (ligne {bi:.3f}, colonne {bj:.3f}), source (ligne {semis['row']}, "
        f"colonne {semis['col']}) : axes transposés ou décalés ?")


def test_les_semis_suivent_le_noyau_du_contrat(semis):
    semis = semis.get()
    di, dj = _distances(semis)
    r_m = 25.0 * np.hypot(di, dj)
    k = H.noyau(r_m, G.REGENERATION_DEFAUT["kernel_scale_m"][0], G.REGENERATION_DEFAUT["kernel_shape"][0])
    ens = semis["semis"] > H.SEUIL_SEMIS
    q = semis["semis"][ens] / k[ens]
    assert np.ptp(q) <= 1e-6 * q.mean(), (
        f"[{semis['cas']}] semis / k(r) varie de {q.min():.6g} à {q.max():.6g} : la forme du noyau n'est pas "
        "exp(−(r/a)^b), ou r n'est pas la distance entre centres de cellules")


def test_un_seul_noyau_par_source(semis):
    """Le cas asymétrique transposé enverrait des semis vers (colonne, ligne) : rien autour de la cellule miroir."""
    semis = semis.get()
    if semis["row"] == semis["col"]:
        assert semis["semis"][semis["row"], semis["col"]] > H.SEUIL_SEMIS
        return
    mi, mj = semis["col"], semis["row"]
    a = semis["semis"][max(mi - 1, 0):mi + 2, max(mj - 1, 0):mj + 2]
    assert not (a > H.SEUIL_SEMIS).any(), f"semis autour de la cellule miroir ({mi}, {mj}) : grille transposée"
