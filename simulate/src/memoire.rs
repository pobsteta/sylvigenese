//! Mémoire : estimation avant le premier pas, comparaison à `MemAvailable`, réservations sans
//! arrêt brutal (spec §6, « Codes de sortie » ; plan M3a, T3).
//!
//! Étape du BRIEF codée ici : BRIEF §13 (rejouable sur un portable) et spec §6 : « avant le
//! premier pas, le moteur estime la mémoire nécessaire et la compare à `MemAvailable`. Le noyau
//! Linux tue un programme qui sur-alloue (code 137) : le moteur doit donc refuser avant. »
//!
//! - [`lire_mem_available`] lit la ligne `MemAvailable:` de `/proc/meminfo` (en kio, rendue en
//!   octets) ; fichier absent ou ligne introuvable : code 4, « mémoire non vérifiable », jamais
//!   une valeur devinée. L'option de test `--memoire-disponible` (mission 038) passe outre.
//! - [`estimer`] additionne : [`COPIES_ETAT`] copies de l'état des arbres (l'état figé au
//!   1er janvier et ses mises à jour, plan M3a) au plus grand nombre d'arbres attendu, chaque
//!   arbre comptant [`crate::etat::OCTETS_FIXES_PAR_ARBRE`] plus le texte de ses chaînes ; les
//!   valeurs des rasters en f32 ; et les octets supplémentaires déclarés par l'appelant.
//!   C'est une estimation, à mesurer contre la mémoire résidente en M5 (spec §11 : à moins de
//!   10 %).
//! - [`verifier`] refuse (code 4) si l'estimation dépasse [`MARGE`] × `MemAvailable`
//!   (T3 : 0,9), calcul en entiers, sans arrondi flottant.
//! - [`erreur_allocation`] et [`reserver_f64`] : un `try_reserve_exact` qui échoue donne le
//!   code 4 avec un message en français.
//! - [`estimer_ser`] : l'estimation du **niveau SER** (mission 063, plan m5a, T7), une formule
//!   fermée, voir sa documentation : une part fixe du programme **mesurée** ([`PART_FIXE_SER`]),
//!   l'état qui dure toute l'exécution, et le plus grand des besoins passagers (le pas annuel,
//!   l'écriture d'un fichier, la lecture des cohortes). Critère de M5a (spec §11, décision de
//!   Pascal Q5) : à moins de 10 % de la mémoire résidente mesurée hors du moteur.
//!
//! Règle de lisibilité (CLAUDE.md) : fonctions libres et une structure concrète, sans macro
//! maison ni générique.

use std::path::Path;

use crate::erreurs::Erreur;
use crate::etat::OCTETS_FIXES_PAR_ARBRE;

/// Part de `MemAvailable` que l'estimation peut occuper : 9 dixièmes (T3).
pub const MARGE_DIXIEMES: u64 = 9;
/// La même marge, pour l'affichage.
pub const MARGE: f64 = 0.9;
/// Copies de l'état des arbres présentes en même temps : l'état figé et ses mises à jour.
pub const COPIES_ETAT: u64 = 2;
/// Octets d'une valeur de raster (f32, lecteur GeoTIFF).
pub const OCTETS_PAR_VALEUR_RASTER: u64 = 4;
/// Le fichier lu par défaut sous Linux.
pub const MEMINFO: &str = "/proc/meminfo";

/// Ce qu'il faut savoir pour estimer la mémoire d'une simulation.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct Besoin {
    /// Le plus grand nombre d'arbres présents en même temps dans l'état.
    pub arbres_max: u64,
    /// Octets de texte par arbre (`tree_id` et code d'essence), mesurés sur l'état initial.
    pub octets_texte_par_arbre: u64,
    /// Nombre de valeurs de rasters gardées en mémoire (pixels × bandes, toutes couches).
    pub valeurs_raster: u64,
    /// Autres octets déclarés par l'appelant (cellules, sorties en cours…).
    pub octets_supplementaires: u64,
}

/// L'estimation en octets. Code 4 si le calcul dépasse 2^64 octets (besoin hors de portée).
pub fn estimer(besoin: &Besoin) -> Result<u64, Erreur> {
    let trop = || {
        Erreur::memoire_insuffisante(format!(
            "besoin de mémoire hors de portée (plus de 2^64 octets) pour {} arbres et {} valeurs de raster",
            besoin.arbres_max, besoin.valeurs_raster
        ))
    };
    let par_arbre = OCTETS_FIXES_PAR_ARBRE
        .checked_add(besoin.octets_texte_par_arbre)
        .ok_or_else(trop)?;
    let arbres = COPIES_ETAT
        .checked_mul(besoin.arbres_max)
        .and_then(|n| n.checked_mul(par_arbre))
        .ok_or_else(trop)?;
    let rasters = besoin
        .valeurs_raster
        .checked_mul(OCTETS_PAR_VALEUR_RASTER)
        .ok_or_else(trop)?;
    arbres
        .checked_add(rasters)
        .and_then(|n| n.checked_add(besoin.octets_supplementaires))
        .ok_or_else(trop)
}

