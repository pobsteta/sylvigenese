//! Appel du validateur des contrats en sous-processus (spec §2, ADR 0002).
//!
//! Aucun import du code du validateur : c'est un passage par fichiers.

use std::path::{Path, PathBuf};
use std::process::Command;

/// Chemin du validateur : variable `SYLVIGENESE_VALIDATE` si elle existe,
/// sinon `contracts/validate` depuis le dossier courant (la racine du dépôt).
pub fn chemin_validateur() -> PathBuf {
    match std::env::var("SYLVIGENESE_VALIDATE") {
        Ok(chemin) if !chemin.is_empty() => PathBuf::from(chemin),
        _ => PathBuf::from("contracts").join("validate"),
    }
}

/// Lance `python3 <validateur> <arguments>` et rend son code de sortie
/// (0 conforme, 2 contrôle impossible, 3 non conforme).
pub fn appeler(arguments: &[&str]) -> Result<i32, String> {
    let validateur = chemin_validateur();
    if !validateur.exists() {
        return Err(format!(
            "validateur introuvable : {} (mission 009)",
            validateur.display()
        ));
    }
    let statut = Command::new("python3")
        .arg(&validateur)
        .args(arguments)
        .status()
        .map_err(|e| format!("python3 n'a pas pu être lancé : {e}"))?;
    statut
        .code()
        .ok_or_else(|| "le validateur a été interrompu par un signal".to_string())
}

/// Fait valider `config.yml`. Erreur si le validateur ne rend pas 0.
pub fn valider_config(chemin: &Path) -> Result<(), String> {
    let chemin_texte = chemin.to_string_lossy();
    let code = appeler(&["config", chemin_texte.as_ref()])?;
    if code == 0 {
        Ok(())
    } else {
        Err(format!("config.yml non conforme (validateur, code {code})"))
    }
}
