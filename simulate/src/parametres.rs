//! Paramètres de la dynamique relus aux nœuds (ADR 0004 ; contrat
//! `contracts/tables/params/dynamics_params.schema.json` ; plan M3a, pas annuel points 2 à 5).
//!
//! Étape du BRIEF codée ici : BRIEF §6, « Diamètre, mortalité, recrutement » et « Hauteur » :
//! `simulate` relit, sans R, les modèles ajustés par `dynamics` sur l'IFN.
//!
//! Ce que fait ce module :
//!
//! 1. **Lecture** d'un fichier `params/*.parquet` au format long (une ligne par nombre) :
//!    [`lire_parquet`] rend des [`LigneParametre`] ; toute ligne hors contrat est refusée
//!    (code 2), jamais corrigée.
//! 2. **Assemblage** en structures concrètes ([`Parametres::depuis_lignes`]) : un
//!    [`JeuDeParametres`] par porteur (essence ou groupe) et par modèle, avec son intercept, ses
//!    effets de SER, ses termes lisses ([`SplineNaturelle`]) et ses nombres nommés (`scale`,
//!    `tweedie_p`, `A_class1` … `A_class5`, `k`, `p`, ou tout autre terme sans variable).
//! 3. **Spline cubique naturelle** passant par les nœuds, dérivées secondes par l'algorithme de
//!    Thomas, évaluation après bornage aux nœuds extrêmes, exactement selon la description du
//!    contrat (point 2) ; c'est la fonction `dyn_ncs` de `R/dynamics.R`, et `tests/parametres.rs`
//!    vérifie l'accord à 1e-10 sur des valeurs produites par R.
//! 4. **Prédicteur** η = intercept + Σ_v f_v(x_v) + b_ser ([`JeuDeParametres::predicteur`]),
//!    sommé dans un ordre fixe (intercept, puis les variables dans l'ordre de [`Variable`], puis
//!    la SER) pour que le résultat ne dépende pas de l'ordre des lignes du fichier. Une variable
//!    hors des nœuds extrêmes est bornée **et comptée** ([`SortiesDeDomaine`]) ; une SER sans
//!    effet compte pour 0 (contrat) **et est comptée**.
//! 5. **Recherche** d'un jeu pour une essence ([`Parametres::chercher`]) : ses lignes propres,
//!    sinon celles de son groupe (`groupe` de `contracts/species.csv` : feuillu, resineux),
//!    sinon `toutes_essences`, sinon **erreur code 2**. Une essence absente du référentiel est
//!    refusée (code 2) : on ne devine pas son groupe.
//!
//! Le lien et le décalage de chaque modèle (exp, cloglog…) ne sont pas appliqués ici : c'est
//! l'affaire du pas annuel (mission 037), selon le point 3 de la description du contrat.
//!
//! Règle de lisibilité (CLAUDE.md) : structures et énumérations concrètes, aucune macro maison,
//! aucun générique ni trait maison.

use std::collections::{HashMap, HashSet};
use std::fs::File;
use std::path::Path;

use arrow_array::{Array, BooleanArray, Float64Array, LargeStringArray, RecordBatch, StringArray};
use arrow_schema::DataType;
use parquet::arrow::arrow_reader::ParquetRecordBatchReaderBuilder;

use crate::alea::packer_essence;
use crate::erreurs::Erreur;

/// Nom du groupe qui porte les paramètres de toutes les essences (contrat, `species_group`).
pub const TOUTES_ESSENCES: &str = "toutes_essences";

/// Les colonnes du contrat, dans son ordre.
pub const COLONNES: [&str; 9] = [
    "species",
    "species_group",
    "model",
    "term",
    "variable",
    "x",
    "value",
    "provisoire",
    "source",
];

// ------------------------------------------------------------------------------------------
// Lignes du fichier

/// Une ligne du format long, telle que lue (contrat `dynamics_params`).
#[derive(Debug, Clone, PartialEq)]
pub struct LigneParametre {
    pub species: Option<String>,
    pub species_group: Option<String>,
    pub model: String,
    pub term: String,
    pub variable: Option<String>,
    pub x: Option<f64>,
    pub value: f64,
    pub provisoire: bool,
    pub source: String,
}

/// Lit un fichier `params/*.parquet` au contrat `dynamics_params`.
///
/// Code 2 si le fichier est illisible, s'il lui manque une colonne ou en a une de trop
/// (`fieldsMatch: equal`), si un type ne convient pas, ou si une valeur obligatoire est vide.
pub fn lire_parquet(chemin: &Path) -> Result<Vec<LigneParametre>, Erreur> {
    let nom = chemin.display().to_string();
    let fichier = File::open(chemin)
        .map_err(|e| Erreur::entree_refusee(format!("{nom} : lecture impossible ({e})")))?;
    let constructeur = ParquetRecordBatchReaderBuilder::try_new(fichier)
        .map_err(|e| Erreur::entree_refusee(format!("{nom} : Parquet illisible ({e})")))?;
    let lecteur = constructeur
        .build()
        .map_err(|e| Erreur::entree_refusee(format!("{nom} : Parquet illisible ({e})")))?;
    let mut lignes: Vec<LigneParametre> = Vec::new();
    for lot in lecteur {
        let lot =
            lot.map_err(|e| Erreur::entree_refusee(format!("{nom} : Parquet illisible ({e})")))?;
        lire_lot(&lot, &nom, &mut lignes)?;
    }
    Ok(lignes)
}

