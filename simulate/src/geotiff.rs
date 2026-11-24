//! Lecteur GeoTIFF sans GDAL (spec §9, ADR 0002, mission 015).
//!
//! Étape du BRIEF codée ici : la lecture des rasters échangés entre modules (BRIEF §4,
//! « les modules ne se parlent que par fichiers »). Le profil fait foi dans
//! `contracts/geotiff_profile.json` ; ce module en reprend les règles en constantes, et un test
//! vérifie qu'elles restent identiques à celles du fichier.
//!
//! Le profil accepté (variante `grille`) :
//! - TIFF classique (BigTIFF refusé), en-tête II ou MM ;
//! - tuiles de 256 × 256, entrelacement PLANARCONFIG=2 ;
//! - compression aucune ou Deflate (codes 1, 8 et 32946), PREDICTOR 1 ou 2 ;
//! - valeurs Float32 ou UInt16 ;
//! - EPSG:2154 dans les GeoKeys, nodata dans la balise 42113.
//!
//! Tout le reste est **refusé avec le code de sortie 2** et un message en français : on ne
//! devine jamais. Une allocation qui échoue donne le code 4 (`try_reserve`, spec §6).
//! Seul le premier IFD (l'image pleine résolution) est lu ; les aperçus des COG sont ignorés.
//!
//! Ce module ne vérifie pas l'alignement sur `grid.tif` : c'est l'affaire de l'appelant,
//! avec l'origine et la maille rendues dans [`Raster`].
//!
//! Règle de lisibilité (CLAUDE.md) : pas de macros maison ni de génériques avancés.

use std::collections::HashMap;
use std::fmt;
use std::io::Read;
use std::path::Path;

use flate2::read::ZlibDecoder;

/// Code de sortie : entrée refusée (spec §6).
pub const SORTIE_REFUSEE: i32 = 2;
/// Code de sortie : mémoire insuffisante (spec §6).
pub const SORTIE_MEMOIRE: i32 = 4;

// Règles du profil (contracts/geotiff_profile.json, « allowed »).
pub const TUILE: usize = 256;
pub const EPSG_ATTENDU: u64 = 2154;
pub const COMPRESSION_AUCUNE: u64 = 1;
pub const COMPRESSIONS_DEFLATE: [u64; 2] = [8, 32946];
pub const PREDICTEURS: [u64; 2] = [1, 2];
pub const ENTRELACEMENT_ATTENDU: u64 = 2;

// Numéros de balises (TIFF 6.0, GeoTIFF 1.1).
const T_LARGEUR: u16 = 256;
const T_HAUTEUR: u16 = 257;
const T_BITS: u16 = 258;
const T_COMPRESSION: u16 = 259;
const T_BANDES_LIGNES: u16 = 273;
const T_ECHANTILLONS: u16 = 277;
const T_ENTRELACEMENT: u16 = 284;
const T_PREDICTEUR: u16 = 317;
const T_TUILE_LARGEUR: u16 = 322;
const T_TUILE_HAUTEUR: u16 = 323;
const T_TUILE_DEBUTS: u16 = 324;
const T_TUILE_TAILLES: u16 = 325;
const T_FORMAT: u16 = 339;
const T_ECHELLE: u16 = 33550;
const T_POINT_LIE: u16 = 33922;
const T_TRANSFORMATION: u16 = 34264;
const T_GEOKEYS: u16 = 34735;
const T_NODATA: u16 = 42113;

const GEOKEY_TYPE_RASTER: u64 = 1025;
const GEOKEY_GEOGRAPHIQUE: u64 = 2048;
const GEOKEY_PROJETE: u64 = 3072;

/// Erreur de lecture : un code de sortie (2 ou 4) et un message en français.
#[derive(Debug, Clone, PartialEq)]
pub struct ErreurGeotiff {
    pub code: i32,
    pub message: String,
}

impl fmt::Display for ErreurGeotiff {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "{}", self.message)
    }
}

