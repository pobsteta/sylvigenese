"""La fiche v3 dans le navigateur (mission 057, reprise de la relecture de la PR n° 10 : « vue v3 sans test
navigateur »). Contrat : contracts/json/cell_sheet.schema.json v3 ; décisions de Pascal Q3 à Q5 du 26/11/2026.

Chaîne : zone échantillon `post_ech` de conftest.py (aucune année simulée : sim/ de 2022 et 2023 écrit par l'aide de
test), post, puis assets (fiches v3), puis la vue (`make viewer`), pilotée par probe_fiche_v3.cjs (Playwright de Node,
réseau coupé). Pour chaque année et pour cinq cellules choisies, la sonde ouvre la fiche ; le test vérifie que la vue
affiche, pour l'année :
  - le volume aérien total et le carbone aérien, égaux à ceux de la fiche JSON (web/cells) ;
  - « volume partiel » avec la part de G non calculée, quand elle est > 0 ;
  - « non calculé » avec la raison, quand la valeur est null ;
  - les racines à part et « provisoire », quand l'année les porte ;
  - les mentions « sol et bois mort » et « non validée écologiquement ».
Captures à deviceScaleFactor 2, gardées sous data/releves_post/ (hors dépôt), comme les relevés de tests/m4.

CONVENTIONS DE LECTURE (le contrat ne fixe pas la mise en forme ; ce qui suit est la règle du test) :
  - la fiche porte un tableau d'évolution : une ligne par année (première case = l'année) et une colonne par grandeur,
    reconnue à son en-tête : « volume aérien total », « carbone aérien », « racines » ; « de l'année » = la case
    (ligne de l'année, colonne de la grandeur) ;
  - un nombre y est « affiché » égal à la valeur de la fiche JSON s'il vaut cette valeur arrondie (ou tronquée) à la
    précision affichée, virgule ou point décimal, espaces de milliers admises ; au moins une décimale pour les m³/ha
    et les tC/ha (30,96 s'écrit 31,0, pas 31) ;
  - une part s'affiche en pourcentage, à l'unité au moins (3 % pour 0,034), ou en fraction à deux décimales au moins.
"""
import json
import math
import re
import struct
import subprocess
import sys

import pytest

import helpers_post as P

H = P.H
sys.path.insert(0, str(P.M4))
from test_m4_vue import Serveur  # noqa: E402

PROBE = P.HERE / "probe_fiche_v3.cjs"
RELEVES = H.ROOT / "data" / "releves_post"
NUM = re.compile(r"(?<![\w.,])-?\d{1,3}(?:[   ]\d{3})+(?:[.,]\d+)?|(?<![\w.,])-?\d+(?:[.,]\d+)?")


PETIT = re.compile(r"<\s*0[.,]1(?!\d)")


def nombres(texte: str) -> list[tuple[float, int]]:
    """(valeur, nombre de décimales) de chaque nombre du texte."""
    out = []
    for m in NUM.finditer(texte or ""):
        t = re.sub(r"[ \u00a0\u202f]", "", m.group(0)).replace(",", ".")
        k = len(t.split(".")[1]) if "." in t else 0
        out.append((float(t), k))
    return out


def affiche(texte: str, v: float, decimales_min: int = 1) -> bool:
    """v est-il écrit dans texte, arrondi ou tronqué à la précision affichée (au moins `decimales_min` décimales) ?
    Règle de l'orchestrateur (mission 056, « signaler plutôt que deviner ») pour les grandeurs à une décimale : une
    valeur > 0 et < 0,05 s'écrit exactement « < 0,1 », jamais « 0,0 » ; une valeur nulle s'écrit « 0,0 », jamais « < 0,1 »."""
    texte = texte or ""
    if decimales_min == 1:
        petit = PETIT.search(texte) is not None
        if 0 < v < 0.05:
            return petit
        if v == 0:
            return not petit and any(n == 0 and k >= 1 for n, k in nombres(texte))
        texte = PETIT.sub(" ", texte)          # « < 0,1 » n'est pas l'écriture d'une valeur de 0,05 ou plus
    for n, k in nombres(texte):
        if k < decimales_min:
            continue
        pas = 10.0 ** (-k)
        if abs(n - v) <= pas * (1 + 1e-9) and (abs(n - v) <= pas / 2 * (1 + 1e-9) or abs(n) <= abs(v)):
            return True
    return False


