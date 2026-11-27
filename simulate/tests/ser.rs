//! Tests du niveau SER (mission 063 ; src/ser.rs, src/memoire.rs, src/entrees.rs, src/sorties.rs) :
//! classes de diamètre, transferts entre classes (conservation des tiges), `bal` exact, diamètre
//! dominant, années écrites, cellules forestières, lecture de `cohorts_init`, estimation de
//! mémoire, et le niveau SER de bout en bout sur la zone d'essai en mémoire.
//!
//! Coordonnées : x = est, y = nord, en m, EPSG:2154 ; `cell_id` = ligne × largeur + colonne,
//! ligne 0 au nord ; coin nord-ouest de la zone d'essai (700 000 ; 6 501 000), cellules de 25 m.
//! Les valeurs des paramètres sont des réglages d'essai, sans sens écologique.

#[path = "non_regression.rs"]
mod non_regression;

use std::f64::consts::PI;
use std::path::{Path, PathBuf};
use std::sync::Arc;

use arrow_array::{ArrayRef, Float32Array, Float64Array, Int64Array, RecordBatch, StringArray};
use arrow_schema::{DataType, Field, Schema};
use parquet::arrow::ArrowWriter;

use simulate::config::{ModeRecrutement, NiveauSimulation, ReglagesRegeneration, ReglagesSer};
use simulate::entrees;
use simulate::erreurs::CodeSortie;
use simulate::geotiff::Raster;
use simulate::memoire::{self, BesoinSer, PART_FIXE_SER};
use simulate::semis::{self, LigneRegeneration};
use simulate::ser::{self, Classes, EntreesSer, IndexForet, HORS_FORET};

use non_regression::{chaines, dossier_neuf, entiers, lancement, lire_parquet, nombres, zone_d_essai, T0, X0, Y0};

// ------------------------------------------------------------------------------------------
// Classes, transferts, bal, diamètre dominant

#[test]
fn les_classes_partent_du_seuil_de_recrutement_et_portent_leur_centre() {
    let classes = Classes::nouvelles(5.0, 6);
    let d_min = 23.5 / PI;
    assert!((classes.d_min_cm - d_min).abs() < 1e-15);
    for k in 0..6 {
        let centre = d_min + (k as f64 + 0.5) * 5.0;
        assert_eq!(classes.centres_cm[k], centre);
        let rayon_m = centre / 200.0;
        assert!((classes.surfaces_m2[k] - PI * rayon_m * rayon_m).abs() < 1e-15);
    }
}

#[test]
fn le_transfert_conserve_les_tiges_et_monte_la_part_dd_sur_w() {
    let survivants = [100.0, 40.0, 7.5, 3.0];
    // Δd < w : la part Δd / w monte d'une classe ; la dernière classe garde tout.
    let accroissements = [1.0, 2.5, 4.0, 3.0];
    let mut sortie = [0.0; 4];
    ser::transferer(&survivants, &accroissements, 5.0, &mut sortie).unwrap();
    let attendu = [
        100.0 * 0.8,
        100.0 * 0.2 + 40.0 * 0.5,
        40.0 * 0.5 + 7.5 * 0.2,
        7.5 * 0.8 + 3.0,
    ];
    for k in 0..4 {
        assert!((sortie[k] - attendu[k]).abs() < 1e-12, "classe {k} : {} au lieu de {}", sortie[k], attendu[k]);
    }
    let avant: f64 = survivants.iter().sum();
    let apres: f64 = sortie.iter().sum();
    assert!((avant - apres).abs() <= 1e-12 * avant);
}

#[test]
fn le_transfert_conserve_les_tiges_quand_la_croissance_depasse_une_classe() {
    // Δd = 1,6 w : 60 % montent de deux classes, 40 % d'une ; Δd ≥ K w : tout à la dernière.
    let survivants = [10.0, 20.0, 30.0, 40.0, 50.0];
    let accroissements = [8.0, 8.0, 8.0, 100.0, 0.0];
    let mut sortie = [0.0; 5];
    ser::transferer(&survivants, &accroissements, 5.0, &mut sortie).unwrap();
    let attendu = [0.0, 10.0 * 0.4, 10.0 * 0.6 + 20.0 * 0.4, 20.0 * 0.6 + 30.0 * 0.4, 30.0 * 0.6 + 40.0 + 50.0];
    for k in 0..5 {
        assert!((sortie[k] - attendu[k]).abs() < 1e-12, "classe {k} : {} au lieu de {}", sortie[k], attendu[k]);
    }
    let avant: f64 = survivants.iter().sum();
    let apres: f64 = sortie.iter().sum();
    assert!((avant - apres).abs() <= 1e-12 * avant);
}

