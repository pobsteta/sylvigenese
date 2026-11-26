//! Contrôles des valeurs, comptes de `run.json` et signalements (plan M3a, « Sorties, contrôles,
//! codes » ; spec §6, « Contrôles »).
//!
//! Étape du BRIEF codée ici : BRIEF §6 et §13, « signaler plutôt que deviner » : une valeur
//! impossible arrête le moteur avec un message en français (code 3), et tout ce que le moteur a
//! dû borner, tenir ou tirer est compté (`run.json`) ou signalé (`sim/flags.parquet`).
//!
//! # Contrôles (code 3)
//!
//! Après chaque pas, pour chaque arbre écrit : x, y, d130, h, hcb et cw finis (ni NaN ni infini),
//! **d130 > 0** et **h > 0**, hcb ≥ 0 et cw ≥ 0 (contrat `sim.trees`). Le premier écart, dans
//! l'ordre des arbres, arrête le moteur : le message dit l'année, l'arbre, la grandeur et sa valeur.
//!
//! # Règle |Q| < 1e-9 × max(Q) (spec §6 ; T10)
//!
//! Une valeur dont la valeur absolue est sous 1e-9 fois le maximum des valeurs absolues du champ
//! est mise à zéro et comptée (`zeroed_values`), positives comprises ([`mettre_a_zero`]). En M5a
//! (mission 062), le champ calculé par FFT est celui des graines dispersées : le pas annuel en mode
//! `cohorts` applique la règle avec le seuil de `config.yml` (`simulate.regeneration.zero_threshold`),
//! par essence et par année, et arrête le moteur sur une valeur négative au-delà du seuil
//! ([`crate::dispersion::mettre_a_zero`]).
//!
//! # Sortes de signalement (colonne `kind` de `sim/flags.parquet`)
//!
//! | Sorte | Entité | Valeur |
//! |---|---|---|
//! | [`SORTE_HDOM_AU_DESSUS_DU_PLAFOND`] | cellule | H_dom de début d'année (m) |
//! | [`SORTE_HDOM_ASYMPTOTE_KORF`] | cellule | H_dom (m) |
//! | [`SORTE_CLASSE_KORF`] | cellule | classe retenue (1 à 5), à l'état initial |
//! | [`SORTE_DH_ARBRE_MIS_A_ZERO`] | arbre | part f(rel_d) (sans unité) |
//! | [`SORTE_TROUEE_SANS_RECRUE`] | cellule, chaque année | H_dom de fin d'année (0 m) |
//! | [`SORTE_TROUEE_HORS_DE_PORTEE`] | cellule, t0 puis chaque année | vide |
//!
//! Les autres faits (sorties de domaine, disques au bord, cellules mêlées, cellules sans arbre,
//! recrues en cellule vide) sont trop nombreux pour une ligne chacun : ils sont **comptés**
//! ([`Comptes`]) ; c'est à l'écriture de `run.json` (mission 038) d'en rendre les totaux.
//!
//! Règle de lisibilité (CLAUDE.md) : structures concrètes, fonctions libres, aucune macro maison
//! ni générique.

use crate::accroissement::SortiesParSens;
use crate::erreurs::Erreur;
use crate::etat::EtatArbres;

/// H_dom d'une cellule strictement au-dessus de son plafond (`site_potential`), non corrigée.
pub const SORTE_HDOM_AU_DESSUS_DU_PLAFOND: &str = "hdom_au_dessus_du_plafond";
/// H_dom d'une cellule de Korf à l'asymptote a ou au-delà : elle n'avance plus.
pub const SORTE_HDOM_ASYMPTOTE_KORF: &str = "hdom_asymptote_korf";
/// Classe de fertilité de Korf retenue pour une cellule (règle provisoire, décision sur 033).
pub const SORTE_CLASSE_KORF: &str = "classe_korf";
/// Hausse de hauteur d'un arbre négative (part f(rel_d) < 0), mise à 0.
pub const SORTE_DH_ARBRE_MIS_A_ZERO: &str = "dh_arbre_mis_a_zero";

/// Cellule simulée dont la hauteur dominante est nulle : aucune recrue n'y est ajoutée tant
/// qu'elle le reste (décision de Pascal du 25/11/2026 ; la recolonisation des trouées viendra en
/// M5 par les cohortes de semis).
pub const SORTE_TROUEE_SANS_RECRUE: &str = "trouee_sans_recrue";