/// Refuse (code 4) si `besoin` dépasse 0,9 × `disponible` (octets). À appeler avant toute écriture.
pub fn verifier(besoin: u64, disponible: u64) -> Result<(), Erreur> {
    let besoin_dixiemes = u128::from(besoin) * 10;
    let permis_dixiemes = u128::from(disponible) * u128::from(MARGE_DIXIEMES);
    if besoin_dixiemes > permis_dixiemes {
        return Err(Erreur::memoire_insuffisante(format!(
            "la simulation demanderait environ {} Mio ; disponible : {} Mio (MemAvailable), dont {} % utilisables",
            mio(besoin),
            mio(disponible),
            MARGE_DIXIEMES * 10
        )));
    }
    Ok(())
}

fn mio(octets: u64) -> u64 {
    octets / (1024 * 1024)
}

/// Lit `MemAvailable` (en octets) dans un fichier au format de `/proc/meminfo`.
/// Code 4 si le fichier est illisible ou sans ligne `MemAvailable` valide.
pub fn lire_mem_available(chemin: &Path) -> Result<u64, Erreur> {
    let texte = std::fs::read_to_string(chemin).map_err(|e| {
        Erreur::memoire_insuffisante(format!(
            "mémoire non vérifiable : {} illisible ({e})",
            chemin.display()
        ))
    })?;
    analyser_meminfo(&texte)
        .map_err(|e| Erreur::memoire_insuffisante(format!("{} : {}", chemin.display(), e.message)))
}

/// Extrait `MemAvailable` (en octets) du texte de `/proc/meminfo` (`MemAvailable:  1234 kB`).
/// Code 4 si la ligne manque ou est mal formée.
pub fn analyser_meminfo(texte: &str) -> Result<u64, Erreur> {
    for ligne in texte.lines() {
        if let Some(reste) = ligne.strip_prefix("MemAvailable:") {
            let morceaux: Vec<&str> = reste.split_whitespace().collect();
            let kio = match morceaux.as_slice() {
                [nombre, "kB"] => nombre.parse::<u64>().ok(),
                _ => None,
            };
            return match kio.and_then(|k| k.checked_mul(1024)) {
                Some(octets) => Ok(octets),
                None => Err(Erreur::memoire_insuffisante(format!(
                    "mémoire non vérifiable : ligne MemAvailable mal formée (« {} »)",
                    ligne.trim()
                ))),
            };
        }
    }
    Err(Erreur::memoire_insuffisante(
        "mémoire non vérifiable : pas de ligne MemAvailable".to_string(),
    ))
}

/// L'erreur (code 4) d'une réservation de `nombre` valeurs qui a échoué.
pub fn erreur_allocation(nombre: usize, quoi: &str) -> Erreur {
    Erreur::memoire_insuffisante(format!("impossible de réserver {nombre} valeurs ({quoi})"))
}

/// Un vecteur vide de f64 avec la place de `nombre` valeurs. Code 4 si la mémoire manque.
pub fn reserver_f64(nombre: usize, quoi: &str) -> Result<Vec<f64>, Erreur> {
    let mut vecteur: Vec<f64> = Vec::new();
    vecteur
        .try_reserve_exact(nombre)
        .map_err(|_| erreur_allocation(nombre, quoi))?;
    Ok(vecteur)
}

// ------------------------------------------------------------------------------------------
// Niveau SER (mission 063)

/// Part fixe du programme au niveau SER, en octets : la mémoire résidente maximale (`VmHWM`) d'une
/// exécution « à vide », mesurée et non devinée. Mesure du 26/11/2026 (mission 063) : SER fictive
/// de 4 × 4 cellules (`tests/m5/ser_fictive.py --n 4 --graine 1`), 1 an, binaire de
/// `cargo build --release --locked` (rustc 1.97, glibc 2.39, Linux x86_64, 4 cœurs) ; 18 exécutions
/// à 1 et à 4 fils (6 à la main, puis deux passes de `bench/m5/mesurer.sh --a-vide`) : VmHWM de
/// 9 844 à 10 436 kio ; la valeur retenue est la plus grande, 10 436 kio. Elle comprend le code du
/// programme et ses bibliothèques, la lecture de config.yml et des paramètres, les plans de FFT et
/// les fils de calcul ; ce qui grandit avec la SER est dans la formule de [`estimer_ser`]. C'est
/// une constante technique, pas écologique ; à remesurer si le programme ou sa chaîne de
/// compilation change (`bench/m5/mesurer.sh --a-vide`).
pub const PART_FIXE_SER: u64 = 10_436 * 1024;

