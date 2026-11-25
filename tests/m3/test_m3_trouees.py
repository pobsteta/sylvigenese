"""M3a, trouées (décision de Pascal, 25/11/2026) : pas de recrue dans une cellule tant que sa hauteur dominante est
nulle ; le fait est compté et signalé ; la recolonisation des trouées viendra en M5 par les cohortes.

Le jeu fictif porte une trouée : 62 cellules dont h0.tif vaut 0, sans aucun arbre à t0 (S03, spec §5). Sans arbre,
sa H_dom n'avance pas (aucune essence ne la fait grandir) : elle reste nulle sur les 100 ans, donc aucune recrue ne
doit y naître, quelle que soit l'année. Le contrôle positif (des recrues naissent ailleurs, dans des cellules de
hauteur non nulle) est dans test_m3_chaine.py (« il y a des recrues ») et repris ici pour que le test discrimine.

Signalement : la sorte est tenue par simulate et DOCUMENTÉE dans contracts/tables/sim/flags.schema.json (champ
`kind`). Le test ne suppose aucun nom : il exige un signalement dont la sorte figure dans cette documentation et
dont le message dit en français qu'une recrue a été refusée parce que la hauteur dominante est nulle (mots « recrue »
et « trouée » ou « hauteur dominante »), et un décompte : soit une ligne par cellule en cause (toutes les cellules de
la trouée), soit un total (une valeur au moins égale au nombre de cellules de la trouée)."""
import json

import numpy as np
import pyarrow.parquet as pq
import pytest

import helpers_m3 as H

T0 = H.SIM_NOMINAL["t0"]
ANNEES = H.SIM_NOMINAL["years"]
SCHEMA_FLAGS = H.ROOT / "contracts" / "tables" / "sim" / "flags.schema.json"


@pytest.fixture(scope="module")
def trouee(grid):
    """cell_id des cellules à hauteur dominante nulle au départ (h0.tif = 0)."""
    h0 = grid.raster("h0")
    lig, col = np.nonzero(h0 == 0)
    ids = set((lig * grid.ncols + col).tolist())
    assert len(ids) >= 50, f"le jeu fictif n'a plus de trouée à h0 = 0 ({len(ids)} cellules)"
    return ids


def _cellule_de_recrue(tree_id: str) -> int:
    return int(H.RE_RECRUE.match(tree_id).group(1))


def test_la_trouee_est_sans_arbre_au_depart(init, grid, trouee):
    """Précondition : aucun arbre initial dans la trouée, sinon « H_dom nulle » ne dirait rien de ses arbres."""
    cid = set(grid.cell_id(init["x"], init["y"]).tolist())
    assert not (cid & trouee), f"{len(cid & trouee)} cellules de la trouée portent des arbres à t0"


def test_aucune_recrue_ne_nait_dans_une_cellule_de_hauteur_dominante_nulle(arbres, trouee):
    rec = np.unique(arbres["tree_id"][H.commence_par(arbres["tree_id"], "r")]).tolist()
    assert len(rec) > 100, "précondition : le jeu fictif doit recruter ailleurs que dans la trouée"
    en_trouee = [t for t in rec if _cellule_de_recrue(t) in trouee]
    assert not en_trouee, f"{len(en_trouee)} recrues nées dans la trouée (H_dom = 0), par exemple {en_trouee[:3]}"
    cellules = {_cellule_de_recrue(t) for t in rec}
    assert len(cellules) > 100, f"recrutement sur seulement {len(cellules)} cellules : test peu discriminant"


def test_aucun_arbre_ne_pousse_dans_la_trouee(arbres, grid, trouee):
    """Position des arbres de toutes les années (x est, y nord) : aucun dans une cellule de la trouée."""
    cid = grid.cell_id(arbres["x"], arbres["y"])
    dedans = np.isin(cid, np.array(sorted(trouee)))
    assert not dedans.any(), f"{int(dedans.sum())} lignes d'arbres dans la trouée, par exemple {arbres['tree_id'][dedans][:3].tolist()}"


@pytest.mark.parametrize("annee", [T0, T0 + 1, T0 + 50, T0 + ANNEES])
def test_les_cellules_de_la_trouee_restent_sans_tige(chaine, trouee, annee):
    c = H.read_year(chaine["dir"], "cells", annee)
    dedans = np.isin(c["cell_id"], np.array(sorted(trouee)))
    assert not (c["stems_ha"][dedans] > 0).any(), f"des tiges dans la trouée en {annee}"
    assert not (c["basal_area_m2_ha"][dedans] > 0).any(), f"de la surface terrière dans la trouée en {annee}"


def _sortes_documentees() -> str:
    schema = json.loads(SCHEMA_FLAGS.read_text(encoding="utf-8"))
    return next(f["description"] for f in schema["fields"] if f["name"] == "kind")


def test_la_trouee_sans_recrue_est_comptee_et_signalee(chaine, trouee):
    """Sortes documentées dans flags.schema.json : `trouee_sans_recrue` (une ligne par cellule de la trouée et par
    année simulée après t0 ; valeur : H_dom, 0) et `total_trouees_sans_recrue` (zone, dernière année, total)."""
    t = H.Tab.from_arrow(pq.read_table(chaine["dir"] / "sim" / "flags.parquet"))
    doc = _sortes_documentees()
    for k in ("trouee_sans_recrue", "total_trouees_sans_recrue"):
        assert k in doc, f"sorte {k} non documentée dans flags.schema.json (champ kind)"
    par = t.where(t["kind"] == "trouee_sans_recrue")
    couples = set(zip(par["entity"].tolist(), par["year"].tolist()))
    assert len(couples) == len(par), "signalements trouee_sans_recrue en double"
    attendu = {(str(c), y) for c in trouee for y in range(T0 + 1, T0 + ANNEES + 1)}
    assert couples == attendu, (f"{len(attendu - couples)} couples (cellule, année) manquants, "
                                f"{len(couples - attendu)} en trop ; ex. manquants {sorted(attendu - couples)[:3]}")
    assert (par["value"] == 0).all(), "la valeur d'un signalement de trouée est la H_dom (0 m)"
    assert all("recrue" in m.lower() for m in par["message"].tolist()[:50])
    tot = t.where(t["kind"] == "total_trouees_sans_recrue")
    assert len(tot) == 1, f"{len(tot)} lignes total_trouees_sans_recrue"
    assert tot["entity"][0] == chaine["name"] and tot["year"][0] == T0 + ANNEES
    assert tot["value"][0] == len(attendu), (tot["value"][0], len(attendu))
