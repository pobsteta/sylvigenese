//! Moteur `simulate` (ADR 0001) : de `config.yml` aux sorties `sim/` (mission 038).
//!
//! Étape du BRIEF codée ici : BRIEF §8 (le massif simulé de t0 à t0 + years) et §4 (fichiers
//! écrits, validés en fin de module). Ce module enchaîne :
//!
//! 1. lecture de `config.yml` (absente ou illisible : code 2), empreinte SHA-256 de ses octets,
//!    validation par `contracts/validate config` (code 2 si non conforme) ;
//! 2. dossier de la zone, même règle que `prepare_zone_dir` (R) : `tests/fixtures/zone_fictive`
//!    pour le jeu fictif, sinon `data/<zone>`, sous la racine `SYLVIGENESE_ROOT` (défaut : le
//!    dossier courant) ; référentiel `contracts/species.csv` sous la même racine ;
//! 3. entrées ([`entrees::Entrees::charger`]), puis simulation et écriture dans un dossier
//!    temporaire `<zone>/.sim_en_cours/` ([`sorties::simuler_et_ecrire`], mémoire vérifiée avant
//!    toute écriture) ;
//! 4. validation de chaque sortie par `contracts/validate` (`sim_trees`, `sim_cells`,
//!    `sim_flags`, `run`), **sur le dossier temporaire** ;
//! 5. publication : le dossier temporaire devient `<zone>/sim/` (l'ancien `sim/` est retiré
//!    seulement à ce moment). Sur toute erreur, le dossier temporaire est supprimé : **aucune
//!    sortie partielle** ; un `sim/` d'une exécution précédente reste tel quel.
//!
//! Codes de sortie (module [`erreurs`]) : 0 tout va bien ; 1 anomalie du programme (dont une
//! sortie refusée par le validateur) ; 2 entrée refusée ; 3 contrôle échoué ; 4 mémoire
//! insuffisante. Le message, en français, est écrit sur stderr.
//!
//! Options (voir `main.rs`) : `--config`, `--threads` (sinon `simulate.threads` de config.yml,
//! sinon 1), et pour les tests `--memoire-disponible <octets>` et `--inject-nan [année]`.
//!
//! Règle de lisibilité (CLAUDE.md) : pas de macros maison ni de génériques avancés.

pub mod accroissement;
pub mod alea;
pub mod concurrence;
pub mod config;
pub mod controles;
pub mod entrees;
pub mod erreurs;
pub mod etat;
pub mod geotiff;
pub mod grille;
pub mod hauteur;
pub mod memoire;
pub mod mortalite;
pub mod parametres;
pub mod pas;
pub mod recrutement;
pub mod sorties;
pub mod validateur;

use std::path::{Path, PathBuf};

use erreurs::Erreur;

/// Code de sortie : tout va bien.
pub const SORTIE_OK: i32 = 0;
/// Code de sortie : l'exécution est impossible (entrée refusée, message sur stderr).
pub const SORTIE_IMPOSSIBLE: i32 = 2;

/// Nom du dossier temporaire d'écriture, dans le dossier de la zone.
pub const DOSSIER_EN_COURS: &str = ".sim_en_cours";
/// Nom du dossier où l'ancien `sim/` attend d'être retiré pendant la publication.
pub const DOSSIER_ANCIEN: &str = ".sim_ancien";

/// Les options de la ligne de commande.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Options {
    pub config: PathBuf,
    /// `--threads N` ; sinon `simulate.threads`, sinon 1.
    pub threads: Option<usize>,
    /// `--memoire-disponible <octets>` (tests) ; sinon `MemAvailable` de /proc/meminfo.
    pub memoire_disponible: Option<u64>,
    /// `--inject-nan [année]` (tests) : `Some(None)` sans année, c'est-à-dire t0 + 1.
    pub inject_nan: Option<Option<i32>>,
}

/// Lit les arguments (sans le nom du programme). Message d'usage en français sinon.
pub fn lire_options(arguments: &[String]) -> Result<Options, String> {
    let mut options = Options {
        config: PathBuf::from("config.yml"),
        threads: None,
        memoire_disponible: None,
        inject_nan: None,
    };
    let mut rang = 0;
    while rang < arguments.len() {
        let option = arguments[rang].as_str();
        let valeur = arguments.get(rang + 1);
        match option {
            "--config" => {
                options.config = PathBuf::from(valeur.ok_or("--config sans chemin")?);
                rang += 2;
            }
            "--threads" => {
                let texte = valeur.ok_or("--threads sans nombre")?;
                let n: usize = texte
                    .parse()
                    .map_err(|_| format!("--threads « {texte} » n'est pas un entier"))?;
                if n == 0 {
                    return Err("--threads doit valoir au moins 1".to_string());
                }
                options.threads = Some(n);
                rang += 2;
            }
            "--memoire-disponible" => {
                let texte = valeur.ok_or("--memoire-disponible sans nombre d'octets")?;
                let n: u64 = texte.parse().map_err(|_| {
                    format!("--memoire-disponible « {texte} » n'est pas un nombre d'octets")
                })?;
                options.memoire_disponible = Some(n);
                rang += 2;
            }
            "--inject-nan" => match valeur.and_then(|texte| texte.parse::<i32>().ok()) {
                Some(annee) => {
                    options.inject_nan = Some(Some(annee));
                    rang += 2;
                }
                None => {
                    options.inject_nan = Some(None);
                    rang += 1;
                }
            },
            autre => return Err(format!("option inconnue : {autre}")),
        }
    }
    Ok(options)
}

