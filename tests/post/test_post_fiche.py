"""Fiche de cellule v3 écrite par assets quand sim/summary.parquet existe (contrat cell_sheet v3, mission 051 ;
décisions Q1, Q3 à Q5) : mêmes chiffres que le summary, « volume partiel » dès qu'une part est non calculée, mentions
exigées, null avec sa raison quand rien n'est calculé, tarif et commit cités."""
import math

import pytest

import helpers_post as P

H, T = P.H, P.T
ANNEES_BASE = T.retained_years(P.T0, P.YEARS, P.STEP)
ANNEES_ECH = T.retained_years(P.MINI_YEARS[0], len(P.MINI_YEARS) - 1, P.STEP)


def proche(a, b, rel=P.TOL):
    return a is not None and b is not None and math.isclose(float(a), float(b), rel_tol=rel, abs_tol=1e-9)


def fiches(res):
    assert res["assets"].returncode == 0, "assets après post :\n" + P.queue(res["assets"])
    assert (res["dir"] / "sim" / "summary.parquet").is_file(), "sim/summary.parquet absent : pas de fiche v3 possible"
    sh = H.read_sheets(res["dir"])
    assert sh, "aucune fiche web/cells/*.json"
    v = sorted({s.get("schema_version") for s in sh.values()})
    assert v == [3], f"fiches en version {v} : la v3 est exigée dès que sim/summary.parquet existe"
    return sh


def attendu_annee(summary, cells_rows, cid, year):
    """Ce que l'année d'une cellule doit porter, depuis summary et sim/cells (somme sur les essences)."""
    lignes = {sp: r for (c, y, sp), r in summary.items() if c == cid and y == year}
    g = {str(r["species"]): float(r["basal_area_m2_ha"]) for r in cells_rows.get((cid, year), [])}
    if not lignes:
        return {"volume": 0.0, "carbon": 0.0, "roots": 0.0, "share": 0.0, "nc": 0.0, "comp": {}}
    gt = sum(g.values())
    gnc = sum(r["basal_area_not_computed_share"] * g[sp] for sp, r in lignes.items())
    share = 1.0 if all(r["basal_area_not_computed_share"] == 1.0 for r in lignes.values()) else (gnc / gt if gt else 0.0)
    return {"volume": sum(r["volume_m3_ha"] for r in lignes.values()),
            "carbon": sum(r["carbon_t_ha"] for r in lignes.values()),
            "roots": sum(r.get("carbon_roots_t_ha", 0.0) for r in lignes.values()),
            "share": share, "nc": sum(r["stems_not_computed_ha"] for r in lignes.values()),
            "comp": lignes}


