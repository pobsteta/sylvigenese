//! La release dont vient `simulate` (mission 087) : `simulate --version`, et la lecture par git
//! de `build.rs` (module `simulate::release`) sur des dépôts temporaires à étiquettes
//! synthétiques. Le choix entre git, `SYLVIGENESE_RELEASE` et `inconnue` est testé dans le
//! module lui-même (`src/release.rs`) ; `run.json` porte la même valeur
//! (`tests/non_regression.rs`, `run_json_porte_tous_les_comptes_...`).

use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

use simulate::release;

fn dossier_temporaire(nom: &str) -> PathBuf {
    let dossier =
        std::env::temp_dir().join(format!("simulate-release-{}-{nom}", std::process::id()));
    let _ = fs::remove_dir_all(&dossier);
    fs::create_dir_all(&dossier).unwrap();
    dossier
}

/// Lance git dans `dossier`, sans dépendre de la configuration de la machine.
fn git(dossier: &Path, arguments: &[&str]) -> String {
    let sortie = Command::new("git")
        .arg("-C")
        .arg(dossier)
        .args([
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@t",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "tag.gpgsign=false",
        ])
        .args(arguments)
        .env("GIT_CONFIG_NOSYSTEM", "1")
        .output()
        .unwrap();
    assert!(sortie.status.success(), "git {arguments:?} : {}", String::from_utf8_lossy(&sortie.stderr));
    String::from_utf8_lossy(&sortie.stdout).trim().to_string()
}

fn depot_neuf(nom: &str) -> PathBuf {
    let dossier = dossier_temporaire(nom);
    git(&dossier, &["init", "-q", "."]);
    fs::write(dossier.join("a.txt"), "1\n").unwrap();
    git(&dossier, &["add", "-A"]);
    git(&dossier, &["commit", "-q", "-m", "init"]);
    dossier
}

#[test]
fn version_affiche_la_release_compilee() {
    let sortie = Command::new(env!("CARGO_BIN_EXE_simulate"))
        .arg("--version")
        .output()
        .unwrap();
    assert_eq!(sortie.status.code(), Some(0));
    assert_eq!(
        String::from_utf8_lossy(&sortie.stdout),
        format!("simulate {}\n", simulate::RELEASE)
    );
    let stderr = String::from_utf8_lossy(&sortie.stderr);
    if simulate::RELEASE == release::INCONNUE {
        assert!(stderr.contains("release inconnue"), "{stderr}");
    } else {
        assert!(stderr.is_empty(), "{stderr}");
    }
}

#[test]
fn la_release_compilee_a_la_forme_d_une_release_ou_est_inconnue() {
    assert!(
        simulate::RELEASE == release::INCONNUE || release::est_une_release(simulate::RELEASE),
        "{}",
        simulate::RELEASE
    );
    // Dépôt du projet avec ses étiquettes, sans variable posée : git a parlé, pas « inconnue ».
    let depot = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("..");
    if release::decrire_par_git(&depot).is_ok() && std::env::var(release::VARIABLE).is_err() {
        assert_ne!(simulate::RELEASE, release::INCONNUE);
    }
}

#[test]
fn git_dit_l_etiquette_les_commits_suivants_et_la_modification() {
    let depot = depot_neuf("describe");
    let erreur = release::decrire_par_git(&depot).unwrap_err();
    assert!(erreur.contains("describe"), "sans étiquette : {erreur}");

    git(&depot, &["tag", "v0.1"]);
    git(&depot, &["tag", "v2026.11.5-rc1"]);
    assert!(release::decrire_par_git(&depot).is_err(), "étiquettes non calendaires");

    git(&depot, &["tag", "v2026.11.1"]);
    assert_eq!(release::decrire_par_git(&depot).unwrap(), "v2026.11.1");

    fs::write(depot.join("a.txt"), "2\n").unwrap();
    assert_eq!(release::decrire_par_git(&depot).unwrap(), "v2026.11.1-dirty");

    git(&depot, &["commit", "-q", "-am", "deux"]);
    let empreinte = git(&depot, &["rev-parse", "--short", "HEAD"]);
    assert_eq!(
        release::decrire_par_git(&depot).unwrap(),
        format!("v2026.11.1-1-g{empreinte}")
    );

    git(&depot, &["tag", "v2026.11.2"]);
    assert_eq!(release::decrire_par_git(&depot).unwrap(), "v2026.11.2");
    let _ = fs::remove_dir_all(&depot);
}

