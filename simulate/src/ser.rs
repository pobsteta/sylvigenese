//! Le niveau SER : des cohortes d'adultes en classes de diamètre fixes, en f32, sur les seules
//! cellules forestières (mission 063 ; plan m5a, mission E, choix T1, T4, T7 et T8 ; ADR 0006 ;
//! décisions de Pascal Q1 à Q5 du 26/11/2026).
//!
//! Étape du BRIEF codée ici : BRIEF §3 (au niveau SER, des cohortes et non des arbres) et §6
//! (diamètre, mortalité, recrutement, hauteur), appliqués par classe de diamètre ; BRIEF §7 (la
//! régénération) par le **même module de semis** que le niveau massif ([`crate::semis`],
//! [`crate::dispersion`], décision Q4) ; BRIEF §11 (une SER simulée, recrutement calé sur l'IFN).
//!
//! # L'état
//!
//! Chaque cellule **forestière** (`forest_mask.tif` = 1 dans une cellule de `grid.tif`) a un rang
//! dense ([`IndexForet`]) ; une cellule non forestière n'a ni classes ni semis. Pour chaque cellule
//! forestière et chaque essence du moteur (essences de `cohorts_init` et candidates au recrutement,
//! dans l'ordre des codes), K densités de tiges (tiges/ha, **f32**, ADR 0006 choix 3), rangées
//! `tiges[(rang × S + essence) × K + classe]`. La classe k couvre
//! [d_min + k w, d_min + (k + 1) w[ cm, d_min = 23,5 / π ≈ 7,48 cm (C13 = 0,235 m, seuil du modèle de
//! recrutement, contrat `cohorts_init`) ; la dernière est ouverte. Toutes les tiges d'une classe
//! portent le diamètre de son **centre** d_min + (k + 1/2) w, la dernière comprise : c'est l'erreur
//! de discrétisation du niveau, qui dépend de w et de K (réglages de `config.yml`, à dire au
//! rapport). Les sommes (surface terrière, `bal`, flux) sont faites en f64.
//!
//! # Le pas annuel (espérances, sans tirage : T4)
//!
//! Sur l'état figé au 1er janvier, cellule par cellule :
//!
//! 1. **résumé** : surface terrière par essence et totale (m²/ha), essence de plus forte surface
//!    terrière (à égalité, le plus petit code), cellule mêlée, d_dom des 100 plus grosses tiges/ha
//!    ([`diametre_dominant_classes`], même définition que le massif) ; **H_dom** avancée d'un an
//!    sur la courbe de cette essence ([`crate::hauteur::avancer_hdom`], plafond `site_potential`) ;
//!    une cellule sans adulte garde sa H_dom ; **indice de couvert** : Σ tiges/ha × π (cw / 2)² /
//!    10 000 m² (allométrie `cw` au centre de la classe, comme les houppiers du massif) ;
//! 2. **semis**, essence candidate par essence candidate : graines = `fecundity_seeds_per_m2_ba_yr`
//!    × surface terrière (m²) des classes semencières ; une classe est semencière si sa hauteur,
//!    H_dom × f(rel_d) au centre de la classe (`relative_height_gam`, rel_d = d / d_dom, la forme de
//!    la hauteur d'une recrue du massif), atteint `maturity_height_m` ; dispersion par FFT et règle
//!    |Q| ([`crate::dispersion`]) ; installation, survie selon l'ombre, croissance d'une classe
//!    ([`semis::avancer`]) ; **passage en espérance** ([`semis::passage_esperance`]) : sous couvert
//!    R = min(F, stock), F = exp(η) tiges/ha/an du modèle `recruitment_gam` (Q1) ; en trouée
//!    (H_dom nulle), tout le stock à la hauteur de passage passe ;
//! 3. **adultes**, classe par classe : covariables d130 = centre de la classe, `ba_plot` =
//!    surface terrière de la cellule, `bal` = surface terrière des classes **strictement plus
//!    grosses**, toutes essences ([`bal_par_classe`] : exact à la résolution d'une classe) ;
//!    mortalité en espérance, survivants S (1 − p), p = 1 − exp(−exp(η)) ; **transfert** des
//!    survivants vers les classes supérieures selon Δd = 2 exp(η) ([`transferer`] : une part Δd / w
//!    monte d'une classe, les tiges sont conservées) ; puis les recrues R entrent en classe 0.
//!    L'ordre est donc S' = transfert(S (1 − p)) + R, le même pour toute l'exécution.
//!
//! Une trouée qui recrute prend pour H_dom la plus grande hauteur de passage des essences qui y
//! recrutent, et elle est comptée recolonisée (comme au massif). Un compte de `run.json` qui est
//! un nombre d'arbres au massif (`recruits`, `deaths`) est ici l'espérance totale des tiges
//! (densité × aire de la cellule, sommée sur la simulation), arrondie à l'entier le plus proche ;
//! `edge_disks` vaut 0 (pas de disque de concurrence : `ba_plot` est la surface terrière de la
//! cellule). Seules les essences de `cohorts_init` sont simulées ([`preparer_modeles_ser`]) ; le
//! mode `ifn_direct` est refusé (code 2) au niveau SER.
//!
//! # Mémoire (T7)
//!
//! L'état ne grandit pas : il est réservé une fois, après l'estimation de
//! [`crate::memoire::estimer_ser`] et sa comparaison à `MemAvailable` (code 4 avant toute lecture
//! des cohortes et toute écriture). Les tampons du pas sont rendus à chaque pas ; la mémoire libérée
//! par la préparation et par l'écriture est rendue au système ([`rendre_la_memoire_liberee`]) pour
//! que la mémoire résidente reste celle de la formule.
//!
//! # Identité entre nombres de fils
//!
//! Les cellules sont traitées par blocs de [`CELLULES_PAR_BLOC`] cellules forestières, de taille
//! fixe (elle ne dépend pas du nombre de fils) ; chaque bloc fait ses sommes en ordre fixe et rend
//! ses comptes ; les blocs sont réunis dans leur ordre. La première erreur dans l'ordre des blocs,
//! donc des cellules, est rendue. Aucun tirage au niveau SER.
//!
//! Règle de lisibilité (CLAUDE.md) : structures concrètes, boucles simples, fermetures de rayon
//! seulement ; aucune macro maison ni générique.

use std::path::{Path, PathBuf};
use std::time::Instant;

use rayon::prelude::*;

use crate::accroissement::{self, SortiesParSens};
use crate::concurrence::{self, GeometrieGrille};
use crate::config::{ModeRecrutement, ReglagesSer};
use crate::controles::{self, Comptes, Signalement};
use crate::dispersion;
use crate::entrees::{self, Entrees};
use crate::erreurs::Erreur;
use crate::geotiff::Raster;
use crate::grille::Grille;
use crate::hauteur::{self, AvanceeHdom};
use crate::memoire::{self, BesoinSer};
use crate::mortalite;
use crate::parametres::Covariables;
use crate::pas::{self, EtatSemis, Modeles, ModelesEssence, Regeneration};
use crate::recrutement;
use crate::semis;
use crate::sorties::{self, Bilan, Lancement, MemoireDuRun};

/// Rang d'une cellule hors forêt dans [`IndexForet::rang_de_cellule`].
pub const HORS_FORET: u32 = u32::MAX;

/// Cellules forestières par bloc de calcul (réglage de calcul, sans effet sur les résultats).
pub const CELLULES_PAR_BLOC: usize = 4096;

/// Surface d'un hectare, en m² (passage des m²/ha à un indice de couvert sans unité).
const M2_PAR_HA: f64 = 10_000.0;

// ------------------------------------------------------------------------------------------
// Cellules forestières

/// L'index dense des cellules forestières : rang de chaque cellule de la grille (ou
/// [`HORS_FORET`]) et cellule de chaque rang, dans l'ordre des `cell_id`.
#[derive(Debug, Clone, PartialEq)]
pub struct IndexForet {
    pub rang_de_cellule: Vec<u32>,
    pub cellule_de_rang: Vec<u32>,
}

