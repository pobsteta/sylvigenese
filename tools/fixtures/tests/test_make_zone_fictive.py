"""Tests du générateur du jeu fictif (mission 013). Tout y est synthétique.

Lancer : python3 -m pytest tools/fixtures/tests
"""
import hashlib
import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import rasterio

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import make_zone_fictive as gen  # noqa: E402

REPO = HERE.parents[2]
# CONTRACTS_VALIDATE : chemin du validateur si `contracts/validate` n'est pas dans ce dépôt
VALIDATE = Path(os.environ.get("CONTRACTS_VALIDATE", REPO / "contracts" / "validate"))


@pytest.fixture(scope="module")
def zone(tmp_path_factory):
    return gen.generate(tmp_path_factory.mktemp("zone_a"), seed=42)


def checksums(root):
    """Somme de contrôle SHA-256 de chaque fichier, par chemin relatif."""
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(root).rglob("*")) if p.is_file()}


# ------------------------------------------------------------------ générateur à compteur
@pytest.mark.parametrize("seed,year,cell,sp,expected", [
    (42, 0, 0, 0, 0.7415648787718233),
    (42, 1, 0, 0, 0.1599103928769201),
    (42, 0, 1, 0, 0.14994666025136738),
    (42, 0, 0, 1, 0.5322551776720237),
    (42, 99, 999999, 7, 0.8685522737309959),
    (7, 3, 123456, 2, 0.3924761688504701),
])
def test_u_valeurs_de_reference_du_banc(seed, year, cell, sp, expected):
    # bench/SPEC.md §2
    assert float(gen.u(seed, year, cell, sp)) == expected


def test_u_ne_depend_pas_de_lordre():
    cells = np.arange(1000)
    ensemble = gen.u(42, 3, cells, 5)
    un_par_un = np.array([float(gen.u(42, 3, int(c), 5)) for c in cells[::-1]])[::-1]
    assert np.array_equal(ensemble, un_par_un)


# ------------------------------------------------------------------ rejouable au bit près
def test_rejeu_meme_graine_memes_octets(zone, tmp_path):
    second = gen.generate(tmp_path / "zone_b", seed=42)
    assert checksums(second) == checksums(zone)


def test_autre_graine_autres_octets(zone, tmp_path):
    autre = gen.generate(tmp_path / "zone_c", seed=43)
    a, b = checksums(zone), checksums(autre)
    assert a.keys() == b.keys()
    assert a["inputs/chm.tif"] != b["inputs/chm.tif"]
    assert a["inputs/ifn/PLACETTE.csv"] != b["inputs/ifn/PLACETTE.csv"]


def test_ligne_de_commande_rejoue_le_jeu_versionne(zone, tmp_path):
    """Le jeu versionné sous tests/fixtures/zone_fictive est celui de la graine 42."""
    versionne = REPO / "tests" / "fixtures" / "zone_fictive"
    if not versionne.exists():
        pytest.skip("jeu fictif non généré dans ce dépôt")
    out = tmp_path / "cli"
    subprocess.run([sys.executable, str(HERE.parent / "make_zone_fictive.py"), "--out", str(out)],
                   check=True, capture_output=True)
    attendu = {k: v for k, v in checksums(versionne).items() if k != "README.md"}
    assert checksums(out) == attendu


# ------------------------------------------------------------------ mailles et profil
@pytest.mark.parametrize("name,res,count", [
    ("chm.tif", 0.5, 1), ("dtm.tif", 25.0, 1), ("station_gradients.tif", 20.0, 3),
    ("station_type.tif", 20.0, 1), ("h_pot.tif", 26.6, 1)])
def test_rasters_maille_profil_et_emprise(zone, name, res, count):
    with rasterio.open(zone / "inputs" / name) as r:
        assert r.crs.to_epsg() == 2154
        assert r.res == (res, res)
        assert r.count == count
        assert r.nodata is not None
        assert r.profile["tiled"] and r.profile["blockxsize"] == 256
        assert r.profile["compress"] == "deflate"
        assert r.profile["interleave"] == "band"
        # coin nord-ouest au coin du massif, emprise qui couvre tout le massif
        assert (r.bounds.left, r.bounds.top) == (gen.X0, gen.YTOP)
        assert r.bounds.right >= gen.X0 + gen.SIDE - 1e-6
        assert r.bounds.bottom <= gen.Y0 + 1e-6


def test_mailles_differentes_entre_elles(zone):
    res = {}
    for name in ("chm", "dtm", "station_gradients", "h_pot"):
        with rasterio.open(zone / "inputs" / f"{name}.tif") as r:
            res[name] = r.res[0]
    assert len(set(res.values())) == 4


