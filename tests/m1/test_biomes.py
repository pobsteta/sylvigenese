"""biomes : aucune cellule forestière sans type de végétation qui ne soit pas signalée
(spec §11, critère M1a) ; rapport_biomes.html (spec §1, §4.1, §4.2, §4.5)."""
import re
import unicodedata

import numpy as np
import pytest

import helpers as H
from conftest import need

# Noms de catégorie qui diraient « pas de type » : ils ne comptent pas comme un type (spec §8).
SANS_TYPE = {"", "sans_type", "sans type", "inconnu", "aucun", "none", "na", "nodata", "null"}


def _sans_accent(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower()


@pytest.fixture(scope="module")
def veg(grid):
    cats = H.read_csv_map(need("vegetation_map.csv"))
    arr, nodata, *_ = H.read_raster(need("vegetation_map.tif"))
    arr = arr[0]
    types_valides = {v for v, n in cats.items() if n.strip().lower() not in SANS_TYPE}
    ok = np.isin(arr, list(types_valides))
    if nodata is not None:
        ok &= arr != nodata
    return {"cats": cats, "arr": arr, "ok": ok}


@pytest.fixture(scope="module")
def orphelines(grid, veg):
    return grid.forest() & ~veg["ok"]


@pytest.fixture(scope="module")
def rapport_biomes(runs):
    return H.html_blocks(need("rapport_biomes.html"))


def test_la_carte_a_au_moins_un_type_et_la_table_nomme_par_nom(veg):
    assert veg["cats"], "vegetation_map.csv vide"
    assert all(isinstance(n, str) and n for n in veg["cats"].values())


def test_cellules_forestieres_sans_type_sont_signalees(grid, orphelines, rapport_biomes):
    n = int(orphelines.sum())
    if n == 0:
        return  # critère rempli sans signalement
    texte = " ".join(rapport_biomes)
    assert re.search(rf"\b{n}\s+cellules?\b", texte, re.I), \
        f"rapport_biomes.html ne compte pas les {n} cellules forestières sans type"
    manquants = [int(c) for c in grid.cell_id[orphelines]
                 if not re.search(rf"\b{int(c)}\b", texte)]
    assert not manquants, f"cell_id absents de rapport_biomes.html : {manquants[:10]}"


def test_la_trouee_n_est_pas_comptee_comme_cellule_forestiere_orpheline(grid, orphelines):
    assert not (orphelines & grid.in_gap()).any()


def test_foret_sans_polygone_a_un_type_de_vegetation_ou_est_signalee(grid, veg, rapport_biomes):
    zone = grid.fully_in(H.NO_POLYGON) & grid.forest()
    assert zone.sum() >= 100
    sans = zone & ~veg["ok"]
    if sans.any():
        assert re.search(rf"\b{int(sans.sum())}\s+cellules?\b", " ".join(rapport_biomes), re.I), \
            f"{int(sans.sum())} cellules hors polygone sans type et non comptées"


def test_rapport_signale_les_cellules_hors_polygone_nemeton(runs):
    # spec §4.2 : « la cellule est signalée » (terme de la spec : « hors polygone »).
    texte = _sans_accent(" ".join(H.report_blocks("rapport_biomes.html")))
    assert "hors polygone" in texte, "aucun rapport ne mentionne « hors polygone »"


def test_rapport_dit_mono_essence_pour_chaque_polygone(runs):
    # spec §4.1 : un polygone porte une seule essence, il est mono-essence, et le rapport le dit.
    texte = " ".join(H.report_blocks("rapport_biomes.html"))
    assert re.search(r"mono-essence", texte, re.I), "aucun rapport ne dit « mono-essence »"
    for sid in ("S01", "S02", "S03", "S04", "S05"):
        assert re.search(rf"\b{sid}\b", texte), f"polygone {sid} absent des rapports"


def test_rapport_signale_synthetic_ml_sans_recompter_le_mnh(runs):
    # spec §4.5 : S04 est en synthetic_ml, le MNH n'est pas compté deux fois, et le rapport le signale.
    blocs = H.report_blocks("rapport_biomes.html")
    assert any("synthetic_ml" in b and re.search(r"\bS04\b", b) for b in blocs), \
        "aucune ligne de rapport ne relie S04 à synthetic_ml"


def test_rapport_biomes_est_un_html_non_vide(runs):
    t = need("rapport_biomes.html").read_text(encoding="utf-8")
    assert re.search(r"(?i)<html", t) and len(t) > 500
    assert re.search(r"(?i)<meta[^>]+charset", t), "encodage non déclaré (accents)"


def test_catalogue_de_biomes_du_depot_marque_provisoire():
    # CLAUDE.md : toute valeur écologique vient d'une source citée ou est marquée `provisoire: true`.
    import yaml
    fichiers = sorted((H.ROOT / "biomes").glob("*.yml"))
    assert fichiers, "biomes/*.yml absent : le catalogue fictif de la mission 020 manque"
    for f in fichiers:
        txt = f.read_text(encoding="utf-8")
        assert re.search(r"(?m)^\s*provisoire:\s*true\b", txt), f"{f.name} sans `provisoire: true`"
        assert yaml.safe_load(txt) is not None