impl IndexForet {
    /// L'index tiré de `forest_mask.tif` (1 = forêt, 0 = hors forêt ; contrat
    /// `prepare.forest_mask`) : une cellule est forestière si elle a une valeur dans `grid.tif` et
    /// vaut 1 dans le masque. Code 2 si le masque n'est pas aligné sur la grille, n'a pas une
    /// bande, ou n'a ni 0 ni 1 dans une cellule de la grille (rien n'est deviné).
    pub fn depuis_masque(grille: &Grille, masque: &Raster) -> Result<IndexForet, Erreur> {
        let nom = "forest_mask.tif";
        grille.verifier_alignement(masque, nom)?;
        if masque.bandes.len() != 1 {
            return Err(Erreur::entree_refusee(format!(
                "{nom} : {} bandes au lieu d'une",
                masque.bandes.len()
            )));
        }
        let n = grille.nombre_cellules();
        if n >= HORS_FORET as usize {
            return Err(Erreur::entree_refusee(format!(
                "{nom} : {n} cellules, au-delà de l'index sur 32 bits"
            )));
        }
        let mut rang_de_cellule: Vec<u32> = Vec::new();
        rang_de_cellule
            .try_reserve_exact(n)
            .map_err(|_| memoire::erreur_allocation(n, "index des cellules forestières"))?;
        let mut forestieres: usize = 0;
        for cellule in 0..n {
            let valeur = masque.bandes[0][cellule];
            if !grille.valide[cellule] {
                rang_de_cellule.push(HORS_FORET);
                continue;
            }
            if masque.est_nodata(valeur) || !(valeur == 0.0 || valeur == 1.0) {
                return Err(Erreur::entree_refusee(format!(
                    "{nom} : cellule {cellule} de la grille sans valeur 0 ou 1 (lu : {valeur}) ; rien n'est deviné"
                )));
            }
            if valeur == 1.0 {
                rang_de_cellule.push(forestieres as u32);
                forestieres += 1;
            } else {
                rang_de_cellule.push(HORS_FORET);
            }
        }
        let mut cellule_de_rang: Vec<u32> = Vec::new();
        cellule_de_rang
            .try_reserve_exact(forestieres)
            .map_err(|_| memoire::erreur_allocation(forestieres, "index des cellules forestières"))?;
        for (cellule, rang) in rang_de_cellule.iter().enumerate() {
            if *rang != HORS_FORET {
                cellule_de_rang.push(cellule as u32);
            }
        }
        Ok(IndexForet {
            rang_de_cellule,
            cellule_de_rang,
        })
    }

    /// Le nombre de cellules forestières.
    pub fn nombre(&self) -> usize {
        self.cellule_de_rang.len()
    }

    /// Le rang d'une cellule de la grille, `None` hors forêt.
    pub fn rang(&self, cellule: usize) -> Option<usize> {
        match self.rang_de_cellule.get(cellule) {
            Some(rang) if *rang != HORS_FORET => Some(*rang as usize),
            _ => None,
        }
    }
}

/// Ce que la lecture des entrées prépare pour le niveau SER (module [`crate::entrees`]).
#[derive(Debug, Clone, PartialEq)]
pub struct EntreesSer {
    /// Le bloc `simulate.ser` de config.yml.
    pub reglages: ReglagesSer,
    /// Les cellules forestières.
    pub foret: IndexForet,
    /// `cohorts_init.parquet` de la zone (lu au lancement, après l'estimation de mémoire).
    pub chemin_cohortes: PathBuf,
    /// Les essences de `cohorts_init`, triées.
    pub essences: Vec<String>,
}

// ------------------------------------------------------------------------------------------
// Classes de diamètre

/// Les K classes de diamètre fixes (ADR 0006, choix 1) : centres (cm) et surface terrière d'une
/// tige au centre (m²).
#[derive(Debug, Clone, PartialEq)]
pub struct Classes {
    pub largeur_cm: f64,
    /// d_min, en cm : le seuil du modèle de recrutement (C13 = 0,235 m).
    pub d_min_cm: f64,
    pub centres_cm: Vec<f64>,
    pub surfaces_m2: Vec<f64>,
}

impl Classes {
    /// Les classes d'une largeur et d'un nombre donnés (au moins une classe).
    pub fn nouvelles(largeur_cm: f64, nombre: usize) -> Classes {
        let d_min_cm = recrutement::d130_recrue_cm();
        let mut centres_cm = Vec::with_capacity(nombre);
        let mut surfaces_m2 = Vec::with_capacity(nombre);
        for k in 0..nombre {
            let centre = d_min_cm + (k as f64 + 0.5) * largeur_cm;
            centres_cm.push(centre);
            surfaces_m2.push(concurrence::surface_terriere_m2(centre));
        }
        Classes {
            largeur_cm,
            d_min_cm,
            centres_cm,
            surfaces_m2,
        }
    }

    /// Le nombre K de classes.
    pub fn nombre(&self) -> usize {
        self.centres_cm.len()
    }
}

/// Les tiges/ha de chaque classe, toutes essences (`tiges_cellule` : S × K valeurs).
pub fn densites_par_classe(tiges_cellule: &[f32], classes: usize, sortie: &mut [f64]) {
    for valeur in sortie.iter_mut() {
        *valeur = 0.0;
    }
    for (rang, tiges) in tiges_cellule.iter().enumerate() {
        sortie[rang % classes] += f64::from(*tiges);
    }
}

/// La surface terrière (m²/ha) de chaque essence (`sortie`, S valeurs) et de la cellule (rendue).
pub fn surfaces_par_espece(tiges_cellule: &[f32], classes: &Classes, sortie: &mut [f64]) -> f64 {
    let k = classes.nombre();
    let mut totale = 0.0;
    for (espece, valeur) in sortie.iter_mut().enumerate() {
        let mut ba = 0.0;
        for classe in 0..k {
            ba += f64::from(tiges_cellule[espece * k + classe]) * classes.surfaces_m2[classe];
        }
        *valeur = ba;
        totale += ba;
    }
    totale
}

/// `bal` de chaque classe (m²/ha) : la surface terrière des classes **strictement plus grosses**,
/// toutes essences ; `densites` : tiges/ha par classe ([`densites_par_classe`]). La classe la
/// plus grosse a un `bal` nul. Sommes de la plus grosse classe vers la plus petite, en f64.
pub fn bal_par_classe(densites: &[f64], surfaces_m2: &[f64], sortie: &mut [f64]) {
    let k = densites.len();
    let mut cumul = 0.0;
    let mut classe = k;
    while classe > 0 {
        classe -= 1;
        sortie[classe] = cumul;
        cumul += densites[classe] * surfaces_m2[classe];
    }
}

/// Le diamètre dominant de classes : diamètre quadratique moyen des 100 plus grosses tiges/ha
/// ([`hauteur::TIGES_DOMINANTES_HA`]), la dernière classe prise pour la part qui complète les
/// 100 tiges (définition de `hauteur::diametre_dominant`, appliquée aux densités). `None` sans tige.
pub fn diametre_dominant_classes(densites: &[f64], centres_cm: &[f64]) -> Option<f64> {
    let mut reste = hauteur::TIGES_DOMINANTES_HA;
    let mut poids = 0.0;
    let mut somme_d2 = 0.0;
    let mut classe = densites.len();
    while classe > 0 && reste > 0.0 {
        classe -= 1;
        let tiges = densites[classe];
        if tiges <= 0.0 {
            continue;
        }
        let pris = if tiges < reste { tiges } else { reste };
        poids += pris;
        somme_d2 += pris * centres_cm[classe] * centres_cm[classe];
        reste -= pris;
    }
    if poids > 0.0 {
        Some((somme_d2 / poids).sqrt())
    } else {
        None
    }
}

/// Le transfert entre classes (matrice d'Usher généralisée, ADR 0006, choix 2) : les survivants
/// `survivants[k]` de la classe k gagnent Δd = `accroissements_cm[k]` ; avec f = Δd / w,
/// m = ⌊f⌋ et r = f − m, la part r monte de m + 1 classes et le reste de m classes (une seule
/// classe, r, quand Δd < w), sans dépasser la dernière classe (ouverte). `sortie` reçoit les K
/// densités ; les tiges sont conservées (Σ sortie = Σ survivants, à l'arrondi près).
///
/// Code 3 si un accroissement n'est pas fini ou est négatif.
pub fn transferer(
    survivants: &[f64],
    accroissements_cm: &[f64],
    largeur_cm: f64,
    sortie: &mut [f64],
) -> Result<(), Erreur> {
    let k = survivants.len();
    for valeur in sortie.iter_mut() {
        *valeur = 0.0;
    }
    for classe in 0..k {
        let tiges = survivants[classe];
        if tiges == 0.0 {
            continue;
        }
        let delta = accroissements_cm[classe];
        if !delta.is_finite() || delta < 0.0 {
            return Err(Erreur::controle_echoue(format!(
                "accroissement du diamètre {delta} cm non fini ou négatif (classe {classe})"
            )));
        }
        let f = delta / largeur_cm;
        let dernier = k - 1;
        // ⌊f⌋ borné par K : au-delà, tout va dans la dernière classe.
        let m = if f >= k as f64 { k } else { f.floor() as usize };
        let r = if m >= k { 0.0 } else { f - m as f64 };
        let bas = (classe + m).min(dernier);
        let haut = (classe + m + 1).min(dernier);
        let montee = tiges * r;
        sortie[haut] += montee;
        sortie[bas] += tiges - montee;
    }
    Ok(())
}