impl std::error::Error for ErreurGeotiff {}

fn refus(message: String) -> ErreurGeotiff {
    ErreurGeotiff { code: SORTIE_REFUSEE, message }
}

fn manque_de_memoire(message: String) -> ErreurGeotiff {
    ErreurGeotiff { code: SORTIE_MEMOIRE, message }
}

/// Un raster lu. Ordre des axes : x = est, y = nord, EPSG:2154.
/// `origine_x` et `origine_y` sont le coin **nord-ouest** du raster ; `pixel_x` et `pixel_y`
/// sont des tailles positives en mètres (la ligne 0 est au nord).
#[derive(Debug, Clone, PartialEq)]
pub struct Raster {
    pub largeur: usize,
    pub hauteur: usize,
    pub origine_x: f64,
    pub origine_y: f64,
    pub pixel_x: f64,
    pub pixel_y: f64,
    /// Valeur « sans donnée » de la balise 42113 (peut être NaN).
    pub nodata: f64,
    /// Une liste de `largeur * hauteur` valeurs par bande, ligne par ligne, du nord au sud.
    /// Les UInt16 sont rendus en f32 (exact).
    pub bandes: Vec<Vec<f32>>,
}

impl Raster {
    /// Vrai si la valeur est la valeur « sans donnée » de ce raster.
    pub fn est_nodata(&self, valeur: f32) -> bool {
        if self.nodata.is_nan() {
            valeur.is_nan()
        } else {
            f64::from(valeur) == self.nodata
        }
    }

    /// Valeur de la bande `bande` à la ligne `ligne` (0 = nord) et à la colonne `colonne`.
    pub fn valeur(&self, bande: usize, ligne: usize, colonne: usize) -> f32 {
        self.bandes[bande][ligne * self.largeur + colonne]
    }
}

/// Réserve un vecteur de `nombre` f32 sans jamais planter : code 4 si la mémoire manque.
pub fn reserver_f32(nombre: usize) -> Result<Vec<f32>, ErreurGeotiff> {
    let mut vecteur: Vec<f32> = Vec::new();
    match vecteur.try_reserve_exact(nombre) {
        Ok(()) => Ok(vecteur),
        Err(_) => Err(manque_de_memoire(format!(
            "mémoire insuffisante : impossible de réserver {nombre} valeurs de 4 octets"
        ))),
    }
}

/// Lit un GeoTIFF au profil `grille`. Code 2 si le fichier est hors profil, 4 si la mémoire manque.
pub fn lire(chemin: &Path) -> Result<Raster, ErreurGeotiff> {
    let octets = std::fs::read(chemin)
        .map_err(|e| refus(format!("{} : lecture impossible ({e})", chemin.display())))?;
    lire_octets(&octets).map_err(|e| ErreurGeotiff {
        code: e.code,
        message: format!("{} : {}", chemin.display(), e.message),
    })
}

/// Comme [`lire`], depuis le contenu d'un fichier déjà en mémoire.
pub fn lire_octets(octets: &[u8]) -> Result<Raster, ErreurGeotiff> {
    let fichier = Fichier::ouvrir(octets)?;
    let entete = fichier.verifier_profil()?;
    let (origine_x, origine_y, pixel_x, pixel_y) = fichier.georeference()?;
    let nodata = fichier.nodata()?;
    let bandes = fichier.lire_pixels(&entete)?;
    Ok(Raster {
        largeur: entete.largeur,
        hauteur: entete.hauteur,
        origine_x,
        origine_y,
        pixel_x,
        pixel_y,
        nodata,
        bandes,
    })
}

// ---------------------------------------------------------------------------------------
// Lecture des balises
// ---------------------------------------------------------------------------------------

/// Où se trouvent les valeurs d'une balise dans le fichier.
struct Entree {
    genre: u16,
    nombre: usize,
    debut: usize,
}

struct Fichier<'a> {
    octets: &'a [u8],
    petit_boutiste: bool,
    balises: HashMap<u16, Entree>,
}