fn lire_lot(lot: &RecordBatch, nom: &str, lignes: &mut Vec<LigneParametre>) -> Result<(), Erreur> {
    let schema = lot.schema();
    for champ in schema.fields() {
        if !COLONNES.contains(&champ.name().as_str()) {
            return Err(Erreur::entree_refusee(format!(
                "{nom} : colonne « {} » hors du contrat dynamics_params",
                champ.name()
            )));
        }
    }
    let species = colonne_texte(lot, "species", nom)?;
    let species_group = colonne_texte(lot, "species_group", nom)?;
    let model = colonne_texte(lot, "model", nom)?;
    let term = colonne_texte(lot, "term", nom)?;
    let variable = colonne_texte(lot, "variable", nom)?;
    let x = colonne_reel(lot, "x", nom)?;
    let value = colonne_reel(lot, "value", nom)?;
    let provisoire = colonne_booleen(lot, "provisoire", nom)?;
    let source = colonne_texte(lot, "source", nom)?;
    for rang in 0..lot.num_rows() {
        let ligne = LigneParametre {
            species: species[rang].clone(),
            species_group: species_group[rang].clone(),
            model: obligatoire_texte(&model[rang], "model", nom, rang)?,
            term: obligatoire_texte(&term[rang], "term", nom, rang)?,
            variable: variable[rang].clone(),
            x: x[rang],
            value: match value[rang] {
                Some(v) => v,
                None => return Err(valeur_vide("value", nom, rang)),
            },
            provisoire: match provisoire[rang] {
                Some(v) => v,
                None => return Err(valeur_vide("provisoire", nom, rang)),
            },
            source: obligatoire_texte(&source[rang], "source", nom, rang)?,
        };
        lignes.push(ligne);
    }
    Ok(())
}

fn valeur_vide(colonne: &str, nom: &str, rang: usize) -> Erreur {
    Erreur::entree_refusee(format!(
        "{nom} : valeur obligatoire vide dans la colonne « {colonne} » (ligne {} du lot)",
        rang + 1
    ))
}

fn obligatoire_texte(
    valeur: &Option<String>,
    colonne: &str,
    nom: &str,
    rang: usize,
) -> Result<String, Erreur> {
    match valeur {
        Some(texte) if !texte.is_empty() => Ok(texte.clone()),
        _ => Err(valeur_vide(colonne, nom, rang)),
    }
}

fn index_colonne(lot: &RecordBatch, colonne: &str, nom: &str) -> Result<usize, Erreur> {
    lot.schema().index_of(colonne).map_err(|_| {
        Erreur::entree_refusee(format!(
            "{nom} : colonne « {colonne} » absente (contrat dynamics_params)"
        ))
    })
}

fn type_refuse(colonne: &str, nom: &str, attendu: &str, lu: &DataType) -> Erreur {
    Erreur::entree_refusee(format!(
        "{nom} : la colonne « {colonne} » devrait être de type {attendu}, elle est {lu}"
    ))
}

fn colonne_texte(
    lot: &RecordBatch,
    colonne: &str,
    nom: &str,
) -> Result<Vec<Option<String>>, Erreur> {
    let tableau = lot.column(index_colonne(lot, colonne, nom)?);
    let mut valeurs: Vec<Option<String>> = Vec::with_capacity(tableau.len());
    match tableau.data_type() {
        DataType::Utf8 => {
            let textes = tableau
                .as_any()
                .downcast_ref::<StringArray>()
                .ok_or_else(|| {
                    Erreur::interne(format!(
                        "{nom} : colonne « {colonne} » Utf8 non convertible"
                    ))
                })?;
            for rang in 0..textes.len() {
                if textes.is_null(rang) {
                    valeurs.push(None);
                } else {
                    valeurs.push(Some(textes.value(rang).to_string()));
                }
            }
        }
        DataType::LargeUtf8 => {
            let textes = tableau
                .as_any()
                .downcast_ref::<LargeStringArray>()
                .ok_or_else(|| {
                    Erreur::interne(format!(
                        "{nom} : colonne « {colonne} » LargeUtf8 non convertible"
                    ))
                })?;
            for rang in 0..textes.len() {
                if textes.is_null(rang) {
                    valeurs.push(None);
                } else {
                    valeurs.push(Some(textes.value(rang).to_string()));
                }
            }
        }
        autre => return Err(type_refuse(colonne, nom, "texte (Utf8)", autre)),
    }
    Ok(valeurs)
}