def verifier(sheets, summary, cells_rows, annees, tarif_commit):
    faux = []
    for stem, s in sheets.items():
        if s.get("schema_version") != 3:
            faux.append((stem, "schema_version", s.get("schema_version")))
            continue
        if s.get("tarif", {}).get("commit") != tarif_commit or s["tarif"].get("provisoire") is not True:
            faux.append((stem, "tarif", s.get("tarif")))
        for c in s["cells"]:
            ys = [e["year"] for e in c["years"]]
            if ys != annees:
                faux.append((stem, c["cell_id"], "années", ys))
                continue
            for e in c["years"]:
                a = attendu_annee(summary, cells_rows, c["cell_id"], e["year"])
                key = (c["cell_id"], e["year"])
                if abs(e["basal_area_not_computed_share"] - a["share"]) > 1e-9:
                    faux.append((key, "part", e["basal_area_not_computed_share"], a["share"]))
                if e["volume_partiel"] is not (a["share"] > 0):
                    faux.append((key, "volume_partiel", e["volume_partiel"], a["share"]))
                if not (proche(e["stems_not_computed_ha"], a["nc"]) or e["stems_not_computed_ha"] == a["nc"] == 0):
                    faux.append((key, "stems_not_computed_ha", e["stems_not_computed_ha"], a["nc"]))
                if a["share"] == 1.0:
                    if e["volume_m3_ha"] is not None or e["carbon_t_ha"] is not None or not e.get("not_computed_reason"):
                        faux.append((key, "rien de calculé : null et raison attendus", e["volume_m3_ha"], e.get("not_computed_reason")))
                else:
                    if not (proche(e["volume_m3_ha"], a["volume"]) or e["volume_m3_ha"] == a["volume"] == 0):
                        faux.append((key, "volume_m3_ha", e["volume_m3_ha"], a["volume"]))
                    if not (proche(e["carbon_t_ha"], a["carbon"]) or e["carbon_t_ha"] == a["carbon"] == 0):
                        faux.append((key, "carbon_t_ha", e["carbon_t_ha"], a["carbon"]))
                    if any("carbon_roots_t_ha" in r for r in a["comp"].values()):
                        rv = e.get("root_carbon_t_ha")
                        if not (proche(rv, a["roots"]) or rv == a["roots"] == 0):
                            faux.append((key, "root_carbon_t_ha", rv, a["roots"]))
                comp = {x["species"]: x for x in e["composition"]}
                if set(comp) != set(a["comp"]):
                    faux.append((key, "essences", sorted(comp), sorted(a["comp"])))
                    continue
                for sp, r in a["comp"].items():
                    x = comp[sp]
                    if abs(x["basal_area_not_computed_share"] - r["basal_area_not_computed_share"]) > 1e-9:
                        faux.append((key, sp, "part", x["basal_area_not_computed_share"]))
                    if r["basal_area_not_computed_share"] == 1.0:
                        if x["volume_m3_ha"] is not None or x["carbon_t_ha"] is not None:
                            faux.append((key, sp, "null attendu", x["volume_m3_ha"]))
                    elif not ((proche(x["volume_m3_ha"], r["volume_m3_ha"]) or x["volume_m3_ha"] == r["volume_m3_ha"] == 0)
                              and (proche(x["carbon_t_ha"], r["carbon_t_ha"]) or x["carbon_t_ha"] == r["carbon_t_ha"] == 0)):
                        faux.append((key, sp, "volume/carbone", x["volume_m3_ha"], r["volume_m3_ha"]))
    return faux


# ------------------------------------------------------------------ zone simulée
@pytest.fixture(scope="module")
def base_fiches(base, base_dir):
    return fiches(base)


def test_les_fiches_v3_sont_conformes_au_validateur(base_fiches, base_dir):
    assert all(s.get("schema_version") == 3 for s in base_fiches.values()), \
        sorted({s.get("schema_version") for s in base_fiches.values()})
    p = H.validate("cell_sheet", *[str(p) for p in sorted((base_dir / "web" / "cells").glob("*.json"))])
    assert p.returncode == 0, p.stdout[-2000:] + p.stderr[-1000:]


def test_les_fiches_v3_recopient_le_summary(base_fiches, base_dir):
    summary = P.read_summary(base_dir)
    cells = T.cell_year_table(T.cells_rows(base_dir, ANNEES_BASE))
    commit = P.read_post_json(base_dir)["tarif_commit"]
    faux = verifier(base_fiches, summary, cells, ANNEES_BASE, commit)
    assert not faux, f"{len(faux)} écarts, ex. {faux[:4]}"


def test_les_mentions_exigees_sont_dans_les_notes(base_fiches):
    partiel = any(e["volume_partiel"] for s in base_fiches.values() for c in s["cells"] for e in c["years"])
    assert partiel, "garde-fou : la zone simulée a des tiges hors domaine, au moins une année doit être partielle"
    for stem, s in base_fiches.items():
        notes = s.get("notes", [])
        for m in (P.MENTION_ECO, P.MENTION_VOLUME, P.MENTION_CARBONE, P.MENTION_SOL):
            assert any(m in n for n in notes), f"{stem} : « {m} » absente des notes {notes}"
        assert not any(P.MENTION_V2 in n for n in notes), f"{stem} : « {P.MENTION_V2} » encore là"
        if any(e["volume_partiel"] for c in s["cells"] for e in c["years"]):
            assert any(P.MENTION_PARTIEL in n for n in notes), f"{stem} : « {P.MENTION_PARTIEL} » absente"
        if any("root_carbon_t_ha" in e for c in s["cells"] for e in c["years"]):
            assert any(P.MENTION_RACINES in n for n in notes), f"{stem} : « {P.MENTION_RACINES} » absente"


