//! Lecture des entrées de `simulate` (spec §2, §4 à §6, §9 à §11 ; plan M3a ; ADR 0001, 0002, 0004).
//!
//! Étape du BRIEF codée ici : BRIEF §4 (formats des fichiers lus : `trees_init`, `params/`,
//! rasters de `prepare`) et §6 (l'état initial de la simulation : chaque arbre dans sa cellule).
//!
//! Ce module lit, contrôle et assemble ; il ne simule rien. Dans l'ordre de [`Entrees::charger`] :
//!
//! 1. `config.yml` : bloc `simulate` complet (`level`, `seed`, `t0`, `years`), CRS EPSG:2154 ;
//! 2. `grid.tif` : la grille (module `grille`) ;
//! 3. les autres rasters (`h0`, `chm_date`, `site_potential`, `station_gradients` à trois bandes
//!    `trophic`, `hydric`, `bioclim`, `ser` avec `ser.csv`), chacun **aligné sur `grid.tif`**,
//!    sans « sans donnée » dans une cellule de la grille ;
//! 4. les paramètres : `growth`, `mortality`, `recruitment`, `height_curve` (contrat
//!    `dynamics_params`) et `allometry` (contrat `parameters`, modèles `hcb` et `cw`), plus
//!    `contracts/species.csv` ; chaque essence de `trees_init` doit y avoir ses paramètres
//!    (essence, puis groupe, puis `toutes_essences`) ;
//! 5. en mode `cohorts` (M5a, mission 062) : `params/regeneration.parquet` (contrat
//!    `dynamics.regeneration`), lu ligne par ligne ; les termes de chaque essence sont cherchés
//!    plus tard, quand les essences candidates sont connues ([`crate::semis::parametres_de`]) ;
//!    en mode `ifn_direct`, ce fichier n'est pas lu (il peut manquer) ;
//! 6. `trees_init/*.parquet` : chaque arbre est affecté à sa cellule
//!    (`ligne = floor((y_max − y) / 25)`, `colonne = floor((x − x_min) / 25)`) ; un arbre hors
//!    grille arrête tout.
//!
//! Aucune valeur par défaut : tout manque, toute incohérence est une erreur de code 2 dont le
//! message, en français, nomme le fichier et la cause. Les valeurs « sans donnée » d'une
//! cellule de la grille sont refusées plutôt que remplacées.
//!
//! Axes : x = est, y = nord, EPSG:2154.
//!
//! Règle de lisibilité (CLAUDE.md) : structures concrètes, aucun générique, aucune macro.

use std::collections::HashMap;
use std::fs::File;
use std::path::{Path, PathBuf};

use arrow_array::{Array, BooleanArray, Float64Array, LargeStringArray, RecordBatch, StringArray};
use arrow_schema::DataType;
use parquet::arrow::arrow_reader::ParquetRecordBatchReaderBuilder;

use crate::config::{self, ModeRecrutement, ReglagesSimulate};
use crate::erreurs::Erreur;
use crate::etat::{ArbreNouveau, EtatArbres};
use crate::geotiff::{self, Raster};
use crate::grille::Grille;
use crate::parametres::{lire_parquet, LigneParametre, Parametres, Referentiel};
use crate::semis::{LigneRegeneration, TERMES};

/// Les colonnes de `trees_init` (contrat `prepare/trees_init`), dans l'ordre du contrat.
pub const COLONNES_ARBRES: [&str; 9] = [
    "tree_id",
    "x",
    "y",
    "species",
    "d130",
    "h",
    "crown_area",
    "species_source",
    "d130_source",
];

/// Les colonnes de `params/allometry.parquet` (contrat `params/parameters`).
pub const COLONNES_ALLOMETRIE: [&str; 7] = [
    "species",
    "species_group",
    "model",
    "term",
    "value",
    "provisoire",
    "source",
];

/// Un arbre tel que lu dans `trees_init`, avant affectation à sa cellule.
#[derive(Debug, Clone, PartialEq)]
pub struct ArbreBrut {
    pub tree_id: String,
    /// Est, en m, EPSG:2154.
    pub x: f64,
    /// Nord, en m, EPSG:2154.
    pub y: f64,
    /// Code espar.
    pub species: String,
    /// cm.
    pub d130: f64,
    /// m.
    pub h: f64,
}

// ------------------------------------------------------------------------------------------
// Lecture Parquet