fn colonne_reel(lot: &RecordBatch, colonne: &str, nom: &str) -> Result<Vec<Option<f64>>, Erreur> {
    let tableau = lot.column(index_colonne(lot, colonne, nom)?);
    let reels = match tableau.data_type() {
        DataType::Float64 => tableau
            .as_any()
            .downcast_ref::<Float64Array>()
            .ok_or_else(|| {
                Erreur::interne(format!(
                    "{nom} : colonne « {colonne} » Float64 non convertible"
                ))
            })?,
        autre => return Err(type_refuse(colonne, nom, "réel (Float64)", autre)),
    };
    let mut valeurs: Vec<Option<f64>> = Vec::with_capacity(reels.len());
    for rang in 0..reels.len() {
        if reels.is_null(rang) {
            valeurs.push(None);
        } else {
            valeurs.push(Some(reels.value(rang)));
        }
    }
    Ok(valeurs)
}

fn colonne_booleen(
    lot: &RecordBatch,
    colonne: &str,
    nom: &str,
) -> Result<Vec<Option<bool>>, Erreur> {
    let tableau = lot.column(index_colonne(lot, colonne, nom)?);
    let booleens = match tableau.data_type() {
        DataType::Boolean => tableau
            .as_any()
            .downcast_ref::<BooleanArray>()
            .ok_or_else(|| {
                Erreur::interne(format!(
                    "{nom} : colonne « {colonne} » Boolean non convertible"
                ))
            })?,
        autre => return Err(type_refuse(colonne, nom, "booléen", autre)),
    };
    let mut valeurs: Vec<Option<bool>> = Vec::with_capacity(booleens.len());
    for rang in 0..booleens.len() {
        if booleens.is_null(rang) {
            valeurs.push(None);
        } else {
            valeurs.push(Some(booleens.value(rang)));
        }
    }
    Ok(valeurs)
}

// ------------------------------------------------------------------------------------------
// Variables et covariables

/// Les covariables d'un terme lisse (colonne `variable` du contrat, hors `ser_code`).
/// L'ordre de cette énumération est l'ordre fixe de la somme du prédicteur.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Variable {
    /// diamètre à 1,30 m (cm)
    D130,
    /// surface terrière de la placette ou du disque de 15 m (m²/ha)
    BaPlot,
    /// surface terrière des arbres plus gros (m²/ha)
    Bal,
    /// surface terrière de l'essence (m²/ha), recrutement
    BaSpecies,
    /// niveau trophique
    Trophic,
    /// gradient hydrique (disque de 700 m à l'ajustement, raster en simulation)
    CoarseHydric700m,
    /// gradient bioclimatique (disque de 700 m à l'ajustement, raster en simulation)
    CoarseBioclim700m,
    /// d130 / d_dom, hauteur relative
    RelD,
}

impl Variable {
    /// Toutes les variables, dans l'ordre fixe de la somme.
    pub const TOUTES: [Variable; 8] = [
        Variable::D130,
        Variable::BaPlot,
        Variable::Bal,
        Variable::BaSpecies,
        Variable::Trophic,
        Variable::CoarseHydric700m,
        Variable::CoarseBioclim700m,
        Variable::RelD,
    ];

    /// Le nom de la variable dans le contrat.
    pub fn nom(self) -> &'static str {
        match self {
            Variable::D130 => "d130",
            Variable::BaPlot => "ba_plot",
            Variable::Bal => "bal",
            Variable::BaSpecies => "ba_species",
            Variable::Trophic => "trophic",
            Variable::CoarseHydric700m => "coarse_hydric_700m",
            Variable::CoarseBioclim700m => "coarse_bioclim_700m",
            Variable::RelD => "rel_d",
        }
    }

    /// Le rang de la variable (0 à 7) dans [`Variable::TOUTES`].
    pub fn rang(self) -> usize {
        match self {
            Variable::D130 => 0,
            Variable::BaPlot => 1,
            Variable::Bal => 2,
            Variable::BaSpecies => 3,
            Variable::Trophic => 4,
            Variable::CoarseHydric700m => 5,
            Variable::CoarseBioclim700m => 6,
            Variable::RelD => 7,
        }
    }

    /// La variable d'après son nom dans le contrat (`None` si inconnue ; `ser_code` n'en est pas une).
    pub fn depuis_nom(nom: &str) -> Option<Variable> {
        Variable::TOUTES
            .into_iter()
            .find(|variable| variable.nom() == nom)
    }
}

/// Les valeurs des covariables pour un arbre ou une cellule. `None` : non fournie ; un terme
/// qui en a besoin rend alors une erreur (code 2), jamais une valeur devinée.
#[derive(Debug, Clone, Copy, Default, PartialEq)]
pub struct Covariables {
    pub d130: Option<f64>,
    pub ba_plot: Option<f64>,
    pub bal: Option<f64>,
    pub ba_species: Option<f64>,
    pub trophic: Option<f64>,
    pub coarse_hydric_700m: Option<f64>,
    pub coarse_bioclim_700m: Option<f64>,
    pub rel_d: Option<f64>,
}

impl Covariables {
    /// La valeur d'une variable.
    pub fn valeur(&self, variable: Variable) -> Option<f64> {
        match variable {
            Variable::D130 => self.d130,
            Variable::BaPlot => self.ba_plot,
            Variable::Bal => self.bal,
            Variable::BaSpecies => self.ba_species,
            Variable::Trophic => self.trophic,
            Variable::CoarseHydric700m => self.coarse_hydric_700m,
            Variable::CoarseBioclim700m => self.coarse_bioclim_700m,
            Variable::RelD => self.rel_d,
        }
    }
}

