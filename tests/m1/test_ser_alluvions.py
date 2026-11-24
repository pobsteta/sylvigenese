"""SER sous-jacente des alluvions (spec §3, §7 ; décision de Pascal du 24/11/2026).

Règle : la SER sous-jacente d'un polygone d'alluvions L1-L5 est la SER voisine qui partage avec
lui la plus longue frontière ; chaque attribution donne une ligne de rapport.
"""
import re
import sqlite3

import numpy as np

import helpers as H
from conftest import need


def _ser_names(zone_dir):
    cats = H.read_csv_map(zone_dir / "ser.csv")
    arr, nodata, *_ = H.read_raster(zone_dir / "ser.tif")
    return cats, arr[0], nodata


def test_fixture_ser_gpkg_a_la_forme_brute_de_l_ign():
    # En entrée, un polygone L3 porte ser_code = "L3" (mission 017 remet le jeu fictif à cette forme).
    c = sqlite3.connect(H.INPUTS / "ser.gpkg")
    codes = [r[0] for r in c.execute("select ser_code from ser")]
    c.close()
    assert any(H.L_CODE.match(x) for x in codes), f"aucun ser_code L1-L5 en entrée : {codes}"


def test_ser_csv_ne_nomme_jamais_une_alluvion(runs):
    cats = H.read_csv_map(need("ser.csv"))
    assert cats, "ser.csv vide"
    bad = [n for n in cats.values() if H.L_CODE.match(n)]
    assert not bad, f"SER sous-jacente attendue, alluvions trouvées : {bad}"


def test_ser_tif_n_a_que_des_valeurs_de_la_table_et_pas_de_trou_dans_le_massif(grid):
    cats, arr, nodata = _ser_names(H.ZONE)
    forest = grid.forest()
    v = arr[forest]
    assert not (np.isin(v, [nodata]) if nodata is not None else np.zeros(1, bool)).any(), \
        "cellule forestière sans SER (nodata) : pas de valeur par défaut silencieuse"
    assert set(int(x) for x in np.unique(v)) <= set(cats)


def test_jeu_fictif_couloir_prend_la_ser_voisine(grid):
    # Dans le jeu fictif, les voisins du couloir sont tous H10 : le couloir est H10.
    cats, arr, nodata = _ser_names(H.ZONE)
    couloir = grid.fully_in((0, 1000, 420, 520))
    assert couloir.sum() >= 100
    noms = {cats[int(x)] for x in np.unique(arr[couloir])}
    assert noms == {"H10"}, f"SER du couloir {noms}, attendu {{'H10'}}"


def test_jeu_fictif_une_ligne_de_rapport_par_attribution(runs):
    blocs = H.report_blocks("rapport_prepare.html")
    lignes = [b for b in blocs if re.search(r"\bL3\b", b) and re.search(r"\bH10\b", b)]
    assert lignes, "aucune ligne de rapport ne relie l'alluvion L3 à sa SER sous-jacente H10"


# ---- Cas discriminant : voisine de plus longue frontière (zone variante data/m1_alluvions) ----
def test_variante_prepare_et_biomes_reussissent(alluvion_zone):
    for k in ("prepare", "biomes"):
        p = alluvion_zone[k]
        assert p.returncode == 0, f"{k} : code {p.returncode}\n{p.stderr[-1500:]}"


def test_variante_couloir_prend_la_voisine_de_plus_longue_frontiere(alluvion_zone):
    d = alluvion_zone["dir"]
    assert (d / "grid.tif").is_file(), "grid.tif absent de data/m1_alluvions/"
    g = H.Grid(d / "grid.tif")
    cats, arr, nodata = _ser_names(d)
    nom = lambda m: {cats[int(x)] for x in np.unique(arr[m])}  # noqa: E731
    # Couloir y 420-520 : H20 (frontière 1000 m), ni H30 (600 m, plus grande surface) ni H10 (400 m).
    couloir = g.fully_in((0, 1000, 420, 520))
    assert couloir.sum() >= 100
    assert nom(couloir) == {"H20"}, f"couloir : {nom(couloir)}, attendu {{'H20'}}"
    # Les SER voisines gardent leur propre code ; aucune alluvion n'apparaît.
    assert nom(g.fully_in((0, 400, 0, 400))) == {"H10"}
    assert nom(g.fully_in((400, 1000, 0, 400))) == {"H30"}
    assert nom(g.fully_in((0, 1000, 525, 600))) == {"H20"}
    assert nom(g.fully_in((0, 1000, 600, 1000))) == {"H40"}
    assert not [n for n in cats.values() if H.L_CODE.match(n)]


