//! Tests de la régénération par cohortes (mission 062) : dispersion par FFT (src/dispersion.rs),
//! cohortes de semis (src/semis.rs) et pas annuel en mode `cohorts` (src/pas.rs, src/sorties.rs).
//!
//! Coordonnées : x = est, y = nord, en m, EPSG:2154 ; `cell_id` = ligne × largeur + colonne,
//! ligne 0 au nord. Les valeurs des paramètres sont des réglages d'essai, sans sens écologique.
//!
//! La zone d'essai en mémoire est celle de `tests/non_regression.rs` (incluse par `#[path]`).

#[path = "non_regression.rs"]
mod non_regression;

use std::collections::BTreeMap;
use std::path::Path;

use simulate::config::{ModeRecrutement, ReglagesRegeneration};
use simulate::dispersion::{self, PlanDispersion};
use simulate::erreurs::CodeSortie;
use simulate::grille::Grille;
use simulate::semis::{self, LigneRegeneration, ParametresSemis};
use simulate::sorties;

use non_regression::{chaines, dossier_neuf, entiers, lancement, lire_parquet, nombres, partition, referentiel, zone_d_essai, T0};

// ------------------------------------------------------------------------------------------
// Aides

/// Un champ pseudo-aléatoire déterministe (générateur congruentiel), avec des zéros.
fn champ_d_essai(n: usize, graine: u64) -> Vec<f64> {
    let mut etat = graine;
    let mut champ = Vec::with_capacity(n);
    for _ in 0..n {
        etat = etat.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
        let u = (etat >> 11) as f64 / (1u64 << 53) as f64;
        champ.push(if u < 0.3 { 0.0 } else { 1000.0 * u });
    }
    champ
}

fn parametres_d_essai() -> ParametresSemis {
    ParametresSemis {
        espece: "03".to_string(),
        echelle_noyau_m: 30.0,
        forme_noyau: 1.0,
        hauteur_maturite_m: 10.0,
        fecondite: 1000.0,
        part_installation: 0.5,
        croissance_m_an: 0.4,
        tolerance_ombre: 3.0,
        coef_extinction: 0.5,
        survie_pleine_lumiere: 0.9,
        hauteur_passage_m: 1.3,
        mortalite_stress: 0.184,
        provisoire: true,
    }
}

fn ligne_regen(species: Option<&str>, groupe: Option<&str>, term: &str, value: f64, unit: &str) -> LigneRegeneration {
    LigneRegeneration {
        species: species.map(|s| s.to_string()),
        species_group: groupe.map(|g| g.to_string()),
        term: term.to_string(),
        value,
        unit: unit.to_string(),
        provisoire: true,
        source: "essai".to_string(),
    }
}

/// Les onze termes du contrat, en `toutes_essences`, valeurs d'essai.
fn lignes_d_essai() -> Vec<LigneRegeneration> {
    let valeurs = [30.0, 1.0, 10.0, 1000.0, 0.5, 0.4, 3.0, 0.5, 0.9, 1.3, 0.184];
    let mut lignes = Vec::new();
    for (rang, (terme, unite)) in semis::TERMES.iter().enumerate() {
        lignes.push(ligne_regen(None, Some("toutes_essences"), terme, valeurs[rang], unite));
    }
    lignes
}

// ------------------------------------------------------------------------------------------
// Noyau et FFT

#[test]
fn le_noyau_est_normalise_a_1e_12_et_tronque_au_disque() {
    for (echelle, forme, k) in [(30.0, 1.0, 3), (12.0, 2.0, 5), (200.0, 0.5, 8), (1.0, 1.0, 2)] {
        let noyau = dispersion::noyau_exponentiel_puissance(echelle, forme, 25.0, k).unwrap();
        assert!((noyau.somme() - 1.0).abs() < 1e-12, "somme {}", noyau.somme());
        let k = k as i64;
        for dl in -k..=k {
            for dc in -k..=k {
                let poids = noyau.poids_de(dl, dc);
                if dl * dl + dc * dc > k * k {
                    assert_eq!(poids, 0.0, "({dl}, {dc}) hors du disque");
                } else {
                    assert!(poids >= 0.0);
                }
            }
        }
        // La forme : k(r) / k(0) = exp(−(r / a)^b), r entre centres de cellules.
        let r = 25.0;
        let attendu = (-(r / echelle).powf(forme)).exp();
        assert!((noyau.poids_de(0, 1) / noyau.poids_de(0, 0) - attendu).abs() < 1e-12);
        assert_eq!(noyau.poids_de(1, 0), noyau.poids_de(0, 1));
    }
}

#[test]
fn le_noyau_refuse_une_echelle_ou_une_forme_non_positive() {
    for (echelle, forme) in [(0.0, 1.0), (-3.0, 1.0), (30.0, 0.0), (f64::NAN, 1.0)] {
        let erreur = dispersion::noyau_exponentiel_puissance(echelle, forme, 25.0, 3).unwrap_err();
        assert_eq!(erreur.code, CodeSortie::EntreeRefusee);
    }
}

