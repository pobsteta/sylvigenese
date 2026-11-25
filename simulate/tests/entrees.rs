//! Tests des entrées de `simulate` (mission 036 ; src/entrees.rs, grille.rs, config.rs).
//!
//! Coordonnées : x = est, y = nord, en m, EPSG:2154. La grille d'essai est celle du jeu fictif :
//! 40 × 40 cellules de 25 m, coin nord-ouest (est 700 000 ; nord 6 501 000). Toutes les entrées
//! sont construites en mémoire ou écrites dans le dossier temporaire de cargo : aucune
//! dépendance aux sorties du jeu fictif ignorées par git.

use std::fs::File;
use std::path::{Path, PathBuf};
use std::sync::Arc;

use arrow_array::{ArrayRef, BooleanArray, Float64Array, RecordBatch, StringArray};
use arrow_schema::{Field, Schema};
use parquet::arrow::ArrowWriter;

use simulate::config::{self, NiveauSimulation};
use simulate::entrees::{
    affecter_aux_cellules, assembler_couches, essences_des_arbres, lire_allometrie, lire_arbres,
    lire_arbres_fichier, verifier_parametres_des_essences, ArbreBrut, JeuxDeParametres, Rasters,
    TableSer,
};
use simulate::erreurs::CodeSortie;
use simulate::geotiff::Raster;
use simulate::grille::Grille;
use simulate::parametres::{LigneParametre, Parametres, Referentiel};

// ------------------------------------------------------------------------------------------
// Aides

fn raster(largeur: usize, hauteur: usize, bandes: Vec<Vec<f32>>) -> Raster {
    Raster {
        largeur,
        hauteur,
        origine_x: 700_000.0,
        origine_y: 6_501_000.0,
        pixel_x: 25.0,
        pixel_y: 25.0,
        nodata: -9999.0,
        bandes,
    }
}

/// grid.tif du jeu fictif : 40 × 40, toutes les cellules ont la valeur 1.
fn grille_fictive() -> Grille {
    let mut r = raster(40, 40, vec![vec![1.0; 1600]]);
    r.nodata = 65535.0;
    Grille::depuis_raster(&r, "grid.tif", 25.0).unwrap()
}

fn brut(id: &str, x: f64, y: f64, species: &str) -> ArbreBrut {
    ArbreBrut {
        tree_id: id.to_string(),
        x,
        y,
        species: species.to_string(),
        d130: 30.0,
        h: 22.0,
    }
}

fn dossier_temp(nom: &str) -> PathBuf {
    let dossier = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("entrees").join(nom);
    let _ = std::fs::remove_dir_all(&dossier);
    std::fs::create_dir_all(&dossier).unwrap();
    dossier
}

fn texte(valeurs: &[Option<&str>]) -> ArrayRef {
    Arc::new(StringArray::from(valeurs.to_vec()))
}

fn reels(valeurs: &[f64]) -> ArrayRef {
    Arc::new(Float64Array::from(valeurs.to_vec()))
}

fn ecrire_parquet(chemin: &Path, colonnes: Vec<(&str, ArrayRef)>) {
    let champs: Vec<Field> = colonnes
        .iter()
        .map(|(nom, tableau)| Field::new(*nom, tableau.data_type().clone(), true))
        .collect();
    let schema = Arc::new(Schema::new(champs));
    let tableaux: Vec<ArrayRef> = colonnes.iter().map(|(_, t)| t.clone()).collect();
    let lot = RecordBatch::try_new(schema.clone(), tableaux).unwrap();
    let mut ecrivain = ArrowWriter::try_new(File::create(chemin).unwrap(), schema, None).unwrap();
    ecrivain.write(&lot).unwrap();
    ecrivain.close().unwrap();
}

/// Colonnes de trees_init pour trois arbres (le premier est le point du terrain).
fn colonnes_arbres() -> Vec<(&'static str, ArrayRef)> {
    vec![
        ("tree_id", texte(&[Some("t1"), Some("t2"), Some("t3")])),
        ("x", reels(&[700_012.5, 700_037.5, 700_999.75])),
        ("y", reels(&[6_500_987.5, 6_500_962.5, 6_500_000.25])),
        ("species", texte(&[Some("09"), Some("61"), Some("03")])),
        ("d130", reels(&[40.0, 35.5, 50.0])),
        ("h", reels(&[28.0, 25.5, 30.0])),
        ("crown_area", reels(&[20.0, 18.0, 25.0])),
        ("species_source", texte(&[Some("nemeton"), Some("nemeton"), Some("nemeton")])),
        ("d130_source", texte(&[Some("tarif_etage_b"), Some("tarif_etage_b"), Some("tarif_etage_b")])),
    ]
}

