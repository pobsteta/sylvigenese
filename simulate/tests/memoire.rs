//! Tests de l'estimation de la mémoire et de la lecture de MemAvailable (mission 035 ;
//! src/memoire.rs, spec §6, T3).

use std::path::Path;

use simulate::erreurs::CodeSortie;
use simulate::etat::{ArbreNouveau, EtatArbres, OCTETS_FIXES_PAR_ARBRE};
use simulate::memoire::{
    analyser_meminfo, estimer, lire_mem_available, reserver_f64, verifier, Besoin, COPIES_ETAT,
    MARGE,
};

const MEMINFO_ESSAI: &str = "MemTotal:       16314996 kB\n\
MemFree:         1203348 kB\n\
MemAvailable:    9876543 kB\n\
Buffers:          412300 kB\n";

#[test]
fn memavailable_est_lu_en_kio_et_rendu_en_octets() {
    assert_eq!(analyser_meminfo(MEMINFO_ESSAI).unwrap(), 9_876_543 * 1024);
}

#[test]
fn sans_ligne_memavailable_la_memoire_n_est_pas_verifiable_code_4() {
    let erreur = analyser_meminfo("MemTotal: 100 kB\nMemFree: 50 kB\n").unwrap_err();
    assert_eq!(erreur.code, CodeSortie::MemoireInsuffisante);
    assert!(erreur.message.contains("non vérifiable"));
    for mal in [
        "MemAvailable: beaucoup kB\n",
        "MemAvailable: 12 MB\n",
        "MemAvailable:\n",
    ] {
        assert_eq!(analyser_meminfo(mal).unwrap_err().code_sortie(), 4, "{mal}");
    }
    let absent = lire_mem_available(Path::new("/chemin/qui/n/existe/pas/meminfo")).unwrap_err();
    assert_eq!(absent.code_sortie(), 4);
}

#[test]
fn le_meminfo_de_la_machine_se_lit_quand_il_existe() {
    let chemin = Path::new(simulate::memoire::MEMINFO);
    if chemin.exists() {
        let octets = lire_mem_available(chemin).unwrap();
        assert!(octets > 0);
    }
}

#[test]
fn l_estimation_suit_sa_formule() {
    let besoin = Besoin {
        arbres_max: 1_000_000,
        octets_texte_par_arbre: 20,
        valeurs_raster: 3 * 1536,
        octets_supplementaires: 1000,
    };
    let attendu = COPIES_ETAT * 1_000_000 * (OCTETS_FIXES_PAR_ARBRE + 20) + 3 * 1536 * 4 + 1000;
    assert_eq!(estimer(&besoin).unwrap(), attendu);
    // 7 colonnes de 8 octets, un booléen, deux en-têtes de String (24 octets sur 64 bits).
    assert_eq!(
        OCTETS_FIXES_PAR_ARBRE,
        7 * 8 + 1 + 2 * std::mem::size_of::<String>() as u64
    );
}

#[test]
fn l_estimation_couvre_un_etat_reel_au_texte_pres() {
    let n = 5000usize;
    let mut arbres = Vec::new();
    for rang in 0..n {
        arbres.push(ArbreNouveau {
            tree_id: format!("t{rang:06}"),
            espece: "09".to_string(),
            cellule: rang as u64 % 1536,
            x: 700_012.5,
            y: 6_500_987.5,
            d130: 25.0,
            h: 20.0,
        });
    }
    let etat = EtatArbres::depuis_initiaux(arbres).unwrap();
    let texte_par_arbre = etat.octets_texte().div_ceil(n as u64);
    let besoin = Besoin {
        arbres_max: n as u64,
        octets_texte_par_arbre: texte_par_arbre,
        ..Besoin::default()
    };
    let une_copie = estimer(&besoin).unwrap() / COPIES_ETAT;
    let occupe = etat.octets_occupes();
    assert!(
        une_copie >= occupe,
        "estimation {une_copie} sous l'occupation réelle {occupe}"
    );
    assert!(
        une_copie - occupe < n as u64,
        "estimation trop large : {une_copie} contre {occupe}"
    );
}

#[test]
fn un_besoin_hors_de_portee_est_le_code_4() {
    let besoin = Besoin {
        arbres_max: u64::MAX / 2,
        ..Besoin::default()
    };
    assert_eq!(estimer(&besoin).unwrap_err().code_sortie(), 4);
}

#[test]
fn la_marge_est_de_neuf_dixiemes() {
    assert_eq!(MARGE, 0.9);
    assert!(verifier(900, 1000).is_ok());
    let erreur = verifier(901, 1000).unwrap_err();
    assert_eq!(erreur.code, CodeSortie::MemoireInsuffisante);
    assert!(erreur.message.contains("MemAvailable"));
    assert!(verifier(0, 0).is_ok());
    assert!(verifier(u64::MAX, u64::MAX).is_err());
    assert!(verifier(9 * (1u64 << 60), 10 * (1u64 << 60)).is_ok());
}

#[test]
fn une_reservation_impossible_rend_le_code_4_sans_planter() {
    let erreur = reserver_f64(usize::MAX / 4, "essai").unwrap_err();
    assert_eq!(erreur.code_sortie(), 4);
    assert!(erreur.message.contains("essai"));
    assert_eq!(reserver_f64(10, "essai").unwrap().capacity(), 10);
}