// ------------------------------------------------------------------------------------------
// Modèles du niveau SER

/// Les modèles du niveau SER : les essences de `cohorts_init`, dont les candidates au recrutement
/// sont celles qui ont les quatre jeux (croissance, mortalité, recrutement, hauteur ; T6). À la
/// différence du massif, une essence qui n'a que des lignes propres dans `params/` (par exemple
/// dans `allometry.parquet`) sans aucune cohorte dans la SER n'est pas candidate : au niveau SER,
/// les essences viennent de `cohorts_init` (écrit par `prepare` sur toute la SER), et une essence
/// sans adulte n'y aurait ni graines ni semenciers (choix de la mission 063, à confirmer par
/// l'orchestrateur). Code 2 si un jeu manque.
pub fn preparer_modeles_ser(entrees: &Entrees, essences_etat: &[String]) -> Result<Modeles, Erreur> {
    let sources = sorties::sources(&entrees.parametres);
    let candidates = pas::essences_candidates(&sources, &entrees.referentiel, essences_etat);
    let reference = sorties::reference_korf(&entrees.parametres.courbe_hauteur, &entrees.referentiel, essences_etat)?;
    Modeles::preparer(&sources, &entrees.referentiel, essences_etat, &candidates, reference)
}

/// Ce que le pas lit, préparé une fois : géométrie, classes, modèles, régénération, et la surface
/// de houppier d'une tige de chaque essence au centre de chaque classe (π (cw / 2)², m²).
pub struct Moteur<'a> {
    pub entrees: &'a Entrees,
    pub foret: &'a IndexForet,
    pub geometrie: GeometrieGrille,
    pub classes: Classes,
    pub modeles: Modeles,
    pub regeneration: Regeneration,
    /// `houppiers_m2[essence × K + classe]`.
    pub houppiers_m2: Vec<f64>,
}

impl<'a> Moteur<'a> {
    /// Prépare le moteur. Code 2 si un modèle ou un paramètre de semis manque.
    pub fn preparer(entrees: &'a Entrees, donnees: &'a EntreesSer) -> Result<Moteur<'a>, Erreur> {
        let reglages_regeneration = match &entrees.recrutement {
            ModeRecrutement::Cohortes(reglages) => *reglages,
            ModeRecrutement::IfnDirect => {
                return Err(Erreur::entree_refusee(
                    "config.yml : le niveau SER exige simulate.recruitment = cohorts (régénération par cohortes \
                     de semis, ADR 0006) ; le mode ifn_direct n'existe qu'au niveau massif"
                        .to_string(),
                ))
            }
        };
        let grille = &entrees.grille;
        let geometrie = GeometrieGrille::nouvelle(
            grille.largeur,
            grille.hauteur,
            grille.origine_x,
            grille.origine_y,
            grille.pas,
        )?;
        let classes = Classes::nouvelles(donnees.reglages.largeur_classe_cm, donnees.reglages.classes);
        let modeles = preparer_modeles_ser(entrees, &donnees.essences)?;
        let regeneration = Regeneration::preparer(
            &modeles,
            &entrees.regeneration,
            &entrees.referentiel,
            &reglages_regeneration,
            &geometrie,
        )?;
        let k = classes.nombre();
        let mut houppiers_m2 = Vec::with_capacity(modeles.essences.len() * k);
        for modele in &modeles.essences {
            for classe in 0..k {
                let rayon = modele.cw.cw(classes.centres_cm[classe]) / 2.0;
                houppiers_m2.push(std::f64::consts::PI * rayon * rayon);
            }
        }
        Ok(Moteur {
            entrees,
            foret: &donnees.foret,
            geometrie,
            classes,
            modeles,
            regeneration,
            houppiers_m2,
        })
    }

    /// Le nombre S d'essences du moteur.
    pub fn especes(&self) -> usize {
        self.modeles.essences.len()
    }

    /// Le nombre de valeurs f32 de l'état des adultes : cellules forestières × S × K.
    pub fn valeurs_etat(&self) -> usize {
        self.foret.nombre() * self.especes() * self.classes.nombre()
    }

    /// Ce que l'estimation de mémoire doit savoir (module [`crate::memoire`]).
    pub fn besoin(&self) -> BesoinSer {
        let plan = &self.regeneration.plan;
        let mut classes_semis: u64 = 0;
        for p in &self.regeneration.parametres {
            classes_semis += p.classes() as u64;
        }
        BesoinSer {
            cellules_grille: self.geometrie.nombre_cellules() as u64,
            cellules_foret: self.foret.nombre() as u64,
            especes: self.especes() as u64,
            classes: self.classes.nombre() as u64,
            classes_semis,
            candidates: self.modeles.candidates.len() as u64,
            valeurs_fft: (plan.colonnes_fft * plan.lignes_fft) as u64,
            valeurs_spectre: (plan.colonnes_spectrales() * plan.lignes_fft) as u64,
            lignes_par_fichier: sorties::LIGNES_PAR_FICHIER as u64,
        }
    }

    /// Le code de SER d'une cellule de la grille (`name` de `ser.csv`).
    fn code_ser(&self, cellule: usize) -> &str {
        self.entrees.couches.code_ser(cellule as u64).unwrap_or("")
    }

    /// Les covariables de station d'une cellule (f32 des rasters, rendues en f64 exactement).
    fn station(&self, cellule: usize) -> (f64, f64, f64) {
        let couches = &self.entrees.couches;
        (
            f64::from(couches.trophic[cellule]),
            f64::from(couches.hydric[cellule]),
            f64::from(couches.bioclim[cellule]),
        )
    }
}

fn avec_contexte(erreur: Erreur, annee: i32, entite: &str) -> Erreur {
    Erreur {
        code: erreur.code,
        message: format!("année {annee}, {entite} : {}", erreur.message),
    }
}

// ------------------------------------------------------------------------------------------
// L'état

/// L'état du niveau SER : adultes (f32), H_dom (m) et semis de chaque cellule forestière.
#[derive(Debug, Clone, PartialEq)]
pub struct EtatSer {
    /// `tiges[(rang × S + essence) × K + classe]`, tiges/ha.
    pub tiges: Vec<f32>,
    /// H_dom de chaque cellule forestière, m.
    pub h_dom: Vec<f64>,
    /// Les semis des essences candidates, rangés par cellule forestière ([`EtatSemis`]).
    pub semis: EtatSemis,
}

/// Les totaux de la simulation qui sont des espérances (tiges, et non arbres) : recrues et morts.
#[derive(Debug, Clone, Copy, Default, PartialEq)]
pub struct TotauxSer {
    /// Σ recrues/ha × aire de la cellule.
    pub recrues: f64,
    /// Σ (tiges/ha × p) × aire de la cellule.
    pub morts: f64,
}

/// Ce qu'un bloc de cellules rend : comptes, signalements dans l'ordre des cellules, totaux.
#[derive(Debug, Clone, Default)]
struct BilanBloc {
    comptes: Comptes,
    signalements: Vec<Signalement>,
    totaux: TotauxSer,
}

fn reunir(resultats: Vec<Result<BilanBloc, Erreur>>, bilan: &mut BilanBloc) -> Result<(), Erreur> {
    for resultat in resultats {
        let bloc = resultat?;
        bilan.comptes.ajouter(&bloc.comptes);
        bilan.signalements.extend(bloc.signalements);
        bilan.totaux.recrues += bloc.totaux.recrues;
        bilan.totaux.morts += bloc.totaux.morts;
    }
    Ok(())
}

/// Contrôle les tiges d'une cellule (finies et positives) : code 3 au premier écart.
fn controler_tiges(
    tiges_cellule: &[f32],
    moteur: &Moteur,
    cellule: usize,
    annee: i32,
    quand: &str,
) -> Result<(), Erreur> {
    let k = moteur.classes.nombre();
    for (rang, valeur) in tiges_cellule.iter().enumerate() {
        let v = f64::from(*valeur);
        if !v.is_finite() || v < 0.0 {
            let espece = &moteur.modeles.essences[rang / k].espece;
            let entite = format!("cellule {cellule}, essence {espece}, classe {} ({quand})", rang % k);
            controles::controler_valeur(annee, &entite, "stems_ha", v, controles::Positivite::Positive)?;
        }
    }
    Ok(())
}

