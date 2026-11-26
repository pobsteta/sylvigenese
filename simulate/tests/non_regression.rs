//! Non-régression et contenu des sorties de `simulate` (mission 038 ; src/sorties.rs).
//!
//! Une **zone d'essai construite en mémoire** ([`zone_d_essai`]) passe par tout le chemin de
//! `sorties::simuler_et_ecrire` (t0 puis les pas, Parquet, flags, run.json) dans un dossier
//! temporaire. Rien ne dépend des sorties ignorées par git ni de R : le bout en bout sur le jeu
//! fictif est dans `tests/integration.rs`.
//!
//! Coordonnées : x = est, y = nord, en m, EPSG:2154. Coin nord-ouest de la grille d'essai :
//! (700 000 ; 6 501 000), cellules de 25 m, `cell_id` = ligne × largeur + colonne, ligne 0 au
//! nord ; le point (700 012,5 ; 6 500 987,5) est le centre de la cellule 0.
//!
//! Les paramètres d'essai (source « essai ») ne valent rien d'écologique : ils servent à faire
//! tourner le moteur. La référence figée (`tests/reference/resume_zone_essai.csv`) est un
//! résumé par année et essence, en 17 chiffres significatifs, relu à 1e-9 près : elle garde le
//! moteur de changer sans qu'on le veuille. Pour la refiger après un changement voulu et
//! expliqué : `SIMULATE_FIGER_REFERENCE=1 cargo test --locked --test non_regression`.

#![allow(dead_code)]

use std::collections::BTreeMap;
use std::fs::File;
use std::path::{Path, PathBuf};

use arrow_array::{Array, Float64Array, Int64Array, RecordBatch, StringArray};
use parquet::arrow::arrow_reader::ParquetRecordBatchReaderBuilder;

use simulate::alea::{u, Sorte};
use simulate::config::{NiveauSimulation, ReglagesSimulate};
use simulate::entrees::{Couches, Entrees, JeuxDeParametres, TableSer};
use simulate::etat::{ArbreNouveau, EtatArbres};
use simulate::grille::Grille;
use simulate::parametres::{LigneParametre, Parametres, Referentiel};
use simulate::sorties::{self, Lancement};

pub const X0: f64 = 700_000.0;
pub const Y0: f64 = 6_501_000.0;
pub const LARGEUR: usize = 8;
pub const HAUTEUR: usize = 6;
pub const T0: i32 = 2022;

// ------------------------------------------------------------------------------------------
// La zone d'essai

fn ligne(
    species: Option<&str>,
    model: &str,
    term: &str,
    variable: Option<&str>,
    x: Option<f64>,
    value: f64,
) -> LigneParametre {
    LigneParametre {
        species: species.map(|s| s.to_string()),
        species_group: if species.is_none() {
            Some("toutes_essences".to_string())
        } else {
            None
        },
        model: model.to_string(),
        term: term.to_string(),
        variable: variable.map(|s| s.to_string()),
        x,
        value,
        provisoire: true,
        source: "essai".to_string(),
    }
}