fn ouvrir_lots(chemin: &Path) -> Result<Vec<RecordBatch>, Erreur> {
    let nom = chemin.display().to_string();
    let fichier = File::open(chemin)
        .map_err(|e| Erreur::entree_refusee(format!("{nom} : lecture impossible ({e})")))?;
    let constructeur = ParquetRecordBatchReaderBuilder::try_new(fichier)
        .map_err(|e| Erreur::entree_refusee(format!("{nom} : Parquet illisible ({e})")))?;
    let lecteur = constructeur
        .build()
        .map_err(|e| Erreur::entree_refusee(format!("{nom} : Parquet illisible ({e})")))?;
    let mut lots: Vec<RecordBatch> = Vec::new();
    for lot in lecteur {
        lots.push(
            lot.map_err(|e| Erreur::entree_refusee(format!("{nom} : Parquet illisible ({e})")))?,
        );
    }
    Ok(lots)
}

/// Contrat `fieldsMatch: equal` : exactement les colonnes attendues, ni plus ni moins.
fn verifier_colonnes(
    lot: &RecordBatch,
    attendues: &[&str],
    nom: &str,
    contrat: &str,
) -> Result<(), Erreur> {
    let schema = lot.schema();
    for champ in schema.fields() {
        if !attendues.contains(&champ.name().as_str()) {
            return Err(Erreur::entree_refusee(format!(
                "{nom} : colonne « {} » hors du contrat {contrat}",
                champ.name()
            )));
        }
    }
    for colonne in attendues {
        if schema.index_of(colonne).is_err() {
            return Err(Erreur::entree_refusee(format!(
                "{nom} : colonne « {colonne} » absente (contrat {contrat})"
            )));
        }
    }
    Ok(())
}

fn type_refuse(colonne: &str, nom: &str, attendu: &str, lu: &DataType) -> Erreur {
    Erreur::entree_refusee(format!(
        "{nom} : la colonne « {colonne} » devrait être de type {attendu}, elle est {lu}"
    ))
}

fn colonne_texte(lot: &RecordBatch, colonne: &str, nom: &str) -> Result<Vec<Option<String>>, Erreur> {
    let rang = lot
        .schema()
        .index_of(colonne)
        .map_err(|_| Erreur::entree_refusee(format!("{nom} : colonne « {colonne} » absente")))?;
    let tableau = lot.column(rang);
    let mut valeurs: Vec<Option<String>> = Vec::with_capacity(tableau.len());
    if let Some(textes) = tableau.as_any().downcast_ref::<StringArray>() {
        for i in 0..textes.len() {
            valeurs.push(if textes.is_null(i) { None } else { Some(textes.value(i).to_string()) });
        }
    } else if let Some(textes) = tableau.as_any().downcast_ref::<LargeStringArray>() {
        for i in 0..textes.len() {
            valeurs.push(if textes.is_null(i) { None } else { Some(textes.value(i).to_string()) });
        }
    } else {
        return Err(type_refuse(colonne, nom, "texte (Utf8)", tableau.data_type()));
    }
    Ok(valeurs)
}

fn colonne_reel(lot: &RecordBatch, colonne: &str, nom: &str) -> Result<Vec<Option<f64>>, Erreur> {
    let rang = lot
        .schema()
        .index_of(colonne)
        .map_err(|_| Erreur::entree_refusee(format!("{nom} : colonne « {colonne} » absente")))?;
    let tableau = lot.column(rang);
    let reels = match tableau.as_any().downcast_ref::<Float64Array>() {
        Some(reels) => reels,
        None => return Err(type_refuse(colonne, nom, "réel (Float64)", tableau.data_type())),
    };
    let mut valeurs: Vec<Option<f64>> = Vec::with_capacity(reels.len());
    for i in 0..reels.len() {
        valeurs.push(if reels.is_null(i) { None } else { Some(reels.value(i)) });
    }
    Ok(valeurs)
}

fn colonne_booleen(lot: &RecordBatch, colonne: &str, nom: &str) -> Result<Vec<Option<bool>>, Erreur> {
    let rang = lot
        .schema()
        .index_of(colonne)
        .map_err(|_| Erreur::entree_refusee(format!("{nom} : colonne « {colonne} » absente")))?;
    let tableau = lot.column(rang);
    let booleens = match tableau.as_any().downcast_ref::<BooleanArray>() {
        Some(b) => b,
        None => return Err(type_refuse(colonne, nom, "booléen", tableau.data_type())),
    };
    let mut valeurs: Vec<Option<bool>> = Vec::with_capacity(booleens.len());
    for i in 0..booleens.len() {
        valeurs.push(if booleens.is_null(i) { None } else { Some(booleens.value(i)) });
    }
    Ok(valeurs)
}