#[test]
fn le_transfert_conserve_les_tiges_sur_un_grand_nombre_de_cas() {
    // Générateur congruentiel déterministe : 2 000 vecteurs de 15 classes, Δd de 0 à 3 w.
    let mut etat: u64 = 63;
    let mut tirer = || {
        etat = etat.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
        (etat >> 11) as f64 / (1u64 << 53) as f64
    };
    for _ in 0..2000 {
        let mut survivants = [0.0; 15];
        let mut accroissements = [0.0; 15];
        for k in 0..15 {
            survivants[k] = if tirer() < 0.2 { 0.0 } else { 500.0 * tirer() };
            accroissements[k] = 15.0 * tirer();
        }
        let mut sortie = [0.0; 15];
        ser::transferer(&survivants, &accroissements, 5.0, &mut sortie).unwrap();
        let avant: f64 = survivants.iter().sum();
        let apres: f64 = sortie.iter().sum();
        assert!((avant - apres).abs() <= 1e-12 * avant.max(1.0), "{avant} ≠ {apres}");
        for valeur in sortie {
            assert!(valeur >= 0.0);
        }
    }
}

#[test]
fn un_accroissement_non_fini_ou_negatif_est_un_controle_echoue() {
    let mut sortie = [0.0; 3];
    for delta in [f64::NAN, f64::INFINITY, -0.1] {
        let erreur = ser::transferer(&[1.0, 1.0, 1.0], &[0.5, delta, 0.5], 5.0, &mut sortie).unwrap_err();
        assert_eq!(erreur.code, CodeSortie::ControleEchoue, "{delta}");
    }
}

#[test]
fn bal_est_exact_sur_un_cas_a_trois_classes() {
    // Trois classes de 10 cm à partir du seuil ; deux essences. bal(k) = surface terrière des
    // classes strictement plus grosses, toutes essences, calculée ici à la main.
    let classes = Classes::nouvelles(10.0, 3);
    let g = |k: usize| {
        let d = 23.5 / PI + (k as f64 + 0.5) * 10.0;
        PI * (d / 200.0) * (d / 200.0)
    };
    // essence 0 : 120, 40, 0 tiges/ha ; essence 1 : 30, 20, 5 tiges/ha.
    let tiges: [f32; 6] = [120.0, 40.0, 0.0, 30.0, 20.0, 5.0];
    let mut densites = [0.0; 3];
    ser::densites_par_classe(&tiges, 3, &mut densites);
    assert_eq!(densites, [150.0, 60.0, 5.0]);
    let mut bal = [0.0; 3];
    ser::bal_par_classe(&densites, &classes.surfaces_m2, &mut bal);
    let attendu = [60.0 * g(1) + 5.0 * g(2), 5.0 * g(2), 0.0];
    for k in 0..3 {
        assert!((bal[k] - attendu[k]).abs() <= 1e-14 * attendu[0], "classe {k} : {} au lieu de {}", bal[k], attendu[k]);
    }
    assert_eq!(bal[2], 0.0, "la plus grosse classe n'a personne au-dessus d'elle");
    // La surface terrière totale et par essence.
    let mut ba = [0.0; 2];
    let totale = ser::surfaces_par_espece(&tiges, &classes, &mut ba);
    assert!((ba[0] - (120.0 * g(0) + 40.0 * g(1))).abs() < 1e-12);
    assert!((ba[1] - (30.0 * g(0) + 20.0 * g(1) + 5.0 * g(2))).abs() < 1e-12);
    assert!((totale - ba[0] - ba[1]).abs() < 1e-12);
}

#[test]
fn le_diametre_dominant_prend_les_100_plus_grosses_tiges() {
    let centres = [10.0, 20.0, 30.0];
    // 30 + 50 + 20 des 200 de la classe 0 font les 100 tiges.
    let d = ser::diametre_dominant_classes(&[200.0, 50.0, 30.0], &centres).unwrap();
    let attendu = ((30.0 * 900.0 + 50.0 * 400.0 + 20.0 * 100.0) / 100.0_f64).sqrt();
    assert!((d - attendu).abs() < 1e-12);
    // Moins de 100 tiges/ha : toutes.
    let d = ser::diametre_dominant_classes(&[10.0, 0.0, 30.0], &centres).unwrap();
    let attendu = ((10.0 * 100.0 + 30.0 * 900.0) / 40.0_f64).sqrt();
    assert!((d - attendu).abs() < 1e-12);
    assert_eq!(ser::diametre_dominant_classes(&[0.0, 0.0, 0.0], &centres), None);
}