fn referentiel() -> Referentiel {
    let chemin = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../contracts/species.csv");
    Referentiel::lire(&chemin).unwrap()
}

// ------------------------------------------------------------------------------------------
// Grille et point du terrain

#[test]
fn point_du_terrain_un_arbre_en_est_700012_5_nord_6500987_5_tombe_dans_cell_id_0() {
    let grille = grille_fictive();
    // x = 700 012,5 : (700 012,5 − 700 000) / 25 = 0,5 -> colonne 0.
    // y = 6 500 987,5 : (6 501 000 − 6 500 987,5) / 25 = 0,5 -> ligne 0 (la ligne 0 est au nord).
    assert_eq!(grille.cellule_de(700_012.5, 6_500_987.5).unwrap(), 0);
    // Par le chemin complet : lecture -> affectation.
    let arbres = affecter_aux_cellules(&grille, vec![brut("t1", 700_012.5, 6_500_987.5, "09")]).unwrap();
    assert_eq!(arbres[0].cellule, 0);
    assert_eq!((arbres[0].x, arbres[0].y), (700_012.5, 6_500_987.5));
}

#[test]
fn l_est_et_le_nord_ne_sont_pas_inverses() {
    let grille = grille_fictive();
    // Une cellule à l'est de la première : colonne 1, ligne 0 -> cell_id 1.
    assert_eq!(grille.cellule_de(700_037.5, 6_500_987.5).unwrap(), 1);
    // Une cellule au sud de la première : colonne 0, ligne 1 -> cell_id 40 (la largeur).
    assert_eq!(grille.cellule_de(700_012.5, 6_500_962.5).unwrap(), 40);
    // Colonne 3, ligne 2 : 2 × 40 + 3 = 83.
    assert_eq!(grille.cellule_de(700_087.5, 6_500_937.5).unwrap(), 83);
    // Dernière cellule : sud-est, ligne 39, colonne 39 -> 1599.
    assert_eq!(grille.cellule_de(700_999.75, 6_500_000.25).unwrap(), 1599);
}

#[test]
fn les_limites_des_cellules_sont_fermees_au_nord_et_a_l_ouest_ouvertes_au_sud_et_a_l_est() {
    let grille = grille_fictive();
    // Bord nord et bord ouest : dedans, cellule 0.
    assert_eq!(grille.cellule_de(700_000.0, 6_501_000.0).unwrap(), 0);
    // Limite entre deux cellules : elle appartient à la cellule du sud-est (floor).
    assert_eq!(grille.cellule_de(700_025.0, 6_500_975.0).unwrap(), 41);
    // Bord est (x = 701 000) et bord sud (y = 6 500 000) : hors grille.
    assert_eq!(grille.cellule_de(701_000.0, 6_500_500.0).unwrap_err().code, CodeSortie::EntreeRefusee);
    assert_eq!(grille.cellule_de(700_500.0, 6_500_000.0).unwrap_err().code, CodeSortie::EntreeRefusee);
}

#[test]
fn cell_id_ligne_colonne_et_bornes_sont_coherents() {
    let grille = grille_fictive();
    assert_eq!(grille.cell_id(2, 3), 83);
    assert_eq!(grille.ligne_colonne(83), (2, 3));
    // Cellule 83 : ouest 700 075, est 700 100, nord 6 500 950, sud 6 500 925.
    assert_eq!(grille.bornes(83), (700_075.0, 700_100.0, 6_500_925.0, 6_500_950.0));
    // Le centre de la cellule retombe dans la cellule.
    let (ouest, est, sud, nord) = grille.bornes(1234);
    assert_eq!(grille.cellule_de((ouest + est) / 2.0, (sud + nord) / 2.0).unwrap(), 1234);
    assert_eq!(grille.nombre_cellules(), 1600);
    assert_eq!(grille.nombre_valides(), 1600);
    assert_eq!((grille.x_max(), grille.y_min()), (701_000.0, 6_500_000.0));
}

