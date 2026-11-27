//! Le pas annuel de `simulate` et l'avance de l'état initial jusqu'à t0 (plan M3a, « Le pas
//! annuel » ; spec §4 point 4, §5 et §6).
//!
//! Étape du BRIEF codée ici : BRIEF §6 (dynamique des arbres et hauteur) et §8 (le massif simulé
//! année par année) : ce module enchaîne, pour une année, la concurrence, l'accroissement, la
//! hauteur, la mortalité et le recrutement, puis les houppiers et les contrôles.
//!
//! # L'état figé au 1er janvier
//!
//! [`pas_annuel`] lit l'état de début d'année (tous les arbres vivants) sans jamais le modifier ;
//! chaque grandeur nouvelle est calculée à partir de lui seul et rangée dans des colonnes
//! séparées, si bien que l'ordre des calculs n'a pas d'effet :
//!
//! 1. **concurrence** : `ba_plot` et `bal` du disque de 15 m ([`crate::concurrence`]) ;
//! 2. **résumé des cellules** : surface terrière par essence (m²/ha, la cellule entière, T7),
//!    essence de plus forte surface terrière (à égalité, le plus petit code), cellule mêlée si
//!    plusieurs essences, d_dom ([`crate::hauteur::diametre_dominant`]) ;
//! 3. **H_dom** de chaque cellule avancée d'un an exactement ([`crate::hauteur::avancer_hdom`]) ;
//!    une cellule sans arbre garde sa H_dom (aucune essence ne donne sa courbe) et est comptée ;
//! 4. **arbres** : d130 += 2 exp(η) ([`crate::accroissement`]) ; h += f(rel_d) × ΔH_dom ;
//!    mort tirée ([`crate::mortalite`]). Un arbre qui meurt dans l'année est écrit `dead` avec
//!    ses valeurs du 1er janvier (il ne grandit pas l'année de sa mort) ;
//! 5. **recrutement** par cellule simulée et essence candidate ([`crate::recrutement`]) ; numéros
//!    des recrues par somme de préfixes séquentielle dans l'ordre des `cell_id` ; hauteur
//!    H_dom (fin d'année) × f(rel_d), rel_d = 7,48 / d_dom de la cellule (1 si la cellule n'a pas
//!    d'arbre : la recrue est alors sa propre dominante ; compté) ; ajoutées en fin d'année ;
//!    **aucune recrue dans une trouée**, cellule simulée dont la H_dom de fin d'année est nulle
//!    (décision de Pascal du 25/11/2026 : la recolonisation des trouées viendra en M5 par les
//!    cohortes) : ni espérance ni tirage n'y sont calculés, chaque couple (cellule, année) est
//!    compté et signalé ([`controles::SORTE_TROUEE_SANS_RECRUE`]) ;
//!    en mode `cohorts` (M5a, mission 062), l'étape 5 est remplacée par la régénération par
//!    cohortes de semis ([`pas_annuel_cohortes`], modules [`crate::dispersion`] et
//!    [`crate::semis`]) : graines des semenciers dispersées par FFT, installation, survie selon
//!    l'ombre, croissance d'une classe, puis passage à la futaie, au flux IFN borné par le stock
//!    sous couvert (mêmes tirages qu'en `ifn_direct`), de tout le stock à la hauteur de passage en
//!    trouée (décisions de Pascal Q1 à Q4 du 26/11/2026) : les trouées se recolonisent ;
//! 6. **houppiers** hcb et cw par les allométries ([`crate::hauteur::AllometrieHcb`],
//!    [`crate::hauteur::AllometrieCw`]) ;
//! 7. **contrôles** ([`crate::controles::controler_arbres`]) : code 3 au premier écart.
//!
//! L'état rendu contient les morts de l'année (`vivant = false`) et les recrues : c'est ce que
//! l'on écrit sous `year=Y`. Avant le pas suivant, on retire les morts
//! ([`crate::etat::EtatArbres::retirer_morts`]).
//!
//! # Identité entre nombres de fils (plan M3a, T1)
//!
//! Les fonctions des étapes sont pures et tournent en parallèle (rayon) sur les arbres ou sur
//! les cellules ; chaque somme flottante est faite par un seul fil, en ordre fixe ; les comptes
//! sont des entiers ; l'aléa ne dépend que de ses clés. Les erreurs sont recueillies dans
//! l'ordre des arbres ou des cellules et la première est rendue : même l'erreur ne dépend pas du
//! nombre de fils. Le pas s'exécute dans le pool rayon de l'appelant.
//!
//! # Paramètres
//!
//! [`Modeles::preparer`] cherche, une fois, tous les jeux de chaque essence (essence, puis groupe,
//! puis `toutes_essences`) ; ce qui manque est une erreur code 2, jamais une valeur inventée.
//!
//! Règle de lisibilité (CLAUDE.md) : structures concrètes, boucles simples, fermetures de rayon
//! seulement ; aucune macro maison ni générique maison.

use rayon::prelude::*;

use crate::accroissement::{self, SortiesParSens};
use crate::alea::packer_essence;
use crate::concurrence::{self, Concurrence, GeometrieGrille, IndexParCellule};
use crate::controles::{self, Comptes, Positivite, Signalement};
use crate::erreurs::Erreur;
use crate::etat::{premiers_numeros, ArbreNouveau, EtatArbres};
use crate::hauteur::{self, AllometrieCw, AllometrieHcb, AvanceeHdom, Courbe, ReferenceKorf};
use crate::mortalite;
use crate::parametres::{
    Covariables, JeuDeParametres, Parametres, Porteur, Referentiel, TOUTES_ESSENCES,
};
use crate::recrutement;
use crate::config::ReglagesRegeneration;
use crate::dispersion::{self, Noyau, PlanDispersion, SpectreNoyau};
use crate::memoire;
use crate::semis::{self, LigneRegeneration, ParametresSemis};

// ------------------------------------------------------------------------------------------
// Cellules

/// Les couches de la grille, une valeur par cellule dans l'ordre de `cell_id` (lues par la
/// mission 036 dans `h0.tif`, `chm_date.tif`, `station_gradients.tif`, `ser.tif`,
/// `site_potential.tif`). Une valeur absente est NaN (ou une chaîne vide pour la SER).
#[derive(Debug, Clone, PartialEq)]
pub struct Cellules {
    pub geometrie: GeometrieGrille,
    /// Vrai si la cellule est simulée (elle a une valeur dans `grid.tif`) ; seules les cellules
    /// simulées reçoivent des recrues.
    pub simulee: Vec<bool>,
    /// H_dom à la date de vol, en m (`h0.tif`).
    pub h0: Vec<f64>,
    /// Date de vol, en jours depuis le 1970-01-01 (`chm_date.tif`).
    pub chm_date: Vec<f64>,
    /// Bandes de `station_gradients.tif`.
    pub trophic: Vec<f64>,
    pub hydric: Vec<f64>,
    pub bioclim: Vec<f64>,
    /// Code de SER (`name` de `ser.csv`).
    pub ser_code: Vec<String>,
    /// Plafond de hauteur `site_potential`, en m : `nombre_bandes` valeurs par cellule, rangées
    /// cellule par cellule (valeur de la cellule c, bande b : `site_potential[c × nombre_bandes + b]`).
    pub site_potential: Vec<f64>,
    pub nombre_bandes: usize,
    /// Table explicite essence → bande (rang à partir de 0), exigée s'il y a plusieurs bandes (T4).
    pub bande_par_essence: Vec<(String, usize)>,
}

impl Cellules {
    /// Vérifie les longueurs et la table des bandes. Code 2 sinon.
    pub fn verifier(&self) -> Result<(), Erreur> {
        let n = self.geometrie.nombre_cellules();
        let longueurs = [
            ("simulee", self.simulee.len()),
            ("h0", self.h0.len()),
            ("chm_date", self.chm_date.len()),
            ("trophic", self.trophic.len()),
            ("hydric", self.hydric.len()),
            ("bioclim", self.bioclim.len()),
            ("ser_code", self.ser_code.len()),
        ];
        for (nom, longueur) in longueurs {
            if longueur != n {
                return Err(Erreur::entree_refusee(format!(
                    "couche {nom} : {longueur} valeurs pour {n} cellules"
                )));
            }
        }
        if self.nombre_bandes == 0 || self.site_potential.len() != n * self.nombre_bandes {
            return Err(Erreur::entree_refusee(format!(
                "site_potential : {} valeurs pour {n} cellules et {} bande(s)",
                self.site_potential.len(),
                self.nombre_bandes
            )));
        }
        for (espece, bande) in &self.bande_par_essence {
            if *bande >= self.nombre_bandes {
                return Err(Erreur::entree_refusee(format!(
                    "table des bandes de site_potential : essence {espece} vers la bande {} (rang {bande}), \
                     il n'y en a que {}",
                    bande + 1,
                    self.nombre_bandes
                )));
            }
        }
        Ok(())
    }

