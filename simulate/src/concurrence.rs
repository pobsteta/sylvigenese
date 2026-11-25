//! Concurrence entre arbres : surface terrière du disque de 15 m (plan M3a, pas annuel, point 1).
//!
//! Étape du BRIEF codée ici : BRIEF §6, « Diamètre, mortalité, recrutement » : la concurrence que
//! voient les modèles de dynamique, telle que la spec §6 la fixe en simulation (tableau
//! « Variables à l'ajustement et en simulation ») :
//!
//! - `ba_plot` d'un arbre = Σ π (d130 / 200)² × 10 000 / (π × 15²) sur tous les arbres simulés
//!   dont le tronc est à **15 m au plus** (distance² ≤ 225 m², l'arbre lui-même compris), en m²/ha ;
//! - `bal` = la même somme sur les seuls arbres **strictement plus gros** (d130 plus grand) ;
//! - le disque de 15 m tient dans les 3 × 3 cellules autour de celle de l'arbre, car la cellule
//!   fait au moins 15 m de côté (25 m, ADR 0001 ; vérifié par [`GeometrieGrille::nouvelle`]) ;
//! - **ordre fixe** : les cellules voisines de la ligne nord à la ligne sud, d'ouest en est, et
//!   dans une cellule les arbres dans l'ordre de l'état (numéro croissant) ; chaque somme est
//!   faite par un seul fil, si bien que le résultat ne dépend pas du nombre de fils (plan, T1) ;
//! - **pas de correction de bord** : un disque qui déborde de la grille est compté tel quel, et le
//!   débordement est compté ([`Concurrence::au_bord`], `edge_disks` de `run.json`).
//!
//! Le décalage avec l'ajustement (placette IFN à cercles de 6, 9 et 15 m) est une limite connue,
//! écrite dans `rapport_dynamics.html` (spec §6).
//!
//! Coordonnées : x = est, y = nord, en m, EPSG:2154 ; `cell_id` = ligne × largeur + colonne, la
//! ligne 0 au nord (contrat `sim.cells`).
//!
//! Règle de lisibilité (CLAUDE.md) : structures concrètes, boucles simples, aucune macro maison
//! ni générique.

use std::f64::consts::PI;

use rayon::prelude::*;

use crate::erreurs::Erreur;
use crate::etat::EtatArbres;
use crate::memoire;

/// Rayon du disque de concurrence, en m (spec §6).
pub const RAYON_DISQUE_M: f64 = 15.0;

/// Aire du disque de concurrence, en m² (π × 15² ≈ 706,858).
pub fn aire_disque_m2() -> f64 {
    PI * RAYON_DISQUE_M * RAYON_DISQUE_M
}

/// Surface terrière d'un arbre, en m² : π (d130 / 200)², d130 en cm.
pub fn surface_terriere_m2(d130_cm: f64) -> f64 {
    let rayon_m = d130_cm / 200.0;
    PI * rayon_m * rayon_m
}

/// La géométrie de la grille de simulation (EPSG:2154), mêmes conventions que `grid.tif`.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct GeometrieGrille {
    /// Nombre de colonnes.
    pub largeur: usize,
    /// Nombre de lignes.
    pub hauteur: usize,
    /// x du bord ouest, en m.
    pub origine_x: f64,
    /// y du bord nord, en m.
    pub origine_y: f64,
    /// Côté d'une cellule, en m (25 m, ADR 0001).
    pub pas: f64,
}

