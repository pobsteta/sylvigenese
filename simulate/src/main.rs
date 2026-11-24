//! Exécutable `simulate` (ADR 0001).
//!
//! Étape du BRIEF codée ici : aucune étape métier (squelette) ; le moteur (BRIEF §6 et §8) viendra plus tard.
//!
//! Usage : `simulate [--config <chemin>]` (par défaut `config.yml`).
//! Code de sortie : 0 (tout va bien) ou 2 (impossible, message sur stderr).

use std::path::PathBuf;

fn main() {
    let arguments: Vec<String> = std::env::args().skip(1).collect();
    let chemin = match arguments.as_slice() {
        [] => PathBuf::from("config.yml"),
        [option, valeur] if option == "--config" => PathBuf::from(valeur),
        _ => {
            eprintln!("usage : simulate [--config <chemin>]");
            std::process::exit(simulate::SORTIE_IMPOSSIBLE);
        }
    };
    std::process::exit(simulate::executer(&chemin));
}