#[test]
fn la_fft_redonne_la_convolution_directe_a_1e_9() {
    for (largeur, hauteur, k, echelle, forme) in [(31, 23, 3, 30.0, 1.0), (17, 40, 5, 60.0, 2.0), (9, 9, 4, 100.0, 0.7)] {
        let noyau = dispersion::noyau_exponentiel_puissance(echelle, forme, 25.0, k).unwrap();
        let plan = PlanDispersion::nouveau(largeur, hauteur, k).unwrap();
        let spectre = plan.spectre(&noyau).unwrap();
        let champ = champ_d_essai(largeur * hauteur, (largeur * 1000 + hauteur) as u64);
        let fft = plan.convoluer(&champ, &spectre).unwrap();
        let direct = dispersion::convoluer_directement(&champ, largeur, hauteur, &noyau);
        let mut maximum: f64 = 0.0;
        for valeur in &direct {
            maximum = maximum.max(valeur.abs());
        }
        for (a, b) in fft.iter().zip(direct.iter()) {
            assert!((a - b).abs() <= 1e-9 * maximum, "FFT {a} contre directe {b}");
        }
    }
}

#[test]
fn le_bord_est_absorbant_les_graines_sorties_sont_perdues() {
    let (largeur, hauteur, k) = (12, 10, 3);
    let noyau = dispersion::noyau_exponentiel_puissance(40.0, 1.0, 25.0, k).unwrap();
    let plan = PlanDispersion::nouveau(largeur, hauteur, k).unwrap();
    let spectre = plan.spectre(&noyau).unwrap();
    // Une source au coin nord-ouest : seul le quart du disque à l'est et au sud reste dans la grille.
    let mut champ = vec![0.0; largeur * hauteur];
    champ[0] = 1.0;
    let recu = plan.convoluer(&champ, &spectre).unwrap();
    let mut total = 0.0;
    for valeur in &recu {
        total += *valeur;
    }
    let mut attendu = 0.0;
    for dl in 0..=k as i64 {
        for dc in 0..=k as i64 {
            attendu += noyau.poids_de(dl, dc);
        }
    }
    assert!((total - attendu).abs() < 1e-12, "reçu {total}, attendu {attendu}");
    assert!(total < 0.5, "la plus grande part des graines tombe hors de la grille et y est perdue");
    // Rien ne revient par l'autre bord (pas de repli circulaire) : le coin sud-est ne reçoit rien.
    let mut recu_zero = recu.clone();
    dispersion::mettre_a_zero(&mut recu_zero, 1e-9, "essai").unwrap();
    assert_eq!(recu_zero[largeur * hauteur - 1], 0.0);
    assert_eq!(recu_zero[largeur - 1], 0.0);
    assert_eq!(dispersion::cellules_tampon(largeur, hauteur, k), 18 * 16 - 120);
}

/// La source au point connu (est 700 012,5 ; nord 6 500 987,5 ; EPSG:2154), centre de la cellule
/// (ligne, colonne) d'une grille dont on choisit l'origine.
fn semis_autour_du_point_connu(ligne: usize, colonne: usize) -> (Grille, Vec<f64>) {
    let (largeur, hauteur, k) = (30, 26, 3);
    let x_point = 700_012.5;
    let y_point = 6_500_987.5;
    let grille = Grille {
        largeur,
        hauteur,
        origine_x: x_point - 12.5 - 25.0 * colonne as f64,
        origine_y: y_point + 12.5 + 25.0 * ligne as f64,
        pas: 25.0,
        valide: vec![true; largeur * hauteur],
    };
    let source = grille.cellule_de(x_point, y_point).unwrap() as usize;
    assert_eq!(grille.ligne_colonne(source as u64), (ligne, colonne), "le point tombe dans la bonne cellule");
    let noyau = dispersion::noyau_exponentiel_puissance(30.0, 1.0, 25.0, k).unwrap();
    let plan = PlanDispersion::nouveau(largeur, hauteur, k).unwrap();
    let mut champ = vec![0.0; largeur * hauteur];
    champ[source] = 5000.0;
    let mut recu = plan.convoluer(&champ, &plan.spectre(&noyau).unwrap()).unwrap();
    dispersion::mettre_a_zero(&mut recu, 1e-9, "essai").unwrap();
    (grille, recu)
}