fn vide(colonne: &str, nom: &str, ligne: usize) -> Erreur {
    Erreur::entree_refusee(format!(
        "{nom} : valeur obligatoire vide dans la colonne « {colonne} » (ligne {} du lot)",
        ligne + 1
    ))
}

// ------------------------------------------------------------------------------------------
// trees_init

/// Lit les arbres d'un fichier `trees_init/*.parquet` (contrat `prepare/trees_init`).
///
/// Code 2 : fichier illisible, colonne absente ou en trop, type inattendu, valeur vide,
/// `tree_id` vide, coordonnée non finie, `d130` ou `h` non fini ou ≤ 0.
pub fn lire_arbres_fichier(chemin: &Path) -> Result<Vec<ArbreBrut>, Erreur> {
    let nom = chemin.display().to_string();
    let mut arbres: Vec<ArbreBrut> = Vec::new();
    for lot in ouvrir_lots(chemin)? {
        verifier_colonnes(&lot, &COLONNES_ARBRES, &nom, "prepare/trees_init")?;
        let tree_id = colonne_texte(&lot, "tree_id", &nom)?;
        let x = colonne_reel(&lot, "x", &nom)?;
        let y = colonne_reel(&lot, "y", &nom)?;
        let species = colonne_texte(&lot, "species", &nom)?;
        let d130 = colonne_reel(&lot, "d130", &nom)?;
        let h = colonne_reel(&lot, "h", &nom)?;
        for i in 0..lot.num_rows() {
            let id = match &tree_id[i] {
                Some(id) if !id.is_empty() => id.clone(),
                _ => return Err(vide("tree_id", &nom, i)),
            };
            let essence = match &species[i] {
                Some(s) if !s.is_empty() => s.clone(),
                _ => return Err(vide("species", &nom, i)),
            };
            let (xi, yi) = match (x[i], y[i]) {
                (Some(xi), Some(yi)) if xi.is_finite() && yi.is_finite() => (xi, yi),
                _ => {
                    return Err(Erreur::entree_refusee(format!(
                        "{nom} : arbre « {id} » : coordonnées x, y absentes ou non finies"
                    )))
                }
            };
            let di = positif(d130[i], "d130", &id, &nom)?;
            let hi = positif(h[i], "h", &id, &nom)?;
            arbres.push(ArbreBrut {
                tree_id: id,
                x: xi,
                y: yi,
                species: essence,
                d130: di,
                h: hi,
            });
        }
    }
    Ok(arbres)
}

fn positif(valeur: Option<f64>, colonne: &str, id: &str, nom: &str) -> Result<f64, Erreur> {
    match valeur {
        Some(v) if v.is_finite() && v > 0.0 => Ok(v),
        Some(v) => Err(Erreur::entree_refusee(format!(
            "{nom} : arbre « {id} » : {colonne} = {v} ; il doit être fini et strictement positif"
        ))),
        None => Err(Erreur::entree_refusee(format!(
            "{nom} : arbre « {id} » : {colonne} vide"
        ))),
    }
}

/// Lit tous les `*.parquet` du dossier `trees_init/` (par ordre de nom). Code 2 si le dossier
/// est absent ou sans fichier Parquet.
pub fn lire_arbres(dossier: &Path) -> Result<Vec<ArbreBrut>, Erreur> {
    let nom = dossier.display().to_string();
    let entrees = std::fs::read_dir(dossier)
        .map_err(|e| Erreur::entree_refusee(format!("{nom} : dossier illisible ({e})")))?;
    let mut fichiers: Vec<PathBuf> = Vec::new();
    for entree in entrees {
        let entree = entree
            .map_err(|e| Erreur::entree_refusee(format!("{nom} : dossier illisible ({e})")))?;
        let chemin = entree.path();
        if chemin.extension().and_then(|e| e.to_str()) == Some("parquet") {
            fichiers.push(chemin);
        }
    }
    fichiers.sort();
    if fichiers.is_empty() {
        return Err(Erreur::entree_refusee(format!(
            "{nom} : aucun fichier .parquet (trees_init est vide)"
        )));
    }
    let mut arbres: Vec<ArbreBrut> = Vec::new();
    for fichier in fichiers {
        arbres.extend(lire_arbres_fichier(&fichier)?);
    }
    Ok(arbres)
}

