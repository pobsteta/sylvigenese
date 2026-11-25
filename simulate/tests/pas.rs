//! Tests du pas annuel (mission 037 ; src/{concurrence,accroissement,hauteur,mortalite,
//! recrutement,controles,pas}.rs), sur des états construits en mémoire.
//!
//! Coordonnées : x = est, y = nord, en m, EPSG:2154. La grille d'essai a son coin nord-ouest en
//! (700 000 ; 6 501 000), des cellules de 25 m, `cell_id` = ligne × largeur + colonne, la ligne 0
//! au nord : le point (700 012,5 ; 6 500 987,5) est le centre de la cellule 0.
//!
//! Les paramètres d'essai sont des nombres d'essai (source « essai »), choisis pour que le
//! résultat se calcule à la main ; ils ne valent rien d'écologique. Les valeurs de référence
//! notées « Python » ont été calculées indépendamment (Python 3, math) le 25/11/2026.

use std::path::PathBuf;

use simulate::accroissement::{self, SortiesParSens};
use simulate::alea::{packer_essence, u, Sorte};
use simulate::concurrence::{self, GeometrieGrille};
use simulate::controles::{self, Comptes, Positivite};
use simulate::erreurs::CodeSortie;
use simulate::etat::{ArbreNouveau, EtatArbres};
use simulate::hauteur::{self, Courbe, ReferenceKorf};
use simulate::mortalite;
use simulate::parametres::{Covariables, LigneParametre, Parametres, Referentiel, Variable};
use simulate::pas::{self, Cellules, EtatCellules, Modeles, ResultatPas, SourcesDeParametres};
use simulate::recrutement;

// ------------------------------------------------------------------------------------------
// Aides

const X0: f64 = 700_000.0;
const Y0: f64 = 6_501_000.0;

fn referentiel() -> Referentiel {
    let chemin = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../contracts/species.csv");
    Referentiel::lire(&chemin).unwrap()
}

fn ligne(
    species: Option<&str>,
    group: Option<&str>,
    model: &str,
    term: &str,
    variable: Option<&str>,
    x: Option<f64>,
    value: f64,
) -> LigneParametre {
    LigneParametre {
        species: species.map(|s| s.to_string()),
        species_group: group.map(|s| s.to_string()),
        model: model.to_string(),
        term: term.to_string(),
        variable: variable.map(|s| s.to_string()),
        x,
        value,
        provisoire: true,
        source: "essai".to_string(),
    }
}

fn toutes(
    model: &str,
    term: &str,
    variable: Option<&str>,
    x: Option<f64>,
    value: f64,
) -> LigneParametre {
    ligne(
        None,
        Some("toutes_essences"),
        model,
        term,
        variable,
        x,
        value,
    )
}

/// Croissance : 2 × exp(ln 0,2) = 0,4 cm/an ; terme lisse nul en d130 (nœuds 10 et 60 cm).
fn lignes_croissance() -> Vec<LigneParametre> {
    vec![
        toutes("growth_gam", "intercept", None, None, 0.2_f64.ln()),
        toutes("growth_gam", "s(d130)[01]", Some("d130"), Some(10.0), 0.0),
        toutes("growth_gam", "s(d130)[02]", Some("d130"), Some(60.0), 0.0),
    ]
}

/// Mortalité : risque annuel 0,02.
fn lignes_mortalite() -> Vec<LigneParametre> {
    vec![toutes(
        "mortality_gam",
        "intercept",
        None,
        None,
        0.02_f64.ln(),
    )]
}

/// Recrutement : 40 tiges/ha/an, soit λ = 2,5 par cellule de 25 m et par essence.
fn lignes_recrutement() -> Vec<LigneParametre> {
    vec![toutes(
        "recruitment_gam",
        "intercept",
        None,
        None,
        40.0_f64.ln(),
    )]
}

/// Hauteur : f(rel_d) = 0,9 + (rel_d − 1) / 2 (spline à deux nœuds : droite) ; Chapman-Richards
/// pour 03, Korf pour 09 (nombres de la fixture du jeu fictif, moyenne NO et NE de nemeton).
fn lignes_hauteur() -> Vec<LigneParametre> {
    let mut lignes = vec![
        toutes("relative_height_gam", "intercept", None, None, 0.9),
        toutes(
            "relative_height_gam",
            "s(rel_d)[01]",
            Some("rel_d"),
            Some(0.0),
            -0.5,
        ),
        toutes(
            "relative_height_gam",
            "s(rel_d)[02]",
            Some("rel_d"),
            Some(2.0),
            0.5,
        ),
    ];
    let cr = Some("03");
    for (rang, a) in [38.0, 34.0, 29.0, 24.0, 20.0].iter().enumerate() {
        lignes.push(ligne(
            cr,
            None,
            "chapman_richards",
            &format!("A_class{}", rang + 1),
            None,
            None,
            *a,
        ));
    }
    lignes.push(ligne(cr, None, "chapman_richards", "k", None, None, 0.022));
    lignes.push(ligne(cr, None, "chapman_richards", "p", None, None, 1.5));
    let korf = Some("09");
    lignes.push(ligne(korf, None, "korf", "a", None, None, 56.45));
    lignes.push(ligne(korf, None, "korf", "b", None, None, 0.03));
    lignes.push(ligne(korf, None, "korf", "c", None, None, 1.235));
    for (rang, p_f) in [0.555, 0.47875, 0.4025, 0.32625, 0.25].iter().enumerate() {
        lignes.push(ligne(
            korf,
            None,
            "korf",
            &format!("p_f_class{}", rang + 1),
            None,
            None,
            *p_f,
        ));
    }
    lignes
}

fn lignes_allometrie() -> Vec<LigneParametre> {
    vec![
        toutes("hcb", "CR_a", None, None, 1.1),
        toutes("hcb", "CR_b", None, None, -0.15),
        toutes("hcb", "CR_min", None, None, 0.2),
        toutes("hcb", "CR_max", None, None, 0.9),
        toutes("cw", "R_a", None, None, -0.3),
        toutes("cw", "R_b", None, None, 0.55),
    ]
}

struct Jeux {
    croissance: Parametres,
    mortalite: Parametres,
    recrutement: Parametres,
    hauteur: Parametres,
    allometrie: Parametres,
}

impl Jeux {
    fn essai() -> Jeux {
        Jeux {
            croissance: Parametres::depuis_lignes(&lignes_croissance()).unwrap(),
            mortalite: Parametres::depuis_lignes(&lignes_mortalite()).unwrap(),
            recrutement: Parametres::depuis_lignes(&lignes_recrutement()).unwrap(),
            hauteur: Parametres::depuis_lignes(&lignes_hauteur()).unwrap(),
            allometrie: Parametres::depuis_lignes(&lignes_allometrie()).unwrap(),
        }
    }

    fn sources(&self) -> SourcesDeParametres<'_> {
        SourcesDeParametres {
            croissance: &self.croissance,
            mortalite: &self.mortalite,
            recrutement: &self.recrutement,
            courbe_hauteur: &self.hauteur,
            allometrie: &self.allometrie,
        }
    }
}