#[test]
fn une_source_au_point_connu_ensemence_les_cellules_attendues_meme_asymetrique() {
    for (ligne, colonne) in [(12, 12), (7, 16)] {
        let (grille, recu) = semis_autour_du_point_connu(ligne, colonne);
        let mut somme = 0.0;
        let mut barycentre = (0.0, 0.0);
        for cellule in 0..recu.len() {
            let (l, c) = grille.ligne_colonne(cellule as u64);
            let dl = l as i64 - ligne as i64;
            let dc = c as i64 - colonne as i64;
            let dans = dl * dl + dc * dc <= 9;
            assert_eq!(recu[cellule] > 0.0, dans, "cellule ({l}, {c}) pour une source en ({ligne}, {colonne})");
            somme += recu[cellule];
            barycentre.0 += recu[cellule] * l as f64;
            barycentre.1 += recu[cellule] * c as f64;
        }
        assert!((somme - 5000.0).abs() < 1e-9, "toutes les graines arrivent dans le disque : {somme}");
        assert!((barycentre.0 / somme - ligne as f64).abs() < 1e-9);
        assert!((barycentre.1 / somme - colonne as f64).abs() < 1e-9);
        if ligne != colonne {
            // Grille transposée : la source serait en (colonne, ligne).
            let miroir = colonne * grille.largeur + ligne;
            assert_eq!(recu[miroir], 0.0, "semis autour de la cellule miroir : axes transposés");
        }
        // Le voisin à l'est (x + 25 m) reçoit autant que le voisin au sud (y − 25 m) : noyau isotrope.
        let est = grille.cellule_de(700_037.5, 6_500_987.5).unwrap() as usize;
        let sud = grille.cellule_de(700_012.5, 6_500_962.5).unwrap() as usize;
        assert!((recu[est] - recu[sud]).abs() < 1e-9 * recu[est]);
        assert_eq!(grille.ligne_colonne(est as u64), (ligne, colonne + 1));
        assert_eq!(grille.ligne_colonne(sud as u64), (ligne + 1, colonne));
    }
}

#[test]
fn la_regle_q_met_a_zero_le_bruit_et_arrete_sur_un_negatif_au_dela_du_seuil() {
    let mut champ = vec![100.0, 1e-12, -1e-12, 0.0, 5.0];
    let zeros = dispersion::mettre_a_zero(&mut champ, 1e-9, "essai").unwrap();
    assert_eq!(zeros, 2);
    assert_eq!(champ, vec![100.0, 0.0, 0.0, 0.0, 5.0]);
    let mut fautif = vec![100.0, -1.0];
    let erreur = dispersion::mettre_a_zero(&mut fautif, 1e-9, "essai").unwrap_err();
    assert_eq!(erreur.code, CodeSortie::ControleEchoue);
    let mut non_fini = vec![1.0, f64::NAN];
    assert_eq!(
        dispersion::mettre_a_zero(&mut non_fini, 1e-9, "essai").unwrap_err().code,
        CodeSortie::ControleEchoue
    );
}

#[test]
fn la_fft_ne_depend_pas_du_nombre_de_fils() {
    let (largeur, hauteur, k) = (45, 38, 4);
    let noyau = dispersion::noyau_exponentiel_puissance(50.0, 1.5, 25.0, k).unwrap();
    let champ = champ_d_essai(largeur * hauteur, 99);
    let mut reference: Option<Vec<u64>> = None;
    for fils in [1, 2, 3, 7] {
        let pool = rayon::ThreadPoolBuilder::new().num_threads(fils).build().unwrap();
        let recu = pool.install(|| {
            let plan = PlanDispersion::nouveau(largeur, hauteur, k).unwrap();
            plan.convoluer(&champ, &plan.spectre(&noyau).unwrap()).unwrap()
        });
        let bits: Vec<u64> = recu.iter().map(|v| v.to_bits()).collect();
        match &reference {
            None => reference = Some(bits),
            Some(attendus) => assert_eq!(&bits, attendus, "{fils} fils"),
        }
    }
}

// ------------------------------------------------------------------------------------------
// Cohortes

#[test]
fn le_nombre_de_classes_est_le_premier_entier_qui_atteint_la_hauteur_de_passage() {
    assert_eq!(semis::nombre_de_classes(1.3, 0.4), 4);
    assert_eq!(semis::nombre_de_classes(1.2, 0.4), 3);
    assert_eq!(semis::nombre_de_classes(0.3, 0.4), 1);
    assert_eq!(semis::nombre_de_classes(0.8, 0.4), 2);
}

