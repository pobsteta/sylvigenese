//! Recrutement IFN direct : nombre, position et identifiant des recrues (plan M3a, pas annuel,
//! point 5).
//!
//! Étape du BRIEF codée ici : BRIEF §6, « Diamètre, mortalité, recrutement » : de nouveaux arbres
//! franchissent chaque année le seuil de recensement de l'IFN, selon le modèle `recruitment_gam`.
//!
//! - **espérance** par cellule et essence candidate : λ = exp(η) × aire de la cellule (en ha ;
//!   0,0625 ha pour 25 m) ; exp(η) est en tiges/ha/an (contrat `dynamics_params`, point 3) ;
//!   `ba_plot` est la surface terrière de la cellule et `ba_species` celle de l'essence dans la
//!   cellule (T7) ; essences candidates : celles qui ont les quatre jeux de paramètres (T6) ;
//! - **arrondi aléatoire** (décision de Pascal, Q4 du 25/11/2026) : n = ⌊λ⌋, plus 1 si
//!   u(graine, année, cell_id, essence, NB_RECRUES) < λ − ⌊λ⌋ ; l'espérance de n est λ ;
//! - **diamètre** : celui du seuil, C13 = 0,235 m (contrat), soit d130 = 23,5 / π ≈ 7,48 cm ;
//! - **position** tirée dans la cellule : x = x ouest + u(…, RECRUE_X) × côté, y = y nord −
//!   u(…, RECRUE_Y) × côté, l'entité étant le numéro stable de la recrue ;
//! - **identifiant** : `r<cell_id>_<année>_<rang>`, le rang comptant à partir de 0 les recrues de
//!   la cellule dans l'année, essences dans l'ordre des codes (spec §6 : cellule, année, rang) ;
//! - **numéros** : somme de préfixes séquentielle sur les comptes des cellules, dans l'ordre des
//!   `cell_id` ([`crate::etat::premiers_numeros`]) ; les recrues s'ajoutent en fin d'année.
//!
//! Règle de lisibilité (CLAUDE.md) : fonctions libres, aucune macro maison ni générique.

use std::f64::consts::PI;

use crate::alea::{u, Sorte};
use crate::erreurs::Erreur;

/// Le diamètre d'une recrue, en cm : seuil de recensement C13 = 0,235 m (contrat
/// `dynamics_params`, `recruitment_gam`), d130 = 23,5 cm / π.
pub fn d130_recrue_cm() -> f64 {
    23.5 / PI
}

/// Plus grande espérance admise par cellule et par an : au-delà, l'arrondi en entier ne serait
/// plus exact en f64 (2^53) ; une telle valeur est un contrôle échoué, pas un nombre de recrues.
pub const ESPERANCE_MAX: f64 = 9_007_199_254_740_992.0;

/// L'espérance du nombre de recrues d'une cellule : exp(η) × aire (ha).
pub fn esperance(eta: f64, aire_cellule_ha: f64) -> f64 {
    eta.exp() * aire_cellule_ha
}

/// L'arrondi aléatoire de λ avec le nombre u ∈ [0, 1) : ⌊λ⌋, plus 1 si u < λ − ⌊λ⌋.
///
/// Code 3 si λ n'est pas fini, est négatif ou dépasse [`ESPERANCE_MAX`] ; le message dit la
/// cellule, l'essence et l'année.
pub fn arrondi_aleatoire(
    lambda: f64,
    u_tire: f64,
    annee: i32,
    cell_id: u64,
    espece: &str,
) -> Result<u64, Erreur> {
    if !lambda.is_finite() || lambda < 0.0 || lambda > ESPERANCE_MAX {
        return Err(Erreur::controle_echoue(format!(
            "année {annee}, cellule {cell_id}, essence {espece} : espérance de recrues {lambda} \
             non finie, négative ou démesurée"
        )));
    }
    let entier = lambda.floor();
    let reste = lambda - entier;
    let mut n = entier as u64;
    if u_tire < reste {
        n += 1;
    }
    Ok(n)
}

/// Le nombre de recrues d'une cellule et d'une essence : arrondi aléatoire de λ, tirage
/// u(graine, année, cell_id, essence, NB_RECRUES).
pub fn nombre_de_recrues(
    graine: u64,
    annee: i32,
    cell_id: u64,
    espece: &str,
    espece_packee: u64,
    lambda: f64,
) -> Result<u64, Erreur> {
    let tire = u(graine, annee, cell_id, espece_packee, Sorte::NbRecrues);
    arrondi_aleatoire(lambda, tire, annee, cell_id, espece)
}

/// La position d'une recrue dans sa cellule (x ouest, y nord, côté en m) : (x est, y nord),
/// EPSG:2154. L'entité des tirages est le numéro stable de la recrue.
pub fn position(
    graine: u64,
    annee: i32,
    numero: u64,
    espece_packee: u64,
    x_ouest: f64,
    y_nord: f64,
    cote: f64,
) -> (f64, f64) {
    let ux = u(graine, annee, numero, espece_packee, Sorte::RecrueX);
    let uy = u(graine, annee, numero, espece_packee, Sorte::RecrueY);
    (x_ouest + ux * cote, y_nord - uy * cote)
}

/// L'identifiant d'une recrue : `r<cell_id>_<année>_<rang>`.
pub fn tree_id_recrue(cell_id: u64, annee: i32, rang: u64) -> String {
    format!("r{cell_id}_{annee}_{rang}")
}
