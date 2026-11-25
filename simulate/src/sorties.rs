//! Assemblage et sorties de `simulate` (plan M3a, « Sorties, contrôles, codes » ; spec §2, §6,
//! §9 ; contrats `sim.trees`, `sim.cells`, `simulate.flags`, `run.json`).
//!
//! Étape du BRIEF codée ici : BRIEF §8 (le massif simulé année par année, de t0 à t0 + years) et
//! §4 (formats des fichiers écrits). Ce module prend les entrées lues par [`crate::entrees`],
//! enchaîne l'état initial ([`crate::pas::initialiser_t0`]) puis `years` pas annuels
//! ([`crate::pas::pas_annuel`]) et écrit, dans un dossier donné :
//!
//! - `trees/year=AAAA/part-00000.parquet` : un arbre par ligne, les vivants et les morts de
//!   l'année (un mort est écrit une seule fois, l'année de sa mort) ; colonnes du contrat
//!   `sim.trees` **sans `year`**, qui n'est que dans le nom du dossier (convention Hive,
//!   ADR 0002 : le validateur refuse une année écrite deux fois) ;
//! - `cells/year=AAAA/part-00000.parquet` : par cellule et essence, les seuls arbres **vivants** :
//!   tiges/ha, surface terrière (m²/ha) et d130 moyen **arithmétique** (T8) ; une ligne par couple
//!   (cellule, essence) qui a au moins un arbre vivant. S'y ajoute `h_dom_m`, la hauteur dominante
//!   de la cellule à la fin de l'année, en m, **telle que le moteur la calcule** (mission 046,
//!   décision de Pascal du 25/11/2026) : la même valeur sur les lignes de toutes les essences d'une
//!   cellule ; vide (null) si elle n'est pas finie, jamais 0 en silence. Les colonnes de semis ne
//!   sont pas écrites : **semis non simulés** jusqu'à M5 (décision de Pascal, Q3), dit par un
//!   signalement ;
//! - `flags.parquet` : les signalements du pas ([`crate::controles`]) puis ceux de ce module ;
//! - `run.json` : réglages, mémoire estimée, durée, empreinte de `config.yml`, comptes.
//!
//! Toutes les tiges vivantes sont comptées dans `stems_ha`, recrues de 7,48 cm comprises : le
//! seuil « 7,5 cm » du contrat est l'arrondi du seuil de l'IFN (C13 = 0,235 m, soit 7,48 cm),
//! celui-là même qui fait entrer une recrue (mission 038, dit dans son rendu).
//!
//! # Avant le premier pas : la mémoire (spec §6, T3)
//!
//! [`estimer_memoire`] estime l'occupation (deux copies de l'état initial, couches, tampons
//! d'écriture d'une année) et la compare à 0,9 × `MemAvailable` **avant de créer le moindre
//! dossier** : code 4 sinon ; c'est la valeur `memory_estimate_bytes` de `run.json`. L'état
//! grandit ensuite avec les recrues (sur le jeu fictif, de 14 080 à environ 400 000 arbres en
//! 100 ans) : la même estimation est refaite **avant chaque pas** sur l'état courant, contre le
//! `MemAvailable` lu au lancement (code 4, et rien n'est publié). Chaque réservation passe par
//! `try_reserve_exact` (code 4, jamais un arrêt brutal). Mesurer l'estimation contre la mémoire
//! résidente est un travail de M5 (spec §11).
//!
//! # Identité entre nombres de fils (T1)
//!
//! Tout le calcul tourne dans un pool rayon de `threads` fils ; les sorties ne sont écrites que
//! par le fil appelant, dans l'ordre de l'état et des `cell_id`. Les fichiers Parquet (Snappy,
//! T2) ne portent ni date ni nom de machine : mêmes entrées, mêmes octets, quel que soit le
//! nombre de fils. Seuls `duration_s` et `threads` de `run.json` en dépendent.
//!
//! # Sortes de signalement ajoutées ici (colonne `kind`, contrat `simulate.flags`)
//!
//! | Sorte | Entité | Valeur |
//! |---|---|---|
//! | [`SORTE_SEMIS_NON_SIMULES`] | la zone (`zone` de config.yml), année t0 | vide |
//! | [`SORTE_TOTAL_CELLULES_SANS_ARBRE`] | la zone, dernière année | nombre de couples (cellule, année) |
//! | [`SORTE_TOTAL_RECRUES_CELLULE_VIDE`] | la zone, dernière année | nombre de recrues |
//! | [`SORTE_TOTAL_SER_SANS_EFFET`] | la zone, dernière année | nombre de prédicteurs |
//! | [`SORTE_TOTAL_TROUEES_SANS_RECRUE`] | la zone, dernière année | nombre de couples (cellule, année) |
//!
//! Les quatre totaux ne sont écrits que s'ils ne sont pas nuls : `run.json` n'a pas de place pour
//! eux (son contrat refuse toute clé en plus), et les taire serait deviner à la place du lecteur.
//!
//! Règle de lisibilité (CLAUDE.md) : structures concrètes, fonctions libres, aucune macro maison
//! ni générique maison.

