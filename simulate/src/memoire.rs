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
