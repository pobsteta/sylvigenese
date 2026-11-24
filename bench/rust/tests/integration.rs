//! Tests de bout en bout : arrêt de contrôle, entrée invalide, identité au bit près 1 fil / 4 fils.

use bench_sim::sim::{Config, init_state, run};
use std::path::PathBuf;
use std::process::Command;

fn tmp(nom: &str) -> PathBuf {
    let d = std::env::temp_dir().join(format!("bench-sim-test-{}-{nom}", std::process::id()));
    let _ = std::fs::remove_dir_all(&d);
    d
}

fn cfg(n: usize, years: u64, threads: usize, out: PathBuf) -> Config {
    Config { n, years, seed: 42, threads, out, inject_nan: None, hmax_zero: false }
}

#[test]
fn identite_au_bit_pres_1_et_4_fils_n200_y5() {
    let (d1, d4) = (tmp("t1"), tmp("t4"));
    run(&cfg(200, 5, 1, d1.clone())).unwrap();
    run(&cfg(200, 5, 4, d4.clone())).unwrap();
    for f in ["summary.csv", "state_final.f32"] {
        let a = std::fs::read(d1.join(f)).unwrap();
        let b = std::fs::read(d4.join(f)).unwrap();
        assert!(!a.is_empty());
        assert!(a == b, "{f} diffère entre 1 et 4 fils");
    }
    // forme des sorties : 3 * 8 * 200 * 200 f32 ; 5 ans * 8 essences + entête
    assert_eq!(std::fs::metadata(d1.join("state_final.f32")).unwrap().len(), 3 * 8 * 200 * 200 * 4);
    let csv = std::fs::read_to_string(d1.join("summary.csv")).unwrap();
    assert_eq!(csv.lines().count(), 1 + 5 * 8);
    assert_eq!(csv.lines().next().unwrap(), "year,species,sum_B,sum_D,mean_H");
    assert!(d1.join("timing.json").exists());
    // la simulation fait quelque chose (pas un état nul)
    assert!(csv.lines().skip(1).any(|l| l.split(',').nth(3).unwrap().parse::<f64>().unwrap() > 0.0));
}

#[test]
fn inject_nan_arrete_avec_message() {
    let out = tmp("nan");
    let mut c = cfg(12, 6, 2, out.clone());
    c.inject_nan = Some(3);
    let e = run(&c).unwrap_err().to_string();
    assert!(e.contains("année 3"), "{e}");
    assert!(e.contains("essence 0"), "{e}");
    assert!(e.contains("cellule 0"), "{e}");
    assert!(e.contains("NaN"), "{e}");
    assert!(!out.join("summary.csv").exists(), "aucune sortie partielle");
}

#[test]
fn hmax_zero_refuse_avant_le_premier_pas() {
    let e = init_state(12, 42, true).err().expect("doit être refusé").to_string();
    assert!(e.contains("Hmax"), "{e}");
    assert!(e.contains("essence 0") && e.contains("cellule 0"), "{e}");
    let out = tmp("hz");
    let mut c = cfg(12, 6, 1, out.clone());
    c.hmax_zero = true;
    assert!(run(&c).is_err());
    assert!(!out.exists(), "rien n'est écrit : refus avant le premier pas");
}

#[test]
fn binaire_code_de_sortie_non_nul_et_message_francais() {
    let exe = env!("CARGO_BIN_EXE_bench-sim");
    let out = tmp("bin");
    let o = Command::new(exe)
        .args(["--n", "12", "--years", "6", "--out"])
        .arg(&out)
        .args(["--inject-nan", "2"])
        .output()
        .unwrap();
    assert_eq!(o.status.code(), Some(3));
    let msg = String::from_utf8_lossy(&o.stderr);
    assert!(msg.contains("Contrôle échoué à l'année 2"), "{msg}");

    let o = Command::new(exe).args(["--n", "12", "--years", "6", "--hmax-zero", "--out"]).arg(&out).output().unwrap();
    assert_eq!(o.status.code(), Some(2));
    assert!(String::from_utf8_lossy(&o.stderr).contains("refusée avant le premier pas"));

    let o = Command::new(exe).args(["--n", "abc"]).output().unwrap();
    assert_eq!(o.status.code(), Some(2));
    assert!(String::from_utf8_lossy(&o.stderr).contains("Valeur invalide"));
}