    /// Le plafond de hauteur d'une essence dans une cellule : la bande unique, sinon celle de la
    /// table explicite (T4). Code 2 si l'essence n'est pas dans la table.
    pub fn plafond(&self, cellule: usize, espece: &str) -> Result<f64, Erreur> {
        if self.nombre_bandes == 1 {
            return Ok(self.site_potential[cellule]);
        }
        for (code, bande) in &self.bande_par_essence {
            if code == espece {
                return Ok(self.site_potential[cellule * self.nombre_bandes + *bande]);
            }
        }
        Err(Erreur::entree_refusee(format!(
            "site_potential a {} bandes et l'essence {espece} n'a pas de bande dans la table explicite (T4)",
            self.nombre_bandes
        )))
    }
}

/// La H_dom courante de chaque cellule, en m (ordre de `cell_id`).
#[derive(Debug, Clone, PartialEq)]
pub struct EtatCellules {
    pub h_dom: Vec<f64>,
}

// ------------------------------------------------------------------------------------------
// Modèles

/// Les jeux de paramètres lus par le moteur (un `Parametres` par fichier de `params/`, ou le
/// même pour plusieurs).
#[derive(Debug, Clone, Copy)]
pub struct SourcesDeParametres<'a> {
    /// `growth_gam`
    pub croissance: &'a Parametres,
    /// `mortality_gam`
    pub mortalite: &'a Parametres,
    /// `recruitment_gam`
    pub recrutement: &'a Parametres,
    /// `relative_height_gam`, `chapman_richards`, `korf`
    pub courbe_hauteur: &'a Parametres,
    /// `hcb`, `cw` (contrat `parameters`)
    pub allometrie: &'a Parametres,
}

/// Les modèles d'une essence, cherchés une fois.
#[derive(Debug, Clone, PartialEq)]
pub struct ModelesEssence {
    pub espece: String,
    pub packee: u64,
    pub croissance: JeuDeParametres,
    pub mortalite: JeuDeParametres,
    pub hauteur_relative: JeuDeParametres,
    pub courbe: Courbe,
    /// `None` si l'essence n'est pas candidate au recrutement.
    pub recrutement: Option<JeuDeParametres>,
    pub hcb: AllometrieHcb,
    pub cw: AllometrieCw,
    /// Statut provisoire des jeux utilisés : courbe, hcb, cw (les autres sont dans leurs jeux).
    pub courbe_provisoire: bool,
    pub hcb_provisoire: bool,
    pub cw_provisoire: bool,
}

/// Les modèles de toutes les essences du moteur, triées par code.
#[derive(Debug, Clone, PartialEq)]
pub struct Modeles {
    pub essences: Vec<ModelesEssence>,
    /// Rangs (dans `essences`) des essences candidates au recrutement, dans l'ordre des codes.
    pub candidates: Vec<usize>,
    /// Point de départ de nemeton pour les classes de Korf (absent : code 2 dès qu'une cellule a
    /// une courbe de Korf).
    pub reference_korf: Option<ReferenceKorf>,
}

/// La courbe de hauteur d'une essence : à chaque niveau (essence, groupe, `toutes_essences`),
/// `korf` s'il existe, sinon `chapman_richards` ; code 2 si aucun niveau n'en a.
pub fn chercher_courbe<'a>(
    parametres: &'a Parametres,
    espece: &str,
    referentiel: &Referentiel,
) -> Result<&'a JeuDeParametres, Erreur> {
    let groupe = match referentiel.groupe(espece) {
        Some(groupe) => groupe.to_string(),
        None => {
            return Err(Erreur::entree_refusee(format!(
                "essence {espece} absente de contracts/species.csv : pas de groupe, pas de courbe de hauteur"
            )))
        }
    };
    let porteurs = [
        Porteur::Essence(espece.to_string()),
        Porteur::Groupe(groupe),
        Porteur::Groupe(TOUTES_ESSENCES.to_string()),
    ];
    for porteur in &porteurs {
        if let Some(jeu) = parametres.jeu(porteur, "korf") {
            return Ok(jeu);
        }
        if let Some(jeu) = parametres.jeu(porteur, "chapman_richards") {
            return Ok(jeu);
        }
    }
    Err(Erreur::entree_refusee(format!(
        "aucune courbe de hauteur (korf ou chapman_richards) pour l'essence {espece}"
    )))
}

/// Vrai si l'essence a les quatre jeux de paramètres (T6) : croissance, mortalité, recrutement
/// et hauteur (hauteur relative et courbe).
pub fn a_les_quatre_jeux(
    sources: &SourcesDeParametres,
    referentiel: &Referentiel,
    espece: &str,
) -> bool {
    sources
        .croissance
        .chercher("growth_gam", espece, referentiel)
        .is_ok()
        && sources
            .mortalite
            .chercher("mortality_gam", espece, referentiel)
            .is_ok()
        && sources
            .recrutement
            .chercher("recruitment_gam", espece, referentiel)
            .is_ok()
        && sources
            .courbe_hauteur
            .chercher("relative_height_gam", espece, referentiel)
            .is_ok()
        && chercher_courbe(sources.courbe_hauteur, espece, referentiel).is_ok()
}

/// Les essences candidates au recrutement (T6) parmi `essences` : celles qui ont les quatre jeux,
/// triées par code et sans doublon. Le choix de la liste de départ revient à l'appelant.
pub fn essences_candidates(
    sources: &SourcesDeParametres,
    referentiel: &Referentiel,
    essences: &[String],
) -> Vec<String> {
    let mut retenues: Vec<String> = Vec::new();
    for espece in essences {
        if a_les_quatre_jeux(sources, referentiel, espece) && !retenues.contains(espece) {
            retenues.push(espece.clone());
        }
    }
    retenues.sort();
    retenues
}

impl Modeles {
    /// Cherche les modèles des essences de l'état et des candidates au recrutement.
    ///
    /// Code 2 si une essence n'a pas l'un de ses jeux (croissance, mortalité, hauteur relative,
    /// courbe, hcb, cw ; recrutement pour une candidate), si un terme manque, ou si un code
    /// d'essence est hors motif.
    pub fn preparer(
        sources: &SourcesDeParametres,
        referentiel: &Referentiel,
        essences_etat: &[String],
        candidates: &[String],
        reference_korf: Option<ReferenceKorf>,
    ) -> Result<Modeles, Erreur> {
        let mut codes: Vec<String> = Vec::new();
        for espece in essences_etat.iter().chain(candidates.iter()) {
            if !codes.contains(espece) {
                codes.push(espece.clone());
            }
        }
        codes.sort();
        let mut essences: Vec<ModelesEssence> = Vec::with_capacity(codes.len());
        let mut rangs_candidats: Vec<usize> = Vec::new();
        for (rang, espece) in codes.iter().enumerate() {
            let packee = packer_essence(espece)?;
            let (croissance, _) = sources
                .croissance
                .chercher("growth_gam", espece, referentiel)?;
            let (mortalite, _) =
                sources
                    .mortalite
                    .chercher("mortality_gam", espece, referentiel)?;
            let (hauteur_relative, _) =
                sources
                    .courbe_hauteur
                    .chercher("relative_height_gam", espece, referentiel)?;
            let jeu_courbe = chercher_courbe(sources.courbe_hauteur, espece, referentiel)?;
            let courbe = Courbe::depuis_jeu(jeu_courbe).map_err(|e| avec_essence(e, espece))?;
            let (jeu_hcb, _) = sources.allometrie.chercher("hcb", espece, referentiel)?;
            let hcb = AllometrieHcb::depuis_jeu(jeu_hcb).map_err(|e| avec_essence(e, espece))?;
            let (jeu_cw, _) = sources.allometrie.chercher("cw", espece, referentiel)?;
            let cw = AllometrieCw::depuis_jeu(jeu_cw).map_err(|e| avec_essence(e, espece))?;
            let mut recrutement = None;
            if candidates.contains(espece) {
                let (jeu, _) =
                    sources
                        .recrutement
                        .chercher("recruitment_gam", espece, referentiel)?;
                recrutement = Some(jeu.clone());
                rangs_candidats.push(rang);
            }
            essences.push(ModelesEssence {
                espece: espece.clone(),
                packee,
                croissance: croissance.clone(),
                mortalite: mortalite.clone(),
                hauteur_relative: hauteur_relative.clone(),
                courbe,
                recrutement,
                hcb,
                cw,
                courbe_provisoire: jeu_courbe.provisoire,
                hcb_provisoire: jeu_hcb.provisoire,
                cw_provisoire: jeu_cw.provisoire,
            });
        }
        Ok(Modeles {
            essences,
            candidates: rangs_candidats,
            reference_korf,
        })
    }

    /// Le rang d'une essence dans [`Modeles::essences`]. Code 2 si elle n'a pas été préparée.
    pub fn rang(&self, espece: &str) -> Result<usize, Erreur> {
        match self
            .essences
            .binary_search_by(|modele| modele.espece.as_str().cmp(espece))
        {
            Ok(rang) => Ok(rang),
            Err(_) => Err(Erreur::entree_refusee(format!(
                "essence {espece} sans modèles préparés (paramètres non cherchés)"
            ))),
        }
    }