/// Le résumé d'une cellule sur l'état figé : essence de la courbe de hauteur, cellule mêlée.
struct Resume {
    essence_courbe: Option<usize>,
    melee: bool,
}

/// Résume une cellule (`ba` : S valeurs, tampon du bloc) : l'essence de plus forte surface
/// terrière (à égalité, le plus petit code) parmi celles qui ont des tiges.
fn resumer(tiges_cellule: &[f32], classes: &Classes, ba: &mut [f64]) -> Resume {
    surfaces_par_espece(tiges_cellule, classes, ba);
    let mut essence_courbe = None;
    let mut ba_max = 0.0;
    let mut presentes = 0;
    for (espece, valeur) in ba.iter().enumerate() {
        if *valeur > 0.0 {
            presentes += 1;
            if *valeur > ba_max {
                ba_max = *valeur;
                essence_courbe = Some(espece);
            }
        }
    }
    Resume {
        essence_courbe,
        melee: presentes > 1,
    }
}

/// Compte et signale l'avance de H_dom d'une cellule (mêmes sortes que le massif).
fn bilan_hdom(
    avancee: &AvanceeHdom,
    h_depart: f64,
    modele: &ModelesEssence,
    cellule: usize,
    annee: i32,
    initialisation: bool,
    bloc: &mut BilanBloc,
) {
    let entite = cellule.to_string();
    if avancee.au_plafond {
        bloc.comptes.cellules_au_plafond += 1;
    }
    if avancee.au_dessus {
        bloc.comptes.cellules_au_dessus_du_plafond += 1;
        bloc.signalements.push(Signalement {
            annee,
            entite: entite.clone(),
            sorte: controles::SORTE_HDOM_AU_DESSUS_DU_PLAFOND.to_string(),
            message: format!(
                "hauteur dominante {h_depart:.2} m au-dessus du plafond de la station (site_potential), non corrigée"
            ),
            valeur: Some(h_depart),
        });
    }
    if avancee.au_dela_asymptote {
        bloc.comptes.cellules_asymptote_korf += 1;
        bloc.signalements.push(Signalement {
            annee,
            entite: entite.clone(),
            sorte: controles::SORTE_HDOM_ASYMPTOTE_KORF.to_string(),
            message: format!(
                "hauteur dominante {h_depart:.2} m à l'asymptote de la courbe de Korf ou au-delà : elle n'avance plus"
            ),
            valeur: Some(h_depart),
        });
    }
    if initialisation {
        if let Some(classe) = avancee.classe_korf {
            bloc.signalements.push(Signalement {
                annee,
                entite,
                sorte: controles::SORTE_CLASSE_KORF.to_string(),
                message: format!(
                    "courbe de Korf de l'essence {} : classe de fertilité {classe}, celle dont la hauteur \
                     à l'âge de référence de nemeton est la plus proche du plafond (règle provisoire)",
                    modele.espece
                ),
                valeur: Some(classe as f64),
            });
        }
    }
}

/// Étape 1 d'une cellule : vérifie l'état figé, avance H_dom (`h_depart`, sur `duree` années ;
/// à t0, la durée de la date de vol à t0), compte, et rend (H_dom de fin, indice de couvert).
#[allow(clippy::too_many_arguments)]
fn etape_cellule(
    moteur: &Moteur,
    tiges_cellule: &[f32],
    h_depart: f64,
    cellule: usize,
    annee: i32,
    t0: Option<i32>,
    ba: &mut [f64],
    bloc: &mut BilanBloc,
) -> Result<(f64, f64), Erreur> {
    controler_tiges(tiges_cellule, moteur, cellule, annee, "état de début d'année")?;
    let resume = resumer(tiges_cellule, &moteur.classes, ba);
    if resume.melee {
        bloc.comptes.cellules_melees += 1;
    }
    let mut couvert = 0.0;
    for (rang, tiges) in tiges_cellule.iter().enumerate() {
        couvert += f64::from(*tiges) * moteur.houppiers_m2[rang];
    }
    couvert /= M2_PAR_HA;
    let essence = match resume.essence_courbe {
        Some(essence) => essence,
        None => {
            bloc.comptes.cellules_sans_arbre += 1;
            return Ok((h_depart, couvert));
        }
    };
    let modele = &moteur.modeles.essences[essence];
    let entite = || format!("cellule {cellule} (courbe de l'essence {})", modele.espece);
    let couches = &moteur.entrees.couches;
    let duree = match t0 {
        Some(t0) => hauteur::annees_de_vol_a_t0(f64::from(couches.chm_date[cellule]), t0)
            .map_err(|e| avec_contexte(e, annee, &entite()))?,
        None => 1.0,
    };
    let plafond = f64::from(couches.h_pot[cellule]);
    let avancee = hauteur::avancer_hdom(
        &modele.courbe,
        h_depart,
        plafond,
        moteur.modeles.reference_korf.as_ref(),
        duree,
    )
    .map_err(|e| avec_contexte(e, annee, &entite()))?;
    bilan_hdom(&avancee, h_depart, modele, cellule, annee, t0.is_some(), bloc);
    Ok((avancee.h, couvert))
}

/// Le flux IFN (exp(η) tiges/ha/an, `recruitment_gam`) d'une essence candidate dans une cellule,
/// avec la surface terrière de la cellule et de l'essence (état figé).
#[allow(clippy::too_many_arguments)]
fn flux_ifn(
    moteur: &Moteur,
    modele: &ModelesEssence,
    ba_totale: f64,
    ba_espece: f64,
    cellule: usize,
    annee: i32,
    sorties_domaine: &mut SortiesParSens,
) -> Result<f64, Erreur> {
    let jeu = match &modele.recrutement {
        Some(jeu) => jeu,
        None => {
            return Err(Erreur::interne(format!(
                "essence candidate {} sans jeu de recrutement",
                modele.espece
            )))
        }
    };
    let (trophic, hydric, bioclim) = moteur.station(cellule);
    let covariables = Covariables {
        ba_plot: Some(ba_totale),
        ba_species: Some(ba_espece),
        trophic: Some(trophic),
        coarse_hydric_700m: Some(hydric),
        coarse_bioclim_700m: Some(bioclim),
        ..Covariables::default()
    };
    let entite = || format!("cellule {cellule}, essence {}", modele.espece);
    let eta = accroissement::predicteur(jeu, &covariables, moteur.code_ser(cellule), sorties_domaine)
        .map_err(|e| avec_contexte(e, annee, &entite()))?;
    let flux = eta.exp();
    if !flux.is_finite() {
        return Err(Erreur::controle_echoue(format!(
            "année {annee}, {} : flux de recrues {flux} non fini",
            entite()
        )));
    }
    Ok(flux)
}

/// Les graines produites dans une cellule par une essence (fécondité × surface terrière des classes
/// semencières, m²) ; `h_dom` : H_dom de l'état figé.
#[allow(clippy::too_many_arguments)]
fn graines_cellule(
    moteur: &Moteur,
    tiges_cellule: &[f32],
    essence: usize,
    p: &semis::ParametresSemis,
    h_dom: f64,
    cellule: usize,
    annee: i32,
    densites: &mut [f64],
    sorties_domaine: &mut SortiesParSens,
) -> Result<f64, Erreur> {
    if p.fecondite == 0.0 {
        return Ok(0.0);
    }
    let k = moteur.classes.nombre();
    let mut a_des_tiges = false;
    for classe in 0..k {
        if tiges_cellule[essence * k + classe] > 0.0 {
            a_des_tiges = true;
        }
    }
    if !a_des_tiges {
        return Ok(0.0);
    }
    densites_par_classe(tiges_cellule, k, densites);
    let d_dom = match diametre_dominant_classes(densites, &moteur.classes.centres_cm) {
        Some(d) => d,
        None => return Ok(0.0),
    };
    let modele = &moteur.modeles.essences[essence];
    let aire_ha = moteur.geometrie.aire_cellule_ha();
    let ser = moteur.code_ser(cellule);
    let mut surface_m2 = 0.0;
    for classe in 0..k {
        let tiges = f64::from(tiges_cellule[essence * k + classe]);
        if tiges <= 0.0 {
            continue;
        }
        let d = moteur.classes.centres_cm[classe];
        let covariables = Covariables {
            d130: Some(d),
            rel_d: Some(d / d_dom),
            ..Covariables::default()
        };
        let part = accroissement::predicteur(&modele.hauteur_relative, &covariables, ser, sorties_domaine)
            .map_err(|e| avec_contexte(e, annee, &format!("cellule {cellule}, essence {}", modele.espece)))?;
        if h_dom * part >= p.hauteur_maturite_m {
            surface_m2 += tiges * aire_ha * moteur.classes.surfaces_m2[classe];
        }
    }
    Ok(p.fecondite * surface_m2)
}

