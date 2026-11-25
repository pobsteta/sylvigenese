//! Tests de la relecture des paramètres (mission 035 ; src/parametres.rs, ADR 0004).
//!
//! Les valeurs de référence viennent de R : `simulate/tests/fixtures/make_parametres_r.R` les
//! produit avec `dyn_ncs` et `dyn_eta` de `R/dynamics.R` et l'écrivain `dyn_write_params`
//! (fichiers versionnés sous `tests/fixtures/parametres/`). Accord exigé : 1e-10.

use std::collections::BTreeMap;
use std::path::PathBuf;

use simulate::erreurs::CodeSortie;
use simulate::parametres::{
    derivees_secondes, lire_parquet, Covariables, LigneParametre, Niveau, Parametres, Porteur,
    Referentiel, SortiesDeDomaine, SplineNaturelle, Variable, TOUTES_ESSENCES,
};

const TOLERANCE: f64 = 1e-10;

fn fixtures() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/parametres")
}

fn referentiel() -> Referentiel {
    let chemin = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../contracts/species.csv");
    Referentiel::lire(&chemin).unwrap()
}

/// Lit un CSV simple (sans guillemets) : en-tête puis lignes.
fn lire_csv(nom: &str) -> Vec<BTreeMap<String, String>> {
    let texte = std::fs::read_to_string(fixtures().join(nom)).unwrap();
    let mut lignes = texte.lines();
    let entete: Vec<String> = lignes
        .next()
        .unwrap()
        .split(',')
        .map(|s| s.to_string())
        .collect();
    let mut sortie = Vec::new();
    for ligne in lignes {
        let champs: Vec<&str> = ligne.split(',').collect();
        assert_eq!(champs.len(), entete.len(), "{nom} : {ligne}");
        let mut enregistrement = BTreeMap::new();
        for (cle, valeur) in entete.iter().zip(champs) {
            enregistrement.insert(cle.clone(), valeur.to_string());
        }
        sortie.push(enregistrement);
    }
    sortie
}

fn reel(enregistrement: &BTreeMap<String, String>, cle: &str) -> f64 {
    enregistrement[cle].parse::<f64>().unwrap()
}

fn proche(obtenu: f64, attendu: f64) -> bool {
    (obtenu - attendu).abs() <= TOLERANCE * attendu.abs().max(1.0)
}

// ------------------------------------------------------------------ spline contre R

#[test]
fn la_spline_redonne_dyn_ncs_de_r_a_1e_10() {
    let mut noeuds: BTreeMap<String, Vec<(f64, f64)>> = BTreeMap::new();
    for ligne in lire_csv("splines_noeuds.csv") {
        noeuds
            .entry(ligne["cas"].clone())
            .or_default()
            .push((reel(&ligne, "x"), reel(&ligne, "y")));
    }
    assert_eq!(noeuds.len(), 5);
    let mut splines: BTreeMap<String, SplineNaturelle> = BTreeMap::new();
    for (cas, couples) in &noeuds {
        // Les nœuds sont donnés à l'envers pour vérifier le tri.
        let mut a_l_envers = couples.clone();
        a_l_envers.reverse();
        splines.insert(
            cas.clone(),
            SplineNaturelle::construire(Variable::D130, &a_l_envers).unwrap(),
        );
    }
    let valeurs = lire_csv("splines_valeurs.csv");
    assert!(
        valeurs.len() >= 150,
        "{} valeurs de R seulement",
        valeurs.len()
    );
    let mut ecart_max: f64 = 0.0;
    for ligne in &valeurs {
        let spline = &splines[&ligne["cas"]];
        let x = reel(ligne, "x");
        let attendu = reel(ligne, "valeur");
        let (obtenu, _) = spline.evaluer(x).unwrap();
        ecart_max = ecart_max.max((obtenu - attendu).abs() / attendu.abs().max(1.0));
        assert!(
            proche(obtenu, attendu),
            "cas {} en x = {x} : Rust {obtenu}, R {attendu}",
            ligne["cas"]
        );
    }
    // Trace du plus grand écart relatif mesuré (lisible avec --nocapture).
    println!(
        "écart relatif max avec R : {ecart_max:e} sur {} valeurs",
        valeurs.len()
    );
}