/// Le point de départ de nemeton pour le hêtre : âge 6, hauteur moyenne NO et NE 1,375 m,
/// âge de référence 100 (R/dynamics.R, DYN_KORF_REGIONS et DYN_KORF_REF_AGE).
fn reference_korf() -> ReferenceKorf {
    ReferenceKorf {
        age_depart: 6.0,
        hauteur_depart: 1.375,
        age_reference: 100.0,
    }
}

fn modeles(jeux: &Jeux, candidates: &[&str], reference: Option<ReferenceKorf>) -> Modeles {
    let referentiel = referentiel();
    let essences: Vec<String> = vec!["03".to_string(), "09".to_string()];
    let candidates: Vec<String> = candidates.iter().map(|c| c.to_string()).collect();
    Modeles::preparer(
        &jeux.sources(),
        &referentiel,
        &essences,
        &candidates,
        reference,
    )
    .unwrap()
}

fn grille(largeur: usize, hauteur: usize) -> GeometrieGrille {
    GeometrieGrille::nouvelle(largeur, hauteur, X0, Y0, 25.0).unwrap()
}

/// Des cellules toutes simulées, station uniforme, une bande de site_potential.
fn cellules(largeur: usize, hauteur: usize, h0: f64, plafond: f64) -> Cellules {
    let n = largeur * hauteur;
    Cellules {
        geometrie: grille(largeur, hauteur),
        simulee: vec![true; n],
        h0: vec![h0; n],
        // 2021-07-01 : 18 809 jours depuis le 1970-01-01.
        chm_date: vec![18_809.0; n],
        trophic: vec![5.0; n],
        hydric: vec![-1.0; n],
        bioclim: vec![0.05; n],
        ser_code: vec!["B10".to_string(); n],
        site_potential: vec![plafond; n],
        nombre_bandes: 1,
        bande_par_essence: Vec::new(),
    }
}

fn cellule_de(geometrie: &GeometrieGrille, x: f64, y: f64) -> u64 {
    let colonne = ((x - geometrie.origine_x) / geometrie.pas).floor() as u64;
    let ligne = ((geometrie.origine_y - y) / geometrie.pas).floor() as u64;
    ligne * geometrie.largeur as u64 + colonne
}

fn arbre(
    tree_id: &str,
    espece: &str,
    geometrie: &GeometrieGrille,
    x: f64,
    y: f64,
    d130: f64,
    h: f64,
) -> ArbreNouveau {
    ArbreNouveau {
        tree_id: tree_id.to_string(),
        espece: espece.to_string(),
        cellule: cellule_de(geometrie, x, y),
        x,
        y,
        d130,
        h,
    }
}

fn proche(a: f64, b: f64, tolerance: f64) -> bool {
    (a - b).abs() <= tolerance
}

// ------------------------------------------------------------------------------------------
// Géométrie

#[test]
fn le_point_du_terrain_tombe_dans_la_cellule_zero_et_la_grille_le_sait() {
    let geometrie = grille(3, 3);
    // (700 012,5 ; 6 500 987,5), x est, y nord, EPSG:2154 : centre de la cellule 0.
    assert_eq!(cellule_de(&geometrie, 700_012.5, 6_500_987.5), 0);
    let (x_ouest, x_est, y_sud, y_nord) = geometrie.bornes(0);
    assert_eq!(
        (x_ouest, x_est, y_sud, y_nord),
        (700_000.0, 700_025.0, 6_500_975.0, 6_501_000.0)
    );
    // Le centre de la cellule 4 (milieu de la grille 3 × 3) : (700 037,5 ; 6 500 962,5).
    assert_eq!(cellule_de(&geometrie, 700_037.5, 6_500_962.5), 4);
    assert_eq!(geometrie.ligne_colonne(4), (1, 1));
    assert_eq!(geometrie.aire_cellule_ha(), 0.0625);
}

#[test]
fn une_cellule_de_moins_de_15_m_est_refusee() {
    let erreur = GeometrieGrille::nouvelle(3, 3, X0, Y0, 10.0).unwrap_err();
    assert_eq!(erreur.code, CodeSortie::EntreeRefusee);
}

// ------------------------------------------------------------------------------------------
// Concurrence

/// Un arbre au centre de la cellule 4 et deux voisins plein est, à 14,9 m et 15,1 m.
fn etat_disque() -> (EtatArbres, GeometrieGrille) {
    let geometrie = grille(3, 3);
    let xc = 700_037.5;
    let yc = 6_500_962.5;
    let etat = EtatArbres::depuis_initiaux(vec![
        arbre("a_centre", "03", &geometrie, xc, yc, 30.0, 20.0),
        arbre("b_14_9", "03", &geometrie, xc + 14.9, yc, 30.0, 20.0),
        arbre("c_15_1", "03", &geometrie, xc - 15.1, yc, 40.0, 20.0),
    ])
    .unwrap();
    (etat, geometrie)
}

#[test]
fn disque_de_15_m_l_arbre_a_14_9_m_compte_celui_a_15_1_m_non() {
    let (etat, geometrie) = etat_disque();
    let index = concurrence::indexer(&etat, &geometrie).unwrap();
    let resultats = concurrence::calculer(&etat, &geometrie, &index);
    // Un arbre de 30 cm dans le disque de 706,858 m² : π 0,15² × 10 000 / (π 15²) = 1 m²/ha.
    let un = concurrence::surface_terriere_m2(30.0) * 10_000.0 / concurrence::aire_disque_m2();
    assert!(proche(un, 1.0, 1e-12));
    // a_centre (rang 0) : lui-même + b à 14,9 m ; c à 15,1 m ne compte pas.
    assert!(
        proche(resultats[0].ba_plot, 2.0, 1e-12),
        "{}",
        resultats[0].ba_plot
    );
    // b a le même diamètre : il n'entre pas dans bal (strictement plus gros seulement).
    assert_eq!(resultats[0].bal, 0.0);
    // c (rang 2, 40 cm) est à 30,1 m de b et à 15,1 m de a : seul.
    let quarante =
        concurrence::surface_terriere_m2(40.0) * 10_000.0 / concurrence::aire_disque_m2();
    assert!(proche(resultats[2].ba_plot, quarante, 1e-12));
    assert!(proche(quarante, 16.0 / 9.0, 1e-12));
}