impl GeometrieGrille {
    /// Construit la géométrie. Code 2 si la grille est vide, si une coordonnée n'est pas finie,
    /// ou si le côté est sous 15 m (le disque ne tiendrait plus dans les 3 × 3 cellules).
    pub fn nouvelle(
        largeur: usize,
        hauteur: usize,
        origine_x: f64,
        origine_y: f64,
        pas: f64,
    ) -> Result<GeometrieGrille, Erreur> {
        if largeur == 0 || hauteur == 0 {
            return Err(Erreur::entree_refusee(format!(
                "grille vide ({largeur} colonnes × {hauteur} lignes)"
            )));
        }
        if !origine_x.is_finite() || !origine_y.is_finite() || !pas.is_finite() {
            return Err(Erreur::entree_refusee(
                "grille : origine ou côté non fini".to_string(),
            ));
        }
        if pas < RAYON_DISQUE_M {
            return Err(Erreur::entree_refusee(format!(
                "grille : côté de cellule {pas} m sous le rayon du disque de concurrence (15 m) ; \
                 le voisinage 3 × 3 ne suffirait plus"
            )));
        }
        Ok(GeometrieGrille {
            largeur,
            hauteur,
            origine_x,
            origine_y,
            pas,
        })
    }

    /// Le nombre de cellules (largeur × hauteur).
    pub fn nombre_cellules(&self) -> usize {
        self.largeur * self.hauteur
    }

    /// L'aire d'une cellule, en ha (0,0625 ha pour 25 m).
    pub fn aire_cellule_ha(&self) -> f64 {
        self.pas * self.pas / 10_000.0
    }

    /// Ligne et colonne d'un `cell_id`.
    pub fn ligne_colonne(&self, cell_id: u64) -> (usize, usize) {
        let rang = cell_id as usize;
        (rang / self.largeur, rang % self.largeur)
    }

    /// Les bords d'une cellule : (x ouest, x est, y sud, y nord), en m.
    pub fn bornes(&self, cell_id: u64) -> (f64, f64, f64, f64) {
        let (ligne, colonne) = self.ligne_colonne(cell_id);
        let x_ouest = self.origine_x + colonne as f64 * self.pas;
        let y_nord = self.origine_y - ligne as f64 * self.pas;
        (x_ouest, x_ouest + self.pas, y_nord - self.pas, y_nord)
    }

    /// Vrai si le disque de 15 m centré en (x, y) sort de l'emprise de la grille.
    pub fn disque_deborde(&self, x: f64, y: f64) -> bool {
        let x_est = self.origine_x + self.largeur as f64 * self.pas;
        let y_sud = self.origine_y - self.hauteur as f64 * self.pas;
        x - RAYON_DISQUE_M < self.origine_x
            || x + RAYON_DISQUE_M > x_est
            || y - RAYON_DISQUE_M < y_sud
            || y + RAYON_DISQUE_M > self.origine_y
    }
}

/// Les arbres vivants rangés par cellule : ceux de la cellule c sont
/// `rangs[debut[c] .. debut[c + 1]]`, dans l'ordre de l'état (tri par dénombrement, stable).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IndexParCellule {
    pub debut: Vec<usize>,
    pub rangs: Vec<usize>,
}

impl IndexParCellule {
    /// Les rangs (dans l'état) des arbres vivants d'une cellule.
    pub fn arbres_de(&self, cell_id: usize) -> &[usize] {
        &self.rangs[self.debut[cell_id]..self.debut[cell_id + 1]]
    }
}