/// Le compte des signalements de la relecture : valeurs bornées aux nœuds extrêmes, par
/// variable, et SER sans effet dans les paramètres. Ce sont des entiers : la somme de comptes
/// faits sur plusieurs fils ne dépend pas de l'ordre (plan M3a, T1).
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct SortiesDeDomaine {
    /// Évaluations bornées, rangées selon [`Variable::rang`].
    pub par_variable: [u64; 8],
    /// Prédicteurs calculés pour une SER absente des effets du jeu (effet pris à 0, contrat).
    pub ser_sans_effet: u64,
}

impl SortiesDeDomaine {
    /// Ajoute les comptes d'un autre compteur (par exemple celui d'un autre fil).
    pub fn ajouter(&mut self, autre: &SortiesDeDomaine) {
        for rang in 0..self.par_variable.len() {
            self.par_variable[rang] += autre.par_variable[rang];
        }
        self.ser_sans_effet += autre.ser_sans_effet;
    }

    /// Le nombre d'évaluations bornées d'une variable.
    pub fn pour(&self, variable: Variable) -> u64 {
        self.par_variable[variable.rang()]
    }

    /// Le total des évaluations bornées, toutes variables.
    pub fn total_borne(&self) -> u64 {
        let mut total = 0;
        for compte in self.par_variable {
            total += compte;
        }
        total
    }
}

// ------------------------------------------------------------------------------------------
// Spline cubique naturelle

/// Un terme lisse : la spline cubique naturelle passant par ses nœuds (contrat, point 2).
#[derive(Debug, Clone, PartialEq)]
pub struct SplineNaturelle {
    pub variable: Variable,
    /// Abscisses des nœuds, strictement croissantes (n ≥ 2).
    pub x: Vec<f64>,
    /// Valeurs du terme aux nœuds.
    pub y: Vec<f64>,
    /// Dérivées secondes aux nœuds (M_1 = M_n = 0), par l'algorithme de Thomas.
    pub m: Vec<f64>,
}

impl SplineNaturelle {
    /// Construit la spline à partir de couples (x, valeur) dans un ordre quelconque.
    ///
    /// Code 2 si moins de deux nœuds, si une abscisse ou une valeur n'est pas finie, ou si deux
    /// nœuds ont la même abscisse.
    pub fn construire(
        variable: Variable,
        noeuds: &[(f64, f64)],
    ) -> Result<SplineNaturelle, Erreur> {
        if noeuds.len() < 2 {
            return Err(Erreur::entree_refusee(format!(
                "terme lisse s({}) : {} nœud(s), il en faut au moins deux",
                variable.nom(),
                noeuds.len()
            )));
        }
        for (x, y) in noeuds {
            if !x.is_finite() || !y.is_finite() {
                return Err(Erreur::entree_refusee(format!(
                    "terme lisse s({}) : nœud non fini (x = {x}, valeur = {y})",
                    variable.nom()
                )));
            }
        }
        let mut tries: Vec<(f64, f64)> = noeuds.to_vec();
        tries.sort_by(|a, b| a.0.total_cmp(&b.0));
        let mut x: Vec<f64> = Vec::with_capacity(tries.len());
        let mut y: Vec<f64> = Vec::with_capacity(tries.len());
        for (xi, yi) in &tries {
            if let Some(precedent) = x.last() {
                if *xi <= *precedent {
                    return Err(Erreur::entree_refusee(format!(
                        "terme lisse s({}) : deux nœuds à la même abscisse {xi}",
                        variable.nom()
                    )));
                }
            }
            x.push(*xi);
            y.push(*yi);
        }
        let m = derivees_secondes(&x, &y);
        Ok(SplineNaturelle { variable, x, y, m })
    }

    /// Évalue la spline en `x` : rend la valeur et vrai si `x` a été borné (hors de [x_1, x_n]).
    ///
    /// Code 3 si `x` n'est pas fini : borner un NaN serait deviner.
    pub fn evaluer(&self, x: f64) -> Result<(f64, bool), Erreur> {
        if !x.is_finite() {
            return Err(Erreur::controle_echoue(format!(
                "terme lisse s({}) : valeur non finie ({x})",
                self.variable.nom()
            )));
        }
        let n = self.x.len();
        let premier = self.x[0];
        let dernier = self.x[n - 1];
        let mut borne = false;
        let mut xc = x;
        if xc < premier {
            xc = premier;
            borne = true;
        }
        if xc > dernier {
            xc = dernier;
            borne = true;
        }
        // i tel que x_i ≤ xc ≤ x_{i+1}, et i = n − 2 (indices à partir de 0) si xc = x_n.
        let nombre_inferieurs = self.x.partition_point(|noeud| *noeud <= xc);
        let mut i = nombre_inferieurs.saturating_sub(1);
        if i > n - 2 {
            i = n - 2;
        }
        let h = self.x[i + 1] - self.x[i];
        let a = self.x[i + 1] - xc;
        let b = xc - self.x[i];
        let mi = self.m[i];
        let mj = self.m[i + 1];
        let valeur = (mi * a * a * a + mj * b * b * b) / (6.0 * h)
            + (self.y[i] / h - mi * h / 6.0) * a
            + (self.y[i + 1] / h - mj * h / 6.0) * b;
        Ok((valeur, borne))
    }
}