/// Affecte chaque arbre à sa cellule : `cell_id = ligne × largeur + colonne`.
///
/// Code 2 pour le premier arbre hors grille (ou sur une cellule sans valeur dans `grid.tif`),
/// avec son `tree_id` et ses coordonnées.
pub fn affecter_aux_cellules(
    grille: &Grille,
    arbres: Vec<ArbreBrut>,
) -> Result<Vec<ArbreNouveau>, Erreur> {
    let mut affectes: Vec<ArbreNouveau> = Vec::with_capacity(arbres.len());
    for arbre in arbres {
        let cellule = match grille.cellule_de(arbre.x, arbre.y) {
            Ok(cellule) => cellule,
            Err(erreur) => {
                return Err(Erreur::entree_refusee(format!(
                    "trees_init : arbre « {} » : {}",
                    arbre.tree_id, erreur.message
                )))
            }
        };
        affectes.push(ArbreNouveau {
            tree_id: arbre.tree_id,
            espece: arbre.species,
            cellule,
            x: arbre.x,
            y: arbre.y,
            d130: arbre.d130,
            h: arbre.h,
        });
    }
    Ok(affectes)
}

// ------------------------------------------------------------------------------------------
// Paramètres

/// Lit `params/allometry.parquet` (contrat `params/parameters`, sans colonnes `variable` ni `x`)
/// en lignes du format long, prêtes pour [`Parametres::depuis_lignes`].
///
/// Code 2 : colonne absente ou en trop, type inattendu, valeur obligatoire vide.
pub fn lire_allometrie(chemin: &Path) -> Result<Vec<LigneParametre>, Erreur> {
    let nom = chemin.display().to_string();
    let mut lignes: Vec<LigneParametre> = Vec::new();
    for lot in ouvrir_lots(chemin)? {
        verifier_colonnes(&lot, &COLONNES_ALLOMETRIE, &nom, "params/parameters")?;
        let species = colonne_texte(&lot, "species", &nom)?;
        let groupe = colonne_texte(&lot, "species_group", &nom)?;
        let model = colonne_texte(&lot, "model", &nom)?;
        let term = colonne_texte(&lot, "term", &nom)?;
        let value = colonne_reel(&lot, "value", &nom)?;
        let provisoire = colonne_booleen(&lot, "provisoire", &nom)?;
        let source = colonne_texte(&lot, "source", &nom)?;
        for i in 0..lot.num_rows() {
            lignes.push(LigneParametre {
                species: species[i].clone(),
                species_group: groupe[i].clone(),
                model: model[i].clone().filter(|m| !m.is_empty()).ok_or_else(|| vide("model", &nom, i))?,
                term: term[i].clone().filter(|t| !t.is_empty()).ok_or_else(|| vide("term", &nom, i))?,
                variable: None,
                x: None,
                value: value[i].ok_or_else(|| vide("value", &nom, i))?,
                provisoire: provisoire[i].ok_or_else(|| vide("provisoire", &nom, i))?,
                source: source[i].clone().filter(|s| !s.is_empty()).ok_or_else(|| vide("source", &nom, i))?,
            });
        }
    }
    Ok(lignes)
}

/// Les colonnes de `params/regeneration.parquet` (contrat `dynamics.regeneration`).
pub const COLONNES_REGENERATION: [&str; 7] = [
    "species",
    "species_group",
    "term",
    "value",
    "unit",
    "provisoire",
    "source",
];