    /// (jeux provisoires, jeux utilisés) sur toutes les essences préparées : croissance,
    /// mortalité, hauteur relative, courbe, hcb, cw et, pour une candidate, recrutement.
    pub fn jeux_provisoires(&self) -> (u64, u64) {
        let mut provisoires = 0;
        let mut total = 0;
        for modele in &self.essences {
            let mut statuts = vec![
                modele.croissance.provisoire,
                modele.mortalite.provisoire,
                modele.hauteur_relative.provisoire,
                modele.courbe_provisoire,
                modele.hcb_provisoire,
                modele.cw_provisoire,
            ];
            if let Some(jeu) = &modele.recrutement {
                statuts.push(jeu.provisoire);
            }
            for statut in statuts {
                total += 1;
                if statut {
                    provisoires += 1;
                }
            }
        }
        (provisoires, total)
    }
}

fn avec_essence(erreur: Erreur, espece: &str) -> Erreur {
    Erreur {
        code: erreur.code,
        message: format!("essence {espece} : {}", erreur.message),
    }
}

fn avec_contexte(erreur: Erreur, annee: i32, entite: &str) -> Erreur {
    Erreur {
        code: erreur.code,
        message: format!("année {annee}, {entite} : {}", erreur.message),
    }
}

// ------------------------------------------------------------------------------------------
// Résultat d'un pas

/// Ce que rend un pas (ou l'initialisation à t0).
#[derive(Debug, Clone, PartialEq)]
pub struct ResultatPas {
    /// L'état à la fin de l'année : morts de l'année (`vivant = false`) compris, recrues ajoutées.
    pub etat: EtatArbres,
    /// hcb (m) de chaque arbre de `etat`.
    pub hcb: Vec<f64>,
    /// cw (m) de chaque arbre de `etat`.
    pub cw: Vec<f64>,
    /// H_dom de chaque cellule à la fin de l'année.
    pub cellules: EtatCellules,
    pub comptes: Comptes,
    /// Dans l'ordre : cellules (ordre des `cell_id`), puis trouées (ordre des `cell_id`), puis
    /// arbres (ordre de l'état).
    pub signalements: Vec<Signalement>,
}

/// Le résumé d'une cellule sur l'état figé.
#[derive(Debug, Clone, PartialEq)]
struct ResumeCellule {
    /// Surface terrière de la cellule, m²/ha.
    ba_totale: f64,
    /// (rang d'essence, surface terrière m²/ha), triés par rang d'essence.
    ba_par_essence: Vec<(usize, f64)>,
    /// Essence de plus forte surface terrière (à égalité, le plus petit code).
    essence_courbe: Option<usize>,
    melee: bool,
    d_dom: Option<f64>,
}

impl ResumeCellule {
    fn ba_de(&self, essence: usize) -> f64 {
        for (rang, ba) in &self.ba_par_essence {
            if *rang == essence {
                return *ba;
            }
        }
        0.0
    }
}

fn resumer_cellule(
    etat: &EtatArbres,
    index: &IndexParCellule,
    essence_de: &[usize],
    cellule: usize,
    aire_ha: f64,
) -> ResumeCellule {
    let arbres = index.arbres_de(cellule);
    let mut ba_par_essence: Vec<(usize, f64)> = Vec::new();
    let mut ba_totale = 0.0;
    let mut diametres: Vec<f64> = Vec::with_capacity(arbres.len());
    for rang in arbres {
        let g = concurrence::surface_terriere_m2(etat.d130[*rang]) / aire_ha;
        ba_totale += g;
        diametres.push(etat.d130[*rang]);
        let essence = essence_de[*rang];
        let mut trouve = false;
        for paire in ba_par_essence.iter_mut() {
            if paire.0 == essence {
                paire.1 += g;
                trouve = true;
                break;
            }
        }
        if !trouve {
            ba_par_essence.push((essence, g));
        }
    }
    ba_par_essence.sort_by(|a, b| a.0.cmp(&b.0));
    let mut essence_courbe = None;
    let mut ba_max = f64::NEG_INFINITY;
    for (essence, ba) in &ba_par_essence {
        if *ba > ba_max {
            ba_max = *ba;
            essence_courbe = Some(*essence);
        }
    }
    ResumeCellule {
        ba_totale,
        melee: ba_par_essence.len() > 1,
        ba_par_essence,
        essence_courbe,
        d_dom: hauteur::diametre_dominant(&diametres, aire_ha),
    }
}

/// Le rang d'essence de chaque arbre de l'état (code 2 si une essence n'a pas été préparée).
fn essences_des_arbres(etat: &EtatArbres, modeles: &Modeles) -> Result<Vec<usize>, Erreur> {
    let resultats: Vec<Result<usize, Erreur>> = etat
        .espece
        .par_iter()
        .map(|espece| modeles.rang(espece))
        .collect();
    let mut rangs = Vec::with_capacity(resultats.len());
    for resultat in resultats {
        rangs.push(resultat?);
    }
    Ok(rangs)
}

fn resumer_cellules(
    etat: &EtatArbres,
    index: &IndexParCellule,
    essence_de: &[usize],
    geometrie: &GeometrieGrille,
) -> Vec<ResumeCellule> {
    let aire_ha = geometrie.aire_cellule_ha();
    (0..geometrie.nombre_cellules())
        .into_par_iter()
        .map(|cellule| resumer_cellule(etat, index, essence_de, cellule, aire_ha))
        .collect()
}

/// L'avance de H_dom de chaque cellule qui a des arbres (`None` sinon), sur `duree` années ou,
/// à l'état initial, de sa date de vol à t0 (`t0` renseigné).
fn avancer_cellules(
    cellules: &Cellules,
    h_dom: &[f64],
    resumes: &[ResumeCellule],
    modeles: &Modeles,
    annee: i32,
    t0: Option<i32>,
) -> Result<Vec<Option<AvanceeHdom>>, Erreur> {
    let resultats: Vec<Result<Option<AvanceeHdom>, Erreur>> = (0..resumes.len())
        .into_par_iter()
        .map(|cellule| {
            let essence = match resumes[cellule].essence_courbe {
                Some(essence) => essence,
                None => return Ok(None),
            };
            let modele = &modeles.essences[essence];
            let entite = format!("cellule {cellule} (courbe de l'essence {})", modele.espece);
            let duree = match t0 {
                Some(t0) => hauteur::annees_de_vol_a_t0(cellules.chm_date[cellule], t0)
                    .map_err(|e| avec_contexte(e, annee, &entite))?,
                None => 1.0,
            };
            let plafond = cellules
                .plafond(cellule, &modele.espece)
                .map_err(|e| avec_contexte(e, annee, &entite))?;
            let avancee = hauteur::avancer_hdom(
                &modele.courbe,
                h_dom[cellule],
                plafond,
                modeles.reference_korf.as_ref(),
                duree,
            )
            .map_err(|e| avec_contexte(e, annee, &entite))?;
            Ok(Some(avancee))
        })
        .collect();
    let mut avancees = Vec::with_capacity(resultats.len());
    for resultat in resultats {
        avancees.push(resultat?);
    }
    Ok(avancees)
}

/// Compte et signale ce que l'avance de H_dom a constaté, dans l'ordre des cellules.
#[allow(clippy::too_many_arguments)]
fn bilan_cellules(
    cellules: &Cellules,
    h_dom_depart: &[f64],
    resumes: &[ResumeCellule],
    avancees: &[Option<AvanceeHdom>],
    modeles: &Modeles,
    annee: i32,
    initialisation: bool,
    comptes: &mut Comptes,
    signalements: &mut Vec<Signalement>,
) {
    for cellule in 0..avancees.len() {
        if resumes[cellule].melee {
            comptes.cellules_melees += 1;
        }
        let avancee = match &avancees[cellule] {
            Some(avancee) => avancee,
            None => {
                if cellules.simulee[cellule] {
                    comptes.cellules_sans_arbre += 1;
                }
                continue;
            }
        };
        let entite = cellule.to_string();
        if avancee.au_plafond {
            comptes.cellules_au_plafond += 1;
        }
        if avancee.au_dessus {
            comptes.cellules_au_dessus_du_plafond += 1;
            signalements.push(Signalement {
                annee,
                entite: entite.clone(),
                sorte: controles::SORTE_HDOM_AU_DESSUS_DU_PLAFOND.to_string(),
                message: format!(
                    "hauteur dominante {:.2} m au-dessus du plafond de la station (site_potential), non corrigée",
                    h_dom_depart[cellule]
                ),
                valeur: Some(h_dom_depart[cellule]),
            });
        }
        if avancee.au_dela_asymptote {
            comptes.cellules_asymptote_korf += 1;
            signalements.push(Signalement {
                annee,
                entite: entite.clone(),
                sorte: controles::SORTE_HDOM_ASYMPTOTE_KORF.to_string(),
                message: format!(
                    "hauteur dominante {:.2} m à l'asymptote de la courbe de Korf ou au-delà : elle n'avance plus",
                    h_dom_depart[cellule]
                ),
                valeur: Some(h_dom_depart[cellule]),
            });
        }
        if initialisation {
            if let Some(classe) = avancee.classe_korf {
                let espece = match resumes[cellule].essence_courbe {
                    Some(essence) => modeles.essences[essence].espece.clone(),
                    None => String::new(),
                };
                signalements.push(Signalement {
                    annee,
                    entite,
                    sorte: controles::SORTE_CLASSE_KORF.to_string(),
                    message: format!(
                        "courbe de Korf de l'essence {espece} : classe de fertilité {classe}, celle dont la hauteur \
                         à l'âge de référence de nemeton est la plus proche du plafond (règle provisoire)"
                    ),
                    valeur: Some(classe as f64),
                });
            }
        }
    }
}