/// Range les arbres vivants de l'état par cellule. Code 1 si un arbre est dans une cellule hors
/// de la grille (l'affectation aux cellules, mission 036, l'aurait refusé) ; code 4 si la
/// mémoire manque.
pub fn indexer(etat: &EtatArbres, geometrie: &GeometrieGrille) -> Result<IndexParCellule, Erreur> {
    let nombre = geometrie.nombre_cellules();
    let mut debut: Vec<usize> = Vec::new();
    debut
        .try_reserve_exact(nombre + 1)
        .map_err(|_| memoire::erreur_allocation(nombre + 1, "index des cellules"))?;
    debut.resize(nombre + 1, 0);
    let mut vivants = 0;
    for rang in 0..etat.len() {
        if !etat.vivant[rang] {
            continue;
        }
        let cellule = etat.cellule[rang] as usize;
        if cellule >= nombre {
            return Err(Erreur::interne(format!(
                "arbre {} dans la cellule {cellule}, hors de la grille ({nombre} cellules)",
                etat.tree_id[rang]
            )));
        }
        debut[cellule + 1] += 1;
        vivants += 1;
    }
    for c in 0..nombre {
        debut[c + 1] += debut[c];
    }
    let mut rangs: Vec<usize> = Vec::new();
    rangs
        .try_reserve_exact(vivants)
        .map_err(|_| memoire::erreur_allocation(vivants, "index des arbres par cellule"))?;
    rangs.resize(vivants, 0);
    let mut prochain = debut.clone();
    for rang in 0..etat.len() {
        if !etat.vivant[rang] {
            continue;
        }
        let cellule = etat.cellule[rang] as usize;
        rangs[prochain[cellule]] = rang;
        prochain[cellule] += 1;
    }
    Ok(IndexParCellule { debut, rangs })
}

/// La concurrence vue par un arbre.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Concurrence {
    /// Surface terrière du disque de 15 m, l'arbre compris, en m²/ha.
    pub ba_plot: f64,
    /// Surface terrière des arbres strictement plus gros du disque, en m²/ha.
    pub bal: f64,
    /// Vrai si le disque sort de la grille (compté, sans correction).
    pub au_bord: bool,
}

/// La concurrence d'un arbre de l'état (rang `rang`), sur les arbres vivants de l'index.
pub fn concurrence_de(
    etat: &EtatArbres,
    geometrie: &GeometrieGrille,
    index: &IndexParCellule,
    rang: usize,
) -> Concurrence {
    let x = etat.x[rang];
    let y = etat.y[rang];
    let d130 = etat.d130[rang];
    let rayon2 = RAYON_DISQUE_M * RAYON_DISQUE_M;
    let par_hectare = 10_000.0 / aire_disque_m2();
    let (ligne, colonne) = geometrie.ligne_colonne(etat.cellule[rang]);
    let mut ba_plot = 0.0;
    let mut bal = 0.0;
    // Ordre fixe : ligne nord (ligne − 1) à ligne sud (ligne + 1), puis colonne ouest à est.
    for dl in 0..3 {
        if ligne + dl < 1 || ligne + dl - 1 >= geometrie.hauteur {
            continue;
        }
        let l = ligne + dl - 1;
        for dc in 0..3 {
            if colonne + dc < 1 || colonne + dc - 1 >= geometrie.largeur {
                continue;
            }
            let c = colonne + dc - 1;
            let voisine = l * geometrie.largeur + c;
            for autre in index.arbres_de(voisine) {
                let dx = etat.x[*autre] - x;
                let dy = etat.y[*autre] - y;
                if dx * dx + dy * dy <= rayon2 {
                    let g = surface_terriere_m2(etat.d130[*autre]) * par_hectare;
                    ba_plot += g;
                    if etat.d130[*autre] > d130 {
                        bal += g;
                    }
                }
            }
        }
    }
    Concurrence {
        ba_plot,
        bal,
        au_bord: geometrie.disque_deborde(x, y),
    }
}

/// La concurrence de chaque arbre de l'état (une valeur par rang ; un arbre mort reçoit des
/// zéros, il ne sera pas simulé). En parallèle sur les arbres ; chaque somme reste séquentielle.
pub fn calculer(
    etat: &EtatArbres,
    geometrie: &GeometrieGrille,
    index: &IndexParCellule,
) -> Vec<Concurrence> {
    (0..etat.len())
        .into_par_iter()
        .map(|rang| {
            if etat.vivant[rang] {
                concurrence_de(etat, geometrie, index, rang)
            } else {
                Concurrence {
                    ba_plot: 0.0,
                    bal: 0.0,
                    au_bord: false,
                }
            }
        })
        .collect()
}