use std::collections::BTreeMap;
use std::fs::{self, File};
use std::path::Path;
use std::sync::Arc;
use std::time::Instant;

use arrow_array::{ArrayRef, Float64Array, Int64Array, RecordBatch, StringArray};
use arrow_schema::{DataType, Field, Schema};
use parquet::arrow::ArrowWriter;
use parquet::basic::Compression;
use parquet::file::properties::WriterProperties;
use sha2::{Digest, Sha256};

use crate::concurrence::{self, GeometrieGrille};
use crate::config::NiveauSimulation;
use crate::controles::{Comptes, Signalement};
use crate::entrees::{Couches, Entrees, JeuxDeParametres};
use crate::erreurs::Erreur;
use crate::etat::{EtatArbres, OCTETS_FIXES_PAR_ARBRE};
use crate::grille::Grille;
use crate::hauteur::ReferenceKorf;
use crate::memoire::{self, Besoin};
use crate::parametres::{Parametres, Porteur, Referentiel, Variable};
use crate::pas::{self, Cellules, EtatCellules, Modeles, ResultatPas, SourcesDeParametres};

/// Les semis ne sont pas simulés avant M5 (décision de Pascal, Q3).
pub const SORTE_SEMIS_NON_SIMULES: &str = "semis_non_simules";
/// Total des couples (cellule, année) simulés sans arbre vivant (H_dom tenue, T5).
pub const SORTE_TOTAL_CELLULES_SANS_ARBRE: &str = "total_cellules_sans_arbre";
/// Total des recrues nées dans une cellule sans arbre (rel_d pris à 1).
pub const SORTE_TOTAL_RECRUES_CELLULE_VIDE: &str = "total_recrues_cellule_vide";
/// Total des prédicteurs calculés pour une SER absente des effets du jeu (effet pris à 0).
pub const SORTE_TOTAL_SER_SANS_EFFET: &str = "total_ser_sans_effet";

/// Total des couples (cellule, année) en trouée (H_dom nulle), sans recrue (décision de Pascal du
/// 25/11/2026) ; chaque couple a aussi sa ligne `trouee_sans_recrue`.
pub const SORTE_TOTAL_TROUEES_SANS_RECRUE: &str = "total_trouees_sans_recrue";

/// Nom du fichier de chaque partition.
pub const FICHIER_PARTITION: &str = "part-00000.parquet";

/// Les réglages d'une exécution qui ne viennent pas des entrées.
#[derive(Debug, Clone, PartialEq)]
pub struct Lancement {
    /// Nombre de fils de calcul (au moins 1).
    pub threads: usize,
    /// `MemAvailable`, en octets (lu dans /proc/meminfo, ou option `--memoire-disponible`).
    pub memoire_disponible: u64,
    /// Option de test `--inject-nan` : l'année où un NaN est mis dans l'état (code 3 attendu).
    pub inject_nan: Option<i32>,
    /// La zone (`zone` de config.yml), entité des signalements qui portent sur tout le massif.
    pub zone: String,
    /// SHA-256 des octets de config.yml, en hexadécimal minuscule.
    pub config_sha256: String,
}

/// Ce que rend une simulation écrite.
#[derive(Debug, Clone, PartialEq)]
pub struct Bilan {
    /// Comptes de toute la simulation (t0 à t0 + years).
    pub comptes: Comptes,
    /// Estimation d'avant le premier pas (écrite dans run.json).
    pub memoire_estimee: u64,
    /// La plus grande des estimations faites avant chaque pas (l'état grandit avec les recrues).
    pub memoire_maximale: u64,
    pub duree_s: f64,
    /// Arbres écrits (lignes de toutes les partitions de `trees`).
    pub lignes_arbres: u64,
    pub signalements: u64,
}

/// SHA-256 d'octets, en hexadécimal minuscule.
pub fn sha256_hex(octets: &[u8]) -> String {
    let empreinte = Sha256::digest(octets);
    let mut texte = String::with_capacity(64);
    for octet in empreinte.iter() {
        texte.push_str(&format!("{octet:02x}"));
    }
    texte
}

// ------------------------------------------------------------------------------------------
// Des entrées au moteur