/// Dérivées secondes M_1 … M_n de la spline cubique naturelle (M_1 = M_n = 0) : système
/// tridiagonal du contrat résolu par l'algorithme de Thomas (élimination puis remontée).
/// `x` strictement croissant, `x.len() == y.len() >= 2`.
pub fn derivees_secondes(x: &[f64], y: &[f64]) -> Vec<f64> {
    let n = x.len();
    let mut m = vec![0.0; n];
    if n <= 2 {
        return m;
    }
    let inconnues = n - 2;
    let mut h: Vec<f64> = Vec::with_capacity(n - 1);
    for i in 0..n - 1 {
        h.push(x[i + 1] - x[i]);
    }
    // Ligne j (j = 0 … inconnues − 1) pour le nœud i = j + 1 :
    // h_{i−1} M_{i−1} + 2 (h_{i−1} + h_i) M_i + h_i M_{i+1} = 6 [pente_i − pente_{i−1}].
    let mut sous: Vec<f64> = Vec::with_capacity(inconnues);
    let mut diagonale: Vec<f64> = Vec::with_capacity(inconnues);
    let mut sur: Vec<f64> = Vec::with_capacity(inconnues);
    let mut droite: Vec<f64> = Vec::with_capacity(inconnues);
    for j in 0..inconnues {
        let i = j + 1;
        sous.push(h[i - 1]);
        diagonale.push(2.0 * (h[i - 1] + h[i]));
        sur.push(h[i]);
        droite.push(6.0 * ((y[i + 1] - y[i]) / h[i] - (y[i] - y[i - 1]) / h[i - 1]));
    }
    // Élimination (la matrice est à diagonale strictement dominante : pas de pivot nul).
    for j in 1..inconnues {
        let facteur = sous[j] / diagonale[j - 1];
        diagonale[j] -= facteur * sur[j - 1];
        droite[j] -= facteur * droite[j - 1];
    }
    // Remontée.
    let mut solution = vec![0.0; inconnues];
    solution[inconnues - 1] = droite[inconnues - 1] / diagonale[inconnues - 1];
    for j in (0..inconnues - 1).rev() {
        solution[j] = (droite[j] - sur[j] * solution[j + 1]) / diagonale[j];
    }
    m[1..(inconnues + 1)].copy_from_slice(&solution);
    m
}

// ------------------------------------------------------------------------------------------
// Jeux de paramètres

/// Qui porte un jeu de paramètres : une essence (code espar) ou un groupe
/// (`feuillu`, `resineux`, `toutes_essences`).
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub enum Porteur {
    Essence(String),
    Groupe(String),
}

/// D'où vient le jeu rendu par la recherche.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Niveau {
    /// les lignes propres de l'essence
    Essence,
    /// les lignes de son groupe (feuillu, resineux)
    Groupe,
    /// les lignes de `toutes_essences`
    ToutesEssences,
}

/// Les nombres d'un modèle pour un porteur.
#[derive(Debug, Clone, PartialEq)]
pub struct JeuDeParametres {
    pub porteur: Porteur,
    pub modele: String,
    /// La ligne `intercept`, si le modèle en a une (pas Chapman-Richards).
    pub intercept: Option<f64>,
    /// Les effets `ser_code=<code>`, triés par code.
    pub effets_ser: Vec<(String, f64)>,
    /// Les termes lisses, triés selon l'ordre de [`Variable`].
    pub splines: Vec<SplineNaturelle>,
    /// Les autres nombres nommés (`scale`, `tweedie_p`, `A_class1`, `k`, `p`…), triés par nom.
    pub scalaires: Vec<(String, f64)>,
    /// Vrai si au moins une ligne du jeu est provisoire.
    pub provisoire: bool,
    /// Les sources citées, sans doublon, dans l'ordre de première apparition.
    pub sources: Vec<String>,
}

impl JeuDeParametres {
    /// Un nombre nommé du jeu (`scale`, `k`…). Code 2 s'il manque.
    pub fn scalaire(&self, terme: &str) -> Result<f64, Erreur> {
        for (nom, valeur) in &self.scalaires {
            if nom == terme {
                return Ok(*valeur);
            }
        }
        Err(Erreur::entree_refusee(format!(
            "paramètre « {terme} » absent du modèle {} ({})",
            self.modele,
            decrire_porteur(&self.porteur)
        )))
    }

