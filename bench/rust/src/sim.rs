//! État, pas annuel (spec §6), contrôle (§6.8) et sorties (§7).
//!
//! Disposition : tableau plat, index `s * n * n + c`, avec `c = i * n + j`.
//! État stocké en f32 ; intermédiaires en f64 ; arrondi en f32 à chaque étape numérotée
//! qui écrit l'état (voir README, ambiguïté A1).

use crate::conv::{Convolver, kernel};
use crate::erreur::{CODE_CONTROLE, Res, alloue};
use crate::{erreur, erreur_code};
use crate::rng::u;
use rayon::prelude::*;
use std::fmt::Write as _;
use std::io::Write as _;
use std::path::PathBuf;
use std::time::Instant;

pub const S: usize = 8;
const FEC: f64 = 100.0;
const ALPHA: f64 = 50.0;
const K_EXT: f64 = 0.05;
const EST: f64 = 0.01;
const H_REC: f64 = 3.0;
const G: f64 = 0.0001;
const DMAX: f64 = 1.0e6;

fn tol(s: usize) -> f64 { 0.5 + 0.25 * s as f64 }
fn growth(s: usize) -> f64 { 0.3 + 0.05 * s as f64 }
fn mort(s: usize) -> f64 { 0.05 + 0.01 * s as f64 }

#[derive(Debug, Clone)]
pub struct Config {
    pub n: usize,
    pub years: u64,
    pub seed: u64,
    pub threads: usize,
    pub out: PathBuf,
    pub inject_nan: Option<u64>,
    pub hmax_zero: bool,
}

impl Config {
    pub fn valider(&self) -> Res<()> {
        if self.n == 0 {
            return Err(erreur!("--n doit être >= 1."));
        }
        if self.n > 1 << 20 {
            return Err(erreur!("--n = {} est déraisonnable (maximum accepté : {}).", self.n, 1 << 20));
        }
        if self.seed >= 1u64 << 53 {
            return Err(erreur!("--seed doit être un entier dans [0, 2^53) ; reçu {}.", self.seed));
        }
        if self.years == 0 {
            return Err(erreur!("--years doit être >= 1."));
        }
        if self.threads == 0 || self.threads > 4096 {
            return Err(erreur!("--threads doit être compris entre 1 et 4096."));
        }
        if let Some(y) = self.inject_nan {
            if y < 1 || y > self.years {
                return Err(erreur!("--inject-nan {y} : l'année doit être comprise entre 1 et --years ({}).", self.years));
            }
        }
        Ok(())
    }
}

pub struct State {
    pub n: usize,
    pub b: Vec<f32>,
    pub d: Vec<f32>,
    pub h: Vec<f32>,
    pub hmax: Vec<f32>,
    pub forest: Vec<u8>,
}

/// État initial (spec §3) et refus des entrées invalides (Hmax <= 0 ou non fini).
pub fn init_state(n: usize, seed: u64, hmax_zero: bool) -> Res<State> {
    let nn = n * n;
    let mut forest = alloue(nn, 0u8, "la carte des cellules boisées")?;
    forest.par_iter_mut().enumerate().for_each(|(c, f)| {
        *f = (u(seed, 0, c as u64, 100) < 0.7) as u8;
    });
    let mut hmax = alloue(S * nn, 0f32, "Hmax")?;
    let mut b = alloue(S * nn, 0f32, "B")?;
    hmax.par_chunks_mut(nn).zip(b.par_chunks_mut(nn)).enumerate().for_each(|(s, (hm, bb))| {
        for c in 0..nn {
            hm[c] = (10.0 + 30.0 * u(seed, 0, c as u64, 200 + s as u64)) as f32;
            bb[c] = (forest[c] as f64 * 5.0 * u(seed, 0, c as u64, 300 + s as u64)) as f32;
        }
    });
    if hmax_zero {
        hmax[0] = 0.0;
    }
    // Lecture/validation : refus avant le premier pas.
    for s in 0..S {
        for c in 0..nn {
            let v = hmax[s * nn + c];
            if !(v > 0.0) || !v.is_finite() {
                return Err(erreur!(
                    "Entrée invalide : Hmax doit être strictement positif et fini, or Hmax = {v} (essence {s}, cellule {c}, ligne {}, colonne {}). Simulation refusée avant le premier pas.",
                    c / n, c % n
                ));
            }
        }
    }
    let d = alloue(S * nn, 0f32, "D")?;
    let h = alloue(S * nn, 0f32, "H")?;
    Ok(State { n, b, d, h, hmax, forest })
}

