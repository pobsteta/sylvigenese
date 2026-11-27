//! Dispersion des graines par FFT réelle, avec zone tampon à bord absorbant (mission 062 ; plan
//! m5a, choix T2 et T3 ; spec §6 « règle |Q| » et §7 « zone tampon » ; ADR 0006, choix 7 et 8).
//!
//! Étape du BRIEF codée ici : BRIEF §7, point 1, « arrivée des graines » : les graines produites
//! par les semenciers d'une cellule se répartissent sur les cellules voisines selon un noyau de
//! dispersion propre à l'essence.
//!
//! # Le noyau (contrat `params/regeneration`)
//!
//! k(r) ∝ exp(−(r / a)^b), r en mètres **entre centres de cellules**, a = `kernel_scale_m`,
//! b = `kernel_shape` (b = 1 : exponentielle ; b = 2 : gaussienne). Le noyau est tronqué au
//! **disque** de rayon K cellules (K = `simulate.regeneration.kernel_truncation_cells`) : une
//! cellule dont le centre est à plus de K × 25 m du centre de la source ne reçoit rien. Il est
//! normalisé pour que la somme de ses poids sur le disque soit 1 (à 1e-12 près, testé) : les
//! graines qui partent d'une source arrivent toutes dans le disque. Aucune valeur n'est écrite
//! ici : a et b viennent de `params/regeneration.parquet` (sur une zone réelle, déduites des
//! distances à 50 % et 99 % de la classe de Lososová et al. 2023 de l'essence, décision de
//! l'orchestrateur du 26/11/2026).
//!
//! # Portée : K doit couvrir d99 (mission 080, décision de Pascal du 27/11/2026)
//!
//! La part des graines à moins de r du noyau non tronqué est P(2 / b, (r / a)^b) (gamma
//! incomplète régularisée) : c'est la relation qui déduit a et b des d50 et d99 de Lososová. La
//! distance à 99 % d99 se recalcule donc **exactement** de `kernel_scale_m` et `kernel_shape`
//! ([`distance_a_99_pourcent`]), sans nouveau terme au contrat. [`verifier_portee`] refuse
//! (code 2) un K tel que K × côté de cellule < d99, pour chaque essence présente : la
//! renormalisation ne déplace ainsi au plus que 1 % des graines.
//!
//! # Axes
//!
//! Le champ est rangé comme la grille : `rang = ligne × largeur + colonne`, ligne 0 au **nord**,
//! colonne 0 à l'**ouest** (EPSG:2154, x vers l'est). Le noyau est indexé par le décalage
//! (Δligne, Δcolonne) ; un test met une source au point connu (est 700 012,5 ; nord 6 500 987,5)
//! dans un cas asymétrique, pour qu'une transposition des axes se voie.
//!
//! # Zone tampon, bord absorbant (spec §7)
//!
//! La grille est entourée d'une couronne de K cellules : c'est la **zone tampon**. Le champ des
//! graines est posé dans un tableau plus grand (au moins largeur + 2K et hauteur + 2K, arrondis à
//! une taille dont les facteurs premiers sont 2, 3, 5 ou 7, pour la vitesse de la FFT) ; la
//! convolution circulaire y est donc une convolution linéaire. Les graines qui tombent dans la
//! couronne sont **perdues** (bord absorbant) : elles ne reviennent jamais dans la grille, et
//! aucun semis n'y est simulé. La couronne est source de graines seulement ; au niveau massif,
//! hors de `grid.tif`, il n'y a aucun arbre : elle n'en produit pas. Son nombre de cellules est
//! écrit dans `run.json` (`buffer_cells`).
//!
//! # FFT et identité entre fils
//!
//! Transformée réelle des lignes (`realfft`), puis transformée complexe des colonnes (`rustfft`),
//! produit par le spectre du noyau, puis les transformées inverses, et la division par le nombre
//! de valeurs. Chaque ligne ou colonne est transformée par **un seul fil**, avec le même plan :
//! le résultat ne dépend pas du nombre de fils (preuve par SHA-256 dans les tests d'identité).
//!
//! # Règle |Q| (spec §6, T3)
//!
//! Après la convolution, une valeur |Q| < `zero_threshold` × max|Q| (maximum pris sur la grille,
//! pour une essence et une année) est mise à zéro et comptée (`zeroed_values`), positives
//! comprises ; une valeur **négative au-delà du seuil** arrête le moteur (code 3) : ce ne serait
//! plus le bruit de la FFT (environ 1e-13 en relatif), mais une erreur.
//!
//! Règle de lisibilité (CLAUDE.md) : structures concrètes, boucles simples ; les seuls types
//! génériques sont ceux des crates `rustfft` et `realfft` (plans de FFT en `f64`).