    /// Le prédicteur linéaire η = intercept + Σ_v f_v(x_v) + b_ser, sans lien ni décalage.
    ///
    /// Les valeurs hors nœuds sont bornées et comptées dans `sorties` ; une SER absente des
    /// effets du jeu compte pour 0 et est comptée (si le jeu a des effets de SER).
    /// Code 2 si le jeu n'a pas d'intercept ou si une covariable nécessaire n'est pas fournie ;
    /// code 3 si une covariable n'est pas finie.
    pub fn predicteur(
        &self,
        covariables: &Covariables,
        ser_code: &str,
        sorties: &mut SortiesDeDomaine,
    ) -> Result<f64, Erreur> {
        let intercept = match self.intercept {
            Some(valeur) => valeur,
            None => {
                return Err(Erreur::entree_refusee(format!(
                    "le modèle {} ({}) n'a pas de ligne intercept",
                    self.modele,
                    decrire_porteur(&self.porteur)
                )))
            }
        };
        let mut eta = intercept;
        for spline in &self.splines {
            let x = match covariables.valeur(spline.variable) {
                Some(valeur) => valeur,
                None => {
                    return Err(Erreur::entree_refusee(format!(
                        "le modèle {} ({}) a besoin de la variable {}, non fournie",
                        self.modele,
                        decrire_porteur(&self.porteur),
                        spline.variable.nom()
                    )))
                }
            };
            let (valeur, borne) = spline.evaluer(x)?;
            if borne {
                sorties.par_variable[spline.variable.rang()] += 1;
            }
            eta += valeur;
        }
        if !self.effets_ser.is_empty() {
            let mut trouve = false;
            for (code, valeur) in &self.effets_ser {
                if code == ser_code {
                    eta += *valeur;
                    trouve = true;
                    break;
                }
            }
            if !trouve {
                sorties.ser_sans_effet += 1;
            }
        }
        Ok(eta)
    }
}

/// « essence 09 », « groupe feuillu ».
pub fn decrire_porteur(porteur: &Porteur) -> String {
    match porteur {
        Porteur::Essence(code) => format!("essence {code}"),
        Porteur::Groupe(groupe) => format!("groupe {groupe}"),
    }
}

/// Le référentiel des essences : code espar → groupe (`contracts/species.csv`, colonne `groupe`).
#[derive(Debug, Clone, PartialEq)]
pub struct Referentiel {
    groupes: HashMap<String, String>,
}

impl Referentiel {
    /// Lit `contracts/species.csv` (colonnes `espar` et `groupe`). Code 2 si le fichier est
    /// illisible, si une colonne manque, si une ligne n'a pas le nombre de champs de l'en-tête,
    /// si un groupe n'est ni feuillu ni resineux, ou si un code est en double.
    pub fn lire(chemin: &Path) -> Result<Referentiel, Erreur> {
        let nom = chemin.display().to_string();
        let texte = std::fs::read_to_string(chemin)
            .map_err(|e| Erreur::entree_refusee(format!("{nom} : lecture impossible ({e})")))?;
        let mut lignes = texte.lines();
        let entete: Vec<&str> = match lignes.next() {
            Some(ligne) => ligne.split(',').collect(),
            None => return Err(Erreur::entree_refusee(format!("{nom} : fichier vide"))),
        };
        let rang_espar = rang_de(&entete, "espar", &nom)?;
        let rang_groupe = rang_de(&entete, "groupe", &nom)?;
        let mut groupes: HashMap<String, String> = HashMap::new();
        for (numero, ligne) in lignes.enumerate() {
            if ligne.is_empty() {
                continue;
            }
            let champs: Vec<&str> = ligne.split(',').collect();
            if champs.len() != entete.len() {
                return Err(Erreur::entree_refusee(format!(
                    "{nom}, ligne {} : {} champs au lieu de {} (virgule dans une valeur ?)",
                    numero + 2,
                    champs.len(),
                    entete.len()
                )));
            }
            let espar = champs[rang_espar].to_string();
            let groupe = champs[rang_groupe].to_string();
            if groupe != "feuillu" && groupe != "resineux" {
                return Err(Erreur::entree_refusee(format!(
                    "{nom}, ligne {} : groupe « {groupe} » ni feuillu ni resineux",
                    numero + 2
                )));
            }
            if groupes.insert(espar.clone(), groupe).is_some() {
                return Err(Erreur::entree_refusee(format!(
                    "{nom} : code espar {espar} en double"
                )));
            }
        }
        Ok(Referentiel { groupes })
    }

    /// Le groupe d'une essence, ou `None` si le code est absent du référentiel.
    pub fn groupe(&self, espar: &str) -> Option<&str> {
        self.groupes.get(espar).map(|groupe| groupe.as_str())
    }

    /// Le nombre d'essences du référentiel.
    pub fn nombre(&self) -> usize {
        self.groupes.len()
    }
}

fn rang_de(entete: &[&str], colonne: &str, nom: &str) -> Result<usize, Erreur> {
    for (rang, champ) in entete.iter().enumerate() {
        if *champ == colonne {
            return Ok(rang);
        }
    }
    Err(Erreur::entree_refusee(format!(
        "{nom} : colonne « {colonne} » absente"
    )))
}

/// Clé d'un jeu : son porteur et son modèle.
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
struct Cle {
    porteur: Porteur,
    modele: String,
}

