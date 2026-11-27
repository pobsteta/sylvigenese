//! Mesure le coût de la convolution de dispersion seule (plan, spectre du noyau, une convolution)
//! pour une grille N x N et un K donnés. Ligne CSV sur stdout :
//! n,k,fils,colonnes_fft,lignes_fft,tampon_cellules,plan_s,spectre_s,convolution_s_mediane,repetitions
//! Usage : noyau_fft N K REPETITIONS ECHELLE_M   (fils : variable RAYON_NUM_THREADS)
use simulate::dispersion::{cellules_tampon, noyau_exponentiel_puissance, PlanDispersion};
use std::time::Instant;

fn main() {
    let a: Vec<String> = std::env::args().collect();
    let n: usize = a[1].parse().unwrap();
    let k: usize = a[2].parse().unwrap();
    let rep: usize = a[3].parse().unwrap();
    let echelle: f64 = a[4].parse().unwrap();
    let fils = std::env::var("RAYON_NUM_THREADS").unwrap_or_default();
    let t = Instant::now();
    let plan = PlanDispersion::nouveau(n, n, k).expect("plan");
    let plan_s = t.elapsed().as_secs_f64();
    let t = Instant::now();
    let noyau = noyau_exponentiel_puissance(echelle, 1.0, 25.0, k).expect("noyau");
    let spectre = plan.spectre(&noyau).expect("spectre");
    let spectre_s = t.elapsed().as_secs_f64();
    // champ de graines déterministe (un semencier sur sept)
    let champ: Vec<f64> = (0..n * n).map(|i| if i % 7 == 0 { 1.0 } else { 0.0 }).collect();
    let mut temps = Vec::new();
    let mut somme = 0.0;
    for _ in 0..rep {
        let t = Instant::now();
        let r = plan.convoluer(&champ, &spectre).expect("convoluer");
        temps.push(t.elapsed().as_secs_f64());
        somme += r[r.len() / 2];
    }
    temps.sort_by(|x, y| x.partial_cmp(y).unwrap());
    eprintln!("controle {somme}");
    println!(
        "{n},{k},{fils},{},{},{},{plan_s:.4},{spectre_s:.4},{:.4},{rep}",
        plan.colonnes_fft, plan.lignes_fft, cellules_tampon(n, n, k), temps[temps.len() / 2]
    );
}
