//! Script de compilation de `simulate` (mission 087) : lit la release dont vient le code et la
//! passe au moteur par la variable de compilation `SYLVIGENESE_RELEASE_COMPILEE` (lue par
//! `simulate::RELEASE`, écrite dans `run.json` et par `simulate --version`).
//!
//! Étape du BRIEF codée ici : BRIEF §13 (rejouable). La règle est dans `src/release.rs`, inclus
//! tel quel : git d'abord, sinon `SYLVIGENESE_RELEASE`, sinon `inconnue` ; les deux derniers cas
//! sont signalés par un avertissement de cargo. Une `SYLVIGENESE_RELEASE` mal formée fait
//! échouer la compilation (message en français).
//!
//! Recompilation : quand `SYLVIGENESE_RELEASE`, la tête de git, l'index, les étiquettes ou les
//! fichiers de `simulate/` changent. Limite : une modification non indexée hors de `simulate/`
//! ne relance pas ce script, la marque `-dirty` peut alors manquer jusqu'au prochain `git add`
//! ou commit (le code de `simulate` compilé, lui, est bien celui du dépôt).

#[allow(dead_code)]
#[path = "src/release.rs"]
mod release;

use std::path::{Path, PathBuf};

fn main() {
    let paquet = PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").expect("CARGO_MANIFEST_DIR posé par cargo"));
    let racine = match paquet.parent() {
        Some(parent) => parent.to_path_buf(),
        None => paquet.clone(),
    };

    println!("cargo:rerun-if-env-changed={}", release::VARIABLE);
    for fichier in ["build.rs", "Cargo.toml", "Cargo.lock", "src"] {
        println!("cargo:rerun-if-changed={}", paquet.join(fichier).display());
    }
    let git = release::decrire_par_git(&racine);
    if git.is_ok() {
        surveiller_git(&racine);
    }

    let variable = std::env::var(release::VARIABLE).ok();
    match release::choisir(git, variable) {
        Ok((valeur, avertissements)) => {
            for avertissement in avertissements {
                println!("cargo:warning={avertissement}");
            }
            println!("cargo:rustc-env=SYLVIGENESE_RELEASE_COMPILEE={valeur}");
        }
        Err(message) => {
            eprintln!("simulate : compilation refusée : {message}");
            std::process::exit(1);
        }
    }
}

/// Relance ce script quand la tête, l'index ou les étiquettes de git changent. Seuls les chemins
/// qui existent sont donnés (un chemin absent ferait relancer le script à chaque compilation).
fn surveiller_git(racine: &Path) {
    let dossier_git = lire_chemin_git(racine, "--git-dir");
    let dossier_commun = lire_chemin_git(racine, "--git-common-dir");
    let mut chemins = Vec::new();
    if let Some(dossier) = &dossier_git {
        chemins.push(dossier.join("HEAD"));
        chemins.push(dossier.join("index"));
    }
    if let Some(dossier) = &dossier_commun {
        chemins.push(dossier.join("refs"));
        chemins.push(dossier.join("packed-refs"));
    }
    for chemin in chemins {
        if chemin.exists() {
            println!("cargo:rerun-if-changed={}", chemin.display());
        }
    }
}

fn lire_chemin_git(racine: &Path, option: &str) -> Option<PathBuf> {
    let sortie = std::process::Command::new("git")
        .arg("-C")
        .arg(racine)
        .args(["rev-parse", option])
        .output()
        .ok()?;
    if !sortie.status.success() {
        return None;
    }
    let texte = String::from_utf8_lossy(&sortie.stdout).trim().to_string();
    let chemin = PathBuf::from(texte);
    if chemin.is_absolute() {
        Some(chemin)
    } else {
        Some(racine.join(chemin))
    }
}
