//! Tests du squelette `simulate` (mission 012).
//!
//! Le validateur est remplacé par un faux script pour les cas 0 / 3 / absent. Le test
//! d'intégration appelle le vrai validateur : rouge tant que `contracts/validate`
//! (mission 009) n'est pas dans l'arbre, sauf si `SYLVIGENESE_VALIDATE` le désigne.

use std::fs;
use std::path::PathBuf;
use std::process::Command;

fn racine() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("..")
}

/// Dossier temporaire propre à un test.
fn dossier_temporaire(nom: &str) -> PathBuf {
    let dossier = std::env::temp_dir().join(format!("simulate-test-{}-{nom}", std::process::id()));
    fs::create_dir_all(&dossier).unwrap();
    dossier
}

fn faux_validateur(dossier: &PathBuf, code: i32) -> PathBuf {
    let chemin = dossier.join("validate");
    fs::write(&chemin, format!("import sys\nsys.exit({code})\n")).unwrap();
    chemin
}

/// Lance l'exécutable `simulate` avec une config donnée et un validateur donné.
fn lancer(config: &PathBuf, validateur: Option<&PathBuf>) -> i32 {
    let mut commande = Command::new(env!("CARGO_BIN_EXE_simulate"));
    commande.current_dir(racine()).arg("--config").arg(config);
    // Sans validateur imposé, l'environnement du test est transmis tel quel.
    if let Some(v) = validateur {
        commande.env("SYLVIGENESE_VALIDATE", v);
    }
    commande.output().unwrap().status.code().unwrap()
}

fn config_du_depot() -> PathBuf {
    racine().join("config.yml")
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
fn sortie_0_si_le_validateur_dit_0() {
    let dossier = dossier_temporaire("ok");
    let v = faux_validateur(&dossier, 0);
    assert_eq!(lancer(&config_du_depot(), Some(&v)), 0);
}

#[test]
fn sortie_2_si_le_validateur_refuse() {
    let dossier = dossier_temporaire("refus");
    let v = faux_validateur(&dossier, 3);
    assert_eq!(lancer(&config_du_depot(), Some(&v)), 2);
}

#[test]
fn sortie_2_si_le_validateur_est_absent() {
    let absent = PathBuf::from("/nulle/part/validate");
    assert_eq!(lancer(&config_du_depot(), Some(&absent)), 2);
}

#[test]
fn sortie_2_si_config_absent() {
    let dossier = dossier_temporaire("sans-config");
    let v = faux_validateur(&dossier, 0);
    assert_eq!(lancer(&PathBuf::from("/nulle/part/config.yml"), Some(&v)), 2);
}

#[test]
fn integration_le_vrai_validateur_accepte_config_yml() {
    // Rouge tant que contracts/validate (mission 009) est absent de l'arbre.
    assert_eq!(lancer(&config_du_depot(), None), 0);
}