#[test]
fn les_annees_ecrites_sont_t0_le_pas_et_la_derniere() {
    assert_eq!(ser::annees_ecrites(2022, 5, 2), vec![2022, 2024, 2026, 2027]);
    assert_eq!(ser::annees_ecrites(2022, 3, 3), vec![2022, 2025]);
    assert_eq!(ser::annees_ecrites(2022, 3, 1), vec![2022, 2023, 2024, 2025]);
    assert_eq!(ser::annees_ecrites(2022, 2, 10), vec![2022, 2024]);
    assert_eq!(ser::annees_ecrites(2022, 100, 10).len(), 11);
}

#[test]
fn le_bloc_ser_de_config_yml_est_exige_au_niveau_ser_sans_valeur_par_defaut() {
    let base = "schema_version: 1\nzone: z\ncrs: \"EPSG:2154\"\ngrid:\n  resolution_m: 25\nmanagement: aucune\n\
                simulate:\n  level: ser\n  seed: 1\n  t0: 2022\n  years: 3\n";
    let sans = simulate::config::depuis_texte(base).unwrap();
    let erreur = sans.reglages_ser().unwrap_err();
    assert_eq!(erreur.code, CodeSortie::EntreeRefusee);
    assert!(erreur.message.contains("simulate.ser") && erreur.message.contains("absent"), "{}", erreur.message);
    let complet = format!("{base}  ser:\n    diameter_class_width_cm: 5\n    diameter_classes: 6\n    write_step: 2\n");
    let reglages = simulate::config::depuis_texte(&complet).unwrap().reglages_ser().unwrap();
    assert_eq!(reglages, ReglagesSer { largeur_classe_cm: 5.0, classes: 6, pas_ecriture: 2 });
    let incomplet = format!("{base}  ser:\n    diameter_classes: 1\n    write_step: 0\n");
    let erreur = simulate::config::depuis_texte(&incomplet).unwrap().reglages_ser().unwrap_err();
    assert!(erreur.message.contains("diameter_class_width_cm"), "{}", erreur.message);
    let faux = format!("{base}  ser:\n    diameter_class_width_cm: 5\n    diameter_classes: 1\n    write_step: 1\n");
    let erreur = simulate::config::depuis_texte(&faux).unwrap().reglages_ser().unwrap_err();
    assert!(erreur.message.contains("au moins 2"), "{}", erreur.message);
}

// ------------------------------------------------------------------------------------------
// Cellules forestières

fn masque(largeur: usize, hauteur: usize, valeurs: Vec<f32>) -> Raster {
    Raster {
        largeur,
        hauteur,
        origine_x: X0,
        origine_y: Y0,
        pixel_x: 25.0,
        pixel_y: 25.0,
        nodata: 65535.0,
        bandes: vec![valeurs],
    }
}

#[test]
fn un_point_connu_tombe_dans_la_bonne_cellule_forestiere() {
    // Zone d'essai de 8 × 6 cellules, la cellule 47 hors de grid.tif. Masque : la colonne 0 hors
    // forêt. Le point (est 700 037,5 ; nord 6 500 962,5), EPSG:2154, est le centre de la cellule
    // (ligne 1, colonne 1), cell_id 9 : 6 cellules forestières le précèdent (cell_id 1 à 7).
    let entrees = zone_d_essai(1);
    let grille = &entrees.grille;
    let mut valeurs = vec![1.0_f32; 48];
    for ligne in 0..6 {
        valeurs[ligne * 8] = 0.0;
    }
    let foret = IndexForet::depuis_masque(grille, &masque(8, 6, valeurs)).unwrap();
    let cellule = grille.cellule_de(700_037.5, 6_500_962.5).unwrap();
    assert_eq!(cellule, 9);
    assert_eq!(foret.rang(9), Some(7));
    assert_eq!(foret.cellule_de_rang[7], 9);
    assert_eq!(foret.rang(8), None, "colonne 0 hors forêt");
    assert_eq!(foret.rang_de_cellule[47], HORS_FORET, "hors de grid.tif");
    assert_eq!(foret.nombre(), 48 - 6 - 1);
    for (rang, cellule) in foret.cellule_de_rang.iter().enumerate() {
        assert_eq!(foret.rang(*cellule as usize), Some(rang));
    }
}

