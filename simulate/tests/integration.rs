//! Bout en bout de `simulate` sur le jeu fictif (mission 038) : options de la ligne de commande,
//! dossier de la zone, et la chaîne `make prepare biomes trees dynamics` puis `make simulate`
//! dans une **racine temporaire** construite par le test.
//!
//! Le test ne dépend d'aucune sortie ignorée par git : il copie seulement les entrées versionnées
//! du jeu fictif (`inputs/`, `zone.yml`, et les paramètres versionnés de `params/` :
//! `allometry.parquet`, `tarif.parquet`, `indicator_values.csv`), `biomes/` et
//! `contracts/species.csv`, puis fait tourner la chaîne avec `SYLVIGENESE_ROOT` sur cette racine.
//! Il faut R (`Rscript`) : sans lui, le test **échoue** en le disant, il ne saute jamais.
//!
//! La config est `config.yml` du dépôt, telle quelle (zone_fictive, graine, t0, 100 ans) :
//! c'est elle que Pascal rejoue. Coordonnées : EPSG:2154, x = est, y = nord.

use std::path::{Path, PathBuf};
use std::process::{Command, Output};

use simulate::{dossier_zone, lire_options, Options};

fn depot() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .canonicalize()
        .unwrap()
}

fn arguments(texte: &[&str]) -> Vec<String> {
    texte.iter().map(|t| t.to_string()).collect()
}

// ------------------------------------------------------------------------------------------
// Options et dossier de zone

#[test]
fn les_options_se_lisent_et_l_inject_nan_prend_une_annee_facultative() {
    let options = lire_options(&arguments(&[])).unwrap();
    assert_eq!(
        options,
        Options {
            config: PathBuf::from("config.yml"),
            threads: None,
            memoire_disponible: None,
            inject_nan: None
        }
    );
    let options = lire_options(&arguments(&[
        "--config",
        "a.yml",
        "--threads",
        "7",
        "--memoire-disponible",
        "1",
        "--inject-nan",
        "2030",
    ]))
    .unwrap();
    assert_eq!(options.config, PathBuf::from("a.yml"));
    assert_eq!(options.threads, Some(7));
    assert_eq!(options.memoire_disponible, Some(1));
    assert_eq!(options.inject_nan, Some(Some(2030)));
    // Sans année (dernière option, ou suivie d'une autre option) : t0 + 1, choisi par lib.rs.
    assert_eq!(
        lire_options(&arguments(&["--inject-nan"]))
            .unwrap()
            .inject_nan,
        Some(None)
    );
    let options = lire_options(&arguments(&["--inject-nan", "--threads", "2"])).unwrap();
    assert_eq!((options.inject_nan, options.threads), (Some(None), Some(2)));
    assert!(lire_options(&arguments(&["--threads", "0"])).is_err());
    assert!(lire_options(&arguments(&["--threads"])).is_err());
    assert!(lire_options(&arguments(&["--memoire-disponible", "beaucoup"])).is_err());
    assert!(lire_options(&arguments(&["--graine", "1"])).is_err());
}

#[test]
fn le_dossier_de_zone_suit_la_regle_de_prepare_zone_dir() {
    let racine = Path::new("/racine");
    assert_eq!(
        dossier_zone(racine, "zone_fictive").unwrap(),
        PathBuf::from("/racine/tests/fixtures/zone_fictive")
    );
    assert_eq!(
        dossier_zone(racine, "vosges").unwrap(),
        PathBuf::from("/racine/data/vosges")
    );
    for refusee in ["", "../ailleurs", "a/b"] {
        let erreur = dossier_zone(racine, refusee).unwrap_err();
        assert_eq!(erreur.code_sortie(), 2);
    }
}

#[test]
fn une_config_introuvable_sort_avec_le_code_2_et_le_dit() {
    let sortie = Command::new(env!("CARGO_BIN_EXE_simulate"))
        .current_dir(depot())
        .args(["--config", "/nulle/part/config.yml"])
        .output()
        .unwrap();
    assert_eq!(sortie.status.code(), Some(2));
    let texte = String::from_utf8_lossy(&sortie.stderr);
    assert!(texte.contains("config.yml introuvable"), "{texte}");
}

#[test]
fn une_option_inconnue_sort_avec_le_code_2() {
    let sortie = Command::new(env!("CARGO_BIN_EXE_simulate"))
        .args(["--graine", "3"])
        .output()
        .unwrap();
    assert_eq!(sortie.status.code(), Some(2));
    assert!(String::from_utf8_lossy(&sortie.stderr).contains("usage"));
}

// ------------------------------------------------------------------------------------------
// La chaîne sur le jeu fictif

fn copier_dossier(source: &Path, cible: &Path) {
    std::fs::create_dir_all(cible).unwrap();
    for entree in std::fs::read_dir(source).unwrap() {
        let chemin = entree.unwrap().path();
        let destination = cible.join(chemin.file_name().unwrap());
        if chemin.is_dir() {
            copier_dossier(&chemin, &destination);
        } else {
            std::fs::copy(&chemin, &destination).unwrap();
        }
    }
}

