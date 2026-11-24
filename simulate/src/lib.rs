//! Moteur `simulate` (ADR 0001) : squelette de la mission 012.
//!
//! Étape du BRIEF codée ici : aucune encore. Le moteur (BRIEF §6 et §8) viendra plus tard ;
//! pour l'instant `simulate` ne fait que lire `config.yml` et faire valider ce fichier.
//!
//! Règle de lisibilité (CLAUDE.md) : pas de macros maison ni de génériques avancés.

pub mod config;
pub mod geotiff;
pub mod validateur;

use std::path::Path;

/// Code de sortie : tout va bien.
pub const SORTIE_OK: i32 = 0;
/// Code de sortie : l'exécution est impossible (message sur stderr).
pub const SORTIE_IMPOSSIBLE: i32 = 2;

/// Exécute le squelette : lit la config, la fait valider, rend le code de sortie (0 ou 2).
pub fn executer(chemin_config: &Path) -> i32 {
    match preparer(chemin_config) {
        Ok(()) => {
            eprintln!("[simulate] config.yml lu et conforme ; rien d'autre à faire (squelette).");
            SORTIE_OK
        }
        Err(message) => {
            eprintln!("[simulate] erreur : {message}");
            SORTIE_IMPOSSIBLE
        }
    }
}

fn preparer(chemin_config: &Path) -> Result<(), String> {
    config::lire(chemin_config)?;
    validateur::valider_config(chemin_config)
}
