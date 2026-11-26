"""Passage à la futaie calé sur le modèle IFN (décision de Pascal Q1 du 26/11/2026, option a), stock initial « en
régime » (Q2) et conservation des tiges (plan m5a, mission C) : niveau SER, où les cohortes portent des espérances,
sans tirage (T4), donc où le calage est exact.

Oracle : les modèles synthétiques du générateur ne dépendent que de la station (trophic) et de la SER ; pour chaque
cellule c et essence s, flux IFN F(c, s) = exp(η_recrutement) tiges/ha/an et risque annuel p(c) = 1 − exp(−exp(η_mort))
se recalculent ICI, depuis station_gradients.tif, ser.tif, ser.csv et params/*.parquet (contrat dynamics_params).
Avec S(t) les tiges/ha d'un couple (cellule, essence) sommées sur les classes de sim/cohorts, la recrue de l'année est
R = S(t+1) − S(t)(1 − p), ou R = S(t+1)/(1 − p) − S(t) si les recrues de l'année meurent avec les autres ; UNE des deux
lectures doit valoir pour toute l'exécution (helpers_m5, conventions). Les transferts entre classes ne changent pas S.

- stock ample : R = F partout, à la tolérance f32 près (1e-9 × F sinon) ; aucun manque compté ;
- stock rare (fécondité quasi nulle) : R ≤ F partout ; là où R < F, le stock a borné le flux ; le nombre de couples
  (cellule, essence, année) bornés égale run.json `seedling_stock_limited`, et il n'est pas nul (le bornage agit) ;
- Q2 : à t0, chaque couple qui a des adultes a des semis ; la première année n'est bornée nulle part (pas de
  rupture à t0) ; à lumière uniforme, semis(t0) / F est le même pour toutes les cellules d'une essence (flux × temps de
  passage), et ce temps est d'au moins un an."""
import numpy as np
import pytest

import helpers_m5 as H
import ser_fictive as G

SP = G.ESSENCES_DEFAUT


def _ok(r):
    assert r["proc"].returncode == 0, H.queue(r["proc"])


class Bilan:
    """Recrues par (cellule, essence, année) déduites de sim/cohorts, selon les deux lectures de l'ordre mort/recrue."""

    def __init__(self, r):
        _ok(r)
        self.st = H.Station(r["dir"])
        self.coh = H.read_kind(r["dir"], "cohorts")
        self.years = sorted(set(self.coh["year"].tolist()))
        t0, years = r["sim"]["t0"], r["sim"]["years"]
        assert self.years == list(range(t0, t0 + years + 1)), f"années de sim/cohorts : {self.years}"
        n = self.st.ncell
        self.S = {y: H.stems_by_key(self.coh, y, SP, n) for y in self.years}
        self.F = np.stack([self.st.flux_recrues_ha(s) for s in SP], axis=1)
        self.p = np.stack([self.st.p_mort(s) for s in SP], axis=1)

    def recrues(self, y, variante):
        s0, s1 = self.S[y], self.S[y + 1]
        return s1 - s0 * (1 - self.p) if variante == "A" else s1 / (1 - self.p) - s0

    def variante_qui_vaut(self, critere):
        ok = {v: all(critere(self.recrues(y, v), y) for y in self.years[:-1]) for v in "AB"}
        return ok


@pytest.fixture(scope="module")
def ample(ser_calage):
    return H.Paresseux(lambda: Bilan(ser_calage))


@pytest.fixture(scope="module")
def rare(ser_stock_rare):
    return H.Paresseux(lambda: Bilan(ser_stock_rare))


def test_stock_ample_le_flux_de_recrues_egale_exp_eta_par_cellule_et_essence(ample):
    b = ample.get()
    ecarts = {}
    for v in "AB":
        pire = 0.0
        for y in b.years[:-1]:
            R = b.recrues(y, v)
            e = np.abs(R - b.F) / H.tol(b.F, b.S[y], b.S[y + 1], b.F)
            pire = max(pire, float(e.max()))
        ecarts[v] = pire
    assert min(ecarts.values()) <= 1.0, (
        "le flux de recrues n'est pas exp(η) tiges/ha/an (Q1, sous couvert, stock ample) ; pire écart rapporté à la "
        f"tolérance : S'=S(1-p)+R : {ecarts['A']:.3g}, S'=(S+R)(1-p) : {ecarts['B']:.3g}")


def test_stock_ample_aucun_manque_compte(ser_calage, ample):
    ample.get()
    j = H.read_run_json(ser_calage["dir"])
    assert j.get("seedling_stock_limited") == 0, j.get("seedling_stock_limited")


def test_stock_ample_le_test_discrimine(ample):
    """Précondition : le flux n'est pas négligeable devant les tiges (sinon l'égalité ne prouverait rien), et il
    varie d'une cellule à l'autre (trophic, deux SER)."""
    b = ample.get()
    assert (b.F > 1.0).all() and float(b.F.max() / b.F.min()) > 1.2, (b.F.min(), b.F.max())
    assert float(b.F.min()) > 1e3 * float(H.tol(0.0, b.S[b.years[0]]).max()), "tolérance trop large devant le flux"


def test_stock_rare_le_flux_ne_depasse_jamais_exp_eta(rare):
    b = rare.get()
    ok = b.variante_qui_vaut(lambda R, y: bool((R <= b.F + H.tol(b.F, b.S[y], b.S[y + 1], b.F)).all()))
    assert any(ok.values()), f"des recrues au-delà du flux IFN (le stock borne, il n'ajoute pas) : {ok}"