/// La part f(rel_d) d'un arbre de diamètre `d130` dans une cellule de diamètre dominant `d_dom`.
fn part_hauteur(
    modele: &ModelesEssence,
    d130: f64,
    d_dom: f64,
    ser_code: &str,
    sorties: &mut SortiesParSens,
) -> Result<f64, Erreur> {
    let covariables = Covariables {
        d130: Some(d130),
        rel_d: Some(d130 / d_dom),
        ..Covariables::default()
    };
    accroissement::predicteur(&modele.hauteur_relative, &covariables, ser_code, sorties)
}

/// Ce que le pas calcule pour un arbre.
#[derive(Debug, Clone, Copy, PartialEq)]
struct ResultatArbre {
    d130: f64,
    h: f64,
    mort: bool,
    part: f64,
    dh_mis_a_zero: bool,
    sorties: SortiesParSens,
}

#[allow(clippy::too_many_arguments)]
fn simuler_arbre(
    etat: &EtatArbres,
    rang: usize,
    essence: usize,
    concurrence: &Concurrence,
    cellules: &Cellules,
    resumes: &[ResumeCellule],
    avancees: &[Option<AvanceeHdom>],
    modeles: &Modeles,
    graine: u64,
    annee: i32,
) -> Result<ResultatArbre, Erreur> {
    let modele = &modeles.essences[essence];
    let cellule = etat.cellule[rang] as usize;
    let ser = cellules.ser_code[cellule].as_str();
    let d130 = etat.d130[rang];
    let mut sorties = SortiesParSens::default();
    let covariables = accroissement::covariables_arbre(
        d130,
        concurrence.ba_plot,
        concurrence.bal,
        cellules.trophic[cellule],
        cellules.hydric[cellule],
        cellules.bioclim[cellule],
    );
    let accroissement =
        accroissement::accroissement_diametre(&modele.croissance, &covariables, ser, &mut sorties)?;
    let eta_mort = accroissement::predicteur(&modele.mortalite, &covariables, ser, &mut sorties)?;
    let probabilite = mortalite::probabilite_annuelle(eta_mort);
    let mort = mortalite::meurt(graine, annee, etat.numero[rang], modele.packee, probabilite);
    let d_dom = match resumes[cellule].d_dom {
        Some(d_dom) => d_dom,
        None => {
            return Err(Erreur::interne(format!(
                "cellule {cellule} sans diamètre dominant alors qu'elle a un arbre"
            )))
        }
    };
    let delta = match &avancees[cellule] {
        Some(avancee) => avancee.delta,
        None => {
            return Err(Erreur::interne(format!(
                "cellule {cellule} sans avance de H_dom alors qu'elle a un arbre"
            )))
        }
    };
    let part = part_hauteur(modele, d130, d_dom, ser, &mut sorties)?;
    let (dh, dh_mis_a_zero) = hauteur::hausse_arbre(part, delta);
    if mort {
        return Ok(ResultatArbre {
            d130,
            h: etat.h[rang],
            mort,
            part,
            dh_mis_a_zero,
            sorties,
        });
    }
    Ok(ResultatArbre {
        d130: d130 + accroissement,
        h: etat.h[rang] + dh,
        mort,
        part,
        dh_mis_a_zero,
        sorties,
    })
}

/// hcb et cw de chaque arbre de l'état (en parallèle, sans somme).
pub fn houppiers(etat: &EtatArbres, modeles: &Modeles) -> Result<(Vec<f64>, Vec<f64>), Erreur> {
    let essence_de = essences_des_arbres(etat, modeles)?;
    let paires: Vec<(f64, f64)> = (0..etat.len())
        .into_par_iter()
        .map(|rang| {
            let modele = &modeles.essences[essence_de[rang]];
            (
                modele.hcb.hcb(etat.h[rang], etat.d130[rang]),
                modele.cw.cw(etat.d130[rang]),
            )
        })
        .collect();
    let mut hcb = Vec::with_capacity(paires.len());
    let mut cw = Vec::with_capacity(paires.len());
    for (une_hcb, une_cw) in paires {
        hcb.push(une_hcb);
        cw.push(une_cw);
    }
    Ok((hcb, cw))
}

/// Vérifie l'état de début d'année : invariants (code 1), aucun mort (code 1), et les contrôles
/// de x, y, d130 et h (code 3) avant tout calcul, pour qu'un NaN ne se propage jamais.
fn verifier_etat_fige(etat: &EtatArbres, annee: i32) -> Result<(), Erreur> {
    etat.verifier()?;
    for rang in 0..etat.len() {
        if !etat.vivant[rang] {
            return Err(Erreur::interne(format!(
                "arbre {} mort dans l'état de début d'année (les morts doivent être retirés)",
                etat.tree_id[rang]
            )));
        }
        let entite = format!("arbre {} (état de début d'année)", etat.tree_id[rang]);
        controles::controler_valeur(annee, &entite, "x", etat.x[rang], Positivite::Aucune)?;
        controles::controler_valeur(annee, &entite, "y", etat.y[rang], Positivite::Aucune)?;
        controles::controler_valeur(annee, &entite, "d130", etat.d130[rang], Positivite::Stricte)?;
        controles::controler_valeur(annee, &entite, "h", etat.h[rang], Positivite::Stricte)?;
    }
    Ok(())
}

// ------------------------------------------------------------------------------------------
// État initial à t0

/// Avance l'état initial de la date de vol jusqu'à la fin de l'année t0 (décision de Pascal, Q2) :
/// H_dom de chaque cellule à arbres part de `h0` et avance de la durée de vol à t0 sur sa courbe ;
/// chaque arbre garde sa hauteur du MNH comme ancre et gagne f(rel_d) × ΔH_dom. Les cellules sans
/// arbre gardent `h0`. Rend l'état à t0 (à écrire sous `year=t0`), ses houppiers, les H_dom, les
/// comptes et les signalements de l'année t0 ; les contrôles sont faits (code 3).
pub fn initialiser_t0(
    etat: &EtatArbres,
    cellules: &Cellules,
    modeles: &Modeles,
    t0: i32,
) -> Result<ResultatPas, Erreur> {
    cellules.verifier()?;
    verifier_etat_fige(etat, t0)?;
    let geometrie = &cellules.geometrie;
    let index = concurrence::indexer(etat, geometrie)?;
    let essence_de = essences_des_arbres(etat, modeles)?;
    let resumes = resumer_cellules(etat, &index, &essence_de, geometrie);
    let avancees = avancer_cellules(cellules, &cellules.h0, &resumes, modeles, t0, Some(t0))?;
    let mut comptes = Comptes::default();
    let mut signalements: Vec<Signalement> = Vec::new();
    bilan_cellules(
        cellules,
        &cellules.h0,
        &resumes,
        &avancees,
        modeles,
        t0,
        true,
        &mut comptes,
        &mut signalements,
    );
    let mut h_dom = cellules.h0.clone();
    for cellule in 0..avancees.len() {
        if let Some(avancee) = &avancees[cellule] {
            h_dom[cellule] = avancee.h;
        }
    }
    let resultats: Vec<Result<(f64, f64, bool, SortiesParSens), Erreur>> = (0..etat.len())
        .into_par_iter()
        .map(|rang| {
            let modele = &modeles.essences[essence_de[rang]];
            let cellule = etat.cellule[rang] as usize;
            let mut sorties = SortiesParSens::default();
            let d_dom = match resumes[cellule].d_dom {
                Some(d_dom) => d_dom,
                None => return Err(Erreur::interne(format!("cellule {cellule} sans d_dom"))),
            };
            let delta = match &avancees[cellule] {
                Some(avancee) => avancee.delta,
                None => return Err(Erreur::interne(format!("cellule {cellule} sans avance"))),
            };
            let part = part_hauteur(
                modele,
                etat.d130[rang],
                d_dom,
                &cellules.ser_code[cellule],
                &mut sorties,
            )
            .map_err(|e| avec_contexte(e, t0, &format!("arbre {}", etat.tree_id[rang])))?;
            let (dh, mis_a_zero) = hauteur::hausse_arbre(part, delta);
            Ok((etat.h[rang] + dh, part, mis_a_zero, sorties))
        })
        .collect();
    let mut nouvel = etat.clone();
    for (rang, resultat) in resultats.into_iter().enumerate() {
        let (h, part, mis_a_zero, sorties) = resultat?;
        nouvel.h[rang] = h;
        comptes.sorties_domaine.ajouter(&sorties);
        if mis_a_zero {
            comptes.dh_arbre_mis_a_zero += 1;
            signalements.push(signalement_dh(t0, &etat.tree_id[rang], part));
        }
    }
    let (hcb, cw) = houppiers(&nouvel, modeles)?;
    controles::controler_arbres(t0, &nouvel, &hcb, &cw)?;
    Ok(ResultatPas {
        etat: nouvel,
        hcb,
        cw,
        cellules: EtatCellules { h_dom },
        comptes,
        signalements,
    })
}

