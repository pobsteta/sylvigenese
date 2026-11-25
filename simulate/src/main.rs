//! Exécutable `simulate` (ADR 0001, mission 038).
//!
//! Étape du BRIEF codée ici : BRIEF §8 (simulation du massif de t0 à t0 + years) ; tout le
//! travail est dans la bibliothèque (`lib.rs`, `sorties.rs`).
//!
//! Usage : `simulate [--config <chemin>] [--threads N] [--memoire-disponible <octets>]
//! [--inject-nan [année]]` (par défaut `config.yml`). Les deux dernières options servent aux
//! tests : mémoire disponible imposée (code 4), NaN injecté dans l'état (code 3).
//! Codes de sortie : 0 tout va bien, 1 anomalie, 2 entrée refusée, 3 contrôle échoué,
//! 4 mémoire insuffisante (message en français sur stderr).

fn main() {
    let arguments: Vec<String> = std::env::args().skip(1).collect();
    let options = match simulate::lire_options(&arguments) {
        Ok(options) => options,
        Err(message) => {
            eprintln!("[simulate] entrée refusée (code 2) : {message}");
            eprintln!(
                "usage : simulate [--config <chemin>] [--threads N] [--memoire-disponible <octets>] [--inject-nan [année]]"
            );
            std::process::exit(simulate::SORTIE_IMPOSSIBLE);
        }
    };
    std::process::exit(simulate::executer(&options));
}