#[test]
fn le_stock_en_regime_vaut_le_flux_fois_le_temps_de_passage() {
    // À survie 1, l'état stationnaire est la formule de Pascal (Q2) : flux × temps de passage.
    let p = parametres_d_essai();
    let mut classes = vec![0.0; p.classes()];
    semis::en_regime_avec_survie(&p, 40.0, 1.0, &mut classes);
    assert_eq!(classes.len(), 4);
    assert!((semis::total(&classes) - 40.0 * 1.3 / 0.4).abs() < 1e-12);
    assert_eq!(&classes[..3], &[40.0, 40.0, 40.0]);
    assert!((semis::stock(&classes) - 40.0 * 0.25).abs() < 1e-12);
    // Sans graines ni mort, le flux passe intact pendant trois ans, puis le stock s'épuise.
    let mut recrues = Vec::new();
    for _ in 0..5 {
        semis::avancer(&mut classes, 1.0, 0.0);
        recrues.push(semis::passage_esperance(&mut classes, Some(40.0)));
    }
    assert_eq!(recrues[0], (40.0, false));
    assert_eq!(recrues[1], (40.0, false));
    assert_eq!(recrues[2], (40.0, false));
    assert!(recrues[3].1 && (recrues[3].0 - 10.0).abs() < 1e-12, "{:?}", recrues[3]);
    assert_eq!(recrues[4], (0.0, true));
}

/// Une année de la dynamique (survie, montée, installation de `nouveaux`, passage de F) depuis
/// `classes` ; rend (recrues, borné).
fn une_annee(classes: &mut [f64], survie: f64, nouveaux: f64, flux: f64) -> (f64, bool) {
    semis::avancer(classes, survie, nouveaux);
    semis::passage_esperance(classes, Some(flux))
}

#[test]
fn le_stock_en_regime_est_stationnaire_a_flux_constant_meme_si_la_survie_est_sous_1() {
    let p = parametres_d_essai();
    for survie in [1.0, 0.9, 0.716, 0.35] {
        for flux in [40.0, 2.5, 1234.5] {
            let mut classes = vec![0.0; p.classes()];
            semis::en_regime_avec_survie(&p, flux, survie, &mut classes);
            let initiales = classes.clone();
            // Avec l'installation du régime (la classe 0 de l'état stationnaire), une année redonne
            // le même état, et le flux entier passe : rien n'est borné.
            for annee in 0..5 {
                let (recrues, borne) = une_annee(&mut classes, survie, initiales[0], flux);
                assert!(!borne, "survie {survie}, flux {flux}, année {annee} : stock limitant");
                assert!((recrues - flux).abs() <= 1e-12 * flux);
                for (a, b) in classes.iter().zip(initiales.iter()) {
                    assert!((a - b).abs() <= 1e-12 * b.abs().max(flux), "survie {survie} : {classes:?} contre {initiales:?}");
                }
            }
            // Sans aucune graine nouvelle, la première année n'est pas bornée non plus.
            let mut sans_graines = initiales.clone();
            let (recrues, borne) = une_annee(&mut sans_graines, survie, 0.0, flux);
            assert!(!borne && (recrues - flux).abs() <= 1e-12 * flux, "survie {survie} : première année bornée");
        }
    }
}

#[test]
fn le_stock_en_regime_suit_la_formule_ecrite_et_se_refuse_a_survie_nulle() {
    let p = parametres_d_essai();
    let (f, s) = (40.0, 0.9);
    let mut classes = vec![0.0; 4];
    semis::en_regime_avec_survie(&p, f, s, &mut classes);
    let w = f * (1.3 / 0.4 - 3.0);
    let e = (f + w) / s - w;
    let attendu = [e / (s * s), e / s, e, w];
    for (a, b) in classes.iter().zip(attendu.iter()) {
        assert!((a - b).abs() < 1e-12 * b, "{classes:?} contre {attendu:?}");
    }
    assert!(semis::total(&classes) > f * 1.3 / 0.4, "à survie < 1, il faut plus que flux × temps de passage");
    // en_regime prend la survie à pleine lumière de l'essence.
    let mut pleine = vec![0.0; 4];
    semis::en_regime(&p, f, &mut pleine);
    assert_eq!(pleine, classes);
    // Survie nulle : aucun état stationnaire, aucun semis initial (le manque sera compté).
    let mut nulle = vec![9.0; 4];
    semis::en_regime_avec_survie(&p, f, 0.0, &mut nulle);
    assert_eq!(nulle, vec![0.0; 4]);
    // Une seule classe : les semis de l'année passent l'année même ; la première année reste couverte.
    let mut court = parametres_d_essai();
    court.hauteur_passage_m = 0.3;
    let mut une = vec![0.0; 1];
    semis::en_regime_avec_survie(&court, f, s, &mut une);
    let (r, borne) = une_annee(&mut une, s, 0.0, f);
    assert!(!borne && (r - f).abs() < 1e-12 * f);
}

#[test]
fn en_mode_cohortes_aucun_couple_n_est_borne_la_premiere_annee() {
    // Zone d'essai, un an : le stock initial stationnaire suffit partout au flux IFN de l'année.
    let dossier = dossier_neuf("cohortes-premiere-annee");
    let bilan = sorties::simuler_et_ecrire(&zone_cohortes(1), &lancement(1), &dossier).unwrap();
    assert_eq!(bilan.comptes.stock_de_semis_limitant, 0);
    let run: serde_json::Value =
        serde_json::from_str(&std::fs::read_to_string(dossier.join("run.json")).unwrap()).unwrap();
    assert_eq!(run["seedling_stock_limited"], 0);
    assert!(bilan.comptes.recrues > 0, "le test ne discriminerait rien sans recrue");
    std::fs::remove_dir_all(&dossier).unwrap();
}

