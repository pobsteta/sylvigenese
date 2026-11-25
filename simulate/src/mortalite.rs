//! Mortalité annuelle tirée selon le risque (plan M3a, pas annuel, point 4).
//!
//! Étape du BRIEF codée ici : BRIEF §6, « Diamètre, mortalité, recrutement » : chaque année,
//! chaque arbre vivant meurt ou non selon le modèle `mortality_gam` ajusté par `dynamics`.
//!
//! - lien cloglog avec décalage log(Δt) (contrat `dynamics_params`, point 3) : exp(η) est le
//!   risque annuel, et la probabilité de mourir dans l'année vaut **p = 1 − exp(−exp(η))** ;
//! - **tirage** : l'arbre meurt si u(graine, année, numéro de l'arbre, essence, MORT) < p
//!   (module [`crate::alea`]) ; la mort est tirée selon le risque annuel (décision de Pascal,
//!   Q4 du 25/11/2026), et le tirage ne dépend ni de l'ordre des calculs ni du nombre de fils ;
//! - l'arbre mort est écrit une fois, l'année de sa mort, avec le statut `dead` (contrat
//!   `sim.trees`), puis retiré de l'état.
//!
//! Règle de lisibilité (CLAUDE.md) : fonctions libres, aucune macro maison ni générique.

use crate::alea::{u, Sorte};

/// La probabilité de mourir dans l'année : 1 − exp(−exp(η)), calculée par −expm1(−exp(η)) pour
/// garder la précision quand le risque est petit.
pub fn probabilite_annuelle(eta: f64) -> f64 {
    -(-eta.exp()).exp_m1()
}

/// Le tirage de mort d'un arbre : vrai si u(graine, année, numéro, essence, MORT) < p.
pub fn meurt(graine: u64, annee: i32, numero: u64, essence_packee: u64, probabilite: f64) -> bool {
    u(graine, annee, numero, essence_packee, Sorte::Mort) < probabilite
}