#[test]
fn la_spline_passe_par_ses_noeuds_et_borne_hors_domaine() {
    let noeuds = [
        (7.5, -0.41),
        (12.0, -0.12),
        (23.7, 0.05),
        (41.0, 0.11),
        (88.3, -0.3),
    ];
    let spline = SplineNaturelle::construire(Variable::D130, &noeuds).unwrap();
    for (x, y) in noeuds {
        let (valeur, borne) = spline.evaluer(x).unwrap();
        assert!(
            (valeur - y).abs() < 1e-12,
            "en x = {x} : {valeur} au lieu de {y}"
        );
        assert!(!borne, "un nœud extrême est dans le domaine");
    }
    let (sous, borne_sous) = spline.evaluer(1.0).unwrap();
    let (sur, borne_sur) = spline.evaluer(500.0).unwrap();
    assert!(borne_sous && borne_sur);
    assert_eq!(sous, spline.evaluer(7.5).unwrap().0);
    assert_eq!(sur, spline.evaluer(88.3).unwrap().0);
}

#[test]
fn les_derivees_secondes_sont_nulles_aux_bouts_et_exactes_sur_une_parabole_par_morceaux() {
    // Trois nœuds : un seul inconnu, M_2 = 6 [(y3 − y2)/h2 − (y2 − y1)/h1] / (2 (h1 + h2)).
    let m = derivees_secondes(&[0.0, 1.0, 3.0], &[0.0, 1.0, 0.0]);
    assert_eq!(m[0], 0.0);
    assert_eq!(m[2], 0.0);
    let attendu = 6.0 * ((0.0 - 1.0) / 2.0 - (1.0 - 0.0) / 1.0) / (2.0 * 3.0);
    assert!((m[1] - attendu).abs() < 1e-15);
    // Données linéaires : toutes les dérivées secondes sont nulles.
    let lineaire = derivees_secondes(&[0.0, 2.0, 3.0, 7.0, 8.0], &[1.0, 5.0, 7.0, 15.0, 17.0]);
    for valeur in lineaire {
        assert!(valeur.abs() < 1e-13);
    }
}

#[test]
fn une_spline_mal_formee_est_refusee() {
    let un_noeud = SplineNaturelle::construire(Variable::D130, &[(1.0, 2.0)]).unwrap_err();
    assert_eq!(un_noeud.code, CodeSortie::EntreeRefusee);
    let double =
        SplineNaturelle::construire(Variable::D130, &[(1.0, 2.0), (1.0, 3.0)]).unwrap_err();
    assert_eq!(double.code, CodeSortie::EntreeRefusee);
    let non_fini =
        SplineNaturelle::construire(Variable::D130, &[(1.0, 2.0), (f64::NAN, 3.0)]).unwrap_err();
    assert_eq!(non_fini.code, CodeSortie::EntreeRefusee);
}

#[test]
fn evaluer_un_nan_est_un_controle_echoue_code_3() {
    let spline = SplineNaturelle::construire(Variable::Trophic, &[(0.0, 0.0), (1.0, 1.0)]).unwrap();
    for x in [f64::NAN, f64::INFINITY, f64::NEG_INFINITY] {
        let erreur = spline.evaluer(x).unwrap_err();
        assert_eq!(erreur.code_sortie(), 3);
        assert!(erreur.message.contains("trophic"));
    }
}

// ------------------------------------------------------------------ lecture du Parquet de R

fn parametres_essai() -> Parametres {
    let lignes = lire_parquet(&fixtures().join("params_essai.parquet")).unwrap();
    Parametres::depuis_lignes(&lignes).unwrap()
}

#[test]
fn le_parquet_ecrit_par_r_se_relit_ligne_a_ligne() {
    let lignes = lire_parquet(&fixtures().join("params_essai.parquet")).unwrap();
    assert_eq!(lignes.len(), 32);
    let intercept = lignes
        .iter()
        .find(|l| {
            l.species.as_deref() == Some("09") && l.model == "growth_gam" && l.term == "intercept"
        })
        .unwrap();
    assert_eq!(intercept.value, -1.234);
    assert_eq!(intercept.variable, None);
    assert_eq!(intercept.x, None);
    assert_eq!(intercept.species_group, None);
    assert!(intercept.provisoire);
    assert_eq!(
        intercept.source,
        "jeu d'essai de la mission 035 (valeurs fictives, sans sens écologique)"
    );
    let noeud = lignes
        .iter()
        .find(|l| l.term == "s(d130)[03]" && l.species.as_deref() == Some("09"))
        .unwrap();
    assert_eq!(noeud.variable.as_deref(), Some("d130"));
    assert_eq!(noeud.x, Some(35.0));
    assert_eq!(noeud.value, 0.12);
}