/// Ce que l'estimation du niveau SER doit savoir (tout est connu avant la lecture des cohortes).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct BesoinSer {
    /// Cellules de la grille, forêt ou non (largeur × hauteur de `grid.tif`).
    pub cellules_grille: u64,
    /// Cellules forestières.
    pub cellules_foret: u64,
    /// Essences du moteur (S).
    pub especes: u64,
    /// Classes de diamètre (K).
    pub classes: u64,
    /// Somme, sur les essences candidates, de leurs classes annuelles de semis (Σ A).
    pub classes_semis: u64,
    /// Essences candidates au recrutement.
    pub candidates: u64,
    /// Valeurs réelles du tableau de la FFT (colonnes × lignes, zone tampon et rembourrage compris).
    pub valeurs_fft: u64,
    /// Valeurs complexes d'un spectre (colonnes spectrales × lignes).
    pub valeurs_spectre: u64,
    /// Lignes au plus d'un fichier Parquet écrit.
    pub lignes_par_fichier: u64,
}

/// Octets d'une ligne de `sim/cells` en construction : cell_id (8), six réels (8 × 6), l'en-tête
/// de chaîne de l'essence dans la table Arrow (4 de décalage, 8 de texte au plus) et les masques
/// des valeurs vides ; compté deux fois (colonnes Arrow et pages Parquet encodées avant écriture).
pub const OCTETS_LIGNE_ECRITE: u64 = 2 * (8 + 6 * 8 + 4 + 8 + 1);

/// Octets d'une ligne de `cohorts_init` en lecture (un lot) : cell_id et d_class (8 + 8, et leur
/// copie en `Option<i64>`, 16 + 16), tiges (8 et 16), essence et source (24 + 24 d'en-tête, plus le
/// texte, 8 et 80 au plus).
pub const OCTETS_LIGNE_LUE: u64 = 8 + 8 + 16 + 16 + 8 + 16 + 24 + 24 + 8 + 80;

/// L'estimation de mémoire du niveau SER, en octets : une formule fermée.
///
/// - **état durable** :
///   - couches de la grille (`h0`, `chm_date`, `site_potential`, trois gradients en f32 ; `ser`
///     en u32 ; validité de `grid.tif`, 1 octet ; index forestier, u32) : 33 octets par cellule ;
///   - par cellule forestière : rang (u32), H_dom (f64), adultes 4 × S × K (f32), semis 8 × Σ A
///     (f64) ;
///   - les spectres des noyaux : 16 octets par valeur complexe et par essence candidate ;
/// - **besoins passagers**, le plus grand des trois :
///   - le **pas annuel** : H_dom de fin d'année et indice de couvert (2 × 8 par cellule
///     forestière), recrues de l'année (8 par cellule forestière et essence candidate), semenciers
///     (1 par cellule), champ des graines (8 par cellule) et, pendant la convolution, les lignes
///     transformées (16 par valeur complexe), le tableau réel de sortie (8 par valeur de la FFT)
///     et le champ reçu (8 par cellule) ;
///   - l'**écriture** d'un fichier : [`OCTETS_LIGNE_ECRITE`] par ligne, pour au plus
///     `lignes_par_fichier` lignes et jamais plus que de valeurs dans l'état (cellules forestières
///     × S × K) ;
///   - la **lecture** d'un lot de `cohorts_init` : [`OCTETS_LIGNE_LUE`] par ligne, même borne ;
/// - la **part fixe** mesurée [`PART_FIXE_SER`].
///
/// Code 4 si le calcul dépasse 2^64 octets.
pub fn estimer_ser(besoin: &BesoinSer) -> Result<u64, Erreur> {
    let trop = || {
        Erreur::memoire_insuffisante(format!(
            "besoin de mémoire du niveau SER hors de portée (plus de 2^64 octets) pour {} cellules",
            besoin.cellules_grille
        ))
    };
    let c = u128::from(besoin.cellules_grille);
    let f = u128::from(besoin.cellules_foret);
    let durable = 33 * c
        + f * (4 + 8 + 4 * u128::from(besoin.especes) * u128::from(besoin.classes) + 8 * u128::from(besoin.classes_semis))
        + 16 * u128::from(besoin.valeurs_spectre) * u128::from(besoin.candidates);
    let pas = f * (16 + 8 * u128::from(besoin.candidates))
        + c * (1 + 8 + 8)
        + 16 * u128::from(besoin.valeurs_spectre)
        + 8 * u128::from(besoin.valeurs_fft);
    // Lignes au plus d'un fichier écrit ou d'un lot lu : jamais plus que de valeurs dans l'état.
    let lignes_etat = f * u128::from(besoin.especes) * u128::from(besoin.classes);
    let ecriture = u128::from(besoin.lignes_par_fichier).min(lignes_etat) * u128::from(OCTETS_LIGNE_ECRITE);
    let lecture = (crate::entrees::LIGNES_PAR_LOT_COHORTES as u128).min(lignes_etat) * u128::from(OCTETS_LIGNE_LUE);
    let passager = pas.max(ecriture).max(lecture);
    let total = u128::from(PART_FIXE_SER) + durable + passager;
    u64::try_from(total).map_err(|_| trop())
}
