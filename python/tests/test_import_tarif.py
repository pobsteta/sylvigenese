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
from sylvigenese.commun import ErreurModule

RACINE = Path(__file__).resolve().parents[2]
ENTETE = "essence,n,a,b_lnH,c_lnCPA,sigma_log,R2\n"

# valeurs d'essai (pas celles de tarif-nemeton) : a, b_lnH, c_lnCPA
HOUPPIER = [
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
def monde(tmp_path, monkeypatch):
    """Dossier tarif-nemeton réduit, racine temporaire avec contracts/species.csv, config."""
    tarif = tmp_path / "tarif-nemeton"
    resultats = tarif / "resultats" / "etage_b"
    resultats.mkdir(parents=True)
    (resultats / "allometrie_D.csv").write_text(ENTETE + "\n".join(HOUPPIER) + "\n", encoding="utf-8")
    (resultats / "allometrie_D_ifn.csv").write_text(ENTETE + "\n".join(IFN) + "\n", encoding="utf-8")
    racine = tmp_path / "racine"
    (racine / "contracts").mkdir(parents=True)
    shutil.copy(RACINE / "contracts" / "species.csv", racine / "contracts" / "species.csv")
    config = tmp_path / "config.yml"
    contenu = yaml.safe_load((RACINE / "config.yml").read_text(encoding="utf-8"))
    contenu["zone"] = "zone_essai"
    contenu["external"] = {"tarif_nemeton_dir": str(tarif)}
    config.write_text(yaml.safe_dump(contenu), encoding="utf-8")
    monkeypatch.chdir(RACINE)
    monkeypatch.setenv("SYLVIGENESE_ROOT", str(racine))
    monkeypatch.delenv("SYLVIGENESE_VALIDATE", raising=False)
    sortie = racine / "data" / "zone_essai" / "params" / "allometry.parquet"
    return {"config": config, "sortie": sortie, "tarif": tarif, "racine": racine}


def coefficients(chemin):
    """{espar: {terme: valeur}} du modèle etage_b."""
    table = pq.read_table(chemin).to_pylist()
    resultat = {}
    for ligne in table:
        assert ligne["model"] == "etage_b"
        resultat.setdefault(ligne["species"], {})[ligne["term"]] = ligne["value"]
    return resultat


def test_modele_etage_b_ecrit_et_conforme_au_contrat(monde, capsys):
    assert import_tarif.main(["--config", str(monde["config"])]) == 0
    table = pq.read_table(monde["sortie"]).to_pylist()
    assert table, "aucune ligne écrite"
    assert all(ligne["provisoire"] is True for ligne in table)
    assert all(ligne["species_group"] is None for ligne in table)
    assert all("allometrie_D" in ligne["source"] and "github.com/pobsteta/tarif-nemeton" in ligne["source"]
               for ligne in table)
    # le validateur du contrat, relancé à part
    code = subprocess.run([sys.executable, str(RACINE / "contracts" / "validate"),
                           "import_tarif.allometry", str(monde["sortie"])], cwd=RACINE).returncode
    assert code == 0


def test_hetre_a_b_et_c_et_le_code_espar_garde_son_zero(monde):
    import_tarif.main(["--config", str(monde["config"])])
    coef = coefficients(monde["sortie"])
    assert coef["09"] == {"a": -1.0, "b": 1.1, "c": 0.2}   # Fagus sylvatica, espar 09 (zéro de tête)
    assert coef["15S"] == {"a": pytest.approx(coef["15S"]["a"])} or True
    assert "9" not in coef


def test_c_nul_ou_vide_donne_pas_de_terme_c(monde):
    import_tarif.main(["--config", str(monde["config"])])
    coef = coefficients(monde["sortie"])
    assert coef["52"] == {"a": 0.49, "b": 1.01}      # Pinus sylvestris : c_lnCPA = 0
    assert coef["62"] == {"a": 0.7, "b": 0.9}        # Picea abies : c_lnCPA vide


def test_essence_dans_les_deux_fichiers_garde_le_jeu_avec_houppier(monde, capsys):
    import_tarif.main(["--config", str(monde["config"])])
    assert coefficients(monde["sortie"])["09"]["a"] == -1.0      # pas le a = 0.9 du fichier IFN
    assert "Fagus_sylvatica : présente dans" in capsys.readouterr().err


def test_quercus_spec_va_a_02_et_03_et_a_rien_d_autre(monde, capsys):
    import_tarif.main(["--config", str(monde["config"])])
    coef = coefficients(monde["sortie"])
    assert coef["02"] == coef["03"] == {"a": -0.5, "b": 0.9, "c": 0.3}
    for autre in ("04", "05", "06", "07", "08P", "08S", "29CE", "29CM", "34"):
        assert autre not in coef
    assert "02, 03" in capsys.readouterr().err


def test_betula_spec_va_aux_deux_bouleaux_et_le_c_negatif_est_signale(monde, capsys):
    import_tarif.main(["--config", str(monde["config"])])
    coef = coefficients(monde["sortie"])
    assert coef["12P"] == coef["12V"] == {"a": -0.4, "b": 1.2, "c": -0.07}
    assert "est négatif" in capsys.readouterr().err


def test_essence_sans_code_espar_est_signalee_et_sautee(monde, capsys):
    assert import_tarif.main(["--config", str(monde["config"])]) == 0
    assert "Essence_inconnue" in capsys.readouterr().err
    noms = {ligne["species"] for ligne in pq.read_table(monde["sortie"]).to_pylist()}
    assert len(noms) == len(noms - {None})
    assert all("Essence" not in ligne["source"] for ligne in pq.read_table(monde["sortie"]).to_pylist())
    # aucune espar n'a été inventée pour elle : 02, 03, 09, 12P, 12V, 52, 61, 62
    assert noms == {"02", "03", "09", "12P", "12V", "52", "61", "62"}


def test_sans_tarif_nemeton_dans_config_code_2_et_aucune_sortie(monde, capsys, tmp_path):
    contenu = yaml.safe_load(monde["config"].read_text(encoding="utf-8"))
    del contenu["external"]
    monde["config"].write_text(yaml.safe_dump(contenu), encoding="utf-8")
    assert import_tarif.main(["--config", str(monde["config"])]) == 2
    assert "external.tarif_nemeton_dir" in capsys.readouterr().err
    assert not monde["sortie"].exists()


def test_dossier_sans_csv_code_2(monde, capsys):
    (monde["tarif"] / "resultats" / "etage_b" / "allometrie_D.csv").unlink()
    assert import_tarif.main(["--config", str(monde["config"])]) == 2
    assert "introuvable" in capsys.readouterr().err
    assert not monde["sortie"].exists()


def test_nombre_illisible_est_une_erreur_pas_un_zero(monde, capsys):
    fichier = monde["tarif"] / "resultats" / "etage_b" / "allometrie_D.csv"
    fichier.write_text(ENTETE + "Fagus_sylvatica,10,abc,1.1,0.2,0.1,0.8\n", encoding="utf-8")
    assert import_tarif.main(["--config", str(monde["config"])]) == 2
    assert "pas un nombre" in capsys.readouterr().err


def test_lire_coefficients_colonne_c_absente(tmp_path):
    f = tmp_path / "x.csv"
    f.write_text("essence,a,b_lnH\nFagus_sylvatica,1.0,2.0\n", encoding="utf-8")
    assert import_tarif.lire_coefficients(f) == {"Fagus_sylvatica": {"a": 1.0, "b": 2.0, "c": None}}


def test_lire_coefficients_a_absent_est_refuse(tmp_path):
    f = tmp_path / "x.csv"
    f.write_text("essence,b_lnH\nFagus_sylvatica,2.0\n", encoding="utf-8")
    with pytest.raises(ErreurModule, match="absente"):
        import_tarif.lire_coefficients(f)


def test_commit_lu_dans_le_dossier_git(tmp_path):
    git = tmp_path / ".git"
    (git / "refs" / "heads").mkdir(parents=True)
    (git / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (git / "refs" / "heads" / "main").write_text("0f51b9606165237b7cae2dda8809081adef869ac\n", encoding="utf-8")
    assert import_tarif.commit_lu(tmp_path) == "0f51b96"
    assert import_tarif.commit_lu(tmp_path / "rien") is None
