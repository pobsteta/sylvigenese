//! Identité au bit près entre nombres de fils, et codes d'arrêt de l'assemblage (mission 038 ;
//! plan M3a, T1 ; spec §6).
//!
//! La zone d'essai en mémoire est celle de `tests/non_regression.rs` (incluse ici par `#[path]`,
//! un lien plutôt qu'une copie ; ses tests y tournent donc une seconde fois, en moins d'une
//! seconde). Coordonnées : x = est, y = nord, EPSG:2154 (voir ce fichier).
//!
//! Preuve d'identité : les SHA-256 de tous les fichiers écrits (Parquet de `trees` et `cells`,
//! `flags.parquet`) et de `run.json` sans `duration_s` ni `threads` sont les mêmes pour 1, 2, 3,
//! 4 et 7 fils (même machine).

#[path = "non_regression.rs"]
mod non_regression;

use std::collections::BTreeMap;
use std::path::Path;

use simulate::erreurs::CodeSortie;
use simulate::sorties;

use non_regression::{dossier_neuf, jeux_d_essai, lancement, zone_d_essai, T0};

/// SHA-256 de chaque fichier du dossier (chemin relatif → empreinte) ; run.json sans les champs
/// qui disent le calcul (durée, fils) et non le résultat.
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
            let relatif = chemin
                .strip_prefix(dossier)
                .unwrap()
                .to_string_lossy()
                .to_string();
            let octets = std::fs::read(&chemin).unwrap();
            let empreinte = if relatif == "run.json" {
                let mut run: serde_json::Value = serde_json::from_slice(&octets).unwrap();
                let objet = run.as_object_mut().unwrap();
                assert!(objet.remove("duration_s").is_some());
                assert!(objet.remove("threads").is_some());
                sorties::sha256_hex(serde_json::to_string(&run).unwrap().as_bytes())
            } else {
                sorties::sha256_hex(&octets)
            };
            resultat.insert(relatif, empreinte);
        }
    }
    resultat
}

const ANNEES: u32 = 15;

#[test]
fn memes_octets_pour_1_2_3_4_et_7_fils() {
    let entrees = zone_d_essai(ANNEES);
    let mut reference: Option<BTreeMap<String, String>> = None;
    for fils in [1, 2, 3, 4, 7] {
        let dossier = dossier_neuf(&format!("identite-{fils}"));
        sorties::simuler_et_ecrire(&entrees, &lancement(fils), &dossier).unwrap();
        let run: serde_json::Value =
            serde_json::from_str(&std::fs::read_to_string(dossier.join("run.json")).unwrap())
                .unwrap();
        assert_eq!(run["threads"], fils);
        let actuelles = empreintes(&dossier);
        // 16 années × (trees, cells) + flags + run.json.
        assert_eq!(actuelles.len(), 2 * (ANNEES as usize + 1) + 2);
        match &reference {
            None => reference = Some(actuelles),
            Some(attendues) => {
                for (fichier, empreinte) in attendues {
                    assert_eq!(
                        actuelles.get(fichier),
                        Some(empreinte),
                        "{fichier} diffère entre 1 et {fils} fils"
                    );
                }
            }
        }
        std::fs::remove_dir_all(&dossier).unwrap();
    }
}

#[test]
fn une_autre_graine_donne_d_autres_morts() {
    let mut entrees = zone_d_essai(3);
    let dossier_a = dossier_neuf("graine-a");
    sorties::simuler_et_ecrire(&entrees, &lancement(2), &dossier_a).unwrap();
    entrees.reglages.seed += 1;
    let dossier_b = dossier_neuf("graine-b");
    sorties::simuler_et_ecrire(&entrees, &lancement(2), &dossier_b).unwrap();
    let a = empreintes(&dossier_a);
    let b = empreintes(&dossier_b);
    assert_eq!(
        a["trees/year=2022/part-00000.parquet"], b["trees/year=2022/part-00000.parquet"],
        "t0 ne tire rien"
    );
    assert_ne!(
        a["trees/year=2023/part-00000.parquet"],
        b["trees/year=2023/part-00000.parquet"]
    );
    std::fs::remove_dir_all(&dossier_a).unwrap();
    std::fs::remove_dir_all(&dossier_b).unwrap();
}

#[test]
fn une_memoire_trop_faible_est_refusee_code_4_avant_toute_ecriture() {
    let entrees = zone_d_essai(3);
    let mut lance = lancement(2);
    lance.memoire_disponible = 1;
    let dossier = dossier_neuf("memoire");
    let erreur = sorties::simuler_et_ecrire(&entrees, &lance, &dossier).unwrap_err();
    assert_eq!(erreur.code, CodeSortie::MemoireInsuffisante, "{erreur}");
    assert_eq!(erreur.code_sortie(), 4);
    assert!(erreur.message.contains("Mio"), "{erreur}");
    assert!(
        !dossier.exists(),
        "rien ne doit être écrit avant le contrôle de la mémoire"
    );
}

