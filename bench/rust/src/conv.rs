//! Noyau de dispersion (spec §5) et convolution 2D par FFT (spec §6.2).
//!
//! FFT sur TOUTE la grille (pas de tuiles), remplissage à zéro jusqu'à
//! `p >= n + 16` (taille « lisse » 2^a 3^b 5^c), lignes puis colonnes (par
//! transposition). Résultat = convolution linéaire (bord à zéro), recadrée sur n x n.

use crate::erreur::Res;
use crate::erreur;
use rayon::prelude::*;
use rustfft::num_complex::Complex;
use rustfft::{Fft, FftPlanner};
use std::sync::Arc;

pub const RADIUS: usize = 16;
pub const KSIZE: usize = 2 * RADIUS + 1;
const CELL_M: f64 = 25.0;
const RADIUS_M: f64 = 400.0;

type C = Complex<f64>;

/// Noyau KSIZE x KSIZE, indice `(di+16)*33 + (dj+16)`, en f64, somme = 1.
pub fn kernel(alpha: f64) -> Vec<f64> {
    let mut k = vec![0.0f64; KSIZE * KSIZE];
    let r = RADIUS as i64;
    for di in -r..=r {
        for dj in -r..=r {
            let d = CELL_M * ((di * di + dj * dj) as f64).sqrt();
            if d <= RADIUS_M {
                k[(di + r) as usize * KSIZE + (dj + r) as usize] = (-d / alpha).exp();
            }
        }
    }
    let s: f64 = k.iter().sum(); // ordre fixe, séquentiel
    for v in k.iter_mut() {
        *v /= s;
    }
    k
}

/// Plus petite taille >= `min` de la forme 2^a 3^b 5^c.
pub fn fast_size(min: usize) -> usize {
    let mut m = min.max(1);
    loop {
        let mut x = m;
        for f in [2, 3, 5] {
            while x % f == 0 {
                x /= f;
            }
        }
        if x == 1 {
            return m;
        }
        m += 1;
    }
}

fn rows_fft(buf: &mut [C], p: usize, rows: usize, plan: &Arc<dyn Fft<f64>>) {
    let sl = plan.get_inplace_scratch_len();
    buf[..rows * p].par_chunks_mut(p).for_each_init(
        || vec![C::new(0.0, 0.0); sl],
        |scr, row| plan.process_with_scratch(row, scr),
    );
}

/// `dst[j*p + i] = src[i*p + j]`
fn transpose(src: &[C], dst: &mut [C], p: usize) {
    dst.par_chunks_mut(p).enumerate().for_each(|(j, row)| {
        for (i, v) in row.iter_mut().enumerate() {
            *v = src[i * p + j];
        }
    });
}

pub struct Convolver {
    n: usize,
    p: usize,
    fwd: Arc<dyn Fft<f64>>,
    inv: Arc<dyn Fft<f64>>,
    khat: Vec<C>,
    a: Vec<C>,
    b: Vec<C>,
}

impl Convolver {
    /// `kern` : noyau KSIZE x KSIZE (voir `kernel`).
    pub fn new(n: usize, kern: &[f64]) -> Res<Self> {
        if kern.len() != KSIZE * KSIZE {
            return Err(erreur!("Noyau de taille inattendue : {} (attendu {}).", kern.len(), KSIZE * KSIZE));
        }
        let p = fast_size(n + RADIUS);
        let mut planner = FftPlanner::<f64>::new();
        let fwd = planner.plan_fft_forward(p);
        let inv = planner.plan_fft_inverse(p);
        let zero = C::new(0.0, 0.0);
        let mut cv = Convolver { n, p, fwd, inv, khat: Vec::new(), a: vec![zero; p * p], b: vec![zero; p * p] };
        // Noyau placé à l'origine, indices négatifs repliés (modulo p) ; transformé une fois.
        let r = RADIUS as i64;
        for di in -r..=r {
            for dj in -r..=r {
                let i = di.rem_euclid(p as i64) as usize;
                let j = dj.rem_euclid(p as i64) as usize;
                cv.a[i * p + j] = C::new(kern[(di + r) as usize * KSIZE + (dj + r) as usize], 0.0);
            }
        }
        cv.forward(p);
        cv.khat = cv.b.clone();
        Ok(cv)
    }

    /// Taille de la FFT (côté du carré rempli de zéros).
    pub fn padded_size(&self) -> usize {
        self.p
    }

    /// FFT 2D de `a` vers `b` (disposition transposée). Seules les `rows` premières
    /// lignes de `a` peuvent être non nulles : les autres ont une FFT nulle.
    fn forward(&mut self, rows: usize) {
        let p = self.p;
        rows_fft(&mut self.a, p, rows, &self.fwd);
        transpose(&self.a, &mut self.b, p);
        rows_fft(&mut self.b, p, p, &self.fwd);
    }

