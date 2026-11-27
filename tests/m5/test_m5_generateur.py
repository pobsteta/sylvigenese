"""Le générateur de SER fictive (plan m5a, mission C, T9) : conforme aux contrats, à toute taille N, deux codes de SER
du référentiel, `fictive: true`, valeurs synthétiques et provisoires, mêmes octets à graine égale.

Ces tests jugent l'aide de test elle-même (pas le moteur) : ils sont verts dès la mission 061. Un générateur faux
rendrait faux tous les autres tests de tests/m5."""
import csv
import json
import subprocess
import sys

import numpy as np
import pyarrow.parquet as pq
import pytest
import rasterio
import yaml

import helpers_m5 as H
import ser_fictive as G

SCRATCH = "m5_gen"
CONTRATS = {
    "grid.tif": "prepare.grid", "forest_mask.tif": "prepare.forest_mask", "h0.tif": "prepare.h0",
    "chm_date.tif": "prepare.chm_date", "site_potential.tif": "prepare.site_potential",
    "station_gradients.tif": "prepare.station_gradients", "ser.tif": "prepare.ser", "ser.csv": "prepare.ser_categories",
    "cohorts_init.parquet": "prepare.cohorts_init", "params/growth.parquet": "dynamics.growth",
    "params/mortality.parquet": "dynamics.mortality", "params/recruitment.parquet": "dynamics.recruitment",
    "params/height_curve.parquet": "dynamics.height_curve", "params/regeneration.parquet": "dynamics.regeneration",
    "params/allometry.parquet": "import_tarif.allometry", "zone.yml": "zone_marker",
}


@pytest.fixture(scope="module", params=[1, 7, 33])
def zone(request):
    """N = 1 (dégénéré : une seule SER), 7 et 33 (impairs : la frontière des deux SER n'est pas au milieu exact)."""
    n = request.param
    d = H.zone_dir(f"{SCRATCH}_{n}")
    G.generer(d, n, 5)
    yield {"dir": d, "n": n}
    H.remove_zone(d.name)


def test_chaque_fichier_ecrit_est_conforme_a_son_contrat(zone):
    d = zone["dir"]
    ecrits = {str(p.relative_to(d)) for p in d.rglob("*") if p.is_file()}
    assert ecrits == set(CONTRATS), f"fichiers inattendus ou manquants : {ecrits ^ set(CONTRATS)}"
    for rel, contrat in CONTRATS.items():
        p = H.run_validate(contrat, str(d / rel), "--grid", str(d / "grid.tif"))
        assert p.returncode == 0, f"{rel} ({contrat}) : {p.stdout[-800:]} {p.stderr[-400:]}"


def test_la_grille_fait_n_sur_n_cellules_de_25_m_en_lambert_93(zone):
    with rasterio.open(zone["dir"] / "grid.tif") as r:
        assert (r.width, r.height) == (zone["n"], zone["n"])
        assert r.crs.to_epsg() == 2154
        assert (r.transform.a, r.transform.e) == (25.0, -25.0)
        assert (r.transform.c, r.transform.f) == (H.G.X0_DEFAUT, H.G.Y0_DEFAUT)


def test_le_point_connu_est_le_centre_de_la_cellule_0_par_defaut(zone):
    """Piège des axes : (est 700 012,5 ; nord 6 500 987,5) tombe dans la cellule 0 ; inversés, ils sortent de
    l'emprise de Lambert-93 (y vers 700 012 est hors de [6 000 000 ; 7 200 000])."""
    g = H.H3.Grid(zone["dir"])
    assert H.cellule_du_point(g, H.SOURCE_EST, H.SOURCE_NORD) == (0, 0)
    assert g.cell_center(0) == (H.SOURCE_EST, H.SOURCE_NORD)
    assert not (6_000_000 <= H.SOURCE_EST <= 7_200_000), "x et y inversés passeraient l'emprise"


def test_zone_yml_dit_fictive_et_nomme_les_deux_ser(zone):
    z = yaml.safe_load((zone["dir"] / "zone.yml").read_text(encoding="utf-8"))
    assert z["fictive"] is True and z["schema_version"] == 1
    for code in G.SER_CODES:
        assert code in z["reason"], z["reason"]


def test_deux_codes_de_ser_du_referentiel(zone):
    with open(zone["dir"] / "ser.csv", encoding="utf-8", newline="") as f:
        lignes = list(csv.DictReader(f))
    noms = [l["name"] for l in lignes]
    assert len(set(noms)) == 2, noms
    with open(H.ROOT / "docs" / "referentiels" / "surfaces-ser.csv", encoding="utf-8", newline="") as f:
        ref = {r["code_ser"] for r in csv.DictReader(f)}
    assert set(noms) <= ref, f"code de SER hors référentiel : {set(noms) - ref}"
    with rasterio.open(zone["dir"] / "ser.tif") as r:
        v = set(np.unique(r.read(1)).tolist())
    attendu = {1} if zone["n"] == 1 else {1, 2}
    assert v == attendu, f"valeurs de ser.tif : {v}"
    assert v <= {int(l["value"]) for l in lignes}


