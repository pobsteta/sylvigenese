//! Tests de l'appel du validateur par `simulate` (mission 012, réécrits en 037/038).
//!
//! Chaque lancement se fait avec `SYLVIGENESE_ROOT` sur une **racine temporaire vide** : aucun
//! test ne lit ni n'écrit une sortie ignorée par git du dépôt (copie `git archive` suffisante).
//! Le validateur est remplacé par un faux script (codes 0, 3, absent), ou c'est le vrai
//! (`contracts/validate`, versionné).
//!
//! Le cas nominal (code 0 avec le vrai validateur, sorties `sim/` acceptées) demande une zone
//! construite par la chaîne : il est couvert par `tests/integration.rs`
//! (`la_chaine_du_jeu_fictif_simule_100_ans_et_le_validateur_l_accepte`), qui la construit
//! lui-même. Ici, on vérifie que config.yml passe par le validateur **avant** toute lecture de
//! la zone, et que son refus ou son absence donnent le code 2.

use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Command, Output};

fn depot() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("..")
}

/// Dossier temporaire propre à un test, vidé d'abord.
fn dossier_temporaire(nom: &str) -> PathBuf {
    let dossier =
        std::env::temp_dir().join(format!("simulate-squelette-{}-{nom}", std::process::id()));
    let _ = fs::remove_dir_all(&dossier);
    fs::create_dir_all(&dossier).unwrap();
    dossier
}

/// Un faux validateur qui écrit ses arguments dans `appels.txt` puis sort avec `code`.
fn faux_validateur(dossier: &Path, code: i32) -> PathBuf {
    let chemin = dossier.join("validate");
    let journal = dossier.join("appels.txt");
    fs::write(
        &chemin,
        format!(
            "import sys\nwith open({journal:?}, 'a') as f:\n    f.write(' '.join(sys.argv[1:]) + '\\n')\nsys.exit({code})\n"
        ),
    )
    .unwrap();
    chemin
}

/// Lance `simulate` sur une config, avec une racine de données vide et un validateur donné
/// (sans validateur imposé : le vrai, `contracts/validate` depuis la racine du dépôt).
fn lancer(config: &Path, racine_donnees: &Path, validateur: Option<&Path>) -> Output {
    let mut commande = Command::new(env!("CARGO_BIN_EXE_simulate"));
    commande
        .current_dir(depot())
        .env("SYLVIGENESE_ROOT", racine_donnees)
        .env_remove("SYLVIGENESE_VALIDATE")
        .arg("--config")
        .arg(config);
    if let Some(v) = validateur {
        commande.env("SYLVIGENESE_VALIDATE", v);
    }
    commande.output().unwrap()
}

fn config_du_depot() -> PathBuf {
    depot().join("config.yml")
}

fn erreur(sortie: &Output) -> String {
    String::from_utf8_lossy(&sortie.stderr).to_string()
}

#[test]
fn lit_le_config_du_depot() {
    let config = simulate::config::lire(&config_du_depot()).unwrap();
    assert_eq!(config.crs, "EPSG:2154");
    assert_eq!(config.grid.resolution_m, 25);
    assert_eq!(config.management, "none");
}

#[test]
fn config_absent_donne_une_erreur() {
    let erreur = simulate::config::lire(&PathBuf::from("/nulle/part/config.yml")).unwrap_err();
    assert!(erreur.contains("illisible"), "{erreur}");
}

#[test]
fn le_validateur_est_appele_sur_config_yml_avant_la_zone() {
    // Faux validateur qui accepte : config.yml passe, puis la zone (absente de la racine vide)
    // est refusée, code 2. Le validateur n'a été appelé que pour config.yml : rien n'est écrit.
    let dossier = dossier_temporaire("accepte");
    let racine = dossier.join("racine");
    fs::create_dir_all(&racine).unwrap();
    let v = faux_validateur(&dossier, 0);
    let sortie = lancer(&config_du_depot(), &racine, Some(&v));
    assert_eq!(sortie.status.code(), Some(2), "{}", erreur(&sortie));
    assert!(
        !erreur(&sortie).contains("non conforme"),
        "{}",
        erreur(&sortie)
    );
    let appels = fs::read_to_string(dossier.join("appels.txt")).unwrap();
    let config = config_du_depot().to_string_lossy().to_string();
    assert_eq!(appels, format!("config {config}\n"));
    assert!(!racine.join("tests").exists() && !racine.join("data").exists());
    fs::remove_dir_all(&dossier).unwrap();
}

#[test]
fn sortie_2_si_le_validateur_refuse() {
    let dossier = dossier_temporaire("refus");
    let v = faux_validateur(&dossier, 3);
    let sortie = lancer(&config_du_depot(), &dossier, Some(&v));
    assert_eq!(sortie.status.code(), Some(2));
    assert!(
        erreur(&sortie).contains("config.yml non conforme"),
        "{}",
        erreur(&sortie)
    );
    fs::remove_dir_all(&dossier).unwrap();
}

#[test]
fn sortie_2_si_le_validateur_est_absent() {
    let dossier = dossier_temporaire("absent");
    let absent = PathBuf::from("/nulle/part/validate");
    let sortie = lancer(&config_du_depot(), &dossier, Some(&absent));
    assert_eq!(sortie.status.code(), Some(2));
    assert!(
        erreur(&sortie).contains("validateur introuvable"),
        "{}",
        erreur(&sortie)
    );
    fs::remove_dir_all(&dossier).unwrap();
}

#[test]
fn sortie_2_si_config_absent() {
    let dossier = dossier_temporaire("sans-config");
    let v = faux_validateur(&dossier, 0);
    let sortie = lancer(Path::new("/nulle/part/config.yml"), &dossier, Some(&v));
    assert_eq!(sortie.status.code(), Some(2));
    // Le validateur n'est pas appelé sur un fichier qui n'existe pas.
    assert!(!dossier.join("appels.txt").exists());
    fs::remove_dir_all(&dossier).unwrap();
}

#[test]
fn le_vrai_validateur_accepte_config_yml_du_depot() {
    // Le vrai contracts/validate juge config.yml conforme : simulate passe la validation et ne
    // s'arrête qu'à la zone, absente de la racine vide (code 2, sans « non conforme »).
    let dossier = dossier_temporaire("vrai");
    let sortie = lancer(&config_du_depot(), &dossier, None);
    assert_eq!(sortie.status.code(), Some(2), "{}", erreur(&sortie));
    let texte = erreur(&sortie);
    assert!(!texte.contains("non conforme"), "{texte}");
    assert!(!texte.contains("validateur introuvable"), "{texte}");
    assert!(!texte.contains("config.yml introuvable"), "{texte}");
    fs::remove_dir_all(&dossier).unwrap();
}