/// Mode `cohorts` (M5a) : trouée (H_dom nulle) qu'aucun semencier ne peut atteindre dans le noyau
/// tronqué ; elle reste vide, et c'est dit (contrat `simulate.flags`), dès t0.
pub const SORTE_TROUEE_HORS_DE_PORTEE: &str = "trouee_hors_de_portee";

/// Seuil relatif de la règle |Q| < 1e-9 × max(Q) (spec §6).
pub const SEUIL_RELATIF_ZERO: f64 = 1e-9;

/// Une ligne de signalement (contrat `simulate.flags`).
#[derive(Debug, Clone, PartialEq)]
pub struct Signalement {
    pub annee: i32,
    /// `tree_id`, ou `cell_id` écrit en décimal.
    pub entite: String,
    pub sorte: String,
    /// Phrase en français.
    pub message: String,
    /// Valeur en cause, finie, ou `None`.
    pub valeur: Option<f64>,
}

/// Les comptes d'un pas (ou de toute la simulation, par [`Comptes::ajouter`]). Tous entiers.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct Comptes {
    /// Sorties de domaine par variable et par sens, et SER sans effet (`domain_outputs`).
    pub sorties_domaine: SortiesParSens,
    /// Couples (cellule, année) où H_dom est au plafond ou au-dessus (`cells_at_height_ceiling`).
    pub cellules_au_plafond: u64,
    /// Dont strictement au-dessus (signalées).
    pub cellules_au_dessus_du_plafond: u64,
    /// Couples (cellule, année) de Korf à l'asymptote (signalés).
    pub cellules_asymptote_korf: u64,
    /// Couples (arbre, année) dont le disque de 15 m sort de la grille (`edge_disks`).
    pub disques_au_bord: u64,
    /// Couples (cellule, année) à plusieurs essences (`mixed_cells`).
    pub cellules_melees: u64,
    /// Couples (cellule, année) simulés sans arbre vivant : H_dom tenue, faute de courbe (T5).
    pub cellules_sans_arbre: u64,
    /// Recrues ajoutées (`recruits`).
    pub recrues: u64,
    /// Recrues nées dans une cellule sans arbre : rel_d pris à 1 (elles sont leurs propres
    /// dominantes, par la définition de d_dom).
    pub recrues_cellule_vide: u64,
    /// Couples (cellule, année) simulés à H_dom nulle en fin d'année : recrutement suspendu
    /// (décision de Pascal du 25/11/2026), chacun signalé ([`SORTE_TROUEE_SANS_RECRUE`]).
    pub cellules_trouee_sans_recrue: u64,
    /// Arbres morts (`deaths`).
    pub morts: u64,
    /// Couples (arbre, année) dont la hausse de hauteur négative a été mise à 0 (signalés).
    pub dh_arbre_mis_a_zero: u64,
    /// Valeurs mises à zéro par la règle |Q| (`zeroed_values`) ; 0 en M3a.
    pub valeurs_mises_a_zero: u64,
    /// Mode `cohorts` : couples (cellule, essence, année) où le stock de semis à la hauteur de
    /// passage a borné le flux IFN (`seedling_stock_limited`, Q1).
    pub stock_de_semis_limitant: u64,
    /// Mode `cohorts` : cellules en trouée qui ont recruté (`gaps_recolonised`) ; une trouée qui
    /// recrute prend une H_dom non nulle, elle n'est comptée qu'une fois.
    pub trouees_recolonisees: u64,
}

impl Comptes {
    /// Ajoute les comptes d'un autre pas.
    pub fn ajouter(&mut self, autre: &Comptes) {
        self.sorties_domaine.ajouter(&autre.sorties_domaine);
        self.cellules_au_plafond += autre.cellules_au_plafond;
        self.cellules_au_dessus_du_plafond += autre.cellules_au_dessus_du_plafond;
        self.cellules_asymptote_korf += autre.cellules_asymptote_korf;
        self.disques_au_bord += autre.disques_au_bord;
        self.cellules_melees += autre.cellules_melees;
        self.cellules_sans_arbre += autre.cellules_sans_arbre;
        self.recrues += autre.recrues;
        self.recrues_cellule_vide += autre.recrues_cellule_vide;
        self.cellules_trouee_sans_recrue += autre.cellules_trouee_sans_recrue;
        self.morts += autre.morts;
        self.dh_arbre_mis_a_zero += autre.dh_arbre_mis_a_zero;
        self.valeurs_mises_a_zero += autre.valeurs_mises_a_zero;
        self.stock_de_semis_limitant += autre.stock_de_semis_limitant;
        self.trouees_recolonisees += autre.trouees_recolonisees;
    }
}