/// La racine des données : `SYLVIGENESE_ROOT`, sinon le dossier courant.
pub fn racine() -> PathBuf {
    match std::env::var("SYLVIGENESE_ROOT") {
        Ok(chemin) if !chemin.is_empty() => PathBuf::from(chemin),
        _ => PathBuf::from("."),
    }
}

/// Le dossier d'une zone sous une racine (même règle que `prepare_zone_dir` de R/commun.R).
pub fn dossier_zone(racine: &Path, zone: &str) -> Result<PathBuf, Erreur> {
    if zone.is_empty() || zone.contains('/') || zone.contains("..") {
        return Err(Erreur::entree_refusee(format!(
            "config.yml : zone « {zone} » invalide (un nom de dossier simple est attendu)"
        )));
    }
    if zone == "zone_fictive" {
        return Ok(racine.join("tests").join("fixtures").join("zone_fictive"));
    }
    Ok(racine.join("data").join(zone))
}

/// Exécute `simulate` et rend le code de sortie (0 à 4) ; le message va sur stderr.
pub fn executer(options: &Options) -> i32 {
    match executer_sans_code(options) {
        Ok(bilan) => {
            eprintln!(
                "[simulate] terminé en {:.1} s : {} lignes d'arbres, {} recrues, {} morts, {} signalements ; \
                 mémoire estimée {} octets avant le premier pas, {} au plus.",
                bilan.duree_s,
                bilan.lignes_arbres,
                bilan.comptes.recrues,
                bilan.comptes.morts,
                bilan.signalements,
                bilan.memoire_estimee,
                bilan.memoire_maximale
            );
            SORTIE_OK
        }
        Err(erreur) => {
            eprintln!("[simulate] {erreur}");
            erreur.code_sortie()
        }
    }
}

fn executer_sans_code(options: &Options) -> Result<sorties::Bilan, Erreur> {
    let octets = std::fs::read(&options.config).map_err(|e| {
        Erreur::entree_refusee(format!(
            "config.yml introuvable ou illisible ({}) : {e}",
            options.config.display()
        ))
    })?;
    validateur::valider_config(&options.config).map_err(Erreur::entree_refusee)?;
    let config = config::lire(&options.config).map_err(Erreur::entree_refusee)?;
    let racine = racine();
    let zone = dossier_zone(&racine, &config.zone)?;
    let especes = racine.join("contracts").join("species.csv");
    let entrees = entrees::Entrees::charger(&options.config, &zone, &especes)?;

    let threads = match options.threads {
        Some(n) => n,
        None => entrees.reglages.threads.unwrap_or(1) as usize,
    };
    let memoire_disponible = match options.memoire_disponible {
        Some(octets) => octets,
        None => memoire::lire_mem_available(Path::new(memoire::MEMINFO))?,
    };
    let inject_nan = match options.inject_nan {
        None => None,
        Some(Some(annee)) => Some(annee),
        Some(None) => Some(entrees.reglages.t0 + 1),
    };
    let lancement = sorties::Lancement {
        threads,
        memoire_disponible,
        inject_nan,
        zone: config.zone.clone(),
        config_sha256: sorties::sha256_hex(&octets),
    };

    let en_cours = zone.join(DOSSIER_EN_COURS);
    retirer(&en_cours)?;
    let resultat = sorties::simuler_et_ecrire(&entrees, &lancement, &en_cours)
        .and_then(|bilan| valider_sorties(&en_cours).map(|_| bilan))
        .and_then(|bilan| publier(&en_cours, &zone).map(|_| bilan));
    if resultat.is_err() {
        // Aucune sortie partielle : l'erreur d'origine prime sur celle du nettoyage.
        let _ = std::fs::remove_dir_all(&en_cours);
    }
    resultat
}

fn retirer(dossier: &Path) -> Result<(), Erreur> {
    if dossier.exists() {
        std::fs::remove_dir_all(dossier).map_err(|e| {
            Erreur::interne(format!("{} impossible à retirer : {e}", dossier.display()))
        })?;
    }
    Ok(())
}

/// Fait valider les quatre sorties d'un dossier `sim` (temporaire). Code 1 si une sortie est
/// refusée (anomalie du programme), code 2 si le validateur ne peut pas être lancé.
pub fn valider_sorties(dossier: &Path) -> Result<(), Erreur> {
    let sorties = [
        ("sim_trees", dossier.join("trees")),
        ("sim_cells", dossier.join("cells")),
        ("sim_flags", dossier.join("flags.parquet")),
        ("run", dossier.join("run.json")),
    ];
    for (contrat, chemin) in sorties {
        let texte = chemin.to_string_lossy().to_string();
        let code = validateur::appeler(&[contrat, texte.as_str()]).map_err(|e| {
            Erreur::entree_refusee(format!("validation des sorties impossible : {e}"))
        })?;
        if code != 0 {
            return Err(Erreur::interne(format!(
                "sortie {} refusée par le validateur (contrat {contrat}, code {code}) : rien n'est publié",
                chemin.display()
            )));
        }
    }
    Ok(())
}

/// Le dossier temporaire devient `<zone>/sim/` ; l'ancien `sim/` n'est retiré qu'ensuite.
fn publier(en_cours: &Path, zone: &Path) -> Result<(), Erreur> {
    let sim = zone.join("sim");
    let ancien = zone.join(DOSSIER_ANCIEN);
    retirer(&ancien)?;
    if sim.exists() {
        std::fs::rename(&sim, &ancien).map_err(|e| {
            Erreur::interne(format!(
                "{} impossible à mettre de côté : {e}",
                sim.display()
            ))
        })?;
    }
    std::fs::rename(en_cours, &sim).map_err(|e| {
        Erreur::interne(format!("publication de {} impossible : {e}", sim.display()))
    })?;
    retirer(&ancien)
}