use std::sync::Arc;

use rayon::prelude::*;
use realfft::{ComplexToReal, RealFftPlanner, RealToComplex};
use rustfft::num_complex::Complex;
use rustfft::{Fft, FftPlanner};

use crate::erreurs::Erreur;

/// Les poids d'un noyau tronqué au disque de rayon `demi_largeur` cellules, normalisés à 1.
///
/// `poids[(Δligne + K) × (2K + 1) + (Δcolonne + K)]`, Δ de −K à +K ; un poids hors du disque
/// vaut 0.
#[derive(Debug, Clone, PartialEq)]
pub struct Noyau {
    pub demi_largeur: usize,
    pub poids: Vec<f64>,
}

impl Noyau {
    /// Côté de la fenêtre carrée qui porte le disque : 2K + 1.
    pub fn cote(&self) -> usize {
        2 * self.demi_largeur + 1
    }

    /// Le poids du décalage (Δligne, Δcolonne), 0 hors de la fenêtre.
    pub fn poids_de(&self, delta_ligne: i64, delta_colonne: i64) -> f64 {
        let k = self.demi_largeur as i64;
        if delta_ligne.abs() > k || delta_colonne.abs() > k {
            return 0.0;
        }
        let rang = (delta_ligne + k) as usize * self.cote() + (delta_colonne + k) as usize;
        self.poids[rang]
    }

    /// La somme des poids, en ordre fixe (1 à 1e-12 près après normalisation).
    pub fn somme(&self) -> f64 {
        let mut somme = 0.0;
        for poids in &self.poids {
            somme += *poids;
        }
        somme
    }
}

/// Vrai si le décalage (Δligne, Δcolonne) est dans le disque de rayon K cellules (centres de
/// cellules à au plus K × côté l'un de l'autre). Calcul exact en entiers.
pub fn dans_le_disque(delta_ligne: i64, delta_colonne: i64, demi_largeur: usize) -> bool {
    let k = demi_largeur as i64;
    delta_ligne * delta_ligne + delta_colonne * delta_colonne <= k * k
}

/// Le noyau exponentielle-puissance k(r) ∝ exp(−(r / echelle_m)^forme), r = pas × distance entre
/// centres, tronqué au disque de rayon `demi_largeur` cellules et normalisé.
///
/// Code 2 si l'échelle ou la forme n'est pas finie et strictement positive, si le pas n'est pas
/// fini et positif, si K vaut 0, ou si tous les poids sont nuls (échelle trop petite devant le pas
/// pour que même la cellule source garde un poids : impossible, exp(0) = 1, mais le contrôle reste).
pub fn noyau_exponentiel_puissance(
    echelle_m: f64,
    forme: f64,
    pas_m: f64,
    demi_largeur: usize,
) -> Result<Noyau, Erreur> {
    if !(echelle_m.is_finite() && echelle_m > 0.0) {
        return Err(Erreur::entree_refusee(format!(
            "noyau de dispersion : kernel_scale_m = {echelle_m} ; il doit être fini et strictement positif"
        )));
    }
    if !(forme.is_finite() && forme > 0.0) {
        return Err(Erreur::entree_refusee(format!(
            "noyau de dispersion : kernel_shape = {forme} ; il doit être fini et strictement positif"
        )));
    }
    if !(pas_m.is_finite() && pas_m > 0.0) {
        return Err(Erreur::entree_refusee(format!(
            "noyau de dispersion : côté de cellule {pas_m} m invalide"
        )));
    }
    if demi_largeur == 0 {
        return Err(Erreur::entree_refusee(
            "noyau de dispersion : kernel_truncation_cells doit valoir au moins 1".to_string(),
        ));
    }
    let k = demi_largeur as i64;
    let cote = 2 * demi_largeur + 1;
    let mut poids: Vec<f64> = Vec::with_capacity(cote * cote);
    for delta_ligne in -k..=k {
        for delta_colonne in -k..=k {
            if !dans_le_disque(delta_ligne, delta_colonne, demi_largeur) {
                poids.push(0.0);
                continue;
            }
            let distance = ((delta_ligne * delta_ligne + delta_colonne * delta_colonne) as f64).sqrt();
            let r = pas_m * distance;
            poids.push((-(r / echelle_m).powf(forme)).exp());
        }
    }
    let mut somme = 0.0;
    for valeur in &poids {
        somme += *valeur;
    }
    if !(somme.is_finite() && somme > 0.0) {
        return Err(Erreur::entree_refusee(format!(
            "noyau de dispersion (échelle {echelle_m} m, forme {forme}) : somme des poids {somme}, impossible à normaliser"
        )));
    }
    for valeur in poids.iter_mut() {
        *valeur /= somme;
    }
    Ok(Noyau {
        demi_largeur,
        poids,
    })
}