#[test]
fn hors_de_git_la_release_n_est_pas_lue() {
    // Copie sans .git (comme `git archive`).
    let copie = dossier_temporaire("copie");
    fs::write(copie.join("a.txt"), "1\n").unwrap();
    assert!(release::decrire_par_git(&copie).is_err());
    let _ = fs::remove_dir_all(&copie);

    // Copie posée dans un autre dépôt étiqueté : git ne doit pas dire la release de celui-ci.
    let autre = depot_neuf("autre");
    git(&autre, &["tag", "v2026.11.9"]);
    let dedans = autre.join("copie");
    fs::create_dir_all(&dedans).unwrap();
    let erreur = release::decrire_par_git(&dedans).unwrap_err();
    assert!(erreur.contains("n'est pas la racine"), "{erreur}");
    let _ = fs::remove_dir_all(&autre);
}

/// Mission 092 : le vrai `build.rs` (et le vrai `src/release.rs`) relancent la compilation quand
/// une étiquette ou la tête de git change. Banc : une crate minuscule, sans dépendance, dans un
/// dépôt git temporaire hors de l'arbre (rien n'est écrit dans le dépôt du projet) ; sa racine
/// de dépôt est le parent de la crate, comme pour `simulate/`.
#[test]
fn le_build_rs_recompile_quand_une_etiquette_ou_la_tete_change() {
    let racine = depot_neuf("recompilation");
    let crate_ = racine.join("mini");
    fs::create_dir_all(crate_.join("src")).unwrap();
    let manifeste = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    fs::copy(manifeste.join("build.rs"), crate_.join("build.rs")).unwrap();
    fs::copy(manifeste.join("src/release.rs"), crate_.join("src/release.rs")).unwrap();
    fs::write(
        crate_.join("Cargo.toml"),
        "[package]\nname = \"mini\"\nversion = \"0.0.0\"\nedition = \"2021\"\n\n[workspace]\n",
    )
    .unwrap();
    fs::write(
        crate_.join("src/main.rs"),
        "fn main() { println!(\"{}\", env!(\"SYLVIGENESE_RELEASE_COMPILEE\")); }\n",
    )
    .unwrap();
    git(&racine, &["add", "-A"]);
    git(&racine, &["commit", "-q", "-m", "mini"]);
    git(&racine, &["tag", "v2026.11.1"]);

    let cible = racine.join("cible");
    let compiler_et_lire = || -> String {
        let cargo = std::env::var("CARGO").unwrap_or_else(|_| "cargo".to_string());
        let sortie = Command::new(&cargo)
            .current_dir(&crate_)
            .args(["run", "-q", "--offline"])
            .env("CARGO_TARGET_DIR", &cible)
            .env_remove(release::VARIABLE)
            .output()
            .unwrap();
        assert!(sortie.status.success(), "{}", String::from_utf8_lossy(&sortie.stderr));
        String::from_utf8_lossy(&sortie.stdout).trim().to_string()
    };

    assert_eq!(compiler_et_lire(), "v2026.11.1");
    // Nouveau commit : tête déplacée, commits depuis l'étiquette.
    fs::write(racine.join("a.txt"), "2\n").unwrap();
    git(&racine, &["commit", "-q", "-am", "deux"]);
    let empreinte = git(&racine, &["rev-parse", "--short", "HEAD"]);
    assert_eq!(compiler_et_lire(), format!("v2026.11.1-1-g{empreinte}"));
    // Étiquette posée sur ce même commit (la tête ne bouge pas) : la release compilée change.
    git(&racine, &["tag", "v2026.11.2"]);
    assert_eq!(compiler_et_lire(), "v2026.11.2");
    // Modification indexée : la marque -dirty apparaît (l'index est surveillé).
    fs::write(racine.join("a.txt"), "3\n").unwrap();
    git(&racine, &["add", "a.txt"]);
    assert_eq!(compiler_et_lire(), "v2026.11.2-dirty");
    let _ = fs::remove_dir_all(&racine);
}