/// Les couches de la grille pour le pas annuel (f64, ordre de `cell_id`). Une cellule hors de
/// `grid.tif` reçoit NaN (et une SER vide) : elle n'est jamais simulée.
pub fn cellules_depuis(grille: &Grille, couches: &Couches) -> Result<Cellules, Erreur> {
    let geometrie = GeometrieGrille::nouvelle(
        grille.largeur,
        grille.hauteur,
        grille.origine_x,
        grille.origine_y,
        grille.pas,
    )?;
    let n = grille.nombre_cellules();
    let mut cellules = Cellules {
        geometrie,
        simulee: grille.valide.clone(),
        h0: memoire::reserver_f64(n, "couche h0")?,
        chm_date: memoire::reserver_f64(n, "couche chm_date")?,
        trophic: memoire::reserver_f64(n, "couche trophic")?,
        hydric: memoire::reserver_f64(n, "couche hydric")?,
        bioclim: memoire::reserver_f64(n, "couche bioclim")?,
        ser_code: Vec::with_capacity(n),
        site_potential: memoire::reserver_f64(n, "couche site_potential")?,
        nombre_bandes: 1,
        bande_par_essence: Vec::new(),
    };
    for cellule in 0..n {
        if !grille.valide[cellule] {
            cellules.h0.push(f64::NAN);
            cellules.chm_date.push(f64::NAN);
            cellules.trophic.push(f64::NAN);
            cellules.hydric.push(f64::NAN);
            cellules.bioclim.push(f64::NAN);
            cellules.site_potential.push(f64::NAN);
            cellules.ser_code.push(String::new());
            continue;
        }
        let code = match couches.code_ser(cellule as u64) {
            Some(code) => code.to_string(),
            None => {
                return Err(Erreur::entree_refusee(format!(
                    "ser.tif : cellule {cellule} sans code de SER dans ser.csv"
                )))
            }
        };
        cellules.h0.push(f64::from(couches.h0[cellule]));
        cellules.chm_date.push(f64::from(couches.chm_date[cellule]));
        cellules.trophic.push(f64::from(couches.trophic[cellule]));
        cellules.hydric.push(f64::from(couches.hydric[cellule]));
        cellules.bioclim.push(f64::from(couches.bioclim[cellule]));
        cellules
            .site_potential
            .push(f64::from(couches.h_pot[cellule]));
        cellules.ser_code.push(code);
    }
    cellules.verifier()?;
    Ok(cellules)
}

/// Les jeux de paramètres vus par le moteur.
pub fn sources(jeux: &JeuxDeParametres) -> SourcesDeParametres<'_> {
    SourcesDeParametres {
        croissance: &jeux.croissance,
        mortalite: &jeux.mortalite,
        recrutement: &jeux.recrutement,
        courbe_hauteur: &jeux.courbe_hauteur,
        allometrie: &jeux.allometrie,
    }
}

/// Les essences distinctes de l'état, triées.
pub fn essences_de_l_etat(etat: &EtatArbres) -> Vec<String> {
    let mut essences: Vec<String> = etat.espece.clone();
    essences.sort();
    essences.dedup();
    essences
}

/// Les essences qui ont des lignes propres (colonne `species`) dans l'un des jeux, triées.
pub fn essences_a_lignes_propres(jeux: &JeuxDeParametres) -> Vec<String> {
    let mut essences: Vec<String> = Vec::new();
    let tous: [&Parametres; 5] = [
        &jeux.croissance,
        &jeux.mortalite,
        &jeux.recrutement,
        &jeux.courbe_hauteur,
        &jeux.allometrie,
    ];
    for parametres in tous {
        for jeu in &parametres.jeux {
            if let Porteur::Essence(code) = &jeu.porteur {
                essences.push(code.clone());
            }
        }
    }
    essences.sort();
    essences.dedup();
    essences
}

/// Le point de départ de Korf (mission 040) : les termes `t_ref0`, `h_ref0` et `age_ref` du jeu
/// `korf` de chaque essence dont la courbe est de Korf. `None` si aucune ne l'est.
///
/// Code 2 si un jeu `korf` n'a pas ces trois termes (paramètres d'avant la mission 040 :
/// relancer `make dynamics`), ou si deux essences de Korf ont des points de départ différents
/// (le pas annuel n'en tient qu'un).
pub fn reference_korf(
    courbes: &Parametres,
    referentiel: &Referentiel,
    essences: &[String],
) -> Result<Option<ReferenceKorf>, Erreur> {
    let mut retenue: Option<(String, ReferenceKorf)> = None;
    for espece in essences {
        let jeu = pas::chercher_courbe(courbes, espece, referentiel)?;
        if jeu.modele != "korf" {
            continue;
        }
        let mut valeurs = [0.0; 3];
        for (rang, terme) in ["t_ref0", "h_ref0", "age_ref"].iter().enumerate() {
            valeurs[rang] = jeu.scalaire(terme).map_err(|_| {
                Erreur::entree_refusee(format!(
                    "courbe de Korf de l'essence {espece} sans le terme « {terme} » (point de départ, \
                     mission 040) : relancer make dynamics ; la classe de fertilité ne se devine pas"
                ))
            })?;
        }
        let reference = ReferenceKorf {
            age_depart: valeurs[0],
            hauteur_depart: valeurs[1],
            age_reference: valeurs[2],
        };
        match &retenue {
            None => retenue = Some((espece.clone(), reference)),
            Some((autre, deja)) => {
                if *deja != reference {
                    return Err(Erreur::entree_refusee(format!(
                        "points de départ de Korf différents pour les essences {autre} et {espece} : \
                         le moteur n'en tient qu'un"
                    )));
                }
            }
        }
    }
    Ok(retenue.map(|(_, reference)| reference))
}