/// Le champ des graines d'une essence candidate sur toute la grille (0 hors forêt), et les
/// cellules qui en produisent (`semenciers`, mis à vrai, jamais à faux).
fn champ_de_graines(
    moteur: &Moteur,
    etat: &EtatSer,
    rang_candidat: usize,
    annee: i32,
    semenciers: &mut [bool],
    sorties_domaine: &mut SortiesParSens,
) -> Result<Vec<f64>, Erreur> {
    let n = moteur.geometrie.nombre_cellules();
    let largeur = moteur.geometrie.largeur;
    let essence = moteur.modeles.candidates[rang_candidat];
    let p = &moteur.regeneration.parametres[rang_candidat];
    let sk = moteur.especes() * moteur.classes.nombre();
    let mut champ = memoire::reserver_f64(n, "champ des graines")?;
    champ.resize(n, 0.0);
    let resultats: Vec<Result<SortiesParSens, Erreur>> = champ
        .par_chunks_mut(largeur)
        .zip(semenciers.par_chunks_mut(largeur))
        .enumerate()
        .map(|(ligne, (valeurs, semence))| {
            let mut sorties = SortiesParSens::default();
            let mut densites = vec![0.0_f64; moteur.classes.nombre()];
            for colonne in 0..valeurs.len() {
                let cellule = ligne * largeur + colonne;
                let rang = match moteur.foret.rang(cellule) {
                    Some(rang) => rang,
                    None => continue,
                };
                let tiges_cellule = &etat.tiges[rang * sk..(rang + 1) * sk];
                let g = graines_cellule(
                    moteur,
                    tiges_cellule,
                    essence,
                    p,
                    etat.h_dom[rang],
                    cellule,
                    annee,
                    &mut densites,
                    &mut sorties,
                )?;
                valeurs[colonne] = g;
                if g > 0.0 {
                    semence[colonne] = true;
                }
            }
            Ok(sorties)
        })
        .collect();
    for resultat in resultats {
        sorties_domaine.ajouter(&resultat?);
    }
    Ok(champ)
}

/// Vrai si une cellule du disque de rayon K autour de `cellule` produit des graines.
fn a_portee_d_un_semencier(cellule: usize, semenciers: &[bool], geometrie: &GeometrieGrille, k: usize) -> bool {
    let (ligne, colonne) = geometrie.ligne_colonne(cellule as u64);
    let kk = k as i64;
    for delta_ligne in -kk..=kk {
        let l = ligne as i64 + delta_ligne;
        if l < 0 || l >= geometrie.hauteur as i64 {
            continue;
        }
        for delta_colonne in -kk..=kk {
            let c = colonne as i64 + delta_colonne;
            if c < 0 || c >= geometrie.largeur as i64 {
                continue;
            }
            if dispersion::dans_le_disque(delta_ligne, delta_colonne, k)
                && semenciers[(l * geometrie.largeur as i64 + c) as usize]
            {
                return true;
            }
        }
    }
    false
}

fn signalement_hors_de_portee(annee: i32, cellule: usize, k: usize) -> Signalement {
    Signalement {
        annee,
        entite: cellule.to_string(),
        sorte: controles::SORTE_TROUEE_HORS_DE_PORTEE.to_string(),
        message: format!(
            "trouée (hauteur dominante nulle) hors de portée : aucun semencier dans le noyau tronqué \
             ({k} cellule(s) de rayon) ; elle reste vide"
        ),
        valeur: None,
    }
}

// ------------------------------------------------------------------------------------------
// t0

/// L'état à t0 : adultes de `cohorts_init` (déjà lus dans `tiges`), H_dom de `h0` avancée de la
/// date de vol à t0 dans les cellules qui ont des adultes (les autres gardent `h0`), semis « en
/// régime » (Q2 : état stationnaire du flux IFN de t0 à la survie de la cellule, ombre du couvert
/// de t0 comprise, [`semis::en_regime_avec_survie`] ; sous couvert ; rien en trouée), et les
/// signalements de t0 (dont les trouées hors de portée de tout semencier).
pub fn initialiser_t0(moteur: &Moteur, tiges: Vec<f32>, t0: i32) -> Result<(EtatSer, Comptes, Vec<Signalement>), Erreur> {
    let nf = moteur.foret.nombre();
    let s = moteur.especes();
    let k = moteur.classes.nombre();
    let sk = s * k;
    if tiges.len() != nf * sk {
        return Err(Erreur::interne(format!("{} tiges pour {} valeurs attendues", tiges.len(), nf * sk)));
    }
    let couches = &moteur.entrees.couches;
    let mut h_dom = memoire::reserver_f64(nf, "H_dom des cellules forestières")?;
    for rang in 0..nf {
        h_dom.push(f64::from(couches.h0[moteur.foret.cellule_de_rang[rang] as usize]));
    }
    // Indice de couvert de t0, celui que lira le premier pas (même état, même calcul) : il donne la
    // survie des semis du stock initial « en régime » (reprise de 062).
    let mut couvert_t0 = memoire::reserver_f64(nf, "indice de couvert de t0")?;
    couvert_t0.resize(nf, 0.0);
    let mut bilan = BilanBloc::default();
    let resultats: Vec<Result<BilanBloc, Erreur>> = tiges
        .par_chunks(CELLULES_PAR_BLOC * sk)
        .zip(h_dom.par_chunks_mut(CELLULES_PAR_BLOC))
        .zip(couvert_t0.par_chunks_mut(CELLULES_PAR_BLOC))
        .enumerate()
        .map(|(numero, ((tiges_bloc, h_bloc), couvert_bloc))| {
            let mut bloc = BilanBloc::default();
            let mut ba = vec![0.0_f64; s];
            for (i, h) in h_bloc.iter_mut().enumerate() {
                let rang = numero * CELLULES_PAR_BLOC + i;
                let cellule = moteur.foret.cellule_de_rang[rang] as usize;
                let (h_fin, couvert) = etape_cellule(
                    moteur,
                    &tiges_bloc[i * sk..(i + 1) * sk],
                    *h,
                    cellule,
                    t0,
                    Some(t0),
                    &mut ba,
                    &mut bloc,
                )?;
                *h = h_fin;
                couvert_bloc[i] = couvert;
            }
            Ok(bloc)
        })
        .collect();
    reunir(resultats, &mut bilan)?;

    // Semis en régime (Q2) : état stationnaire à la survie de la cellule (ombre du couvert de t0).
    let couvert_t0_ref = &couvert_t0;
    let mut classes_semis = Vec::with_capacity(moteur.modeles.candidates.len());
    let mut densites_semis = Vec::with_capacity(moteur.modeles.candidates.len());
    for (rang_candidat, essence) in moteur.modeles.candidates.iter().enumerate() {
        let p = &moteur.regeneration.parametres[rang_candidat];
        let a = p.classes();
        let modele = &moteur.modeles.essences[*essence];
        let mut valeurs = memoire::reserver_f64(nf * a, "classes de semis")?;
        valeurs.resize(nf * a, 0.0);
        let resultats: Vec<Result<BilanBloc, Erreur>> = valeurs
            .par_chunks_mut(CELLULES_PAR_BLOC * a)
            .enumerate()
            .map(|(numero, bloc_semis)| {
                let mut bloc = BilanBloc::default();
                let mut ba = vec![0.0_f64; s];
                for (i, classes_cellule) in bloc_semis.chunks_mut(a).enumerate() {
                    let rang = numero * CELLULES_PAR_BLOC + i;
                    if h_dom[rang] == 0.0 {
                        continue;
                    }
                    let cellule = moteur.foret.cellule_de_rang[rang] as usize;
                    let ba_totale = surfaces_par_espece(&tiges[rang * sk..(rang + 1) * sk], &moteur.classes, &mut ba);
                    let flux = flux_ifn(
                        moteur,
                        modele,
                        ba_totale,
                        ba[*essence],
                        cellule,
                        t0,
                        &mut bloc.comptes.sorties_domaine,
                    )?;
                    let survie = semis::survie(p, semis::lumiere_relative(p.coef_extinction, couvert_t0_ref[rang]));
                    semis::en_regime_avec_survie(p, flux, survie, classes_cellule);
                }
                Ok(bloc)
            })
            .collect();
        reunir(resultats, &mut bilan)?;
        classes_semis.push(a);
        densites_semis.push(valeurs);
    }
    let etat = EtatSer {
        tiges,
        h_dom,
        semis: EtatSemis {
            classes: classes_semis,
            densites: densites_semis,
        },
    };

    // Trouées de t0 hors de portée (calculées seulement s'il y a des trouées).
    let mut trouees = false;
    for h in &etat.h_dom {
        if *h == 0.0 {
            trouees = true;
            break;
        }
    }
    if trouees {
        let mut semenciers = vec![false; moteur.geometrie.nombre_cellules()];
        for rang_candidat in 0..moteur.modeles.candidates.len() {
            let mut sorties_domaine = SortiesParSens::default();
            let champ = champ_de_graines(moteur, &etat, rang_candidat, t0, &mut semenciers, &mut sorties_domaine)?;
            drop(champ);
        }
        let kk = moteur.regeneration.plan.demi_largeur;
        for rang in 0..nf {
            let cellule = moteur.foret.cellule_de_rang[rang] as usize;
            if etat.h_dom[rang] == 0.0 && !a_portee_d_un_semencier(cellule, &semenciers, &moteur.geometrie, kk) {
                bilan.signalements.push(signalement_hors_de_portee(t0, cellule, kk));
            }
        }
    }
    Ok((etat, bilan.comptes, bilan.signalements))
}

