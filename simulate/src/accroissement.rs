//! Accroissement en diamètre et relecture des prédicteurs avec le sens des sorties de domaine
//! (plan M3a, pas annuel, point 2 ; contrat `dynamics_params`, point 3).
//!
//! Étape du BRIEF codée ici : BRIEF §6, « Diamètre, mortalité, recrutement » : le diamètre de
//! chaque arbre avance d'un an selon le modèle `growth_gam` ajusté par `dynamics` sur l'IFN.
//!
//! - η = intercept + Σ_v f_v(x_v) + b_ser, relu aux nœuds par [`crate::parametres`] ;
//! - l'accroissement **radial** annuel vaut exp(η) cm/an (lien log du contrat) ; le diamètre
//!   gagne le double : **d130 += 2 × exp(η)** ;
//! - **en moyenne, sans bruit** (décision de Pascal, Q4 du 25/11/2026) : aucun tirage ici ;
//! - variables : d130 (cm), `ba_plot` et `bal` (m²/ha, module [`crate::concurrence`]),
//!   `trophic`, `coarse_hydric_700m` et `coarse_bioclim_700m` (bandes de
//!   `station_gradients.tif` en simulation, spec §6), et la SER (`ser.tif`).
//!
//! Une variable hors des nœuds extrêmes est bornée (le contrat le veut) **et comptée, avec son
//! sens** ([`SortiesParSens`]) : `run.json` distingue `below` et `above` (contrat `run`).
//! Ce compteur sert aussi à la mortalité, au recrutement et à la hauteur relative.
//!
//! Règle de lisibilité (CLAUDE.md) : fonctions libres, structures concrètes, aucune macro maison
//! ni générique.

use crate::erreurs::Erreur;
use crate::parametres::{Covariables, JeuDeParametres, SortiesDeDomaine, Variable};

/// Les sorties de domaine par variable et par sens, et les SER sans effet. Des entiers : la
/// somme de comptes faits sur plusieurs fils ne dépend pas de l'ordre (plan M3a, T1).
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct SortiesParSens {
    /// Valeurs sous le premier nœud x_1, rangées selon [`Variable::rang`].
    pub dessous: [u64; 8],
    /// Valeurs au-dessus du dernier nœud x_n, rangées selon [`Variable::rang`].
    pub dessus: [u64; 8],
    /// Prédicteurs calculés pour une SER absente des effets du jeu (effet pris à 0, contrat).
    pub ser_sans_effet: u64,
}

impl SortiesParSens {
    /// Ajoute les comptes d'un autre compteur.
    pub fn ajouter(&mut self, autre: &SortiesParSens) {
        for rang in 0..8 {
            self.dessous[rang] += autre.dessous[rang];
            self.dessus[rang] += autre.dessus[rang];
        }
        self.ser_sans_effet += autre.ser_sans_effet;
    }

    /// Le total des sorties de domaine, toutes variables et tous sens.
    pub fn total(&self) -> u64 {
        let mut total = 0;
        for rang in 0..8 {
            total += self.dessous[rang] + self.dessus[rang];
        }
        total
    }

    /// (sous, au-dessus) pour une variable.
    pub fn pour(&self, variable: Variable) -> (u64, u64) {
        (self.dessous[variable.rang()], self.dessus[variable.rang()])
    }
}

/// Le prédicteur η d'un jeu, avec le compte des sorties de domaine par sens.
///
/// Mêmes erreurs que [`JeuDeParametres::predicteur`] : code 2 si une covariable nécessaire
/// manque ou si le jeu n'a pas d'intercept, code 3 si une covariable n'est pas finie.
pub fn predicteur(
    jeu: &JeuDeParametres,
    covariables: &Covariables,
    ser_code: &str,
    sorties: &mut SortiesParSens,
) -> Result<f64, Erreur> {
    let mut brut = SortiesDeDomaine::default();
    let eta = jeu.predicteur(covariables, ser_code, &mut brut)?;
    // Le sens de chaque sortie : la valeur est finie ici (sinon predicteur a déjà refusé).
    for spline in &jeu.splines {
        if let Some(x) = covariables.valeur(spline.variable) {
            let premier = spline.x[0];
            let dernier = spline.x[spline.x.len() - 1];
            if x < premier {
                sorties.dessous[spline.variable.rang()] += 1;
            }
            if x > dernier {
                sorties.dessus[spline.variable.rang()] += 1;
            }
        }
    }
    sorties.ser_sans_effet += brut.ser_sans_effet;
    Ok(eta)
}

/// Les covariables d'un arbre pour la croissance et la mortalité.
pub fn covariables_arbre(
    d130: f64,
    ba_plot: f64,
    bal: f64,
    trophic: f64,
    hydric: f64,
    bioclim: f64,
) -> Covariables {
    Covariables {
        d130: Some(d130),
        ba_plot: Some(ba_plot),
        bal: Some(bal),
        ba_species: None,
        trophic: Some(trophic),
        coarse_hydric_700m: Some(hydric),
        coarse_bioclim_700m: Some(bioclim),
        rel_d: None,
    }
}

/// L'accroissement annuel du diamètre, en cm : 2 × exp(η) (`growth_gam`, lien log, rayon doublé).
pub fn accroissement_diametre(
    croissance: &JeuDeParametres,
    covariables: &Covariables,
    ser_code: &str,
    sorties: &mut SortiesParSens,
) -> Result<f64, Erreur> {
    let eta = predicteur(croissance, covariables, ser_code, sorties)?;
    Ok(2.0 * eta.exp())
}