/// Lit `params/regeneration.parquet` (contrat `dynamics.regeneration`, mission 060).
///
/// Code 2 : fichier absent ou illisible, colonne absente ou en trop, type inattendu, valeur
/// obligatoire vide, terme hors de la liste fermée du contrat, ni essence ni groupe, groupe
/// inconnu, valeur non finie.
pub fn lire_regeneration(chemin: &Path) -> Result<Vec<LigneRegeneration>, Erreur> {
    let nom = chemin.display().to_string();
    if !chemin.is_file() {
        return Err(Erreur::entree_refusee(format!(
            "{nom} absent : le mode cohorts (simulate.recruitment) exige les paramètres de régénération \
             (contrat dynamics.regeneration) ; aucune valeur par défaut"
        )));
    }
    let mut lignes: Vec<LigneRegeneration> = Vec::new();
    for lot in ouvrir_lots(chemin)? {
        verifier_colonnes(&lot, &COLONNES_REGENERATION, &nom, "dynamics.regeneration")?;
        let species = colonne_texte(&lot, "species", &nom)?;
        let groupe = colonne_texte(&lot, "species_group", &nom)?;
        let term = colonne_texte(&lot, "term", &nom)?;
        let value = colonne_reel(&lot, "value", &nom)?;
        let unit = colonne_texte(&lot, "unit", &nom)?;
        let provisoire = colonne_booleen(&lot, "provisoire", &nom)?;
        let source = colonne_texte(&lot, "source", &nom)?;
        for i in 0..lot.num_rows() {
            let terme = term[i].clone().filter(|t| !t.is_empty()).ok_or_else(|| vide("term", &nom, i))?;
            if !TERMES.iter().any(|(t, _)| *t == terme) {
                return Err(Erreur::entree_refusee(format!(
                    "{nom} : terme « {terme} » hors de la liste fermée du contrat dynamics.regeneration"
                )));
            }
            let essence = species[i].clone().filter(|s| !s.is_empty());
            let groupe_ligne = groupe[i].clone().filter(|g| !g.is_empty());
            if essence.is_none() && groupe_ligne.is_none() {
                return Err(Erreur::entree_refusee(format!(
                    "{nom} : terme « {terme} » sans essence (species) ni groupe (species_group)"
                )));
            }
            if let Some(g) = &groupe_ligne {
                if g != "feuillu" && g != "resineux" && g != crate::parametres::TOUTES_ESSENCES {
                    return Err(Erreur::entree_refusee(format!(
                        "{nom} : terme « {terme} » : groupe « {g} » ni feuillu, ni resineux, ni toutes_essences"
                    )));
                }
            }
            let valeur = value[i].ok_or_else(|| vide("value", &nom, i))?;
            if !valeur.is_finite() {
                return Err(Erreur::entree_refusee(format!(
                    "{nom} : terme « {terme} » : valeur non finie ({valeur})"
                )));
            }
            lignes.push(LigneRegeneration {
                species: essence,
                species_group: groupe_ligne,
                term: terme,
                value: valeur,
                unit: unit[i].clone().filter(|u| !u.is_empty()).ok_or_else(|| vide("unit", &nom, i))?,
                provisoire: provisoire[i].ok_or_else(|| vide("provisoire", &nom, i))?,
                source: source[i].clone().filter(|s| !s.is_empty()).ok_or_else(|| vide("source", &nom, i))?,
            });
        }
    }
    Ok(lignes)
}

/// Tous les jeux de paramètres lus.
#[derive(Debug, Clone, PartialEq)]
pub struct JeuxDeParametres {
    pub croissance: Parametres,
    pub mortalite: Parametres,
    pub recrutement: Parametres,
    pub courbe_hauteur: Parametres,
    pub allometrie: Parametres,
}

/// Lit les cinq fichiers de `params/` d'une zone. Chaque erreur nomme le fichier.
pub fn lire_parametres(dossier_params: &Path) -> Result<JeuxDeParametres, Erreur> {
    let dynamique = |nom: &str| -> Result<Parametres, Erreur> {
        let chemin = dossier_params.join(nom);
        let lignes = lire_parquet(&chemin)?;
        Parametres::depuis_lignes(&lignes).map_err(|e| avec_fichier(e, &chemin))
    };
    let chemin_allometrie = dossier_params.join("allometry.parquet");
    let allometrie = Parametres::depuis_lignes(&lire_allometrie(&chemin_allometrie)?)
        .map_err(|e| avec_fichier(e, &chemin_allometrie))?;
    Ok(JeuxDeParametres {
        croissance: dynamique("growth.parquet")?,
        mortalite: dynamique("mortality.parquet")?,
        recrutement: dynamique("recruitment.parquet")?,
        courbe_hauteur: dynamique("height_curve.parquet")?,
        allometrie,
    })
}

fn avec_fichier(erreur: Erreur, chemin: &Path) -> Erreur {
    Erreur {
        code: erreur.code,
        message: format!("{} : {}", chemin.display(), erreur.message),
    }
}

/// Les essences distinctes des arbres, triées.
pub fn essences_des_arbres(arbres: &[ArbreBrut]) -> Vec<String> {
    let mut essences: Vec<String> = arbres.iter().map(|a| a.species.clone()).collect();
    essences.sort();
    essences.dedup();
    essences
}