// ------------------------------------------------------------------------------------------
// Portée du noyau : la distance à 99 % de dispersion (mission 080, décision de Pascal du 27/11/2026)

/// Part des graines que le noyau exponentielle-puissance k(r) ∝ exp(−(r / a)^b), en deux
/// dimensions et **non tronqué**, fait tomber à moins de `rayon_m` de la source :
/// P(2 / b, (r / a)^b), fonction gamma incomplète régularisée (contrat `params/regeneration`,
/// ADR 0006 choix 7). Preuve : la masse à moins de r est ∫ 2π r exp(−(r/a)^b) dr ; avec
/// u = (r/a)^b, r dr = (a² / b) u^(2/b − 1) du, soit la loi gamma de forme 2 / b. C'est la
/// relation même qui a servi à déduire a et b des distances d50 et d99 de Lososová et al. 2023.
pub fn part_dans_le_rayon(echelle_m: f64, forme: f64, rayon_m: f64) -> f64 {
    if rayon_m <= 0.0 {
        return 0.0;
    }
    gamma_incomplete_regularisee(2.0 / forme, (rayon_m / echelle_m).powf(forme))
}

/// La distance à 99 % de dispersion d99 (m) : le rayon où [`part_dans_le_rayon`] vaut 0,99.
/// Calcul exact (dichotomie à la précision des f64), aucune valeur tirée d'ailleurs : elle ne
/// dépend que de `kernel_scale_m` et `kernel_shape`.
pub fn distance_a_99_pourcent(echelle_m: f64, forme: f64) -> f64 {
    let mut bas = 0.0_f64;
    let mut haut = echelle_m;
    // Le rayon cherché n'est pas borné d'avance : on double jusqu'à passer 99 %.
    let mut doublements = 0;
    while part_dans_le_rayon(echelle_m, forme, haut) < 0.99 && doublements < 200 {
        bas = haut;
        haut *= 2.0;
        doublements += 1;
    }
    for _ in 0..200 {
        let milieu = 0.5 * (bas + haut);
        if part_dans_le_rayon(echelle_m, forme, milieu) < 0.99 {
            bas = milieu;
        } else {
            haut = milieu;
        }
    }
    haut
}

/// Refuse (code 2) un K qui ne couvre pas la distance à 99 % de l'essence : la renormalisation
/// du noyau tronqué ne déplace alors au plus que 1 % des graines. Le message nomme l'essence,
/// son d99 et le K demandé. Passe aux deux niveaux (massif et SER), par `Regeneration::preparer`.
pub fn verifier_portee(
    espece: &str,
    echelle_m: f64,
    forme: f64,
    pas_m: f64,
    demi_largeur: usize,
) -> Result<(), Erreur> {
    let d99 = distance_a_99_pourcent(echelle_m, forme);
    let portee_m = demi_largeur as f64 * pas_m;
    if portee_m >= d99 {
        return Ok(());
    }
    let k_minimal = (d99 / pas_m).ceil() as u64;
    Err(Erreur::entree_refusee(format!(
        "essence {espece} : simulate.regeneration.kernel_truncation_cells = {demi_largeur} \
         ({portee_m} m) ne couvre pas la distance à 99 % de dispersion de l'essence, d99 = {d99:.1} m \
         (kernel_scale_m = {echelle_m}, kernel_shape = {forme}) ; il faut au moins {k_minimal} cellules \
         de {pas_m} m"
    )))
}