#[test]
fn le_bal_ne_compte_que_les_plus_gros_et_le_voisinage_passe_les_bords_de_cellule() {
    let geometrie = grille(3, 3);
    // Petit arbre au bord est de la cellule 4, gros arbre dans la cellule 5 à 10 m.
    let x = 700_049.0;
    let y = 6_500_962.5;
    let etat = EtatArbres::depuis_initiaux(vec![
        arbre("petit", "03", &geometrie, x, y, 20.0, 15.0),
        arbre("gros", "09", &geometrie, x + 10.0, y, 40.0, 25.0),
    ])
    .unwrap();
    assert_eq!(etat.cellule, vec![5, 4]); // « gros » < « petit » : gros au rang 0
    let index = concurrence::indexer(&etat, &geometrie).unwrap();
    let resultats = concurrence::calculer(&etat, &geometrie, &index);
    let g20 = concurrence::surface_terriere_m2(20.0) * 10_000.0 / concurrence::aire_disque_m2();
    let g40 = concurrence::surface_terriere_m2(40.0) * 10_000.0 / concurrence::aire_disque_m2();
    // Rang 1 = petit : voit le gros (cellule voisine) dans ba_plot et dans bal.
    assert!(proche(resultats[1].ba_plot, g20 + g40, 1e-12));
    assert!(proche(resultats[1].bal, g40, 1e-12));
    // Rang 0 = gros : bal nul.
    assert_eq!(resultats[0].bal, 0.0);
    assert!(proche(resultats[0].ba_plot, g20 + g40, 1e-12));
}

#[test]
fn un_disque_qui_deborde_de_la_grille_est_compte_au_bord_sans_correction() {
    let (etat, geometrie) = etat_disque();
    let index = concurrence::indexer(&etat, &geometrie).unwrap();
    let resultats = concurrence::calculer(&etat, &geometrie, &index);
    // Grille de 75 m : le centre est à 37,5 m des bords (pas au bord) ; b à 22,6 m du bord est
    // (pas au bord) ; c à 22,4 m du bord ouest (pas au bord).
    assert!(!resultats[0].au_bord);
    let geometrie_bord = grille(3, 3);
    assert!(geometrie_bord.disque_deborde(700_012.5, 6_500_962.5)); // à 12,5 m du bord ouest
    assert!(!geometrie_bord.disque_deborde(700_037.5, 6_500_962.5));
    assert!(geometrie_bord.disque_deborde(700_037.5, 6_500_986.0)); // à 14 m du bord nord
}

// ------------------------------------------------------------------------------------------
// Accroissement et sorties de domaine

#[test]
fn l_accroissement_vaut_deux_fois_exp_eta_et_les_sorties_de_domaine_ont_leur_sens() {
    let jeux = Jeux::essai();
    let (jeu, _) = jeux
        .croissance
        .chercher("growth_gam", "03", &referentiel())
        .unwrap();
    let mut sorties = SortiesParSens::default();
    let covariables = accroissement::covariables_arbre(30.0, 10.0, 2.0, 5.0, -1.0, 0.05);
    let dd = accroissement::accroissement_diametre(jeu, &covariables, "B10", &mut sorties).unwrap();
    assert!(proche(dd, 0.4, 1e-15), "{dd}");
    assert_eq!(sorties.total(), 0);
    // d130 = 5 cm sous le premier nœud (10 cm), puis 70 cm au-dessus du dernier (60 cm).
    let bas = accroissement::covariables_arbre(5.0, 10.0, 2.0, 5.0, -1.0, 0.05);
    let haut = accroissement::covariables_arbre(70.0, 10.0, 2.0, 5.0, -1.0, 0.05);
    accroissement::accroissement_diametre(jeu, &bas, "B10", &mut sorties).unwrap();
    accroissement::accroissement_diametre(jeu, &haut, "B10", &mut sorties).unwrap();
    accroissement::accroissement_diametre(jeu, &haut, "B10", &mut sorties).unwrap();
    assert_eq!(sorties.pour(Variable::D130), (1, 2));
    assert_eq!(sorties.total(), 3);
}

#[test]
fn une_covariable_manquante_est_une_erreur_code_2() {
    let jeux = Jeux::essai();
    let (jeu, _) = jeux
        .croissance
        .chercher("growth_gam", "03", &referentiel())
        .unwrap();
    let mut sorties = SortiesParSens::default();
    let erreur =
        accroissement::predicteur(jeu, &Covariables::default(), "B10", &mut sorties).unwrap_err();
    assert_eq!(erreur.code, CodeSortie::EntreeRefusee);
}

// ------------------------------------------------------------------------------------------
// Hauteur : Chapman-Richards et Korf

#[test]
fn pas_exact_de_chapman_richards_contre_la_forme_fermee() {
    // H(t) = 30 (1 − e^(−0,022 t))^1,5 ; H(30), H(31), H(30,5) calculés en Python.
    let (a, k, p) = (30.0, 0.022, 1.5);
    let h30 = 10.074939136312661;
    let h31 = 10.428759721286882;
    let h30_5 = 10.25231360468309;
    let un_an = hauteur::avance_chapman_richards(h30, a, k, p, 1.0);
    assert!(proche(un_an, h31, 1e-12), "{un_an}");
    let demi = hauteur::avance_chapman_richards(h30, a, k, p, 0.5);
    assert!(proche(demi, h30_5, 1e-12), "{demi}");
    // Cent pas d'un an redonnent la forme fermée à H(130).
    let mut h = h30;
    for _ in 0..100 {
        h = hauteur::avance_chapman_richards(h, a, k, p, 1.0);
    }
    let ferme = a * (1.0 - (-k * 130.0_f64).exp()).powf(p);
    assert!(proche(h, ferme, 1e-10), "{h} contre {ferme}");
}

#[test]
fn chapman_richards_a_pour_asymptote_site_potential_et_dh_reste_positif() {
    let courbe = Courbe::ChapmanRichards { k: 0.022, p: 1.5 };
    let normal = hauteur::avancer_hdom(&courbe, 10.074939136312661, 30.0, None, 1.0).unwrap();
    assert!(proche(normal.h, 10.428759721286882, 1e-12));
    assert!(normal.delta > 0.0);
    assert!(!normal.au_plafond && !normal.au_dessus && !normal.dh_mis_a_zero);
    // Au-dessus du plafond : dH < 0 mis à 0, compté et signalé, la hauteur n'est pas corrigée.
    let dessus = hauteur::avancer_hdom(&courbe, 32.0, 30.0, None, 1.0).unwrap();
    assert_eq!(dessus.delta, 0.0);
    assert_eq!(dessus.h, 32.0);
    assert!(dessus.au_plafond && dessus.au_dessus && dessus.dh_mis_a_zero);
    // Au plafond exactement : dH = 0, compté au plafond, pas au-dessus.
    let pile = hauteur::avancer_hdom(&courbe, 30.0, 30.0, None, 1.0).unwrap();
    assert_eq!(pile.delta, 0.0);
    assert!(pile.au_plafond && !pile.au_dessus);
}

#[test]
fn pas_exact_de_korf_contre_la_forme_recursive_et_la_forme_fermee() {
    let (a, b, c, p_f) = (56.45, 0.03, 1.235, 0.4025);
    // Un an depuis 20 m (forme du contrat), valeur Python.
    let un_an = hauteur::avance_korf(20.0, a, b, c, p_f, 1.0).unwrap();
    assert!(proche(un_an, 20.316979212743444, 1e-12), "{un_an}");
    // Vingt pas d'un an = un pas de vingt ans (X avance de p_f · b par an).
    let mut h = 20.0;
    for _ in 0..20 {
        h = hauteur::avance_korf(h, a, b, c, p_f, 1.0).unwrap();
    }
    let vingt = hauteur::avance_korf(20.0, a, b, c, p_f, 20.0).unwrap();
    assert!(proche(h, vingt, 1e-10), "{h} contre {vingt}");
    // Hors de ]0 ; a[ : pas de valeur.
    assert!(hauteur::avance_korf(a, a, b, c, p_f, 1.0).is_none());
    assert!(hauteur::avance_korf(0.0, a, b, c, p_f, 1.0).is_none());
}

