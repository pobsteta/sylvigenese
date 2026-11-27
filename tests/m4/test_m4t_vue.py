"""Suite de M4a (mission 045) : la vue dans le temps, pilotée par probe_temps.cjs (Playwright de Node, réseau coupé).
  - zone `m4_temps` (sim/ de 15 ans) : `years` = années de l'index, `setYear(a)`, compte des instances année par
    année égal aux vivants, fiche de l'année avec son évolution, captures à deviceScaleFactor 2 en t0 et en dernière
    année (gardées sous data/releves_m4/ pour Pascal, hors dépôt) ;
  - zone de charge synthétique `m4_charge` (T8) : EXACTEMENT 100 000 instances chargées et dessinées en 2023, comptées
    par l'API (100 013 en 2022 : les 13 morts de 2023 ne sont pas dessinés) ; images par seconde relevées, sans seuil.
Le serveur est celui de 030 (`make viewer ZONE=<zone> PORT=<port>`)."""
import json
import math
import re
import subprocess

import pytest

import helpers_m4 as H
import helpers_m4_temps as T
from test_m4_vue import Serveur

PROBE = H.HERE / "probe_temps.cjs"
RELEVES = H.ROOT / "data" / "releves_m4"


def sonde_temps(url: str, cell=None, shots=None, dsf=1) -> dict:
    opts = {"cell": cell, "shots": {str(k): str(v) for k, v in (shots or {}).items()}, "dsf": dsf}
    p = subprocess.run(["node", str(PROBE), url, json.dumps(opts)], capture_output=True, text=True, timeout=1800)
    assert p.returncode == 0 and p.stdout.strip(), f"sonde Playwright en échec (code {p.returncode}) :\n{p.stderr[-1500:]}"
    return json.loads(p.stdout)


def _servir(nom, **kw):
    srv = Serveur(nom)
    try:
        srv.attendre()
        return sonde_temps(srv.url, **kw)
    finally:
        srv.arreter()


@pytest.fixture(scope="module")
def cellule_suivie(temps_cells):
    ys = T.retained_years(T.T0, T.YEARS, T.STEP)
    return next(c for c in sorted({c for c, _ in temps_cells}) if all((c, y) in temps_cells for y in ys))


@pytest.fixture(scope="module")
def vue_temps(temps, temps_index, cellule_suivie):
    T.exige_temps(temps)
    RELEVES.mkdir(parents=True, exist_ok=True)
    ys = [e["year"] for e in temps_index["years"]]
    shots = {ys[0]: RELEVES / f"vue_{ys[0]}_dsf2.png", ys[-1]: RELEVES / f"vue_{ys[-1]}_dsf2.png"}
    for p in shots.values():
        p.unlink(missing_ok=True)
    res = _servir(temps["name"], cell=cellule_suivie, shots=shots, dsf=2)
    res["shots"] = shots
    (RELEVES / "temps.json").write_text(json.dumps({k: v for k, v in res.items() if k not in ("bodyText", "sheets", "shots")},
                                                   indent=1, default=str), encoding="utf-8")
    return res


@pytest.fixture(scope="module")
def vue_charge(charge):
    T.exige_charge(charge)
    RELEVES.mkdir(parents=True, exist_ok=True)
    res = _servir(charge["name"], dsf=1)
    (RELEVES / "charge.json").write_text(json.dumps({k: v for k, v in res.items() if k not in ("bodyText", "sheets")},
                                                    indent=1, default=str), encoding="utf-8")
    return res


def _sans_erreur(vue):
    assert "fatal" not in vue, vue.get("fatal")
    assert vue["state"]["error"] is None and vue["state"]["ready"] is True, vue["state"]
    assert vue["errors"] == [], f"erreurs de la page : {vue['errors'][:3]}"


# ------------------------------------------------------------------ zone m4_temps
def test_la_page_charge_sans_erreur_avec_sim(vue_temps):
    _sans_erreur(vue_temps)


def test_years_expose_les_annees_de_l_index(vue_temps, temps_index):
    assert vue_temps["state"]["hasSetYear"] is True, "window.sylvigenese.setYear absent"
    assert vue_temps["state"]["years"] == [e["year"] for e in temps_index["years"]], vue_temps["state"]["years"]


