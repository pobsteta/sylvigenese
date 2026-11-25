//! Grille de simulation à 25 m, définie par `grid.tif` (spec §7 ; ADR 0001).
//!
//! Étape du BRIEF codée ici : BRIEF §4 (une seule grille de simulation, EPSG:2154) et §6
//! (placer chaque arbre dans sa cellule).
//!
//! Axes : x = est, y = nord, EPSG:2154. Le coin nord-ouest de la grille est
//! (`origine_x` ; `origine_y`) ; la ligne 0 est au nord, la colonne 0 à l'ouest.
//! Pour un point (x, y) :
//!
//! - `ligne = floor((origine_y − y) / pas)` ;
//! - `colonne = floor((x − origine_x) / pas)` ;
//! - `cell_id = ligne × largeur + colonne` (contrat `sim/cells`).
//!
//! Le bord sud et le bord est sont exclus : un point sur la limite sud ou est est hors grille.
//! Un point hors grille est refusé (code 2), jamais ramené dans la grille.
//!
//! Règle de lisibilité (CLAUDE.md) : une structure concrète, aucune macro, aucun générique.

use crate::erreurs::Erreur;
use crate::geotiff::Raster;

/// Écart toléré (m) entre deux géoréférencements pour les dire alignés.
const TOLERANCE_ALIGNEMENT_M: f64 = 1e-6;

/// La grille de simulation : emprise, pas et cellules retenues (celles où `grid.tif` a une valeur).
#[derive(Debug, Clone, PartialEq)]
pub struct Grille {
    pub largeur: usize,
    pub hauteur: usize,
    /// x du bord ouest, en m.
    pub origine_x: f64,
    /// y du bord nord, en m.
    pub origine_y: f64,
    /// Côté d'une cellule, en m.
    pub pas: f64,
    /// Une valeur par cellule (ordre de `cell_id`) : vrai si `grid.tif` y a une valeur.
    pub valide: Vec<bool>,
}

impl Grille {
    /// Construit la grille depuis le raster `grid.tif` (une bande).
    ///
    /// Code 2 si le raster n'a pas une seule bande, si son pixel n'est pas carré, ou s'il ne
    /// vaut pas `resolution_m` (la résolution de `config.yml`).
    pub fn depuis_raster(
        raster: &Raster,
        nom: &str,
        resolution_m: f64,
    ) -> Result<Grille, Erreur> {
        if raster.bandes.len() != 1 {
            return Err(Erreur::entree_refusee(format!(
                "{nom} : {} bandes ; la grille n'en a qu'une",
                raster.bandes.len()
            )));
        }
        if raster.pixel_x != raster.pixel_y {
            return Err(Erreur::entree_refusee(format!(
                "{nom} : pixel non carré ({} × {} m)",
                raster.pixel_x, raster.pixel_y
            )));
        }
        if (raster.pixel_x - resolution_m).abs() > TOLERANCE_ALIGNEMENT_M {
            return Err(Erreur::entree_refusee(format!(
                "{nom} : pixel de {} m, mais config.yml demande grid.resolution_m = {resolution_m}",
                raster.pixel_x
            )));
        }
        let mut valide: Vec<bool> = Vec::new();
        valide.try_reserve_exact(raster.bandes[0].len()).map_err(|_| {
            Erreur::memoire_insuffisante(format!("{nom} : mémoire insuffisante pour la grille"))
        })?;
        for valeur in &raster.bandes[0] {
            valide.push(!raster.est_nodata(*valeur));
        }
        Ok(Grille {
            largeur: raster.largeur,
            hauteur: raster.hauteur,
            origine_x: raster.origine_x,
            origine_y: raster.origine_y,
            pas: raster.pixel_x,
            valide,
        })
    }

    /// Le nombre de cellules de la grille (largeur × hauteur), valides ou non.
    pub fn nombre_cellules(&self) -> usize {
        self.largeur * self.hauteur
    }

    /// Le nombre de cellules où `grid.tif` a une valeur.
    pub fn nombre_valides(&self) -> usize {
        self.valide.iter().filter(|v| **v).count()
    }

    /// x du bord est, en m.
    pub fn x_max(&self) -> f64 {
        self.origine_x + self.largeur as f64 * self.pas
    }

    /// y du bord sud, en m.
    pub fn y_min(&self) -> f64 {
        self.origine_y - self.hauteur as f64 * self.pas
    }

