//! Tests de l'état des arbres en colonnes (mission 035 ; src/etat.rs).
//!
//! Coordonnées : x = est, y = nord, en m, EPSG:2154.

use simulate::alea::packer_essence;
use simulate::erreurs::CodeSortie;
use simulate::etat::{premiers_numeros, ArbreNouveau, EtatArbres};

fn arbre(tree_id: &str, espece: &str, x: f64, y: f64) -> ArbreNouveau {
    ArbreNouveau {
        tree_id: tree_id.to_string(),
        espece: espece.to_string(),
        cellule: 0,
        x,
        y,
        d130: 30.0,
        h: 22.5,
    }
}

#[test]
fn les_initiaux_sont_tries_par_tree_id_et_numerotes_de_zero() {
    let etat = EtatArbres::depuis_initiaux(vec![
        arbre("t3", "61", 700_037.5, 6_500_962.5),
        arbre("t10", "09", 700_012.5, 6_500_987.5),
        arbre("t2", "02", 700_062.5, 6_500_912.5),
    ])
    .unwrap();
    // Ordre des octets : « t10 » < « t2 » < « t3 ».
    assert_eq!(etat.tree_id, vec!["t10", "t2", "t3"]);
    assert_eq!(etat.numero, vec![0, 1, 2]);
    assert_eq!(etat.espece, vec!["09", "02", "61"]);
    assert_eq!(etat.espece_packee, vec![0x3039, 0x3032, 0x3631]);
    // Les colonnes suivent leur arbre : t10 est en (est 700 012,5 ; nord 6 500 987,5).
    assert_eq!((etat.x[0], etat.y[0]), (700_012.5, 6_500_987.5));
    assert_eq!(etat.vivant, vec![true, true, true]);
    assert_eq!(etat.prochain_numero(), 3);
    etat.verifier().unwrap();
}

#[test]
fn le_numero_ne_depend_pas_de_l_ordre_de_lecture() {
    let a = vec![
        arbre("b", "09", 1.0, 1.0),
        arbre("a", "09", 2.0, 2.0),
        arbre("c", "09", 3.0, 3.0),
    ];
    let mut b = a.clone();
    b.reverse();
    let ea = EtatArbres::depuis_initiaux(a).unwrap();
    let eb = EtatArbres::depuis_initiaux(b).unwrap();
    assert_eq!(ea, eb);
}

#[test]
fn un_tree_id_en_double_ou_vide_est_refuse_code_2() {
    let double = EtatArbres::depuis_initiaux(vec![
        arbre("t1", "09", 0.0, 0.0),
        arbre("t1", "61", 1.0, 1.0),
    ])
    .unwrap_err();
    assert_eq!(double.code, CodeSortie::EntreeRefusee);
    assert!(double.message.contains("t1"));
    let vide = EtatArbres::depuis_initiaux(vec![arbre("", "09", 0.0, 0.0)]).unwrap_err();
    assert_eq!(vide.code_sortie(), 2);
    let essence = EtatArbres::depuis_initiaux(vec![arbre("t1", "hetre", 0.0, 0.0)]).unwrap_err();
    assert_eq!(essence.code_sortie(), 2);
}

#[test]
fn les_recrues_sont_numerotees_par_somme_de_prefixes() {
    let (premiers, prochain) = premiers_numeros(100, &[2, 0, 3, 1]).unwrap();
    assert_eq!(premiers, vec![100, 102, 102, 105]);
    assert_eq!(prochain, 106);
    let (vide, meme) = premiers_numeros(7, &[]).unwrap();
    assert!(vide.is_empty());
    assert_eq!(meme, 7);
    assert_eq!(
        premiers_numeros(u64::MAX - 1, &[1, 1])
            .unwrap_err()
            .code_sortie(),
        1
    );
}

#[test]
fn les_recrues_s_ajoutent_dans_l_ordre_et_un_numero_hors_ordre_est_le_code_1() {
    let mut etat = EtatArbres::depuis_initiaux(vec![arbre("t1", "09", 0.0, 0.0)]).unwrap();
    let (premiers, prochain) = premiers_numeros(etat.prochain_numero(), &[2, 1]).unwrap();
    etat.ajouter(premiers[0], arbre("r7_2022_0", "09", 1.0, 1.0))
        .unwrap();
    etat.ajouter(premiers[0] + 1, arbre("r7_2022_1", "09", 2.0, 2.0))
        .unwrap();
    etat.ajouter(premiers[1], arbre("r8_2022_0", "61", 3.0, 3.0))
        .unwrap();
    assert_eq!(etat.prochain_numero(), prochain);
    assert_eq!(etat.numero, vec![0, 1, 2, 3]);
    etat.verifier().unwrap();
    let erreur = etat
        .ajouter(99, arbre("r9_2022_0", "09", 0.0, 0.0))
        .unwrap_err();
    assert_eq!(erreur.code, CodeSortie::ErreurInterne);
    assert_eq!(etat.len(), 4, "un ajout refusé ne laisse aucune trace");
    etat.verifier().unwrap();
}

#[test]
fn retirer_les_morts_garde_l_ordre_et_ne_reattribue_aucun_numero() {
    let mut etat = EtatArbres::depuis_initiaux(vec![
        arbre("a", "09", 1.0, 10.0),
        arbre("b", "61", 2.0, 20.0),
        arbre("c", "02", 3.0, 30.0),
        arbre("d", "09", 4.0, 40.0),
    ])
    .unwrap();
    etat.vivant[0] = false;
    etat.vivant[2] = false;
    etat.retirer_morts();
    assert_eq!(etat.tree_id, vec!["b", "d"]);
    assert_eq!(etat.numero, vec![1, 3]);
    assert_eq!(etat.x, vec![2.0, 4.0]);
    assert_eq!(etat.y, vec![20.0, 40.0]);
    assert_eq!(
        etat.espece_packee,
        vec![packer_essence("61").unwrap(), packer_essence("09").unwrap()]
    );
    assert_eq!(etat.prochain_numero(), 4);
    etat.verifier().unwrap();
}

#[test]
fn des_colonnes_desaccordees_sont_le_code_1() {
    let mut etat = EtatArbres::depuis_initiaux(vec![arbre("a", "09", 1.0, 1.0)]).unwrap();
    etat.d130.push(12.0);
    assert_eq!(etat.verifier().unwrap_err().code_sortie(), 1);
}

#[test]
fn ajouter_beaucoup_d_arbres_reste_lineaire_et_occupe_ce_qui_est_reserve() {
    let mut etat = EtatArbres::vide();
    for rang in 0..100_000u64 {
        etat.ajouter(rang, arbre(&format!("r{rang}"), "09", 0.0, 0.0))
            .unwrap();
    }
    assert_eq!(etat.len(), 100_000);
    // Croissance par doublement : au plus deux fois la place nécessaire.
    assert!(etat.x.capacity() < 2 * 100_000 + 16);
    assert!(etat.octets_occupes() > 100_000 * 57);
}

#[test]
fn une_reservation_impossible_est_le_code_4() {
    let mut etat = EtatArbres::vide();
    assert_eq!(etat.reserver(usize::MAX / 4).unwrap_err().code_sortie(), 4);
}
