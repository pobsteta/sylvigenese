"""Suite de M4a (mission 045) : simulate puis assets sur une zone avec sim/ ; années retenues, tiles/index.json,
années périmées effacées, rejeu identique (plan m4a-suite-temps §2 mission B, §3, T1, T5, T6 ; contrat tiles_index)."""
import json

import numpy as np

import helpers_m4 as H
import helpers_m4_temps as T
from helpers_m4_temps import exige_temps, queue as _queue

ANNEES = T.retained_years(T.T0, T.YEARS, T.STEP)          # [2022, 2032, 2037]
ANNEES_5 = T.retained_years(T.T0, T.YEARS, T.STEP_FIN)    # [2022, 2027, 2032, 2037]


def test_simulate_tourne_sur_la_copie_et_ecrit_h_dom_m(temps):
    assert temps["make"].returncode == 0, _queue(temps["make"])
    assert T.sim_years(temps["dir"], "cells") == list(range(T.T0, T.T0 + T.YEARS + 1))
    import pyarrow.parquet as pq
    sans = [str(p.relative_to(temps["dir"])) for p in sorted((temps["dir"] / "sim" / "cells").rglob("*.parquet"))
            if "h_dom_m" not in pq.read_schema(p).names]
    assert not sans, f"h_dom_m absent de sim/cells (décision de Pascal Q1, mission 046) : {sans[:3]}…"


def test_assets_sort_avec_le_code_0_sur_une_zone_avec_sim(temps):
    for k in ("assets_5", "assets_10", "assets_10b"):
        assert temps[k].returncode == 0, f"{k} : " + _queue(temps[k])


def test_les_annees_retenues_sont_t0_puis_une_sur_10_puis_la_derniere(temps_index):
    assert [y["year"] for y in temps_index["years"]] == ANNEES == [2022, 2032, 2037]
    assert temps_index["t0"] == T.T0 and temps_index["year_step"] == T.STEP


def test_le_pas_se_regle_dans_config_et_la_derniere_annee_n_est_pas_en_double(temps):
    exige_temps(temps)
    idx = temps["apres_5"]["index"]
    assert idx is not None, "pas de 5 : tiles/index.json absent"
    assert [y["year"] for y in idx["years"]] == ANNEES_5 == [2022, 2027, 2032, 2037]
    assert idx["year_step"] == T.STEP_FIN


def test_l_index_est_conforme_au_contrat(temps):
    zdir = exige_temps(temps)
    p = H.validate("tiles_index", str(zdir / "tiles" / "index.json"))
    assert p.returncode == 0, p.stdout[-1500:] + p.stderr[-1500:]


def test_l_index_dit_sa_source_son_run_et_la_mention(temps, temps_index):
    run = json.loads((temps["dir"] / "sim" / "run.json").read_text(encoding="utf-8"))
    assert temps_index["source"] == "sim"
    assert temps_index["run_config_sha256"] == run["config_sha256"]
    assert temps_index["provisoire"] is True
    assert any(T.MENTION_ECO in n for n in temps_index["notes"]), temps_index["notes"]


def test_instances_de_l_index_egales_aux_vivants_et_morts_comptes_a_part(temps, temps_index):
    zdir = temps["dir"]
    for e in temps_index["years"]:
        tr = T.trees_of_year(zdir, e["year"])
        vivants = int((tr["status"] == "alive").sum())
        morts = int((tr["status"] == "dead").sum())
        assert e["instances"] == vivants, f"{e['year']} : instances {e['instances']} != {vivants} vivants"
        assert e["dead"] == morts, f"{e['year']} : dead {e['dead']} != {morts} morts de la partition"
    assert sum(e["dead"] for e in temps_index["years"][1:]) > 0, "aucun mort sur les années retenues : test sans pouvoir"


