//! Tests de l'aléa à compteur chaîné (mission 035 ; src/alea.rs, table de référence).

use simulate::alea::{mix, packer_essence, u, Sorte};
use simulate::erreurs::CodeSortie;

/// La table publiée dans la documentation de src/alea.rs (graine, année, entité, essence,
/// essence packée, sorte, u), calculée indépendamment en Python avec des entiers exacts.
const TABLE: [(u64, i32, u64, &str, u64, u64, f64); 21] = [
    (0, 0, 0, "09", 0x3039, 1, 0.48056368115436876),
    (42, 2021, 0, "09", 0x3039, 1, 0.06895494909539879),
    (42, 2022, 0, "09", 0x3039, 1, 0.4503299362101849),
    (42, 2021, 1, "09", 0x3039, 1, 0.30124461246969614),
    (42, 2021, 0, "02", 0x3032, 1, 0.7497589962937468),
    (42, 2021, 0, "09", 0x3039, 2, 0.07547703664965388),
    (42, 2021, 0, "09", 0x3039, 3, 0.07052374013721907),
    (42, 2021, 0, "09", 0x3039, 4, 0.5321586419134955),
    (20261125, 2021, 12345, "61", 0x3631, 1, 0.27819323804150864),
    (20261125, 2021, 12345, "61", 0x3631, 2, 0.9476109114532498),
    (
        20261125,
        2050,
        999999,
        "53CA",
        0x35334341,
        3,
        0.29362229884891977,
    ),
    (
        20261125,
        2050,
        999999,
        "53CA",
        0x35334341,
        4,
        0.029784762073752136,
    ),
    (1, -1, 0, "09", 0x3039, 1, 0.8490581469247986),
    (
        u64::MAX,
        2100,
        u64::MAX,
        "62",
        0x3632,
        1,
        0.9707035288058078,
    ),
    (7, 0, 0, "15S", 0x313553, 1, 0.9040441808514458),
    (
        123456789,
        2030,
        1535,
        "17C",
        0x313743,
        2,
        0.008639326053565544,
    ),
    (42, 2021, 7, "05", 0x3035, 1, 0.6521829738191267),
    (42, 2021, 8, "05", 0x3035, 1, 0.7265085658991912),
    (99, 2025, 1 << 32, "52", 0x3532, 4, 0.5117011474945781),
    (1 << 63, 1999, 31, "10", 0x3130, 3, 0.3806009485614703),
    (5, 2040, 77, "23AB", 0x32334142, 2, 0.018409045937601398),
];

fn sorte(numero: u64) -> Sorte {
    match numero {
        1 => Sorte::Mort,
        2 => Sorte::NbRecrues,
        3 => Sorte::RecrueX,
        4 => Sorte::RecrueY,
        _ => panic!("sorte {numero} inconnue"),
    }
}

#[test]
fn mix_de_zero_est_la_premiere_sortie_connue_de_splitmix64() {
    assert_eq!(mix(0), 0xE220_A839_7B1D_CDAF);
}

#[test]
fn la_table_de_reference_est_redonnee_au_bit_pres() {
    for (graine, annee, entite, code, packee, numero, attendu) in TABLE {
        assert_eq!(packer_essence(code).unwrap(), packee, "essence {code}");
        let obtenu = u(graine, annee, entite, packee, sorte(numero));
        assert_eq!(
            obtenu.to_bits(),
            attendu.to_bits(),
            "u({graine}, {annee}, {entite}, {code}, {numero}) = {obtenu}, attendu {attendu}"
        );
    }
}

#[test]
fn la_table_de_la_documentation_est_celle_du_test() {
    let doc = std::fs::read_to_string(concat!(env!("CARGO_MANIFEST_DIR"), "/src/alea.rs")).unwrap();
    for (_, _, _, code, packee, _, attendu) in TABLE {
        let cellule_u = format!("| {attendu:?} |");
        assert!(
            doc.contains(&cellule_u),
            "valeur {attendu:?} absente de la doc de src/alea.rs"
        );
        let cellule_essence = format!("{code} ({packee:#x})");
        assert!(
            doc.contains(&cellule_essence),
            "« {cellule_essence} » absent de la doc"
        );
    }
}