/// Ce que le profil a validé et dont la lecture des pixels a besoin.
struct Entete {
    largeur: usize,
    hauteur: usize,
    nb_bandes: usize,
    flottant: bool,
    predicteur: bool,
    deflate: bool,
    petit_boutiste: bool,
}

fn taille_genre(genre: u16) -> Option<usize> {
    match genre {
        1 | 2 | 6 | 7 => Some(1),
        3 | 8 => Some(2),
        4 | 9 | 11 | 13 => Some(4),
        5 | 10 | 12 | 16 | 17 | 18 => Some(8),
        _ => None,
    }
}

/// Nom d'une compression connue (table `known_compressions` du profil), pour le message.
fn nom_compression(code: u64) -> &'static str {
    match code {
        5 => "LZW",
        6 | 7 => "JPEG",
        32773 => "PackBits",
        34887 => "LERC",
        34925 => "LZMA",
        50000 => "ZSTD",
        50001 => "WEBP",
        _ => "inconnue",
    }
}

impl<'a> Fichier<'a> {
    fn ouvrir(octets: &'a [u8]) -> Result<Fichier<'a>, ErreurGeotiff> {
        if octets.len() < 8 || (&octets[0..2] != b"II" && &octets[0..2] != b"MM") {
            return Err(refus("fichier non TIFF : l'en-tête II ou MM est absent".to_string()));
        }
        let mut fichier = Fichier {
            octets,
            petit_boutiste: &octets[0..2] == b"II",
            balises: HashMap::new(),
        };
        let magique = fichier.u16_en(2)?;
        if magique == 43 {
            return Err(refus(
                "BigTIFF refusé : le profil n'accepte que le TIFF classique (spec §9)".to_string(),
            ));
        }
        if magique != 42 {
            return Err(refus(format!("fichier non TIFF : nombre magique {magique} au lieu de 42")));
        }
        let debut_ifd = fichier.u32_en(4)? as usize;
        fichier.lire_ifd(debut_ifd)?;
        Ok(fichier)
    }

    fn tranche(&self, debut: usize, longueur: usize) -> Result<&'a [u8], ErreurGeotiff> {
        match debut.checked_add(longueur) {
            Some(fin) if fin <= self.octets.len() => Ok(&self.octets[debut..fin]),
            _ => Err(refus("fichier TIFF tronqué ou corrompu (lecture hors du fichier)".to_string())),
        }
    }

    fn u16_en(&self, position: usize) -> Result<u16, ErreurGeotiff> {
        let b = self.tranche(position, 2)?;
        let tableau = [b[0], b[1]];
        Ok(if self.petit_boutiste { u16::from_le_bytes(tableau) } else { u16::from_be_bytes(tableau) })
    }

    fn u32_en(&self, position: usize) -> Result<u32, ErreurGeotiff> {
        let b = self.tranche(position, 4)?;
        let tableau = [b[0], b[1], b[2], b[3]];
        Ok(if self.petit_boutiste { u32::from_le_bytes(tableau) } else { u32::from_be_bytes(tableau) })
    }

    fn f64_en(&self, position: usize) -> Result<f64, ErreurGeotiff> {
        let b = self.tranche(position, 8)?;
        let tableau = [b[0], b[1], b[2], b[3], b[4], b[5], b[6], b[7]];
        Ok(if self.petit_boutiste { f64::from_le_bytes(tableau) } else { f64::from_be_bytes(tableau) })
    }