/// Les modèles du moteur : essences de l'état et candidates au recrutement, soit les essences de
/// l'état plus celles qui ont des lignes propres, parmi lesquelles celles qui ont les quatre jeux
/// (T6, décision du 25/11/2026 sur 037). Code 2 si un jeu manque.
pub fn preparer_modeles(entrees: &Entrees) -> Result<Modeles, Erreur> {
    let sources = sources(&entrees.parametres);
    let essences_etat = essences_de_l_etat(&entrees.arbres);
    let mut depart = essences_etat.clone();
    depart.extend(essences_a_lignes_propres(&entrees.parametres));
    let candidates = pas::essences_candidates(&sources, &entrees.referentiel, &depart);
    let mut toutes = essences_etat.clone();
    toutes.extend(candidates.iter().cloned());
    toutes.sort();
    toutes.dedup();
    let reference = reference_korf(
        &entrees.parametres.courbe_hauteur,
        &entrees.referentiel,
        &toutes,
    )?;
    Modeles::preparer(
        &sources,
        &entrees.referentiel,
        &essences_etat,
        &candidates,
        reference,
    )
}

/// La part des jeux de paramètres utilisés marqués provisoires (spec §10), de 0 à 1.
pub fn part_provisoire(modeles: &Modeles) -> f64 {
    let (provisoires, total) = modeles.jeux_provisoires();
    if total == 0 {
        return 0.0;
    }
    provisoires as f64 / total as f64
}

// ------------------------------------------------------------------------------------------
// Mémoire

/// L'estimation de la mémoire (octets) pour un état de `arbres` arbres : deux copies de l'état,
/// les couches lues (f32) et celles du moteur (f64), les tampons d'écriture d'une année.
/// `texte_par_arbre` : octets de texte (tree_id, essence) par arbre. Code 4 si le calcul déborde.
pub fn estimer_memoire(arbres: u64, texte_par_arbre: u64, grille: &Grille) -> Result<u64, Erreur> {
    let cellules = grille.nombre_cellules() as u64;
    // Couches f32 des entrées : h0, chm_date, h_pot, trois gradients, ser (u32).
    let valeurs_raster = cellules * 7;
    // Couches f64 du moteur (6), H_dom de début et de fin d'année (2), drapeau, code de SER.
    let par_cellule = 8 * 8 + 1 + std::mem::size_of::<String>() as u64 + 8;
    // Tampons d'une année : hcb, cw, et les colonnes du Parquet (copie de l'état).
    let par_arbre_ecrit = 2 * 8 + OCTETS_FIXES_PAR_ARBRE + texte_par_arbre;
    let supplementaires = cellules
        .checked_mul(par_cellule)
        .and_then(|c| {
            arbres
                .checked_mul(par_arbre_ecrit)
                .and_then(|a| c.checked_add(a))
        })
        .ok_or_else(|| {
            Erreur::memoire_insuffisante("besoin de mémoire hors de portée".to_string())
        })?;
    memoire::estimer(&Besoin {
        arbres_max: arbres,
        octets_texte_par_arbre: texte_par_arbre,
        valeurs_raster,
        octets_supplementaires: supplementaires,
    })
}

/// Octets de texte par arbre de l'état (arrondi au-dessus ; 0 pour un état vide).
pub fn texte_par_arbre(etat: &EtatArbres) -> u64 {
    let arbres = etat.len() as u64;
    if arbres == 0 {
        return 0;
    }
    etat.octets_texte().div_ceil(arbres)
}

/// Vérifie la mémoire pour l'état de début d'année (code 4 sinon) et rend l'estimation.
/// L'état grandit avec les recrues : l'estimation d'avant le premier pas ne le prévoit pas,
/// d'où ce contrôle à chaque année, contre le `MemAvailable` lu au lancement.
fn verifier_memoire_annee(
    etat: &EtatArbres,
    grille: &Grille,
    disponible: u64,
    annee: i32,
) -> Result<u64, Erreur> {
    let besoin = estimer_memoire(etat.len() as u64, texte_par_arbre(etat), grille)?;
    memoire::verifier(besoin, disponible).map_err(|e| Erreur {
        code: e.code,
        message: format!(
            "avant le pas de l'année {annee} ({} arbres) : {}",
            etat.len(),
            e.message
        ),
    })?;
    Ok(besoin)
}