/// ln Γ(x) pour x > 0, approximation de Lanczos (g = 7, 9 termes ; Numerical Recipes, §6.1),
/// précise à environ 1e-15 en relatif.
fn ln_gamma(x: f64) -> f64 {
    const COEFFICIENTS: [f64; 9] = [
        0.999_999_999_999_809_9,
        676.520_368_121_885_1,
        -1_259.139_216_722_402_8,
        771.323_428_777_653_1,
        -176.615_029_162_140_6,
        12.507_343_278_686_905,
        -0.138_571_095_265_720_12,
        9.984_369_578_019_572e-6,
        1.505_632_735_149_311_6e-7,
    ];
    if x < 0.5 {
        // Formule des compléments : Γ(x) Γ(1 − x) = π / sin(π x).
        let pi = std::f64::consts::PI;
        return (pi / (pi * x).sin()).ln() - ln_gamma(1.0 - x);
    }
    let x = x - 1.0;
    let mut somme = COEFFICIENTS[0];
    for (i, c) in COEFFICIENTS.iter().enumerate().skip(1) {
        somme += c / (x + i as f64);
    }
    let t = x + 7.5;
    0.5 * (2.0 * std::f64::consts::PI).ln() + (x + 0.5) * t.ln() - t + somme.ln()
}

/// Fonction gamma incomplète inférieure régularisée P(s, x), s > 0, x ≥ 0 : série pour
/// x < s + 1, fraction continue (Lentz) sinon (Numerical Recipes, §6.2).
fn gamma_incomplete_regularisee(s: f64, x: f64) -> f64 {
    if x <= 0.0 {
        return 0.0;
    }
    let ln_devant = s * x.ln() - x - ln_gamma(s);
    if x < s + 1.0 {
        let mut terme = 1.0 / s;
        let mut somme = terme;
        let mut a = s;
        for _ in 0..10_000 {
            a += 1.0;
            terme *= x / a;
            somme += terme;
            if terme.abs() < somme.abs() * 1e-16 {
                break;
            }
        }
        (somme * ln_devant.exp()).min(1.0)
    } else {
        let minuscule = 1e-300;
        let mut b = x + 1.0 - s;
        let mut c = 1.0 / minuscule;
        let mut d = 1.0 / b;
        let mut h = d;
        for i in 1..10_000 {
            let an = -(i as f64) * (i as f64 - s);
            b += 2.0;
            d = an * d + b;
            if d.abs() < minuscule {
                d = minuscule;
            }
            c = b + an / c;
            if c.abs() < minuscule {
                c = minuscule;
            }
            d = 1.0 / d;
            let delta = d * c;
            h *= delta;
            if (delta - 1.0).abs() < 1e-16 {
                break;
            }
        }
        (1.0 - ln_devant.exp() * h).clamp(0.0, 1.0)
    }
}

/// Le plus petit entier ≥ `n` dont les seuls facteurs premiers sont 2, 3, 5 et 7 (taille rapide
/// pour la FFT). Réglage de calcul, sans effet sur le résultat au-delà de l'arrondi.
pub fn taille_rapide(n: usize) -> usize {
    let mut candidat = n.max(1);
    loop {
        let mut reste = candidat;
        for facteur in [2, 3, 5, 7] {
            while reste % facteur == 0 {
                reste /= facteur;
            }
        }
        if reste == 1 {
            return candidat;
        }
        candidat += 1;
    }
}

/// Le nombre de cellules de la zone tampon : la couronne de K cellules autour de la grille.
pub fn cellules_tampon(largeur: usize, hauteur: usize, demi_largeur: usize) -> u64 {
    let exterieur = (largeur + 2 * demi_largeur) as u64 * (hauteur + 2 * demi_largeur) as u64;
    exterieur - largeur as u64 * hauteur as u64
}

/// Les plans de FFT d'une grille (une fois par exécution) et la taille du tableau de calcul.
#[derive(Clone)]
pub struct PlanDispersion {
    /// Colonnes et lignes de la grille de simulation.
    pub largeur: usize,
    pub hauteur: usize,
    /// Demi-largeur K du noyau tronqué (largeur de la zone tampon).
    pub demi_largeur: usize,
    /// Colonnes et lignes du tableau de calcul (zone tampon et rembourrage compris).
    pub colonnes_fft: usize,
    pub lignes_fft: usize,
    lignes_avant: Arc<dyn RealToComplex<f64>>,
    lignes_arriere: Arc<dyn ComplexToReal<f64>>,
    colonnes_avant: Arc<dyn Fft<f64>>,
    colonnes_arriere: Arc<dyn Fft<f64>>,
}