def affiche_part(texte: str, part: float) -> bool:
    for m in re.finditer(r"(\d+(?:[.,]\d+)?)\s*%", texte or ""):
        if affiche(m.group(1), 100 * part, decimales_min=0):
            return True
    return affiche(texte, part, decimales_min=2)


def colonne(rec: dict, mot: str) -> int:
    rows = rec.get("rows") or []
    assert rows, f"la fiche n'a pas de tableau d'évolution : {rec.get('text', '')[:300]}"
    j = [i for i, c in enumerate(rows[0]) if norm(mot) in norm(c)]
    assert len(j) == 1, f"colonne « {mot} » introuvable ou en double dans l'en-tête {rows[0]}"
    return j[0]


def case(rec: dict, annee: int, mot: str) -> str:
    """Case (ligne de l'année, colonne dont l'en-tête contient `mot`) du tableau d'évolution de la fiche."""
    j = colonne(rec, mot)
    lignes = [r for r in rec["rows"][1:] if r and r[0].strip() == str(annee)]
    assert len(lignes) == 1, f"ligne de l'année {annee} absente ou en double : {rec['rows']}"
    assert len(lignes[0]) > j, lignes[0]
    return lignes[0][j]


def non_calcule(x: str) -> bool:
    """« non calculé » (et non « G non calculée ») dans x."""
    return re.search(r"\bnon calcule\b", norm(x)) is not None


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", H.sans_accent(s or "")).strip()


def sonde(url: str, cells: list[int], shots: dict, dsf: int = 2) -> dict:
    opts = {"cells": cells, "dsf": dsf, "shots": {k: str(v) for k, v in shots.items()}}
    p = subprocess.run(["node", str(PROBE), url, json.dumps(opts)], capture_output=True, text=True, timeout=1800)
    assert p.returncode == 0 and p.stdout.strip(), f"sonde Playwright en échec (code {p.returncode}) :\n{p.stderr[-1500:]}"
    return json.loads(p.stdout)


# ------------------------------------------------------------------ chaîne : post, assets, vue
@pytest.fixture(scope="module")
def cellules(ech):
    return P.mini_cells(ech["dir"])


@pytest.fixture(scope="module")
def fiches_json(ech, ech_dir):
    assert ech["assets"].returncode == 0, "assets après post :\n" + P.queue(ech["assets"])
    sh = H.read_sheets(ech_dir)
    assert sh and {s.get("schema_version") for s in sh.values()} == {3}, \
        f"fiches v3 attendues : {sorted({s.get('schema_version') for s in sh.values()})}"
    return sh


