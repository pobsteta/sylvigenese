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
    # Sur le jeu fictif, il peut n'y avoir aucune orpheline : le contrôle discriminant est
    # test_variante_cellules_orphelines_listees_dans_la_section_sans_type (zone variante).
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


def test_rapport_signale_les_cellules_hors_polygone_nemeton(grid):
    # spec §4.2 : « la cellule est signalée ». Les cellules forestières hors de tout polygone
    # (x 350-650, y 0-500 : 12 x 20 = 240 cellules de 25 m, moins les 64 de la trouée = 176) sont
    # comptées ou listées dans la section / les lignes « hors polygone », pas ailleurs.
    cellules = grid.in_rect(H.NO_POLYGON) & grid.forest()
    n = int(cellules.sum())
    assert n == 176, n
    texte = H.section_text(need("rapport_biomes.html"), "hors polygone")
    assert texte, "aucune section ni ligne « hors polygone » dans rapport_biomes.html"
    compte = re.search(rf"\b{n}\b", texte)
    liste = all(re.search(rf"\b{int(c)}\b", texte) for c in grid.cell_id[cellules])
    assert compte or liste, \
        f"la section « hors polygone » ne donne ni le compte ({n}) ni les cell_id des {n} cellules"


def test_rapport_dit_mono_essence_pour_chaque_polygone(runs):
    # spec §4.1 : un polygone porte une seule essence, il est mono-essence, et le rapport le dit :
    # chaque stand_id est lié à « mono-essence » dans le même bloc (ligne ou item).
    blocs = H.report_blocks("rapport_biomes.html")
    for s in H.read_stands():
        sid = s["stand_id"]
        assert any(re.search(rf"\b{sid}\b", b) and re.search(r"mono-essence", b, re.I)
                   for b in blocs), f"{sid} n'est pas lié à « mono-essence » dans rapport_biomes.html"


def test_rapport_signale_synthetic_ml_sans_recompter_le_mnh(runs):
    # spec §4.5 : S04 est en synthetic_ml, le MNH n'est pas compté deux fois, et le rapport le signale.
    blocs = H.report_blocks("rapport_biomes.html")
    assert any("synthetic_ml" in b and re.search(r"\bS04\b", b) for b in blocs), \
        "aucune ligne de rapport ne relie S04 à synthetic_ml"
    autres = [b for b in blocs if "synthetic_ml" in b and re.search(r"\bS0[1235]\b", b)
              and not re.search(r"\bS04\b", b)]
    assert not autres, f"synthetic_ml attribué à un autre polygone : {autres[:2]}"


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


def test_variante_cellules_orphelines_listees_dans_la_section_sans_type(orphan_zone, grid):
    # Variante : un bloc de station_type.tif sans valeur (nodata) au milieu de S02. Chaque cellule
    # forestière du bloc, sans type de végétation ou comblée, doit être dite dans la bonne section
    # de rapport_biomes.html (spec §1 : « cellules sans type de végétation, comblements »).
    d = orphan_zone["dir"]
    for k in ("prepare", "biomes"):
        assert orphan_zone[k].returncode == 0, \
            f"{k} : code {orphan_zone[k].returncode}\n{orphan_zone[k].stderr[-1500:]}"
    from conftest import ORPHAN_BLOCK
    g = H.Grid(d / "grid.tif")
    cats = H.read_csv_map(d / "vegetation_map.csv")
    arr, nodata, *_ = H.read_raster(d / "vegetation_map.tif")
    ok = np.isin(arr[0], [v for v, n in cats.items() if n.strip().lower() not in SANS_TYPE])
    if nodata is not None:
        ok &= arr[0] != nodata
    bloc = g.fully_in(ORPHAN_BLOCK) & g.forest()
    assert bloc.sum() >= 50, f"bloc d'essai trop petit : {bloc.sum()} cellules"
    orphelines = bloc & ~ok
    comblees = bloc & ok
    rapport = d / "rapport_biomes.html"
    if orphelines.any():
        texte = H.section_text(rapport, "sans type")
        assert texte, "aucune section « sans type » dans rapport_biomes.html"
        manquants = [int(c) for c in g.cell_id[orphelines] if not re.search(rf"\b{int(c)}\b", texte)]
        assert not manquants, \
            f"{len(manquants)}/{int(orphelines.sum())} cell_id sans type absents de la section : {manquants[:10]}"
    if comblees.any():
        texte = H.section_text(rapport, "comblement")
        assert texte, "cellules comblées sans section « comblement » dans rapport_biomes.html"
        manquants = [int(c) for c in g.cell_id[comblees] if not re.search(rf"\b{int(c)}\b", texte)]
        assert not manquants, f"cell_id comblés absents de la section : {manquants[:10]}"
    # Aucune cellule forestière hors du bloc ne devient orpheline sans être signalée.
    hors_bloc = g.forest() & ~ok & ~bloc
    if hors_bloc.any():
        texte = H.section_text(rapport, "sans type")
        manquants = [int(c) for c in g.cell_id[hors_bloc] if not re.search(rf"\b{int(c)}\b", texte)]
        assert not manquants, f"orphelines hors bloc non signalées : {manquants[:10]}"


def test_biomes_tourne_sans_nemeton_stands_gpkg_apres_prepare(sans_stands_zone, runs):
    # spec §2 : biomes lit stand_map (écrit par prepare), plus inputs/nemeton_stands.gpkg.
    d = sans_stands_zone["dir"]
    assert not (d / "inputs" / "nemeton_stands.gpkg").exists()
    assert sans_stands_zone["prepare"].returncode == 0, sans_stands_zone["prepare"].stderr[-1500:]
    p = sans_stands_zone["biomes"]
    assert p.returncode == 0, f"biomes sans le gpkg : code {p.returncode}\n{p.stderr[-1500:]}"
    ref, *_ = H.read_raster(need("vegetation_map.tif"))
    got, *_ = H.read_raster(d / "vegetation_map.tif")
    assert np.array_equal(ref, got), "vegetation_map.tif diffère quand le gpkg est retiré"
    blocs = H.report_blocks("rapport_biomes.html", d)
    for sid in ("S01", "S02", "S03", "S04", "S05"):
        assert any(re.search(rf"\b{sid}\b", b) and "mono-essence" in b.lower() for b in blocs), sid