// ------------------------------------------------------------------------------------------
// Simulation et écriture

/// Simule de t0 à t0 + years et écrit tout dans `dossier` (qui ne doit pas exister).
///
/// La mémoire est vérifiée **avant** la création du dossier (code 4). Codes : 1 anomalie du
/// programme ou écriture impossible, 2 entrée refusée, 3 contrôle échoué (dont `--inject-nan`),
/// 4 mémoire. En cas d'erreur, le dossier peut contenir une sortie partielle : c'est à l'appelant
/// de le supprimer (il écrit toujours dans un dossier temporaire, voir `lib.rs`).
pub fn simuler_et_ecrire(
    entrees: &Entrees,
    lancement: &Lancement,
    dossier: &Path,
) -> Result<Bilan, Erreur> {
    let debut = Instant::now();
    let reglages = &entrees.reglages;
    if lancement.threads == 0 {
        return Err(Erreur::entree_refusee(
            "nombre de fils nul : il en faut au moins un".to_string(),
        ));
    }
    let derniere = reglages
        .t0
        .checked_add(reglages.years as i32)
        .ok_or_else(|| {
            Erreur::entree_refusee("t0 + years dépasse les années représentables".to_string())
        })?;
    if let Some(annee) = lancement.inject_nan {
        if annee < reglages.t0 || annee > derniere || entrees.arbres.is_empty() {
            return Err(Erreur::entree_refusee(format!(
                "--inject-nan {annee} : l'année doit être entre t0 = {} et t0 + years = {derniere}, \
                 et l'état initial non vide",
                reglages.t0
            )));
        }
    }
    let cellules = cellules_depuis(&entrees.grille, &entrees.couches)?;
    let modeles = preparer_modeles(entrees)?;

    // Avant toute écriture : la mémoire.
    let memoire_estimee = estimer_memoire(
        entrees.arbres.len() as u64,
        texte_par_arbre(&entrees.arbres),
        &entrees.grille,
    )?;
    memoire::verifier(memoire_estimee, lancement.memoire_disponible)?;

    if dossier.exists() {
        return Err(Erreur::interne(format!(
            "le dossier de sortie {} existe déjà",
            dossier.display()
        )));
    }
    creer_dossier(dossier)?;

    let pool = rayon::ThreadPoolBuilder::new()
        .num_threads(lancement.threads)
        .build()
        .map_err(|e| {
            Erreur::interne(format!(
                "pool de {} fils impossible : {e}",
                lancement.threads
            ))
        })?;
    let resultat = pool.install(|| boucle(entrees, &cellules, &modeles, lancement, dossier))?;
    let (comptes, mut signalements, lignes_arbres, memoire_maximale) = resultat;

    ajouter_signalements_de_zone(
        &mut signalements,
        &comptes,
        lancement,
        reglages.t0,
        derniere,
    );
    ecrire_signalements(&dossier.join("flags.parquet"), &signalements)?;

    let duree_s = debut.elapsed().as_secs_f64();
    let run = run_json(
        entrees,
        lancement,
        &comptes,
        part_provisoire(&modeles),
        memoire_estimee,
        duree_s,
    );
    ecrire_texte(&dossier.join("run.json"), &run)?;
    Ok(Bilan {
        comptes,
        memoire_estimee,
        memoire_maximale,
        duree_s,
        lignes_arbres,
        signalements: signalements.len() as u64,
    })
}

/// t0 puis les pas annuels, avec écriture de chaque année ; dans le pool de l'appelant.
fn boucle(
    entrees: &Entrees,
    cellules: &Cellules,
    modeles: &Modeles,
    lancement: &Lancement,
    dossier: &Path,
) -> Result<(Comptes, Vec<Signalement>, u64, u64), Erreur> {
    let reglages = &entrees.reglages;
    let mut memoire_maximale: u64 = 0;
    let mut comptes = Comptes::default();
    let mut signalements: Vec<Signalement> = Vec::new();
    let mut lignes: u64 = 0;

    let mut etat = entrees.arbres.clone();
    if lancement.inject_nan == Some(reglages.t0) {
        injecter_nan(&mut etat);
    }
    let resultat = pas::initialiser_t0(&etat, cellules, modeles, reglages.t0)?;
    lignes += ecrire_annee(dossier, reglages.t0, &resultat, &cellules.geometrie)?;
    let (mut etat, mut hdom) = absorber(resultat, &mut comptes, &mut signalements);

    for rang in 1..=reglages.years {
        let annee = reglages.t0 + rang as i32;
        etat.retirer_morts();
        let besoin =
            verifier_memoire_annee(&etat, &entrees.grille, lancement.memoire_disponible, annee)?;
        memoire_maximale = memoire_maximale.max(besoin);
        if lancement.inject_nan == Some(annee) {
            injecter_nan(&mut etat);
        }
        let resultat = pas::pas_annuel(&etat, cellules, &hdom, modeles, reglages.seed, annee)?;
        lignes += ecrire_annee(dossier, annee, &resultat, &cellules.geometrie)?;
        let suite = absorber(resultat, &mut comptes, &mut signalements);
        etat = suite.0;
        hdom = suite.1;
        if rang % 10 == 0 || rang == reglages.years {
            eprintln!(
                "[simulate] année {annee} écrite ({rang}/{}) : {} arbres vivants",
                reglages.years,
                etat.vivant.iter().filter(|v| **v).count()
            );
        }
    }
    Ok((comptes, signalements, lignes, memoire_maximale))
}