#[test]
fn la_classe_de_korf_est_celle_dont_la_hauteur_a_100_ans_est_la_plus_proche_du_plafond() {
    let (a, b, c) = (56.45, 0.03, 1.235);
    let p_f = [0.555, 0.47875, 0.4025, 0.32625, 0.25];
    let reference = reference_korf();
    // H(100) par classe, de (6 ans ; 1,375 m) par 94 pas récursifs, en Python.
    let attendues = [
        36.011622694249489,
        33.529488030654321,
        30.491675618865226,
        26.728823384276915,
        22.030646505205738,
    ];
    for (rang, attendue) in attendues.iter().enumerate() {
        let h = hauteur::hauteur_korf_reference(a, b, c, p_f[rang], &reference);
        assert!(proche(h, *attendue, 1e-9), "classe {} : {h}", rang + 1);
    }
    // 29,2 m (point de référence de nemeton) : classe 3 ; 35 m : classe 1 ; 10 m : classe 5.
    assert_eq!(
        hauteur::choisir_classe_korf(a, b, c, &p_f, &reference, 29.2).unwrap(),
        (3, 0.4025)
    );
    assert_eq!(
        hauteur::choisir_classe_korf(a, b, c, &p_f, &reference, 35.0)
            .unwrap()
            .0,
        1
    );
    assert_eq!(
        hauteur::choisir_classe_korf(a, b, c, &p_f, &reference, 10.0)
            .unwrap()
            .0,
        5
    );
    // À égalité (milieu exact entre deux classes, à l'arrondi près), la plus petite classe.
    let milieu = (attendues[1] + attendues[2]) / 2.0;
    let classe = hauteur::choisir_classe_korf(a, b, c, &p_f, &reference, milieu)
        .unwrap()
        .0;
    assert!(classe == 2 || classe == 3);
}

#[test]
fn korf_sans_point_de_depart_est_refuse_code_2_et_l_asymptote_est_signalee() {
    let courbe = Courbe::Korf {
        a: 56.45,
        b: 0.03,
        c: 1.235,
        p_f: [0.555, 0.47875, 0.4025, 0.32625, 0.25],
    };
    let erreur = hauteur::avancer_hdom(&courbe, 20.0, 29.2, None, 1.0).unwrap_err();
    assert_eq!(erreur.code, CodeSortie::EntreeRefusee);
    let reference = reference_korf();
    let normal = hauteur::avancer_hdom(&courbe, 20.0, 29.2, Some(&reference), 1.0).unwrap();
    assert_eq!(normal.classe_korf, Some(3));
    assert!(proche(normal.h, 20.316979212743444, 1e-12));
    // Au-dessus du plafond, Korf continue (rien n'est corrigé), c'est signalé.
    let dessus = hauteur::avancer_hdom(&courbe, 31.0, 29.2, Some(&reference), 1.0).unwrap();
    assert!(dessus.au_dessus && dessus.delta > 0.0);
    let asymptote = hauteur::avancer_hdom(&courbe, 60.0, 29.2, Some(&reference), 1.0).unwrap();
    assert!(asymptote.au_dela_asymptote);
    assert_eq!(asymptote.delta, 0.0);
}

#[test]
fn une_hdom_nulle_ou_nan_est_un_controle_echoue_code_3() {
    let courbe = Courbe::ChapmanRichards { k: 0.022, p: 1.5 };
    for h in [0.0, -1.0, f64::NAN, f64::INFINITY] {
        let erreur = hauteur::avancer_hdom(&courbe, h, 30.0, None, 1.0).unwrap_err();
        assert_eq!(erreur.code, CodeSortie::ControleEchoue);
    }
    let erreur = hauteur::avancer_hdom(&courbe, 10.0, f64::NAN, None, 1.0).unwrap_err();
    assert_eq!(erreur.code, CodeSortie::EntreeRefusee);
}

#[test]
fn la_hausse_d_un_arbre_n_est_jamais_negative() {
    assert_eq!(hauteur::hausse_arbre(0.8, 0.5), (0.4, false));
    assert_eq!(hauteur::hausse_arbre(-0.2, 0.5), (0.0, true));
    assert_eq!(hauteur::hausse_arbre(0.8, 0.0), (0.0, false));
}

#[test]
fn le_diametre_dominant_suit_la_definition_de_dynamics() {
    // Huit arbres de 80 à 10 cm dans 0,0625 ha : 16 tiges/ha chacun ; 100 tiges = six arbres
    // entiers et le quart du septième. Valeur Python : 56,568542494923804.
    let d = [10.0, 80.0, 30.0, 70.0, 60.0, 20.0, 50.0, 40.0];
    let d_dom = hauteur::diametre_dominant(&d, 0.0625).unwrap();
    assert!(proche(d_dom, 56.568542494923804, 1e-12), "{d_dom}");
    assert_eq!(hauteur::diametre_dominant(&[], 0.0625), None);
    assert_eq!(hauteur::diametre_dominant(&[25.0], 0.0625), Some(25.0));
}

#[test]
fn la_duree_de_la_date_de_vol_a_la_fin_de_t0() {
    assert_eq!(hauteur::jours_au_premier_janvier(1970), 0);
    assert_eq!(hauteur::jours_au_premier_janvier(2022), 18_993);
    assert_eq!(hauteur::jours_au_premier_janvier(1900), -25_567);
    assert_eq!(hauteur::jours_au_premier_janvier(2400), 157_054);
    // Vol le 2021-07-01 (18 809), t0 = 2021 : 184 jours jusqu'au 2022-01-01.
    let duree = hauteur::annees_de_vol_a_t0(18_809.0, 2021).unwrap();
    assert!(proche(duree, 184.0 / 365.2425, 1e-15));
    // Vol après la fin de t0 : refusé ; date absente : refusée.
    assert_eq!(
        hauteur::annees_de_vol_a_t0(18_809.0, 2020)
            .unwrap_err()
            .code,
        CodeSortie::EntreeRefusee
    );
    assert_eq!(
        hauteur::annees_de_vol_a_t0(f64::NAN, 2021)
            .unwrap_err()
            .code,
        CodeSortie::EntreeRefusee
    );
}

// ------------------------------------------------------------------------------------------
// Mortalité et recrutement

#[test]
fn la_mort_est_tiree_selon_le_risque_annuel_cloglog() {
    let p = mortalite::probabilite_annuelle(0.02_f64.ln());
    assert!(proche(p, 1.0 - (-0.02_f64).exp(), 1e-15));
    let essence = packer_essence("09").unwrap();
    for numero in 0..200 {
        let tire = u(42, 2022, numero, essence, Sorte::Mort);
        assert_eq!(mortalite::meurt(42, 2022, numero, essence, p), tire < p);
    }
}