def test_instances_par_tuile_egales_aux_vivants_de_chaque_tuile(temps, temps_index):
    zdir = temps["dir"]
    for e in temps_index["years"]:
        tr = T.trees_of_year(zdir, e["year"])
        a = tr["status"] == "alive"
        noms, n = np.unique(T.tile_name(tr["x"][a], tr["y"][a]), return_counts=True)
        attendu = dict(zip(noms.tolist(), n.tolist()))
        lu = {t["tile"]: t["instances"] for t in e["tiles"]}
        assert {k: v for k, v in lu.items() if v} == attendu, f"{e['year']} : par tuile {lu} != {attendu}"
        assert sum(lu.values()) == e["instances"]
        assert e["tileset"] == f"{e['year']}/tileset.json"


def test_chaque_annee_a_son_dossier_et_rien_d_autre_sous_tiles(temps, temps_index):
    zdir = temps["dir"]
    for e in temps_index["years"]:
        assert (zdir / "tiles" / e["tileset"]).is_file(), f"tiles/{e['tileset']} absent"
    present = sorted(p.name for p in (zdir / "tiles").iterdir())
    assert present == sorted([str(y) for y in ANNEES] + ["index.json"]), f"tiles/ contient {present}"


def test_les_annees_perimees_sont_effacees(temps):
    zdir = exige_temps(temps)
    # 2021 (ancien t0, planté avant le premier passage) disparaît dès le pas de 5 ; 2027 (pas de 5) au pas de 10
    assert "2021" not in temps["apres_5"]["tiles"], f"pas de 5 : tiles/ garde {temps['apres_5']['tiles']}"
    assert "g_2021.tif" not in temps["apres_5"]["rasters"], f"pas de 5 : {temps['apres_5']['rasters']}"
    assert not (zdir / "tiles" / "2027").exists() and not (zdir / "tiles" / "2021").exists()
    rasters = sorted(p.name for p in (zdir / "web" / "rasters").glob("g_*.tif"))
    assert rasters == [f"g_{y}.tif" for y in ANNEES], f"web/rasters : {rasters}"
    assert not list(zdir.rglob(".en_cours")), "un dossier d'écriture .en_cours est resté"


def test_le_rejeu_est_identique_a_l_octet_pres(temps):
    exige_temps(temps)
    a, b = temps["sorties_10a"], temps["sorties_10b"]
    assert set(a) == set(b)
    diff = sorted(k for k in a if a[k] != b[k])
    assert not diff, f"rejeu différent : {diff[:5]}"


def test_les_extras_du_tileset_disent_l_etat_simule(temps, temps_index):
    zdir = temps["dir"]
    for e in temps_index["years"]:
        ex = T.tileset_extras(zdir / "tiles" / e["tileset"])
        assert ex.get("etat") == "simulé", f"{e['year']} : etat = {ex.get('etat')!r}"
        assert ex.get("annee") == e["year"] and ex.get("instances") == e["instances"], ex
        assert "sim" in str(ex.get("source", "")), f"{e['year']} : source = {ex.get('source')!r}"


def test_les_fiches_sont_les_tuiles_de_l_index(temps, temps_index, temps_sheets):
    tuiles = {t["tile"] for e in temps_index["years"] for t in e["tiles"]}
    assert set(temps_sheets) == tuiles, f"fiches {sorted(temps_sheets)} != tuiles {sorted(tuiles)}"


def test_l_etat_initial_sans_sim_ecrit_un_index_trees_init(chaine):
    # Mode état initial gardé quand sim/ est absent (plan §2 mission C ; contrat tiles_index, mode trees_init).
    assert chaine["make"].returncode == 0, chaine["make"].stderr[-1500:]
    idx = T.read_index(H.ZONE)
    assert idx["source"] == "trees_init" and len(idx["years"]) == 1, idx
    assert idx["years"][0]["instances"] == 14080
    assert idx["years"][0]["year"] == int(H.find_tilesets(H.ZONE)[0].parent.name)
    assert not (H.ZONE / "sim").exists(), "la zone de l'état initial porte un sim/"
    p = H.validate("tiles_index", str(H.ZONE / "tiles" / "index.json"))
    assert p.returncode == 0, p.stdout[-1500:]
