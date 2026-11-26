"""Le générateur de SER fictive au-delà de N ≈ 2 016, et ses options --essences S et --classes K (reprise de la
mission 064 : « Take operation overflowed binary array capacity » à N = 4 000 ; l'analyste mesure à S = 8, K = 15).

Ces tests jugent l'aide de test (pas le moteur, sauf un passage pour prouver que simulate lit le type large_string
et un passage à S = 8, K = 15). Ils ne génèrent jamais une grande zone : la colonne `source` est construite seule à
la taille qui débordait, et les morceaux de la zone N = 2 100 sont lus un par un. Aucun test sauté.

Règles vues dans le contrat prepare.cohorts_init : `source` est une chaîne (le validateur accepte string,
large_string et dictionnaire de chaînes) ; `species` appartient à contracts/species.csv, avec son zéro de tête ;
d_class < K ; clé (cell_id, species, d_class) unique."""
import csv
import hashlib
import subprocess
import sys

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml

import helpers_m5 as H
import ser_fictive as G
import test_m5_generateur as TG

SCRATCH = "m5_echelle"
LIGNES_AU_DELA = 36_000_000        # 36 M lignes × 66 octets > 2^31 : N = 2 100 à 2 essences et 4 classes en fait 35,3 M


def _especes_referentiel() -> dict:
    with open(H.ROOT / "contracts" / "species.csv", encoding="utf-8", newline="") as f:
        return {r["espar"]: r["groupe"] for r in csv.DictReader(f)}


def _empreinte(t: pa.Table) -> str:
    h = hashlib.sha256()
    h.update(t["cell_id"].to_numpy().tobytes())
    h.update(t["d_class"].to_numpy().tobytes())
    h.update(t["stems_ha"].to_numpy().tobytes())
    h.update("|".join(t["species"].to_pylist()).encode())
    h.update("|".join(sorted(set(t["source"].to_pylist()))).encode())
    return h.hexdigest()


# ------------------------------------------------------------------ 1. colonne source au-delà de 2^31 octets
def test_la_colonne_source_est_en_large_string_quand_ses_octets_depassent_2_puissance_31():
    octets = len(G.SOURCE.encode("utf-8"))
    limite = (2**31 - 1) // octets                       # nombre de lignes à partir duquel un pa.string() déborde
    assert G.type_colonne_source(limite - 1) == pa.string()
    assert G.type_colonne_source(limite + 1) == pa.large_string()
    assert G.type_colonne_source(LIGNES_AU_DELA) == pa.large_string()
    assert G.schema_cohortes(LIGNES_AU_DELA).field("source").type == pa.large_string()
    # les autres colonnes ne changent pas de type, et le schéma des petites tailles est l'ancien
    assert G.schema_cohortes(10).field("source").type == pa.string()
    attendus = {"cell_id": pa.int64(), "species": pa.string(), "d_class": pa.int64(), "stems_ha": pa.float64()}
    for nl in (10, LIGNES_AU_DELA):
        sch = G.schema_cohortes(nl)
        assert list(sch.names) == ["cell_id", "species", "d_class", "stems_ha", "source"]
        for nom, typ in attendus.items():
            assert sch.field(nom).type == typ