#[test]
fn avancer_fait_survivre_monter_et_entrer_les_nouveaux() {
    let mut classes = vec![10.0, 20.0, 30.0, 5.0];
    semis::avancer(&mut classes, 0.5, 7.0);
    assert_eq!(classes, vec![7.0, 5.0, 10.0, 17.5]);
    let mut une = vec![4.0];
    semis::avancer(&mut une, 0.5, 1.0);
    assert_eq!(une, vec![3.0]);
    let p = parametres_d_essai();
    let h = semis::hauteur_moyenne(&p, &[1.0, 0.0, 0.0, 1.0]).unwrap();
    assert!((h - (0.4 + 1.6) / 2.0).abs() < 1e-12);
    assert_eq!(semis::hauteur_moyenne(&p, &[0.0; 4]), None);
}

#[test]
fn le_passage_massif_borne_par_le_stock_et_vide_le_stock_en_trouee() {
    // 0,0625 ha : 40 semis/ha font 2,5 arbres, donc 2 offerts.
    let mut classes = vec![0.0, 0.0, 0.0, 40.0];
    assert_eq!(semis::passage_massif(&mut classes, 0.0625, Some(3)), (2, true));
    assert!((classes[3] - 8.0).abs() < 1e-12);
    let mut classes = vec![0.0, 0.0, 0.0, 400.0];
    assert_eq!(semis::passage_massif(&mut classes, 0.0625, Some(3)), (3, false));
    assert!((classes[3] - 352.0).abs() < 1e-9);
    let mut classes = vec![9.0, 0.0, 0.0, 100.0];
    assert_eq!(semis::passage_massif(&mut classes, 0.0625, None), (6, false));
    assert!((classes[3] - 4.0).abs() < 1e-9);
    assert_eq!(classes[0], 9.0, "les classes sous la hauteur de passage ne passent pas");
}

#[test]
fn la_survie_suit_la_forme_de_treemig() {
    let p = parametres_d_essai();
    assert_eq!(semis::survie(&p, 0.0), 0.9);
    assert_eq!(semis::survie(&p, 3.0), 0.9, "au seuil, pas de stress");
    assert!((semis::survie(&p, 3.01) - (0.9 - 0.184)).abs() < 1e-15);
    let mut faible = parametres_d_essai();
    faible.survie_pleine_lumiere = 0.1;
    assert_eq!(semis::survie(&faible, 10.0), 0.0, "bornée à 0");
    assert_eq!(semis::ombre(0.5, 4.0), 2.0);
}

#[test]
fn la_mortalite_de_stress_est_lue_du_contrat_et_son_absence_est_refusee() {
    let referentiel = referentiel();
    // Lue : la valeur de la ligne, pas une constante du code.
    let mut lignes = lignes_d_essai();
    for l in lignes.iter_mut() {
        if l.term == "stress_mortality" {
            l.value = 0.3;
        }
    }
    let p = semis::parametres_de(&lignes, "03", &referentiel).unwrap();
    assert_eq!(p.mortalite_stress, 0.3);
    assert!((semis::survie(&p, 10.0) - (0.9 - 0.3)).abs() < 1e-15);
    // Absente : code 2 qui nomme le terme et l'essence, aucune valeur d'emprunt.
    let sans: Vec<LigneRegeneration> = lignes_d_essai().into_iter().filter(|l| l.term != "stress_mortality").collect();
    let erreur = semis::parametres_de(&sans, "03", &referentiel).unwrap_err();
    assert_eq!(erreur.code, CodeSortie::EntreeRefusee);
    assert!(erreur.message.contains("stress_mortality") && erreur.message.contains("03"), "{}", erreur.message);
    // Hors domaine (une mortalité annuelle est entre 0 et 1) : code 2.
    let mut hors = lignes_d_essai();
    for l in hors.iter_mut() {
        if l.term == "stress_mortality" {
            l.value = 1.2;
        }
    }
    let erreur = semis::parametres_de(&hors, "03", &referentiel).unwrap_err();
    assert_eq!(erreur.code, CodeSortie::EntreeRefusee);
    assert!(erreur.message.contains("stress_mortality"), "{}", erreur.message);
}

#[test]
fn un_terme_est_cherche_dans_l_essence_puis_le_groupe_puis_toutes_essences() {
    let referentiel = referentiel();
    let mut lignes = lignes_d_essai();
    lignes.push(ligne_regen(None, Some("feuillu"), "kernel_scale_m", 55.0, "m"));
    lignes.push(ligne_regen(Some("09"), None, "kernel_scale_m", 77.0, "m"));
    assert_eq!(semis::parametres_de(&lignes, "09", &referentiel).unwrap().echelle_noyau_m, 77.0);
    assert_eq!(semis::parametres_de(&lignes, "03", &referentiel).unwrap().echelle_noyau_m, 55.0);
    assert_eq!(semis::parametres_de(&lignes, "61", &referentiel).unwrap().echelle_noyau_m, 30.0);
}