/// Vérifie que chaque essence a ses paramètres de croissance, de mortalité, de hauteur relative,
/// de courbe de hauteur (Chapman-Richards ou Korf), `hcb` et `cw` (essence, puis groupe, puis
/// `toutes_essences`). Code 2 pour la première essence qui manque, avec le modèle.
///
/// Le recrutement n'est pas vérifié ici : il porte sur des essences candidates, pas sur celles
/// des arbres (pas de recrutement, pas de recrue ; voir le pas annuel, mission 037).
pub fn verifier_parametres_des_essences(
    essences: &[String],
    jeux: &JeuxDeParametres,
    referentiel: &Referentiel,
) -> Result<(), Erreur> {
    for essence in essences {
        jeux.croissance.chercher("growth_gam", essence, referentiel)?;
        jeux.mortalite.chercher("mortality_gam", essence, referentiel)?;
        jeux.courbe_hauteur.chercher("relative_height_gam", essence, referentiel)?;
        let chapman = jeux.courbe_hauteur.chercher("chapman_richards", essence, referentiel);
        if chapman.is_err() {
            // Pas de Chapman-Richards : il faut au moins Korf (hêtre 09, décision Q1).
            jeux.courbe_hauteur.chercher("korf", essence, referentiel)?;
        }
        let hcb = jeux.allometrie.chercher("hcb", essence, referentiel)?.0;
        for terme in ["CR_a", "CR_b", "CR_min", "CR_max"] {
            hcb.scalaire(terme)?;
        }
        let cw = jeux.allometrie.chercher("cw", essence, referentiel)?.0;
        for terme in ["R_a", "R_b"] {
            cw.scalaire(terme)?;
        }
    }
    Ok(())
}

// ------------------------------------------------------------------------------------------
// Rasters

/// La table de `ser.tif` : valeur du raster → code de SER sous-jacente (colonne `name`).
#[derive(Debug, Clone, PartialEq, Default)]
pub struct TableSer {
    noms: HashMap<u32, String>,
}

impl TableSer {
    /// Lit le texte de `ser.csv` (colonnes `value`, `name`, `alluvium_code`).
    /// Code 2 : colonne absente, valeur non entière, `name` vide, valeur en double.
    pub fn depuis_texte(texte: &str, nom: &str) -> Result<TableSer, Erreur> {
        let mut lignes = texte.lines();
        let entete = match lignes.next() {
            Some(ligne) => champs_csv(ligne),
            None => return Err(Erreur::entree_refusee(format!("{nom} : fichier vide"))),
        };
        let rang_valeur = entete.iter().position(|c| c == "value").ok_or_else(|| {
            Erreur::entree_refusee(format!("{nom} : colonne « value » absente"))
        })?;
        let rang_nom = entete.iter().position(|c| c == "name").ok_or_else(|| {
            Erreur::entree_refusee(format!("{nom} : colonne « name » absente"))
        })?;
        let mut noms: HashMap<u32, String> = HashMap::new();
        for (i, ligne) in lignes.enumerate() {
            if ligne.trim().is_empty() {
                continue;
            }
            let champs = champs_csv(ligne);
            if champs.len() <= rang_valeur.max(rang_nom) {
                return Err(Erreur::entree_refusee(format!(
                    "{nom}, ligne {} : trop peu de champs",
                    i + 2
                )));
            }
            let valeur: u32 = champs[rang_valeur].trim().parse().map_err(|_| {
                Erreur::entree_refusee(format!(
                    "{nom}, ligne {} : value « {} » n'est pas un entier",
                    i + 2,
                    champs[rang_valeur]
                ))
            })?;
            if champs[rang_nom].is_empty() {
                return Err(Erreur::entree_refusee(format!(
                    "{nom}, ligne {} : name vide",
                    i + 2
                )));
            }
            if noms.insert(valeur, champs[rang_nom].clone()).is_some() {
                return Err(Erreur::entree_refusee(format!(
                    "{nom} : value {valeur} en double"
                )));
            }
        }
        Ok(TableSer { noms })
    }

    /// Lit un fichier `ser.csv`.
    pub fn lire(chemin: &Path) -> Result<TableSer, Erreur> {
        let nom = chemin.display().to_string();
        let texte = std::fs::read_to_string(chemin)
            .map_err(|e| Erreur::entree_refusee(format!("{nom} : lecture impossible ({e})")))?;
        TableSer::depuis_texte(&texte, &nom)
    }

    /// Le code de SER d'une valeur du raster.
    pub fn nom(&self, valeur: u32) -> Option<&str> {
        self.noms.get(&valeur).map(|n| n.as_str())
    }
}