#[test]
fn un_masque_sans_0_ni_1_ou_non_aligne_est_refuse() {
    let entrees = zone_d_essai(1);
    let mut valeurs = vec![1.0_f32; 48];
    valeurs[5] = 2.0;
    let erreur = IndexForet::depuis_masque(&entrees.grille, &masque(8, 6, valeurs)).unwrap_err();
    assert_eq!(erreur.code, CodeSortie::EntreeRefusee);
    let mut valeurs = vec![1.0_f32; 48];
    valeurs[5] = 65535.0;
    assert!(IndexForet::depuis_masque(&entrees.grille, &masque(8, 6, valeurs)).is_err());
    let erreur = IndexForet::depuis_masque(&entrees.grille, &masque(7, 6, vec![1.0; 42])).unwrap_err();
    assert!(erreur.message.contains("non aligné"), "{}", erreur.message);
}

// ------------------------------------------------------------------------------------------
// cohorts_init

/// Écrit un `cohorts_init.parquet` d'essai : (cell_id, essence, d_class, tiges/ha).
fn ecrire_cohortes(chemin: &Path, lignes: &[(i64, &str, i64, f64)]) {
    let schema = Arc::new(Schema::new(vec![
        Field::new("cell_id", DataType::Int64, false),
        Field::new("species", DataType::Utf8, false),
        Field::new("d_class", DataType::Int64, false),
        Field::new("stems_ha", DataType::Float64, false),
        Field::new("source", DataType::Utf8, false),
    ]));
    let colonnes: Vec<ArrayRef> = vec![
        Arc::new(Int64Array::from(lignes.iter().map(|l| l.0).collect::<Vec<i64>>())),
        Arc::new(StringArray::from(lignes.iter().map(|l| l.1).collect::<Vec<&str>>())),
        Arc::new(Int64Array::from(lignes.iter().map(|l| l.2).collect::<Vec<i64>>())),
        Arc::new(Float64Array::from(lignes.iter().map(|l| l.3).collect::<Vec<f64>>())),
        Arc::new(StringArray::from(vec!["essai"; lignes.len()])),
    ];
    let lot = RecordBatch::try_new(schema.clone(), colonnes).unwrap();
    std::fs::create_dir_all(chemin.parent().unwrap()).unwrap();
    let mut ecrivain = ArrowWriter::try_new(std::fs::File::create(chemin).unwrap(), schema, None).unwrap();
    ecrivain.write(&lot).unwrap();
    ecrivain.close().unwrap();
}

fn foret_complete() -> IndexForet {
    let entrees = zone_d_essai(1);
    IndexForet::depuis_masque(&entrees.grille, &masque(8, 6, vec![1.0; 48])).unwrap()
}

fn lire(lignes: &[(i64, &str, i64, f64)], nom: &str) -> Result<Vec<f32>, simulate::erreurs::Erreur> {
    let dossier = dossier_neuf(nom);
    let chemin = dossier.join("cohorts_init.parquet");
    ecrire_cohortes(&chemin, lignes);
    let entrees = zone_d_essai(1);
    let foret = foret_complete();
    let essences = vec!["03".to_string(), "09".to_string()];
    let mut tiges = vec![entrees::ABSENTE; foret.nombre() * 2 * 3];
    let resultat = entrees::lire_cohortes(&chemin, &entrees.grille, &foret, &essences, 3, &mut tiges);
    let _ = std::fs::remove_dir_all(&dossier);
    resultat.map(|_| tiges)
}

#[test]
fn les_cohortes_sont_rangees_par_cellule_essence_et_classe_et_le_reste_vaut_0() {
    let tiges = lire(&[(0, "03", 0, 12.5), (0, "09", 2, 3.0), (46, "03", 1, 7.25)], "cohortes-ok").unwrap();
    assert_eq!(tiges.len(), 47 * 6);
    assert_eq!(tiges[0], 12.5);
    assert_eq!(tiges[3 + 2], 3.0);
    assert_eq!(tiges[46 * 6 + 1], 7.25);
    let non_nuls = tiges.iter().filter(|v| **v != 0.0).count();
    assert_eq!(non_nuls, 3, "les classes sans ligne valent 0, aucune ne reste « absente »");
}