#[test]
fn une_essence_sans_un_terme_donne_le_code_2_qui_nomme_le_terme_et_l_essence() {
    let referentiel = referentiel();
    let mut lignes = lignes_d_essai();
    lignes.retain(|l| l.term != "passage_height_m");
    lignes.push(ligne_regen(Some("09"), None, "passage_height_m", 1.3, "m"));
    assert!(semis::parametres_de(&lignes, "09", &referentiel).is_ok());
    let erreur = semis::parametres_de(&lignes, "03", &referentiel).unwrap_err();
    assert_eq!(erreur.code, CodeSortie::EntreeRefusee);
    assert!(erreur.message.contains("passage_height_m") && erreur.message.contains("03"), "{}", erreur.message);
    assert!(erreur.message.contains("absent"), "{}", erreur.message);
}

#[test]
fn une_unite_differente_du_contrat_ou_une_valeur_hors_domaine_est_refusee() {
    let referentiel = referentiel();
    let mut lignes = lignes_d_essai();
    for l in lignes.iter_mut() {
        if l.term == "maturity_height_m" {
            l.unit = "cm".to_string();
        }
    }
    let erreur = semis::parametres_de(&lignes, "03", &referentiel).unwrap_err();
    assert!(erreur.message.contains("maturity_height_m") && erreur.message.contains("cm"), "{}", erreur.message);
    let mut lignes = lignes_d_essai();
    for l in lignes.iter_mut() {
        if l.term == "establishment_share" {
            l.value = 1.5;
        }
    }
    let erreur = semis::parametres_de(&lignes, "03", &referentiel).unwrap_err();
    assert_eq!(erreur.code, CodeSortie::EntreeRefusee);
    assert!(erreur.message.contains("establishment_share"), "{}", erreur.message);
}

// ------------------------------------------------------------------------------------------
// Le moteur en mode cohorts, sur la zone d'essai

/// La zone d'essai, en mode `cohorts` (K = 2), avec une trouée : les cellules de la colonne 7
/// (bord est), lignes 0 à 4, sans arbre et à H_dom nulle.
fn zone_cohortes(years: u32) -> simulate::entrees::Entrees {
    let mut entrees = zone_d_essai(years);
    let mut garder = Vec::new();
    for rang in 0..entrees.arbres.len() {
        let (_, colonne) = entrees.grille.ligne_colonne(entrees.arbres.cellule[rang]);
        garder.push(colonne != 7);
    }
    let mut arbres = Vec::new();
    for rang in 0..entrees.arbres.len() {
        if garder[rang] {
            arbres.push(simulate::etat::ArbreNouveau {
                tree_id: entrees.arbres.tree_id[rang].clone(),
                espece: entrees.arbres.espece[rang].clone(),
                cellule: entrees.arbres.cellule[rang],
                x: entrees.arbres.x[rang],
                y: entrees.arbres.y[rang],
                d130: entrees.arbres.d130[rang],
                h: entrees.arbres.h[rang],
            });
        }
    }
    entrees.arbres = simulate::etat::EtatArbres::depuis_initiaux(arbres).unwrap();
    for ligne in 0..5 {
        entrees.couches.h0[ligne * 8 + 7] = 0.0;
    }
    entrees.recrutement = ModeRecrutement::Cohortes(ReglagesRegeneration {
        demi_largeur_noyau: 2,
        seuil_zero: 1e-9,
    });
    entrees.regeneration = lignes_d_essai();
    entrees
}

fn empreintes(dossier: &Path) -> BTreeMap<String, String> {
    let mut resultat = BTreeMap::new();
    let mut a_voir = vec![dossier.to_path_buf()];
    while let Some(courant) = a_voir.pop() {
        for entree in std::fs::read_dir(&courant).unwrap() {
            let chemin = entree.unwrap().path();
            if chemin.is_dir() {
                a_voir.push(chemin);
                continue;
            }
            let relatif = chemin.strip_prefix(dossier).unwrap().to_string_lossy().to_string();
            let octets = std::fs::read(&chemin).unwrap();
            let empreinte = if relatif == "run.json" {
                let mut run: serde_json::Value = serde_json::from_slice(&octets).unwrap();
                let objet = run.as_object_mut().unwrap();
                objet.remove("duration_s");
                objet.remove("threads");
                objet.remove("memory_peak_rss_bytes");
                sorties::sha256_hex(serde_json::to_string(&run).unwrap().as_bytes())
            } else {
                sorties::sha256_hex(&octets)
            };
            resultat.insert(relatif, empreinte);
        }
    }
    resultat
}