#[test]
fn la_memoire_est_revue_avant_chaque_pas_quand_l_etat_grandit() {
    let entrees = zone_d_essai(20);
    let premiere = sorties::estimer_memoire(
        entrees.arbres.len() as u64,
        sorties::texte_par_arbre(&entrees.arbres),
        &entrees.grille,
    )
    .unwrap();
    // Assez pour l'état initial (0,9 × disponible ≥ estimation), pas pour l'état qui grandit.
    let mut lance = lancement(1);
    lance.memoire_disponible = premiere * 10 / 9 + 10;
    let dossier = dossier_neuf("memoire-croissance");
    let erreur = sorties::simuler_et_ecrire(&entrees, &lance, &dossier).unwrap_err();
    assert_eq!(erreur.code_sortie(), 4, "{erreur}");
    assert!(
        erreur.message.contains("avant le pas de l'année"),
        "{erreur}"
    );
    let _ = std::fs::remove_dir_all(&dossier);
}

#[test]
fn un_nan_injecte_arrete_avec_le_code_3_et_dit_l_annee() {
    let entrees = zone_d_essai(5);
    for annee in [T0, T0 + 2] {
        let mut lance = lancement(3);
        lance.inject_nan = Some(annee);
        let dossier = dossier_neuf(&format!("nan-{annee}"));
        let erreur = sorties::simuler_et_ecrire(&entrees, &lance, &dossier).unwrap_err();
        assert_eq!(erreur.code_sortie(), 3, "{erreur}");
        assert!(erreur.message.contains("NaN"), "{erreur}");
        assert!(
            erreur.message.contains(&format!("année {annee}")),
            "{erreur}"
        );
        let _ = std::fs::remove_dir_all(&dossier);
    }
}

#[test]
fn un_nan_hors_de_l_horizon_est_une_option_refusee_code_2() {
    let entrees = zone_d_essai(5);
    let mut lance = lancement(1);
    lance.inject_nan = Some(T0 + 6);
    let dossier = dossier_neuf("nan-hors");
    let erreur = sorties::simuler_et_ecrire(&entrees, &lance, &dossier).unwrap_err();
    assert_eq!(erreur.code_sortie(), 2, "{erreur}");
    assert!(!dossier.exists());
}

#[test]
fn korf_sans_point_de_depart_est_refuse_code_2_avant_toute_ecriture() {
    let mut entrees = zone_d_essai(2);
    entrees.parametres = jeux_d_essai(false);
    let dossier = dossier_neuf("korf");
    let erreur = sorties::simuler_et_ecrire(&entrees, &lancement(1), &dossier).unwrap_err();
    assert_eq!(erreur.code_sortie(), 2, "{erreur}");
    assert!(
        erreur.message.contains("t_ref0") && erreur.message.contains("09"),
        "{erreur}"
    );
    assert!(!dossier.exists());
}

#[test]
fn le_point_de_depart_de_korf_vient_des_termes_du_contrat() {
    let entrees = zone_d_essai(1);
    let essences = vec!["03".to_string(), "09".to_string()];
    let reference = sorties::reference_korf(
        &entrees.parametres.courbe_hauteur,
        &entrees.referentiel,
        &essences,
    )
    .unwrap()
    .unwrap();
    assert_eq!(
        (
            reference.age_depart,
            reference.hauteur_depart,
            reference.age_reference
        ),
        (6.0, 1.375, 100.0)
    );
    // Sans essence de Korf, pas de point de départ, et ce n'est pas une erreur.
    let seule = vec!["03".to_string()];
    assert!(sorties::reference_korf(
        &entrees.parametres.courbe_hauteur,
        &entrees.referentiel,
        &seule
    )
    .unwrap()
    .is_none());
}

#[test]
fn un_dossier_de_sortie_deja_present_n_est_pas_ecrase() {
    let dossier = dossier_neuf("present");
    std::fs::create_dir_all(&dossier).unwrap();
    let erreur = sorties::simuler_et_ecrire(&zone_d_essai(1), &lancement(1), &dossier).unwrap_err();
    assert_eq!(erreur.code_sortie(), 1, "{erreur}");
    std::fs::remove_dir_all(&dossier).unwrap();
}

#[test]
fn les_candidates_au_recrutement_sont_l_etat_plus_les_lignes_propres() {
    // État initial de la seule essence 03 : 09 (lignes propres de Korf) reste candidate (T6, 037).
    let mut entrees = zone_d_essai(1);
    let mut arbres = entrees.arbres.clone();
    for espece in arbres.espece.iter_mut() {
        *espece = "03".to_string();
    }
    let initiaux: Vec<simulate::etat::ArbreNouveau> = (0..arbres.len())
        .map(|i| simulate::etat::ArbreNouveau {
            tree_id: arbres.tree_id[i].clone(),
            espece: "03".to_string(),
            cellule: arbres.cellule[i],
            x: arbres.x[i],
            y: arbres.y[i],
            d130: arbres.d130[i],
            h: arbres.h[i],
        })
        .collect();
    arbres = simulate::etat::EtatArbres::depuis_initiaux(initiaux).unwrap();
    entrees.arbres = arbres;
    let modeles = sorties::preparer_modeles(&entrees).unwrap();
    let codes: Vec<&str> = modeles
        .candidates
        .iter()
        .map(|r| modeles.essences[*r].espece.as_str())
        .collect();
    assert_eq!(codes, vec!["03", "09"]);
}