impl std::fmt::Debug for PlanDispersion {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "PlanDispersion {{ grille {} × {}, K = {}, tableau {} × {} }}",
            self.largeur, self.hauteur, self.demi_largeur, self.colonnes_fft, self.lignes_fft
        )
    }
}

/// Le spectre d'un noyau sur le tableau de calcul d'un plan (rangé colonne par colonne :
/// `spectre[colonne_spectrale × lignes_fft + ligne]`).
#[derive(Debug, Clone, PartialEq)]
pub struct SpectreNoyau {
    pub valeurs: Vec<Complex<f64>>,
}

impl PlanDispersion {
    /// Prépare les plans pour une grille de `largeur` × `hauteur` cellules et un noyau de
    /// demi-largeur K. Code 2 si la grille est vide ou K nul.
    pub fn nouveau(largeur: usize, hauteur: usize, demi_largeur: usize) -> Result<PlanDispersion, Erreur> {
        if largeur == 0 || hauteur == 0 || demi_largeur == 0 {
            return Err(Erreur::entree_refusee(format!(
                "dispersion : grille {largeur} × {hauteur} ou demi-largeur du noyau {demi_largeur} nulle"
            )));
        }
        let colonnes_fft = taille_rapide(largeur + 2 * demi_largeur);
        let lignes_fft = taille_rapide(hauteur + 2 * demi_largeur);
        let mut planificateur_reel = RealFftPlanner::<f64>::new();
        let mut planificateur = FftPlanner::<f64>::new();
        Ok(PlanDispersion {
            largeur,
            hauteur,
            demi_largeur,
            colonnes_fft,
            lignes_fft,
            lignes_avant: planificateur_reel.plan_fft_forward(colonnes_fft),
            lignes_arriere: planificateur_reel.plan_fft_inverse(colonnes_fft),
            colonnes_avant: planificateur.plan_fft_forward(lignes_fft),
            colonnes_arriere: planificateur.plan_fft_inverse(lignes_fft),
        })
    }

    /// Nombre de colonnes spectrales d'une ligne transformée : colonnes_fft / 2 + 1.
    pub fn colonnes_spectrales(&self) -> usize {
        self.colonnes_fft / 2 + 1
    }

    /// Octets des tableaux de travail d'une convolution (pour l'estimation de mémoire) : le
    /// tableau réel, deux tableaux complexes (lignes transformées et colonnes), un spectre de
    /// noyau par essence en plus (compté par l'appelant).
    pub fn octets_de_travail(&self) -> u64 {
        let reels = (self.colonnes_fft * self.lignes_fft) as u64 * 8;
        let complexes = (self.colonnes_spectrales() * self.lignes_fft) as u64 * 16;
        reels + 2 * complexes
    }

    /// Octets d'un spectre de noyau.
    pub fn octets_spectre(&self) -> u64 {
        (self.colonnes_spectrales() * self.lignes_fft) as u64 * 16
    }

    /// Le spectre d'un noyau : le noyau est posé centré sur la case (0, 0) du tableau de calcul,
    /// les décalages négatifs repliés à la fin (convolution circulaire). Code 2 si le noyau n'a
    /// pas la demi-largeur du plan.
    pub fn spectre(&self, noyau: &Noyau) -> Result<SpectreNoyau, Erreur> {
        if noyau.demi_largeur != self.demi_largeur {
            return Err(Erreur::interne(format!(
                "noyau de demi-largeur {} pour un plan de demi-largeur {}",
                noyau.demi_largeur, self.demi_largeur
            )));
        }
        let k = self.demi_largeur as i64;
        let mut tableau = vec![0.0_f64; self.colonnes_fft * self.lignes_fft];
        for delta_ligne in -k..=k {
            for delta_colonne in -k..=k {
                let ligne = delta_ligne.rem_euclid(self.lignes_fft as i64) as usize;
                let colonne = delta_colonne.rem_euclid(self.colonnes_fft as i64) as usize;
                tableau[ligne * self.colonnes_fft + colonne] = noyau.poids_de(delta_ligne, delta_colonne);
            }
        }
        Ok(SpectreNoyau {
            valeurs: self.transformer(tableau)?,
        })
    }