#[test]
fn les_cohortes_fautives_sont_refusees_en_code_2_avec_leur_cause() {
    let cas: [(&str, Vec<(i64, &str, i64, f64)>, &str); 6] = [
        ("doublon", vec![(1, "03", 0, 1.0), (1, "03", 0, 2.0)], "doublon"),
        ("classe", vec![(1, "03", 3, 1.0)], "d_class 3 hors"),
        ("grille", vec![(48, "03", 0, 1.0)], "hors de la grille"),
        ("foret", vec![(47, "03", 0, 1.0)], "hors forêt"),
        ("negatif", vec![(1, "03", 0, -3.0)], "stems_ha = -3"),
        ("essence", vec![(1, "61", 0, 1.0)], "« 61 »"),
    ];
    for (nom, lignes, mot) in cas {
        let erreur = lire(&lignes, nom).unwrap_err();
        assert_eq!(erreur.code, CodeSortie::EntreeRefusee, "[{nom}] {}", erreur.message);
        assert!(erreur.message.contains(mot), "[{nom}] {}", erreur.message);
    }
}

#[test]
fn les_essences_des_cohortes_sont_triees_et_dans_le_referentiel() {
    let dossier = dossier_neuf("cohortes-essences");
    let chemin = dossier.join("cohorts_init.parquet");
    ecrire_cohortes(&chemin, &[(0, "09", 0, 1.0), (1, "03", 0, 1.0), (2, "09", 1, 1.0)]);
    let referentiel = non_regression::referentiel();
    assert_eq!(entrees::essences_des_cohortes(&chemin, &referentiel).unwrap(), vec!["03", "09"]);
    ecrire_cohortes(&chemin, &[(0, "99", 0, 1.0)]);
    let erreur = entrees::essences_des_cohortes(&chemin, &referentiel).unwrap_err();
    assert!(erreur.message.contains("99") && erreur.message.contains("hors référentiel"), "{}", erreur.message);
    let erreur = entrees::essences_des_cohortes(&dossier.join("absent.parquet"), &referentiel).unwrap_err();
    assert_eq!(erreur.code, CodeSortie::EntreeRefusee);
    assert!(erreur.message.contains("absent"), "{}", erreur.message);
    let _ = std::fs::remove_dir_all(&dossier);
}

// ------------------------------------------------------------------------------------------
// Estimation de mémoire

#[test]
fn l_estimation_du_niveau_ser_est_la_formule_fermee() {
    let besoin = BesoinSer {
        cellules_grille: 1000,
        cellules_foret: 800,
        especes: 2,
        classes: 6,
        classes_semis: 8,
        candidates: 2,
        valeurs_fft: 1200,
        valeurs_spectre: 620,
        lignes_par_fichier: 65_536,
    };
    let durable = 33 * 1000 + 800 * (4 + 8 + 4 * 2 * 6 + 8 * 8) + 16 * 620 * 2;
    let pas = 800 * (16 + 8 * 2) + 1000 * 17 + 16 * 620 + 8 * 1200;
    let ecriture = (800 * 2 * 6) * memoire::OCTETS_LIGNE_ECRITE;
    let lecture = (800 * 2 * 6) * memoire::OCTETS_LIGNE_LUE;
    let attendu = PART_FIXE_SER + durable + pas.max(ecriture).max(lecture);
    assert_eq!(memoire::estimer_ser(&besoin).unwrap(), attendu);
    // L'état grandit avec les classes : 4 octets par cellule forestière, essence et classe.
    let plus = BesoinSer { classes: 7, ..besoin };
    let ecart = memoire::estimer_ser(&plus).unwrap() - memoire::estimer_ser(&besoin).unwrap();
    assert!(ecart >= 4 * 800 * 2, "{ecart}");
    // Hors de portée : code 4, jamais un débordement.
    let enorme = BesoinSer { cellules_foret: u64::MAX / 2, ..besoin };
    assert_eq!(memoire::estimer_ser(&enorme).unwrap_err().code, CodeSortie::MemoireInsuffisante);
}

// ------------------------------------------------------------------------------------------
// Le niveau SER de bout en bout, sur la zone d'essai en mémoire