/// Tampons de travail f64 (n x n) : deux champs de graines, deux de dispersion, L, Btot.
pub struct Work {
    pa: Vec<f64>,
    pb: Vec<f64>,
    qa: Vec<f64>,
    qb: Vec<f64>,
    l: Vec<f64>,
    btot: Vec<f64>,
}

impl Work {
    pub fn new(n: usize) -> Res<Self> {
        let m = n * n;
        Ok(Work {
            pa: alloue(m, 0f64, "le tampon des graines A")?,
            pb: alloue(m, 0f64, "le tampon des graines B")?,
            qa: alloue(m, 0f64, "le tampon de dispersion A")?,
            qb: alloue(m, 0f64, "le tampon de dispersion B")?,
            l: alloue(m, 0f64, "la lumière L")?,
            btot: alloue(m, 0f64, "Btot")?,
        })
    }
}

impl State {
    /// Un pas annuel, spec §6.1 à §6.7. Les étapes 4 à 7 sont indépendantes d'une
    /// essence à l'autre une fois `L` calculée (étape 3, avant tout recrutement), donc
    /// on traite essence par essence (économie de mémoire, même résultat).
    pub fn step(&mut self, year: u64, seed: u64, conv: &mut Convolver, w: &mut Work) {
        let n = self.n;
        let nn = n * n;

        // 3. Lumière : Btot (somme sur s dans l'ordre), Bbar (3x3, cellules présentes), L.
        {
            let b = &self.b;
            w.btot.par_iter_mut().enumerate().for_each(|(c, t)| {
                let mut sum = 0.0f64;
                for s in 0..S {
                    sum += b[s * nn + c] as f64;
                }
                *t = sum;
            });
            let btot = &w.btot;
            w.l.par_chunks_mut(n).enumerate().for_each(|(i, row)| {
                for (j, lv) in row.iter_mut().enumerate() {
                    let mut sum = 0.0f64;
                    let mut cnt = 0u32;
                    for ii in i.saturating_sub(1)..=(i + 1).min(n - 1) {
                        for jj in j.saturating_sub(1)..=(j + 1).min(n - 1) {
                            sum += btot[ii * n + jj];
                            cnt += 1;
                        }
                    }
                    *lv = (-K_EXT * (sum / cnt as f64)).exp();
                }
            });
        }

        // Essences regroupées deux par deux dans une FFT complexe (AM1).
        for s0 in (0..S).step_by(2) {
            // 1. Graines
            {
                let (b0, b1) = (&self.b[s0 * nn..(s0 + 1) * nn], &self.b[(s0 + 1) * nn..(s0 + 2) * nn]);
                w.pa.par_iter_mut().zip(b0.par_iter()).for_each(|(p, &b)| *p = FEC * b as f64);
                w.pb.par_iter_mut().zip(b1.par_iter()).for_each(|(p, &b)| *p = FEC * b as f64);
            }
            // 2. Dispersion par FFT (deux essences par FFT complexe)
            conv.convolve_pair(&w.pa, &w.pb, &mut w.qa, &mut w.qb);
            self.update_species(s0, year, seed, &w.qa, &w.l);
            self.update_species(s0 + 1, year, seed, &w.qb, &w.l);
        }
    }