#[test]
fn un_arbre_hors_grille_arrete_tout_code_2_avec_son_nom() {
    let grille = grille_fictive();
    let cas = [
        ("a l'ouest", 699_999.0, 6_500_500.0),
        ("a l'est", 701_000.5, 6_500_500.0),
        ("au nord", 700_500.0, 6_501_000.5),
        ("au sud", 700_500.0, 6_499_999.0),
    ];
    for (nom, x, y) in cas {
        let erreur = affecter_aux_cellules(
            &grille,
            vec![brut("bon", 700_500.0, 6_500_500.0, "09"), brut("dehors", x, y, "09")],
        )
        .unwrap_err();
        assert_eq!(erreur.code_sortie(), 2, "{nom}");
        assert!(erreur.message.contains("« dehors »"), "{nom} : {}", erreur.message);
        assert!(erreur.message.contains("hors de la grille"), "{nom} : {}", erreur.message);
    }
}

#[test]
fn des_coordonnees_non_finies_sont_refusees() {
    let grille = grille_fictive();
    assert_eq!(grille.cellule_de(f64::NAN, 6_500_500.0).unwrap_err().code_sortie(), 2);
    assert_eq!(grille.cellule_de(700_500.0, f64::INFINITY).unwrap_err().code_sortie(), 2);
}

#[test]
fn un_arbre_sur_une_cellule_sans_valeur_dans_grid_tif_est_refuse() {
    let mut r = raster(2, 2, vec![vec![1.0, 65535.0, 1.0, 1.0]]);
    r.nodata = 65535.0;
    let grille = Grille::depuis_raster(&r, "grid.tif", 25.0).unwrap();
    assert_eq!(grille.nombre_valides(), 3);
    // Cellule 1 (ligne 0, colonne 1) : sans valeur.
    let erreur = grille.cellule_de(700_037.5, 6_500_987.5).unwrap_err();
    assert_eq!(erreur.code_sortie(), 2);
    assert!(erreur.message.contains("grid.tif"), "{}", erreur.message);
    assert_eq!(grille.cellule_de(700_012.5, 6_500_987.5).unwrap(), 0);
}

#[test]
fn grid_tif_a_plusieurs_bandes_ou_un_autre_pas_est_refuse() {
    let deux_bandes = raster(2, 2, vec![vec![1.0; 4], vec![1.0; 4]]);
    assert_eq!(Grille::depuis_raster(&deux_bandes, "grid.tif", 25.0).unwrap_err().code_sortie(), 2);
    let un = raster(2, 2, vec![vec![1.0; 4]]);
    let erreur = Grille::depuis_raster(&un, "grid.tif", 20.0).unwrap_err();
    assert_eq!(erreur.code_sortie(), 2);
    assert!(erreur.message.contains("grid.resolution_m"), "{}", erreur.message);
    let mut rectangle = raster(2, 2, vec![vec![1.0; 4]]);
    rectangle.pixel_y = 20.0;
    assert_eq!(Grille::depuis_raster(&rectangle, "grid.tif", 25.0).unwrap_err().code_sortie(), 2);
}

// ------------------------------------------------------------------------------------------
// Alignement

#[test]
fn un_raster_non_aligne_sur_grid_tif_est_refuse_avec_son_nom() {
    let grille = grille_fictive();
    let bon = raster(40, 40, vec![vec![0.0; 1600]]);
    grille.verifier_alignement(&bon, "h0.tif").unwrap();

    let mut decale_x = bon.clone();
    decale_x.origine_x += 12.5;
    let mut decale_y = bon.clone();
    decale_y.origine_y -= 0.5;
    let mut pas = bon.clone();
    pas.pixel_x = 26.6;
    let taille = raster(39, 40, vec![vec![0.0; 39 * 40]]);
    for (quoi, r) in [("x", decale_x), ("y", decale_y), ("pas", pas), ("taille", taille)] {
        let erreur = grille.verifier_alignement(&r, "h0.tif").unwrap_err();
        assert_eq!(erreur.code_sortie(), 2, "{quoi}");
        assert!(erreur.message.contains("h0.tif"), "{quoi} : {}", erreur.message);
        assert!(erreur.message.contains("non aligné"), "{quoi} : {}", erreur.message);
    }
}