// ------------------------------------------------------------------------------------------
// Le pas annuel

/// Ce que rend un pas : comptes, signalements (cellules, puis trouées), totaux en espérance.
#[derive(Debug, Clone, Default)]
pub struct ResultatPasSer {
    pub comptes: Comptes,
    pub signalements: Vec<Signalement>,
    pub totaux: TotauxSer,
}

/// Le pas de l'année `annee` sur l'état figé au 1er janvier (voir la documentation du module) ;
/// l'état est mis à jour sur place, cellule par cellule. Codes : 1 invariant rompu, 2 entrée
/// manquante, 3 contrôle échoué (valeur non finie ou négative, dispersion fautive), 4 mémoire.
pub fn pas_annuel(moteur: &Moteur, etat: &mut EtatSer, annee: i32) -> Result<ResultatPasSer, Erreur> {
    let nf = moteur.foret.nombre();
    let s = moteur.especes();
    let k = moteur.classes.nombre();
    let sk = s * k;
    let n = moteur.geometrie.nombre_cellules();
    let aire_ha = moteur.geometrie.aire_cellule_ha();
    let candidates = moteur.modeles.candidates.len();
    if etat.tiges.len() != nf * sk || etat.h_dom.len() != nf || etat.semis.classes.len() != candidates {
        return Err(Erreur::interne("état du niveau SER de taille inattendue".to_string()));
    }
    let mut bilan = BilanBloc::default();

    // 1. Résumés, H_dom de fin d'année, indice de couvert (état figé).
    let mut h_fin = memoire::reserver_f64(nf, "H_dom de fin d'année")?;
    h_fin.resize(nf, 0.0);
    let mut couvert = memoire::reserver_f64(nf, "indice de couvert")?;
    couvert.resize(nf, 0.0);
    {
        let tiges = &etat.tiges;
        let h_dom = &etat.h_dom;
        let resultats: Vec<Result<BilanBloc, Erreur>> = h_fin
            .par_chunks_mut(CELLULES_PAR_BLOC)
            .zip(couvert.par_chunks_mut(CELLULES_PAR_BLOC))
            .enumerate()
            .map(|(numero, (h_bloc, couvert_bloc))| {
                let mut bloc = BilanBloc::default();
                let mut ba = vec![0.0_f64; s];
                for i in 0..h_bloc.len() {
                    let rang = numero * CELLULES_PAR_BLOC + i;
                    let cellule = moteur.foret.cellule_de_rang[rang] as usize;
                    let (h, c) = etape_cellule(
                        moteur,
                        &tiges[rang * sk..(rang + 1) * sk],
                        h_dom[rang],
                        cellule,
                        annee,
                        None,
                        &mut ba,
                        &mut bloc,
                    )?;
                    h_bloc[i] = h;
                    couvert_bloc[i] = c;
                }
                Ok(bloc)
            })
            .collect();
        reunir(resultats, &mut bilan)?;
    }

    // 2. Semis, essence candidate par essence candidate : graines, dispersion, installation,
    // survie, croissance, passage ; les recrues/ha de chaque cellule sont gardées.
    let mut recrues: Vec<Vec<f64>> = Vec::with_capacity(candidates);
    for _ in 0..candidates {
        let mut r = memoire::reserver_f64(nf, "recrues de l'année")?;
        r.resize(nf, 0.0);
        recrues.push(r);
    }
    let mut semenciers = vec![false; n];
    for rang_candidat in 0..candidates {
        let essence = moteur.modeles.candidates[rang_candidat];
        let modele = &moteur.modeles.essences[essence];
        let p = &moteur.regeneration.parametres[rang_candidat];
        let a = etat.semis.classes[rang_candidat];
        let champ = champ_de_graines(
            moteur,
            etat,
            rang_candidat,
            annee,
            &mut semenciers,
            &mut bilan.comptes.sorties_domaine,
        )?;
        let mut a_disperser = false;
        for valeur in &champ {
            if *valeur > 0.0 {
                a_disperser = true;
                break;
            }
        }
        let arrivees = if a_disperser {
            let mut arrivees = moteur
                .regeneration
                .plan
                .convoluer(&champ, &moteur.regeneration.spectres[rang_candidat])?;
            drop(champ);
            let quoi = format!("graines de l'essence {}, année {annee}", modele.espece);
            bilan.comptes.valeurs_mises_a_zero +=
                dispersion::mettre_a_zero(&mut arrivees, moteur.regeneration.seuil_zero, &quoi)?;
            Some(arrivees)
        } else {
            drop(champ);
            None
        };
        let tiges = &etat.tiges;
        let h_fin_ref = &h_fin;
        let couvert_ref = &couvert;
        let arrivees_ref = arrivees.as_ref();
        let resultats: Vec<Result<BilanBloc, Erreur>> = etat.semis.densites[rang_candidat]
            .par_chunks_mut(CELLULES_PAR_BLOC * a)
            .zip(recrues[rang_candidat].par_chunks_mut(CELLULES_PAR_BLOC))
            .enumerate()
            .map(|(numero, (bloc_semis, bloc_recrues))| {
                let mut bloc = BilanBloc::default();
                let mut ba = vec![0.0_f64; s];
                for (i, classes_cellule) in bloc_semis.chunks_mut(a).enumerate() {
                    let rang = numero * CELLULES_PAR_BLOC + i;
                    let cellule = moteur.foret.cellule_de_rang[rang] as usize;
                    let arrivee = match arrivees_ref {
                        Some(valeurs) => valeurs[cellule],
                        None => 0.0,
                    };
                    let nouveaux = p.part_installation * arrivee / aire_ha;
                    let survie = semis::survie(p, semis::lumiere_relative(p.coef_extinction, couvert_ref[rang]));
                    semis::avancer(classes_cellule, survie, nouveaux);
                    if h_fin_ref[rang] == 0.0 {
                        let (r, _) = semis::passage_esperance(classes_cellule, None);
                        bloc_recrues[i] = r;
                        continue;
                    }
                    let ba_totale = surfaces_par_espece(&tiges[rang * sk..(rang + 1) * sk], &moteur.classes, &mut ba);
                    let flux = flux_ifn(
                        moteur,
                        modele,
                        ba_totale,
                        ba[essence],
                        cellule,
                        annee,
                        &mut bloc.comptes.sorties_domaine,
                    )?;
                    let (r, borne) = semis::passage_esperance(classes_cellule, Some(flux));
                    bloc_recrues[i] = r;
                    if borne {
                        bloc.comptes.stock_de_semis_limitant += 1;
                    }
                }
                Ok(bloc)
            })
            .collect();
        drop(arrivees);
        reunir(resultats, &mut bilan)?;
    }

    // 3. Adultes : mortalité, accroissement et transfert, recrues ; H_dom de fin d'année.
    {
        let recrues_ref = &recrues;
        let h_fin_ref = &h_fin;
        let resultats: Vec<Result<BilanBloc, Erreur>> = etat
            .tiges
            .par_chunks_mut(CELLULES_PAR_BLOC * sk)
            .zip(etat.h_dom.par_chunks_mut(CELLULES_PAR_BLOC))
            .enumerate()
            .map(|(numero, (tiges_bloc, h_bloc))| {
                let mut bloc = BilanBloc::default();
                let mut tampons = Tampons::nouveaux(s, k);
                for i in 0..h_bloc.len() {
                    let rang = numero * CELLULES_PAR_BLOC + i;
                    let cellule = moteur.foret.cellule_de_rang[rang] as usize;
                    let tiges_cellule = &mut tiges_bloc[i * sk..(i + 1) * sk];
                    avancer_adultes(moteur, tiges_cellule, recrues_ref, rang, cellule, annee, &mut tampons, &mut bloc)?;
                    h_bloc[i] = h_fin_ref[rang];
                    if h_fin_ref[rang] == 0.0 {
                        let mut hauteur_trouee: f64 = 0.0;
                        let mut a_recrute = false;
                        for (rang_candidat, r) in recrues_ref.iter().enumerate() {
                            if r[rang] > 0.0 {
                                a_recrute = true;
                                hauteur_trouee =
                                    hauteur_trouee.max(moteur.regeneration.parametres[rang_candidat].hauteur_passage_m);
                            }
                        }
                        if a_recrute {
                            h_bloc[i] = hauteur_trouee;
                            bloc.comptes.trouees_recolonisees += 1;
                        }
                    }
                }
                Ok(bloc)
            })
            .collect();
        reunir(resultats, &mut bilan)?;
    }

    // 4. Trouées sans recrue : hors de portée, ou à portée mais sans aucun semis.
    let kk = moteur.regeneration.plan.demi_largeur;
    for rang in 0..nf {
        if h_fin[rang] != 0.0 {
            continue;
        }
        let mut a_recrute = false;
        for r in &recrues {
            if r[rang] > 0.0 {
                a_recrute = true;
            }
        }
        if a_recrute {
            continue;
        }
        let cellule = moteur.foret.cellule_de_rang[rang] as usize;
        if !a_portee_d_un_semencier(cellule, &semenciers, &moteur.geometrie, kk) {
            bilan.signalements.push(signalement_hors_de_portee(annee, cellule, kk));
            continue;
        }
        let mut semis_presents = false;
        for rang_candidat in 0..candidates {
            if semis::total(etat.semis.de(rang_candidat, rang)) > 0.0 {
                semis_presents = true;
            }
        }
        if !semis_presents {
            bilan.comptes.cellules_trouee_sans_recrue += 1;
            bilan.signalements.push(Signalement {
                annee,
                entite: cellule.to_string(),
                sorte: controles::SORTE_TROUEE_SANS_RECRUE.to_string(),
                message: "trouée (hauteur dominante nulle) à portée de semenciers mais sans aucun semis \
                          cette année : aucune recrue"
                    .to_string(),
                valeur: Some(0.0),
            });
        }
    }
    Ok(ResultatPasSer {
        comptes: bilan.comptes,
        signalements: bilan.signalements,
        totaux: bilan.totaux,
    })
}