    /// Lit les entrées du premier IFD (l'image pleine résolution).
    fn lire_ifd(&mut self, debut: usize) -> Result<(), ErreurGeotiff> {
        let nombre_entrees = self.u16_en(debut)? as usize;
        for i in 0..nombre_entrees {
            let position = debut + 2 + 12 * i;
            let balise = self.u16_en(position)?;
            let genre = self.u16_en(position + 2)?;
            let nombre = self.u32_en(position + 4)? as usize;
            let taille = match taille_genre(genre) {
                Some(taille) => taille,
                None => continue,
            };
            let longueur = nombre
                .checked_mul(taille)
                .ok_or_else(|| refus("balise TIFF de taille absurde".to_string()))?;
            let debut_valeurs =
                if longueur <= 4 { position + 8 } else { self.u32_en(position + 8)? as usize };
            self.tranche(debut_valeurs, longueur)?;
            self.balises.insert(balise, Entree { genre, nombre, debut: debut_valeurs });
        }
        Ok(())
    }

    /// Valeurs entières (SHORT ou LONG) d'une balise ; `None` si elle est absente.
    fn entiers(&self, balise: u16) -> Result<Option<Vec<u64>>, ErreurGeotiff> {
        let entree = match self.balises.get(&balise) {
            Some(entree) => entree,
            None => return Ok(None),
        };
        let mut valeurs = Vec::new();
        for i in 0..entree.nombre {
            let valeur = match entree.genre {
                3 => u64::from(self.u16_en(entree.debut + 2 * i)?),
                4 => u64::from(self.u32_en(entree.debut + 4 * i)?),
                _ => {
                    return Err(refus(format!(
                        "balise {balise} : type TIFF {} inattendu",
                        entree.genre
                    )))
                }
            };
            valeurs.push(valeur);
        }
        Ok(Some(valeurs))
    }

    /// Une seule valeur entière ; `defaut` si la balise est absente.
    fn entier(&self, balise: u16, defaut: u64) -> Result<u64, ErreurGeotiff> {
        match self.entiers(balise)? {
            Some(valeurs) if valeurs.len() == 1 => Ok(valeurs[0]),
            Some(_) => Err(refus(format!("balise {balise} : une seule valeur attendue"))),
            None => Ok(defaut),
        }
    }

    /// Valeurs DOUBLE d'une balise ; `None` si elle est absente.
    fn reels(&self, balise: u16) -> Result<Option<Vec<f64>>, ErreurGeotiff> {
        let entree = match self.balises.get(&balise) {
            Some(entree) => entree,
            None => return Ok(None),
        };
        if entree.genre != 12 {
            return Err(refus(format!("balise {balise} : type DOUBLE attendu")));
        }
        let mut valeurs = Vec::new();
        for i in 0..entree.nombre {
            valeurs.push(self.f64_en(entree.debut + 8 * i)?);
        }
        Ok(Some(valeurs))
    }

    // -----------------------------------------------------------------------------------
    // Le profil
    // -----------------------------------------------------------------------------------