#[test]
fn arrondi_aleatoire_fait_a_la_main() {
    // λ = 2,3 : 3 si u < 0,3, sinon 2.
    assert_eq!(
        recrutement::arrondi_aleatoire(2.3, 0.29, 2022, 0, "09").unwrap(),
        3
    );
    assert_eq!(
        recrutement::arrondi_aleatoire(2.3, 0.31, 2022, 0, "09").unwrap(),
        2
    );
    assert_eq!(
        recrutement::arrondi_aleatoire(0.0, 0.0, 2022, 0, "09").unwrap(),
        0
    );
    assert_eq!(
        recrutement::arrondi_aleatoire(4.0, 0.0, 2022, 0, "09").unwrap(),
        4
    );
    for lambda in [f64::NAN, f64::INFINITY, -0.1, 1e20] {
        let erreur = recrutement::arrondi_aleatoire(lambda, 0.5, 2022, 7, "09").unwrap_err();
        assert_eq!(erreur.code, CodeSortie::ControleEchoue);
        assert!(erreur.message.contains("cellule 7"));
    }
}

#[test]
fn arrondi_aleatoire_garde_l_esperance_sur_beaucoup_de_cellules() {
    // λ = 2,5 sur 20 000 cellules : moyenne attendue 2,5, écart type de la moyenne 0,0035.
    let essence = packer_essence("03").unwrap();
    let mut total: u64 = 0;
    let mut valeurs = [0u64; 2];
    let n = 20_000;
    for cellule in 0..n {
        let k = recrutement::nombre_de_recrues(42, 2022, cellule, "03", essence, 2.5).unwrap();
        assert!(k == 2 || k == 3);
        valeurs[(k - 2) as usize] += 1;
        total += k;
    }
    let moyenne = total as f64 / n as f64;
    assert!(proche(moyenne, 2.5, 0.02), "{moyenne}");
    assert!(valeurs[0] > 0 && valeurs[1] > 0);
}

#[test]
fn une_recrue_a_le_diametre_du_seuil_un_identifiant_et_une_position_dans_sa_cellule() {
    assert!(proche(
        recrutement::d130_recrue_cm(),
        7.480282325319081,
        1e-14
    ));
    assert_eq!(recrutement::tree_id_recrue(4, 2022, 0), "r4_2022_0");
    let geometrie = grille(3, 3);
    let (x_ouest, x_est, y_sud, y_nord) = geometrie.bornes(4);
    let essence = packer_essence("09").unwrap();
    for numero in 0..100 {
        let (x, y) = recrutement::position(42, 2022, numero, essence, x_ouest, y_nord, 25.0);
        assert!(x >= x_ouest && x < x_est && y > y_sud && y <= y_nord);
        assert_eq!(cellule_de(&geometrie, x, y), 4);
    }
}

// ------------------------------------------------------------------------------------------
// Contrôles

#[test]
fn nan_non_fini_d130_ou_h_nuls_sont_un_controle_echoue_code_3() {
    let geometrie = grille(3, 3);
    let base = EtatArbres::depuis_initiaux(vec![arbre(
        "t1",
        "03",
        &geometrie,
        700_012.5,
        6_500_987.5,
        30.0,
        20.0,
    )])
    .unwrap();
    assert!(controles::controler_arbres(2022, &base, &[5.0], &[4.0]).is_ok());
    let cas: Vec<(&str, f64)> = vec![
        ("d130", f64::NAN),
        ("d130", 0.0),
        ("d130", -1.0),
        ("h", 0.0),
        ("h", f64::INFINITY),
        ("x", f64::NAN),
    ];
    for (grandeur, valeur) in cas {
        let mut etat = base.clone();
        match grandeur {
            "d130" => etat.d130[0] = valeur,
            "h" => etat.h[0] = valeur,
            _ => etat.x[0] = valeur,
        }
        let erreur = controles::controler_arbres(2022, &etat, &[5.0], &[4.0]).unwrap_err();
        assert_eq!(
            erreur.code,
            CodeSortie::ControleEchoue,
            "{grandeur} = {valeur}"
        );
        assert_eq!(erreur.code_sortie(), 3);
        assert!(erreur.message.contains("année 2022") && erreur.message.contains("t1"));
        assert!(erreur.message.contains(grandeur));
    }
    let erreur = controles::controler_arbres(2022, &base, &[-0.1], &[4.0]).unwrap_err();
    assert_eq!(erreur.code, CodeSortie::ControleEchoue);
    assert!(controles::controler_valeur(2022, "x", "hcb", 0.0, Positivite::Positive).is_ok());
}

#[test]
fn la_regle_des_petites_valeurs_met_a_zero_sous_1e_9_fois_le_maximum() {
    // max |Q| = 2 : seuil 2e-9 ; 1e-9 et −1,5e-9 (positives comprises, T10) passent à 0 ;
    // 2e-9 (égal au seuil) et 3e-9 restent.
    let mut champ = vec![2.0, 1e-9, -1.5e-9, 2e-9, 3e-9, 0.0, -2.0];
    let n = controles::mettre_a_zero(&mut champ).unwrap();
    assert_eq!(n, 2);
    assert_eq!(champ, vec![2.0, 0.0, 0.0, 2e-9, 3e-9, 0.0, -2.0]);
    let mut vide: Vec<f64> = Vec::new();
    assert_eq!(controles::mettre_a_zero(&mut vide).unwrap(), 0);
    let mut zeros = vec![0.0, 0.0];
    assert_eq!(controles::mettre_a_zero(&mut zeros).unwrap(), 0);
    let mut mauvais = vec![1.0, f64::NAN];
    assert_eq!(
        controles::mettre_a_zero(&mut mauvais).unwrap_err().code,
        CodeSortie::ControleEchoue
    );
}

// ------------------------------------------------------------------------------------------
// Paramètres manquants

