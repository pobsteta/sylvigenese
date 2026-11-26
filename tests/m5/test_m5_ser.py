"""Niveau SER (BRIEF §3 et §11 ; ADR 0006 projet, choix 1, 4 et 9 ; T8 du plan m5a ; contrats sim.cohorts, sim.cells,
run) : `simulate --level ser` tourne sur une SER fictive, n'écrit aucun sim/trees (il n'y a pas d'individu), écrit
sim/cells et sim/cohorts aux années retenues (t0, tous les write_step ans, la dernière), sans en inventer d'autres ;
les tiges de sim/cells sont la somme des classes de sim/cohorts ; t0 redonne cohorts_init ; les sorties sont
conformes à leurs contrats."""
import numpy as np
import pyarrow.parquet as pq

import helpers_m5 as H
import ser_fictive as G

SP = G.ESSENCES_DEFAUT


def _ok(r):
    assert r["proc"].returncode == 0, H.queue(r["proc"])


def test_la_ser_fictive_va_a_son_terme(ser_nominale):
    _ok(ser_nominale)


def test_aucune_sortie_sim_trees_au_niveau_ser(ser_nominale):
    _ok(ser_nominale)
    assert not (ser_nominale["dir"] / "sim" / "trees").exists(), "sim/trees écrit au niveau SER (aucun individu)"


def test_annees_ecrites_t0_pas_de_write_step_et_la_derniere(ser_nominale):
    _ok(ser_nominale)
    t0, y, w = H.T0, ser_nominale["sim"]["years"], ser_nominale["sim"]["ser"]["write_step"]
    attendu = sorted(set(range(t0, t0 + y + 1, w)) | {t0 + y})
    assert attendu == [t0, t0 + 2, t0 + 4, t0 + 5]
    for kind in ("cohorts", "cells"):
        vues = sorted(H.partitions(ser_nominale["dir"], kind))
        assert vues == attendu, f"sim/{kind} : années {vues}, attendu {attendu} (pas d'année inventée ni omise)"


def test_sorties_conformes_aux_contrats(ser_nominale):
    _ok(ser_nominale)
    d = ser_nominale["dir"] / "sim"
    for contrat, rel in (("sim_cohorts", "cohorts"), ("sim_cells", "cells"), ("flags", "flags.parquet"),
                         ("run", "run.json")):
        p = H.run_validate(contrat, str(d / rel))
        assert p.returncode == 0, f"sim/{rel} : {p.stdout[-800:]}"
    assert not H.H3.fichiers_sans_year(ser_nominale["dir"], "cohorts"), "colonne year dans les fichiers de partition"


def test_run_json_dit_le_niveau_ser(ser_nominale):
    _ok(ser_nominale)
    j = H.read_run_json(ser_nominale["dir"])
    assert j["level"] == "ser" and j["recruitment"] == "cohorts" and j["years"] == 5


def test_les_tiges_de_sim_cells_sont_la_somme_des_classes(ser_nominale):
    _ok(ser_nominale)
    coh = H.read_kind(ser_nominale["dir"], "cohorts")
    cel = H.read_kind(ser_nominale["dir"], "cells")
    n = ser_nominale["n"] ** 2
    for y in sorted(set(coh["year"].tolist())):
        s = H.stems_by_key(coh, y, SP, n)
        c = np.zeros_like(s)
        m = cel["year"] == y
        for j, sp in enumerate(SP):
            k = m & (cel["species"] == sp)
            c[cel["cell_id"][k].astype(int), j] = cel["stems_ha"][k].astype("float64")
        assert (np.abs(c - s) <= H.tol(0.0, s, c) + 1e-12).all(), f"année {y} : stems_ha ≠ Σ classes"


def test_t0_redonne_cohorts_init(ser_nominale):
    _ok(ser_nominale)
    coh = H.read_kind(ser_nominale["dir"], "cohorts")
    init = H.Tab.from_arrow(pq.read_table(ser_nominale["dir"] / "cohorts_init.parquet"))
    init = init.where(init["stems_ha"] > 0)
    m = coh["year"] == H.T0
    t = coh.where(m)
    cle = lambda tab: {(int(c), s, int(k)): float(v) for c, s, k, v in
                       zip(tab["cell_id"].tolist(), tab["species"].tolist(), tab["d_class"].tolist(),
                           tab["stems_ha"].tolist())}
    a, b = cle(init), cle(t)
    assert set(a) == set(b), f"clés de t0 ≠ cohorts_init : {len(set(a) ^ set(b))} écarts"
    ecart = max(abs(a[k] - b[k]) / a[k] for k in a)
    assert ecart <= 2 * H.EPS32, f"tiges de t0 ≠ cohorts_init (écart relatif {ecart:.3g}, au-delà de l'arrondi f32)"


def test_les_cohortes_ecrites_sont_dans_la_grille_et_ont_des_tiges(ser_nominale):
    _ok(ser_nominale)
    coh = H.read_kind(ser_nominale["dir"], "cohorts")
    n = ser_nominale["n"] ** 2
    assert int(coh["cell_id"].min()) >= 0 and int(coh["cell_id"].max()) < n
    assert (coh["stems_ha"] > 0).all(), "contrat sim.cohorts : une ligne n'existe que pour une classe qui a des tiges"
