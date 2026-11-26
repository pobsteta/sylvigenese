"""Trouées recolonisées en mode cohorts au niveau massif (décision de Pascal Q4 du 26/11/2026 ; journal du 25/11 :
« la recolonisation des trouées viendra en M5 par les cohortes ») et calage du passage au niveau massif (Q1).

Massif fictif (entrées figées de M3a) : la trouée de 62 cellules à h0 = 0, sans arbre à t0 (S03). Noyau tronqué à
K = 1 cellule ; tous les arbres initiaux sont semenciers (maturité synthétique 30 cm, le plus petit arbre fait 35,8 cm),
aucune recrue ne le devient en 8 ans. Les cellules semencières sont celles qui portent un arbre initial.
  - « sûrement à portée » : une cellule de la trouée qui a une voisine semencière par un côté (25 m, dans le disque
    comme dans le carré de demi-largeur K) : elle reçoit des semis, qui passent à mesure qu'ils atteignent la hauteur
    de passage (Q1, en trouée) ; elle doit avoir recruté au bout de 8 ans ;
  - « sûrement hors de portée » : aucune cellule semencière dans son voisinage de 3 × 3 : elle reste vide, et elle
    est signalée `trouee_hors_de_portee` (contrat sim.flags) ;
  - run.json `gaps_recolonised` = nombre de cellules de la trouée qui ont recruté (recompté dans sim/trees).
Calage au niveau massif : le recrutement synthétique ne dépend que de la station, λ = exp(η) × 0,0625 ha par cellule
et par an ; l'arrondi aléatoire donne floor(λ) ou ceil(λ) recrues, jamais plus ; moins, seulement quand le stock
borne (compté dans `seedling_stock_limited`)."""
import math

import numpy as np
import pytest

import helpers_m5 as H

T0 = H.H3.SIM_NOMINAL["t0"]


def _ok(r):
    assert r["proc"].returncode == 0, H.queue(r["proc"])


@pytest.fixture(scope="module")
def massif(massif_cohorts):
    return H.Paresseux(lambda: _massif(massif_cohorts))