/// Découpe une ligne CSV : champs séparés par des virgules, guillemets doubles retirés
/// (aucune virgule dans un champ guillemeté dans nos tables).
fn champs_csv(ligne: &str) -> Vec<String> {
    ligne
        .split(',')
        .map(|c| c.trim().trim_matches('"').to_string())
        .collect()
}

/// Les couches de la station et de la hauteur, une valeur par cellule (ordre de `cell_id`).
#[derive(Debug, Clone, PartialEq)]
pub struct Couches {
    /// Hauteur dominante de la cellule à la date de vol, en m (`h0.tif`).
    pub h0: Vec<f32>,
    /// Date de vol, en jours depuis le 1970-01-01 (`chm_date.tif`).
    pub chm_date: Vec<f32>,
    /// Plafond de hauteur de la station, en m (`site_potential.tif`).
    pub h_pot: Vec<f32>,
    /// Gradient trophique (`station_gradients.tif`, bande 1).
    pub trophic: Vec<f32>,
    /// Gradient hydrique (bande 2).
    pub hydric: Vec<f32>,
    /// Gradient bioclimatique (bande 3).
    pub bioclim: Vec<f32>,
    /// Valeur de `ser.tif` par cellule.
    pub ser: Vec<u32>,
    /// La table des valeurs de `ser.tif`.
    pub table_ser: TableSer,
}

impl Couches {
    /// Le code de SER d'une cellule (`name` de `ser.csv`).
    pub fn code_ser(&self, cell_id: u64) -> Option<&str> {
        self.table_ser.nom(self.ser[cell_id as usize])
    }
}

/// Contrôle un raster (alignement sur la grille, nombre de bandes, aucun « sans donnée » ni valeur
/// non finie dans une cellule de la grille) et rend ses bandes.
fn bandes_controlees(
    grille: &Grille,
    raster: Raster,
    nom: &str,
    bandes_attendues: usize,
) -> Result<Vec<Vec<f32>>, Erreur> {
    grille.verifier_alignement(&raster, nom)?;
    if raster.bandes.len() != bandes_attendues {
        return Err(Erreur::entree_refusee(format!(
            "{nom} : {} bande(s) au lieu de {bandes_attendues}",
            raster.bandes.len()
        )));
    }
    for (numero, bande) in raster.bandes.iter().enumerate() {
        let mut manquantes: u64 = 0;
        let mut premiere: Option<usize> = None;
        for (cellule, valeur) in bande.iter().enumerate() {
            if grille.valide[cellule] && (raster.est_nodata(*valeur) || !valeur.is_finite()) {
                manquantes += 1;
                if premiere.is_none() {
                    premiere = Some(cellule);
                }
            }
        }
        if let Some(cellule) = premiere {
            return Err(Erreur::entree_refusee(format!(
                "{nom} : bande {} : {manquantes} cellule(s) de la grille sans donnée (première : cell_id {cellule}) ; rien n'est deviné",
                numero + 1
            )));
        }
    }
    Ok(raster.bandes)
}

/// Les rasters lus de `prepare`, avant contrôle.
pub struct Rasters {
    pub h0: Raster,
    pub chm_date: Raster,
    pub site_potential: Raster,
    pub station_gradients: Raster,
    pub ser: Raster,
}

/// Contrôle l'alignement et la complétude des rasters et en tire les couches par cellule.
///
/// Code 2 : raster non aligné sur `grid.tif`, mauvais nombre de bandes, cellule de la grille sans
/// donnée, valeur de `ser.tif` absente de `ser.csv` ou non entière.
pub fn assembler_couches(
    grille: &Grille,
    rasters: Rasters,
    table_ser: TableSer,
) -> Result<Couches, Erreur> {
    let mut h0 = bandes_controlees(grille, rasters.h0, "h0.tif", 1)?;
    let mut chm_date = bandes_controlees(grille, rasters.chm_date, "chm_date.tif", 1)?;
    let mut h_pot = bandes_controlees(grille, rasters.site_potential, "site_potential.tif", 1)?;
    let mut gradients = bandes_controlees(grille, rasters.station_gradients, "station_gradients.tif", 3)?;
    let mut ser_bandes = bandes_controlees(grille, rasters.ser, "ser.tif", 1)?;
    let ser_flottants = ser_bandes.remove(0);
    let mut ser: Vec<u32> = Vec::with_capacity(ser_flottants.len());
    for (cellule, valeur) in ser_flottants.iter().enumerate() {
        if !grille.valide[cellule] {
            ser.push(0);
            continue;
        }
        if valeur.fract() != 0.0 || *valeur < 0.0 {
            return Err(Erreur::entree_refusee(format!(
                "ser.tif : valeur {valeur} non entière à la cellule {cellule}"
            )));
        }
        let entier = *valeur as u32;
        if table_ser.nom(entier).is_none() {
            return Err(Erreur::entree_refusee(format!(
                "ser.tif : valeur {entier} (cellule {cellule}) absente de ser.csv"
            )));
        }
        ser.push(entier);
    }
    // Les bandes de station_gradients sont dans l'ordre du contrat : trophic, hydric, bioclim.
    let bioclim = gradients.remove(2);
    let hydric = gradients.remove(1);
    let trophic = gradients.remove(0);
    Ok(Couches {
        h0: h0.remove(0),
        chm_date: chm_date.remove(0),
        h_pot: h_pot.remove(0),
        trophic,
        hydric,
        bioclim,
        ser,
        table_ser,
    })
}