// ------------------------------------------------------------------------------------------
// Couches

fn rasters_valides() -> Rasters {
    let mut ser = raster(40, 40, vec![vec![1.0; 1600]]);
    ser.nodata = 65535.0;
    ser.bandes[0][1] = 2.0;
    let mut chm = raster(40, 40, vec![vec![18_842.0; 1600]]);
    chm.nodata = 65535.0;
    Rasters {
        h0: raster(40, 40, vec![vec![27.5; 1600]]),
        chm_date: chm,
        site_potential: raster(40, 40, vec![vec![33.0; 1600]]),
        station_gradients: raster(
            40,
            40,
            vec![vec![0.1; 1600], vec![0.2; 1600], vec![0.3; 1600]],
        ),
        ser,
    }
}

fn table_ser() -> TableSer {
    TableSer::depuis_texte("\"value\",\"name\",\"alluvium_code\"\n1,\"H10\",\n2,\"H10\",\"L3\"\n", "ser.csv").unwrap()
}

#[test]
fn les_couches_sont_rangees_par_cellule_et_les_bandes_dans_l_ordre_du_contrat() {
    let grille = grille_fictive();
    let couches = assembler_couches(&grille, rasters_valides(), table_ser()).unwrap();
    assert_eq!(couches.h0.len(), 1600);
    assert_eq!(couches.h0[0], 27.5);
    assert_eq!(couches.chm_date[7], 18_842.0);
    assert_eq!(couches.h_pot[1599], 33.0);
    assert_eq!((couches.trophic[0], couches.hydric[0], couches.bioclim[0]), (0.1, 0.2, 0.3));
    assert_eq!(couches.code_ser(0), Some("H10"));
    assert_eq!(couches.code_ser(1), Some("H10"));
    assert_eq!(couches.ser[1], 2);
}

#[test]
fn un_raster_non_aligne_ou_incomplet_arrete_l_assemblage_code_2() {
    let grille = grille_fictive();
    // Non aligné : site_potential décalé d'une cellule vers l'est.
    let mut r = rasters_valides();
    r.site_potential.origine_x += 25.0;
    let erreur = assembler_couches(&grille, r, table_ser()).unwrap_err();
    assert_eq!(erreur.code_sortie(), 2);
    assert!(erreur.message.contains("site_potential.tif"), "{}", erreur.message);

    // Une cellule de la grille sans donnée dans h0.
    let mut r = rasters_valides();
    r.h0.bandes[0][5] = -9999.0;
    let erreur = assembler_couches(&grille, r, table_ser()).unwrap_err();
    assert_eq!(erreur.code_sortie(), 2);
    assert!(erreur.message.contains("h0.tif"), "{}", erreur.message);
    assert!(erreur.message.contains("cell_id 5"), "{}", erreur.message);

    // NaN dans une bande de station_gradients.
    let mut r = rasters_valides();
    r.station_gradients.bandes[2][9] = f32::NAN;
    let erreur = assembler_couches(&grille, r, table_ser()).unwrap_err();
    assert!(erreur.message.contains("station_gradients.tif"), "{}", erreur.message);
    assert!(erreur.message.contains("bande 3"), "{}", erreur.message);

    // Deux bandes au lieu de trois.
    let mut r = rasters_valides();
    r.station_gradients.bandes.pop();
    let erreur = assembler_couches(&grille, r, table_ser()).unwrap_err();
    assert!(erreur.message.contains("2 bande(s) au lieu de 3"), "{}", erreur.message);
}

#[test]
fn une_cellule_sans_valeur_dans_grid_tif_peut_etre_sans_donnee_ailleurs() {
    let mut g = raster(40, 40, vec![vec![1.0; 1600]]);
    g.nodata = 65535.0;
    g.bandes[0][5] = 65535.0;
    let grille = Grille::depuis_raster(&g, "grid.tif", 25.0).unwrap();
    let mut r = rasters_valides();
    r.h0.bandes[0][5] = -9999.0;
    assembler_couches(&grille, r, table_ser()).unwrap();
}