/// Tous les jeux de paramètres lus, avec leur index de recherche.
#[derive(Debug, Clone, PartialEq)]
pub struct Parametres {
    /// Les jeux, dans l'ordre de première apparition de leur porteur et modèle.
    pub jeux: Vec<JeuDeParametres>,
    index: HashMap<Cle, usize>,
}

/// Ce que l'on accumule pour un jeu pendant l'assemblage.
struct JeuEnCours {
    porteur: Porteur,
    modele: String,
    intercept: Option<f64>,
    effets_ser: Vec<(String, f64)>,
    noeuds: Vec<(Variable, f64, f64)>,
    scalaires: Vec<(String, f64)>,
    provisoire: bool,
    sources: Vec<String>,
}

impl Parametres {
    /// Assemble les lignes (de un ou plusieurs fichiers) en jeux de paramètres.
    ///
    /// Code 2 pour toute ligne hors contrat : ni essence ni groupe, groupe inconnu, code espar
    /// hors motif, valeur non finie, terme mal formé, variable qui ne correspond pas au terme,
    /// abscisse manquante ou en trop, terme en double (clé primaire), terme lisse à moins de
    /// deux nœuds ou à deux nœuds de même abscisse.
    pub fn depuis_lignes(lignes: &[LigneParametre]) -> Result<Parametres, Erreur> {
        let mut en_cours: Vec<JeuEnCours> = Vec::new();
        let mut index: HashMap<Cle, usize> = HashMap::new();
        let mut termes_vus: HashSet<(Cle, String)> = HashSet::new();
        for ligne in lignes {
            let porteur = porteur_de(ligne)?;
            let cle = Cle {
                porteur: porteur.clone(),
                modele: ligne.model.clone(),
            };
            let contexte = format!(
                "{} ({}), terme {}",
                ligne.model,
                decrire_porteur(&porteur),
                ligne.term
            );
            if !ligne.value.is_finite() {
                return Err(Erreur::entree_refusee(format!(
                    "paramètres {contexte} : valeur non finie ({})",
                    ligne.value
                )));
            }
            if !termes_vus.insert((cle.clone(), ligne.term.clone())) {
                return Err(Erreur::entree_refusee(format!(
                    "paramètres {contexte} : terme en double"
                )));
            }
            let rang = match index.get(&cle) {
                Some(rang) => *rang,
                None => {
                    en_cours.push(JeuEnCours {
                        porteur: porteur.clone(),
                        modele: ligne.model.clone(),
                        intercept: None,
                        effets_ser: Vec::new(),
                        noeuds: Vec::new(),
                        scalaires: Vec::new(),
                        provisoire: false,
                        sources: Vec::new(),
                    });
                    index.insert(cle, en_cours.len() - 1);
                    en_cours.len() - 1
                }
            };
            let jeu = &mut en_cours[rang];
            ranger_ligne(jeu, ligne, &contexte)?;
            if ligne.provisoire {
                jeu.provisoire = true;
            }
            if !jeu.sources.contains(&ligne.source) {
                jeu.sources.push(ligne.source.clone());
            }
        }
        let mut jeux: Vec<JeuDeParametres> = Vec::with_capacity(en_cours.len());
        for jeu in en_cours {
            jeux.push(terminer(jeu)?);
        }
        Ok(Parametres { jeux, index })
    }

    /// Le jeu d'un porteur et d'un modèle, s'il existe.
    pub fn jeu(&self, porteur: &Porteur, modele: &str) -> Option<&JeuDeParametres> {
        let cle = Cle {
            porteur: porteur.clone(),
            modele: modele.to_string(),
        };
        self.index.get(&cle).map(|rang| &self.jeux[*rang])
    }

    /// Le jeu d'un modèle pour une essence : ses lignes propres, sinon son groupe, sinon
    /// `toutes_essences` ; rend aussi le niveau trouvé.
    ///
    /// Code 2 si l'essence est absente du référentiel, ou si aucun des trois niveaux n'a le modèle.
    pub fn chercher(
        &self,
        modele: &str,
        espar: &str,
        referentiel: &Referentiel,
    ) -> Result<(&JeuDeParametres, Niveau), Erreur> {
        let groupe = match referentiel.groupe(espar) {
            Some(groupe) => groupe,
            None => {
                return Err(Erreur::entree_refusee(format!(
                    "essence {espar} absente de contracts/species.csv : pas de groupe, pas de paramètres"
                )))
            }
        };
        if let Some(jeu) = self.jeu(&Porteur::Essence(espar.to_string()), modele) {
            return Ok((jeu, Niveau::Essence));
        }
        if let Some(jeu) = self.jeu(&Porteur::Groupe(groupe.to_string()), modele) {
            return Ok((jeu, Niveau::Groupe));
        }
        if let Some(jeu) = self.jeu(&Porteur::Groupe(TOUTES_ESSENCES.to_string()), modele) {
            return Ok((jeu, Niveau::ToutesEssences));
        }
        Err(Erreur::entree_refusee(format!(
            "aucun paramètre {modele} pour l'essence {espar} : ni ses lignes propres, ni le groupe {groupe}, ni {TOUTES_ESSENCES}"
        )))
    }
}