def test_le_carbone_des_racines_est_dans_la_fiche_et_jamais_additionne(base_fiches, base_dir):
    summary = P.read_summary(base_dir)
    cells = T.cell_year_table(T.cells_rows(base_dir, ANNEES_BASE))
    n = 0
    for s in base_fiches.values():
        for c in s["cells"]:
            for e in c["years"]:
                a = attendu_annee(summary, cells, c["cell_id"], e["year"])
                if a["comp"] and e["volume_m3_ha"] is not None:
                    assert "root_carbon_t_ha" in e, (c["cell_id"], e["year"])
                    assert e["provisoire"] is True
                    assert proche(e["carbon_t_ha"], a["carbon"]) or e["carbon_t_ha"] == a["carbon"] == 0
                    n += 1
    assert n > 0


def test_aucune_grandeur_hors_contrat(base_fiches):
    interdits = ("co2", "bois_fort", "sup7", "soil", "deadwood")
    for stem, s in base_fiches.items():
        for c in s["cells"]:
            for e in c["years"]:
                assert not [k for k in e if any(i in k.lower() for i in interdits)], (stem, sorted(e))


# ------------------------------------------------------------------ zone échantillon
@pytest.fixture(scope="module")
def ech_fiches(ech, ech_dir):
    return fiches(ech)


def test_fiches_de_l_echantillon_conformes_et_egales_au_summary(ech_fiches, ech_dir):
    p = H.validate("cell_sheet", *[str(p) for p in sorted((ech_dir / "web" / "cells").glob("*.json"))])
    assert p.returncode == 0, p.stdout[-2000:] + p.stderr[-1000:]
    faux = verifier(ech_fiches, P.read_summary(ech_dir), T.cell_year_table(T.cells_rows(ech_dir)), ANNEES_ECH, "0000000")
    assert not faux, faux[:4]


def test_fiche_du_point_connu(ech_fiches):
    c = H.sheet_cells(ech_fiches)[0]
    for e in c["years"]:
        assert proche(e["volume_m3_ha"], 1.8471724842550155 / 0.0625), e["volume_m3_ha"]   # 29,55476 m³/ha
        assert proche(e["carbon_t_ha"], 1.8471724842550155 * 0.09 / 0.0625)
        assert e["volume_partiel"] is True and e["basal_area_not_computed_share"] > 0     # la recrue de 7,5 cm


def test_fiche_d_une_cellule_sans_aucun_arbre_calcule(ech_fiches, ech):
    cid = P.mini_cells(ech["dir"])[1]           # deux chênes hors domaine
    c = H.sheet_cells(ech_fiches)[cid]
    for e in c["years"]:
        assert e["basal_area_not_computed_share"] == 1.0
        assert e["volume_m3_ha"] is None and e["carbon_t_ha"] is None, "rien n'est calculé : null, jamais 0"
        assert e.get("not_computed_reason"), "null sans sa raison"
        assert e["volume_partiel"] is True


def test_fiche_d_une_cellule_sans_arbre_vivant(ech_fiches, ech):
    cid = P.mini_cells(ech["dir"])[3]           # ses deux hêtres meurent en 2023
    e = {x["year"]: x for x in H.sheet_cells(ech_fiches)[cid]["years"]}[2023]
    assert e["volume_m3_ha"] == 0 and e["carbon_t_ha"] == 0, "cellule vide : 0, fait arithmétique"
    assert e["basal_area_not_computed_share"] == 0 and e["volume_partiel"] is False
    assert e["stems_not_computed_ha"] == 0


def test_sans_racines_la_fiche_n_a_pas_de_carbone_des_racines(ech_sans_racines):
    sh = fiches(ech_sans_racines)
    for s in sh.values():
        assert s["schema_version"] == 3
        for c in s["cells"]:
            for e in c["years"]:
                assert "root_carbon_t_ha" not in e, (c["cell_id"], e["year"])