fn lignes_regeneration() -> Vec<LigneRegeneration> {
    // kernel_scale_m = 7 m : d99 = 46,5 m, couvert par K = 2 cellules de 25 m (mission 080).
    let valeurs = [
        7.0, 1.0, 10.0, 1000.0, 0.5, 0.4, 3.0, 0.5, 0.9, 1.3, 0.184, 9.091, -1.238, 1.0, 9.0, 5.0, 0.1, -0.4, 0.025, 1.0,
    ];
    let mut lignes = Vec::new();
    for (rang, (terme, unite)) in semis::TERMES.iter().enumerate() {
        lignes.push(LigneRegeneration {
            species: None,
            species_group: Some("toutes_essences".to_string()),
            term: terme.to_string(),
            value: valeurs[rang],
            unit: unite.to_string(),
            provisoire: true,
            source: "essai".to_string(),
        });
    }
    lignes
}

/// La zone d'essai au niveau SER : toutes les cellules de la grille forestières sauf la colonne 0 ;
/// cohortes de 03 et 09 dans 3 classes de 10 cm, écrites dans `dossier`.
fn zone_ser(years: u32, pas_ecriture: u32, dossier: &Path) -> simulate::entrees::Entrees {
    let mut entrees = zone_d_essai(years);
    entrees.reglages.niveau = NiveauSimulation::Ser;
    entrees.arbres = simulate::etat::EtatArbres::vide();
    entrees.recrutement = ModeRecrutement::Cohortes(ReglagesRegeneration {
        demi_largeur_noyau: 2,
        seuil_zero: 1e-9,
    });
    entrees.regeneration = lignes_regeneration();
    let mut valeurs = vec![1.0_f32; 48];
    for ligne in 0..6 {
        valeurs[ligne * 8] = 0.0;
    }
    let foret = IndexForet::depuis_masque(&entrees.grille, &masque(8, 6, valeurs)).unwrap();
    let mut lignes: Vec<(i64, &str, i64, f64)> = Vec::new();
    for cellule in foret.cellule_de_rang.iter() {
        let c = i64::from(*cellule);
        let colonne = c % 8;
        if colonne < 4 {
            lignes.push((c, "03", 0, 80.0 + c as f64));
            lignes.push((c, "03", 1, 40.0));
        }
        if colonne >= 3 {
            lignes.push((c, "09", 1, 25.0));
            lignes.push((c, "09", 2, 10.0 + 0.5 * c as f64));
        }
    }
    let chemin = dossier.join("cohorts_init.parquet");
    ecrire_cohortes(&chemin, &lignes);
    entrees.ser = Some(EntreesSer {
        reglages: ReglagesSer {
            largeur_classe_cm: 10.0,
            classes: 3,
            pas_ecriture,
        },
        foret,
        chemin_cohortes: chemin,
        essences: vec!["03".to_string(), "09".to_string()],
    });
    entrees
}

fn fichiers(dossier: &Path) -> Vec<(String, Vec<u8>)> {
    let mut resultat = Vec::new();
    let mut a_voir: Vec<PathBuf> = vec![dossier.to_path_buf()];
    while let Some(courant) = a_voir.pop() {
        for entree in std::fs::read_dir(&courant).unwrap() {
            let chemin = entree.unwrap().path();
            if chemin.is_dir() {
                a_voir.push(chemin);
            } else if chemin.extension().and_then(|e| e.to_str()) == Some("parquet") {
                let relatif = chemin.strip_prefix(dossier).unwrap().to_string_lossy().to_string();
                resultat.push((relatif, std::fs::read(&chemin).unwrap()));
            }
        }
    }
    resultat.sort();
    resultat
}

fn tiges_f32(lot: &RecordBatch) -> Vec<f32> {
    let colonne = lot.column_by_name("stems_ha").unwrap();
    let valeurs = colonne.as_any().downcast_ref::<Float32Array>().unwrap();
    (0..valeurs.len()).map(|i| valeurs.value(i)).collect()
}