fn porteur_de(ligne: &LigneParametre) -> Result<Porteur, Erreur> {
    if let Some(espar) = &ligne.species {
        packer_essence(espar)?;
        return Ok(Porteur::Essence(espar.clone()));
    }
    match &ligne.species_group {
        Some(groupe) if groupe == "feuillu" || groupe == "resineux" || groupe == TOUTES_ESSENCES => {
            Ok(Porteur::Groupe(groupe.clone()))
        }
        Some(groupe) => Err(Erreur::entree_refusee(format!(
            "paramètres {}, terme {} : groupe « {groupe} » ni feuillu, ni resineux, ni {TOUTES_ESSENCES}",
            ligne.model, ligne.term
        ))),
        None => Err(Erreur::entree_refusee(format!(
            "paramètres {}, terme {} : ni essence (species) ni groupe (species_group)",
            ligne.model, ligne.term
        ))),
    }
}

/// Range une ligne dans le jeu en cours selon la forme de son terme.
fn ranger_ligne(
    jeu: &mut JeuEnCours,
    ligne: &LigneParametre,
    contexte: &str,
) -> Result<(), Erreur> {
    let terme = ligne.term.as_str();
    if terme == "intercept" {
        sans_variable_ni_x(ligne, contexte)?;
        jeu.intercept = Some(ligne.value);
        return Ok(());
    }
    if let Some(code) = terme.strip_prefix("ser_code=") {
        if code.is_empty() {
            return Err(Erreur::entree_refusee(format!(
                "paramètres {contexte} : code de SER vide"
            )));
        }
        if ligne.variable.as_deref() != Some("ser_code") {
            return Err(Erreur::entree_refusee(format!(
                "paramètres {contexte} : la variable devrait être ser_code"
            )));
        }
        if ligne.x.is_some() {
            return Err(Erreur::entree_refusee(format!(
                "paramètres {contexte} : un effet de SER n'a pas d'abscisse x"
            )));
        }
        jeu.effets_ser.push((code.to_string(), ligne.value));
        return Ok(());
    }
    if let Some(reste) = terme.strip_prefix("s(") {
        let nom_variable = match reste.split_once(")[") {
            Some((nom, suite)) if suite.ends_with(']') && suite.len() > 1 => nom,
            _ => {
                return Err(Erreur::entree_refusee(format!(
                    "paramètres {contexte} : terme lisse mal formé (attendu s(<variable>)[NN])"
                )))
            }
        };
        let variable = match Variable::depuis_nom(nom_variable) {
            Some(variable) => variable,
            None => {
                return Err(Erreur::entree_refusee(format!(
                    "paramètres {contexte} : variable « {nom_variable} » inconnue du contrat"
                )))
            }
        };
        if ligne.variable.as_deref() != Some(nom_variable) {
            return Err(Erreur::entree_refusee(format!(
                "paramètres {contexte} : la colonne variable ({}) ne correspond pas au terme",
                ligne.variable.as_deref().unwrap_or("vide")
            )));
        }
        let x = match ligne.x {
            Some(x) if x.is_finite() => x,
            _ => {
                return Err(Erreur::entree_refusee(format!(
                    "paramètres {contexte} : abscisse x absente ou non finie"
                )))
            }
        };
        jeu.noeuds.push((variable, x, ligne.value));
        return Ok(());
    }
    sans_variable_ni_x(ligne, contexte)?;
    jeu.scalaires.push((terme.to_string(), ligne.value));
    Ok(())
}

fn sans_variable_ni_x(ligne: &LigneParametre, contexte: &str) -> Result<(), Erreur> {
    if ligne.variable.is_some() || ligne.x.is_some() {
        return Err(Erreur::entree_refusee(format!(
            "paramètres {contexte} : ce terme n'a ni variable ni abscisse x (contrat)"
        )));
    }
    Ok(())
}

/// Construit les splines et trie tout dans un ordre fixe.
fn terminer(jeu: JeuEnCours) -> Result<JeuDeParametres, Erreur> {
    let mut splines: Vec<SplineNaturelle> = Vec::new();
    for variable in Variable::TOUTES {
        let mut noeuds: Vec<(f64, f64)> = Vec::new();
        for (v, x, y) in &jeu.noeuds {
            if *v == variable {
                noeuds.push((*x, *y));
            }
        }
        if noeuds.is_empty() {
            continue;
        }
        let spline = SplineNaturelle::construire(variable, &noeuds).map_err(|e| {
            Erreur::entree_refusee(format!(
                "paramètres {} ({}) : {}",
                jeu.modele,
                decrire_porteur(&jeu.porteur),
                e.message
            ))
        })?;
        splines.push(spline);
    }
    let mut effets_ser = jeu.effets_ser;
    effets_ser.sort_by(|a, b| a.0.cmp(&b.0));
    let mut scalaires = jeu.scalaires;
    scalaires.sort_by(|a, b| a.0.cmp(&b.0));
    Ok(JeuDeParametres {
        porteur: jeu.porteur,
        modele: jeu.modele,
        intercept: jeu.intercept,
        effets_ser,
        splines,
        scalaires,
        provisoire: jeu.provisoire,
        sources: jeu.sources,
    })
}