fn signalement_dh(annee: i32, tree_id: &str, part: f64) -> Signalement {
    Signalement {
        annee,
        entite: tree_id.to_string(),
        sorte: controles::SORTE_DH_ARBRE_MIS_A_ZERO.to_string(),
        message: format!(
            "part de la croissance de la hauteur dominante négative (f(rel_d) = {part:.4}) : hausse de hauteur mise à 0"
        ),
        valeur: Some(part),
    }
}

// ------------------------------------------------------------------------------------------
// Le pas annuel

/// Les trouées de l'année : cellules simulées dont la H_dom de fin d'année est nulle. Aucune recrue
/// n'y est ajoutée (décision de Pascal du 25/11/2026) ; chacune est comptée et signalée, dans
/// l'ordre des `cell_id`. Une H_dom négative n'est pas une trouée : elle reste aux contrôles.
fn reperer_trouees(
    cellules: &Cellules,
    h_dom_fin: &[f64],
    annee: i32,
    comptes: &mut Comptes,
    signalements: &mut Vec<Signalement>,
) -> Vec<bool> {
    let mut trouees = vec![false; h_dom_fin.len()];
    for cellule in 0..h_dom_fin.len() {
        if !cellules.simulee[cellule] || h_dom_fin[cellule] != 0.0 {
            continue;
        }
        trouees[cellule] = true;
        comptes.cellules_trouee_sans_recrue += 1;
        signalements.push(Signalement {
            annee,
            entite: cellule.to_string(),
            sorte: controles::SORTE_TROUEE_SANS_RECRUE.to_string(),
            message: "hauteur dominante nulle (trouée) : aucune recrue ajoutée cette année ; la \
                      recolonisation des trouées viendra en M5 par les cohortes de semis"
                .to_string(),
            valeur: Some(h_dom_fin[cellule]),
        });
    }
    trouees
}

/// Le nombre de recrues de chaque essence candidate dans une cellule, et les sorties de domaine.
fn compter_recrues(
    cellules: &Cellules,
    resume: &ResumeCellule,
    modeles: &Modeles,
    cellule: usize,
    graine: u64,
    annee: i32,
) -> Result<(Vec<(usize, u64)>, SortiesParSens), Erreur> {
    let mut sorties = SortiesParSens::default();
    let mut nombres: Vec<(usize, u64)> = Vec::new();
    if !cellules.simulee[cellule] {
        return Ok((nombres, sorties));
    }
    let aire_ha = cellules.geometrie.aire_cellule_ha();
    for essence in &modeles.candidates {
        let modele = &modeles.essences[*essence];
        let jeu = match &modele.recrutement {
            Some(jeu) => jeu,
            None => {
                return Err(Erreur::interne(format!(
                    "essence candidate {} sans jeu de recrutement",
                    modele.espece
                )))
            }
        };
        let covariables = Covariables {
            ba_plot: Some(resume.ba_totale),
            ba_species: Some(resume.ba_de(*essence)),
            trophic: Some(cellules.trophic[cellule]),
            coarse_hydric_700m: Some(cellules.hydric[cellule]),
            coarse_bioclim_700m: Some(cellules.bioclim[cellule]),
            ..Covariables::default()
        };
        let entite = format!("cellule {cellule}, essence {}", modele.espece);
        let eta =
            accroissement::predicteur(jeu, &covariables, &cellules.ser_code[cellule], &mut sorties)
                .map_err(|e| avec_contexte(e, annee, &entite))?;
        let lambda = recrutement::esperance(eta, aire_ha);
        let n = recrutement::nombre_de_recrues(
            graine,
            annee,
            cellule as u64,
            &modele.espece,
            modele.packee,
            lambda,
        )?;
        if n > 0 {
            nombres.push((*essence, n));
        }
    }
    Ok((nombres, sorties))
}

/// Les recrues d'une cellule, numérotées à partir de `premier`.
#[allow(clippy::too_many_arguments)]
fn creer_recrues(
    cellules: &Cellules,
    resume: &ResumeCellule,
    h_dom_fin: f64,
    modeles: &Modeles,
    cellule: usize,
    nombres: &[(usize, u64)],
    premier: u64,
    graine: u64,
    annee: i32,
) -> Result<(Vec<(u64, usize, ArbreNouveau)>, SortiesParSens, u64), Erreur> {
    let mut sorties = SortiesParSens::default();
    let mut recrues: Vec<(u64, usize, ArbreNouveau)> = Vec::new();
    let mut en_cellule_vide = 0;
    let (x_ouest, _, _, y_nord) = cellules.geometrie.bornes(cellule as u64);
    let cote = cellules.geometrie.pas;
    let d130 = recrutement::d130_recrue_cm();
    // Sans arbre, les recrues sont leurs propres dominantes : d_dom = 7,48 cm, rel_d = 1.
    let d_dom = match resume.d_dom {
        Some(d_dom) => d_dom,
        None => d130,
    };
    let mut rang_dans_cellule: u64 = 0;
    for (essence, n) in nombres {
        let modele = &modeles.essences[*essence];
        let entite = format!("recrues de la cellule {cellule}, essence {}", modele.espece);
        let part = part_hauteur(
            modele,
            d130,
            d_dom,
            &cellules.ser_code[cellule],
            &mut sorties,
        )
        .map_err(|e| avec_contexte(e, annee, &entite))?;
        for _ in 0..*n {
            let numero = premier + rang_dans_cellule;
            let (x, y) =
                recrutement::position(graine, annee, numero, modele.packee, x_ouest, y_nord, cote);
            recrues.push((
                numero,
                *essence,
                ArbreNouveau {
                    tree_id: recrutement::tree_id_recrue(cellule as u64, annee, rang_dans_cellule),
                    espece: modele.espece.clone(),
                    cellule: cellule as u64,
                    x,
                    y,
                    d130,
                    h: h_dom_fin * part,
                },
            ));
            if resume.d_dom.is_none() {
                en_cellule_vide += 1;
            }
            rang_dans_cellule += 1;
        }
    }
    Ok((recrues, sorties, en_cellule_vide))
}

/// Ce que les étapes 1 à 4 du pas laissent aux étapes suivantes.
struct DebutDuPas {
    index: IndexParCellule,
    essence_de: Vec<usize>,
    resumes: Vec<ResumeCellule>,
    h_dom_fin: Vec<f64>,
    nouvel: EtatArbres,
    comptes: Comptes,
    signalements: Vec<Signalement>,
    signalements_arbres: Vec<Signalement>,
}

/// Étapes 1 à 4 du pas (concurrence, résumé, H_dom, arbres), communes aux deux modes de
/// recrutement.
fn debut_du_pas(
    etat: &EtatArbres,
    cellules: &Cellules,
    hdom: &EtatCellules,
    modeles: &Modeles,
    graine: u64,
    annee: i32,
) -> Result<DebutDuPas, Erreur> {
    cellules.verifier()?;
    verifier_etat_fige(etat, annee)?;
    let geometrie = &cellules.geometrie;
    if hdom.h_dom.len() != geometrie.nombre_cellules() {
        return Err(Erreur::interne(format!(
            "{} H_dom pour {} cellules",
            hdom.h_dom.len(),
            geometrie.nombre_cellules()
        )));
    }

    // 1. Concurrence et 2. résumé des cellules, sur l'état figé.
    let index = concurrence::indexer(etat, geometrie)?;
    let essence_de = essences_des_arbres(etat, modeles)?;
    let concurrences = concurrence::calculer(etat, geometrie, &index);
    let resumes = resumer_cellules(etat, &index, &essence_de, geometrie);

    // 3. H_dom avancée d'un an.
    let avancees = avancer_cellules(cellules, &hdom.h_dom, &resumes, modeles, annee, None)?;
    let mut comptes = Comptes::default();
    let mut signalements: Vec<Signalement> = Vec::new();
    bilan_cellules(
        cellules,
        &hdom.h_dom,
        &resumes,
        &avancees,
        modeles,
        annee,
        false,
        &mut comptes,
        &mut signalements,
    );
    let mut h_dom_fin = hdom.h_dom.clone();
    for cellule in 0..avancees.len() {
        if let Some(avancee) = &avancees[cellule] {
            h_dom_fin[cellule] = avancee.h;
        }
    }

    // 4. Arbres : accroissement, hauteur, mort.
    let resultats: Vec<Result<ResultatArbre, Erreur>> = (0..etat.len())
        .into_par_iter()
        .map(|rang| {
            simuler_arbre(
                etat,
                rang,
                essence_de[rang],
                &concurrences[rang],
                cellules,
                &resumes,
                &avancees,
                modeles,
                graine,
                annee,
            )
            .map_err(|e| avec_contexte(e, annee, &format!("arbre {}", etat.tree_id[rang])))
        })
        .collect();
    let mut nouvel = etat.clone();
    let mut signalements_arbres: Vec<Signalement> = Vec::new();
    for (rang, resultat) in resultats.into_iter().enumerate() {
        let arbre = resultat?;
        nouvel.d130[rang] = arbre.d130;
        nouvel.h[rang] = arbre.h;
        nouvel.vivant[rang] = !arbre.mort;
        comptes.sorties_domaine.ajouter(&arbre.sorties);
        if concurrences[rang].au_bord {
            comptes.disques_au_bord += 1;
        }
        if arbre.mort {
            comptes.morts += 1;
        }
        if arbre.dh_mis_a_zero {
            comptes.dh_arbre_mis_a_zero += 1;
            signalements_arbres.push(signalement_dh(annee, &etat.tree_id[rang], arbre.part));
        }
    }
    Ok(DebutDuPas {
        index,
        essence_de,
        resumes,
        h_dom_fin,
        nouvel,
        comptes,
        signalements,
        signalements_arbres,
    })
}