// ------------------------------------------------------------------------------------------
// Tout ensemble

/// Toutes les entrées de `simulate`, lues et contrôlées.
#[derive(Debug, Clone, PartialEq)]
pub struct Entrees {
    pub reglages: ReglagesSimulate,
    pub grille: Grille,
    pub couches: Couches,
    pub referentiel: Referentiel,
    pub parametres: JeuxDeParametres,
    /// L'état initial : arbres triés par `tree_id`, numérotés, chacun dans sa cellule.
    pub arbres: EtatArbres,
    /// Le mode de recrutement (`simulate.recruitment`, M5a).
    pub recrutement: ModeRecrutement,
    /// Les lignes de `params/regeneration.parquet` (mode `cohorts` ; vide en `ifn_direct`).
    pub regeneration: Vec<LigneRegeneration>,
}

impl Entrees {
    /// Lit et contrôle tout.
    ///
    /// - `chemin_config` : `config.yml` ;
    /// - `dossier_zone` : le dossier de la zone (`data/<zone>/`), qui contient `grid.tif`,
    ///   `h0.tif`… `trees_init/` et `params/` ;
    /// - `chemin_especes` : `contracts/species.csv`.
    ///
    /// Code 2 pour toute entrée absente, hors contrat, non alignée ou incohérente.
    pub fn charger(
        chemin_config: &Path,
        dossier_zone: &Path,
        chemin_especes: &Path,
    ) -> Result<Entrees, Erreur> {
        let config = config::lire(chemin_config).map_err(Erreur::entree_refusee)?;
        config.verifier_crs()?;
        let reglages = config.reglages_simulate()?;
        let recrutement = config.recrutement()?;

        let raster_grille = geotiff::lire(&dossier_zone.join("grid.tif"))?;
        let grille = Grille::depuis_raster(
            &raster_grille,
            "grid.tif",
            f64::from(config.grid.resolution_m),
        )?;
        let lire_raster = |nom: &str| -> Result<Raster, Erreur> {
            Ok(geotiff::lire(&dossier_zone.join(nom))?)
        };
        let rasters = Rasters {
            h0: lire_raster("h0.tif")?,
            chm_date: lire_raster("chm_date.tif")?,
            site_potential: lire_raster("site_potential.tif")?,
            station_gradients: lire_raster("station_gradients.tif")?,
            ser: lire_raster("ser.tif")?,
        };
        let table_ser = TableSer::lire(&dossier_zone.join("ser.csv"))?;
        let couches = assembler_couches(&grille, rasters, table_ser)?;

        let referentiel = Referentiel::lire(chemin_especes)?;
        let parametres = lire_parametres(&dossier_zone.join("params"))?;
        let regeneration = match recrutement {
            ModeRecrutement::IfnDirect => Vec::new(),
            ModeRecrutement::Cohortes(_) => {
                lire_regeneration(&dossier_zone.join("params").join("regeneration.parquet"))?
            }
        };

        let brutes = lire_arbres(&dossier_zone.join("trees_init"))?;
        verifier_parametres_des_essences(&essences_des_arbres(&brutes), &parametres, &referentiel)?;
        let affectes = affecter_aux_cellules(&grille, brutes)?;
        let arbres = EtatArbres::depuis_initiaux(affectes)?;

        Ok(Entrees {
            reglages,
            grille,
            couches,
            referentiel,
            parametres,
            arbres,
            recrutement,
            regeneration,
        })
    }
}
