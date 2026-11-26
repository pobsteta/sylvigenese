"""Deux modes de recrutement (décision de Pascal Q4 du 26/11/2026 ; T5) et mentions de ce qui n'est pas simulé (Q3).

- `ifn_direct` garde la référence de M3a : sur les entrées figées de tests/m3/reference/entrees, la configuration
  nominale de M3a plus `recruitment: ifn_direct` redonne l'empreinte tests/m3/reference/nominal.json, empreinte et
  entrées étant elles-mêmes inchangées (SHA-256 relevés le 26/11/2026, mission 061).
- `cohorts` : semis simulés, donc colonnes de semis dans sim/cells ; « gibier, sous-bois et fructification non
  simulés » dans run.json (`not_simulated`), jamais « semis » ; plus de signalement `semis_non_simules`.
- `ifn_direct` : pas de colonne de semis, « semis » dans `not_simulated`, le signalement `semis_non_simules` écrit,
  aucun compte de la régénération dans run.json.

Les mentions du rapport (rapport_simulation.html, écrit par post) et de la fiche (assets) ne sont pas jugées ici :
post et assets refusent le niveau SER jusqu'à M5b, et leur chaîne n'est pas lancée par tests/m5."""
import hashlib
import json

import pyarrow.parquet as pq
import pytest

import helpers_m5 as H
import test_m3_non_regression as NR      # empreinte() et _egal() de M3a, importées (un lien plutôt qu'une copie)

REF_M3 = H.ROOT / "tests" / "m3" / "reference"
# Relevés le 26/11/2026 avant toute mission de M5a : la référence de M3a ne bouge pas en M5a (T5, Q4).
SHA_REFERENCE_M3 = {
    "nominal.json": "0df7a4d1abdf47dc1929b154c25349eb29fcf6fedf996266140fad1fba2e2b5b",
    "entrees/MANIFEST.json": "9ff2e8956ac699f9ddce28540f11a27153cc5b35d2d006719354d1d86f974ea1",
    "u_table.csv": "e00db38e93fe8f530573d5a4c11bbcd467a4f06c8a89622c87a92a93d596d384",
}
MENTIONS_COHORTS = {"gibier", "sous_bois", "fructification"}
COMPTES_REGEN = ("seedling_stock_limited", "gaps_recolonised", "buffer_cells")
COLONNES_SEMIS = {"seedlings_ha", "seedling_h_mean"}


def _ok(r):
    assert r["proc"].returncode == 0, H.queue(r["proc"])


# ------------------------------------------------------------------ ifn_direct : la référence de M3a
@pytest.mark.parametrize("rel", sorted(SHA_REFERENCE_M3))
def test_la_reference_de_m3a_est_inchangee(rel):
    p = REF_M3 / rel
    assert p.is_file(), f"{p} absent"
    assert hashlib.sha256(p.read_bytes()).hexdigest() == SHA_REFERENCE_M3[rel], \
        f"{rel} a changé : en M5a, la référence de M3a ne se regèle pas (mode ifn_direct, décision Q4)"


def test_ifn_direct_redonne_l_empreinte_de_m3a(massif_ifn_direct):
    _ok(massif_ifn_direct)
    ref = json.loads((REF_M3 / "nominal.json").read_text(encoding="utf-8"))
    NR._egal(ref, json.loads(json.dumps(NR.empreinte(massif_ifn_direct["dir"]))))


def test_ifn_direct_run_json(massif_ifn_direct):
    _ok(massif_ifn_direct)
    j = H.read_run_json(massif_ifn_direct["dir"])
    assert j.get("recruitment") == "ifn_direct", j.get("recruitment")
    assert "semis" in j.get("not_simulated", []), j.get("not_simulated")
    assert not set(COMPTES_REGEN) & set(j), f"comptes de régénération en ifn_direct : {set(COMPTES_REGEN) & set(j)}"
    for k in ("memory_estimate_max_bytes", "memory_peak_rss_bytes"):
        assert k in j, f"run.json de M5a sans {k}"
    p = H.run_validate("run", str(massif_ifn_direct["dir"] / "sim" / "run.json"))
    assert p.returncode == 0, p.stdout[-800:]


def test_ifn_direct_sans_colonne_de_semis_et_semis_dits_non_simules(massif_ifn_direct):
    _ok(massif_ifn_direct)
    cols = set(H.column_types(massif_ifn_direct["dir"], "cells"))
    assert not cols & COLONNES_SEMIS, f"colonnes de semis en ifn_direct : {cols & COLONNES_SEMIS}"
    assert "semis_non_simules" in H.flags_kinds(massif_ifn_direct["dir"])


# ------------------------------------------------------------------ cohorts : mentions (Q3) et colonnes de semis
@pytest.fixture(scope="module", params=["massif", "ser"])
def cohorts(request, massif_cohorts, ser_nominale):
    return massif_cohorts if request.param == "massif" else ser_nominale


def test_cohorts_run_json_dit_gibier_sous_bois_et_fructification_non_simules(cohorts):
    _ok(cohorts)
    j = H.read_run_json(cohorts["dir"])
    assert j.get("recruitment") == "cohorts", j.get("recruitment")
    ns = set(j.get("not_simulated", []))
    assert MENTIONS_COHORTS <= ns, f"mentions manquantes : {MENTIONS_COHORTS - ns}"
    assert "semis" not in ns, "en mode cohorts, les semis sont simulés : « semis » ne doit pas être dit non simulé"


def test_cohorts_n_ecrit_plus_semis_non_simules(cohorts):
    _ok(cohorts)
    assert "semis_non_simules" not in H.flags_kinds(cohorts["dir"])


def test_cohorts_ecrit_les_colonnes_de_semis(cohorts):
    """Contrat sim.cells (mission 060) : présentes dès que run.json dit cohorts ; une semis/ha non négatif, une
    hauteur strictement positive quand il y a des semis (vide sinon)."""
    _ok(cohorts)
    cols = set(H.column_types(cohorts["dir"], "cells"))
    assert COLONNES_SEMIS <= cols, f"colonnes de semis absentes en cohorts : {COLONNES_SEMIS - cols}"
    c = H.read_kind(cohorts["dir"], "cells")
    s, h = c["seedlings_ha"].astype("float64"), c["seedling_h_mean"].astype("float64")
    assert (s[~H.H3.isnull(s)] >= 0).all()
    avec = ~H.H3.isnull(s) & (s > 0)
    assert avec.any(), "aucun semis dans toute l'exécution"
    assert (h[avec] > 0).all(), "hauteur de semis nulle ou vide là où il y a des semis"


def test_cohorts_run_json_porte_les_comptes_de_la_regeneration(cohorts):
    _ok(cohorts)
    j = H.read_run_json(cohorts["dir"])
    for k in COMPTES_REGEN + ("zeroed_values",):
        assert isinstance(j.get(k), int) and j[k] >= 0, f"{k} : {j.get(k)!r}"
    p = H.run_validate("run", str(cohorts["dir"] / "sim" / "run.json"))
    assert p.returncode == 0, p.stdout[-800:]


def test_cohorts_les_sorties_sont_conformes(cohorts):
    _ok(cohorts)
    for contrat, rel in (("sim_cells", "sim/cells"), ("flags", "sim/flags.parquet")):
        p = H.run_validate(contrat, str(cohorts["dir"] / rel))
        assert p.returncode == 0, f"{rel} : {p.stdout[-800:]}"
