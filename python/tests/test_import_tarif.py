"""Tests de `import_tarif` (mission 027) : modèle etage_b depuis un dossier tarif-nemeton réduit.

Le dossier tarif-nemeton est fabriqué par le test (quelques lignes, valeurs d'essai) ; le vrai
dépôt n'est pas lu. Le validateur appelé est le vrai (`contracts/validate`, contrat
`import_tarif.allometry`). La racine du projet (SYLVIGENESE_ROOT) est un dossier temporaire :
le jeu fictif versionné n'est jamais écrasé.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pyarrow.parquet as pq
import pytest
import yaml

from sylvigenese import import_tarif
from sylvigenese.common import ModuleError

ROOT = Path(__file__).resolve().parents[2]
HEADER = "essence,n,a,b_lnH,c_lnCPA,sigma_log,R2\n"

# valeurs d'essai (pas celles de tarif-nemeton) : a, b_lnH, c_lnCPA
CROWN_ROWS = [
    "Fagus_sylvatica,10,-1.0,1.1,0.2,0.1,0.8",
    "Quercus_spec,10,-0.5,0.9,0.3,0.1,0.8",
    "Betula_spec,10,-0.4,1.2,-0.07,0.1,0.8",
    "Abies_alba,10,0.3,0.8,0.25,0.1,0.8",
    "Essence_inconnue,10,0.1,0.5,0.1,0.1,0.8",
]
IFN = [
    "Fagus_sylvatica,10,0.9,1.5,0.0,0.2,0.6",      # aussi dans le premier fichier : ignorée
    "Pinus_sylvestris,10,0.49,1.01,0.0,0.2,0.6",   # seulement ici : a et b, pas de c
    "Picea_abies,10,0.7,0.9,,0.2,0.6",             # c vide : pas de c
]


@pytest.fixture
def tarif_setup(tmp_path, monkeypatch):
    """Dossier tarif-nemeton réduit, racine temporaire avec contracts/species.csv, config."""
    tarif = tmp_path / "tarif-nemeton"
    results_dir = tarif / "resultats" / "etage_b"
    results_dir.mkdir(parents=True)
    (results_dir / "allometrie_D.csv").write_text(HEADER + "\n".join(CROWN_ROWS) + "\n", encoding="utf-8")
    (results_dir / "allometrie_D_ifn.csv").write_text(HEADER + "\n".join(IFN) + "\n", encoding="utf-8")
    root = tmp_path / "racine"
    (root / "contracts").mkdir(parents=True)
    shutil.copy(ROOT / "contracts" / "species.csv", root / "contracts" / "species.csv")
    config = tmp_path / "config.yml"
    content = yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8"))
    content["zone"] = "zone_essai"
    content["external"] = {"tarif_nemeton_dir": str(tarif)}
    config.write_text(yaml.safe_dump(content), encoding="utf-8")
    monkeypatch.chdir(ROOT)
    monkeypatch.setenv("SYLVIGENESE_ROOT", str(root))
    monkeypatch.delenv("SYLVIGENESE_VALIDATE", raising=False)
    output = root / "data" / "zone_essai" / "params" / "allometry.parquet"
    return {"config": config, "output": output, "tarif": tarif, "root": root}


def coefficients(path):
    """{espar: {terme: valeur}} du modèle etage_b."""
    table = pq.read_table(path).to_pylist()
    result = {}
    for row in table:
        assert row["model"] == "etage_b"
        result.setdefault(row["species"], {})[row["term"]] = row["value"]
    return result


def test_modele_etage_b_ecrit_et_conforme_au_contrat(tarif_setup, capsys):
    assert import_tarif.main(["--config", str(tarif_setup["config"])]) == 0
    table = pq.read_table(tarif_setup["output"]).to_pylist()
    assert table, "aucune ligne écrite"
    assert all(row["provisoire"] is True for row in table)
    assert all(row["species_group"] is None for row in table)
    assert all("allometrie_D" in row["source"] and "github.com/pobsteta/tarif-nemeton" in row["source"]
               for row in table)
    # le validateur du contrat, relancé à part
    code = subprocess.run([sys.executable, str(ROOT / "contracts" / "validate"),
                           "import_tarif.allometry", str(tarif_setup["output"])], cwd=ROOT).returncode
    assert code == 0


def test_hetre_a_b_et_c_et_le_code_espar_garde_son_zero(tarif_setup):
    import_tarif.main(["--config", str(tarif_setup["config"])])
    coef = coefficients(tarif_setup["output"])
    assert coef["09"] == {"a": -1.0, "b": 1.1, "c": 0.2}   # Fagus sylvatica, espar 09 (zéro de tête)
    assert "9" not in coef


def test_c_nul_ou_vide_donne_pas_de_terme_c(tarif_setup):
    import_tarif.main(["--config", str(tarif_setup["config"])])
    coef = coefficients(tarif_setup["output"])
    assert coef["52"] == {"a": 0.49, "b": 1.01}      # Pinus sylvestris : c_lnCPA = 0
    assert coef["62"] == {"a": 0.7, "b": 0.9}        # Picea abies : c_lnCPA vide


def test_essence_dans_les_deux_fichiers_garde_le_jeu_avec_houppier(tarif_setup, capsys):
    import_tarif.main(["--config", str(tarif_setup["config"])])
    assert coefficients(tarif_setup["output"])["09"]["a"] == -1.0      # pas le a = 0.9 du fichier IFN
    assert "Fagus_sylvatica : présente dans" in capsys.readouterr().err


def test_quercus_spec_va_a_02_et_03_et_a_rien_d_autre(tarif_setup, capsys):
    import_tarif.main(["--config", str(tarif_setup["config"])])
    coef = coefficients(tarif_setup["output"])
    assert coef["02"] == coef["03"] == {"a": -0.5, "b": 0.9, "c": 0.3}
    for other in ("04", "05", "06", "07", "08P", "08S", "29CE", "29CM", "34"):
        assert other not in coef
    assert "02, 03" in capsys.readouterr().err


def test_betula_spec_va_aux_deux_bouleaux_et_le_c_negatif_est_signale(tarif_setup, capsys):
    import_tarif.main(["--config", str(tarif_setup["config"])])
    coef = coefficients(tarif_setup["output"])
    assert coef["12P"] == coef["12V"] == {"a": -0.4, "b": 1.2, "c": -0.07}
    assert "est négatif" in capsys.readouterr().err


def test_essence_sans_code_espar_est_signalee_et_sautee(tarif_setup, capsys):
    assert import_tarif.main(["--config", str(tarif_setup["config"])]) == 0
    assert "Essence_inconnue" in capsys.readouterr().err
    names = {row["species"] for row in pq.read_table(tarif_setup["output"]).to_pylist()}
    # aucune espar n'a été inventée pour elle : 02, 03, 09, 12P, 12V, 52, 61, 62
    assert names == {"02", "03", "09", "12P", "12V", "52", "61", "62"}


def _without_external(tarif_setup):
    content = yaml.safe_load(tarif_setup["config"].read_text(encoding="utf-8"))
    del content["external"]
    tarif_setup["config"].write_text(yaml.safe_dump(content), encoding="utf-8")


def test_sans_tarif_nemeton_ni_params_existant_code_2_et_aucune_sortie(tarif_setup, capsys):
    _without_external(tarif_setup)
    assert import_tarif.main(["--config", str(tarif_setup["config"])]) == 2
    assert "external.tarif_nemeton_dir" in capsys.readouterr().err
    assert not tarif_setup["output"].exists()


def test_sans_tarif_nemeton_avec_params_existant_code_0_fichier_intact(tarif_setup, capsys):
    _without_external(tarif_setup)
    tarif_setup["output"].parent.mkdir(parents=True)
    tarif_setup["output"].write_bytes(b"existant")
    assert import_tarif.main(["--config", str(tarif_setup["config"])]) == 0
    assert "conservé tel quel" in capsys.readouterr().err
    assert tarif_setup["output"].read_bytes() == b"existant"


def test_dossier_sans_csv_code_2(tarif_setup, capsys):
    (tarif_setup["tarif"] / "resultats" / "etage_b" / "allometrie_D.csv").unlink()
    assert import_tarif.main(["--config", str(tarif_setup["config"])]) == 2
    assert "introuvable" in capsys.readouterr().err
    assert not tarif_setup["output"].exists()


def test_nombre_illisible_est_une_erreur_pas_un_zero(tarif_setup, capsys):
    file = tarif_setup["tarif"] / "resultats" / "etage_b" / "allometrie_D.csv"
    file.write_text(HEADER + "Fagus_sylvatica,10,abc,1.1,0.2,0.1,0.8\n", encoding="utf-8")
    assert import_tarif.main(["--config", str(tarif_setup["config"])]) == 2
    assert "pas un nombre" in capsys.readouterr().err


def test_lire_coefficients_colonne_c_absente(tmp_path):
    f = tmp_path / "x.csv"
    f.write_text("essence,a,b_lnH\nFagus_sylvatica,1.0,2.0\n", encoding="utf-8")
    assert import_tarif.read_coefficients(f) == {"Fagus_sylvatica": {"a": 1.0, "b": 2.0, "c": None}}


def test_lire_coefficients_a_absent_est_refuse(tmp_path):
    f = tmp_path / "x.csv"
    f.write_text("essence,b_lnH\nFagus_sylvatica,2.0\n", encoding="utf-8")
    with pytest.raises(ModuleError, match="absente"):
        import_tarif.read_coefficients(f)


def test_commit_lu_dans_le_dossier_git(tmp_path):
    git = tmp_path / ".git"
    (git / "refs" / "heads").mkdir(parents=True)
    (git / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (git / "refs" / "heads" / "main").write_text("0f51b9606165237b7cae2dda8809081adef869ac\n", encoding="utf-8")
    assert import_tarif.read_commit(tmp_path) == "0f51b96"
    assert import_tarif.read_commit(tmp_path / "rien") is None


# ------------------------------------------------------------------ houppier : hcb et cw (mission 034)
# Le calage est fabriqué par le test : un extrait de code/synth_calage.py (les trois relations et
# l'écrêtage de CR) et bornes_dimensions.csv. Les valeurs du hêtre sont celles de tarif-nemeton
# (commit 0f51b96) ; les autres sont d'essai.
CALAGE_SCRIPT = '''
def ajuster(d):
    D = d.dTLS.values
    X = np.c_[np.ones(len(d)), np.log(D)]
    lnE = np.log(d.crown_extent_max_m.clip(lower=0.3).values)

def forme(sp, par, T):
    CR = np.clip(par["CR_a"] + par["CR_b"] * np.log(D), 0.15, 0.95)
'''
BORNES_HEADER = "essence,nom,n_arbres,source,D_obs_q05,D_obs_q95,H_a,H_c,CR_a,CR_b,R_a,R_b\n"
BORNES_ROWS = [
    "Fagus_sylvatica,Hêtre,2987,essence,12.09,56.98,35.58,24.77,1.2673,-0.1686,-0.1465,0.4984",
    "Quercus_spec,Chênes,178,essence,24.68,71.26,32.51,20.37,1.1383,-0.1226,-1.1155,0.7457",
    'Abies_alba,Sapin,5,"forme de Picea_abies, décalée sur 5 arbres",49.97,60.93,43.73,50.52,0.8684,-0.0064,-0.9262,0.6417',
    "Betula_spec,Bouleaux,23,essence,10.38,39.50,31.55,24.77,1.2306,-0.1686,,0.4984",
    "Essence_inconnue,X,40,essence,10.0,50.0,30,20,1.0,-0.1,-0.5,0.5",
]


@pytest.fixture
def crown_setup(tarif_setup):
    tarif = tarif_setup["tarif"]
    (tarif / "resultats" / "synth_arbres").mkdir(parents=True)
    (tarif / "code").mkdir()
    (tarif / "resultats" / "synth_arbres" / "bornes_dimensions.csv").write_text(
        BORNES_HEADER + "\n".join(BORNES_ROWS) + "\n", encoding="utf-8")
    (tarif / "code" / "synth_calage.py").write_text(CALAGE_SCRIPT, encoding="utf-8")
    return tarif_setup


def crown(path):
    """{espar: {modèle: {terme: (valeur, source)}}} pour hcb et cw."""
    result = {}
    for row in pq.read_table(path).to_pylist():
        if row["model"] in ("hcb", "cw"):
            result.setdefault(row["species"], {}).setdefault(row["model"], {})[row["term"]] = (row["value"], row["source"])
    return result


def test_hcb_et_cw_ecrits_avec_les_bornes_de_synth_calage(crown_setup, capsys):
    assert import_tarif.main(["--config", str(crown_setup["config"])]) == 0   # le validateur du contrat passe
    c = crown(crown_setup["output"])
    beech = c["09"]
    assert {t: v for t, (v, _) in beech["hcb"].items()} == {"CR_a": 1.2673, "CR_b": -0.1686, "CR_min": 0.15, "CR_max": 0.95}
    assert {t: v for t, (v, _) in beech["cw"].items()} == {"R_a": -0.1465, "R_b": 0.4984}
    table = pq.read_table(crown_setup["output"]).to_pylist()
    assert all(r["provisoire"] is True for r in table)
    assert "bornes_dimensions.csv" in beech["hcb"]["CR_a"][1] and "d130 en cm vérifié" in beech["cw"]["R_a"][1]
    assert "synth_calage.py ligne 8" in beech["hcb"]["CR_min"][1]   # ligne de l'écrêtage dans le script d'essai
    # l'étage B reste là, intact
    assert coefficients_by_model(crown_setup["output"], "etage_b")["09"] == {"a": -1.0, "b": 1.1, "c": 0.2}


def coefficients_by_model(path, model):
    result = {}
    for row in pq.read_table(path).to_pylist():
        if row["model"] == model:
            result.setdefault(row["species"], {})[row["term"]] = row["value"]
    return result


def test_hetre_de_40_cm_a_un_houppier_de_l_ordre_de_celui_observe(crown_setup):
    """Point du terrain : d130 = 40 cm, hêtre. cw = 2 exp(R_a + R_b ln 40) ~ 10,9 m (tarif-nemeton observe
    une étendue médiane de 5,4 m pour 35 à 45 cm) ; CR = 1,2673 - 0,1686 ln 40 ~ 0,645, hcb = 0,355 h."""
    import math
    import_tarif.main(["--config", str(crown_setup["config"])])
    c = crown(crown_setup["output"])["09"]
    cw = 2 * math.exp(c["cw"]["R_a"][0] + c["cw"]["R_b"][0] * math.log(40))
    cr = c["hcb"]["CR_a"][0] + c["hcb"]["CR_b"][0] * math.log(40)
    assert 10.7 < cw < 11.1
    assert abs(cr - 0.6453) < 1e-3
    assert c["hcb"]["CR_min"][0] <= cr <= c["hcb"]["CR_max"][0]


def test_quercus_spec_hcb_et_cw_pour_02_et_03_seulement(crown_setup):
    import_tarif.main(["--config", str(crown_setup["config"])])
    c = crown(crown_setup["output"])
    assert c["02"] == c["03"]
    assert set(c) == {"02", "03", "09", "61"}
    assert "05" not in c


def test_essence_empruntee_est_signalee_et_prend_le_nom_de_la_forme(crown_setup, capsys):
    import_tarif.main(["--config", str(crown_setup["config"])])
    err = capsys.readouterr().err
    assert "Abies_alba : coefficients de houppier empruntés" in err
    assert "forme de Picea_abies" in crown(crown_setup["output"])["61"]["hcb"]["CR_a"][1]


def test_coefficient_manquant_signale_et_essence_sautee_sans_valeur_inventee(crown_setup, capsys):
    import_tarif.main(["--config", str(crown_setup["config"])])
    err = capsys.readouterr().err
    assert "Betula_spec (bornes_dimensions.csv) : R_a manquant" in err
    assert "Essence_inconnue (bornes_dimensions.csv) : aucun code espar" in err
    c = crown(crown_setup["output"])
    assert "12P" not in c and "12V" not in c    # ni hcb ni cw : rien n'est comblé
    # l'essence a gardé son étage B mais simulate la refusera : dit au rapport
    assert "sans hcb ni cw" in err


def test_d130_en_metres_arrete_le_module_sans_rien_ecrire(crown_setup, capsys):
    file = crown_setup["tarif"] / "resultats" / "synth_arbres" / "bornes_dimensions.csv"
    file.write_text(BORNES_HEADER + "Fagus_sylvatica,Hêtre,2987,essence,0.12,0.57,35.58,24.77,1.2,-0.1,-0.1,0.5\n",
                    encoding="utf-8")
    assert import_tarif.main(["--config", str(crown_setup["config"])]) == 2
    err = capsys.readouterr().err
    assert "pas en centimètres" in err
    assert not crown_setup["output"].exists()


def test_d130_en_millimetres_arrete_aussi_le_module(crown_setup, capsys):
    file = crown_setup["tarif"] / "resultats" / "synth_arbres" / "bornes_dimensions.csv"
    file.write_text(BORNES_HEADER + "Fagus_sylvatica,Hêtre,2987,essence,120,570,35.58,24.77,1.2,-0.1,-0.1,0.5\n",
                    encoding="utf-8")
    assert import_tarif.main(["--config", str(crown_setup["config"])]) == 2
    assert "pas en centimètres" in capsys.readouterr().err


def test_script_sans_ecretage_de_cr_refuse_au_lieu_de_deviner_les_bornes(crown_setup, capsys):
    (crown_setup["tarif"] / "code" / "synth_calage.py").write_text(
        CALAGE_SCRIPT.replace("np.clip(", "np.maximum("), encoding="utf-8")
    assert import_tarif.main(["--config", str(crown_setup["config"])]) == 2
    assert "CR_min et CR_max ne sont pas devinés" in capsys.readouterr().err
    assert not crown_setup["output"].exists()


def test_script_dont_la_relation_sur_d_a_change_est_refuse(crown_setup, capsys):
    (crown_setup["tarif"] / "code" / "synth_calage.py").write_text(
        CALAGE_SCRIPT.replace("D = d.dTLS.values", "D = d.diametre_m.values"), encoding="utf-8")
    assert import_tarif.main(["--config", str(crown_setup["config"])]) == 2
    assert "relation « D = d.dTLS » introuvable" in capsys.readouterr().err


def test_sans_fichier_de_bornes_etage_b_seul_et_signalement(tarif_setup, capsys):
    """Les tests de 027 : pas de bornes dans le dossier. L'étage B est écrit, hcb et cw sont dits absents."""
    assert import_tarif.main(["--config", str(tarif_setup["config"])]) == 0
    assert "hcb et cw non importés" in capsys.readouterr().err
    assert crown(tarif_setup["output"]) == {}


def test_bornes_en_double_ou_nombre_illisible_refuses(tmp_path):
    f = tmp_path / "b.csv"
    f.write_text(BORNES_HEADER + BORNES_ROWS[0] + "\n" + BORNES_ROWS[0] + "\n", encoding="utf-8")
    with pytest.raises(ModuleError, match="en double"):
        import_tarif.read_crown_bounds_table(f)
    f.write_text(BORNES_HEADER + BORNES_ROWS[0].replace("1.2673", "abc") + "\n", encoding="utf-8")
    with pytest.raises(ModuleError, match="pas un nombre"):
        import_tarif.read_crown_bounds_table(f)