    /// Vérifie, dans cet ordre : compression, prédicteur, entrelacement, tuilage, type de
    /// valeurs, projection (le BigTIFF est refusé dès l'ouverture). Rend ce qu'il faut pour
    /// lire les pixels.
    fn verifier_profil(&self) -> Result<Entete, ErreurGeotiff> {
        let largeur = self.entier(T_LARGEUR, 0)? as usize;
        let hauteur = self.entier(T_HAUTEUR, 0)? as usize;
        if largeur == 0 || hauteur == 0 {
            return Err(refus("dimensions de l'image absentes ou nulles".to_string()));
        }

        let compression = self.entier(T_COMPRESSION, COMPRESSION_AUCUNE)?;
        let deflate = COMPRESSIONS_DEFLATE.contains(&compression);
        if compression != COMPRESSION_AUCUNE && !deflate {
            return Err(refus(format!(
                "compression refusée : {} (code {compression}) ; le profil n'accepte que \
                 Deflate ou aucune compression (spec §9)",
                nom_compression(compression)
            )));
        }

        let predicteur = self.entier(T_PREDICTEUR, 1)?;
        if !PREDICTEURS.contains(&predicteur) {
            return Err(refus(format!(
                "PREDICTOR {predicteur} refusé ; le profil n'accepte que 1 ou 2 (spec §9)"
            )));
        }

        let nb_bandes = self.entier(T_ECHANTILLONS, 1)? as usize;
        let entrelacement = self.entier(T_ENTRELACEMENT, 1)?;
        if entrelacement != ENTRELACEMENT_ATTENDU {
            return Err(refus(format!(
                "PLANARCONFIG={entrelacement} refusé ; le profil exige PLANARCONFIG=2 \
                 (une bande après l'autre). Réécrire avec INTERLEAVE=BAND"
            )));
        }

        if self.balises.contains_key(&T_BANDES_LIGNES) || !self.balises.contains_key(&T_TUILE_DEBUTS) {
            return Err(refus(format!(
                "image en bandes de lignes refusée ; le profil exige des tuiles de {TUILE} × {TUILE}"
            )));
        }
        let tuile_largeur = self.entier(T_TUILE_LARGEUR, 0)? as usize;
        let tuile_hauteur = self.entier(T_TUILE_HAUTEUR, 0)? as usize;
        if tuile_largeur != TUILE || tuile_hauteur != TUILE {
            return Err(refus(format!(
                "tuiles de {tuile_largeur} × {tuile_hauteur} refusées ; le profil exige {TUILE} × {TUILE}"
            )));
        }

        let bits = self.entiers(T_BITS)?.unwrap_or_default();
        let formats = self.entiers(T_FORMAT)?.unwrap_or_else(|| vec![1; nb_bandes]);
        if bits.len() != nb_bandes || formats.len() != nb_bandes {
            return Err(refus(format!(
                "{nb_bandes} bande(s) mais {} valeur(s) de bits (balise 258) et {} de format \
                 (balise 339) : fichier incohérent",
                bits.len(),
                formats.len()
            )));
        }
        let flottant = match (bits.first(), formats.first()) {
            (Some(32), Some(3)) => true,
            (Some(16), Some(1)) => false,
            (b, f) => {
                return Err(refus(format!(
                    "type de valeurs refusé (bits {b:?}, format {f:?}) ; le profil n'accepte \
                     que Float32 ou UInt16"
                )))
            }
        };
        let types_mixtes = bits.iter().any(|b| Some(b) != bits.first())
            || formats.iter().any(|f| Some(f) != formats.first());
        if types_mixtes {
            return Err(refus("bandes de types différents refusées".to_string()));
        }

        self.verifier_projection()?;
        Ok(Entete {
            largeur,
            hauteur,
            nb_bandes,
            flottant,
            predicteur: predicteur == 2,
            deflate,
            petit_boutiste: self.petit_boutiste,
        })
    }

    /// Les GeoKeys doivent donner EPSG:2154 en projection (et non un système géographique).
    fn verifier_projection(&self) -> Result<(), ErreurGeotiff> {
        let cles = match self.entiers(T_GEOKEYS)? {
            Some(cles) if cles.len() >= 4 => cles,
            _ => return Err(refus("GeoKeys absentes : le fichier n'est pas géoréférencé".to_string())),
        };
        let mut projete: Option<u64> = None;
        let mut geographique: Option<u64> = None;
        let mut type_raster: u64 = 1;
        let nombre = cles[3] as usize;
        for i in 0..nombre {
            let k = 4 + 4 * i;
            if k + 3 >= cles.len() {
                break;
            }
            // Chaque GeoKey : identifiant, balise source, nombre, valeur.
            match cles[k] {
                GEOKEY_PROJETE => projete = Some(cles[k + 3]),
                GEOKEY_GEOGRAPHIQUE => geographique = Some(cles[k + 3]),
                GEOKEY_TYPE_RASTER => type_raster = cles[k + 3],
                _ => {}
            }
        }
        match (projete, geographique) {
            (Some(EPSG_ATTENDU), _) => {}
            (Some(autre), _) => {
                return Err(refus(format!("EPSG:{autre} refusé ; le profil exige EPSG:{EPSG_ATTENDU}")))
            }
            (None, Some(autre)) => {
                return Err(refus(format!(
                    "système géographique EPSG:{autre} refusé ; le profil exige EPSG:{EPSG_ATTENDU}"
                )))
            }
            (None, None) => {
                return Err(refus(format!("EPSG absent des GeoKeys ; le profil exige EPSG:{EPSG_ATTENDU}")))
            }
        }
        if type_raster != 1 {
            return Err(refus(
                "pixel « point » (RasterPixelIsPoint) refusé : seul « surface » est accepté".to_string(),
            ));
        }
        Ok(())
    }