    /// Transformée 2D d'un tableau réel (`lignes_fft` × `colonnes_fft`, rangé ligne par ligne) ;
    /// rend le spectre rangé colonne spectrale par colonne spectrale.
    fn transformer(&self, mut tableau: Vec<f64>) -> Result<Vec<Complex<f64>>, Erreur> {
        let cs = self.colonnes_spectrales();
        let nl = self.lignes_fft;
        // 1. Lignes : FFT réelle, une ligne par tâche.
        let mut lignes_transformees = vec![Complex::new(0.0, 0.0); cs * nl];
        let plan = &self.lignes_avant;
        let resultats: Vec<Result<(), Erreur>> = tableau
            .par_chunks_mut(self.colonnes_fft)
            .zip(lignes_transformees.par_chunks_mut(cs))
            .map(|(entree, sortie)| {
                plan.process(entree, sortie)
                    .map_err(|e| Erreur::interne(format!("FFT des lignes : {e}")))
            })
            .collect();
        for resultat in resultats {
            resultat?;
        }
        drop(tableau);
        // 2. Colonnes : transposition, puis FFT complexe, une colonne par tâche.
        let mut colonnes = transposer(&lignes_transformees, nl, cs);
        drop(lignes_transformees);
        let plan_colonnes = &self.colonnes_avant;
        colonnes.par_chunks_mut(nl).for_each(|colonne| plan_colonnes.process(colonne));
        Ok(colonnes)
    }

    /// Convolue un champ de la grille (`hauteur` × `largeur`, ligne 0 au nord) par un noyau dont
    /// on donne le spectre ; rend le champ reçu sur la grille seule (ce qui tombe dans la zone
    /// tampon est perdu : bord absorbant). Code 1 si les longueurs ne vont pas.
    pub fn convoluer(&self, champ: &[f64], spectre: &SpectreNoyau) -> Result<Vec<f64>, Erreur> {
        let n = self.largeur * self.hauteur;
        if champ.len() != n {
            return Err(Erreur::interne(format!(
                "dispersion : champ de {} valeurs pour une grille de {n} cellules",
                champ.len()
            )));
        }
        let cs = self.colonnes_spectrales();
        let nl = self.lignes_fft;
        if spectre.valeurs.len() != cs * nl {
            return Err(Erreur::interne(
                "dispersion : spectre du noyau d'une autre taille que le plan".to_string(),
            ));
        }
        // La grille est posée à partir de la case (0, 0) : la zone tampon et le rembourrage sont
        // à l'est et au sud, et, par repli circulaire, à l'ouest et au nord (au moins K cases de
        // chaque côté, puisque colonnes_fft ≥ largeur + 2K et lignes_fft ≥ hauteur + 2K).
        let mut tableau = vec![0.0_f64; self.colonnes_fft * nl];
        for ligne in 0..self.hauteur {
            let debut = ligne * self.colonnes_fft;
            tableau[debut..debut + self.largeur]
                .copy_from_slice(&champ[ligne * self.largeur..(ligne + 1) * self.largeur]);
        }
        let mut colonnes = self.transformer(tableau)?;
        // 3. Produit par le spectre du noyau, puis FFT inverse des colonnes.
        colonnes
            .par_chunks_mut(nl)
            .zip(spectre.valeurs.par_chunks(nl))
            .for_each(|(colonne, noyau)| {
                for (valeur, poids) in colonne.iter_mut().zip(noyau.iter()) {
                    *valeur *= *poids;
                }
            });
        let plan_colonnes = &self.colonnes_arriere;
        colonnes.par_chunks_mut(nl).for_each(|colonne| plan_colonnes.process(colonne));
        // 4. Retour aux lignes, FFT réelle inverse ; la partie imaginaire des fréquences nulle et
        // de Nyquist est nulle pour un champ réel : on l'y remet (bruit d'arrondi seulement).
        let mut lignes_transformees = transposer(&colonnes, cs, nl);
        drop(colonnes);
        let pair = self.colonnes_fft % 2 == 0;
        let mut sortie = vec![0.0_f64; self.colonnes_fft * nl];
        let plan = &self.lignes_arriere;
        let resultats: Vec<Result<(), Erreur>> = lignes_transformees
            .par_chunks_mut(cs)
            .zip(sortie.par_chunks_mut(self.colonnes_fft))
            .map(|(entree, ligne)| {
                entree[0].im = 0.0;
                if pair {
                    entree[cs - 1].im = 0.0;
                }
                plan.process(entree, ligne)
                    .map_err(|e| Erreur::interne(format!("FFT inverse des lignes : {e}")))
            })
            .collect();
        for resultat in resultats {
            resultat?;
        }
        let echelle = 1.0 / (self.colonnes_fft * nl) as f64;
        let mut recu = Vec::with_capacity(n);
        for ligne in 0..self.hauteur {
            let debut = ligne * self.colonnes_fft;
            for colonne in 0..self.largeur {
                recu.push(sortie[debut + colonne] * echelle);
            }
        }
        Ok(recu)
    }
}

