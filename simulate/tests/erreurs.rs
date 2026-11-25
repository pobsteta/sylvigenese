//! Tests des erreurs et des codes de sortie (mission 035 ; src/erreurs.rs).

use simulate::erreurs::{CodeSortie, Erreur};
use simulate::geotiff::ErreurGeotiff;

#[test]
fn les_codes_valent_un_a_quatre() {
    assert_eq!(Erreur::interne("x".to_string()).code_sortie(), 1);
    assert_eq!(Erreur::entree_refusee("x".to_string()).code_sortie(), 2);
    assert_eq!(Erreur::controle_echoue("x".to_string()).code_sortie(), 3);
    assert_eq!(
        Erreur::memoire_insuffisante("x".to_string()).code_sortie(),
        4
    );
}

#[test]
fn le_succes_reste_le_code_0_du_squelette() {
    assert_eq!(simulate::SORTIE_OK, 0);
    assert_eq!(
        simulate::SORTIE_IMPOSSIBLE,
        CodeSortie::EntreeRefusee.valeur()
    );
}

#[test]
fn le_message_est_en_francais_avec_son_code() {
    let erreur = Erreur::entree_refusee("aucun paramètre growth_gam pour l'essence 09".to_string());
    assert_eq!(
        erreur.to_string(),
        "entrée refusée (code 2) : aucun paramètre growth_gam pour l'essence 09"
    );
    assert_eq!(
        Erreur::controle_echoue("d130 ≤ 0".to_string()).to_string(),
        "contrôle échoué (code 3) : d130 ≤ 0"
    );
    assert_eq!(
        Erreur::memoire_insuffisante("trop".to_string()).to_string(),
        "mémoire insuffisante (code 4) : trop"
    );
    assert_eq!(
        Erreur::interne("invariant".to_string()).to_string(),
        "erreur interne (code 1) : invariant"
    );
}

#[test]
fn une_erreur_geotiff_garde_son_code() {
    let refus = ErreurGeotiff {
        code: 2,
        message: "hors profil".to_string(),
    };
    let memoire = ErreurGeotiff {
        code: 4,
        message: "trop gros".to_string(),
    };
    let etrange = ErreurGeotiff {
        code: 9,
        message: "?".to_string(),
    };
    assert_eq!(Erreur::from(refus).code, CodeSortie::EntreeRefusee);
    assert_eq!(Erreur::from(memoire).code, CodeSortie::MemoireInsuffisante);
    let interne = Erreur::from(etrange);
    assert_eq!(interne.code, CodeSortie::ErreurInterne);
    assert!(interne.message.contains("code 9"));
}