#[test]
fn les_sortes_valent_un_a_quatre() {
    assert_eq!(Sorte::Mort.valeur(), 1);
    assert_eq!(Sorte::NbRecrues.valeur(), 2);
    assert_eq!(Sorte::RecrueX.valeur(), 3);
    assert_eq!(Sorte::RecrueY.valeur(), 4);
}

#[test]
fn u_reste_dans_zero_un() {
    for entite in 0..20_000u64 {
        let valeur = u(20261125, 2021, entite, 0x3039, Sorte::Mort);
        assert!((0.0..1.0).contains(&valeur), "u = {valeur}");
    }
}

#[test]
fn u_ne_depend_que_de_ses_cles_pas_de_l_ordre_des_appels() {
    let a_l_endroit: Vec<f64> = (0..1000u64)
        .map(|e| u(3, 2030, e, 0x3631, Sorte::RecrueX))
        .collect();
    let a_l_envers: Vec<f64> = (0..1000u64)
        .rev()
        .map(|e| u(3, 2030, e, 0x3631, Sorte::RecrueX))
        .collect();
    for (rang, valeur) in a_l_endroit.iter().enumerate() {
        assert_eq!(valeur.to_bits(), a_l_envers[999 - rang].to_bits());
    }
}

#[test]
fn le_chainage_ne_laisse_pas_deux_cles_s_annuler() {
    // Avec un simple ou exclusif des clés, (année = a, entité = a) donnerait le même mélange
    // que (0, 0) ; chaîné, non.
    let a = 0x1234_5678u64;
    let annule = u(42, a as i32, a, 0x3039, Sorte::Mort);
    let zero = u(42, 0, 0, 0x3039, Sorte::Mort);
    assert_ne!(annule.to_bits(), zero.to_bits());
}

#[test]
fn la_moyenne_et_la_repartition_sont_plausibles() {
    // Contrôle grossier (pas un test statistique complet) : 100 000 tirages, moyenne proche de
    // 0,5 et dix classes de largeur 0,1 chacune proches de 10 %.
    let n = 100_000u64;
    let mut somme = 0.0;
    let mut classes = [0u64; 10];
    for entite in 0..n {
        let valeur = u(7, 2025, entite, 0x3039, Sorte::NbRecrues);
        somme += valeur;
        classes[(valeur * 10.0) as usize] += 1;
    }
    let moyenne = somme / n as f64;
    assert!((moyenne - 0.5).abs() < 0.005, "moyenne {moyenne}");
    for compte in classes {
        let part = compte as f64 / n as f64;
        assert!((part - 0.1).abs() < 0.005, "classe à {part}");
    }
}

#[test]
fn un_code_hors_motif_est_refuse_code_2() {
    for code in ["9", "", "AB", "0a", "09abc", "091234", "09-", "1"] {
        let erreur = packer_essence(code).unwrap_err();
        assert_eq!(erreur.code, CodeSortie::EntreeRefusee, "code « {code} »");
        assert_eq!(erreur.code_sortie(), 2);
    }
}

#[test]
fn toutes_les_essences_du_referentiel_se_packent_sans_collision() {
    let chemin = concat!(env!("CARGO_MANIFEST_DIR"), "/../contracts/species.csv");
    let texte = std::fs::read_to_string(chemin).unwrap();
    let mut vus = std::collections::HashMap::new();
    for ligne in texte.lines().skip(1) {
        let code = ligne.split(',').next().unwrap();
        let packee = packer_essence(code).unwrap();
        if let Some(autre) = vus.insert(packee, code.to_string()) {
            panic!("{code} et {autre} ont le même code packé");
        }
    }
    assert_eq!(vus.len(), 195);
}