    /// Étapes 4 à 7 pour une essence, cellule par cellule.
    fn update_species(&mut self, s: usize, year: u64, seed: u64, q: &[f64], l: &[f64]) {
        let n = self.n;
        let nn = n * n;
            let hmax = &self.hmax[s * nn..(s + 1) * nn];
            let forest = &self.forest;
            let (ts, rs, ms) = (tol(s), growth(s), mort(s));
            let bs = &mut self.b[s * nn..(s + 1) * nn];
            let ds = &mut self.d[s * nn..(s + 1) * nn];
            let hs = &mut self.h[s * nn..(s + 1) * nn];
            bs.par_chunks_mut(n)
                .zip(ds.par_chunks_mut(n))
                .zip(hs.par_chunks_mut(n))
                .enumerate()
                .for_each(|(i, ((brow, drow), hrow))| {
                    for j in 0..n {
                        let c = i * n + j;
                        let lc = l[c];
                        // 4. Installation
                        drow[j] = (drow[j] as f64 + forest[c] as f64 * EST * q[c] * lc.powf(ts)) as f32;
                        // 5. Croissance, puis plafond (comparaison explicite : un NaN n'est pas masqué)
                        if drow[j] > 0.0 {
                            let h = hrow[j] as f64;
                            hrow[j] = (h + rs * lc * (1.0 - h / hmax[c] as f64)) as f32;
                        }
                        if hrow[j] > hmax[c] {
                            hrow[j] = hmax[c];
                        }
                        // 6. Mortalité
                        let uu = u(seed, year, c as u64, s as u64);
                        drow[j] = (drow[j] as f64 * (1.0 - ms * (0.8 + 0.4 * uu))) as f32;
                        // 7. Recrutement
                        if hrow[j] as f64 >= H_REC {
                            brow[j] = (brow[j] as f64 + G * drow[j] as f64) as f32;
                            drow[j] = 0.0;
                            hrow[j] = 0.0;
                        }
                    }
                });
    }

    /// 8. Contrôle. Premier défaut dans l'ordre (essence, ligne, colonne, puis B, D, H) :
    /// déterministe quel que soit le nombre de fils (`find_map_first`).
    pub fn controle(&self, year: u64) -> Res<()> {
        let n = self.n;
        let nn = n * n;
        for s in 0..S {
            let r = (0..n).into_par_iter().find_map_first(|i| {
                for j in 0..n {
                    let c = s * nn + i * n + j;
                    let vals = [("B", self.b[c]), ("D", self.d[c]), ("H", self.h[c])];
                    for (nom, v) in vals {
                        let raison = if v.is_nan() {
                            Some("NaN")
                        } else if v < 0.0 {
                            Some("négative")
                        } else if nom == "D" && v as f64 > DMAX {
                            Some("supérieure à Dmax = 1e6")
                        } else {
                            None
                        };
                        if let Some(r) = raison {
                            return Some((i, j, nom, v, r));
                        }
                    }
                }
                None
            });
            if let Some((i, j, nom, v, r)) = r {
                return Err(erreur_code!(
                    CODE_CONTROLE,
                    "Contrôle échoué à l'année {year} : {nom} = {v} ({r}) pour l'essence {s}, cellule {} (ligne {i}, colonne {j}). Arrêt, aucune correction silencieuse.",
                    i * n + j
                ));
            }
        }
        Ok(())
    }

    /// Les lignes de summary.csv (valeurs, non formatées) pour pour l'année `year` (spec §7).
    /// Réduction déterministe : une somme partielle f64 par ligne de grille (j croissant),
    /// puis somme des lignes dans l'ordre i croissant.
    pub fn summary_rows(&self, year: u64, out: &mut Vec<SummaryRow>) {
        let n = self.n;
        let nn = n * n;
        for s in 0..S {
            let rows: Vec<(f64, f64, f64, u64)> = (0..n)
                .into_par_iter()
                .map(|i| {
                    let (mut sb, mut sd, mut sh, mut cnt) = (0.0f64, 0.0f64, 0.0f64, 0u64);
                    for j in 0..n {
                        let c = s * nn + i * n + j;
                        sb += self.b[c] as f64;
                        sd += self.d[c] as f64;
                        if self.d[c] > 0.0 {
                            sh += self.h[c] as f64;
                            cnt += 1;
                        }
                    }
                    (sb, sd, sh, cnt)
                })
                .collect();
            let (mut sb, mut sd, mut sh, mut cnt) = (0.0f64, 0.0f64, 0.0f64, 0u64);
            for r in &rows {
                sb += r.0;
                sd += r.1;
                sh += r.2;
                cnt += r.3;
            }
            let mh = if cnt > 0 { sh / cnt as f64 } else { 0.0 };
            out.push(SummaryRow { year, species: s, sum_b: sb, sum_d: sd, mean_h: mh });
        }
    }
}