#[test]
fn une_valeur_de_ser_absente_de_ser_csv_est_refusee() {
    let grille = grille_fictive();
    let mut r = rasters_valides();
    r.ser.bandes[0][3] = 7.0;
    let erreur = assembler_couches(&grille, r, table_ser()).unwrap_err();
    assert_eq!(erreur.code_sortie(), 2);
    assert!(erreur.message.contains("ser.tif"), "{}", erreur.message);
    assert!(erreur.message.contains("ser.csv"), "{}", erreur.message);
}

#[test]
fn la_table_ser_refuse_les_tables_mal_formees() {
    let cas = [
        ("", "fichier vide"),
        ("value,nom\n1,H10\n", "colonne « name » absente"),
        ("value,name\nun,H10\n", "n'est pas un entier"),
        ("value,name\n1,H10\n1,K12\n", "en double"),
        ("value,name\n1,\n", "name vide"),
    ];
    for (texte, attendu) in cas {
        let erreur = TableSer::depuis_texte(texte, "ser.csv").unwrap_err();
        assert_eq!(erreur.code_sortie(), 2, "{texte}");
        assert!(erreur.message.contains(attendu), "{texte} : {}", erreur.message);
        assert!(erreur.message.contains("ser.csv"), "{texte} : {}", erreur.message);
    }
}

// ------------------------------------------------------------------------------------------
// config.yml

const CONFIG_BASE: &str = "schema_version: 1\nzone: zone_fictive\ncrs: EPSG:2154\ngrid:\n  resolution_m: 25\nmanagement: none\n";

fn config_avec(bloc: &str) -> config::Config {
    config::depuis_texte(&format!("{CONFIG_BASE}{bloc}")).unwrap()
}

#[test]
fn le_bloc_simulate_complet_est_lu() {
    let c = config_avec("simulate:\n  level: massif\n  seed: 42\n  t0: 2021\n  years: 100\n");
    let r = c.reglages_simulate().unwrap();
    assert_eq!(r.niveau, NiveauSimulation::Massif);
    assert_eq!((r.seed, r.t0, r.years, r.threads), (42, 2021, 100, None));
    let c = config_avec("simulate:\n  level: ser\n  seed: 0\n  t0: 2021\n  years: 1\n  threads: 4\n");
    let r = c.reglages_simulate().unwrap();
    assert_eq!(r.niveau, NiveauSimulation::Ser);
    assert_eq!((r.seed, r.threads), (0, Some(4)));
    c.verifier_crs().unwrap();
}

#[test]
fn un_bloc_simulate_absent_ou_incomplet_est_refuse_code_2_sans_valeur_par_defaut() {
    let erreur = config_avec("").reglages_simulate().unwrap_err();
    assert_eq!(erreur.code_sortie(), 2);
    assert!(erreur.message.contains("bloc « simulate » est absent"), "{}", erreur.message);

    let erreur = config_avec("simulate:\n  level: massif\n  years: 100\n").reglages_simulate().unwrap_err();
    assert_eq!(erreur.code_sortie(), 2);
    assert!(erreur.message.contains("clés absentes : seed, t0"), "{}", erreur.message);

    for (bloc, attendu) in [
        ("simulate:\n  seed: 1\n  t0: 2021\n  years: 5\n", "level"),
        ("simulate:\n  level: massif\n  t0: 2021\n  years: 5\n", "seed"),
        ("simulate:\n  level: massif\n  seed: 1\n  years: 5\n", "t0"),
        ("simulate:\n  level: massif\n  seed: 1\n  t0: 2021\n", "years"),
    ] {
        let erreur = config_avec(bloc).reglages_simulate().unwrap_err();
        assert_eq!(erreur.code_sortie(), 2, "{bloc}");
        assert!(erreur.message.contains(&format!("clés absentes : {attendu} ")), "{bloc} : {}", erreur.message);
    }
}

#[test]
fn des_reglages_hors_domaine_sont_refuses() {
    for (bloc, attendu) in [
        ("simulate:\n  level: foret\n  seed: 1\n  t0: 2021\n  years: 5\n", "simulate.level"),
        ("simulate:\n  level: massif\n  seed: 1\n  t0: 2021\n  years: 0\n", "simulate.years"),
        ("simulate:\n  level: massif\n  seed: 1\n  t0: 2021\n  years: 5\n  threads: 0\n", "simulate.threads"),
    ] {
        let erreur = config_avec(bloc).reglages_simulate().unwrap_err();
        assert_eq!(erreur.code_sortie(), 2, "{bloc}");
        assert!(erreur.message.contains(attendu), "{bloc} : {}", erreur.message);
    }
    let autre_crs = config::depuis_texte(&CONFIG_BASE.replace("EPSG:2154", "EPSG:4326")).unwrap();
    let erreur = autre_crs.verifier_crs().unwrap_err();
    assert_eq!(erreur.code_sortie(), 2);
    assert!(erreur.message.contains("EPSG:4326"), "{}", erreur.message);
}