# ------------------------------------------------------------------ un point tombe au bon endroit
def test_arbre_le_plus_haut_au_bon_endroit_dans_le_mnh(zone):
    """x vers l'est, y vers le nord, EPSG:2154 : la tige la plus haute est lue sous son houppier,
    et un point de la trouée (sans arbre) est bas."""
    trees = gen.build_trees(42)
    top = trees[np.argmax(trees["h"])]
    with rasterio.open(zone / "inputs" / "chm.tif") as r:
        row, col = r.index(top["x"], top["y"])
        value = r.read(1)[row, col]
        assert 0.9 * top["h"] <= value <= top["h"] + 0.01
        # le même point avec y inversé (symétrie nord-sud) ne tombe pas sur ce houppier
        miroir_y = 2 * (gen.Y0 + gen.SIDE / 2) - top["y"]
        row2, col2 = r.index(top["x"], miroir_y)
        assert r.read(1)[row2, col2] < value
        # centre de la trouée forestière
        cx0, cx1, cy0, cy1 = gen.rect_xy(*gen.CLEARING)
        row3, col3 = r.index((cx0 + cx1) / 2, (cy0 + cy1) / 2)
        assert r.read(1)[row3, col3] == 0.0


def test_hauteur_du_mnh_suit_les_peuplements(zone):
    """Le p95 du MNH de chaque peuplement est proche de la hauteur de son polygone."""
    with rasterio.open(zone / "inputs" / "chm.tif") as r:
        for sid, _, xa, xb, ya, yb, _, h, *_ in gen.STANDS:
            x0, x1, y0, y1 = gen.rect_xy(xa, xb, ya, yb)
            sub = r.read(1, window=r.window(x0, y0, x1, y1))
            assert abs(np.percentile(sub, 95) - h) < 0.15 * h, sid


def test_peuplement_s03_depasse_le_plafond_h_pot(zone):
    """Cas voulu : de la hauteur au-dessus de h_pot, pour le rapport de hauteur (spec §5)."""
    s03 = next(s for s in gen.STANDS if s[0] == "S03")
    x0, x1, y0, y1 = gen.rect_xy(*s03[2:6])
    with rasterio.open(zone / "inputs" / "h_pot.tif") as r:
        plafond = r.read(1, window=r.window(x0, y0, x1, y1))
    assert s03[7] > plafond.max()


# ------------------------------------------------------------------ IFN
def test_ifn_coordonnees_floutees_a_700_m(zone):
    lignes = (zone / "inputs" / "ifn" / "PLACETTE.csv").read_text().splitlines()[1:]
    vraies = gen.ifn_true_positions(42)
    assert len(lignes) == len(vraies)
    ecarts = []
    for ligne, (tx, ty) in zip(lignes, vraies):
        _, _, xl, yl = ligne.split(";")
        ecarts.append(math.hypot(float(xl) - tx, float(yl) - ty))
    assert max(ecarts) <= 700.0 + 0.2          # arrondi au dixième de mètre
    assert max(ecarts) > 100.0                  # les points sont bien déplacés


def test_ifn_c13_en_mm_et_espar_avec_zero_de_tete(zone):
    lignes = (zone / "inputs" / "ifn" / "ARBRE.csv").read_text().splitlines()
    assert lignes[0] == "CAMPAGNE;IDP;ESPAR;C13;HTOT;V;W"
    for ligne in lignes[1:]:
        _, _, espar, c13, *_ = ligne.split(";")
        assert espar in gen.SPECIES_USED and len(espar) == 2
        assert 235 <= int(c13) <= 2600          # seuil de recensabilité, en mm


def test_codes_essence_dans_la_table_des_especes(zone):
    codes = {l.split(",")[0] for l in (REPO / "contracts" / "species.csv").read_text().splitlines()[1:]} \
        if (REPO / "contracts" / "species.csv").exists() else set(gen.SPECIES_USED)
    assert set(gen.SPECIES_USED) <= codes


# ------------------------------------------------------------------ paramètres synthétiques
def test_parametres_provisoires_et_sources(zone):
    import pyarrow.parquet as pq
    for nom in ("tarif", "allometry"):
        t = pq.read_table(zone / "params" / f"{nom}.parquet").to_pydict()
        assert t["provisoire"] and all(t["provisoire"])
        assert set(t["source"]) == {"synthetique_jeu_fictif"}
        assert set(t["species"]) == set(gen.SPECIES_USED)


# ------------------------------------------------------------------ le validateur de 009
@pytest.mark.skipif(not VALIDATE.exists(), reason="contracts/validate absent (mission 009 non fusionnée)")
def test_le_validateur_accepte_le_jeu(zone):
    res = subprocess.run([sys.executable, str(VALIDATE), "--zone", str(zone)],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stdout + res.stderr