/// Étapes 5 (création et ajout des recrues, une fois leurs nombres connus), 6 et 7 du pas,
/// communes aux deux modes.
#[allow(clippy::too_many_arguments)]
fn fin_du_pas(
    etat: &EtatArbres,
    cellules: &Cellules,
    modeles: &Modeles,
    graine: u64,
    annee: i32,
    debut: DebutDuPas,
    nombres_par_cellule: Vec<Vec<(usize, u64)>>,
    totaux: Vec<u64>,
) -> Result<ResultatPas, Erreur> {
    let DebutDuPas {
        resumes,
        h_dom_fin,
        mut nouvel,
        mut comptes,
        mut signalements,
        signalements_arbres,
        ..
    } = debut;
    let (premiers, _) = premiers_numeros(etat.prochain_numero(), &totaux)?;
    let recrues: Vec<Result<(Vec<(u64, usize, ArbreNouveau)>, SortiesParSens, u64), Erreur>> = (0
        ..resumes.len())
        .into_par_iter()
        .map(|cellule| {
            if nombres_par_cellule[cellule].is_empty() {
                return Ok((Vec::new(), SortiesParSens::default(), 0));
            }
            creer_recrues(
                cellules,
                &resumes[cellule],
                h_dom_fin[cellule],
                modeles,
                cellule,
                &nombres_par_cellule[cellule],
                premiers[cellule],
                graine,
                annee,
            )
        })
        .collect();
    let mut total_recrues: usize = 0;
    for total in &totaux {
        total_recrues += *total as usize;
    }
    nouvel.reserver(total_recrues)?;
    for resultat in recrues {
        let (liste, sorties, en_cellule_vide) = resultat?;
        comptes.sorties_domaine.ajouter(&sorties);
        comptes.recrues_cellule_vide += en_cellule_vide;
        for (numero, _essence, arbre) in liste {
            nouvel.ajouter(numero, arbre)?;
            comptes.recrues += 1;
        }
    }

    // 6. Houppiers et 7. contrôles.
    let (hcb, cw) = houppiers(&nouvel, modeles)?;
    controles::controler_arbres(annee, &nouvel, &hcb, &cw)?;
    signalements.extend(signalements_arbres);
    Ok(ResultatPas {
        etat: nouvel,
        hcb,
        cw,
        cellules: EtatCellules { h_dom: h_dom_fin },
        comptes,
        signalements,
    })
}

/// Le pas de l'année `annee`, sur l'état figé au 1er janvier (`etat`, tous vivants) et les H_dom
/// de début d'année, en mode `ifn_direct` (recrutement de M3a). Voir la documentation du module
/// pour l'ordre des étapes.
///
/// Codes : 1 si un invariant est rompu (mort dans l'état figé, arbre hors grille) ; 2 si une
/// entrée manque (plafond, essence sans modèles, Korf sans point de départ) ; 3 si un contrôle
/// échoue ; 4 si la mémoire manque.
pub fn pas_annuel(
    etat: &EtatArbres,
    cellules: &Cellules,
    hdom: &EtatCellules,
    modeles: &Modeles,
    graine: u64,
    annee: i32,
) -> Result<ResultatPas, Erreur> {
    let mut debut = debut_du_pas(etat, cellules, hdom, modeles, graine, annee)?;

    // 5. Recrutement : trouées écartées (en ordre fixe), comptes par cellule (en parallèle),
    // numéros (somme séquentielle), recrues (en parallèle), ajout en ordre fixe.
    let trouees = reperer_trouees(
        cellules,
        &debut.h_dom_fin,
        annee,
        &mut debut.comptes,
        &mut debut.signalements,
    );
    let resumes = &debut.resumes;
    let nombres: Vec<Result<(Vec<(usize, u64)>, SortiesParSens), Erreur>> = (0..resumes.len())
        .into_par_iter()
        .map(|cellule| {
            if trouees[cellule] {
                return Ok((Vec::new(), SortiesParSens::default()));
            }
            compter_recrues(cellules, &resumes[cellule], modeles, cellule, graine, annee)
        })
        .collect();
    let mut nombres_par_cellule: Vec<Vec<(usize, u64)>> = Vec::with_capacity(nombres.len());
    let mut totaux: Vec<u64> = Vec::with_capacity(nombres.len());
    for resultat in nombres {
        let (liste, sorties) = resultat?;
        debut.comptes.sorties_domaine.ajouter(&sorties);
        let mut total = 0;
        for (_, n) in &liste {
            total += *n;
        }
        totaux.push(total);
        nombres_par_cellule.push(liste);
    }
    fin_du_pas(etat, cellules, modeles, graine, annee, debut, nombres_par_cellule, totaux)
}

// ------------------------------------------------------------------------------------------
// Mode `cohorts` : régénération par cohortes de semis (M5a, mission 062)

/// Ce que le pas en mode `cohorts` lit, préparé une fois par exécution : les paramètres de semis
/// et le spectre du noyau de chaque essence candidate (ordre de [`Modeles::candidates`]), les
/// plans de FFT et le seuil de la règle |Q|.
#[derive(Debug, Clone)]
pub struct Regeneration {
    pub parametres: Vec<ParametresSemis>,
    pub spectres: Vec<SpectreNoyau>,
    pub noyaux: Vec<Noyau>,
    pub plan: PlanDispersion,
    pub seuil_zero: f64,
}

impl Regeneration {
    /// Cherche les paramètres de semis de chaque essence candidate et prépare les noyaux.
    ///
    /// Code 2 si une essence candidate n'a pas l'un des termes du contrat (aucun emprunt), si un
    /// terme sort de son domaine, ou si un noyau ne peut être normalisé.
    pub fn preparer(
        modeles: &Modeles,
        lignes: &[LigneRegeneration],
        referentiel: &Referentiel,
        reglages: &ReglagesRegeneration,
        geometrie: &GeometrieGrille,
    ) -> Result<Regeneration, Erreur> {
        let plan = PlanDispersion::nouveau(geometrie.largeur, geometrie.hauteur, reglages.demi_largeur_noyau)?;
        let mut parametres = Vec::with_capacity(modeles.candidates.len());
        let mut spectres = Vec::with_capacity(modeles.candidates.len());
        let mut noyaux = Vec::with_capacity(modeles.candidates.len());
        for rang in &modeles.candidates {
            let espece = &modeles.essences[*rang].espece;
            let p = semis::parametres_de(lignes, espece, referentiel)?;
            dispersion::verifier_portee(
                espece,
                p.echelle_noyau_m,
                p.forme_noyau,
                geometrie.pas,
                reglages.demi_largeur_noyau,
            )?;
            let noyau = dispersion::noyau_exponentiel_puissance(
                p.echelle_noyau_m,
                p.forme_noyau,
                geometrie.pas,
                reglages.demi_largeur_noyau,
            )
            .map_err(|e| avec_essence(e, espece))?;
            spectres.push(plan.spectre(&noyau)?);
            noyaux.push(noyau);
            parametres.push(p);
        }
        Ok(Regeneration {
            parametres,
            spectres,
            noyaux,
            plan,
            seuil_zero: reglages.seuil_zero,
        })
    }

    /// (termes provisoires, essences) : une essence compte pour un jeu, provisoire si l'un de ses
    /// termes l'est.
    pub fn jeux_provisoires(&self) -> (u64, u64) {
        let mut provisoires = 0;
        for p in &self.parametres {
            if p.provisoire {
                provisoires += 1;
            }
        }
        (provisoires, self.parametres.len() as u64)
    }
}