// ------------------------------------------------------------------------------------------
// trees_init

#[test]
fn trees_init_est_lu_puis_affecte_aux_cellules() {
    let dossier = dossier_temp("trees_ok");
    ecrire_parquet(&dossier.join("trees.parquet"), colonnes_arbres());
    let brutes = lire_arbres(&dossier).unwrap();
    assert_eq!(brutes.len(), 3);
    assert_eq!(brutes[0], brut("t1", 700_012.5, 6_500_987.5, "09").clone_avec(40.0, 28.0));
    assert_eq!(essences_des_arbres(&brutes), vec!["03", "09", "61"]);

    let affectes = affecter_aux_cellules(&grille_fictive(), brutes).unwrap();
    let cellules: Vec<u64> = affectes.iter().map(|a| a.cellule).collect();
    // t1 : point du terrain -> 0 ; t2 : (700 037,5 ; 6 500 962,5) -> ligne 1, colonne 1 = 41 ;
    // t3 : coin sud-est -> 1599.
    assert_eq!(cellules, vec![0, 41, 1599]);
}

trait CloneAvec {
    fn clone_avec(self, d130: f64, h: f64) -> ArbreBrut;
}

impl CloneAvec for ArbreBrut {
    fn clone_avec(mut self, d130: f64, h: f64) -> ArbreBrut {
        self.d130 = d130;
        self.h = h;
        self
    }
}

fn sans_colonne(nom: &str) -> Vec<(&'static str, ArrayRef)> {
    colonnes_arbres().into_iter().filter(|(n, _)| *n != nom).collect()
}

#[test]
fn trees_init_hors_contrat_est_refuse_avec_le_nom_du_fichier() {
    let dossier = dossier_temp("trees_refus");
    let chemin = dossier.join("trees.parquet");

    ecrire_parquet(&chemin, sans_colonne("d130"));
    let erreur = lire_arbres_fichier(&chemin).unwrap_err();
    assert_eq!(erreur.code_sortie(), 2);
    assert!(erreur.message.contains("trees.parquet"), "{}", erreur.message);
    assert!(erreur.message.contains("colonne « d130 » absente"), "{}", erreur.message);

    let mut en_trop = colonnes_arbres();
    en_trop.push(("bonus", reels(&[1.0, 2.0, 3.0])));
    ecrire_parquet(&chemin, en_trop);
    let erreur = lire_arbres_fichier(&chemin).unwrap_err();
    assert!(erreur.message.contains("colonne « bonus » hors du contrat"), "{}", erreur.message);

    let mut d130_nul = colonnes_arbres();
    d130_nul[4] = ("d130", reels(&[40.0, 0.0, 50.0]));
    ecrire_parquet(&chemin, d130_nul);
    let erreur = lire_arbres_fichier(&chemin).unwrap_err();
    assert!(erreur.message.contains("« t2 »") && erreur.message.contains("d130"), "{}", erreur.message);

    let mut h_nan = colonnes_arbres();
    h_nan[5] = ("h", reels(&[28.0, f64::NAN, 30.0]));
    ecrire_parquet(&chemin, h_nan);
    assert!(lire_arbres_fichier(&chemin).unwrap_err().message.contains("« t2 »"));

    let mut x_nan = colonnes_arbres();
    x_nan[1] = ("x", reels(&[700_012.5, f64::NAN, 700_999.75]));
    ecrire_parquet(&chemin, x_nan);
    assert!(lire_arbres_fichier(&chemin).unwrap_err().message.contains("coordonnées"));

    let mut sans_id = colonnes_arbres();
    sans_id[0] = ("tree_id", texte(&[Some("t1"), None, Some("t3")]));
    ecrire_parquet(&chemin, sans_id);
    assert!(lire_arbres_fichier(&chemin).unwrap_err().message.contains("tree_id"));

    let mut mauvais_type = colonnes_arbres();
    mauvais_type[4] = ("d130", texte(&[Some("1"), Some("2"), Some("3")]));
    ecrire_parquet(&chemin, mauvais_type);
    assert!(lire_arbres_fichier(&chemin).unwrap_err().message.contains("devrait être de type"));
}