def test_stock_rare_les_couples_bornes_sont_comptes_dans_run_json(ser_stock_rare, rare):
    b = rare.get()
    j = H.read_run_json(ser_stock_rare["dir"])
    assert isinstance(j.get("seedling_stock_limited"), int), j.get("seedling_stock_limited")
    comptes = {}
    for v in "AB":
        comptes[v] = int(sum(((b.recrues(y, v) < b.F - H.tol(b.F, b.S[y], b.S[y + 1], b.F))).sum()
                             for y in b.years[:-1]))
    assert j["seedling_stock_limited"] in comptes.values(), (
        f"seedling_stock_limited = {j['seedling_stock_limited']}, recompté : {comptes} (couples cellule, essence, "
        "année où le flux est sous exp(η))")
    assert j["seedling_stock_limited"] > 0, "le stock rare n'a jamais borné le flux : le test ne discrimine pas"


def test_stock_rare_le_manque_n_est_pas_comble(rare):
    """Là où le stock borne, la recrue est sous le flux et jamais négative : le manque est compté, pas comblé."""
    b = rare.get()
    ok = b.variante_qui_vaut(lambda R, y: bool((R >= -H.tol(b.F, b.S[y], b.S[y + 1])).all()))
    assert any(ok.values()), "recrue négative"
    dernier = b.years[-2]
    R = b.recrues(dernier, "A")
    assert (R < 0.5 * b.F).mean() > 0.5, "au bout de 6 ans de fécondité quasi nulle, le flux devrait être borné"


# ------------------------------------------------------------------ Q2 : stock initial en régime
def test_q2_premiere_annee_sans_rupture(rare):
    """Le stock « en régime » à t0 suffit au flux de la première année, partout, même sans nouvelles graines."""
    b = rare.get()
    y = b.years[0]
    ecarts = {v: float((np.abs(b.recrues(y, v) - b.F) / H.tol(b.F, b.S[y], b.S[y + 1], b.F)).max()) for v in "AB"}
    assert min(ecarts.values()) <= 1.0, f"première année bornée : le stock initial n'est pas en régime ({ecarts})"


def test_q2_des_semis_a_t0_partout_ou_il_y_a_des_adultes(ser_stock_rare, rare):
    b = rare.get()
    c = H.read_kind(ser_stock_rare["dir"], "cells")
    t0 = b.years[0]
    m = c["year"] == t0
    assert "seedlings_ha" in c.names, "sim/cells sans seedlings_ha en mode cohorts"
    sem = np.zeros((b.st.ncell, len(SP)))
    for j, s in enumerate(SP):
        k = m & (c["species"] == s)
        sem[c["cell_id"][k].astype(int), j] = np.nan_to_num(c["seedlings_ha"][k].astype("float64"))
    adultes = b.S[t0] > 0
    assert adultes.all(), "précondition : la SER fictive a les deux essences dans chaque cellule"
    assert (sem[adultes] > 0).all(), f"{int((sem[adultes] <= 0).sum())} couples sans semis à t0 (Q2 : stock en régime)"
    ratio = sem / b.F
    for j, s in enumerate(SP):
        r = ratio[:, j]
        assert np.ptp(r) <= 1e-5 * r.mean(), (
            f"essence {s} : semis(t0) / flux IFN varie de {r.min():.6g} à {r.max():.6g} (Q2 : flux × temps de passage, "
            "à lumière uniforme le même partout)")
        assert r.mean() >= 1.0 - 1e-6, f"essence {s} : temps de passage déduit {r.mean():.4g} an, moins d'un an"


# ------------------------------------------------------------------ conservation dans les transferts
def test_les_transferts_entre_classes_conservent_les_tiges(ser_transfert):
    """Ni mort ni recrue (exp(−40)), croissance forte : la somme des classes est conservée par (cellule, essence),
    tandis que la distribution monte (le test ne serait pas discriminant si rien ne bougeait)."""
    _ok(ser_transfert)
    coh = H.read_kind(ser_transfert["dir"], "cohorts")
    years = sorted(set(coh["year"].tolist()))
    n = ser_transfert["n"] ** 2
    S = {y: H.stems_by_key(coh, y, SP, n) for y in years}
    for y in years[1:]:
        e = np.abs(S[y] - S[years[0]])
        assert (e <= H.tol(0.0, S[years[0]], S[y])).all(), f"année {y} : tiges non conservées, écart max {e.max():.3g}"
    moy = {}
    for y in (years[0], years[-1]):
        m = coh["year"] == y
        moy[y] = float((coh["d_class"][m] * coh["stems_ha"][m]).sum() / coh["stems_ha"][m].sum())
    assert moy[years[-1]] > moy[years[0]] + 0.5, f"rang de classe moyen {moy} : aucun transfert vers le haut"
    assert int(coh["d_class"].max()) == H.K_CLASSES - 1, "la dernière classe (ouverte) n'est jamais atteinte"


def test_aucune_classe_hors_de_k(ser_nominale):
    _ok(ser_nominale)
    coh = H.read_kind(ser_nominale["dir"], "cohorts")
    assert int(coh["d_class"].min()) >= 0 and int(coh["d_class"].max()) < H.K_CLASSES