/// Les cinq jeux d'essai : croissance et mortalité qui dépendent de d130, ba_plot et trophic ;
/// recrutement selon ba_plot ; hauteur relative en rel_d ; Chapman-Richards pour 03, Korf avec
/// son point de départ (mission 040 : t_ref0 6 ans, h_ref0 1,375 m, age_ref 100 ans) pour 09.
pub fn jeux_d_essai(avec_point_de_depart_korf: bool) -> JeuxDeParametres {
    let croissance = vec![
        ligne(None, "growth_gam", "intercept", None, None, 0.2_f64.ln()),
        ligne(
            None,
            "growth_gam",
            "s(d130)[01]",
            Some("d130"),
            Some(10.0),
            0.1,
        ),
        ligne(
            None,
            "growth_gam",
            "s(d130)[02]",
            Some("d130"),
            Some(40.0),
            0.0,
        ),
        ligne(
            None,
            "growth_gam",
            "s(d130)[03]",
            Some("d130"),
            Some(70.0),
            -0.3,
        ),
        ligne(
            None,
            "growth_gam",
            "s(ba_plot)[01]",
            Some("ba_plot"),
            Some(0.0),
            0.2,
        ),
        ligne(
            None,
            "growth_gam",
            "s(ba_plot)[02]",
            Some("ba_plot"),
            Some(40.0),
            -0.4,
        ),
        ligne(
            None,
            "growth_gam",
            "s(trophic)[01]",
            Some("trophic"),
            Some(3.0),
            -0.1,
        ),
        ligne(
            None,
            "growth_gam",
            "s(trophic)[02]",
            Some("trophic"),
            Some(6.0),
            0.1,
        ),
    ];
    let mortalite = vec![
        ligne(
            None,
            "mortality_gam",
            "intercept",
            None,
            None,
            0.015_f64.ln(),
        ),
        ligne(
            None,
            "mortality_gam",
            "s(bal)[01]",
            Some("bal"),
            Some(0.0),
            -0.2,
        ),
        ligne(
            None,
            "mortality_gam",
            "s(bal)[02]",
            Some("bal"),
            Some(30.0),
            0.6,
        ),
    ];
    let recrutement = vec![
        ligne(
            None,
            "recruitment_gam",
            "intercept",
            None,
            None,
            12.0_f64.ln(),
        ),
        ligne(
            None,
            "recruitment_gam",
            "s(ba_plot)[01]",
            Some("ba_plot"),
            Some(0.0),
            0.3,
        ),
        ligne(
            None,
            "recruitment_gam",
            "s(ba_plot)[02]",
            Some("ba_plot"),
            Some(50.0),
            -0.8,
        ),
    ];
    let mut hauteur = vec![
        ligne(None, "relative_height_gam", "intercept", None, None, 0.9),
        ligne(
            None,
            "relative_height_gam",
            "s(rel_d)[01]",
            Some("rel_d"),
            Some(0.0),
            -0.5,
        ),
        ligne(
            None,
            "relative_height_gam",
            "s(rel_d)[02]",
            Some("rel_d"),
            Some(2.0),
            0.5,
        ),
    ];
    for (rang, a) in [38.0, 34.0, 29.0, 24.0, 20.0].iter().enumerate() {
        hauteur.push(ligne(
            Some("03"),
            "chapman_richards",
            &format!("A_class{}", rang + 1),
            None,
            None,
            *a,
        ));
    }
    hauteur.push(ligne(
        Some("03"),
        "chapman_richards",
        "k",
        None,
        None,
        0.022,
    ));
    hauteur.push(ligne(Some("03"), "chapman_richards", "p", None, None, 1.5));
    hauteur.push(ligne(Some("09"), "korf", "a", None, None, 56.45));
    hauteur.push(ligne(Some("09"), "korf", "b", None, None, 0.03));
    hauteur.push(ligne(Some("09"), "korf", "c", None, None, 1.235));
    if avec_point_de_depart_korf {
        hauteur.push(ligne(Some("09"), "korf", "t_ref0", None, None, 6.0));
        hauteur.push(ligne(Some("09"), "korf", "h_ref0", None, None, 1.375));
        hauteur.push(ligne(Some("09"), "korf", "age_ref", None, None, 100.0));
    }
    for (rang, p_f) in [0.555, 0.47875, 0.4025, 0.32625, 0.25].iter().enumerate() {
        hauteur.push(ligne(
            Some("09"),
            "korf",
            &format!("p_f_class{}", rang + 1),
            None,
            None,
            *p_f,
        ));
    }
    let allometrie = vec![
        ligne(None, "hcb", "CR_a", None, None, 1.1),
        ligne(None, "hcb", "CR_b", None, None, -0.15),
        ligne(None, "hcb", "CR_min", None, None, 0.2),
        ligne(None, "hcb", "CR_max", None, None, 0.9),
        ligne(None, "cw", "R_a", None, None, -0.3),
        ligne(None, "cw", "R_b", None, None, 0.55),
    ];
    JeuxDeParametres {
        croissance: Parametres::depuis_lignes(&croissance).unwrap(),
        mortalite: Parametres::depuis_lignes(&mortalite).unwrap(),
        recrutement: Parametres::depuis_lignes(&recrutement).unwrap(),
        courbe_hauteur: Parametres::depuis_lignes(&hauteur).unwrap(),
        allometrie: Parametres::depuis_lignes(&allometrie).unwrap(),
    }
}