#[test]
fn en_mode_cohortes_les_sorties_sont_les_memes_de_1_a_7_fils() {
    let entrees = zone_cohortes(8);
    let mut reference: Option<BTreeMap<String, String>> = None;
    for fils in [1, 2, 3, 4, 5, 6, 7] {
        let dossier = dossier_neuf(&format!("cohortes-identite-{fils}"));
        sorties::simuler_et_ecrire(&entrees, &lancement(fils), &dossier).unwrap();
        let actuelles = empreintes(&dossier);
        match &reference {
            None => reference = Some(actuelles),
            Some(attendues) => assert_eq!(&actuelles, attendues, "sorties différentes entre 1 et {fils} fils"),
        }
        std::fs::remove_dir_all(&dossier).unwrap();
    }
}

#[test]
fn en_mode_cohortes_la_trouee_se_recolonise_et_les_semis_sont_ecrits() {
    let dossier = dossier_neuf("cohortes-trouee");
    let bilan = sorties::simuler_et_ecrire(&zone_cohortes(8), &lancement(2), &dossier).unwrap();
    let run: serde_json::Value =
        serde_json::from_str(&std::fs::read_to_string(dossier.join("run.json")).unwrap()).unwrap();
    assert_eq!(run["recruitment"], "cohorts");
    let non_simules: Vec<String> = run["not_simulated"]
        .as_array()
        .unwrap()
        .iter()
        .map(|v| v.as_str().unwrap().to_string())
        .collect();
    assert_eq!(non_simules, vec!["sous_bois", "gibier", "fructification"]);
    assert!(run["gaps_recolonised"].as_u64().unwrap() > 0, "{run}");
    assert_eq!(run["gaps_recolonised"].as_u64().unwrap(), bilan.comptes.trouees_recolonisees);
    assert_eq!(run["buffer_cells"].as_u64().unwrap(), 12 * 10 - 48);
    assert!(run["zeroed_values"].as_u64().is_some());
    // Les recrues de la colonne 7 (la trouée) existent, et la trouée prend la hauteur de passage.
    let mut recrues_en_trouee = 0;
    for annee in T0 + 1..=T0 + 8 {
        let arbres = partition(&dossier, "trees", annee);
        for id in chaines(&arbres, "tree_id") {
            if let Some(reste) = id.strip_prefix('r') {
                let cellule: u64 = reste.split('_').next().unwrap().parse().unwrap();
                if cellule % 8 == 7 && cellule < 40 {
                    recrues_en_trouee += 1;
                }
            }
        }
    }
    assert!(recrues_en_trouee > 0, "aucune recrue dans la trouée en 8 ans");
    // sim/cells : colonnes de semis, semis ≥ 0, hauteur > 0 là où il y a des semis.
    let cellules = partition(&dossier, "cells", T0 + 1);
    let semis_ha = nombres(&cellules, "seedlings_ha");
    let semis_h = nombres(&cellules, "seedling_h_mean");
    let mut avec_semis = 0;
    for (s, h) in semis_ha.iter().zip(semis_h.iter()) {
        let s = s.unwrap();
        assert!(s >= 0.0);
        if s > 0.0 {
            avec_semis += 1;
            assert!(h.unwrap() > 0.0);
        }
    }
    assert!(avec_semis > 0);
    // t0 : semis « en régime » partout où il y a des arbres d'une essence candidate.
    let cellules_t0 = partition(&dossier, "cells", T0);
    assert!(nombres(&cellules_t0, "seedlings_ha").iter().all(|s| s.unwrap() > 0.0));
    let _ = entiers(&cellules_t0, "cell_id");
    // Signalements : plus de « semis non simulés ».
    let flags = lire_parquet(&dossier.join("flags.parquet"));
    assert!(!chaines(&flags, "kind").iter().any(|k| k == "semis_non_simules"));
    std::fs::remove_dir_all(&dossier).unwrap();
}

#[test]
fn en_mode_ifn_direct_rien_ne_change_et_les_semis_sont_dits_non_simules() {
    let dossier = dossier_neuf("ifn-direct-semis");
    sorties::simuler_et_ecrire(&zone_d_essai(2), &lancement(1), &dossier).unwrap();
    let cellules = partition(&dossier, "cells", T0 + 1);
    assert!(cellules.schema().index_of("seedlings_ha").is_err());
    let flags = lire_parquet(&dossier.join("flags.parquet"));
    assert!(chaines(&flags, "kind").iter().any(|k| k == "semis_non_simules"));
    std::fs::remove_dir_all(&dossier).unwrap();
}