#[test]
fn les_jeux_sont_assembles_en_structures_concretes() {
    let parametres = parametres_essai();
    assert_eq!(parametres.jeux.len(), 5);
    let g09 = parametres
        .jeu(&Porteur::Essence("09".to_string()), "growth_gam")
        .unwrap();
    assert_eq!(g09.intercept, Some(-1.234));
    let variables: Vec<Variable> = g09.splines.iter().map(|s| s.variable).collect();
    assert_eq!(
        variables,
        vec![Variable::D130, Variable::BaPlot, Variable::Trophic]
    );
    assert_eq!(g09.splines[0].x, vec![7.5, 20.0, 35.0, 55.0, 90.0]);
    assert_eq!(
        g09.effets_ser,
        vec![("A11".to_string(), 0.05), ("B21".to_string(), -0.07)]
    );
    assert_eq!(g09.scalaire("scale").unwrap(), 0.31);
    assert_eq!(g09.scalaire("tweedie_p").unwrap(), 1.42);
    assert!(g09.provisoire);
    assert_eq!(g09.sources.len(), 1);
    let absent = g09.scalaire("k").unwrap_err();
    assert_eq!(absent.code_sortie(), 2);

    let cr = parametres
        .jeu(&Porteur::Essence("61".to_string()), "chapman_richards")
        .unwrap();
    assert_eq!(cr.intercept, None);
    assert!(cr.splines.is_empty());
    assert_eq!(cr.scalaire("A_class3").unwrap(), 24.0);
    assert_eq!(cr.scalaire("k").unwrap(), 0.021);
    assert_eq!(cr.scalaire("p").unwrap(), 1.3);
}

#[test]
fn le_predicteur_redonne_dyn_eta_de_r_a_1e_10_et_compte_les_sorties() {
    let parametres = parametres_essai();
    let g09 = parametres
        .jeu(&Porteur::Essence("09".to_string()), "growth_gam")
        .unwrap();
    let mut sorties = SortiesDeDomaine::default();
    let lignes = lire_csv("eta_valeurs.csv");
    assert_eq!(lignes.len(), 20);
    for ligne in &lignes {
        let covariables = Covariables {
            d130: Some(reel(ligne, "d130")),
            ba_plot: Some(reel(ligne, "ba_plot")),
            trophic: Some(reel(ligne, "trophic")),
            ..Covariables::default()
        };
        let obtenu = g09
            .predicteur(&covariables, &ligne["ser_code"], &mut sorties)
            .unwrap();
        let attendu = reel(ligne, "eta");
        assert!(
            proche(obtenu, attendu),
            "ligne {} : Rust {obtenu}, R {attendu}",
            ligne["ligne"]
        );
    }
    let sans_effet_r: u64 = std::fs::read_to_string(fixtures().join("eta_ser_sans_effet.txt"))
        .unwrap()
        .trim()
        .parse()
        .unwrap();
    assert_eq!(sorties.ser_sans_effet, sans_effet_r);
    // Lignes 1 et 2 : aux nœuds extrêmes (dans le domaine) ; lignes 3 et 4 : d130 = 3 et 150,
    // ba_plot = −1 et 70, trophic = 1 et 7, toutes hors nœuds ; les suivantes sont tirées par R
    // sur une plage un peu plus large que les nœuds (voir make_parametres_r.R).
    assert_eq!(
        sorties.pour(Variable::D130),
        2 + compte_hors(&lignes, "d130", 7.5, 90.0)
    );
    assert_eq!(
        sorties.pour(Variable::BaPlot),
        2 + compte_hors(&lignes, "ba_plot", 0.0, 50.0)
    );
    assert_eq!(
        sorties.pour(Variable::Trophic),
        2 + compte_hors(&lignes, "trophic", 2.1, 5.9)
    );
    assert!(
        sorties.total_borne() > 6,
        "le jeu d'essai devrait borner aussi des valeurs tirées"
    );
    assert_eq!(sorties.pour(Variable::Bal), 0);
    assert_eq!(
        sorties.total_borne(),
        sorties.pour(Variable::D130)
            + sorties.pour(Variable::BaPlot)
            + sorties.pour(Variable::Trophic)
    );
}

/// Lignes 5 et suivantes dont la variable sort de [bas, haut] (tirées au hasard par R).
fn compte_hors(lignes: &[BTreeMap<String, String>], cle: &str, bas: f64, haut: f64) -> u64 {
    lignes[4..]
        .iter()
        .filter(|l| {
            let v = reel(l, cle);
            v < bas || v > haut
        })
        .count() as u64
}

