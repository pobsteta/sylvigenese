//! Appel du validateur des contrats en sous-processus (spec §2, ADR 0002).
//!
//! Étape du BRIEF codée ici : aucune étape métier (squelette) ; BRIEF §4 (contrats validés en fin de module).
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
    lancer(arguments, false)
}

/// Comme [`appeler`], la mémoire du validateur bornée (niveau SER, mission 063) : Arrow y prend
/// le pool de mémoire du système et un seul fil de calcul (`ARROW_DEFAULT_MEMORY_POOL=system`,
/// `OMP_NUM_THREADS=1`, variables lues par pyarrow). Mesuré à N = 1 000 sur `sim/cohorts` et
/// `sim/cells` : environ 140 Mio au lieu de 240 à 270 Mio, pour une durée de 10 à 20 % plus longue.
/// Le validateur est un enfant de `simulate` : sa mémoire résidente compte dans celle de
/// l'exécution mesurée de l'extérieur (`/usr/bin/time -v`) ; bornée, elle reste sous celle du
/// moteur, que l'estimation de mémoire décrit. Les résultats de la validation n'en dépendent pas.
pub fn appeler_sobre(arguments: &[&str]) -> Result<i32, String> {
    lancer(arguments, true)
}

fn lancer(arguments: &[&str], sobre: bool) -> Result<i32, String> {
    let validateur = chemin_validateur();
    if !validateur.exists() {
        return Err(format!(
            "validateur introuvable : {} (mission 009)",
            validateur.display()
        ));
    }
    let mut commande = Command::new("python3");
    commande.arg(&validateur).args(arguments);
    if sobre {
        commande.env("ARROW_DEFAULT_MEMORY_POOL", "system").env("OMP_NUM_THREADS", "1");
    }
    let statut = commande
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