#[test]
fn un_dossier_trees_init_absent_ou_vide_est_refuse() {
    let vide = dossier_temp("trees_vide");
    let erreur = lire_arbres(&vide).unwrap_err();
    assert_eq!(erreur.code_sortie(), 2);
    assert!(erreur.message.contains("aucun fichier .parquet"), "{}", erreur.message);
    let absent = vide.join("nulle_part");
    assert_eq!(lire_arbres(&absent).unwrap_err().code_sortie(), 2);
}

// ------------------------------------------------------------------------------------------
// Paramètres

fn ligne(species: Option<&str>, groupe: Option<&str>, model: &str, term: &str, value: f64) -> LigneParametre {
    LigneParametre {
        species: species.map(|s| s.to_string()),
        species_group: groupe.map(|s| s.to_string()),
        model: model.to_string(),
        term: term.to_string(),
        variable: None,
        x: None,
        value,
        provisoire: true,
        source: "essai_unitaire".to_string(),
    }
}

fn jeu_complet_pour(essence: &str) -> Vec<LigneParametre> {
    let mut lignes = Vec::new();
    for terme in ["CR_a", "CR_b", "CR_min", "CR_max"] {
        lignes.push(ligne(Some(essence), None, "hcb", terme, 0.5));
    }
    for terme in ["R_a", "R_b"] {
        lignes.push(ligne(Some(essence), None, "cw", terme, 0.5));
    }
    lignes
}

fn jeux(essence: &str) -> JeuxDeParametres {
    let un = |modele: &str| -> Parametres {
        Parametres::depuis_lignes(&[ligne(Some(essence), None, modele, "intercept", 0.1)]).unwrap()
    };
    JeuxDeParametres {
        croissance: un("growth_gam"),
        mortalite: un("mortality_gam"),
        recrutement: un("recruitment_gam"),
        courbe_hauteur: Parametres::depuis_lignes(&[
            ligne(Some(essence), None, "relative_height_gam", "intercept", 0.1),
            ligne(Some(essence), None, "chapman_richards", "a", 1.0),
        ])
        .unwrap(),
        allometrie: Parametres::depuis_lignes(&jeu_complet_pour(essence)).unwrap(),
    }
}

#[test]
fn les_parametres_de_chaque_essence_sont_exiges_code_2_sinon() {
    let r = referentiel();
    let essences = vec!["09".to_string()];
    verifier_parametres_des_essences(&essences, &jeux("09"), &r).unwrap();

    // Essence sans aucun paramètre (ni sien, ni de son groupe, ni toutes_essences).
    let erreur = verifier_parametres_des_essences(&["61".to_string()], &jeux("09"), &r).unwrap_err();
    assert_eq!(erreur.code_sortie(), 2);
    assert!(erreur.message.contains("61"), "{}", erreur.message);
    assert!(erreur.message.contains("growth_gam"), "{}", erreur.message);

    // Essence hors de contracts/species.csv : refusée, son groupe ne se devine pas.
    let erreur = verifier_parametres_des_essences(&["99".to_string()], &jeux("09"), &r).unwrap_err();
    assert!(erreur.message.contains("species.csv"), "{}", erreur.message);
}