    /// `cell_id` d'une ligne et d'une colonne (rang ligne × largeur + colonne).
    pub fn cell_id(&self, ligne: usize, colonne: usize) -> u64 {
        (ligne * self.largeur + colonne) as u64
    }

    /// Ligne et colonne d'un `cell_id` (l'inverse de [`Grille::cell_id`]).
    pub fn ligne_colonne(&self, cell_id: u64) -> (usize, usize) {
        let rang = cell_id as usize;
        (rang / self.largeur, rang % self.largeur)
    }

    /// Vrai si la cellule existe et a une valeur dans `grid.tif`.
    pub fn est_valide(&self, cell_id: u64) -> bool {
        match self.valide.get(cell_id as usize) {
            Some(v) => *v,
            None => false,
        }
    }

    /// Les bords d'une cellule : (x ouest, x est, y sud, y nord), en m.
    pub fn bornes(&self, cell_id: u64) -> (f64, f64, f64, f64) {
        let (ligne, colonne) = self.ligne_colonne(cell_id);
        let x_ouest = self.origine_x + colonne as f64 * self.pas;
        let y_nord = self.origine_y - ligne as f64 * self.pas;
        (x_ouest, x_ouest + self.pas, y_nord - self.pas, y_nord)
    }

    /// Le `cell_id` de la cellule qui contient le point (x est ; y nord), EPSG:2154.
    ///
    /// Code 2 si une coordonnée n'est pas finie, si le point est hors de l'emprise (bords sud et
    /// est exclus), ou si la cellule n'a pas de valeur dans `grid.tif`.
    pub fn cellule_de(&self, x: f64, y: f64) -> Result<u64, Erreur> {
        if !x.is_finite() || !y.is_finite() {
            return Err(Erreur::entree_refusee(format!(
                "point (x est {x} ; y nord {y}) : coordonnée non finie"
            )));
        }
        let colonne_reelle = ((x - self.origine_x) / self.pas).floor();
        let ligne_reelle = ((self.origine_y - y) / self.pas).floor();
        let dedans = colonne_reelle >= 0.0
            && ligne_reelle >= 0.0
            && colonne_reelle < self.largeur as f64
            && ligne_reelle < self.hauteur as f64;
        if !dedans {
            return Err(Erreur::entree_refusee(format!(
                "point (x est {x} ; y nord {y}) hors de la grille (x de {} à {} exclu ; y de {} exclu à {})",
                self.origine_x,
                self.x_max(),
                self.y_min(),
                self.origine_y
            )));
        }
        let cell_id = self.cell_id(ligne_reelle as usize, colonne_reelle as usize);
        if !self.est_valide(cell_id) {
            return Err(Erreur::entree_refusee(format!(
                "point (x est {x} ; y nord {y}) : la cellule {cell_id} n'a pas de valeur dans grid.tif (hors zone simulée)"
            )));
        }
        Ok(cell_id)
    }

    /// Vérifie qu'un raster est aligné sur la grille : mêmes largeur, hauteur, coin nord-ouest et
    /// pixel (à 1e-6 m près). Code 2 sinon, avec le nom du fichier et la première différence.
    pub fn verifier_alignement(&self, raster: &Raster, nom: &str) -> Result<(), Erreur> {
        if raster.largeur != self.largeur || raster.hauteur != self.hauteur {
            return Err(Erreur::entree_refusee(format!(
                "{nom} : {} colonnes × {} lignes, mais grid.tif en a {} × {} (raster non aligné)",
                raster.largeur, raster.hauteur, self.largeur, self.hauteur
            )));
        }
        let ecarts = [
            ("x du coin nord-ouest", raster.origine_x, self.origine_x),
            ("y du coin nord-ouest", raster.origine_y, self.origine_y),
            ("taille du pixel en x", raster.pixel_x, self.pas),
            ("taille du pixel en y", raster.pixel_y, self.pas),
        ];
        for (quoi, lu, attendu) in ecarts {
            if (lu - attendu).abs() > TOLERANCE_ALIGNEMENT_M {
                return Err(Erreur::entree_refusee(format!(
                    "{nom} : {quoi} vaut {lu}, mais grid.tif a {attendu} (raster non aligné)"
                )));
            }
        }
        Ok(())
    }
}