/// Les tampons d'un bloc de cellules pour l'étape des adultes.
struct Tampons {
    ba: Vec<f64>,
    densites: Vec<f64>,
    bal: Vec<f64>,
    survivants: Vec<f64>,
    accroissements: Vec<f64>,
    nouvelles: Vec<f64>,
}

impl Tampons {
    fn nouveaux(especes: usize, classes: usize) -> Tampons {
        Tampons {
            ba: vec![0.0; especes],
            densites: vec![0.0; classes],
            bal: vec![0.0; classes],
            survivants: vec![0.0; classes],
            accroissements: vec![0.0; classes],
            nouvelles: vec![0.0; classes],
        }
    }
}

/// Étape 3 d'une cellule : chaque classe de chaque essence meurt en espérance, grandit et se
/// transfère ; les recrues entrent en classe 0. Covariables de l'état figé de la cellule, calculées
/// avant toute modification. Code 3 si une valeur n'est pas finie ou est négative.
#[allow(clippy::too_many_arguments)]
fn avancer_adultes(
    moteur: &Moteur,
    tiges_cellule: &mut [f32],
    recrues: &[Vec<f64>],
    rang: usize,
    cellule: usize,
    annee: i32,
    t: &mut Tampons,
    bloc: &mut BilanBloc,
) -> Result<(), Erreur> {
    let k = moteur.classes.nombre();
    let aire_ha = moteur.geometrie.aire_cellule_ha();
    let ba_totale = surfaces_par_espece(tiges_cellule, &moteur.classes, &mut t.ba);
    densites_par_classe(tiges_cellule, k, &mut t.densites);
    bal_par_classe(&t.densites, &moteur.classes.surfaces_m2, &mut t.bal);
    let (trophic, hydric, bioclim) = moteur.station(cellule);
    let ser = moteur.code_ser(cellule);
    for (essence, modele) in moteur.modeles.essences.iter().enumerate() {
        let tiges_espece = &mut tiges_cellule[essence * k..(essence + 1) * k];
        let mut morts = 0.0;
        let mut a_des_tiges = false;
        for classe in 0..k {
            let tiges = f64::from(tiges_espece[classe]);
            t.survivants[classe] = 0.0;
            t.accroissements[classe] = 0.0;
            if tiges <= 0.0 {
                continue;
            }
            a_des_tiges = true;
            let covariables = accroissement::covariables_arbre(
                moteur.classes.centres_cm[classe],
                ba_totale,
                t.bal[classe],
                trophic,
                hydric,
                bioclim,
            );
            let entite = || format!("cellule {cellule}, essence {}, classe {classe}", modele.espece);
            let delta = accroissement::accroissement_diametre(
                &modele.croissance,
                &covariables,
                ser,
                &mut bloc.comptes.sorties_domaine,
            )
            .map_err(|e| avec_contexte(e, annee, &entite()))?;
            let eta_mort =
                accroissement::predicteur(&modele.mortalite, &covariables, ser, &mut bloc.comptes.sorties_domaine)
                    .map_err(|e| avec_contexte(e, annee, &entite()))?;
            let p = mortalite::probabilite_annuelle(eta_mort);
            let survivants = tiges * (1.0 - p);
            morts += tiges - survivants;
            t.survivants[classe] = survivants;
            t.accroissements[classe] = delta;
        }
        let mut recrues_espece = 0.0;
        for (rang_candidat, candidate) in moteur.modeles.candidates.iter().enumerate() {
            if *candidate == essence {
                recrues_espece = recrues[rang_candidat][rang];
            }
        }
        if !a_des_tiges && recrues_espece == 0.0 {
            continue;
        }
        transferer(&t.survivants, &t.accroissements, moteur.classes.largeur_cm, &mut t.nouvelles)
            .map_err(|e| avec_contexte(e, annee, &format!("cellule {cellule}, essence {}", modele.espece)))?;
        t.nouvelles[0] += recrues_espece;
        for classe in 0..k {
            let valeur = t.nouvelles[classe];
            if !valeur.is_finite() || valeur < 0.0 {
                let entite = format!("cellule {cellule}, essence {}, classe {classe} (fin d'année)", modele.espece);
                controles::controler_valeur(annee, &entite, "stems_ha", valeur, controles::Positivite::Positive)?;
            }
            tiges_espece[classe] = valeur as f32;
        }
        bloc.totaux.morts += morts * aire_ha;
        bloc.totaux.recrues += recrues_espece * aire_ha;
    }
    Ok(())
}

// ------------------------------------------------------------------------------------------
// La simulation et ses sorties

/// Les années écrites (T8) : t0, t0 + w, t0 + 2w… et la dernière, sans doublon, croissantes.
pub fn annees_ecrites(t0: i32, years: u32, pas: u32) -> Vec<i32> {
    let mut annees = Vec::new();
    let mut rang: u32 = 0;
    while rang <= years {
        annees.push(t0 + rang as i32);
        rang += pas;
    }
    let derniere = t0 + years as i32;
    if annees.last() != Some(&derniere) {
        annees.push(derniere);
    }
    annees
}