#[test]
fn ce_qui_manque_dans_les_parametres_est_une_erreur_code_2() {
    let referentiel = referentiel();
    let jeux = Jeux::essai();
    let essences = vec!["03".to_string()];
    // Sans allométrie cw.
    let mut sans_cw = lignes_allometrie();
    sans_cw.retain(|l| l.model != "cw");
    let allometrie = Parametres::depuis_lignes(&sans_cw).unwrap();
    let mut sources = jeux.sources();
    sources.allometrie = &allometrie;
    let erreur = Modeles::preparer(&sources, &referentiel, &essences, &[], None).unwrap_err();
    assert_eq!(erreur.code, CodeSortie::EntreeRefusee);
    assert!(erreur.message.contains("cw"), "{}", erreur.message);
    // Sans CR_max.
    let mut sans_cr_max = lignes_allometrie();
    sans_cr_max.retain(|l| l.term != "CR_max");
    let allometrie = Parametres::depuis_lignes(&sans_cr_max).unwrap();
    let mut sources = jeux.sources();
    sources.allometrie = &allometrie;
    let erreur = Modeles::preparer(&sources, &referentiel, &essences, &[], None).unwrap_err();
    assert_eq!(erreur.code, CodeSortie::EntreeRefusee);
    assert!(erreur.message.contains("CR_max"));
    // Sans courbe pour 03 (seul 09 a Korf) : code 2.
    let mut sans_cr = lignes_hauteur();
    sans_cr.retain(|l| l.model != "chapman_richards");
    let hauteur_seule = Parametres::depuis_lignes(&sans_cr).unwrap();
    let mut sources = jeux.sources();
    sources.courbe_hauteur = &hauteur_seule;
    let erreur = Modeles::preparer(&sources, &referentiel, &essences, &[], None).unwrap_err();
    assert_eq!(erreur.code, CodeSortie::EntreeRefusee);
    // Une candidate au recrutement sans jeu de recrutement : code 2.
    let vide = Parametres::depuis_lignes(&[]).unwrap();
    let mut sources = jeux.sources();
    sources.recrutement = &vide;
    let erreur = Modeles::preparer(&sources, &referentiel, &essences, &essences, None).unwrap_err();
    assert_eq!(erreur.code, CodeSortie::EntreeRefusee);
    // Les candidates (T6) : celles qui ont les quatre jeux.
    let candidates = pas::essences_candidates(&sources, &referentiel, &essences);
    assert!(candidates.is_empty());
    let candidates = pas::essences_candidates(
        &jeux.sources(),
        &referentiel,
        &["09".to_string(), "03".to_string()],
    );
    assert_eq!(candidates, vec!["03".to_string(), "09".to_string()]);
}

#[test]
fn plusieurs_bandes_de_site_potential_sans_table_est_une_erreur_code_2() {
    let mut c = cellules(1, 1, 10.0, 30.0);
    c.nombre_bandes = 2;
    c.site_potential = vec![30.0, 25.0];
    assert!(c.verifier().is_ok());
    assert_eq!(
        c.plafond(0, "03").unwrap_err().code,
        CodeSortie::EntreeRefusee
    );
    c.bande_par_essence = vec![("03".to_string(), 1)];
    assert_eq!(c.plafond(0, "03").unwrap(), 25.0);
    c.bande_par_essence = vec![("03".to_string(), 2)];
    assert_eq!(c.verifier().unwrap_err().code, CodeSortie::EntreeRefusee);
}

// ------------------------------------------------------------------------------------------
// Le pas entier

#[test]
fn l_etat_initial_avance_de_la_date_de_vol_a_t0_en_gardant_l_ancre_du_mnh() {
    let jeux = Jeux::essai();
    let modeles = modeles(&jeux, &[], Some(reference_korf()));
    let cellules = cellules(3, 3, 10.0, 30.0);
    let geometrie = cellules.geometrie;
    // Un seul arbre de 03 dans la cellule 0 : d_dom = son d130, rel_d = 1, f(1) = 0,9.
    let etat = EtatArbres::depuis_initiaux(vec![arbre(
        "t1",
        "03",
        &geometrie,
        700_012.5,
        6_500_987.5,
        30.0,
        12.0,
    )])
    .unwrap();
    let resultat = pas::initialiser_t0(&etat, &cellules, &modeles, 2021).unwrap();
    let duree = 184.0 / 365.2425;
    let h_dom = hauteur::avance_chapman_richards(10.0, 30.0, 0.022, 1.5, duree);
    assert!(proche(resultat.cellules.h_dom[0], h_dom, 1e-12));
    let attendue = 12.0 + 0.9 * (h_dom - 10.0);
    assert!(
        proche(resultat.etat.h[0], attendue, 1e-12),
        "{} contre {attendue}",
        resultat.etat.h[0]
    );
    // Les cellules sans arbre gardent h0 ; elles sont comptées.
    assert_eq!(resultat.cellules.h_dom[1], 10.0);
    assert_eq!(resultat.comptes.cellules_sans_arbre, 8);
    // hcb = h (1 − CR), CR = 1,1 − 0,15 ln 30 ; cw = 2 exp(−0,3 + 0,55 ln 30).
    let cr = 1.1 - 0.15 * 30.0_f64.ln();
    assert!(proche(resultat.hcb[0], attendue * (1.0 - cr), 1e-12));
    assert!(proche(
        resultat.cw[0],
        2.0 * (-0.3 + 0.55 * 30.0_f64.ln()).exp(),
        1e-12
    ));
}

#[test]
fn un_pas_fait_a_la_main_croissance_hauteur_et_recrues() {
    let jeux = Jeux::essai();
    // Candidate : 03 seule ; λ = 2,5 par cellule.
    let modeles = modeles(&jeux, &["03"], None);
    let cellules = cellules(2, 1, 10.0, 30.0);
    let geometrie = cellules.geometrie;
    let etat = EtatArbres::depuis_initiaux(vec![arbre(
        "t1",
        "03",
        &geometrie,
        700_012.5,
        6_500_987.5,
        30.0,
        12.0,
    )])
    .unwrap();
    let hdom = EtatCellules {
        h_dom: vec![10.0, 10.0],
    };
    let annee = 2022;
    let graine = 42;
    let resultat = pas::pas_annuel(&etat, &cellules, &hdom, &modeles, graine, annee).unwrap();
    let essence = packer_essence("03").unwrap();
    let p = 1.0 - (-0.02_f64).exp();
    let mort = u(graine, annee, 0, essence, Sorte::Mort) < p;
    assert_eq!(resultat.etat.vivant[0], !mort);
    let h_dom = hauteur::avance_chapman_richards(10.0, 30.0, 0.022, 1.5, 1.0);
    assert!(proche(resultat.cellules.h_dom[0], h_dom, 1e-12));
    if !mort {
        assert!(proche(resultat.etat.d130[0], 30.4, 1e-12));
        assert!(proche(
            resultat.etat.h[0],
            12.0 + 0.9 * (h_dom - 10.0),
            1e-12
        ));
    }
    // Recrues : ⌊2,5⌋ + (u < 0,5) par cellule, numérotées après l'arbre 0, cellule 0 d'abord.
    let mut attendus: Vec<u64> = Vec::new();
    for cellule in 0..2u64 {
        let tire = u(graine, annee, cellule, essence, Sorte::NbRecrues);
        attendus.push(if tire < 0.5 { 3 } else { 2 });
    }
    assert_eq!(resultat.comptes.recrues, attendus[0] + attendus[1]);
    assert_eq!(resultat.etat.len() as u64, 1 + attendus[0] + attendus[1]);
    let mut rang = 1;
    for cellule in 0..2u64 {
        for k in 0..attendus[cellule as usize] {
            assert_eq!(resultat.etat.numero[rang], rang as u64);
            assert_eq!(
                resultat.etat.tree_id[rang],
                format!("r{cellule}_{annee}_{k}")
            );
            assert_eq!(resultat.etat.cellule[rang], cellule);
            assert!(proche(
                resultat.etat.d130[rang],
                23.5 / std::f64::consts::PI,
                1e-14
            ));
            rang += 1;
        }
    }
    // Recrue de la cellule 0 : rel_d = 7,48 / 30 ; h = H_dom × (0,9 + (rel_d − 1) / 2).
    let rel_d = recrutement::d130_recrue_cm() / 30.0;
    assert!(proche(
        resultat.etat.h[1],
        h_dom * (0.9 + (rel_d - 1.0) / 2.0),
        1e-12
    ));
    // Recrues de la cellule 1 (vide) : rel_d = 1, H_dom tenue (10 m), comptées.
    let premier_c1 = 1 + attendus[0] as usize;
    assert!(proche(resultat.etat.h[premier_c1], 10.0 * 0.9, 1e-12));
    assert_eq!(resultat.comptes.recrues_cellule_vide, attendus[1]);
    assert_eq!(resultat.comptes.cellules_sans_arbre, 1);
    assert_eq!(resultat.comptes.morts, u64::from(mort));
    resultat.etat.verifier().unwrap();
}

