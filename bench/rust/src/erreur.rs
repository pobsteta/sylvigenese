//! Type d'erreur unique : un code de sortie (SPEC §11 AM3) et un message en français,
//! jamais de panique sur une entrée utilisateur.
//!
//! Codes : 1 = erreur d'entrée/sortie, 2 = entrée refusée, 3 = contrôle §6.8 échoué,
//! 4 = mémoire insuffisante.

use std::fmt;

pub const CODE_ES: i32 = 1;
pub const CODE_ENTREE: i32 = 2;
pub const CODE_CONTROLE: i32 = 3;
pub const CODE_MEMOIRE: i32 = 4;

#[derive(Debug)]
pub struct Erreur {
    pub code: i32,
    pub msg: String,
}

pub type Res<T> = Result<T, Erreur>;

impl fmt::Display for Erreur {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.msg)
    }
}

impl std::error::Error for Erreur {}

impl From<std::io::Error> for Erreur {
    fn from(e: std::io::Error) -> Self {
        Erreur { code: CODE_ES, msg: format!("Erreur d'entrée/sortie : {e}") }
    }
}

/// Erreur d'entrée refusée (code 2) avec `format!`.
#[macro_export]
macro_rules! erreur {
    ($($arg:tt)*) => { $crate::erreur::Erreur { code: $crate::erreur::CODE_ENTREE, msg: format!($($arg)*) } };
}

/// Erreur avec un code explicite.
#[macro_export]
macro_rules! erreur_code {
    ($code:expr, $($arg:tt)*) => { $crate::erreur::Erreur { code: $code, msg: format!($($arg)*) } };
}

/// Alloue un `Vec` de `len` éléments `val` avec `try_reserve_exact` : un manque de
/// mémoire donne une erreur (code 4), jamais un avortement.
pub fn alloue<T: Clone>(len: usize, val: T, nom: &str) -> Res<Vec<T>> {
    let octets = len.saturating_mul(std::mem::size_of::<T>());
    let mut v: Vec<T> = Vec::new();
    v.try_reserve_exact(len).map_err(|_| {
        erreur_code!(
            CODE_MEMOIRE,
            "Mémoire insuffisante : impossible d'allouer {nom} ({octets} octets, soit {:.2} Gio).",
            octets as f64 / (1u64 << 30) as f64
        )
    })?;
    v.resize(len, val);
    Ok(v)
}