    /// Origine (coin nord-ouest) et taille de pixel, depuis les balises 33550 et 33922.
    fn georeference(&self) -> Result<(f64, f64, f64, f64), ErreurGeotiff> {
        let echelle = self.reels(T_ECHELLE)?;
        let points = self.reels(T_POINT_LIE)?;
        match (echelle, points) {
            (Some(e), Some(p)) if e.len() >= 2 && p.len() == 6 => {
                if e[0] <= 0.0 || e[1] <= 0.0 {
                    return Err(refus("taille de pixel nulle ou négative".to_string()));
                }
                // p = (i, j, k, x, y, z) : le pixel (i, j) est au point (x, y).
                Ok((p[3] - p[0] * e[0], p[4] + p[1] * e[1], e[0], e[1]))
            }
            _ if self.balises.contains_key(&T_TRANSFORMATION) => Err(refus(
                "géoréférencement par matrice (balise 34264) refusé ; échelle et point de liaison \
                 attendus"
                    .to_string(),
            )),
            _ => Err(refus("géoréférencement absent (balises 33550 et 33922)".to_string())),
        }
    }

    /// Valeur nodata de la balise 42113 (texte). Absente ou illisible : refus, jamais de défaut.
    fn nodata(&self) -> Result<f64, ErreurGeotiff> {
        let entree = self.balises.get(&T_NODATA).ok_or_else(|| {
            refus("nodata absent : la balise 42113 (GDAL_NODATA) est obligatoire".to_string())
        })?;
        let brut = self.tranche(entree.debut, entree.nombre)?;
        let texte = String::from_utf8_lossy(brut);
        let texte = texte.trim_matches(|c: char| c == '\0' || c.is_whitespace());
        texte
            .parse::<f64>()
            .map_err(|_| refus(format!("nodata illisible dans la balise 42113 : « {texte} »")))
    }

    // -----------------------------------------------------------------------------------
    // Les pixels
    // -----------------------------------------------------------------------------------

    fn lire_pixels(&self, entete: &Entete) -> Result<Vec<Vec<f32>>, ErreurGeotiff> {
        let colonnes_tuiles = entete.largeur.div_ceil(TUILE);
        let lignes_tuiles = entete.hauteur.div_ceil(TUILE);
        let par_bande = colonnes_tuiles * lignes_tuiles;
        let debuts = self.entiers(T_TUILE_DEBUTS)?.unwrap_or_default();
        let tailles = self.entiers(T_TUILE_TAILLES)?.unwrap_or_default();
        if debuts.len() != par_bande * entete.nb_bandes || tailles.len() != debuts.len() {
            return Err(refus(format!(
                "nombre de tuiles incohérent : {} trouvées, {} attendues",
                debuts.len(),
                par_bande * entete.nb_bandes
            )));
        }

        let nombre_pixels = entete
            .largeur
            .checked_mul(entete.hauteur)
            .ok_or_else(|| refus("image de taille absurde".to_string()))?;
        let mut bandes: Vec<Vec<f32>> = Vec::new();
        for _ in 0..entete.nb_bandes {
            let mut bande = reserver_f32(nombre_pixels)?;
            bande.resize(nombre_pixels, 0.0);
            bandes.push(bande);
        }

        // PLANARCONFIG=2 : toutes les tuiles de la bande 0, puis celles de la bande 1, etc.
        for (indice, (debut, taille)) in debuts.iter().zip(tailles.iter()).enumerate() {
            if *debut == 0 && *taille == 0 {
                return Err(refus("tuile absente (fichier creux) : refusé".to_string()));
            }
            let brut = self.tranche(*debut as usize, *taille as usize)?;
            let valeurs = decoder_tuile(brut, entete)?;
            let bande = indice / par_bande;
            let rang = indice % par_bande;
            copier_tuile(&valeurs, &mut bandes[bande], entete, rang / colonnes_tuiles, rang % colonnes_tuiles);
        }
        Ok(bandes)
    }
}