/// L'état des semis : pour chaque essence candidate (ordre de [`Modeles::candidates`]), ses A
/// classes annuelles dans chaque cellule, rangées `densites[essence][cellule × A + k]`, en
/// semis/ha ([`crate::semis`]).
#[derive(Debug, Clone, PartialEq)]
pub struct EtatSemis {
    pub classes: Vec<usize>,
    pub densites: Vec<Vec<f64>>,
}

impl EtatSemis {
    /// Les classes d'une essence (rang parmi les candidates) dans une cellule.
    pub fn de(&self, candidate: usize, cellule: usize) -> &[f64] {
        let a = self.classes[candidate];
        &self.densites[candidate][cellule * a..(cellule + 1) * a]
    }

    /// Octets occupés (estimation de mémoire).
    pub fn octets(&self) -> u64 {
        let mut total: u64 = 0;
        for densites in &self.densites {
            total += densites.len() as u64 * 8;
        }
        total
    }
}

/// Le flux IFN d'une essence candidate dans une cellule, en tiges/ha/an : exp(η) du modèle
/// `recruitment_gam`, avec les covariables du résumé de la cellule (comme [`compter_recrues`]).
fn flux_ifn_ha(
    cellules: &Cellules,
    resume: &ResumeCellule,
    modele: &ModelesEssence,
    essence: usize,
    cellule: usize,
    annee: i32,
    sorties: &mut SortiesParSens,
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
    let covariables = Covariables {
        ba_plot: Some(resume.ba_totale),
        ba_species: Some(resume.ba_de(essence)),
        trophic: Some(cellules.trophic[cellule]),
        coarse_hydric_700m: Some(cellules.hydric[cellule]),
        coarse_bioclim_700m: Some(cellules.bioclim[cellule]),
        ..Covariables::default()
    };
    let entite = format!("cellule {cellule}, essence {}", modele.espece);
    let eta = accroissement::predicteur(jeu, &covariables, &cellules.ser_code[cellule], sorties)
        .map_err(|e| avec_contexte(e, annee, &entite))?;
    Ok(eta.exp())
}

/// Le stock de semis initial « en régime » (Q2) : dans chaque cellule simulée à H_dom non nulle,
/// l'état stationnaire du flux IFN de t0 (covariables de l'état à t0), porté au nombre entier
/// d'arbres que l'arrondi aléatoire peut demander (⌈λ⌉ / aire), à la survie de la cellule (ombre de
/// l'état à t0, celle-là même que lira le premier pas), par
/// [`semis::en_regime_avec_survie`] ; rien en trouée ni hors de la grille. Rend aussi les sorties de
/// domaine de ces prédicteurs.
pub fn etat_semis_initial(
    t0: &ResultatPas,
    cellules: &Cellules,
    modeles: &Modeles,
    regeneration: &Regeneration,
    annee_t0: i32,
) -> Result<(EtatSemis, SortiesParSens), Erreur> {
    let geometrie = &cellules.geometrie;
    let n = geometrie.nombre_cellules();
    let aire_ha = geometrie.aire_cellule_ha();
    let index = concurrence::indexer(&t0.etat, geometrie)?;
    let essence_de = essences_des_arbres(&t0.etat, modeles)?;
    let resumes = resumer_cellules(&t0.etat, &index, &essence_de, geometrie);
    let couvert = indice_de_couvert(&t0.etat, &index, &t0.cw, geometrie);
    let mut classes = Vec::with_capacity(modeles.candidates.len());
    let mut densites = Vec::with_capacity(modeles.candidates.len());
    let mut sorties_totales = SortiesParSens::default();
    for (rang_candidat, essence) in modeles.candidates.iter().enumerate() {
        let p = &regeneration.parametres[rang_candidat];
        let a = p.classes();
        let modele = &modeles.essences[*essence];
        let mut valeurs = memoire::reserver_f64(n * a, "classes de semis")?;
        valeurs.resize(n * a, 0.0);
        let resultats: Vec<Result<SortiesParSens, Erreur>> = valeurs
            .par_chunks_mut(a)
            .enumerate()
            .map(|(cellule, classes_cellule)| {
                let mut sorties = SortiesParSens::default();
                if !cellules.simulee[cellule] || t0.cellules.h_dom[cellule] == 0.0 {
                    return Ok(sorties);
                }
                let flux = flux_ifn_ha(cellules, &resumes[cellule], modele, *essence, cellule, annee_t0, &mut sorties)?;
                let survie = semis::survie(p, semis::ombre(p.coef_extinction, couvert[cellule]));
                // Au massif, l'arrondi aléatoire peut demander ⌈λ⌉ arbres (λ = F × aire) : le régime
                // est celui de ce flux en arbres entiers, sinon le stock initial bornerait le tirage
                // dès la première année là où λ n'est pas entier (la part en plus attend au stock).
                let flux_regime = (flux * aire_ha).ceil() / aire_ha;
                semis::en_regime_avec_survie(p, flux_regime, survie, classes_cellule);
                Ok(sorties)
            })
            .collect();
        for resultat in resultats {
            sorties_totales.ajouter(&resultat?);
        }
        classes.push(a);
        densites.push(valeurs);
    }
    Ok((EtatSemis { classes, densites }, sorties_totales))
}

/// Les graines produites dans chaque cellule par les semenciers d'une essence (arbres vivants de
/// l'état, de hauteur ≥ `maturity_height_m`) : fécondité × surface terrière semencière (m²),
/// sommée dans l'ordre de l'état.
fn graines_produites(
    etat: &EtatArbres,
    index: &IndexParCellule,
    essence_de: &[usize],
    essence: usize,
    parametres: &ParametresSemis,
    nombre_cellules: usize,
) -> Vec<f64> {
    (0..nombre_cellules)
        .into_par_iter()
        .map(|cellule| {
            let mut surface = 0.0;
            for rang in index.arbres_de(cellule) {
                if essence_de[*rang] == essence
                    && etat.vivant[*rang]
                    && etat.h[*rang] >= parametres.hauteur_maturite_m
                {
                    surface += concurrence::surface_terriere_m2(etat.d130[*rang]);
                }
            }
            parametres.fecondite * surface
        })
        .collect()
}

/// L'indice de couvert de chaque cellule : surface des houppiers projetés (π (cw / 2)²) des arbres
/// vivants de la cellule, divisée par la surface de la cellule ; sans unité, sommé dans l'ordre.
fn indice_de_couvert(
    etat: &EtatArbres,
    index: &IndexParCellule,
    cw: &[f64],
    geometrie: &GeometrieGrille,
) -> Vec<f64> {
    let surface_cellule = geometrie.pas * geometrie.pas;
    (0..geometrie.nombre_cellules())
        .into_par_iter()
        .map(|cellule| {
            let mut couvert = 0.0;
            for rang in index.arbres_de(cellule) {
                if etat.vivant[*rang] {
                    let rayon = cw[*rang] / 2.0;
                    couvert += std::f64::consts::PI * rayon * rayon;
                }
            }
            couvert / surface_cellule
        })
        .collect()
}

/// Vrai si une cellule du disque de rayon K autour de `cellule` a des graines à donner.
fn a_portee_d_un_semencier(
    cellule: usize,
    semenciers: &[bool],
    geometrie: &GeometrieGrille,
    demi_largeur: usize,
) -> bool {
    let (ligne, colonne) = geometrie.ligne_colonne(cellule as u64);
    let k = demi_largeur as i64;
    for delta_ligne in -k..=k {
        let l = ligne as i64 + delta_ligne;
        if l < 0 || l >= geometrie.hauteur as i64 {
            continue;
        }
        for delta_colonne in -k..=k {
            let c = colonne as i64 + delta_colonne;
            if c < 0 || c >= geometrie.largeur as i64 {
                continue;
            }
            if !dispersion::dans_le_disque(delta_ligne, delta_colonne, demi_largeur) {
                continue;
            }
            if semenciers[(l * geometrie.largeur as i64 + c) as usize] {
                return true;
            }
        }
    }
    false
}

/// Les cellules qui ont au moins un semencier (graines > 0) d'une essence candidate, sur l'état.
fn cellules_semencieres(
    etat: &EtatArbres,
    cellules: &Cellules,
    modeles: &Modeles,
    regeneration: &Regeneration,
) -> Result<(Vec<bool>, Vec<Vec<f64>>), Erreur> {
    let geometrie = &cellules.geometrie;
    let n = geometrie.nombre_cellules();
    let index = concurrence::indexer(etat, geometrie)?;
    let essence_de = essences_des_arbres(etat, modeles)?;
    let mut semenciers = vec![false; n];
    let mut graines = Vec::with_capacity(modeles.candidates.len());
    for (rang_candidat, essence) in modeles.candidates.iter().enumerate() {
        let g = graines_produites(etat, &index, &essence_de, *essence, &regeneration.parametres[rang_candidat], n);
        for cellule in 0..n {
            if g[cellule] > 0.0 {
                semenciers[cellule] = true;
            }
        }
        graines.push(g);
    }
    Ok((semenciers, graines))
}

