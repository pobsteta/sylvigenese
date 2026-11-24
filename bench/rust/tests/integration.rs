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
    assert_eq!(o.status.code(), Some(1));
    let msg = String::from_utf8_lossy(&o.stderr);
    assert!(msg.contains("Contrôle échoué à l'année 2"), "{msg}");

    let o = Command::new(exe).args(["--n", "12", "--years", "6", "--hmax-zero", "--out"]).arg(&out).output().unwrap();
    assert_eq!(o.status.code(), Some(1));
    assert!(String::from_utf8_lossy(&o.stderr).contains("refusée avant le premier pas"));

    let o = Command::new(exe).args(["--n", "abc"]).output().unwrap();
    assert_eq!(o.status.code(), Some(2));
    assert!(String::from_utf8_lossy(&o.stderr).contains("Valeur invalide"));
}