#[test]
fn une_trouee_sans_semencier_a_portee_est_signalee_des_t0() {
    // Noyau de 1 cellule : la trouée de la colonne 7 est à portée de la colonne 6 ; on vide aussi
    // la colonne 6 de ses arbres (sans changer sa H_dom), si bien que la colonne 7 n'a plus de
    // semencier à portée.
    let mut entrees = zone_cohortes(2);
    entrees.recrutement = ModeRecrutement::Cohortes(ReglagesRegeneration {
        demi_largeur_noyau: 1,
        seuil_zero: 1e-9,
    });
    let mut arbres = Vec::new();
    for rang in 0..entrees.arbres.len() {
        let (_, colonne) = entrees.grille.ligne_colonne(entrees.arbres.cellule[rang]);
        if colonne != 6 {
            arbres.push(simulate::etat::ArbreNouveau {
                tree_id: entrees.arbres.tree_id[rang].clone(),
                espece: entrees.arbres.espece[rang].clone(),
                cellule: entrees.arbres.cellule[rang],
                x: entrees.arbres.x[rang],
                y: entrees.arbres.y[rang],
                d130: entrees.arbres.d130[rang],
                h: entrees.arbres.h[rang],
            });
        }
    }
    entrees.arbres = simulate::etat::EtatArbres::depuis_initiaux(arbres).unwrap();
    let dossier = dossier_neuf("cohortes-hors-portee");
    sorties::simuler_et_ecrire(&entrees, &lancement(1), &dossier).unwrap();
    let flags = lire_parquet(&dossier.join("flags.parquet"));
    let sortes = chaines(&flags, "kind");
    let entites = chaines(&flags, "entity");
    let annees = entiers(&flags, "year");
    let mut a_t0 = Vec::new();
    for rang in 0..sortes.len() {
        if sortes[rang] == "trouee_hors_de_portee" && annees[rang] == T0 as i64 {
            a_t0.push(entites[rang].parse::<u64>().unwrap());
        }
    }
    a_t0.sort();
    assert_eq!(a_t0, vec![7, 15, 23, 31, 39]);
    std::fs::remove_dir_all(&dossier).unwrap();
}

#[test]
fn une_essence_candidate_sans_parametre_de_semis_arrete_avant_toute_ecriture() {
    let mut entrees = zone_cohortes(2);
    entrees.regeneration.retain(|l| l.term != "fecundity_seeds_per_m2_ba_yr");
    let dossier = dossier_neuf("cohortes-sans-terme");
    let erreur = sorties::simuler_et_ecrire(&entrees, &lancement(1), &dossier).unwrap_err();
    assert_eq!(erreur.code, CodeSortie::EntreeRefusee);
    assert!(erreur.message.contains("fecundity_seeds_per_m2_ba_yr"), "{}", erreur.message);
    assert!(!dossier.exists());
}

#[test]
fn la_config_sans_recruitment_est_refusee_et_cohorts_exige_son_bloc() {
    let base = "schema_version: 1\nzone: z\ncrs: EPSG:2154\ngrid:\n  resolution_m: 25\nmanagement: none\n";
    let sans = simulate::config::depuis_texte(&format!(
        "{base}simulate:\n  level: massif\n  seed: 1\n  t0: 2022\n  years: 1\n"
    ))
    .unwrap();
    let erreur = sans.recrutement().unwrap_err();
    assert_eq!(erreur.code, CodeSortie::EntreeRefusee);
    assert!(erreur.message.contains("recruitment") && erreur.message.contains("absent"));
    let inconnu = simulate::config::depuis_texte(&format!(
        "{base}simulate:\n  level: massif\n  seed: 1\n  t0: 2022\n  years: 1\n  recruitment: magie\n"
    ))
    .unwrap();
    assert!(inconnu.recrutement().unwrap_err().message.contains("magie"));
    let sans_bloc = simulate::config::depuis_texte(&format!(
        "{base}simulate:\n  level: massif\n  seed: 1\n  t0: 2022\n  years: 1\n  recruitment: cohorts\n"
    ))
    .unwrap();
    assert!(sans_bloc.recrutement().unwrap_err().message.contains("regeneration"));
    let complet = simulate::config::depuis_texte(&format!(
        "{base}simulate:\n  level: massif\n  seed: 1\n  t0: 2022\n  years: 1\n  recruitment: cohorts\n  regeneration:\n    kernel_truncation_cells: 3\n    zero_threshold: 1.0e-9\n"
    ))
    .unwrap();
    assert_eq!(
        complet.recrutement().unwrap(),
        ModeRecrutement::Cohortes(ReglagesRegeneration {
            demi_largeur_noyau: 3,
            seuil_zero: 1e-9
        })
    );
    let direct = simulate::config::depuis_texte(&format!(
        "{base}simulate:\n  level: massif\n  seed: 1\n  t0: 2022\n  years: 1\n  recruitment: ifn_direct\n"
    ))
    .unwrap();
    assert_eq!(direct.recrutement().unwrap(), ModeRecrutement::IfnDirect);
}