def test_les_cohortes_initiales_sont_dans_la_grille_et_dans_k(zone):
    t = pq.read_table(zone["dir"] / "cohorts_init.parquet").to_pydict()
    n = zone["n"]
    assert t["cell_id"], "cohorts_init vide"
    assert min(t["cell_id"]) >= 0 and max(t["cell_id"]) < n * n
    assert set(range(n * n)) == set(t["cell_id"]), "toute cellule forestière a au moins une ligne"
    assert min(t["d_class"]) >= 0 and max(t["d_class"]) < H.K_CLASSES
    assert len(set(zip(t["cell_id"], t["species"], t["d_class"]))) == len(t["cell_id"]), "clé en double"
    with open(H.ROOT / "contracts" / "species.csv", encoding="utf-8", newline="") as f:
        ref = {r["espar"] for r in csv.DictReader(f)}
    assert set(t["species"]) <= ref
    assert min(t["stems_ha"]) >= 0


def test_toutes_les_valeurs_de_parametres_sont_synthetiques_et_provisoires(zone):
    """Ne rien inventer d'écologique (CLAUDE.md) : chaque valeur écrite par le générateur le dit."""
    for p in sorted((zone["dir"] / "params").glob("*.parquet")):
        if p.name == "allometry.parquet":          # copie du jeu fictif versionné, pas une valeur du générateur
            continue
        t = pq.read_table(p).to_pydict()
        assert all(t["provisoire"]), f"{p.name} : valeur non provisoire"
        termes = t.get("term", [None] * len(t["source"]))
        for term, val, s in zip(termes, t["value"], t["source"]):
            if p.name == "regeneration.parquet" and term == "stress_mortality":
                # terme repris d'une source citée (TreeMig), toujours provisoire
                assert "TreeMig éq. 40" in s and val == 0.184, f"{p.name} : stress_mortality hors TreeMig éq. 40"
            elif p.name == "regeneration.parquet" and term in G.SOURCE_TERME:
                # termes de l'ombre des semis (mission 084b) : source citée (ou décision de Pascal), valeur du générateur
                assert s == G.SOURCE_TERME[term] and val == G.REGENERATION_DEFAUT[term][0], f"{p.name} : {term}"
            else:
                assert "synthétique" in s, f"{p.name} : source non dite synthétique"
    c = pq.read_table(zone["dir"] / "cohorts_init.parquet").to_pydict()
    assert all("synthétique" in s for s in c["source"])


def test_regeneration_porte_les_vingt_termes_pour_chaque_essence(zone):
    t = pq.read_table(zone["dir"] / "params" / "regeneration.parquet").to_pydict()
    schema = json.loads((H.ROOT / "contracts" / "tables" / "params" / "regeneration.schema.json").read_text())
    termes = set(next(f for f in schema["fields"] if f["name"] == "term")["constraints"]["enum"])
    assert set(G.TERMES_REGENERATION) == termes, "le générateur ne suit plus la liste fermée du contrat"
    for s in G.ESSENCES_DEFAUT:
        vus = {term for sp, term in zip(t["species"], t["term"]) if sp == s}
        assert vus == termes, f"essence {s} : termes manquants {termes - vus}"


def _empreintes(d):
    return H.sha_tree(d)


def test_meme_graine_memes_octets_autre_graine_autres_octets():
    a, b, c = (H.zone_dir(f"{SCRATCH}_rejeu_{x}") for x in "abc")
    try:
        G.generer(a, 50, 11)
        G.generer(b, 50, 11)
        G.generer(c, 50, 12)
        ea, eb, ec = _empreintes(a), _empreintes(b), _empreintes(c)
        assert ea == eb, f"rejeu à graine égale : fichiers différents {[k for k in ea if ea[k] != eb.get(k)]}"
        differents = {k for k in ea if ea[k] != ec[k]}
        assert {"cohorts_init.parquet", "h0.tif", "station_gradients.tif"} <= differents, differents
    finally:
        for d in (a, b, c):
            H.remove_zone(d.name)


def test_la_ligne_de_commande_ecrit_les_memes_octets_que_l_aide():
    a, b = H.zone_dir(f"{SCRATCH}_cli"), H.zone_dir(f"{SCRATCH}_lib")
    try:
        p = subprocess.run([sys.executable, str(H.HERE / "ser_fictive.py"), "--n", "17", "--graine", "3",
                            "--sortie", str(a)], capture_output=True, text=True, env=H.offline_env())
        assert p.returncode == 0, p.stderr
        G.generer(b, 17, 3)
        assert _empreintes(a) == _empreintes(b)
    finally:
        H.remove_zone(a.name)
        H.remove_zone(b.name)


def test_la_ligne_de_commande_refuse_une_taille_nulle():
    d = H.zone_dir(f"{SCRATCH}_zero")
    p = subprocess.run([sys.executable, str(H.HERE / "ser_fictive.py"), "--n", "0", "--sortie", str(d)],
                       capture_output=True, text=True)
    assert p.returncode == 2 and "N" in p.stderr
    assert not d.exists()


def test_n_1000_s_ecrit_en_moins_d_une_minute():
    """La taille de la CI (T10) : un million de cellules, conforme (cohorts_init seul revalidé, le plus gros)."""
    import time
    d = H.zone_dir(f"{SCRATCH}_1000")
    try:
        t = time.monotonic()
        G.generer(d, 1000, 1)
        assert time.monotonic() - t < 60
        p = H.run_validate("prepare.cohorts_init", str(d / "cohorts_init.parquet"))
        assert p.returncode == 0, p.stdout[-500:]
        assert pq.read_metadata(d / "cohorts_init.parquet").num_rows == 1000 * 1000 * 2 * G.CLASSES_REMPLIES
    finally:
        H.remove_zone(d.name)