#[test]
fn le_niveau_ser_ecrit_cohortes_et_cellules_aux_annees_retenues_sans_arbres() {
    let dossier = dossier_neuf("ser-bout-en-bout");
    std::fs::create_dir_all(&dossier).unwrap();
    let entrees = zone_ser(5, 2, &dossier);
    let sim = dossier.join("sim");
    let bilan = simulate::sorties::simuler_et_ecrire(&entrees, &lancement(1), &sim).unwrap();
    assert!(!sim.join("trees").exists(), "aucun sim/trees au niveau SER");
    for sorte in ["cohorts", "cells"] {
        let mut annees: Vec<String> = std::fs::read_dir(sim.join(sorte))
            .unwrap()
            .map(|e| e.unwrap().file_name().to_string_lossy().to_string())
            .collect();
        annees.sort();
        assert_eq!(annees, vec!["year=2022", "year=2024", "year=2026", "year=2027"], "sim/{sorte}");
    }
    // t0 redonne cohorts_init (en f32), dans l'ordre (cell_id, essence, classe).
    let t0 = lire_parquet(&sim.join("cohorts").join(format!("year={T0}")).join("part-00000.parquet"));
    let cellules = entiers(&t0, "cell_id");
    let especes = chaines(&t0, "species");
    let classes = entiers(&t0, "d_class");
    let tiges = tiges_f32(&t0);
    assert_eq!(cellules[0], 1);
    assert_eq!((especes[0].as_str(), classes[0], tiges[0]), ("03", 0, 81.0));
    assert_eq!((especes[1].as_str(), classes[1], tiges[1]), ("03", 1, 40.0));
    for rang in 1..cellules.len() {
        let avant = (cellules[rang - 1], especes[rang - 1].clone(), classes[rang - 1]);
        let apres = (cellules[rang], especes[rang].clone(), classes[rang]);
        assert!(avant < apres, "lignes non triées ou en double");
    }
    // Dans sim/cells, les tiges de chaque couple (cellule, essence) sont la somme des classes.
    for annee in [2022, 2027] {
        let coh = lire_parquet(&sim.join("cohorts").join(format!("year={annee}")).join("part-00000.parquet"));
        let cel = lire_parquet(&sim.join("cells").join(format!("year={annee}")).join("part-00000.parquet"));
        let mut sommes = std::collections::BTreeMap::new();
        for ((c, s), t) in entiers(&coh, "cell_id").into_iter().zip(chaines(&coh, "species")).zip(tiges_f32(&coh)) {
            *sommes.entry((c, s)).or_insert(0.0) += f64::from(t);
        }
        let stems = nombres(&cel, "stems_ha");
        let semis = nombres(&cel, "seedlings_ha");
        for (rang, (c, s)) in entiers(&cel, "cell_id").into_iter().zip(chaines(&cel, "species")).enumerate() {
            let attendu = sommes.get(&(c, s.clone())).copied().unwrap_or(0.0);
            assert!((stems[rang].unwrap() - attendu).abs() <= 1e-12 * attendu.max(1.0), "{annee}, {c}, {s}");
            assert!(semis[rang].is_some(), "seedlings_ha écrite sur chaque ligne en mode cohorts");
        }
        assert!(!entiers(&cel, "cell_id").contains(&0), "la cellule 0 n'est pas forestière");
    }
    let run: serde_json::Value = serde_json::from_slice(&std::fs::read(sim.join("run.json")).unwrap()).unwrap();
    assert_eq!(run["level"], "ser");
    assert_eq!(run["recruitment"], "cohorts");
    assert_eq!(run["edge_disks"], 0);
    assert!(run["memory_estimate_max_bytes"].as_u64().unwrap() >= run["memory_estimate_bytes"].as_u64().unwrap());
    assert_eq!(bilan.lignes_arbres, 0);
    let _ = std::fs::remove_dir_all(&dossier);
}

#[test]
fn le_niveau_ser_est_identique_de_1_a_3_fils() {
    let mut empreintes = Vec::new();
    for fils in [1, 3] {
        let dossier = dossier_neuf(&format!("ser-fils-{fils}"));
        std::fs::create_dir_all(&dossier).unwrap();
        let entrees = zone_ser(4, 1, &dossier);
        let sim = dossier.join("sim");
        simulate::sorties::simuler_et_ecrire(&entrees, &lancement(fils), &sim).unwrap();
        empreintes.push(fichiers(&sim));
        let _ = std::fs::remove_dir_all(&dossier);
    }
    assert!(!empreintes[0].is_empty());
    assert_eq!(empreintes[0], empreintes[1], "sorties différentes entre 1 et 3 fils");
}

