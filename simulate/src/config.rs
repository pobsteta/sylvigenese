//! Lecture de `config.yml` (spec §1, §2, §6 ; ADR 0001).
//!
//! Ne contrôle pas les clés : c'est le rôle du validateur
//! (`contracts/json/config.schema.json`). Seules les clés lues par `simulate` sont déclarées.

use serde::Deserialize;
use std::path::Path;

#[derive(Debug, Deserialize)]
pub struct Config {
    pub schema_version: u32,
    pub zone: String,
    pub crs: String,
    pub grid: Grille,
    pub management: String,
    pub simulate: Option<Reglages>,
}

#[derive(Debug, Deserialize)]
pub struct Grille {
    pub resolution_m: u32,
}

/// Réglages facultatifs de `simulate`. Absents : aucune valeur par défaut n'est devinée ici.
#[derive(Debug, Deserialize)]
pub struct Reglages {
    pub level: Option<String>,
    pub seed: Option<u64>,
    pub t0: Option<i32>,
    pub years: Option<u32>,
    pub threads: Option<u32>,
}

/// Lit et décode `config.yml`. Message d'erreur en français.
pub fn lire(chemin: &Path) -> Result<Config, String> {
    let texte = std::fs::read_to_string(chemin)
        .map_err(|e| format!("config.yml illisible ({}) : {e}", chemin.display()))?;
    serde_norway::from_str(&texte)
        .map_err(|e| format!("config.yml mal formé ({}) : {e}", chemin.display()))
}