#[test]
fn une_covariable_manquante_est_refusee_code_2_et_un_nan_code_3() {
    let parametres = parametres_essai();
    let g09 = parametres
        .jeu(&Porteur::Essence("09".to_string()), "growth_gam")
        .unwrap();
    let mut sorties = SortiesDeDomaine::default();
    let incomplete = Covariables {
        d130: Some(20.0),
        trophic: Some(3.0),
        ..Covariables::default()
    };
    let erreur = g09
        .predicteur(&incomplete, "A11", &mut sorties)
        .unwrap_err();
    assert_eq!(erreur.code_sortie(), 2);
    assert!(erreur.message.contains("ba_plot"), "{}", erreur.message);
    let nan = Covariables {
        d130: Some(f64::NAN),
        ba_plot: Some(1.0),
        trophic: Some(3.0),
        ..Covariables::default()
    };
    assert_eq!(
        g09.predicteur(&nan, "A11", &mut sorties)
            .unwrap_err()
            .code_sortie(),
        3
    );
    let cr = parametres
        .jeu(&Porteur::Essence("61".to_string()), "chapman_richards")
        .unwrap();
    assert_eq!(
        cr.predicteur(&incomplete, "A11", &mut sorties)
            .unwrap_err()
            .code_sortie(),
        2
    );
}

#[test]
fn les_comptes_de_plusieurs_fils_s_additionnent() {
    let mut a = SortiesDeDomaine::default();
    a.par_variable[Variable::D130.rang()] = 3;
    a.ser_sans_effet = 1;
    let mut b = SortiesDeDomaine::default();
    b.par_variable[Variable::D130.rang()] = 2;
    b.par_variable[Variable::RelD.rang()] = 5;
    a.ajouter(&b);
    assert_eq!(a.pour(Variable::D130), 5);
    assert_eq!(a.pour(Variable::RelD), 5);
    assert_eq!(a.ser_sans_effet, 1);
    assert_eq!(a.total_borne(), 10);
}

#[test]
fn l_ordre_des_lignes_ne_change_pas_le_predicteur_au_bit_pres() {
    let mut lignes = lire_parquet(&fixtures().join("params_essai.parquet")).unwrap();
    let droit = Parametres::depuis_lignes(&lignes).unwrap();
    lignes.reverse();
    let renverse = Parametres::depuis_lignes(&lignes).unwrap();
    let covariables = Covariables {
        d130: Some(33.3),
        ba_plot: Some(18.0),
        trophic: Some(4.4),
        ..Covariables::default()
    };
    let mut s = SortiesDeDomaine::default();
    let porteur = Porteur::Essence("09".to_string());
    let a = droit
        .jeu(&porteur, "growth_gam")
        .unwrap()
        .predicteur(&covariables, "B21", &mut s)
        .unwrap();
    let b = renverse
        .jeu(&porteur, "growth_gam")
        .unwrap()
        .predicteur(&covariables, "B21", &mut s)
        .unwrap();
    assert_eq!(a.to_bits(), b.to_bits());
}

// ------------------------------------------------------------------ recherche essence → groupe → toutes_essences

#[test]
fn la_recherche_prend_l_essence_puis_le_groupe_puis_toutes_essences() {
    let parametres = parametres_essai();
    let referentiel = referentiel();
    assert_eq!(referentiel.nombre(), 195);
    assert_eq!(referentiel.groupe("09"), Some("feuillu"));
    assert_eq!(referentiel.groupe("61"), Some("resineux"));

    // 09 (Fagus sylvatica) a ses lignes propres.
    let (jeu, niveau) = parametres
        .chercher("growth_gam", "09", &referentiel)
        .unwrap();
    assert_eq!(niveau, Niveau::Essence);
    assert_eq!(jeu.porteur, Porteur::Essence("09".to_string()));
    // 02 (Quercus robur) n'en a pas : groupe feuillu.
    let (jeu, niveau) = parametres
        .chercher("growth_gam", "02", &referentiel)
        .unwrap();
    assert_eq!(niveau, Niveau::Groupe);
    assert_eq!(jeu.porteur, Porteur::Groupe("feuillu".to_string()));
    // 61 (Abies alba), résineux : pas de groupe resineux dans l'essai, donc toutes_essences.
    let (jeu, niveau) = parametres
        .chercher("growth_gam", "61", &referentiel)
        .unwrap();
    assert_eq!(niveau, Niveau::ToutesEssences);
    assert_eq!(jeu.porteur, Porteur::Groupe(TOUTES_ESSENCES.to_string()));
    // Un modèle porté seulement par toutes_essences sert aussi à 09.
    let (_, niveau) = parametres
        .chercher("mortality_gam", "09", &referentiel)
        .unwrap();
    assert_eq!(niveau, Niveau::ToutesEssences);
    // Les lignes propres de 61 pour un autre modèle.
    let (_, niveau) = parametres
        .chercher("chapman_richards", "61", &referentiel)
        .unwrap();
    assert_eq!(niveau, Niveau::Essence);
}