/// Contrôle une grandeur d'une entité : finie, et strictement positive (`strict`) ou positive.
/// Code 3 sinon, avec l'année, l'entité, la grandeur et la valeur.
pub fn controler_valeur(
    annee: i32,
    entite: &str,
    grandeur: &str,
    valeur: f64,
    positivite: Positivite,
) -> Result<(), Erreur> {
    if valeur.is_nan() {
        return Err(Erreur::controle_echoue(format!(
            "année {annee}, {entite} : {grandeur} vaut NaN"
        )));
    }
    if !valeur.is_finite() {
        return Err(Erreur::controle_echoue(format!(
            "année {annee}, {entite} : {grandeur} non fini ({valeur})"
        )));
    }
    match positivite {
        Positivite::Aucune => {}
        Positivite::Positive => {
            if valeur < 0.0 {
                return Err(Erreur::controle_echoue(format!(
                    "année {annee}, {entite} : {grandeur} négatif ({valeur})"
                )));
            }
        }
        Positivite::Stricte => {
            if valeur <= 0.0 {
                return Err(Erreur::controle_echoue(format!(
                    "année {annee}, {entite} : {grandeur} ≤ 0 ({valeur})"
                )));
            }
        }
    }
    Ok(())
}

/// Ce qu'une grandeur doit respecter en plus d'être finie.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Positivite {
    /// rien de plus (x, y)
    Aucune,
    /// ≥ 0 (hcb, cw)
    Positive,
    /// > 0 (d130, h)
    Stricte,
}

/// Contrôle les arbres écrits d'une année (état après le pas, avec `hcb` et `cw` de même
/// longueur). Code 3 au premier écart, dans l'ordre des arbres ; code 1 si les longueurs diffèrent.
pub fn controler_arbres(
    annee: i32,
    etat: &EtatArbres,
    hcb: &[f64],
    cw: &[f64],
) -> Result<(), Erreur> {
    if hcb.len() != etat.len() || cw.len() != etat.len() {
        return Err(Erreur::interne(format!(
            "hcb ({}) ou cw ({}) n'ont pas la longueur de l'état ({})",
            hcb.len(),
            cw.len(),
            etat.len()
        )));
    }
    for rang in 0..etat.len() {
        let entite = format!("arbre {}", etat.tree_id[rang]);
        controler_valeur(annee, &entite, "x", etat.x[rang], Positivite::Aucune)?;
        controler_valeur(annee, &entite, "y", etat.y[rang], Positivite::Aucune)?;
        controler_valeur(annee, &entite, "d130", etat.d130[rang], Positivite::Stricte)?;
        controler_valeur(annee, &entite, "h", etat.h[rang], Positivite::Stricte)?;
        controler_valeur(annee, &entite, "hcb", hcb[rang], Positivite::Positive)?;
        controler_valeur(annee, &entite, "cw", cw[rang], Positivite::Positive)?;
    }
    Ok(())
}

/// Règle |Q| < 1e-9 × max |Q| : met à zéro les valeurs sous le seuil (positives comprises, T10)
/// et rend leur nombre. Un champ vide, ou tout à zéro, ne change pas. Code 3 si une valeur n'est
/// pas finie (le seuil n'aurait pas de sens). Le maximum est cherché en ordre fixe.
pub fn mettre_a_zero(champ: &mut [f64]) -> Result<u64, Erreur> {
    let mut maximum: f64 = 0.0;
    for (rang, valeur) in champ.iter().enumerate() {
        if !valeur.is_finite() {
            return Err(Erreur::controle_echoue(format!(
                "règle |Q| < 1e-9 × max(Q) : valeur non finie ({valeur}) au rang {rang}"
            )));
        }
        if valeur.abs() > maximum {
            maximum = valeur.abs();
        }
    }
    let seuil = SEUIL_RELATIF_ZERO * maximum;
    let mut mises_a_zero = 0;
    for valeur in champ.iter_mut() {
        if *valeur != 0.0 && valeur.abs() < seuil {
            *valeur = 0.0;
            mises_a_zero += 1;
        }
    }
    Ok(mises_a_zero)
}