def _massif(massif_cohorts):
    _ok(massif_cohorts)
    z = massif_cohorts["dir"]
    g = H.H3.Grid(z)
    init = H.H3.read_trees_init(z)
    src = np.zeros((g.nrows, g.ncols), bool)
    cid = g.cell_id(init["x"], init["y"])
    src[cid // g.ncols, cid % g.ncols] = True
    h0 = g.raster("h0")
    trouee = (h0 == 0)
    assert trouee.sum() >= 50 and not (trouee & src).any(), "précondition : trouée sans arbre à t0"
    pad = np.pad(src, 1)
    cote = pad[:-2, 1:-1] | pad[2:, 1:-1] | pad[1:-1, :-2] | pad[1:-1, 2:]
    huit = cote | pad[:-2, :-2] | pad[:-2, 2:] | pad[2:, :-2] | pad[2:, 2:]
    a_portee = trouee & cote
    hors = trouee & ~huit
    assert a_portee.sum() >= 10 and hors.sum() >= 4, (int(a_portee.sum()), int(hors.sum()))
    arbres = H.H3.read_all_trees(z)
    rec = arbres.where(H.H3.commence_par(arbres["tree_id"], "r"))
    ids = np.unique(rec["tree_id"]).tolist()
    cell_rec = {int(H.RE_RECRUE.match(t).group(1)) for t in ids}
    as_ids = lambda m: {int(i) for i in (np.argwhere(m) @ np.array([g.ncols, 1])).tolist()}
    return {"dir": z, "grid": g, "trouee": as_ids(trouee), "a_portee": as_ids(a_portee), "hors": as_ids(hors),
            "cell_rec": cell_rec, "rec": rec, "run": H.read_run_json(z), "flags": H.read_flags(z)}


def test_les_trouees_a_portee_recrutent(massif):
    massif = massif.get()
    manquent = sorted(massif["a_portee"] - massif["cell_rec"])
    assert not manquent, (f"{len(manquent)} cellules de la trouée, voisines d'un semencier, sans recrue en 8 ans "
                          f"(Q4 : recolonisées par les cohortes), par exemple {manquent[:5]}")


def test_les_trouees_hors_de_portee_restent_vides(massif):
    massif = massif.get()
    assert massif["a_portee"] & massif["cell_rec"], \
        "précondition : aucune trouée à portée n'a recruté ; « hors de portée reste vide » ne discriminerait rien"
    pleines = sorted(massif["hors"] & massif["cell_rec"])
    assert not pleines, f"recrues dans des trouées hors de portée du noyau tronqué : {pleines[:5]}"


def test_les_trouees_hors_de_portee_sont_signalees(massif):
    massif = massif.get()
    f = massif["flags"]
    m = f["kind"] == "trouee_hors_de_portee"
    signalees = {int(e) for e in f["entity"][m].tolist()}
    assert massif["hors"] <= signalees, f"trouées hors de portée non signalées : {sorted(massif['hors'] - signalees)[:5]}"
    assert signalees <= massif["trouee"], f"signalées hors de la trouée : {sorted(signalees - massif['trouee'])[:5]}"
    assert not signalees & massif["a_portee"], f"signalées alors qu'à portée : {sorted(signalees & massif['a_portee'])[:5]}"
    assert (f["year"][m] == T0).any(), "trouee_hors_de_portee doit être écrit dès l'année t0 (contrat sim.flags)"


def test_gaps_recolonised_compte_les_cellules_de_trouee_qui_ont_recrute(massif):
    massif = massif.get()
    attendu = len(massif["trouee"] & massif["cell_rec"])
    assert massif["run"].get("gaps_recolonised") == attendu, (massif["run"].get("gaps_recolonised"), attendu)
    assert attendu >= 10


def test_plus_de_trouee_sans_recrue_pour_une_trouee_recolonisee(massif):
    """Contrat sim.flags : en mode cohorts, `trouee_sans_recrue` n'est plus écrit pour une trouée qui reçoit des
    semis ; une cellule à portée, qui en reçoit dès la première année, n'est donc jamais signalée ainsi."""
    massif = massif.get()
    f = massif["flags"]
    m = f["kind"] == "trouee_sans_recrue"
    fautives = {int(e) for e in f["entity"][m].tolist()} & massif["a_portee"]
    assert not fautives, f"trouee_sans_recrue pour des trouées à portée : {sorted(fautives)[:5]}"


def test_massif_le_nombre_de_recrues_est_l_arrondi_du_flux_ifn(massif):
    massif = massif.get()
    rec, g = massif["rec"], massif["grid"]
    st = H.Station(massif["dir"])
    prem = rec.order("tree_id", "year")
    prem = prem.where(H.H3.debuts_de_groupe(prem["tree_id"]))
    cles = {}
    for t, s in zip(prem["tree_id"].tolist(), prem["species"].tolist()):
        c, a, _r = H.RE_RECRUE.match(t).groups()
        cles.setdefault((int(c), int(a), s), 0)
        cles[(int(c), int(a), s)] += 1
    sous_couvert = {k: v for k, v in cles.items() if k[0] not in massif["trouee"]}
    assert len(sous_couvert) > 1000, f"précondition : peu de recrutement sous couvert ({len(sous_couvert)})"
    flux = {s: st.flux_recrues_ha(s) * H.AIRE_CELLULE_HA for s in H.ESSENCES_MASSIF}
    trop = [(k, v, float(flux[k[2]][k[0]])) for k, v in sous_couvert.items() if v > math.ceil(flux[k[2]][k[0]])]
    assert not trop, f"plus de recrues que ceil(exp(η) × 0,0625) : {trop[:3]}"
    sous = sum(1 for k, v in sous_couvert.items() if v < math.floor(flux[k[2]][k[0]]))
    assert sous <= massif["run"].get("seedling_stock_limited", -1), (
        f"{sous} couples sous floor(λ) mais seedling_stock_limited = {massif['run'].get('seedling_stock_limited')}")
    lam = np.array([flux[k[2]][k[0]] for k in sous_couvert])
    assert (np.floor(lam) >= 1).mean() > 0.5, "précondition : λ ≥ 1 sur la plupart des cellules (test discriminant)"