    /// `out = input ⊛ K` (convolution linéaire, bord à zéro), `input` et `out` en n x n.
    pub fn convolve(&mut self, input: &[f64], out: &mut [f64]) {
        let (n, p) = (self.n, self.p);
        assert_eq!(input.len(), n * n);
        assert_eq!(out.len(), n * n);
        self.a.par_chunks_mut(p).enumerate().for_each(|(i, row)| {
            for (j, v) in row.iter_mut().enumerate() {
                *v = if i < n && j < n { C::new(input[i * n + j], 0.0) } else { C::new(0.0, 0.0) };
            }
        });
        self.forward(n);
        let kh = &self.khat;
        self.b.par_iter_mut().zip(kh.par_iter()).for_each(|(x, k)| *x *= *k);
        rows_fft(&mut self.b, p, p, &self.inv);
        transpose(&self.b, &mut self.a, p);
        rows_fft(&mut self.a, p, n, &self.inv);
        let scale = 1.0 / ((p * p) as f64);
        let a = &self.a;
        out.par_chunks_mut(n).enumerate().for_each(|(i, row)| {
            for (j, v) in row.iter_mut().enumerate() {
                *v = a[i * p + j].re * scale;
            }
        });
    }
}

/// Convolution directe (RÉFÉRENCE DE TEST UNIQUEMENT : interdite dans la simulation).
pub fn convolve_direct(input: &[f64], n: usize, kern: &[f64]) -> Vec<f64> {
    let r = RADIUS as i64;
    let mut out = vec![0.0; n * n];
    for i in 0..n as i64 {
        for j in 0..n as i64 {
            let mut s = 0.0;
            for di in -r..=r {
                for dj in -r..=r {
                    let (a, b) = (i - di, j - dj);
                    if a >= 0 && b >= 0 && a < n as i64 && b < n as i64 {
                        s += input[(a * n as i64 + b) as usize] * kern[((di + r) * KSIZE as i64 + dj + r) as usize];
                    }
                }
            }
            out[(i * n as i64 + j) as usize] = s;
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::rng::u;

    #[test]
    fn noyau_normalise_et_symetrique() {
        let k = kernel(50.0);
        let s: f64 = k.iter().sum();
        assert!((s - 1.0).abs() < 1e-12, "somme = {s}");
        let r = RADIUS;
        // coin (16,16) : d = 565 m > 400 m, donc nul
        assert_eq!(k[(2 * r) * KSIZE + 2 * r], 0.0);
        // (16,0) : d = 400 m exactement, inclus
        assert!(k[(2 * r) * KSIZE + r] > 0.0);
        assert_eq!(k[(2 * r) * KSIZE + r], k[r * KSIZE + 2 * r]);
        assert_eq!(k[0 * KSIZE + r], k[(2 * r) * KSIZE + r]);
        // le centre est le maximum
        assert!(k.iter().all(|&v| v <= k[r * KSIZE + r]));
    }

    #[test]
    fn fft_contre_convolution_directe() {
        let n = 20;
        let kern = kernel(50.0);
        let input: Vec<f64> = (0..n * n).map(|c| 100.0 * 5.0 * u(1, 0, c as u64, 0)).collect();
        let mut cv = Convolver::new(n, &kern).unwrap();
        let mut out = vec![0.0; n * n];
        cv.convolve(&input, &mut out);
        let refd = convolve_direct(&input, n, &kern);
        let maxref = refd.iter().fold(0.0f64, |m, v| m.max(v.abs()));
        let ecart = out.iter().zip(&refd).fold(0.0f64, |m, (a, b)| m.max((a - b).abs()));
        assert!(ecart / maxref < 1e-9, "écart relatif = {}", ecart / maxref);
    }

    #[test]
    fn impulsion_tombe_au_bon_endroit_et_bord_a_zero() {
        // Impulsion en (ligne 3, colonne 18) d'une grille 20 x 20, près du bord :
        // Q[3+di, 18+dj] = K[di,dj] ; rien ne se replie de l'autre côté (pas de tore).
        let n = 20;
        let kern = kernel(50.0);
        let mut input = vec![0.0; n * n];
        input[3 * n + 18] = 1.0;
        let mut cv = Convolver::new(n, &kern).unwrap();
        let mut out = vec![0.0; n * n];
        cv.convolve(&input, &mut out);
        let r = RADIUS as i64;
        for i in 0..n as i64 {
            for j in 0..n as i64 {
                let (di, dj) = (i - 3, j - 18);
                let attendu = if di.abs() <= r && dj.abs() <= r {
                    kern[((di + r) as usize) * KSIZE + (dj + r) as usize]
                } else {
                    0.0
                };
                assert!((out[(i * n as i64 + j) as usize] - attendu).abs() < 1e-14, "({i},{j})");
            }
        }
        // la masse perdue par le bord est > 0 : la somme est < 1
        assert!(out.iter().sum::<f64>() < 1.0);
    }

    #[test]
    fn taille_lisse() {
        assert_eq!(fast_size(516), 540);
        assert_eq!(fast_size(36), 36);
        assert!(fast_size(8016) >= 8016);
    }
}