#[test]
fn un_modele_manquant_est_nomme_dans_l_erreur() {
    let r = referentiel();
    let essences = vec!["09".to_string()];

    let mut j = jeux("09");
    j.allometrie = Parametres::depuis_lignes(&jeu_complet_pour("09")[..4]).unwrap();
    let erreur = verifier_parametres_des_essences(&essences, &j, &r).unwrap_err();
    assert_eq!(erreur.code_sortie(), 2);
    assert!(erreur.message.contains("cw"), "{}", erreur.message);

    let mut j = jeux("09");
    let mut sans_cr_max = jeu_complet_pour("09");
    sans_cr_max.retain(|l| l.term != "CR_max");
    j.allometrie = Parametres::depuis_lignes(&sans_cr_max).unwrap();
    let erreur = verifier_parametres_des_essences(&essences, &j, &r).unwrap_err();
    assert!(erreur.message.contains("CR_max"), "{}", erreur.message);

    // Ni Chapman-Richards ni Korf.
    let mut j = jeux("09");
    j.courbe_hauteur =
        Parametres::depuis_lignes(&[ligne(Some("09"), None, "relative_height_gam", "intercept", 0.1)]).unwrap();
    let erreur = verifier_parametres_des_essences(&essences, &j, &r).unwrap_err();
    assert!(erreur.message.contains("korf"), "{}", erreur.message);

    // Korf seul suffit (le hêtre).
    j.courbe_hauteur = Parametres::depuis_lignes(&[
        ligne(Some("09"), None, "relative_height_gam", "intercept", 0.1),
        ligne(Some("09"), None, "korf", "a", 1.0),
    ])
    .unwrap();
    verifier_parametres_des_essences(&essences, &j, &r).unwrap();
}

#[test]
fn le_repli_par_groupe_puis_toutes_essences_suffit() {
    let r = referentiel();
    // 09 est feuillu : growth porté par « feuillu », mortalité par toutes_essences.
    let mut j = jeux("09");
    j.croissance = Parametres::depuis_lignes(&[ligne(None, Some("feuillu"), "growth_gam", "intercept", 0.1)]).unwrap();
    j.mortalite = Parametres::depuis_lignes(&[ligne(None, Some("toutes_essences"), "mortality_gam", "intercept", 0.1)]).unwrap();
    verifier_parametres_des_essences(&["09".to_string()], &j, &r).unwrap();
}

#[test]
fn allometry_parquet_a_sept_colonnes_se_relit_en_lignes() {
    let dossier = dossier_temp("allometrie");
    let chemin = dossier.join("allometry.parquet");
    let colonnes: Vec<(&str, ArrayRef)> = vec![
        ("species", texte(&[Some("09"), None])),
        ("species_group", texte(&[None, Some("resineux")])),
        ("model", texte(&[Some("cw"), Some("cw")])),
        ("term", texte(&[Some("R_a"), Some("R_a")])),
        ("value", reels(&[-0.3, -0.9])),
        ("provisoire", Arc::new(BooleanArray::from(vec![true, true]))),
        ("source", texte(&[Some("synthetique_jeu_fictif"), Some("synthetique_jeu_fictif")])),
    ];
    ecrire_parquet(&chemin, colonnes.clone());
    let lignes = lire_allometrie(&chemin).unwrap();
    assert_eq!(lignes.len(), 2);
    assert_eq!(lignes[0].species.as_deref(), Some("09"));
    assert_eq!(lignes[1].species_group.as_deref(), Some("resineux"));
    assert_eq!((lignes[0].value, lignes[0].variable.clone(), lignes[0].x), (-0.3, None, None));
    Parametres::depuis_lignes(&lignes).unwrap();

    // Une colonne `variable` n'existe pas dans ce contrat.
    let mut en_trop = colonnes.clone();
    en_trop.push(("variable", texte(&[None, None])));
    ecrire_parquet(&chemin, en_trop);
    let erreur = lire_allometrie(&chemin).unwrap_err();
    assert_eq!(erreur.code_sortie(), 2);
    assert!(erreur.message.contains("allometry.parquet"), "{}", erreur.message);
    assert!(erreur.message.contains("variable"), "{}", erreur.message);

    let sans_source: Vec<(&str, ArrayRef)> = colonnes.into_iter().filter(|(n, _)| *n != "source").collect();
    ecrire_parquet(&chemin, sans_source);
    assert!(lire_allometrie(&chemin).unwrap_err().message.contains("colonne « source » absente"));
}

#[test]
fn un_fichier_illisible_est_refuse_avec_son_nom() {
    let dossier = dossier_temp("illisible");
    let chemin = dossier.join("allometry.parquet");
    std::fs::write(&chemin, b"ceci n'est pas du Parquet").unwrap();
    let erreur = lire_allometrie(&chemin).unwrap_err();
    assert_eq!(erreur.code_sortie(), 2);
    assert!(erreur.message.contains("allometry.parquet"), "{}", erreur.message);
    let erreur = lire_allometrie(&dossier.join("absent.parquet")).unwrap_err();
    assert!(erreur.message.contains("absent.parquet"), "{}", erreur.message);
}