fn absorber(
    resultat: ResultatPas,
    comptes: &mut Comptes,
    signalements: &mut Vec<Signalement>,
) -> (EtatArbres, EtatCellules) {
    comptes.ajouter(&resultat.comptes);
    signalements.extend(resultat.signalements);
    (resultat.etat, resultat.cellules)
}

/// Option de test `--inject-nan` : le d130 du premier arbre de l'état devient NaN.
fn injecter_nan(etat: &mut EtatArbres) {
    if let Some(d130) = etat.d130.first_mut() {
        *d130 = f64::NAN;
    }
}

fn ajouter_signalements_de_zone(
    signalements: &mut Vec<Signalement>,
    comptes: &Comptes,
    lancement: &Lancement,
    t0: i32,
    derniere: i32,
) {
    signalements.push(Signalement {
        annee: t0,
        entite: lancement.zone.clone(),
        sorte: SORTE_SEMIS_NON_SIMULES.to_string(),
        message: "semis non simulés (jusqu'à M5, décision de Pascal du 25/11/2026) : les colonnes \
                  seedlings_ha et seedling_h_mean de sim/cells ne sont pas écrites"
            .to_string(),
        valeur: None,
    });
    let totaux = [
        (
            SORTE_TOTAL_CELLULES_SANS_ARBRE,
            comptes.cellules_sans_arbre,
            "couples (cellule, année) simulés sans arbre vivant : la hauteur dominante y est tenue, \
             faute d'essence pour donner sa courbe",
        ),
        (
            SORTE_TOTAL_RECRUES_CELLULE_VIDE,
            comptes.recrues_cellule_vide,
            "recrues nées dans une cellule sans arbre : leur hauteur relative est prise à rel_d = 1 \
             (elles sont leurs propres dominantes)",
        ),
        (
            SORTE_TOTAL_SER_SANS_EFFET,
            comptes.sorties_domaine.ser_sans_effet,
            "prédicteurs calculés pour une SER absente des effets du jeu de paramètres : effet de \
             SER pris à 0, comme le veut le contrat",
        ),
        (
            SORTE_TOTAL_TROUEES_SANS_RECRUE,
            comptes.cellules_trouee_sans_recrue,
            "couples (cellule, année) en trouée, à hauteur dominante nulle : aucune recrue n'y est \
             ajoutée (décision de Pascal du 25/11/2026 ; recolonisation par les cohortes en M5)",
        ),
    ];
    for (sorte, total, texte) in totaux {
        if total > 0 {
            signalements.push(Signalement {
                annee: derniere,
                entite: lancement.zone.clone(),
                sorte: sorte.to_string(),
                message: format!("{total} {texte} (total de t0 = {t0} à {derniere})"),
                valeur: Some(total as f64),
            });
        }
    }
}

// ------------------------------------------------------------------------------------------
// Parquet

fn creer_dossier(dossier: &Path) -> Result<(), Erreur> {
    fs::create_dir_all(dossier).map_err(|e| {
        Erreur::interne(format!(
            "dossier {} impossible à créer : {e}",
            dossier.display()
        ))
    })
}

fn proprietes() -> WriterProperties {
    WriterProperties::builder()
        .set_compression(Compression::SNAPPY)
        .build()
}

fn ecrire_lot(chemin: &Path, lot: RecordBatch) -> Result<(), Erreur> {
    let echec =
        |e: String| Erreur::interne(format!("écriture de {} impossible : {e}", chemin.display()));
    let fichier = File::create(chemin).map_err(|e| echec(e.to_string()))?;
    let mut ecrivain = ArrowWriter::try_new(fichier, lot.schema(), Some(proprietes()))
        .map_err(|e| echec(e.to_string()))?;
    ecrivain.write(&lot).map_err(|e| echec(e.to_string()))?;
    ecrivain.close().map_err(|e| echec(e.to_string()))?;
    Ok(())
}

fn lot(champs: Vec<Field>, colonnes: Vec<ArrayRef>, nom: &str) -> Result<RecordBatch, Erreur> {
    RecordBatch::try_new(Arc::new(Schema::new(champs)), colonnes)
        .map_err(|e| Erreur::interne(format!("table {nom} mal formée : {e}")))
}