/// Une ligne de summary.csv, gardée en valeurs pendant le calcul ; le formatage se fait à l'écriture.
#[derive(Debug, Clone, Copy)]
pub struct SummaryRow {
    pub year: u64,
    pub species: usize,
    pub sum_b: f64,
    pub sum_d: f64,
    pub mean_h: f64,
}

/// Texte de summary.csv : 17 chiffres significatifs (notation scientifique, 16 décimales).
pub fn format_summary(rows: &[SummaryRow]) -> String {
    let mut out = String::from("year,species,sum_B,sum_D,mean_H\n");
    for r in rows {
        let _ = writeln!(out, "{},{},{:.16e},{:.16e},{:.16e}", r.year, r.species, r.sum_b, r.sum_d, r.mean_h);
    }
    out
}

#[derive(Debug, Clone, Copy)]
pub struct Timing {
    pub init_s: f64,
    pub step_mean_s: f64,
    pub total_s: f64,
    pub write_s: f64,
}

/// Exécute toute la simulation et écrit les sorties dans `cfg.out`.
/// Les sorties ne sont écrites qu'à la fin : un arrêt de contrôle n'en laisse aucune partielle.
pub fn run(cfg: &Config) -> Res<Timing> {
    cfg.valider()?;
    let pool = rayon::ThreadPoolBuilder::new()
        .num_threads(cfg.threads)
        .build()
        .map_err(|e| erreur!("Impossible de créer le pool de {} fils : {e}", cfg.threads))?;
    pool.install(|| run_inner(cfg))
}

fn run_inner(cfg: &Config) -> Res<Timing> {
    let t0 = Instant::now();
    let mut st = init_state(cfg.n, cfg.seed, cfg.hmax_zero)?;
    let kern = kernel(ALPHA);
    let mut conv = Convolver::new(cfg.n, &kern)?;
    let mut work = Work::new(cfg.n)?;
    let init_s = t0.elapsed().as_secs_f64();

    let mut summary: Vec<SummaryRow> = Vec::new();
    summary.try_reserve_exact(cfg.years as usize * S).map_err(|_| erreur_code!(crate::erreur::CODE_MEMOIRE, "Mémoire insuffisante : impossible d'allouer le résumé ({} lignes).", cfg.years as usize * S))?;
    let t1 = Instant::now();
    for year in 1..=cfg.years {
        if cfg.inject_nan == Some(year) {
            st.h[0] = f32::NAN;
        }
        st.step(year, cfg.seed, &mut conv, &mut work);
        st.controle(year)?;
        st.summary_rows(year, &mut summary);
    }
    let steps_s = t1.elapsed().as_secs_f64();
    let total_s = t0.elapsed().as_secs_f64();

    let t2 = Instant::now();
    std::fs::create_dir_all(&cfg.out)
        .map_err(|e| erreur!("Impossible de créer le dossier de sortie {} : {e}", cfg.out.display()))?;
    std::fs::write(cfg.out.join("summary.csv"), format_summary(&summary))?;
    {
        let f = std::fs::File::create(cfg.out.join("state_final.f32"))?;
        let mut w = std::io::BufWriter::with_capacity(1 << 20, f);
        for arr in [&st.b, &st.d, &st.h] {
            for chunk in arr.chunks(1 << 16) {
                let mut buf = Vec::with_capacity(chunk.len() * 4);
                for v in chunk {
                    buf.extend_from_slice(&v.to_le_bytes());
                }
                w.write_all(&buf)?;
            }
        }
        w.flush()?;
    }
    let write_s = t2.elapsed().as_secs_f64();
    let tm = Timing { init_s, step_mean_s: steps_s / cfg.years as f64, total_s, write_s };
    let json = format!(
        "{{\"lang\": \"rust\", \"n\": {}, \"years\": {}, \"threads\": {}, \"init_s\": {}, \"step_mean_s\": {}, \"total_s\": {}, \"write_s\": {}}}\n",
        cfg.n, cfg.years, cfg.threads, tm.init_s, tm.step_mean_s, tm.total_s, tm.write_s
    );
    std::fs::write(cfg.out.join("timing.json"), json)?;
    Ok(tm)
}
