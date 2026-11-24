//! Type d'erreur unique : un message en français, jamais de panique sur une entrée utilisateur.

use std::fmt;

#[derive(Debug)]
pub struct Erreur(pub String);

pub type Res<T> = Result<T, Erreur>;

impl fmt::Display for Erreur {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.0)
    }
}

impl std::error::Error for Erreur {}

impl From<std::io::Error> for Erreur {
    fn from(e: std::io::Error) -> Self {
        Erreur(format!("Erreur d'entrée/sortie : {e}"))
    }
}

/// Construit une `Erreur` avec `format!`.
#[macro_export]
macro_rules! erreur {
    ($($arg:tt)*) => { $crate::erreur::Erreur(format!($($arg)*)) };
}