fn ecrire_texte(chemin: &Path, texte: &str) -> Result<(), Erreur> {
    fs::write(chemin, texte)
        .map_err(|e| Erreur::interne(format!("écriture de {} impossible : {e}", chemin.display())))
}

/// Écrit les partitions `trees` et `cells` d'une année ; rend le nombre d'arbres écrits.
fn ecrire_annee(
    dossier: &Path,
    annee: i32,
    resultat: &ResultatPas,
    geometrie: &GeometrieGrille,
) -> Result<u64, Erreur> {
    let partition = format!("year={annee}");
    let dossier_arbres = dossier.join("trees").join(&partition);
    let dossier_cellules = dossier.join("cells").join(&partition);
    creer_dossier(&dossier_arbres)?;
    creer_dossier(&dossier_cellules)?;
    ecrire_lot(
        &dossier_arbres.join(FICHIER_PARTITION),
        table_arbres(resultat)?,
    )?;
    ecrire_lot(
        &dossier_cellules.join(FICHIER_PARTITION),
        table_cellules(&resultat.etat, &resultat.cellules.h_dom, geometrie)?,
    )?;
    Ok(resultat.etat.len() as u64)
}

/// La table `sim.trees` d'une année (sans la colonne `year`, portée par la partition).
pub fn table_arbres(resultat: &ResultatPas) -> Result<RecordBatch, Erreur> {
    let etat = &resultat.etat;
    let mut statut: Vec<&str> = Vec::with_capacity(etat.len());
    for vivant in &etat.vivant {
        statut.push(if *vivant { "alive" } else { "dead" });
    }
    let champs = vec![
        Field::new("tree_id", DataType::Utf8, false),
        Field::new("species", DataType::Utf8, false),
        Field::new("x", DataType::Float64, false),
        Field::new("y", DataType::Float64, false),
        Field::new("d130", DataType::Float64, false),
        Field::new("h", DataType::Float64, false),
        Field::new("hcb", DataType::Float64, false),
        Field::new("cw", DataType::Float64, false),
        Field::new("status", DataType::Utf8, false),
    ];
    let colonnes: Vec<ArrayRef> = vec![
        Arc::new(StringArray::from(etat.tree_id.clone())),
        Arc::new(StringArray::from(etat.espece.clone())),
        Arc::new(Float64Array::from(etat.x.clone())),
        Arc::new(Float64Array::from(etat.y.clone())),
        Arc::new(Float64Array::from(etat.d130.clone())),
        Arc::new(Float64Array::from(etat.h.clone())),
        Arc::new(Float64Array::from(resultat.hcb.clone())),
        Arc::new(Float64Array::from(resultat.cw.clone())),
        Arc::new(StringArray::from(statut)),
    ];
    lot(champs, colonnes, "sim.trees")
}

/// Une ligne de `sim.cells` : une cellule, une essence, ses arbres vivants.
#[derive(Debug, Clone, Copy, PartialEq, Default)]
pub struct LigneCellule {
    pub tiges: u64,
    /// Somme des surfaces terrières, en m².
    pub surface_m2: f64,
    /// Somme des d130, en cm.
    pub somme_d130: f64,
}

/// Les arbres vivants résumés par (cell_id, essence), triés ; sommes dans l'ordre de l'état.
pub fn resumer_cellules(etat: &EtatArbres) -> BTreeMap<(u64, String), LigneCellule> {
    let mut lignes: BTreeMap<(u64, String), LigneCellule> = BTreeMap::new();
    for rang in 0..etat.len() {
        if !etat.vivant[rang] {
            continue;
        }
        let ligne = lignes
            .entry((etat.cellule[rang], etat.espece[rang].clone()))
            .or_default();
        ligne.tiges += 1;
        ligne.surface_m2 += concurrence::surface_terriere_m2(etat.d130[rang]);
        ligne.somme_d130 += etat.d130[rang];
    }
    lignes
}