pub fn referentiel() -> Referentiel {
    let chemin = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../contracts/species.csv");
    Referentiel::lire(&chemin).unwrap()
}

/// Une zone de 8 × 6 cellules : la dernière (cell_id 47) hors de grid.tif ; station et H_dom qui
/// varient ; 600 arbres de 03 (à l'ouest) et 09 (à l'est) dans les cellules de la grille.
pub fn zone_d_essai(years: u32) -> Entrees {
    let n = LARGEUR * HAUTEUR;
    let mut valide = vec![true; n];
    valide[n - 1] = false;
    let grille = Grille {
        largeur: LARGEUR,
        hauteur: HAUTEUR,
        origine_x: X0,
        origine_y: Y0,
        pas: 25.0,
        valide,
    };
    let mut couches = Couches {
        h0: Vec::new(),
        chm_date: Vec::new(),
        h_pot: Vec::new(),
        trophic: Vec::new(),
        hydric: Vec::new(),
        bioclim: Vec::new(),
        ser: Vec::new(),
        table_ser: TableSer::depuis_texte("value,name,alluvium_code\n1,B10,\n", "ser.csv d'essai")
            .unwrap(),
    };
    for cellule in 0..n {
        couches.h0.push(9.0 + (cellule % 7) as f32 * 2.5);
        // 2021-07-01 (18 809 jours) ou 2022-06-21 (19 164 jours), avant la fin de t0 = 2022.
        couches
            .chm_date
            .push(if cellule % 2 == 0 { 18_809.0 } else { 19_164.0 });
        couches.h_pot.push(24.0 + (cellule % 5) as f32 * 3.0);
        couches.trophic.push(3.5 + (cellule % 6) as f32 * 0.5);
        couches.hydric.push(-1.0);
        couches.bioclim.push(0.05);
        couches.ser.push(1);
    }
    let mut arbres = Vec::new();
    for i in 0..600u64 {
        let ux = u(7, 0, i, 1, Sorte::RecrueX);
        let uy = u(7, 0, i, 1, Sorte::RecrueY);
        let ud = u(7, 0, i, 2, Sorte::Mort);
        // Rester hors de la cellule 47 (coin sud-est) : y au-dessus de la dernière ligne.
        let x = X0 + ux * 200.0;
        let y = Y0 - uy * 125.0;
        let colonne = ((x - X0) / 25.0).floor() as u64;
        let ligne_grille = ((Y0 - y) / 25.0).floor() as u64;
        let espece = if colonne < 4 { "03" } else { "09" };
        arbres.push(ArbreNouveau {
            tree_id: format!("t{i:04}"),
            espece: espece.to_string(),
            cellule: ligne_grille * LARGEUR as u64 + colonne,
            x,
            y,
            d130: 8.0 + ud * 45.0,
            h: 7.0 + ud * 18.0,
        });
    }
    Entrees {
        reglages: ReglagesSimulate {
            niveau: NiveauSimulation::Massif,
            seed: 20_261_125,
            t0: T0,
            years,
            threads: None,
        },
        grille,
        couches,
        referentiel: referentiel(),
        parametres: jeux_d_essai(true),
        arbres: EtatArbres::depuis_initiaux(arbres).unwrap(),
        recrutement: simulate::config::ModeRecrutement::IfnDirect,
        regeneration: Vec::new(),
        ser: None,
    }
}

pub fn lancement(threads: usize) -> Lancement {
    Lancement {
        threads,
        memoire_disponible: 1 << 34,
        inject_nan: None,
        zone: "zone_essai".to_string(),
        config_sha256: "0".repeat(64),
    }
}