fn signalement_hors_de_portee(annee: i32, cellule: usize, demi_largeur: usize) -> Signalement {
    Signalement {
        annee,
        entite: cellule.to_string(),
        sorte: controles::SORTE_TROUEE_HORS_DE_PORTEE.to_string(),
        message: format!(
            "trouée (hauteur dominante nulle) hors de portée : aucun semencier dans le noyau tronqué \
             ({demi_largeur} cellule(s) de rayon) ; elle reste vide"
        ),
        valeur: None,
    }
}

/// Les signalements de t0 en mode `cohorts` : chaque trouée (cellule simulée à H_dom nulle à t0)
/// hors de portée de tout semencier de l'état à t0, dans l'ordre des `cell_id`.
pub fn signalements_t0_cohortes(
    t0: &ResultatPas,
    cellules: &Cellules,
    modeles: &Modeles,
    regeneration: &Regeneration,
    annee_t0: i32,
) -> Result<Vec<Signalement>, Erreur> {
    let (semenciers, _) = cellules_semencieres(&t0.etat, cellules, modeles, regeneration)?;
    let k = regeneration.plan.demi_largeur;
    let mut signalements = Vec::new();
    for cellule in 0..cellules.geometrie.nombre_cellules() {
        if cellules.simulee[cellule]
            && t0.cellules.h_dom[cellule] == 0.0
            && !a_portee_d_un_semencier(cellule, &semenciers, &cellules.geometrie, k)
        {
            signalements.push(signalement_hors_de_portee(annee_t0, cellule, k));
        }
    }
    Ok(signalements)
}

/// Ce que le passage d'une essence donne dans une cellule.
#[derive(Debug, Clone, Copy, Default)]
struct PassageCellule {
    recrues: u64,
    stock_limitant: bool,
    sorties: SortiesParSens,
}

/// Le pas de l'année `annee` en mode `cohorts` (régénération par cohortes de semis, Q1 à Q4) :
/// étapes 1 à 4 comme [`pas_annuel`], puis, pour chaque essence candidate, dans l'ordre des codes :
///
/// 5a. graines des semenciers de l'état figé, dispersées par FFT ([`crate::dispersion`]), règle |Q| ;
/// 5b. installation (part des graines arrivées), survie selon l'ombre de l'état figé, croissance
///     d'une classe ([`semis::avancer`]) ;
/// 5c. passage : sous couvert, flux IFN tiré par arrondi aléatoire (mêmes tirages qu'en
///     `ifn_direct`) borné par le stock ; en trouée, tout le stock à la hauteur de passage passe ;
///     une trouée qui recrute prend pour H_dom la plus grande hauteur de passage des essences qui y
///     recrutent (les recrues en sont les seules dominantes), et elle est comptée recolonisée ;
/// 5d. une trouée sans recrue est signalée : hors de portée si aucun semencier n'est dans le
///     disque du noyau, sinon `trouee_sans_recrue` si elle n'a aucun semis ;
///
/// puis l'ajout des recrues, les houppiers et les contrôles. Rend aussi l'état des semis de fin
/// d'année. Codes comme [`pas_annuel`], plus 3 pour une valeur de dispersion fautive.
#[allow(clippy::too_many_arguments)]
pub fn pas_annuel_cohortes(
    etat: &EtatArbres,
    cellules: &Cellules,
    hdom: &EtatCellules,
    modeles: &Modeles,
    graine: u64,
    annee: i32,
    regeneration: &Regeneration,
    semis_debut: &EtatSemis,
) -> Result<(ResultatPas, EtatSemis), Erreur> {
    let mut debut = debut_du_pas(etat, cellules, hdom, modeles, graine, annee)?;
    let geometrie = &cellules.geometrie;
    let n = geometrie.nombre_cellules();
    let aire_ha = geometrie.aire_cellule_ha();
    if semis_debut.classes.len() != modeles.candidates.len() {
        return Err(Erreur::interne(format!(
            "état des semis pour {} essences, {} candidates",
            semis_debut.classes.len(),
            modeles.candidates.len()
        )));
    }

    // Trouées de fin d'année ; ombre et semenciers de l'état figé.
    let mut trouees = vec![false; n];
    for cellule in 0..n {
        trouees[cellule] = cellules.simulee[cellule] && debut.h_dom_fin[cellule] == 0.0;
    }
    let (_, cw) = houppiers(etat, modeles)?;
    let couvert = indice_de_couvert(etat, &debut.index, &cw, geometrie);
    let mut semenciers = vec![false; n];

    let mut semis_fin = semis_debut.clone();
    let mut passages: Vec<Vec<PassageCellule>> = Vec::with_capacity(modeles.candidates.len());
    for (rang_candidat, essence) in modeles.candidates.iter().enumerate() {
        let p = &regeneration.parametres[rang_candidat];
        let modele = &modeles.essences[*essence];
        let a = semis_fin.classes[rang_candidat];

        // 5a. Graines et dispersion.
        let graines = graines_produites(etat, &debut.index, &debut.essence_de, *essence, p, n);
        let mut arrivees = vec![0.0_f64; n];
        let mut a_disperser = false;
        for cellule in 0..n {
            if graines[cellule] > 0.0 {
                semenciers[cellule] = true;
                a_disperser = true;
            }
        }
        if a_disperser {
            arrivees = regeneration
                .plan
                .convoluer(&graines, &regeneration.spectres[rang_candidat])?;
            let quoi = format!("graines de l'essence {}, année {annee}", modele.espece);
            debut.comptes.valeurs_mises_a_zero +=
                dispersion::mettre_a_zero(&mut arrivees, regeneration.seuil_zero, &quoi)?;
        }

        // 5b. Installation, survie, croissance ; 5c. passage.
        let resumes = &debut.resumes;
        let resultats: Vec<Result<PassageCellule, Erreur>> = semis_fin.densites[rang_candidat]
            .par_chunks_mut(a)
            .enumerate()
            .map(|(cellule, classes)| {
                let mut passage = PassageCellule::default();
                if !cellules.simulee[cellule] {
                    return Ok(passage);
                }
                let nouveaux = p.part_installation * arrivees[cellule] / aire_ha;
                let s = semis::survie(p, semis::ombre(p.coef_extinction, couvert[cellule]));
                semis::avancer(classes, s, nouveaux);
                if trouees[cellule] {
                    let (recrues, _) = semis::passage_massif(classes, aire_ha, None);
                    passage.recrues = recrues;
                    return Ok(passage);
                }
                let flux = flux_ifn_ha(cellules, &resumes[cellule], modele, *essence, cellule, annee, &mut passage.sorties)?;
                let lambda = flux * aire_ha;
                let demandees = recrutement::nombre_de_recrues(
                    graine,
                    annee,
                    cellule as u64,
                    &modele.espece,
                    modele.packee,
                    lambda,
                )?;
                let (recrues, borne) = semis::passage_massif(classes, aire_ha, Some(demandees));
                passage.recrues = recrues;
                passage.stock_limitant = borne;
                Ok(passage)
            })
            .collect();
        let mut liste = Vec::with_capacity(n);
        for resultat in resultats {
            liste.push(resultat?);
        }
        passages.push(liste);
    }

    // Nombres par cellule, essences dans l'ordre des codes ; trouées recolonisées.
    let mut nombres_par_cellule: Vec<Vec<(usize, u64)>> = Vec::with_capacity(n);
    let mut totaux: Vec<u64> = Vec::with_capacity(n);
    let k = regeneration.plan.demi_largeur;
    for cellule in 0..n {
        let mut liste: Vec<(usize, u64)> = Vec::new();
        let mut total = 0;
        let mut hauteur_trouee: f64 = 0.0;
        for (rang_candidat, essence) in modeles.candidates.iter().enumerate() {
            let passage = &passages[rang_candidat][cellule];
            debut.comptes.sorties_domaine.ajouter(&passage.sorties);
            if passage.stock_limitant {
                debut.comptes.stock_de_semis_limitant += 1;
            }
            if passage.recrues > 0 {
                liste.push((*essence, passage.recrues));
                total += passage.recrues;
                hauteur_trouee = hauteur_trouee.max(regeneration.parametres[rang_candidat].hauteur_passage_m);
            }
        }
        if trouees[cellule] {
            if total > 0 {
                debut.h_dom_fin[cellule] = hauteur_trouee;
                debut.comptes.trouees_recolonisees += 1;
            } else if !a_portee_d_un_semencier(cellule, &semenciers, geometrie, k) {
                debut.signalements.push(signalement_hors_de_portee(annee, cellule, k));
            } else {
                let mut semis_presents = false;
                for rang_candidat in 0..modeles.candidates.len() {
                    if semis::total(semis_fin.de(rang_candidat, cellule)) > 0.0 {
                        semis_presents = true;
                    }
                }
                if !semis_presents {
                    debut.comptes.cellules_trouee_sans_recrue += 1;
                    debut.signalements.push(Signalement {
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
        }
        totaux.push(total);
        nombres_par_cellule.push(liste);
    }
    let resultat = fin_du_pas(etat, cellules, modeles, graine, annee, debut, nombres_par_cellule, totaux)?;
    Ok((resultat, semis_fin))
}