/// Simule le niveau SER de t0 à t0 + years et écrit tout dans `dossier` (qui ne doit pas
/// exister) : `cohorts/` et `cells/` aux années écrites, `flags.parquet`, `run.json` ; jamais
/// `trees/` (il n'y a pas d'individus, BRIEF §3).
///
/// La mémoire est estimée ([`memoire::estimer_ser`]) et comparée à 0,9 × `MemAvailable` **avant**
/// la lecture des cohortes et la création du dossier : code 4 sinon. Codes comme
/// [`sorties::simuler_et_ecrire`].
pub fn simuler_et_ecrire(entrees: &Entrees, lancement: &Lancement, dossier: &Path) -> Result<Bilan, Erreur> {
    let debut = Instant::now();
    let reglages = &entrees.reglages;
    let donnees = match &entrees.ser {
        Some(donnees) => donnees,
        None => return Err(Erreur::interne("niveau SER sans ses entrées (cohorts_init, forest_mask)".to_string())),
    };
    if lancement.threads == 0 {
        return Err(Erreur::entree_refusee("nombre de fils nul : il en faut au moins un".to_string()));
    }
    let derniere = reglages
        .t0
        .checked_add(reglages.years as i32)
        .ok_or_else(|| Erreur::entree_refusee("t0 + years dépasse les années représentables".to_string()))?;
    if let Some(annee) = lancement.inject_nan {
        if annee < reglages.t0 || annee > derniere || donnees.foret.nombre() == 0 {
            return Err(Erreur::entree_refusee(format!(
                "--inject-nan {annee} : l'année doit être entre t0 = {} et t0 + years = {derniere}, et la \
                 SER doit avoir au moins une cellule forestière",
                reglages.t0
            )));
        }
    }
    let moteur = Moteur::preparer(entrees, donnees)?;

    // Avant toute lecture des cohortes et toute écriture : la mémoire (T7).
    let memoire_estimee = memoire::estimer_ser(&moteur.besoin())?;
    memoire::verifier(memoire_estimee, lancement.memoire_disponible)?;

    if dossier.exists() {
        return Err(Erreur::interne(format!("le dossier de sortie {} existe déjà", dossier.display())));
    }
    std::fs::create_dir_all(dossier)
        .map_err(|e| Erreur::interne(format!("dossier {} impossible à créer : {e}", dossier.display())))?;
    let pool = rayon::ThreadPoolBuilder::new()
        .num_threads(lancement.threads)
        .build()
        .map_err(|e| Erreur::interne(format!("pool de {} fils impossible : {e}", lancement.threads)))?;
    let (mut comptes, mut signalements, totaux, memoire_maximale) =
        pool.install(|| boucle(&moteur, donnees, lancement, dossier, memoire_estimee))?;
    comptes.recrues = totaux.recrues.round() as u64;
    comptes.morts = totaux.morts.round() as u64;

    sorties::ajouter_signalements_de_zone(
        &mut signalements,
        &comptes,
        lancement,
        reglages.t0,
        derniere,
        Some(&moteur.regeneration),
    );
    sorties::ecrire_signalements(&dossier.join("flags.parquet"), &signalements)?;
    let duree_s = debut.elapsed().as_secs_f64();
    let plan = &moteur.regeneration.plan;
    let memoire = MemoireDuRun {
        estimee: memoire_estimee,
        maximale: memoire_maximale.max(memoire_estimee),
        pic_residente: sorties::pic_memoire_residente(),
        cellules_tampon: Some(dispersion::cellules_tampon(plan.largeur, plan.hauteur, plan.demi_largeur)),
    };
    let run = sorties::run_json_m5(
        entrees,
        lancement,
        &comptes,
        sorties::part_provisoire_avec_semis(&moteur.modeles, Some(&moteur.regeneration)),
        &memoire,
        duree_s,
    );
    std::fs::write(dossier.join("run.json"), run)
        .map_err(|e| Erreur::interne(format!("écriture de run.json impossible : {e}")))?;
    Ok(Bilan {
        comptes,
        memoire_estimee,
        memoire_maximale: memoire.maximale,
        duree_s,
        lignes_arbres: 0,
        signalements: signalements.len() as u64,
    })
}

/// Lecture des cohortes, t0, puis les pas ; écriture des années retenues. Dans le pool de
/// l'appelant. Rend les comptes, les signalements, les totaux et la plus grande estimation.
fn boucle(
    moteur: &Moteur,
    donnees: &EntreesSer,
    lancement: &Lancement,
    dossier: &Path,
    memoire_estimee: u64,
) -> Result<(Comptes, Vec<Signalement>, TotauxSer, u64), Erreur> {
    let reglages = &moteur.entrees.reglages;
    let t0 = reglages.t0;
    let ecrites = annees_ecrites(t0, reglages.years, donnees.reglages.pas_ecriture);
    let mut comptes = Comptes::default();
    let mut signalements: Vec<Signalement> = Vec::new();
    let mut totaux = TotauxSer::default();
    let mut memoire_maximale = memoire_estimee;

    let debut = Instant::now();
    let codes: Vec<String> = moteur.modeles.essences.iter().map(|m| m.espece.clone()).collect();
    let valeurs = moteur.valeurs_etat();
    let mut tiges: Vec<f32> = Vec::new();
    tiges
        .try_reserve_exact(valeurs)
        .map_err(|_| memoire::erreur_allocation(valeurs, "classes de diamètre des adultes"))?;
    tiges.resize(valeurs, entrees::ABSENTE);
    entrees::lire_cohortes(
        &donnees.chemin_cohortes,
        &moteur.entrees.grille,
        &donnees.foret,
        &codes,
        moteur.classes.nombre(),
        &mut tiges,
    )?;
    if lancement.inject_nan == Some(t0) {
        injecter_nan(&mut tiges);
    }
    let (mut etat, comptes_t0, signalements_t0) = initialiser_t0(moteur, tiges, t0)?;
    comptes.ajouter(&comptes_t0);
    signalements.extend(signalements_t0);
    let calcul_t0 = debut.elapsed().as_secs_f64();
    let debut_ecriture = Instant::now();
    sorties::ecrire_annee_ser(dossier, t0, moteur, &etat)?;
    rendre_la_memoire_liberee();
    // Ligne lue par bench/m5/mesurer.sh (temps de calcul et d'écriture séparés, T6).
    eprintln!(
        "[simulate] niveau SER : t0 = {t0} : calcul {calcul_t0:.3} s ; écriture {:.3} s",
        debut_ecriture.elapsed().as_secs_f64()
    );

    for rang in 1..=reglages.years {
        let annee = t0 + rang as i32;
        // L'état du niveau SER ne grandit pas : l'estimation est refaite et revérifiée à chaque pas.
        let besoin = memoire::estimer_ser(&moteur.besoin())?;
        memoire::verifier(besoin, lancement.memoire_disponible)?;
        memoire_maximale = memoire_maximale.max(besoin);
        if lancement.inject_nan == Some(annee) {
            injecter_nan(&mut etat.tiges);
        }
        let debut_pas = Instant::now();
        let resultat = pas_annuel(moteur, &mut etat, annee)?;
        comptes.ajouter(&resultat.comptes);
        signalements.extend(resultat.signalements);
        totaux.recrues += resultat.totaux.recrues;
        totaux.morts += resultat.totaux.morts;
        let calcul = debut_pas.elapsed().as_secs_f64();
        let debut_ecriture = Instant::now();
        if ecrites.contains(&annee) {
            sorties::ecrire_annee_ser(dossier, annee, moteur, &etat)?;
            rendre_la_memoire_liberee();
        }
        eprintln!(
            "[simulate] niveau SER : année {annee} ({rang}/{}) : calcul {calcul:.3} s ; écriture {:.3} s",
            reglages.years,
            debut_ecriture.elapsed().as_secs_f64()
        );
    }
    Ok((comptes, signalements, totaux, memoire_maximale))
}

/// Rend au système la mémoire déjà libérée (tampons de lecture des rasters et des cohortes,
/// tableaux de travail des spectres de FFT) : sans cela, l'allocateur de la glibc garde ces pages
/// résidentes, et la mémoire résidente du pas annuel dépasserait la formule de
/// [`memoire::estimer_ser`] d'une quantité qui dépend de l'histoire des allocations (environ 40 Mio
/// à N = 1 000, mesure de la mission 063). Appelé après l'écriture de t0 (avant le premier pas)
/// et après chaque année écrite (tampons d'écriture).
/// Sans effet sur les résultats. Hors de la glibc (Linux), rien n'est fait : l'estimation peut alors
/// être sous la mémoire résidente.
pub fn rendre_la_memoire_liberee() {
    #[cfg(all(target_os = "linux", target_env = "gnu"))]
    {
        extern "C" {
            fn malloc_trim(pad: usize) -> i32;
        }
        // SÛRETÉ : malloc_trim(3) de la glibc ne lit ni n'écrit aucune donnée du programme ; il
        // rend au noyau les pages libres de l'allocateur. Son code de retour (1 si de la mémoire a
        // été rendue, 0 sinon) n'a pas d'usage ici.
        unsafe {
            malloc_trim(0);
        }
    }
}

/// Option de test `--inject-nan` : la première densité de l'état devient NaN.
fn injecter_nan(tiges: &mut [f32]) {
    if let Some(valeur) = tiges.first_mut() {
        *valeur = f32::NAN;
    }
}
