//! Lecture de `config.yml` (spec §1, §2, §6 ; ADR 0001).
//!
//! Étape du BRIEF codée ici : aucune étape métier (squelette) ; BRIEF §13 (config.yml rejouable).
//!
//! Ne contrôle pas les clés : c'est le rôle du validateur
//! (`contracts/json/config.schema.json`). Seules les clés lues par `simulate` sont déclarées.

use serde::Deserialize;
use std::path::Path;

use crate::erreurs::Erreur;

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

/// Comme [`lire`], depuis le texte du fichier (utile aux tests, sans fichier).
pub fn depuis_texte(texte: &str) -> Result<Config, String> {
    serde_norway::from_str(texte).map_err(|e| format!("config.yml mal formé : {e}"))
}

/// Le niveau de simulation (spec §1).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum NiveauSimulation {
    Massif,
    Ser,
}

/// Les réglages de `simulate`, tous présents : `level`, `seed`, `t0` et `years` sont exigés.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ReglagesSimulate {
    pub niveau: NiveauSimulation,
    /// Graine du générateur à compteur (module `alea`).
    pub seed: u64,
    /// Année de départ : l'état initial est celui de l'année `t0`.
    pub t0: i32,
    /// Horizon, en années (au moins 1).
    pub years: u32,
    /// Nombre de fils demandé ; `None` : un fil.
    pub threads: Option<u32>,
}

impl Config {
    /// Les réglages de `simulate`, sans aucune valeur par défaut.
    ///
    /// Code 2 si le bloc `simulate` est absent ou incomplet (le message nomme les clés qui
    /// manquent), si `level` n'est ni `massif` ni `ser`, si `years` ou `threads` vaut 0.
    pub fn reglages_simulate(&self) -> Result<ReglagesSimulate, Erreur> {
        let bloc = match &self.simulate {
            Some(bloc) => bloc,
            None => {
                return Err(Erreur::entree_refusee(
                    "config.yml : le bloc « simulate » est absent ; il doit donner level, seed, t0 et years (aucune valeur par défaut)"
                        .to_string(),
                ))
            }
        };
        let mut absentes: Vec<&str> = Vec::new();
        if bloc.level.is_none() {
            absentes.push("level");
        }
        if bloc.seed.is_none() {
            absentes.push("seed");
        }
        if bloc.t0.is_none() {
            absentes.push("t0");
        }
        if bloc.years.is_none() {
            absentes.push("years");
        }
        if !absentes.is_empty() {
            return Err(Erreur::entree_refusee(format!(
                "config.yml : le bloc « simulate » est incomplet ; clés absentes : {} (aucune valeur par défaut)",
                absentes.join(", ")
            )));
        }
        let niveau = match bloc.level.as_deref() {
            Some("massif") => NiveauSimulation::Massif,
            Some("ser") => NiveauSimulation::Ser,
            autre => {
                return Err(Erreur::entree_refusee(format!(
                    "config.yml : simulate.level vaut « {} » ; attendu « massif » ou « ser »",
                    autre.unwrap_or("")
                )))
            }
        };
        let years = bloc.years.unwrap_or(0);
        if years == 0 {
            return Err(Erreur::entree_refusee(
                "config.yml : simulate.years doit valoir au moins 1".to_string(),
            ));
        }
        if bloc.threads == Some(0) {
            return Err(Erreur::entree_refusee(
                "config.yml : simulate.threads doit valoir au moins 1 (ou être absent)".to_string(),
            ));
        }
        Ok(ReglagesSimulate {
            niveau,
            seed: bloc.seed.unwrap_or(0),
            t0: bloc.t0.unwrap_or(0),
            years,
            threads: bloc.threads,
        })
    }

    /// Code 2 si le CRS n'est pas EPSG:2154 (ADR 0001).
    pub fn verifier_crs(&self) -> Result<(), Erreur> {
        if self.crs != "EPSG:2154" {
            return Err(Erreur::entree_refusee(format!(
                "config.yml : crs vaut « {} » ; seul EPSG:2154 est accepté",
                self.crs
            )));
        }
        Ok(())
    }
}