def test_set_year_affiche_l_annee_et_compte_ses_vivants(vue_temps, temps_index):
    for e in temps_index["years"]:
        r = vue_temps["perYear"].get(str(e["year"])) or vue_temps["perYear"].get(e["year"])
        assert r is not None, f"année {e['year']} non parcourue par la sonde"
        assert "fatal" not in r and r["error"] is None, r
        assert r["year"] == e["year"]
        assert r["instanceCount"] == e["instances"], f"{e['year']} : instanceCount {r['instanceCount']} != {e['instances']} vivants"
    comptes = {r["instanceCount"] for r in vue_temps["perYear"].values()}
    assert len(comptes) == len(temps_index["years"]), f"le compte ne change pas avec l'année : {comptes}"


def test_les_images_par_seconde_sont_relevees_pour_chaque_annee(vue_temps):
    for a, r in vue_temps["perYear"].items():
        assert isinstance(r.get("fps"), (int, float)) and math.isfinite(r["fps"]) and r["fps"] > 0, f"{a} : fps {r.get('fps')!r}"


def test_les_captures_dsf2_en_t0_et_en_derniere_annee(vue_temps):
    import struct
    for a, p in vue_temps["shots"].items():
        assert p.is_file() and p.stat().st_size > 5000, f"capture {p} absente ou vide"
        w, h = struct.unpack(">II", p.read_bytes()[16:24])
        assert (w, h) == (2560, 1600), f"{p.name} : {w} x {h}, deviceScaleFactor 2 attendu (2560 x 1600)"


def test_la_fiche_de_l_annee_montre_son_evolution(vue_temps, temps_index, temps_cells, cellule_suivie):
    ys = [e["year"] for e in temps_index["years"]]
    for a in ys:
        f = vue_temps["sheets"].get(str(a)) or vue_temps["sheets"].get(a)
        assert f is not None, f"fiche non ouverte en {a}"
        assert f["cellId"] == str(cellule_suivie)
        txt = f["text"]
        t = H.sans_accent(txt)
        for y in ys:
            assert str(y) in txt, f"fiche ouverte en {a} : l'année {y} manque au tableau d'évolution"
        assert "provisoire" in t and H.sans_accent(T.MENTION_ECO) in t, f"{a} : mentions absentes"
        assert H.sans_accent(T.MENTION_VC) in t, f"{a} : « {T.MENTION_VC} » absente"
        assert "plafond" in t, f"{a} : le plafond n'est pas à côté de H_dom (Q1)"
        for y in ys:
            hd = T.expected_year(temps_cells.get((cellule_suivie, y)))["h_dom_m"]
            s1 = f"{hd:.1f}"
            assert s1 in txt or s1.replace(".", ",") in txt, f"fiche en {a} : H_dom {s1} m de {y} absente"
        m = re.search(r"tools/viewer-massif\s+--\s+--zone\s+data/\S+\s+--x\s+\d+(?:[.,]\d+)?\s+--y\s+\d+(?:[.,]\d+)?\s+--year\s+(\d{4})", txt)
        assert m and int(m.group(1)) == a, f"{a} : commande viewer-massif absente ou à une autre année"


def test_la_carte_de_g_porte_la_mention_non_validee(vue_temps):
    t = H.sans_accent(vue_temps.get("bodyText", ""))
    assert H.sans_accent(T.MENTION_ECO) in t and ("m2/ha" in t or "m²/ha" in vue_temps.get("bodyText", "")), \
        "légende de la carte de surface terrière (m²/ha, « non validée écologiquement ») absente de la page"


def test_la_vue_ne_depend_pas_du_reseau_avec_sim(vue_temps):
    assert vue_temps["state"]["ready"] is True


# ------------------------------------------------------------------ zone de charge (T8)
def test_la_page_de_charge_charge_sans_erreur(vue_charge):
    _sans_erreur(vue_charge)
    assert vue_charge["state"]["years"] == [2022, 2023]


def test_exactement_100000_instances_dessinees_comptees_par_l_api(vue_charge):
    r = vue_charge["perYear"].get("2023") or vue_charge["perYear"].get(2023)
    assert r is not None and "fatal" not in r and r["error"] is None, r
    assert r["instanceCount"] == 100_000, f"2023 : instanceCount = {r['instanceCount']}"


def test_les_13_morts_ne_sont_pas_dessines_dans_la_vue(vue_charge):
    r = vue_charge["perYear"].get("2022") or vue_charge["perYear"].get(2022)
    assert r is not None and r["instanceCount"] == T.CHARGE_VIVANTS[2022], r


def test_les_images_par_seconde_sont_relevees_sur_la_charge(vue_charge):
    for a, r in vue_charge["perYear"].items():
        assert isinstance(r.get("fps"), (int, float)) and math.isfinite(r["fps"]) and r["fps"] > 0, f"{a} : fps {r.get('fps')!r}"