@pytest.fixture(scope="module")
def vue(ech, fiches_json, cellules):
    RELEVES.mkdir(parents=True, exist_ok=True)
    shots = {}
    for a in P.MINI_YEARS:
        for c in (cellules[0], cellules[1]):
            shots[f"{a}:{c}"] = RELEVES / f"fiche_v3_{a}_cellule_{c}_dsf2.png"
    for p in shots.values():
        p.unlink(missing_ok=True)
    srv = Serveur(ech["name"])
    try:
        srv.attendre()
        res = sonde(srv.url, list(cellules), shots, dsf=2)
    finally:
        srv.arreter()
    res["shot_paths"] = shots
    (RELEVES / "fiche_v3.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    return res


def fiche(vue, annee, cell) -> dict:
    a = vue["sheets"].get(str(annee)) or vue["sheets"].get(annee) or {}
    assert "fatal" not in a, f"{annee} : {a.get('fatal')}"
    rec = a.get(str(cell)) or a.get(cell)
    assert rec is not None, f"fiche de la cellule {cell} non ouverte en {annee}"
    assert "fatal" not in rec, f"{annee}, cellule {cell} : {rec['fatal']}"
    assert rec["cellId"] == str(cell)
    return rec


def entree(fiches_json, cell, annee) -> dict:
    c = H.sheet_cells(fiches_json)[cell]
    return {e["year"]: e for e in c["years"]}[annee]


CAS = [(a, k) for a in P.MINI_YEARS for k in range(5)]


# ------------------------------------------------------------------ tests
def test_la_page_charge_sans_erreur_et_sans_reseau(vue):
    assert "fatal" not in vue, vue.get("fatal")
    assert vue["state"]["error"] is None and vue["state"]["ready"] is True, vue["state"]
    assert vue["errors"] == [], vue["errors"][:3]
    assert vue["state"]["years"] == list(P.MINI_YEARS), vue["state"]["years"]


def test_les_cas_de_la_zone_sont_bien_la(fiches_json, cellules):
    """Garde-fou : la zone échantillon porte un volume partiel, un « non calculé », des racines et une cellule vide."""
    e0 = entree(fiches_json, cellules[0], 2022)
    e1 = entree(fiches_json, cellules[1], 2022)
    e3 = entree(fiches_json, cellules[3], 2023)
    assert e0["volume_partiel"] is True and 0 < e0["basal_area_not_computed_share"] < 1 and "root_carbon_t_ha" in e0
    assert e1["volume_m3_ha"] is None and e1["carbon_t_ha"] is None and e1.get("not_computed_reason")
    assert e3["volume_m3_ha"] == 0 and e3["volume_partiel"] is False


@pytest.mark.parametrize("annee,k", CAS)
def test_volume_et_carbone_de_l_annee_egaux_a_la_fiche(vue, fiches_json, cellules, annee, k):
    cell = cellules[k]
    rec, e = fiche(vue, annee, cell), entree(fiches_json, cell, annee)
    colonne(rec, P.MENTION_VOLUME), colonne(rec, P.MENTION_CARBONE)      # libellés exacts du contrat (Q3, Q4)
    if e["volume_m3_ha"] is None:
        return                                                          # cas « non calculé », test suivant
    v, c = case(rec, annee, P.MENTION_VOLUME), case(rec, annee, P.MENTION_CARBONE)
    assert affiche(v, e["volume_m3_ha"]), f"{annee}, cellule {cell} : volume {e['volume_m3_ha']} absent de « {v} »"
    assert affiche(c, e["carbon_t_ha"]), f"{annee}, cellule {cell} : carbone {e['carbon_t_ha']} absent de « {c} »"
    assert not non_calcule(v) and not non_calcule(c), f"{annee}, cellule {cell} : « non calculé » pour un nombre"


@pytest.mark.parametrize("annee,k", CAS)
def test_volume_partiel_avec_la_part_de_g_non_calculee(vue, fiches_json, cellules, annee, k):
    cell = cellules[k]
    rec, e = fiche(vue, annee, cell), entree(fiches_json, cell, annee)
    v = case(rec, annee, P.MENTION_VOLUME)
    if not e["basal_area_not_computed_share"] > 0:
        assert norm(P.MENTION_PARTIEL) not in norm(v), f"{annee}, cellule {cell} : « volume partiel » sans part non calculée"
        return
    assert norm(P.MENTION_PARTIEL) in norm(v), f"{annee}, cellule {cell} : « volume partiel » absent de « {v} »"
    assert affiche_part(v, e["basal_area_not_computed_share"]), \
        f"{annee}, cellule {cell} : part de G non calculée {e['basal_area_not_computed_share']} absente de « {v} »"


@pytest.mark.parametrize("annee,k", CAS)
def test_non_calcule_avec_la_raison_quand_la_valeur_est_null(vue, fiches_json, cellules, annee, k):
    cell = cellules[k]
    rec, e = fiche(vue, annee, cell), entree(fiches_json, cell, annee)
    if e["volume_m3_ha"] is not None:
        return
    for mot in (P.MENTION_VOLUME, P.MENTION_CARBONE):
        x = case(rec, annee, mot)
        assert non_calcule(x), f"{annee}, cellule {cell} : « non calculé » absent de la case « {mot} » : « {x} »"
        assert not [n for n, _ in nombres(re.sub(r"\d+\s*%", "", x)) if n == 0], f"null affiché comme 0 : « {x} »"
    assert norm(e["not_computed_reason"]) in norm(rec["text"]), \
        f"{annee}, cellule {cell} : raison « {e['not_computed_reason']} » absente de la fiche"


@pytest.mark.parametrize("annee,k", CAS)
def test_racines_a_part_et_provisoires(vue, fiches_json, cellules, annee, k):
    cell = cellules[k]
    rec, e = fiche(vue, annee, cell), entree(fiches_json, cell, annee)
    if "root_carbon_t_ha" not in e:
        return
    j = colonne(rec, P.MENTION_RACINES)
    assert "provisoire" in norm(rec["rows"][0][j]), f"en-tête des racines sans « provisoire » : {rec['rows'][0][j]}"
    assert j != colonne(rec, P.MENTION_CARBONE), "racines dans la colonne du carbone aérien"
    r = case(rec, annee, P.MENTION_RACINES)
    if e["root_carbon_t_ha"] is None:
        assert non_calcule(r), f"{annee}, cellule {cell} : racines null sans « non calculé » : « {r} »"
        return
    assert affiche(r, e["root_carbon_t_ha"]), f"{annee}, cellule {cell} : racines {e['root_carbon_t_ha']} absentes de « {r} »"
    # à part, jamais additionné : la case du carbone aérien porte le seul carbone aérien
    c = case(rec, annee, P.MENTION_CARBONE)
    if e["root_carbon_t_ha"] >= 0.1:
        assert not affiche(c, e["carbon_t_ha"] + e["root_carbon_t_ha"]), f"{annee}, cellule {cell} : racines additionnées : « {c} »"


@pytest.mark.parametrize("annee,k", CAS)
def test_mentions_sol_et_bois_mort_et_non_validee(vue, cellules, annee, k):
    t = norm(fiche(vue, annee, cellules[k])["text"])
    assert norm(P.MENTION_SOL) in t, "« sol et bois mort » absent de la fiche"
    assert norm(P.MENTION_ECO) in t, "« non validée écologiquement » absent de la fiche"
    assert norm(P.MENTION_V2) not in t, f"« {P.MENTION_V2} » encore affiché avec une fiche v3"


def test_captures_a_device_scale_factor_2(vue):
    for k, p in vue["shot_paths"].items():
        assert p.is_file() and p.stat().st_size > 5000, f"capture {p} absente ou vide"
        w, h = struct.unpack(">II", p.read_bytes()[16:24])
        assert (w, h) == (2560, 1600), f"{p.name} : {w} x {h}, deviceScaleFactor 2 attendu (2560 x 1600)"


# ------------------------------------------------------------------ la règle de lecture elle-même (vert sans la vue)
def test_la_regle_de_lecture_des_nombres():
    assert affiche("V 30,96 m³/ha", 30.963537) and affiche("V 31,0", 30.963537) and affiche("V 30.9", 30.963537)
    assert not affiche("V 31", 30.963537), "une décimale au moins"
    assert not affiche("V 31,1", 30.963537) and not affiche("V 29,5", 30.963537) and not affiche("2022", 30.963537)
    assert affiche("1 234,5", 1234.5) and affiche("0,57", 0.5689) and affiche("0,6", 0.5689)
    # valeur positive sous la précision affichée : « < 0,1 », jamais « 0,0 » ; zéro : « 0,0 », jamais « < 0,1 »
    assert affiche("< 0,1", 0.0197) and affiche("<0,1 tC/ha", 0.0197)
    assert not affiche("0,0", 0.0197), "0,0 pour une valeur non nulle"
    assert affiche("0,0", 0.0) and not affiche("< 0,1", 0.0), "« < 0,1 » pour une valeur nulle"
    assert not affiche("< 0,1", 0.08) and affiche("0,1", 0.08)
    assert affiche_part("volume partiel : 3 % de G", 0.0339) and affiche_part("3,4 %", 0.0339)
    assert affiche_part("part 0,034", 0.0339) and affiche_part("100 % de G", 1.0)
    assert not affiche_part("4 %", 0.0339) and not affiche_part("0,3", 0.0339)
    assert non_calcule("non calculé") and not non_calcule("3 % de G non calculée")
    rec = {"rows": [["Année", "Volume aérien total m³/ha", "Carbone aérien tC/ha"], ["2022", "29,6", "2,7"]]}
    assert case(rec, 2022, P.MENTION_VOLUME) == "29,6" and case(rec, 2022, P.MENTION_CARBONE) == "2,7"
    assert math.isclose(nombres("a 1 234,5 b")[0][0], 1234.5)