#[test]
fn sans_aucun_niveau_la_recherche_rend_le_code_2() {
    let parametres = parametres_essai();
    let referentiel = referentiel();
    let erreur = parametres
        .chercher("recruitment_gam", "09", &referentiel)
        .unwrap_err();
    assert_eq!(erreur.code, CodeSortie::EntreeRefusee);
    assert!(
        erreur.message.contains("recruitment_gam") && erreur.message.contains("09"),
        "{}",
        erreur.message
    );
    // chapman_richards : 61 seul ; 52 (Pinus sylvestris) n'a ni ligne propre, ni groupe, ni toutes_essences.
    assert_eq!(
        parametres
            .chercher("chapman_richards", "52", &referentiel)
            .unwrap_err()
            .code_sortie(),
        2
    );
}

#[test]
fn une_essence_absente_du_referentiel_est_refusee_meme_si_toutes_essences_existe() {
    let parametres = parametres_essai();
    let erreur = parametres
        .chercher("growth_gam", "99Z", &referentiel())
        .unwrap_err();
    assert_eq!(erreur.code_sortie(), 2);
    assert!(erreur.message.contains("species.csv"));
}

// ------------------------------------------------------------------ lignes hors contrat

fn ligne(
    species: Option<&str>,
    groupe: Option<&str>,
    term: &str,
    variable: Option<&str>,
    x: Option<f64>,
) -> LigneParametre {
    LigneParametre {
        species: species.map(|s| s.to_string()),
        species_group: groupe.map(|s| s.to_string()),
        model: "growth_gam".to_string(),
        term: term.to_string(),
        variable: variable.map(|s| s.to_string()),
        x,
        value: 0.5,
        provisoire: true,
        source: "essai".to_string(),
    }
}

#[test]
fn les_lignes_hors_contrat_sont_refusees_code_2() {
    let cas: Vec<(&str, Vec<LigneParametre>)> = vec![
        (
            "ni essence ni groupe",
            vec![ligne(None, None, "intercept", None, None)],
        ),
        (
            "groupe inconnu",
            vec![ligne(None, Some("arbustes"), "intercept", None, None)],
        ),
        (
            "espar hors motif",
            vec![ligne(Some("9"), None, "intercept", None, None)],
        ),
        (
            "terme en double",
            vec![
                ligne(Some("09"), None, "intercept", None, None),
                ligne(Some("09"), None, "intercept", None, None),
            ],
        ),
        (
            "intercept avec abscisse",
            vec![ligne(Some("09"), None, "intercept", None, Some(1.0))],
        ),
        (
            "terme lisse mal formé",
            vec![ligne(Some("09"), None, "s(d130", Some("d130"), Some(1.0))],
        ),
        (
            "variable inconnue",
            vec![ligne(
                Some("09"),
                None,
                "s(age)[01]",
                Some("age"),
                Some(1.0),
            )],
        ),
        (
            "variable discordante",
            vec![ligne(
                Some("09"),
                None,
                "s(d130)[01]",
                Some("bal"),
                Some(1.0),
            )],
        ),
        (
            "nœud sans abscisse",
            vec![ligne(Some("09"), None, "s(d130)[01]", Some("d130"), None)],
        ),
        (
            "un seul nœud",
            vec![ligne(
                Some("09"),
                None,
                "s(d130)[01]",
                Some("d130"),
                Some(1.0),
            )],
        ),
        (
            "SER sans variable",
            vec![ligne(Some("09"), None, "ser_code=A11", None, None)],
        ),
        (
            "SER vide",
            vec![ligne(Some("09"), None, "ser_code=", Some("ser_code"), None)],
        ),
        (
            "scalaire avec variable",
            vec![ligne(Some("09"), None, "scale", Some("d130"), None)],
        ),
    ];
    for (nom, lignes) in cas {
        let erreur = Parametres::depuis_lignes(&lignes).unwrap_err();
        assert_eq!(erreur.code, CodeSortie::EntreeRefusee, "cas « {nom} »");
    }
    let mut non_fini = ligne(Some("09"), None, "intercept", None, None);
    non_fini.value = f64::NAN;
    assert_eq!(
        Parametres::depuis_lignes(&[non_fini])
            .unwrap_err()
            .code_sortie(),
        2
    );
}