/// Une racine temporaire avec les seules entrées versionnées du jeu fictif.
fn racine_temporaire() -> PathBuf {
    let racine =
        std::env::temp_dir().join(format!("simulate-038-integration-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&racine);
    let depot = depot();
    let fictif = depot.join("tests/fixtures/zone_fictive");
    let zone = racine.join("tests/fixtures/zone_fictive");
    copier_dossier(&fictif.join("inputs"), &zone.join("inputs"));
    std::fs::copy(fictif.join("zone.yml"), zone.join("zone.yml")).unwrap();
    std::fs::create_dir_all(zone.join("params")).unwrap();
    for nom in ["allometry.parquet", "tarif.parquet", "indicator_values.csv"] {
        std::fs::copy(
            fictif.join("params").join(nom),
            zone.join("params").join(nom),
        )
        .unwrap();
    }
    copier_dossier(&depot.join("biomes"), &racine.join("biomes"));
    std::fs::create_dir_all(racine.join("contracts")).unwrap();
    std::fs::copy(
        depot.join("contracts/species.csv"),
        racine.join("contracts/species.csv"),
    )
    .unwrap();
    std::fs::copy(depot.join("config.yml"), racine.join("config.yml")).unwrap();
    racine
}

fn make(racine: &Path, cibles: &[&str]) -> Output {
    Command::new("make")
        .current_dir(depot())
        .env("SYLVIGENESE_ROOT", racine)
        .args(cibles)
        .arg(format!("CONFIG={}", racine.join("config.yml").display()))
        .output()
        .unwrap()
}

fn simulate_debug(racine: &Path, options: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_simulate"))
        .current_dir(depot())
        .env("SYLVIGENESE_ROOT", racine)
        .arg("--config")
        .arg(racine.join("config.yml"))
        .args(options)
        .output()
        .unwrap()
}

fn queue(sortie: &Output) -> String {
    let erreur = String::from_utf8_lossy(&sortie.stderr);
    let debut = erreur.len().saturating_sub(3000);
    format!(
        "code {:?}\n{}\n{}",
        sortie.status.code(),
        String::from_utf8_lossy(&sortie.stdout),
        &erreur[debut..]
    )
}

#[test]
fn la_chaine_du_jeu_fictif_simule_100_ans_et_le_validateur_l_accepte() {
    let rscript = Command::new("Rscript").arg("--version").output();
    assert!(
        matches!(&rscript, Ok(s) if s.status.success()),
        "Rscript introuvable : ce test construit la zone fictive par make prepare biomes trees dynamics, il lui faut R"
    );
    let racine = racine_temporaire();
    let zone = racine.join("tests/fixtures/zone_fictive");
    let chaine = make(&racine, &["prepare", "biomes", "trees", "dynamics"]);
    assert!(
        chaine.status.success(),
        "chaîne en amont de simulate : {}",
        queue(&chaine)
    );
    assert!(zone.join("trees_init").is_dir() && zone.join("params/height_curve.parquet").is_file());

    // Code 4 : refusé avant toute écriture, aucun sim/.
    let memoire = simulate_debug(&racine, &["--memoire-disponible", "1"]);
    assert_eq!(memoire.status.code(), Some(4), "{}", queue(&memoire));
    assert!(String::from_utf8_lossy(&memoire.stderr).contains("mémoire insuffisante"));
    assert!(!zone.join("sim").exists() && !zone.join(simulate::DOSSIER_EN_COURS).exists());

    // Code 3 : un NaN injecté dans l'état de la première année simulée, aucun sim/.
    let nan = simulate_debug(&racine, &["--inject-nan"]);
    assert_eq!(nan.status.code(), Some(3), "{}", queue(&nan));
    assert!(String::from_utf8_lossy(&nan.stderr).contains("NaN"));
    assert!(!zone.join("sim").exists() && !zone.join(simulate::DOSSIER_EN_COURS).exists());

    // Nominal : make simulate (release, --locked), puis le validateur sur toute la zone.
    let nominal = make(&racine, &["simulate"]);
    assert!(
        nominal.status.success(),
        "make simulate : {}",
        queue(&nominal)
    );
    let sim = zone.join("sim");
    let texte = std::fs::read_to_string(sim.join("run.json")).unwrap();
    let run: serde_json::Value = serde_json::from_str(&texte).unwrap();
    let t0 = run["t0"].as_i64().unwrap();
    let years = run["years"].as_i64().unwrap();
    assert_eq!(years, 100);
    for annee in t0..=t0 + years {
        for sorte in ["trees", "cells"] {
            let fichier = sim
                .join(sorte)
                .join(format!("year={annee}"))
                .join("part-00000.parquet");
            assert!(fichier.is_file(), "{} absent", fichier.display());
        }
    }
    let octets = std::fs::read(racine.join("config.yml")).unwrap();
    assert_eq!(run["config_sha256"], simulate::sorties::sha256_hex(&octets));
    let duree = run["duration_s"].as_f64().unwrap();
    assert!(
        duree > 0.0 && duree < 1800.0,
        "100 ans en {duree} s (CLAUDE.md : moins de 30 minutes)"
    );
    let validation = Command::new("python3")
        .current_dir(depot())
        .arg("contracts/validate")
        .arg("--zone")
        .arg(&zone)
        .output()
        .unwrap();
    assert!(
        validation.status.success(),
        "make validate : {}",
        queue(&validation)
    );
    eprintln!("[integration] 100 ans simulés en {duree:.1} s");
    std::fs::remove_dir_all(&racine).unwrap();
}