#[test]
fn aucune_recrue_dans_une_trouee_a_hdom_nulle_comptee_et_signalee() {
    // Décision de Pascal du 25/11/2026 : pas de recrue dans une cellule tant que sa hauteur
    // dominante est nulle. Trois cellules en ligne (EPSG:2154, x = est, y = nord, 25 m) :
    // 0 a un arbre et H_dom = 10 m ; 1 est vide à H_dom = 10 m ; 2 est vide à H_dom = 0 (trouée).
    let jeux = Jeux::essai();
    let modeles = modeles(&jeux, &["03"], None);
    let cellules = cellules(3, 1, 10.0, 30.0);
    let geometrie = cellules.geometrie;
    // Le point du terrain (est 700 062,5 ; nord 6 500 987,5) est dans la cellule 2, la trouée :
    // bornes du moteur (x ouest, x est, y sud, y nord) = (700 050, 700 075, 6 500 975, 6 501 000).
    assert_eq!(
        geometrie.bornes(2),
        (700_050.0, 700_075.0, 6_500_975.0, 6_501_000.0)
    );
    assert_eq!(cellule_de(&geometrie, 700_062.5, 6_500_987.5), 2);
    let etat = EtatArbres::depuis_initiaux(vec![arbre(
        "t1",
        "03",
        &geometrie,
        700_012.5,
        6_500_987.5,
        30.0,
        12.0,
    )])
    .unwrap();
    let hdom = EtatCellules {
        h_dom: vec![10.0, 10.0, 0.0],
    };
    let (annee, graine) = (2023, 42);
    let resultat = pas::pas_annuel(&etat, &cellules, &hdom, &modeles, graine, annee).unwrap();
    // La trouée garde sa H_dom nulle (aucun arbre ne donne sa courbe) et ne reçoit aucune recrue.
    assert_eq!(resultat.cellules.h_dom[2], 0.0);
    for rang in 0..resultat.etat.len() {
        assert_ne!(resultat.etat.cellule[rang], 2, "recrue dans la trouée");
        assert!(resultat.etat.h[rang] > 0.0);
    }
    // Les deux autres cellules recrutent comme avant : ⌊2,5⌋ + (u < 0,5).
    let essence = packer_essence("03").unwrap();
    let mut attendues = 0;
    for cellule in 0..2u64 {
        let tire = u(graine, annee, cellule, essence, Sorte::NbRecrues);
        attendues += if tire < 0.5 { 3 } else { 2 };
    }
    assert_eq!(resultat.comptes.recrues, attendues);
    // Compté et signalé, une ligne par (cellule, année).
    assert_eq!(resultat.comptes.cellules_trouee_sans_recrue, 1);
    let trouees: Vec<_> = resultat
        .signalements
        .iter()
        .filter(|s| s.sorte == controles::SORTE_TROUEE_SANS_RECRUE)
        .collect();
    assert_eq!(trouees.len(), 1);
    assert_eq!(trouees[0].entite, "2");
    assert_eq!(trouees[0].annee, annee);
    assert_eq!(trouees[0].valeur, Some(0.0));
    assert!(trouees[0].message.contains("aucune recrue"));
    // Une H_dom positive, même petite, n'est pas une trouée.
    let hdom = EtatCellules {
        h_dom: vec![10.0, 10.0, 0.01],
    };
    let resultat = pas::pas_annuel(&etat, &cellules, &hdom, &modeles, graine, annee).unwrap();
    assert_eq!(resultat.comptes.cellules_trouee_sans_recrue, 0);
    assert!((0..resultat.etat.len()).any(|rang| resultat.etat.cellule[rang] == 2));
}

#[test]
fn une_cellule_de_korf_sans_point_de_depart_arrete_le_pas_code_2() {
    let jeux = Jeux::essai();
    let modeles = modeles(&jeux, &[], None);
    let cellules = cellules(1, 1, 20.0, 29.2);
    let geometrie = cellules.geometrie;
    let etat = EtatArbres::depuis_initiaux(vec![arbre(
        "t1",
        "09",
        &geometrie,
        700_012.5,
        6_500_987.5,
        30.0,
        18.0,
    )])
    .unwrap();
    let hdom = EtatCellules { h_dom: vec![20.0] };
    let erreur = pas::pas_annuel(&etat, &cellules, &hdom, &modeles, 42, 2022).unwrap_err();
    assert_eq!(erreur.code, CodeSortie::EntreeRefusee);
    assert!(
        erreur.message.contains("Korf") && erreur.message.contains("cellule 0"),
        "{}",
        erreur.message
    );
}

#[test]
fn un_nan_dans_l_etat_arrete_le_pas_code_3() {
    let jeux = Jeux::essai();
    let modeles = modeles(&jeux, &[], Some(reference_korf()));
    let cellules = cellules(1, 1, 10.0, 30.0);
    let geometrie = cellules.geometrie;
    let mut etat = EtatArbres::depuis_initiaux(vec![
        arbre("t1", "03", &geometrie, 700_010.0, 6_500_987.5, 30.0, 12.0),
        arbre("t2", "03", &geometrie, 700_015.0, 6_500_987.5, 25.0, 11.0),
    ])
    .unwrap();
    etat.d130[1] = f64::NAN;
    let hdom = EtatCellules { h_dom: vec![10.0] };
    let erreur = pas::pas_annuel(&etat, &cellules, &hdom, &modeles, 42, 2022).unwrap_err();
    assert_eq!(erreur.code_sortie(), 3, "{}", erreur.message);
    assert!(
        erreur.message.contains("t2") && erreur.message.contains("d130"),
        "{}",
        erreur.message
    );
}