def test_variante_ligne_de_rapport_pour_l_attribution(alluvion_zone):
    blocs = H.report_blocks("rapport_prepare.html", alluvion_zone["dir"])
    avec_l3 = [b for b in blocs if re.search(r"\bL3\b", b)]
    assert any(re.search(r"\bH20\b", b) for b in avec_l3), \
        "aucune ligne de rapport « L3 -> H20 »"
    # La ligne peut citer la voisine suivante (« suivante : H30 ») ; seule la SER de rattachement compte.
    faux = [b for b in avec_l3
            if (m := re.search(r"rattach\w*\s+à\s+la\s+SER\s+(\S+?)[,\s]", b)) and m.group(1) != "H20"]
    assert not faux, f"ligne de rapport qui lie L3 à une mauvaise SER : {faux[:2]}"


# ---- alluvium_code (spec §3, §7) : une valeur de ser.tif par couple (ser_code, alluvium_code) ----
def test_ser_csv_a_les_colonnes_value_name_alluvium_code(runs):
    table = H.read_ser_table(need("ser.csv"))  # contrôle l'en-tête exact
    assert table
    for v, (nom, alu) in table.items():
        assert not H.L_CODE.match(nom), (v, nom)
        assert alu is None or H.L_CODE.match(alu), (v, alu)
    couples = list(table.values())
    assert len(couples) == len(set(couples)), "un couple (ser_code, alluvium_code) est répété"


def test_jeu_fictif_le_couloir_garde_alluvium_code_l3(grid):
    table = H.read_ser_table(H.ZONE / "ser.csv")
    _, arr, _ = _ser_names(H.ZONE)
    couloir = grid.fully_in((0, 1000, 420, 520))
    assert {table[int(v)] for v in np.unique(arr[couloir])} == {("H10", "L3")}
    hors = grid.forest() & ~grid.in_rect((0, 1000, 400, 540))
    assert {table[int(v)][1] for v in np.unique(arr[hors])} == {None}, \
        "alluvium_code renseigné hors du couloir d'alluvions"


def test_variante_cellules_d_alluvion_gardent_alluvium_code_et_une_ser_sous_jacente(alluvion_zone):
    d = alluvion_zone["dir"]
    g = H.Grid(d / "grid.tif")
    table = H.read_ser_table(d / "ser.csv")
    arr = H.read_raster(d / "ser.tif")[0][0]
    couloir = g.fully_in((0, 1000, 420, 520))
    couples = {table[int(v)] for v in np.unique(arr[couloir])}
    assert couples == {("H20", "L3")}, couples
    # jamais L1-L5 comme ser_code, sur toute la table et toutes les cellules forestières
    assert not [n for n, _ in table.values() if H.L_CODE.match(n)]
    valeurs = {int(v) for v in np.unique(arr[g.forest()])}
    assert not [table[v] for v in valeurs if H.L_CODE.match(table[v][0])]
    # une valeur distincte pour (H20, L3) et pour (H20, NULL) : la bande de H20 hors couloir
    bande_h20 = g.fully_in((0, 1000, 525, 600))
    couples_h20 = {table[int(v)] for v in np.unique(arr[bande_h20])}
    assert couples_h20 == {("H20", None)}, couples_h20
    assert {int(v) for v in np.unique(arr[couloir])}.isdisjoint({int(v) for v in np.unique(arr[bande_h20])})
    # alluvium_code NULL partout ailleurs
    ailleurs = g.forest() & ~g.in_rect((0, 1000, 400, 540))
    assert {table[int(v)][1] for v in np.unique(arr[ailleurs])} == {None}