/// Un dossier temporaire neuf (absent) propre au test.
pub fn dossier_neuf(nom: &str) -> PathBuf {
    let dossier = std::env::temp_dir().join(format!("simulate-038-{}-{nom}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dossier);
    dossier
}

pub fn lire_parquet(chemin: &Path) -> RecordBatch {
    let fichier = File::open(chemin).unwrap_or_else(|e| panic!("{} : {e}", chemin.display()));
    let constructeur = ParquetRecordBatchReaderBuilder::try_new(fichier).unwrap();
    // Un seul lot : la taille de lot vaut le nombre de lignes du fichier (au moins 1).
    let lignes = constructeur.metadata().file_metadata().num_rows().max(1) as usize;
    let schema = constructeur.schema().clone();
    let mut lecteur = constructeur.with_batch_size(lignes).build().unwrap();
    match lecteur.next() {
        Some(lot) => {
            assert!(
                lecteur.next().is_none(),
                "plusieurs lots dans {}",
                chemin.display()
            );
            lot.unwrap()
        }
        None => RecordBatch::new_empty(schema),
    }
}

pub fn chaines(lot: &RecordBatch, nom: &str) -> Vec<String> {
    let colonne = lot
        .column_by_name(nom)
        .unwrap_or_else(|| panic!("colonne {nom} absente"));
    let texte = colonne.as_any().downcast_ref::<StringArray>().unwrap();
    (0..texte.len())
        .map(|i| texte.value(i).to_string())
        .collect()
}

pub fn nombres(lot: &RecordBatch, nom: &str) -> Vec<Option<f64>> {
    let colonne = lot
        .column_by_name(nom)
        .unwrap_or_else(|| panic!("colonne {nom} absente"));
    let valeurs = colonne.as_any().downcast_ref::<Float64Array>().unwrap();
    (0..valeurs.len())
        .map(|i| {
            if valeurs.is_null(i) {
                None
            } else {
                Some(valeurs.value(i))
            }
        })
        .collect()
}

pub fn entiers(lot: &RecordBatch, nom: &str) -> Vec<i64> {
    let colonne = lot
        .column_by_name(nom)
        .unwrap_or_else(|| panic!("colonne {nom} absente"));
    let valeurs = colonne.as_any().downcast_ref::<Int64Array>().unwrap();
    (0..valeurs.len()).map(|i| valeurs.value(i)).collect()
}

pub fn partition(dossier: &Path, sorte: &str, annee: i32) -> RecordBatch {
    lire_parquet(
        &dossier
            .join(sorte)
            .join(format!("year={annee}"))
            .join("part-00000.parquet"),
    )
}

// ------------------------------------------------------------------------------------------
// Le résumé figé

/// Par année et essence : vivants, morts de l'année, recrues de l'année, sommes de d130, h,
/// hcb, cw (vivants), x et y (vivants). Clé (année, essence), valeurs dans cet ordre.
fn resume(dossier: &Path, t0: i32, years: u32) -> BTreeMap<(i32, String), Vec<f64>> {
    let mut resume: BTreeMap<(i32, String), Vec<f64>> = BTreeMap::new();
    for annee in t0..=t0 + years as i32 {
        let lot = partition(dossier, "trees", annee);
        let ids = chaines(&lot, "tree_id");
        let especes = chaines(&lot, "species");
        let statuts = chaines(&lot, "status");
        let colonnes: Vec<Vec<Option<f64>>> = ["d130", "h", "hcb", "cw", "x", "y"]
            .iter()
            .map(|c| nombres(&lot, c))
            .collect();
        let suffixe = format!("_{annee}_");
        for rang in 0..ids.len() {
            let valeurs = resume
                .entry((annee, especes[rang].clone()))
                .or_insert(vec![0.0; 9]);
            if statuts[rang] == "alive" {
                valeurs[0] += 1.0;
                for (k, colonne) in colonnes.iter().enumerate() {
                    valeurs[3 + k] += colonne[rang].unwrap();
                }
            } else {
                valeurs[1] += 1.0;
            }
            if ids[rang].starts_with('r') && ids[rang].contains(&suffixe) {
                valeurs[2] += 1.0;
            }
        }
    }
    resume
}

const ENTETE: &str = "year,species,alive,dead,recruits,sum_d130,sum_h,sum_hcb,sum_cw,sum_x,sum_y";

fn en_csv(resume: &BTreeMap<(i32, String), Vec<f64>>) -> String {
    let mut texte = String::from(ENTETE);
    texte.push('\n');
    for ((annee, espece), valeurs) in resume {
        texte.push_str(&format!("{annee},{espece}"));
        for valeur in valeurs {
            // 17 chiffres significatifs : la valeur f64 se relit au bit près.
            texte.push_str(&format!(",{valeur:.16e}"));
        }
        texte.push('\n');
    }
    texte
}

fn chemin_reference() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/reference/resume_zone_essai.csv")
}

const ANNEES_REFERENCE: u32 = 30;

#[test]
fn la_zone_d_essai_redonne_le_resume_fige_a_1e_9_pres() {
    let entrees = zone_d_essai(ANNEES_REFERENCE);
    let dossier = dossier_neuf("non-regression");
    sorties::simuler_et_ecrire(&entrees, &lancement(3), &dossier).unwrap();
    let calcule = resume(&dossier, T0, ANNEES_REFERENCE);
    let texte = en_csv(&calcule);
    if std::env::var("SIMULATE_FIGER_REFERENCE").as_deref() == Ok("1") {
        std::fs::create_dir_all(chemin_reference().parent().unwrap()).unwrap();
        std::fs::write(chemin_reference(), &texte).unwrap();
    }
    let reference = std::fs::read_to_string(chemin_reference()).unwrap_or_else(|_| {
        panic!(
            "référence absente : {} (la figer : SIMULATE_FIGER_REFERENCE=1)",
            chemin_reference().display()
        )
    });
    let mut lignes = reference.lines();
    assert_eq!(lignes.next(), Some(ENTETE));
    let mut lues = 0;
    for ligne in lignes {
        let champs: Vec<&str> = ligne.split(',').collect();
        let cle = (champs[0].parse::<i32>().unwrap(), champs[1].to_string());
        let valeurs = calcule
            .get(&cle)
            .unwrap_or_else(|| panic!("{cle:?} absent du calcul"));
        for (k, texte_attendu) in champs[2..].iter().enumerate() {
            let attendu: f64 = texte_attendu.parse().unwrap();
            let ecart = (valeurs[k] - attendu).abs();
            assert!(
                ecart <= 1e-9 * attendu.abs().max(1.0),
                "{cle:?}, colonne {} : {} contre {attendu} (référence)",
                ENTETE.split(',').nth(k + 2).unwrap(),
                valeurs[k]
            );
        }
        lues += 1;
    }
    assert_eq!(
        lues,
        calcule.len(),
        "nombre de couples (année, essence) différent de la référence"
    );
    // La zone vit : des morts, des recrues des deux essences.
    let total = |k: usize| calcule.values().map(|v| v[k]).sum::<f64>();
    assert!(total(1) > 0.0 && total(2) > 0.0);
    std::fs::remove_dir_all(&dossier).unwrap();
}

// ------------------------------------------------------------------------------------------
// Ce qui est écrit

#[test]
fn les_partitions_vont_de_t0_a_t0_plus_years_sans_colonne_year() {
    let dossier = dossier_neuf("partitions");
    sorties::simuler_et_ecrire(&zone_d_essai(4), &lancement(2), &dossier).unwrap();
    for sorte in ["trees", "cells"] {
        let mut annees: Vec<String> = std::fs::read_dir(dossier.join(sorte))
            .unwrap()
            .map(|e| e.unwrap().file_name().to_string_lossy().to_string())
            .collect();
        annees.sort();
        assert_eq!(
            annees,
            vec![
                "year=2022",
                "year=2023",
                "year=2024",
                "year=2025",
                "year=2026"
            ]
        );
    }
    let arbres = partition(&dossier, "trees", T0 + 1);
    let noms: Vec<String> = arbres
        .schema()
        .fields()
        .iter()
        .map(|f| f.name().clone())
        .collect();
    assert_eq!(
        noms,
        vec!["tree_id", "species", "x", "y", "d130", "h", "hcb", "cw", "status"]
    );
    let cellules = partition(&dossier, "cells", T0 + 1);
    let noms: Vec<String> = cellules
        .schema()
        .fields()
        .iter()
        .map(|f| f.name().clone())
        .collect();
    assert_eq!(
        noms,
        vec![
            "cell_id",
            "species",
            "stems_ha",
            "basal_area_m2_ha",
            "d130_mean",
            "h_dom_m"
        ]
    );
    assert!(dossier.join("flags.parquet").is_file() && dossier.join("run.json").is_file());
    std::fs::remove_dir_all(&dossier).unwrap();
}

#[test]
fn t0_est_l_etat_initial_et_un_mort_n_est_ecrit_qu_une_fois() {
    let entrees = zone_d_essai(6);
    let dossier = dossier_neuf("morts");
    sorties::simuler_et_ecrire(&entrees, &lancement(2), &dossier).unwrap();
    let t0 = partition(&dossier, "trees", T0);
    assert_eq!(chaines(&t0, "tree_id"), entrees.arbres.tree_id);
    assert!(chaines(&t0, "status").iter().all(|s| s == "alive"));
    let d130: Vec<f64> = nombres(&t0, "d130")
        .into_iter()
        .map(|v| v.unwrap())
        .collect();
    assert_eq!(
        d130, entrees.arbres.d130,
        "d130 de t0 = trees_init au bit près"
    );
    let mut morts_vus = std::collections::HashSet::new();
    let mut morts = 0;
    for annee in T0..=T0 + 6 {
        let lot = partition(&dossier, "trees", annee);
        for (id, statut) in chaines(&lot, "tree_id")
            .into_iter()
            .zip(chaines(&lot, "status"))
        {
            assert!(
                !morts_vus.contains(&id),
                "{id} écrit après sa mort (année {annee})"
            );
            if statut == "dead" {
                morts_vus.insert(id);
                morts += 1;
            }
        }
    }
    let run: serde_json::Value =
        serde_json::from_str(&std::fs::read_to_string(dossier.join("run.json")).unwrap()).unwrap();
    assert_eq!(run["deaths"].as_u64().unwrap(), morts);
    assert!(morts > 0);
    std::fs::remove_dir_all(&dossier).unwrap();
}

#[test]
fn les_cellules_sont_les_arbres_vivants_de_l_annee_et_un_point_tombe_au_bon_endroit() {
    let dossier = dossier_neuf("cellules");
    sorties::simuler_et_ecrire(&zone_d_essai(3), &lancement(1), &dossier).unwrap();
    for annee in [T0, T0 + 3] {
        let arbres = partition(&dossier, "trees", annee);
        let x = nombres(&arbres, "x");
        let y = nombres(&arbres, "y");
        let d = nombres(&arbres, "d130");
        let especes = chaines(&arbres, "species");
        let statuts = chaines(&arbres, "status");
        // (cellule, essence) → (tiges, Σ g, Σ d130), cell_id recalculé depuis (x est, y nord).
        let mut attendu: BTreeMap<(i64, String), (f64, f64, f64)> = BTreeMap::new();
        for rang in 0..x.len() {
            if statuts[rang] != "alive" {
                continue;
            }
            let colonne = ((x[rang].unwrap() - X0) / 25.0).floor() as i64;
            let ligne_grille = ((Y0 - y[rang].unwrap()) / 25.0).floor() as i64;
            let cle = (
                ligne_grille * LARGEUR as i64 + colonne,
                especes[rang].clone(),
            );
            let e = attendu.entry(cle).or_insert((0.0, 0.0, 0.0));
            let r = d[rang].unwrap() / 200.0;
            e.0 += 1.0;
            e.1 += std::f64::consts::PI * r * r;
            e.2 += d[rang].unwrap();
        }
        let cellules = partition(&dossier, "cells", annee);
        let ids = entiers(&cellules, "cell_id");
        let especes = chaines(&cellules, "species");
        let tiges = nombres(&cellules, "stems_ha");
        let g = nombres(&cellules, "basal_area_m2_ha");
        let dm = nombres(&cellules, "d130_mean");
        assert_eq!(ids.len(), attendu.len(), "année {annee}");
        for rang in 0..ids.len() {
            let (n, sg, sd) = attendu[&(ids[rang], especes[rang].clone())];
            assert!((tiges[rang].unwrap() - n / 0.0625).abs() < 1e-9);
            assert!((g[rang].unwrap() - sg / 0.0625).abs() < 1e-9 * (sg / 0.0625).max(1.0));
            assert!(
                (dm[rang].unwrap() - sd / n).abs() < 1e-9,
                "d130 moyen arithmétique (T8)"
            );
        }
    }
    // Point du terrain : un arbre posé au centre de la cellule 0 (700 012,5 ; 6 500 987,5) y est compté.
    let mut entrees = zone_d_essai(1);
    let initiaux: Vec<ArbreNouveau> = vec![ArbreNouveau {
        tree_id: "point_du_terrain".to_string(),
        espece: "03".to_string(),
        cellule: 0,
        x: 700_012.5,
        y: 6_500_987.5,
        d130: 30.0,
        h: 18.0,
    }];
    entrees.arbres = EtatArbres::depuis_initiaux(initiaux).unwrap();
    let dossier2 = dossier_neuf("point");
    sorties::simuler_et_ecrire(&entrees, &lancement(1), &dossier2).unwrap();
    let cellules = partition(&dossier2, "cells", T0);
    assert_eq!(entiers(&cellules, "cell_id"), vec![0]);
    assert!((nombres(&cellules, "stems_ha")[0].unwrap() - 16.0).abs() < 1e-12);
    std::fs::remove_dir_all(&dossier).unwrap();
    std::fs::remove_dir_all(&dossier2).unwrap();
}

#[test]
fn run_json_porte_tous_les_comptes_et_les_signalements_disent_les_semis() {
    let dossier = dossier_neuf("run");
    let mut lance = lancement(2);
    lance.config_sha256 = sorties::sha256_hex(b"schema_version: 1\n");
    let bilan = sorties::simuler_et_ecrire(&zone_d_essai(5), &lance, &dossier).unwrap();
    let run: serde_json::Value =
        serde_json::from_str(&std::fs::read_to_string(dossier.join("run.json")).unwrap()).unwrap();
    let cles: Vec<&str> = run
        .as_object()
        .unwrap()
        .keys()
        .map(|k| k.as_str())
        .collect();
    assert_eq!(
        cles,
        vec![
            "cells_at_height_ceiling",
            "config_sha256",
            "deaths",
            "domain_outputs",
            "duration_s",
            "edge_disks",
            "level",
            "memory_estimate_bytes",
            "memory_estimate_max_bytes",
            "memory_peak_rss_bytes",
            "mixed_cells",
            "not_simulated",
            "provisional_share",
            "recruitment",
            "recruits",
            "schema_version",
            "seed",
            "t0",
            "threads",
            "years",
            "zeroed_values"
        ]
    );
    // M5a, mode ifn_direct : les semis sont dits non simulés, sans compte de régénération.
    assert_eq!(run["recruitment"], "ifn_direct");
    assert!(run["not_simulated"]
        .as_array()
        .unwrap()
        .contains(&serde_json::json!("semis")));
    assert!(run["memory_estimate_max_bytes"].as_u64().unwrap() >= bilan.memoire_estimee);
    // SHA-256 de « schema_version: 1\n » (calculé par sha256sum).
    assert_eq!(
        run["config_sha256"],
        "5c9536c0f64193f535c425baf9f2c7431b89eb46bab5fb85d4bfcffabb565f43"
    );
    assert_eq!(run["level"], "massif");
    assert_eq!(run["seed"], 20_261_125);
    assert_eq!(run["t0"], T0);
    assert_eq!(run["years"], 5);
    assert_eq!(run["threads"], 2);
    assert_eq!(run["zeroed_values"], 0);
    assert_eq!(
        run["provisional_share"], 1.0,
        "tous les jeux d'essai sont provisoires"
    );
    assert_eq!(
        run["memory_estimate_bytes"].as_u64().unwrap(),
        bilan.memoire_estimee
    );
    assert!(run["duration_s"].as_f64().unwrap() > 0.0);
    assert_eq!(run["recruits"].as_u64().unwrap(), bilan.comptes.recrues);
    assert!(bilan.comptes.recrues > 0);
    assert!(
        run["edge_disks"].as_u64().unwrap() > 0,
        "la zone est petite : des disques débordent"
    );
    assert!(
        run["mixed_cells"].as_u64().unwrap() > 0,
        "les essences se mêlent par les recrues"
    );
    assert_eq!(run["domain_outputs"].as_object().unwrap().len(), 8);
    let flags = lire_parquet(&dossier.join("flags.parquet"));
    let sortes = chaines(&flags, "kind");
    let messages = chaines(&flags, "message");
    let rang = sortes
        .iter()
        .position(|s| s == "semis_non_simules")
        .unwrap();
    assert!(messages[rang].contains("semis non simulés"));
    assert_eq!(chaines(&flags, "entity")[rang], "zone_essai");
    assert!(
        sortes.iter().any(|s| s == "classe_korf"),
        "la classe de Korf du hêtre est dite à t0"
    );
    std::fs::remove_dir_all(&dossier).unwrap();
}

#[test]
fn la_part_provisoire_compte_les_jeux_utilises() {
    let mut entrees = zone_d_essai(1);
    let lignes = vec![LigneParametre {
        provisoire: false,
        ..ligne(None, "growth_gam", "intercept", None, None, 0.2_f64.ln())
    }];
    entrees.parametres.croissance = Parametres::depuis_lignes(&lignes).unwrap();
    let modeles = sorties::preparer_modeles(&entrees).unwrap();
    let (provisoires, total) = modeles.jeux_provisoires();
    // Deux essences, une croissance définitive chacune : 2 jeux sur `total` ne sont pas provisoires.
    assert_eq!(total - provisoires, 2);
    let part = sorties::part_provisoire(&modeles);
    assert!((part - provisoires as f64 / total as f64).abs() < 1e-15 && part > 0.0 && part < 1.0);
}

#[test]
fn h_dom_m_est_la_h_dom_de_la_cellule_et_vide_si_elle_n_est_pas_finie() {
    // Trois cellules : 3 (H_dom 17,25 m, deux essences), 4 (H_dom non finie), 5 (sans arbre).
    let arbre = |id: &str, espece: &str, cellule: u64| ArbreNouveau {
        tree_id: id.to_string(),
        espece: espece.to_string(),
        cellule,
        x: 700_012.5,
        y: 6_500_987.5,
        d130: 30.0,
        h: 18.0,
    };
    let etat = EtatArbres::depuis_initiaux(vec![
        arbre("a", "03", 3),
        arbre("b", "09", 3),
        arbre("c", "03", 4),
    ])
    .unwrap();
    let h_dom = vec![0.0, 0.0, 0.0, 17.25, f64::NAN, 12.0];
    let geometrie =
        simulate::concurrence::GeometrieGrille::nouvelle(LARGEUR, HAUTEUR, X0, Y0, 25.0).unwrap();
    let lot = sorties::table_cellules(&etat, &h_dom, &geometrie).unwrap();
    assert_eq!(entiers(&lot, "cell_id"), vec![3, 3, 4]);
    assert_eq!(
        nombres(&lot, "h_dom_m"),
        vec![Some(17.25), Some(17.25), None],
        "H_dom connue écrite à l'identique, non finie : null, jamais 0"
    );
}

#[test]
fn h_dom_m_de_chaque_annee_est_celle_du_moteur() {
    let dossier = dossier_neuf("hdom");
    sorties::simuler_et_ecrire(&zone_d_essai(4), &lancement(2), &dossier).unwrap();
    for annee in T0..=T0 + 4 {
        let cellules = partition(&dossier, "cells", annee);
        let ids = entiers(&cellules, "cell_id");
        let h = nombres(&cellules, "h_dom_m");
        assert!(!ids.is_empty());
        for rang in 0..ids.len() {
            let valeur = h[rang].expect("H_dom définie pour une cellule qui a des arbres");
            assert!(valeur > 0.0 && valeur < 60.0, "année {annee} : {valeur}");
            // Même valeur pour toutes les essences d'une cellule.
            if rang > 0 && ids[rang] == ids[rang - 1] {
                assert_eq!(h[rang], h[rang - 1]);
            }
        }
    }
    std::fs::remove_dir_all(&dossier).unwrap();
}