#[test]
fn un_fichier_absent_ou_hors_contrat_est_refuse_code_2() {
    let absent = lire_parquet(&fixtures().join("absent.parquet")).unwrap_err();
    assert_eq!(absent.code_sortie(), 2);
    let pas_parquet = lire_parquet(&fixtures().join("splines_noeuds.csv")).unwrap_err();
    assert_eq!(pas_parquet.code_sortie(), 2);
}

#[test]
fn un_parquet_sans_colonne_ou_mal_type_est_refuse_code_2() {
    use arrow_array::{ArrayRef, BooleanArray, Float64Array, Int64Array, RecordBatch, StringArray};
    use parquet::arrow::ArrowWriter;
    use std::sync::Arc;

    let dossier =
        std::env::temp_dir().join(format!("simulate-test-{}-parametres", std::process::id()));
    std::fs::create_dir_all(&dossier).unwrap();
    let texte = |v: &str| -> ArrayRef { Arc::new(StringArray::from(vec![Some(v)])) };
    let vide = || -> ArrayRef { Arc::new(StringArray::from(vec![None::<&str>])) };
    let colonnes = |valeur: ArrayRef, avec_source: bool| -> Vec<(&'static str, ArrayRef)> {
        let mut c: Vec<(&'static str, ArrayRef)> = vec![
            ("species", texte("09")),
            ("species_group", vide()),
            ("model", texte("growth_gam")),
            ("term", texte("intercept")),
            ("variable", vide()),
            ("x", Arc::new(Float64Array::from(vec![None::<f64>]))),
            ("value", valeur),
            ("provisoire", Arc::new(BooleanArray::from(vec![true]))),
        ];
        if avec_source {
            c.push(("source", texte("essai")));
        }
        c
    };
    let ecrire = |nom: &str, c: Vec<(&'static str, ArrayRef)>| -> PathBuf {
        let chemin = dossier.join(nom);
        let lot = RecordBatch::try_from_iter(c).unwrap();
        let fichier = std::fs::File::create(&chemin).unwrap();
        let mut ecrivain = ArrowWriter::try_new(fichier, lot.schema(), None).unwrap();
        ecrivain.write(&lot).unwrap();
        ecrivain.close().unwrap();
        chemin
    };
    let bon = ecrire(
        "bon.parquet",
        colonnes(Arc::new(Float64Array::from(vec![-1.0])), true),
    );
    assert_eq!(lire_parquet(&bon).unwrap().len(), 1);
    let sans_source = ecrire(
        "sans_source.parquet",
        colonnes(Arc::new(Float64Array::from(vec![-1.0])), false),
    );
    let erreur = lire_parquet(&sans_source).unwrap_err();
    assert_eq!(erreur.code_sortie(), 2);
    assert!(erreur.message.contains("source"), "{}", erreur.message);
    let entier = ecrire(
        "entier.parquet",
        colonnes(Arc::new(Int64Array::from(vec![1])), true),
    );
    let erreur = lire_parquet(&entier).unwrap_err();
    assert_eq!(erreur.code_sortie(), 2);
    assert!(erreur.message.contains("value"), "{}", erreur.message);
    let mut c = colonnes(Arc::new(Float64Array::from(vec![-1.0])), true);
    c.push(("en_trop", texte("?")));
    let en_trop = ecrire("en_trop.parquet", c);
    assert_eq!(lire_parquet(&en_trop).unwrap_err().code_sortie(), 2);
    let mut c = colonnes(Arc::new(Float64Array::from(vec![None::<f64>])), true);
    c.retain(|(nom, _)| *nom != "value");
    c.push(("value", Arc::new(Float64Array::from(vec![None::<f64>]))));
    let valeur_vide = ecrire("valeur_vide.parquet", c);
    assert_eq!(lire_parquet(&valeur_vide).unwrap_err().code_sortie(), 2);
    std::fs::remove_dir_all(&dossier).unwrap();
}
