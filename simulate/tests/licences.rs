//! Licences du graphe de dépendances de `simulate` (mission 035 ; CLAUDE.md, « formats
//! ouverts, logiciels libres », licence GPL-3).
//!
//! `cargo metadata --locked` liste toutes les crates du Cargo.lock (y compris celles d'autres
//! plateformes). Chaque expression de licence doit être satisfaite par la liste admise : pour
//! chaque partie reliée par AND, au moins une alternative reliée par OR doit être admise.
//! Une expression absente ou d'une forme non prévue fait échouer le test : on ne devine pas.

use std::process::Command;

/// Licences admises : compatibles avec une distribution de l'ensemble sous GPL-3.0
/// (liste de compatibilité de la FSF, gnu.org/licenses/license-list).
const ADMISES: [&str; 13] = [
    "GPL-3.0-only",
    "GPL-3.0-or-later",
    "LGPL-2.1-or-later",
    "Apache-2.0",
    "MIT",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "0BSD",
    "ISC",
    "Zlib",
    "Unlicense",
    "CC0-1.0",
    "Unicode-3.0",
];

/// Vrai si l'expression SPDX est satisfaite par la liste admise.
fn admise(expression: &str) -> bool {
    // Ancienne notation « MIT/Apache-2.0 » = « MIT OR Apache-2.0 ».
    let normalisee = expression.replace('/', " OR ");
    for partie in normalisee.split(" AND ") {
        let partie = partie.trim().trim_start_matches('(').trim_end_matches(')');
        if partie.contains('(') || partie.contains(')') {
            return false;
        }
        let une_admise = partie
            .split(" OR ")
            .any(|alternative| ADMISES.contains(&alternative.trim()));
        if !une_admise {
            return false;
        }
    }
    true
}

#[test]
fn l_evaluation_des_expressions_est_juste() {
    assert!(admise("MIT OR Apache-2.0"));
    assert!(admise("MIT/Apache-2.0"));
    assert!(admise("Apache-2.0 AND MIT"));
    assert!(admise("(MIT OR Apache-2.0) AND Unicode-3.0"));
    assert!(admise("Apache-2.0 OR BSL-1.0"));
    assert!(!admise("BSL-1.0"));
    assert!(!admise("MIT AND SSPL-1.0"));
    assert!(!admise("GPL-2.0-only"));
    assert!(!admise("(MIT OR (Apache-2.0 AND X))"));
}

#[test]
fn toutes_les_crates_du_cargo_lock_ont_une_licence_admise() {
    let cargo = std::env::var("CARGO").unwrap_or_else(|_| "cargo".to_string());
    let sortie = Command::new(cargo)
        .args([
            "metadata",
            "--format-version",
            "1",
            "--locked",
            "--manifest-path",
        ])
        .arg(concat!(env!("CARGO_MANIFEST_DIR"), "/Cargo.toml"))
        .output()
        .expect("cargo metadata n'a pas pu être lancé");
    assert!(
        sortie.status.success(),
        "cargo metadata a échoué : {}",
        String::from_utf8_lossy(&sortie.stderr)
    );
    let metadonnees: serde_json::Value = serde_json::from_slice(&sortie.stdout).unwrap();
    let paquets = metadonnees["packages"].as_array().unwrap();
    assert!(
        paquets.len() > 50,
        "graphe inattendu : {} paquets",
        paquets.len()
    );
    let mut refusees = Vec::new();
    for paquet in paquets {
        let nom = paquet["name"].as_str().unwrap();
        let version = paquet["version"].as_str().unwrap();
        match paquet["license"].as_str() {
            Some(licence) if admise(licence) => {}
            Some(licence) => refusees.push(format!("{nom} {version} : {licence}")),
            None => refusees.push(format!("{nom} {version} : pas d'expression de licence")),
        }
    }
    assert!(
        refusees.is_empty(),
        "licences hors de la liste admise :\n{}",
        refusees.join("\n")
    );
}

#[test]
fn les_crates_directes_sont_figees_par_egal() {
    let manifeste =
        std::fs::read_to_string(concat!(env!("CARGO_MANIFEST_DIR"), "/Cargo.toml")).unwrap();
    let mut dans_dependances = false;
    let mut nombre = 0;
    for ligne in manifeste.lines() {
        let ligne = ligne.trim();
        if ligne.starts_with('[') {
            dans_dependances = ligne == "[dependencies]";
            continue;
        }
        if !dans_dependances || ligne.is_empty() || ligne.starts_with('#') {
            continue;
        }
        nombre += 1;
        assert!(
            ligne.contains("\"="),
            "dépendance non figée par « = » : {ligne}"
        );
    }
    assert_eq!(nombre, 10, "nombre de crates directes inattendu");
}