/// Transpose un tableau complexe de `lignes` × `colonnes` (rangé ligne par ligne) en
/// `colonnes` × `lignes`. Copie simple, sans calcul : identique quel que soit le nombre de fils.
fn transposer(entree: &[Complex<f64>], lignes: usize, colonnes: usize) -> Vec<Complex<f64>> {
    let mut sortie = vec![Complex::new(0.0, 0.0); lignes * colonnes];
    sortie
        .par_chunks_mut(lignes)
        .enumerate()
        .for_each(|(colonne, destination)| {
            for ligne in 0..lignes {
                destination[ligne] = entree[ligne * colonnes + colonne];
            }
        });
    sortie
}

/// La convolution directe (oracle des tests, et petites grilles) : mêmes conventions que
/// [`PlanDispersion::convoluer`], ce qui sort de la grille est perdu.
pub fn convoluer_directement(champ: &[f64], largeur: usize, hauteur: usize, noyau: &Noyau) -> Vec<f64> {
    let k = noyau.demi_largeur as i64;
    let mut recu = vec![0.0_f64; largeur * hauteur];
    for ligne in 0..hauteur as i64 {
        for colonne in 0..largeur as i64 {
            let source = champ[(ligne * largeur as i64 + colonne) as usize];
            if source == 0.0 {
                continue;
            }
            for delta_ligne in -k..=k {
                let l = ligne + delta_ligne;
                if l < 0 || l >= hauteur as i64 {
                    continue;
                }
                for delta_colonne in -k..=k {
                    let c = colonne + delta_colonne;
                    if c < 0 || c >= largeur as i64 {
                        continue;
                    }
                    recu[(l * largeur as i64 + c) as usize] += source * noyau.poids_de(delta_ligne, delta_colonne);
                }
            }
        }
    }
    recu
}

/// Règle |Q| (spec §6, T3) avec le seuil relatif de `config.yml` : met à zéro les valeurs
/// |Q| < seuil × max|Q| (positives comprises) et rend leur nombre. Code 3 si une valeur n'est pas
/// finie, ou si une valeur est **négative au-delà du seuil** (elle n'est plus du bruit de la FFT).
/// Le maximum est cherché en ordre fixe.
pub fn mettre_a_zero(champ: &mut [f64], seuil_relatif: f64, quoi: &str) -> Result<u64, Erreur> {
    let mut maximum: f64 = 0.0;
    for (rang, valeur) in champ.iter().enumerate() {
        if !valeur.is_finite() {
            return Err(Erreur::controle_echoue(format!(
                "règle |Q| ({quoi}) : valeur non finie ({valeur}) à la cellule {rang}"
            )));
        }
        if valeur.abs() > maximum {
            maximum = valeur.abs();
        }
    }
    let seuil = seuil_relatif * maximum;
    let mut mises_a_zero = 0;
    for (rang, valeur) in champ.iter_mut().enumerate() {
        if *valeur == 0.0 {
            continue;
        }
        if valeur.abs() < seuil {
            *valeur = 0.0;
            mises_a_zero += 1;
        } else if *valeur < 0.0 {
            return Err(Erreur::controle_echoue(format!(
                "règle |Q| ({quoi}) : valeur négative {valeur} à la cellule {rang}, au-delà du seuil \
                 {seuil_relatif} × max|Q| = {seuil} : ce n'est pas du bruit de calcul"
            )));
        }
    }
    Ok(mises_a_zero)
}