#[test]
fn un_accroissement_infini_est_arrete_par_les_controles_code_3() {
    // exp(800) déborde en f64 : d130 devient infini, le contrôle de fin de pas l'arrête.
    let mut jeux = Jeux::essai();
    let mut lignes = lignes_croissance();
    lignes[0].value = 800.0;
    jeux.croissance = Parametres::depuis_lignes(&lignes).unwrap();
    // Mortalité nulle en pratique (risque e^-700) pour que l'arbre vive et grandisse.
    jeux.mortalite =
        Parametres::depuis_lignes(&[toutes("mortality_gam", "intercept", None, None, -700.0)])
            .unwrap();
    let modeles = modeles(&jeux, &[], None);
    let cellules = cellules(1, 1, 10.0, 30.0);
    let geometrie = cellules.geometrie;
    let etat = EtatArbres::depuis_initiaux(vec![arbre(
        "t1",
        "03",
        &geometrie,
        700_012.5,
        6_500_987.5,
        30.0,
        12.0,
    )])
    .unwrap();
    let hdom = EtatCellules { h_dom: vec![10.0] };
    let erreur = pas::pas_annuel(&etat, &cellules, &hdom, &modeles, 42, 2022).unwrap_err();
    assert_eq!(erreur.code, CodeSortie::ControleEchoue);
    assert!(
        erreur.message.contains("année 2022") && erreur.message.contains("d130"),
        "{}",
        erreur.message
    );
}

#[test]
fn une_hdom_au_dessus_du_plafond_est_comptee_et_signalee_sans_correction() {
    let jeux = Jeux::essai();
    let modeles = modeles(&jeux, &[], None);
    let cellules = cellules(1, 1, 32.0, 30.0);
    let geometrie = cellules.geometrie;
    let etat = EtatArbres::depuis_initiaux(vec![arbre(
        "t1",
        "03",
        &geometrie,
        700_012.5,
        6_500_987.5,
        30.0,
        31.0,
    )])
    .unwrap();
    let hdom = EtatCellules { h_dom: vec![32.0] };
    let resultat = pas::pas_annuel(&etat, &cellules, &hdom, &modeles, 7, 2022).unwrap();
    assert_eq!(resultat.cellules.h_dom[0], 32.0);
    assert_eq!(resultat.comptes.cellules_au_plafond, 1);
    assert_eq!(resultat.comptes.cellules_au_dessus_du_plafond, 1);
    let s = &resultat.signalements[0];
    assert_eq!(
        (s.annee, s.entite.as_str(), s.sorte.as_str()),
        (2022, "0", "hdom_au_dessus_du_plafond")
    );
    assert_eq!(s.valeur, Some(32.0));
    if resultat.etat.vivant[0] {
        assert_eq!(resultat.etat.h[0], 31.0); // ΔH_dom = 0 : l'arbre ne grandit pas
    }
}

// ------------------------------------------------------------------------------------------
// Identité au bit près entre 1 et N fils

/// Un massif d'essai : 6 × 5 cellules, 400 arbres de 03 et 09 aux positions tirées par l'aléa.
fn massif() -> (EtatArbres, Cellules) {
    let mut c = cellules(6, 5, 14.0, 30.0);
    // Une station qui varie d'une cellule à l'autre, et quelques cellules non simulées.
    for cellule in 0..30 {
        c.trophic[cellule] = 4.0 + (cellule % 5) as f64 * 0.5;
        c.h0[cellule] = 8.0 + (cellule % 7) as f64 * 3.0;
        c.site_potential[cellule] = 26.0 + (cellule % 4) as f64 * 2.0;
    }
    c.simulee[29] = false;
    c.simulee[0] = false;
    let geometrie = c.geometrie;
    let mut arbres = Vec::new();
    for i in 0..400u64 {
        let ux = u(99, 0, i, 1, Sorte::RecrueX);
        let uy = u(99, 0, i, 1, Sorte::RecrueY);
        let ud = u(99, 0, i, 2, Sorte::Mort);
        // Rester hors des cellules 0 et 29 (non simulées) : x dans les colonnes 1 à 4.
        let x = X0 + 25.0 + ux * 100.0;
        let y = Y0 - uy * 125.0;
        let espece = if i % 3 == 0 { "09" } else { "03" };
        let d130 = 8.0 + ud * 50.0;
        arbres.push(arbre(
            &format!("t{i:04}"),
            espece,
            &geometrie,
            x,
            y,
            d130,
            6.0 + ud * 20.0,
        ));
    }
    (EtatArbres::depuis_initiaux(arbres).unwrap(), c)
}

/// Trois années enchaînées (t0 puis trois pas), dans un pool de `fils` fils.
fn simuler(fils: usize) -> Vec<ResultatPas> {
    let pool = rayon::ThreadPoolBuilder::new()
        .num_threads(fils)
        .build()
        .unwrap();
    pool.install(|| {
        let jeux = Jeux::essai();
        let modeles = modeles(&jeux, &["03", "09"], Some(reference_korf()));
        let (etat, cellules) = massif();
        let mut resultats = Vec::new();
        let initial = pas::initialiser_t0(&etat, &cellules, &modeles, 2021).unwrap();
        let mut courant = initial.etat.clone();
        let mut hdom = initial.cellules.clone();
        resultats.push(initial);
        for annee in 2022..2025 {
            let resultat =
                pas::pas_annuel(&courant, &cellules, &hdom, &modeles, 20261125, annee).unwrap();
            courant = resultat.etat.clone();
            courant.retirer_morts();
            hdom = resultat.cellules.clone();
            resultats.push(resultat);
        }
        resultats
    })
}

fn bits(valeurs: &[f64]) -> Vec<u64> {
    valeurs.iter().map(|v| v.to_bits()).collect()
}

fn signature(resultat: &ResultatPas) -> (Vec<u64>, Vec<String>, Vec<bool>, Comptes, Vec<String>) {
    let mut nombres = Vec::new();
    nombres.extend(bits(&resultat.etat.x));
    nombres.extend(bits(&resultat.etat.y));
    nombres.extend(bits(&resultat.etat.d130));
    nombres.extend(bits(&resultat.etat.h));
    nombres.extend(bits(&resultat.hcb));
    nombres.extend(bits(&resultat.cw));
    nombres.extend(bits(&resultat.cellules.h_dom));
    nombres.extend(resultat.etat.numero.iter().copied());
    let signalements = resultat
        .signalements
        .iter()
        .map(|s| {
            format!(
                "{}|{}|{}|{}|{:?}",
                s.annee,
                s.entite,
                s.sorte,
                s.message,
                s.valeur.map(|v| v.to_bits())
            )
        })
        .collect();
    (
        nombres,
        resultat.etat.tree_id.clone(),
        resultat.etat.vivant.clone(),
        resultat.comptes,
        signalements,
    )
}

#[test]
fn identite_au_bit_pres_entre_1_2_3_4_et_7_fils() {
    let reference = simuler(1);
    // Le massif d'essai fait vraiment quelque chose : morts, recrues, cellules mêlées, Korf.
    let mut total = Comptes::default();
    for resultat in &reference {
        total.ajouter(&resultat.comptes);
    }
    assert!(total.morts > 0, "{total:?}");
    assert!(total.recrues > 0);
    assert!(total.cellules_melees > 0);
    assert!(total.disques_au_bord > 0);
    assert!(reference[0]
        .signalements
        .iter()
        .any(|s| s.sorte == "classe_korf"));
    for fils in [2, 3, 4, 7] {
        let autre = simuler(fils);
        assert_eq!(autre.len(), reference.len());
        for (annee, (a, b)) in reference.iter().zip(autre.iter()).enumerate() {
            assert_eq!(signature(a), signature(b), "{fils} fils, pas {annee}");
        }
    }
}