#[test]
fn le_niveau_ser_refuse_ifn_direct_et_une_memoire_trop_faible() {
    let dossier = dossier_neuf("ser-refus");
    std::fs::create_dir_all(&dossier).unwrap();
    let mut entrees = zone_ser(1, 1, &dossier);
    let mut faible = lancement(1);
    faible.memoire_disponible = 1;
    let erreur = simulate::sorties::simuler_et_ecrire(&entrees, &faible, &dossier.join("sim")).unwrap_err();
    assert_eq!(erreur.code, CodeSortie::MemoireInsuffisante);
    assert!(!dossier.join("sim").exists(), "rien n'est écrit avant la vérification de la mémoire");
    entrees.recrutement = ModeRecrutement::IfnDirect;
    let erreur = simulate::sorties::simuler_et_ecrire(&entrees, &lancement(1), &dossier.join("sim")).unwrap_err();
    assert_eq!(erreur.code, CodeSortie::EntreeRefusee);
    assert!(erreur.message.contains("cohorts"), "{}", erreur.message);
    let _ = std::fs::remove_dir_all(&dossier);
}

#[test]
fn le_niveau_ser_refuse_un_k_qui_ne_couvre_pas_d99_avant_toute_ecriture() {
    // kernel_scale_m = 30 m (forme 1) : d99 = 199,2 m ; K = 2 couvre 50 m (mission 080).
    let dossier = dossier_neuf("ser-k-court");
    std::fs::create_dir_all(&dossier).unwrap();
    let mut entrees = zone_ser(1, 1, &dossier);
    for ligne in entrees.regeneration.iter_mut() {
        if ligne.term == "kernel_scale_m" {
            ligne.value = 30.0;
        }
    }
    let erreur = simulate::sorties::simuler_et_ecrire(&entrees, &lancement(1), &dossier.join("sim")).unwrap_err();
    assert_eq!(erreur.code, CodeSortie::EntreeRefusee);
    for mot in ["03", "d99 = 199.2 m", "kernel_truncation_cells = 2"] {
        assert!(erreur.message.contains(mot), "« {mot} » absent de : {}", erreur.message);
    }
    assert!(!dossier.join("sim").exists(), "rien n'est écrit");
    let _ = std::fs::remove_dir_all(&dossier);
}

#[test]
fn un_nan_injecte_au_niveau_ser_est_un_controle_echoue() {
    let dossier = dossier_neuf("ser-nan");
    std::fs::create_dir_all(&dossier).unwrap();
    let entrees = zone_ser(2, 1, &dossier);
    let mut avec_nan = lancement(1);
    avec_nan.inject_nan = Some(T0 + 1);
    let erreur = simulate::sorties::simuler_et_ecrire(&entrees, &avec_nan, &dossier.join("sim")).unwrap_err();
    assert_eq!(erreur.code, CodeSortie::ControleEchoue);
    assert!(erreur.message.contains("NaN"), "{}", erreur.message);
    let _ = std::fs::remove_dir_all(&dossier);
}

#[test]
fn au_niveau_ser_une_cellule_ombragee_n_est_pas_bornee_la_premiere_annee() {
    // Reprise de 062 : le stock initial « en régime » est l'état stationnaire à la survie de la
    // cellule, ombre du couvert de t0 comprise. Avec un coefficient d'extinction d'essai très fort,
    // la lumière de toute cellule qui a des adultes tombe dans la classe 0, sous le seuil de lumière : survie 0,9 − 0,184.
    let dossier = dossier_neuf("ser-ombre-premiere-annee");
    std::fs::create_dir_all(&dossier).unwrap();
    let mut entrees = zone_ser(1, 1, &dossier);
    for ligne in entrees.regeneration.iter_mut() {
        if ligne.term == "light_extinction_coef" {
            ligne.value = 1000.0;
        }
    }
    let sim = dossier.join("sim");
    let bilan = simulate::sorties::simuler_et_ecrire(&entrees, &lancement(1), &sim).unwrap();
    let run: serde_json::Value = serde_json::from_slice(&std::fs::read(sim.join("run.json")).unwrap()).unwrap();
    assert_eq!(run["seedling_stock_limited"], 0, "le stock initial borne le flux dès la première année à l'ombre");
    assert_eq!(bilan.comptes.stock_de_semis_limitant, 0);
    assert!(run["recruits"].as_u64().unwrap() > 0, "le test ne discriminerait rien sans recrue");
    let _ = std::fs::remove_dir_all(&dossier);
}
