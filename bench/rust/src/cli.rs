//! Lecture de la ligne de commande (spec §7), sans `unwrap` sur l'entrée utilisateur.

use crate::erreur::Res;
use crate::erreur;
use crate::sim::Config;
use std::path::PathBuf;

pub const AIDE: &str = "Usage : bench-sim --n N --years Y --out DIR [--seed S] [--threads T] [--inject-nan ANNEE] [--hmax-zero]\n\
  --n N            côté de la grille (N x N cellules de 25 m)\n\
  --years Y        nombre d'années simulées (>= 1)\n\
  --seed S         graine de l'aléa (défaut 42)\n\
  --threads T      nombre de fils rayon (défaut 1)\n\
  --out DIR        dossier de sortie\n\
  --inject-nan A   met H[0,0] = NaN au début de l'année A (test du contrôle)\n\
  --hmax-zero      met Hmax[0,0] = 0 (entrée invalide, refusée avant le premier pas)";

/// `Ok(None)` si l'aide a été demandée.
pub fn parse<I: IntoIterator<Item = String>>(args: I) -> Res<Option<Config>> {
    let mut it = args.into_iter();
    let (mut n, mut years, mut out) = (None, None, None);
    let mut seed = 42u64;
    let mut threads = 1usize;
    let mut inject_nan = None;
    let mut hmax_zero = false;

    fn valeur(it: &mut impl Iterator<Item = String>, nom: &str) -> Res<String> {
        it.next()
            .ok_or_else(|| erreur!("L'option {nom} attend une valeur."))
    }
    fn nombre<T: std::str::FromStr>(s: &str, nom: &str) -> Res<T> {
        s.parse::<T>()
            .map_err(|_| erreur!("Valeur invalide pour {nom} : « {s} » (entier positif attendu)."))
    }

    while let Some(a) = it.next() {
        match a.as_str() {
            "--n" => n = Some(nombre::<usize>(&valeur(&mut it, "--n")?, "--n")?),
            "--years" => years = Some(nombre::<u64>(&valeur(&mut it, "--years")?, "--years")?),
            "--seed" => seed = nombre(&valeur(&mut it, "--seed")?, "--seed")?,
            "--threads" => threads = nombre(&valeur(&mut it, "--threads")?, "--threads")?,
            "--out" => out = Some(PathBuf::from(valeur(&mut it, "--out")?)),
            "--inject-nan" => {
                inject_nan = Some(nombre::<u64>(&valeur(&mut it, "--inject-nan")?, "--inject-nan")?)
            }
            "--hmax-zero" => hmax_zero = true,
            "-h" | "--help" => return Ok(None),
            autre => return Err(erreur!("Option inconnue : « {autre} ». Voir --help.")),
        }
    }
    let n = n.ok_or_else(|| erreur!("Option obligatoire manquante : --n."))?;
    let years = years.ok_or_else(|| erreur!("Option obligatoire manquante : --years."))?;
    let out = out.ok_or_else(|| erreur!("Option obligatoire manquante : --out."))?;
    let cfg = Config { n, years, seed, threads, out, inject_nan, hmax_zero };
    cfg.valider()?;
    Ok(Some(cfg))
}