def test_la_colonne_source_se_construit_a_la_taille_qui_debordait():
    """Le test unitaire de la fonction qui construit la colonne, à N = 2 100 (2 essences, 4 classes) et au-delà."""
    nl = 2100 * 2100 * len(G.ESSENCES_DEFAUT) * G.CLASSES_REMPLIES
    assert nl * len(G.SOURCE.encode("utf-8")) > 2**31 - 1, "N = 2 100 ne dépasse plus la capacité : le test ne prouve rien"
    col = G.colonne_source(nl)
    assert col.type == pa.large_string() and len(col) == nl
    assert col.nbytes > 2**31
    assert col[0].as_py() == G.SOURCE and col[nl - 1].as_py() == G.SOURCE
    assert col[nl // 2].as_py() == G.SOURCE and col.null_count == 0


def test_l_ancienne_construction_debordait_bien():
    """Preuve que le test précédent a un sens : la construction de la mission 061 (dictionnaire casté en pa.string())
    échoue à cette taille, et le cast vers large_string échoue aussi (il faut construire la colonne autrement)."""
    codes = pa.array(np.zeros(LIGNES_AU_DELA, dtype=np.int32))
    dico = pa.DictionaryArray.from_arrays(codes, pa.array([G.SOURCE]))
    for cible in (pa.string(), pa.large_string()):
        with pytest.raises(pa.ArrowInvalid):
            dico.cast(cible)


def test_les_morceaux_de_n_2100_portent_le_type_large_string_et_sont_bornes():
    rng = np.random.Generator(np.random.PCG64(1))
    morceaux = G.cohortes_morceaux(2100, rng, G.ESSENCES_DEFAUT, G.CLASSES_REMPLIES)
    m = next(morceaux)
    assert m.schema.field("source").type == pa.large_string()
    assert m.num_rows <= 2**20 + 8 and m.num_rows >= 2**20 - 8, "morceau non borné : la mémoire croîtrait avec N"
    assert m["cell_id"][0].as_py() == 0 and m["species"][0].as_py() == "03" and m["d_class"][0].as_py() == 0
    m2 = next(morceaux)
    assert m2["cell_id"][0].as_py() == m["cell_id"][m.num_rows - 1].as_py() + 1, "les morceaux ne se suivent pas"
    assert m2["d_class"][0].as_py() == 0 and m2["species"][0].as_py() == "03", "un morceau coupe une cellule"


def test_une_zone_au_dela_du_seuil_s_ecrit_valide_en_large_string(monkeypatch):
    """Le seuil est ramené à 1 000 octets pour qu'une petite zone prenne le chemin large_string : le fichier porte
    ce type, le validateur l'accepte, et simulate (niveau SER) le lit et va à son terme."""
    monkeypatch.setattr(G, "SEUIL_OCTETS_CHAINE", 1000)
    name = f"{SCRATCH}_large"
    try:
        zdir, cfg = H.zone_ser(name, 9, H.sim_ser(1), graine=3)
        schema = pq.read_schema(zdir / "cohorts_init.parquet")
        assert schema.field("source").type == pa.large_string()
        p = H.run_validate("prepare.cohorts_init", str(zdir / "cohorts_init.parquet"), "--grid", str(zdir / "grid.tif"))
        assert p.returncode == 0, p.stdout[-600:]
        r = H.run_simulate(name, cfg)
        assert r.returncode == 0, H.queue(r)
        assert (zdir / "sim" / "run.json").is_file()
    finally:
        H.remove_zone(name)


def test_les_octets_d_une_zone_ne_dependent_pas_du_decoupage_en_morceaux(monkeypatch):
    """Même graine : les mêmes cohortes que le découpage soit en un morceau ou en dix ; les tirages se suivent."""
    un = G.cohortes_generiques(9, np.random.Generator(np.random.PCG64(4)), G.ESSENCES_DEFAUT, 4)
    monkeypatch.setattr(G, "LIGNES_PAR_MORCEAU", 50)
    plusieurs = list(G.cohortes_morceaux(9, np.random.Generator(np.random.PCG64(4)), G.ESSENCES_DEFAUT, 4))
    assert len(plusieurs) > 5
    assert _empreinte(pa.concat_tables(plusieurs)) == _empreinte(un)


# ------------------------------------------------------------------ 2. sortie inchangée sans les options
def test_sortie_par_defaut_inchangee_depuis_la_mission_061():
    """Empreinte des valeurs de cohorts_init (N = 7, graine 7) et du raster h0, calculée avec le générateur de la
    mission 061 (avant cette reprise) : sans option, mêmes tirages, même type de colonne."""
    d = H.zone_dir(f"{SCRATCH}_defaut")
    try:
        G.generer(d, 7, 7)
        t = pq.read_table(d / "cohorts_init.parquet")
        assert t.num_rows == 392 and t.schema.field("source").type == pa.string()
        assert _empreinte(t) == "abc2920e8c9cdfe0df1056cad252c6d90e77f2759da645f7c3cbe020da1fc926"
        import rasterio
        with rasterio.open(d / "h0.tif") as r:
            assert hashlib.sha256(r.read(1).tobytes()).hexdigest() == \
                "0aafc37c9ce411e38e7b542625840b3243d1e614210b9cffee44a1e772ec783b"
    finally:
        H.remove_zone(d.name)


def test_options_a_leurs_valeurs_par_defaut_ecrivent_les_memes_octets():
    a, b, c = (H.zone_dir(f"{SCRATCH}_{x}") for x in "abc")
    try:
        G.generer(a, 21, 5)
        p1 = subprocess.run([sys.executable, str(H.HERE / "ser_fictive.py"), "--n", "21", "--graine", "5",
                             "--sortie", str(b)], capture_output=True, text=True)
        p2 = subprocess.run([sys.executable, str(H.HERE / "ser_fictive.py"), "--n", "21", "--graine", "5",
                             "--essences", "2", "--classes", "6", "--sortie", str(c)], capture_output=True, text=True)
        assert p1.returncode == 0 and p2.returncode == 0, p1.stderr + p2.stderr
        fichiers = sorted(str(p.relative_to(a)) for p in a.rglob("*") if p.is_file())
        for d in (b, c):
            assert sorted(str(p.relative_to(d)) for p in d.rglob("*") if p.is_file()) == fichiers
            for rel in fichiers:
                assert (a / rel).read_bytes() == (d / rel).read_bytes(), f"{rel} diffère"
    finally:
        for d in (a, b, c):
            H.remove_zone(d.name)


# ------------------------------------------------------------------ 3. --essences S et --classes K
@pytest.fixture(scope="module")
def zone_s8_k15():
    d = H.zone_dir(f"{SCRATCH}_s8k15")
    p = subprocess.run([sys.executable, str(H.HERE / "ser_fictive.py"), "--n", "11", "--graine", "2",
                        "--essences", "8", "--classes", "15", "--sortie", str(d)], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    yield d
    H.remove_zone(d.name)


def test_s8_k15_chaque_fichier_est_conforme_a_son_contrat(zone_s8_k15):
    d = zone_s8_k15
    for rel, contrat in TG.CONTRATS.items():
        p = H.run_validate(contrat, str(d / rel), "--grid", str(d / "grid.tif"))
        assert p.returncode == 0, f"{rel} ({contrat}) : {p.stdout[-800:]} {p.stderr[-400:]}"


def test_s8_huit_essences_distinctes_du_referentiel_dans_chaque_cellule(zone_s8_k15):
    t = pq.read_table(zone_s8_k15 / "cohorts_init.parquet").to_pydict()
    ref = _especes_referentiel()
    vues = set(t["species"])
    assert len(vues) == 8 and vues <= set(ref), f"essences : {sorted(vues)}"
    assert {"03", "61"} <= vues, "les deux essences de base restent"
    assert {ref[s] for s in vues} == {"feuillu", "resineux"}, "les essences ajoutées sont des deux groupes"
    assert all(len(s) >= 2 for s in vues), "zéro de tête perdu"
    par_cellule = {}
    for c, s in zip(t["cell_id"], t["species"]):
        par_cellule.setdefault(c, set()).add(s)
    assert len(par_cellule) == 11 * 11 and all(v == vues for v in par_cellule.values())


def test_k15_les_classes_vont_de_0_a_14_et_la_cle_reste_unique(zone_s8_k15):
    t = pq.read_table(zone_s8_k15 / "cohorts_init.parquet").to_pydict()
    assert min(t["d_class"]) == 0 and max(t["d_class"]) <= 14
    assert max(t["d_class"]) >= G.CLASSES_REMPLIES, "K = 15 ne garnit pas plus de classes que K = 6"
    assert len(set(zip(t["cell_id"], t["species"], t["d_class"]))) == len(t["cell_id"])
    assert len(t["cell_id"]) == 11 * 11 * 8 * len(set(t["d_class"]))


def test_s8_les_essences_ajoutees_sont_des_copies_provisoires_sans_valeur_ecologique(zone_s8_k15):
    d = zone_s8_k15
    ref = _especes_referentiel()
    reg = pq.read_table(d / "params" / "regeneration.parquet").to_pydict()
    especes = set(pq.read_table(d / "cohorts_init.parquet").column("species").to_pylist())
    assert set(reg["species"]) == especes
    assert all(reg["provisoire"]) and all("aucune valeur écologique" in s for s in reg["source"])
    par = {}
    for sp, term, v in zip(reg["species"], reg["term"], reg["value"]):
        par.setdefault(sp, {})[term] = v
    assert all(set(v) == set(G.TERMES_REGENERATION) for v in par.values())
    for sp in especes:
        base = "03" if ref[sp] == "feuillu" else "61"
        assert par[sp] == par[base], f"{sp} n'est pas une copie de {base}"
    al = pq.read_table(d / "params" / "allometry.parquet").to_pydict()
    assert especes <= set(al["species"]), "allométrie manquante pour une essence ajoutée"
    assert all(al["provisoire"])
    zone = (d / "zone.yml").read_text(encoding="utf-8")
    assert yaml.safe_load(zone)["fictive"] is True and "copies synthétiques" in zone


def test_s8_k15_simulate_va_a_son_terme_sur_deux_ans():
    name = f"{SCRATCH}_run"
    sim = H.sim_ser(2)
    sim["ser"]["diameter_classes"] = 15
    try:
        zdir, cfg = H.zone_ser(name, 8, sim, species=G.essences_pour(8), classes=15)
        r = H.run_simulate(name, cfg)
        assert r.returncode == 0, H.queue(r)
        coh = H.read_kind(zdir, "cohorts")
        assert set(coh["species"].tolist()) <= set(G.essences_pour(8))
        assert int(max(coh["d_class"].tolist())) <= 14
    finally:
        H.remove_zone(name)


def test_s1_une_seule_essence_k1_une_seule_classe():
    d = H.zone_dir(f"{SCRATCH}_s1")
    try:
        G.generer(d, 5, 1, species=G.essences_pour(1), classes=1)
        t = pq.read_table(d / "cohorts_init.parquet").to_pydict()
        assert set(t["species"]) == {"03"} and set(t["d_class"]) == {0}
        p = H.run_validate("prepare.cohorts_init", str(d / "cohorts_init.parquet"), "--grid", str(d / "grid.tif"))
        assert p.returncode == 0, p.stdout[-500:]
    finally:
        H.remove_zone(d.name)


@pytest.mark.parametrize("options", [["--essences", "0"], ["--essences", "17"], ["--essences", "-3"],
                                     ["--classes", "0"], ["--classes", "-1"]])
def test_valeurs_hors_plage_refusees_en_code_2_sans_ecrire(options):
    d = H.zone_dir(f"{SCRATCH}_refus")
    p = subprocess.run([sys.executable, str(H.HERE / "ser_fictive.py"), "--n", "5", "--sortie", str(d), *options],
                       capture_output=True, text=True)
    assert p.returncode == 2, p.stdout + p.stderr
    assert "ser_fictive" in p.stderr and not d.exists()


def test_valeur_non_entiere_refusee():
    d = H.zone_dir(f"{SCRATCH}_refus2")
    p = subprocess.run([sys.executable, str(H.HERE / "ser_fictive.py"), "--n", "5", "--sortie", str(d),
                        "--essences", "huit"], capture_output=True, text=True)
    assert p.returncode == 2 and not d.exists()


# ------------------------------------------------------------------ 4. bench/m5/mesurer.sh
def _mesurer(tmp_path, *args):
    return subprocess.run(["bash", str(H.ROOT / "bench" / "m5" / "mesurer.sh"), "--n", "12", "--fils", "1",
                           "--annees", "1", "--sortie", str(tmp_path / "m.csv"), *args], cwd=H.ROOT,
                          capture_output=True, text=True, env=H.offline_env(), timeout=1200)


def _lignes(tmp_path):
    rows = list(csv.reader((tmp_path / "m.csv").read_text(encoding="utf-8").splitlines()))
    return rows[0], rows[1:]


def test_mesurer_sans_option_garde_la_zone_et_la_config_d_avant(tmp_path):
    zone = H.zone_dir("ser_fictive_12")
    try:
        p = _mesurer(tmp_path)
        assert p.returncode == 0, H.queue(p, 2500)
        assert zone.is_dir(), "la zone par défaut ne s'appelle plus data/ser_fictive_<N>"
        cfg = yaml.safe_load((zone / "config_mesure.yml").read_text(encoding="utf-8"))
        assert cfg["simulate"]["ser"]["diameter_classes"] == 6
        ent, rows = _lignes(tmp_path)
        assert ent[11] == "memory_peak_rss_bytes" and ent[-2:] == ["essences", "classes"] and len(ent) == 16
        assert len(rows) == 1 and rows[0][-2:] == ["2", "6"] and len(rows[0]) == 16
        assert set(pq.read_table(zone / "cohorts_init.parquet").column("species").to_pylist()) == {"03", "61"}
    finally:
        H.remove_zone("ser_fictive_12")


def test_mesurer_essences_8_classes_15(tmp_path):
    zone = H.zone_dir("ser_fictive_12_s8_k15")
    try:
        p = _mesurer(tmp_path, "--essences", "8", "--classes", "15")
        assert p.returncode == 0, H.queue(p, 2500)
        assert zone.is_dir() and not H.zone_dir("ser_fictive_12").exists(), "la zone S = 8, K = 15 doit avoir son nom"
        cfg = yaml.safe_load((zone / "config_mesure.yml").read_text(encoding="utf-8"))
        assert cfg["simulate"]["ser"]["diameter_classes"] == 15
        t = pq.read_table(zone / "cohorts_init.parquet")
        assert len(set(t.column("species").to_pylist())) == 8 and max(t.column("d_class").to_pylist()) <= 14
        _, rows = _lignes(tmp_path)
        assert rows[0][-2:] == ["8", "15"]
        run = H.read_run_json(zone)
        assert run["level"] == "ser"
    finally:
        H.remove_zone("ser_fictive_12_s8_k15")


@pytest.mark.parametrize("options", [["--essences", "0"], ["--essences", "17"], ["--essences", "x"],
                                     ["--classes", "0"], ["--classes", ""]])
def test_mesurer_refuse_les_valeurs_hors_plage_en_code_2(tmp_path, options):
    p = _mesurer(tmp_path, *options)
    assert p.returncode == 2, H.queue(p)
    assert "mesurer.sh" in p.stderr
    assert not (tmp_path / "m.csv").exists()


def test_mesurer_refuse_un_csv_a_l_ancien_en_tete(tmp_path):
    (tmp_path / "m.csv").write_text("date,commit,n,cellules,threads,years,calcul_s,ecriture_s,duration_s,ecoule_s,"
                                    "rss_time_bytes,memory_peak_rss_bytes,memory_estimate_max_bytes,"
                                    "ecart_estimation_rss\n", encoding="utf-8")
    p = _mesurer(tmp_path)
    assert p.returncode == 2 and "en-tête" in p.stderr, H.queue(p)
    H.remove_zone("ser_fictive_12")