/// Décompresse une tuile et rend ses 256 × 256 valeurs en f32 (prédicteur 2 défait).
fn decoder_tuile(brut: &[u8], entete: &Entete) -> Result<Vec<f32>, ErreurGeotiff> {
    let octets_par_valeur = if entete.flottant { 4 } else { 2 };
    let attendu = TUILE * TUILE * octets_par_valeur;

    let mut tuile: Vec<u8> = Vec::new();
    tuile
        .try_reserve_exact(attendu + 1)
        .map_err(|_| manque_de_memoire("mémoire insuffisante pour lire une tuile".to_string()))?;
    if entete.deflate {
        // `take` borne la sortie : un flux qui gonfle au-delà d'une tuile est refusé.
        let mut decodeur = ZlibDecoder::new(brut).take(attendu as u64 + 1);
        decodeur
            .read_to_end(&mut tuile)
            .map_err(|e| refus(format!("tuile Deflate illisible ({e})")))?;
    } else {
        tuile.extend_from_slice(brut);
    }
    if tuile.len() != attendu {
        return Err(refus(format!(
            "tuile de {} octets au lieu de {attendu} : fichier corrompu",
            tuile.len()
        )));
    }
    convertir_tuile(&tuile, entete)
}

/// Octets de la tuile (ordre du fichier) vers f32, en défaisant le prédicteur 2 :
/// chaque valeur est la différence avec sa voisine de gauche, ligne par ligne.
fn convertir_tuile(tuile: &[u8], entete: &Entete) -> Result<Vec<f32>, ErreurGeotiff> {
    let mut valeurs = reserver_f32(TUILE * TUILE)?;
    for ligne in tuile.chunks(tuile.len() / TUILE) {
        if entete.flottant {
            let mut cumul: u32 = 0;
            for o in ligne.chunks(4) {
                let tableau = [o[0], o[1], o[2], o[3]];
                let lu = if entete.petit_boutiste {
                    u32::from_le_bytes(tableau)
                } else {
                    u32::from_be_bytes(tableau)
                };
                cumul = if entete.predicteur { cumul.wrapping_add(lu) } else { lu };
                valeurs.push(f32::from_bits(cumul));
            }
        } else {
            let mut cumul: u16 = 0;
            for o in ligne.chunks(2) {
                let tableau = [o[0], o[1]];
                let lu = if entete.petit_boutiste {
                    u16::from_le_bytes(tableau)
                } else {
                    u16::from_be_bytes(tableau)
                };
                cumul = if entete.predicteur { cumul.wrapping_add(lu) } else { lu };
                valeurs.push(f32::from(cumul));
            }
        }
    }
    Ok(valeurs)
}

/// Recopie une tuile à sa place dans la bande, en coupant le bord rempli au-delà de l'image.
fn copier_tuile(tuile: &[f32], bande: &mut [f32], entete: &Entete, ligne_tuile: usize, colonne_tuile: usize) {
    let x0 = colonne_tuile * TUILE;
    let y0 = ligne_tuile * TUILE;
    let colonnes = TUILE.min(entete.largeur - x0);
    let lignes = TUILE.min(entete.hauteur - y0);
    for l in 0..lignes {
        let source = &tuile[l * TUILE..l * TUILE + colonnes];
        let debut = (y0 + l) * entete.largeur + x0;
        bande[debut..debut + colonnes].copy_from_slice(source);
    }
}