/// La table `sim.cells` d'une année (sans `year`, sans les colonnes de semis).
///
/// `h_dom` : la H_dom de chaque cellule à la fin de l'année, en m (ordre de `cell_id`). Elle est
/// écrite dans `h_dom_m` ; une valeur non finie, ou une cellule hors de `h_dom`, donne null.
pub fn table_cellules(
    etat: &EtatArbres,
    h_dom: &[f64],
    geometrie: &GeometrieGrille,
) -> Result<RecordBatch, Erreur> {
    let aire_ha = geometrie.aire_cellule_ha();
    let lignes = resumer_cellules(etat);
    let mut cell_id: Vec<i64> = Vec::with_capacity(lignes.len());
    let mut espece: Vec<String> = Vec::with_capacity(lignes.len());
    let mut tiges_ha: Vec<f64> = Vec::with_capacity(lignes.len());
    let mut surface_ha: Vec<f64> = Vec::with_capacity(lignes.len());
    let mut d130_moyen: Vec<Option<f64>> = Vec::with_capacity(lignes.len());
    let mut h_dom_m: Vec<Option<f64>> = Vec::with_capacity(lignes.len());
    for ((cellule, code), ligne) in lignes {
        h_dom_m.push(h_dom.get(cellule as usize).copied().filter(|h| h.is_finite()));
        cell_id.push(cellule as i64);
        espece.push(code);
        tiges_ha.push(ligne.tiges as f64 / aire_ha);
        surface_ha.push(ligne.surface_m2 / aire_ha);
        d130_moyen.push(Some(ligne.somme_d130 / ligne.tiges as f64));
    }
    let champs = vec![
        Field::new("cell_id", DataType::Int64, false),
        Field::new("species", DataType::Utf8, false),
        Field::new("stems_ha", DataType::Float64, false),
        Field::new("basal_area_m2_ha", DataType::Float64, false),
        Field::new("d130_mean", DataType::Float64, true),
        Field::new("h_dom_m", DataType::Float64, true),
    ];
    let colonnes: Vec<ArrayRef> = vec![
        Arc::new(Int64Array::from(cell_id)),
        Arc::new(StringArray::from(espece)),
        Arc::new(Float64Array::from(tiges_ha)),
        Arc::new(Float64Array::from(surface_ha)),
        Arc::new(Float64Array::from(d130_moyen)),
        Arc::new(Float64Array::from(h_dom_m)),
    ];
    lot(champs, colonnes, "sim.cells")
}

/// Écrit `flags.parquet` (contrat `simulate.flags`) ; une valeur non finie est écrite vide (le
/// message la dit).
pub fn ecrire_signalements(chemin: &Path, signalements: &[Signalement]) -> Result<(), Erreur> {
    let mut annee: Vec<i64> = Vec::with_capacity(signalements.len());
    let mut entite: Vec<&str> = Vec::with_capacity(signalements.len());
    let mut sorte: Vec<&str> = Vec::with_capacity(signalements.len());
    let mut message: Vec<&str> = Vec::with_capacity(signalements.len());
    let mut valeur: Vec<Option<f64>> = Vec::with_capacity(signalements.len());
    for signalement in signalements {
        annee.push(i64::from(signalement.annee));
        entite.push(&signalement.entite);
        sorte.push(&signalement.sorte);
        message.push(&signalement.message);
        valeur.push(signalement.valeur.filter(|v| v.is_finite()));
    }
    let champs = vec![
        Field::new("year", DataType::Int64, false),
        Field::new("entity", DataType::Utf8, false),
        Field::new("kind", DataType::Utf8, false),
        Field::new("message", DataType::Utf8, false),
        Field::new("value", DataType::Float64, true),
    ];
    let colonnes: Vec<ArrayRef> = vec![
        Arc::new(Int64Array::from(annee)),
        Arc::new(StringArray::from(entite)),
        Arc::new(StringArray::from(sorte)),
        Arc::new(StringArray::from(message)),
        Arc::new(Float64Array::from(valeur)),
    ];
    ecrire_lot(chemin, lot(champs, colonnes, "simulate.flags")?)
}

// ------------------------------------------------------------------------------------------
// run.json

/// Le texte de `run.json` (contrat `run`), clés triées, terminé par un saut de ligne.
pub fn run_json(
    entrees: &Entrees,
    lancement: &Lancement,
    comptes: &Comptes,
    provisional_share: f64,
    memoire_estimee: u64,
    duree_s: f64,
) -> String {
    let reglages = &entrees.reglages;
    let niveau = match reglages.niveau {
        NiveauSimulation::Massif => "massif",
        NiveauSimulation::Ser => "ser",
    };
    let mut domaine = serde_json::Map::new();
    for variable in Variable::TOUTES {
        let (dessous, dessus) = comptes.sorties_domaine.pour(variable);
        domaine.insert(
            variable.nom().to_string(),
            serde_json::json!({"below": dessous, "above": dessus}),
        );
    }
    let valeur = serde_json::json!({
        "schema_version": 1,
        "level": niveau,
        "seed": reglages.seed,
        "t0": reglages.t0,
        "years": reglages.years,
        "threads": lancement.threads,
        "memory_estimate_bytes": memoire_estimee,
        "duration_s": duree_s,
        "config_sha256": lancement.config_sha256,
        "zeroed_values": comptes.valeurs_mises_a_zero,
        "provisional_share": provisional_share,
        "domain_outputs": domaine,
        "cells_at_height_ceiling": comptes.cellules_au_plafond,
        "edge_disks": comptes.disques_au_bord,
        "mixed_cells": comptes.cellules_melees,
        "recruits": comptes.recrues,
        "deaths": comptes.morts,
    });
    let mut texte = serde_json::to_string_pretty(&valeur).unwrap_or_default();
    texte.push('\n');
    texte
}