#[test]
fn ligne_de_commande_refuse_les_non_entiers_code_2() {
    let exe = env!("CARGO_BIN_EXE_bench-sim");
    let out = tmp("cli");
    let base = |extra: &[&str]| {
        Command::new(exe).args(["--n", "8", "--years", "2", "--out"]).arg(&out).args(extra).output().unwrap()
    };
    for extra in [
        vec!["--seed", "-1"],
        vec!["--seed", "4.5"],
        vec!["--seed", "9007199254740992"], // 2^53
        vec!["--seed", "abc"],
        vec!["--seed", "+3"],
        vec!["--seed", "1e3"],
        vec!["--threads", "2.0"],
        vec!["--threads", "0"],
        vec!["--inject-nan", "1.5"],
        vec!["--inject-nan", "9"],
    ] {
        let o = base(&extra);
        assert_eq!(o.status.code(), Some(2), "{extra:?}");
        assert!(!String::from_utf8_lossy(&o.stderr).is_empty());
    }
    for argv in [["--n", "3.5", "--years", "2"], ["--n", "8", "--years", "2.5"], ["--n", "-8", "--years", "2"]] {
        let o = Command::new(exe).args(argv).arg("--out").arg(&out).output().unwrap();
        assert_eq!(o.status.code(), Some(2), "{argv:?}");
    }
    // 2^53 - 1 est accepté
    assert_eq!(base(&["--seed", "9007199254740991"]).status.code(), Some(0));
}

#[test]
fn memoire_insuffisante_code_4() {
    // 3e12 octets demandés : l'allocation échoue proprement (try_reserve_exact) ou le noyau refuse.
    let exe = env!("CARGO_BIN_EXE_bench-sim");
    let out = tmp("mem");
    let o = Command::new(exe).args(["--n", "400000", "--years", "1", "--out"]).arg(&out).output().unwrap();
    assert_eq!(o.status.code(), Some(4), "{}", String::from_utf8_lossy(&o.stderr));
    assert!(String::from_utf8_lossy(&o.stderr).contains("Mémoire insuffisante"));
}

#[test]
fn controle_d_negatif_et_d_superieur_a_dmax_code_3() {
    use bench_sim::erreur::CODE_CONTROLE;
    let mut st = init_state(8, 42, false).unwrap();
    st.controle(1).unwrap();
    st.d[3 * 64 + 2 * 8 + 5] = -0.5; // essence 3, ligne 2, colonne 5
    let e = st.controle(7).unwrap_err();
    assert_eq!(e.code, CODE_CONTROLE);
    let m = e.to_string();
    assert!(m.contains("année 7") && m.contains("D = -0.5") && m.contains("négative"), "{m}");
    assert!(m.contains("essence 3") && m.contains("ligne 2") && m.contains("colonne 5"), "{m}");

    let mut st = init_state(8, 42, false).unwrap();
    st.d[64 + 9] = 1.0e6 + 1000.0; // essence 1, ligne 1, colonne 1
    let e = st.controle(2).unwrap_err();
    assert_eq!(e.code, CODE_CONTROLE);
    let m = e.to_string();
    assert!(m.contains("Dmax") && m.contains("essence 1") && m.contains("ligne 1") && m.contains("colonne 1"), "{m}");
    // D = Dmax exactement : toléré (D > Dmax seulement)
    let mut st = init_state(8, 42, false).unwrap();
    st.d[0] = 1.0e6;
    st.controle(1).unwrap();
}

#[test]
fn resume_de_reference_n16_y30_seed42() {
    // SPEC §11 AM4 : contient un recrutement (sum_B augmente à partir de l'année 20).
    let out = tmp("ref");
    run(&cfg(16, 30, 1, out.clone())).unwrap();
    let ref_path = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../reference/summary_n16_y30_seed42.csv");
    let attendu = std::fs::read_to_string(&ref_path).expect("référence introuvable");
    let obtenu = std::fs::read_to_string(out.join("summary.csv")).unwrap();
    let (la, lo): (Vec<_>, Vec<_>) = (attendu.lines().collect(), obtenu.lines().collect());
    assert_eq!(la.len(), lo.len());
    assert_eq!(la[0], lo[0]);
    let mut pire = 0.0f64;
    for (a, o) in la.iter().zip(&lo).skip(1) {
        let (fa, fo): (Vec<_>, Vec<_>) = (a.split(',').collect(), o.split(',').collect());
        assert_eq!(fa[0], fo[0]);
        assert_eq!(fa[1], fo[1]);
        for k in 2..5 {
            let (x, y): (f64, f64) = (fa[k].parse().unwrap(), fo[k].parse().unwrap());
            let e = if x == 0.0 { y.abs() } else { ((y - x) / x).abs() };
            pire = pire.max(e);
            assert!(e <= 1e-9, "{a} / {o} : écart relatif {e}");
        }
    }
    eprintln!("écart relatif max contre la référence : {pire:e}");
    // le recrutement a bien lieu : sum_B (essence 0) augmente entre les années 19 et 30
    let sb = |year: usize| -> f64 {
        lo.iter().skip(1).find(|l| l.starts_with(&format!("{year},0,"))).unwrap().split(',').nth(2).unwrap().parse().unwrap()
    };
    assert!(sb(30) > sb(19));
}
