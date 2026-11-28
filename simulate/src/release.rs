//! La release dont vient `simulate` (mission 087, décision de Pascal du 27/11/2026).
//!
//! Étape du BRIEF codée ici : BRIEF §13 (rejouable : chaque sortie dit d'où elle vient). La
//! valeur est écrite dans `run.json` (clé `release`) et affichée par `simulate --version`.
//!
//! Elle est lue **à la compilation** par `build.rs`, qui inclut ce fichier tel quel :
//!
//! 1. `git describe --tags --dirty` à la racine du dépôt, sur les seules étiquettes
//!    `vAAAA.MM.N` (exact entre deux releases : `v2026.11.17` sur le commit étiqueté, `v2026.11.17-3-gabc1234` trois commits
//!    plus loin, `-dirty` si l'arbre de travail est modifié) ;
//! 2. sinon (pas de git, pas d'étiquette, copie `git archive`, archive de release), la variable
//!    d'environnement `SYLVIGENESE_RELEASE` si elle est posée (par la CI ou l'utilisateur), au
//!    même format, sinon la compilation échoue ;
//! 3. sinon `inconnue`.
//!
//! Les cas 2 et 3 sont signalés (avertissement de cargo, et message sur stderr à chaque exécution
//! pour `inconnue`). Le numéro des manifestes (`Cargo.toml`) n'est **jamais** pris à la place :
//! il dit la release visée, pas celle dont vient le code compilé.
//!
//! Ce fichier ne dépend de rien d'autre du moteur (il est compilé aussi dans `build.rs`).

use std::path::Path;
use std::process::Command;

/// La valeur écrite quand ni git ni `SYLVIGENESE_RELEASE` ne disent la release.
pub const INCONNUE: &str = "inconnue";

/// Le nom de la variable d'environnement lue quand git ne dit rien.
pub const VARIABLE: &str = "SYLVIGENESE_RELEASE";

/// Le motif d'étiquette passé à `git describe --match` (étiquettes calendaires seulement).
pub const MOTIF_ETIQUETTE: &str = "v[0-9][0-9][0-9][0-9].[0-9][0-9].[0-9]*";

/// Le motif passé à `git describe --exclude` : écarte `v2026.11.5-rc1` et autres suffixes.
pub const MOTIF_EXCLU: &str = "v*[!0-9.]*";

/// Vrai si `texte` est un nom de release : `vAAAA.MM.N`, suivi au besoin de `-K-g<empreinte>`
/// (commits depuis l'étiquette, empreinte hexadécimale abrégée) puis de `-dirty`.
pub fn est_une_release(texte: &str) -> bool {
    let reste = match texte.strip_suffix("-dirty") {
        Some(avant) => avant,
        None => texte,
    };
    let mut morceaux = reste.split('-');
    let etiquette = morceaux.next().unwrap_or("");
    if !est_une_etiquette(etiquette) {
        return false;
    }
    match (morceaux.next(), morceaux.next(), morceaux.next()) {
        (None, None, None) => true,
        (Some(commits), Some(empreinte), None) => {
            let empreinte_ok = match empreinte.strip_prefix('g') {
                Some(hexa) => {
                    hexa.len() >= 4 && hexa.chars().all(|c| c.is_ascii_hexdigit() && !c.is_ascii_uppercase())
                }
                None => false,
            };
            que_des_chiffres(commits) && empreinte_ok
        }
        _ => false,
    }
}

/// Vrai si `texte` est une étiquette calendaire `vAAAA.MM.N` (N entier positif).
pub fn est_une_etiquette(texte: &str) -> bool {
    let corps = match texte.strip_prefix('v') {
        Some(corps) => corps,
        None => return false,
    };
    let parties: Vec<&str> = corps.split('.').collect();
    if parties.len() != 3 {
        return false;
    }
    let mois_ok = match parties[1].parse::<u32>() {
        Ok(mois) => parties[1].len() == 2 && (1..=12).contains(&mois),
        Err(_) => false,
    };
    parties[0].len() == 4 && que_des_chiffres(parties[0]) && mois_ok && que_des_chiffres(parties[2])
}

fn que_des_chiffres(texte: &str) -> bool {
    !texte.is_empty() && texte.chars().all(|c| c.is_ascii_digit())
}

/// Ce que dit git de la release du dépôt dont `racine` est la racine. Erreur (avec la raison,
/// en français) si git manque, si `racine` n'est pas la racine d'un dépôt git (par exemple une
/// copie `git archive` posée dans un autre dépôt) ou s'il n'y a aucune étiquette calendaire.
pub fn decrire_par_git(racine: &Path) -> Result<String, String> {
    let haut = lancer_git(racine, &["rev-parse", "--show-toplevel"])?;
    let haut_canonique = std::fs::canonicalize(&haut).map_err(|e| format!("{haut} illisible : {e}"))?;
    let racine_canonique =
        std::fs::canonicalize(racine).map_err(|e| format!("{} illisible : {e}", racine.display()))?;
    if haut_canonique != racine_canonique {
        return Err(format!(
            "{} n'est pas la racine d'un dépôt git (git voit le dépôt {haut})",
            racine.display()
        ));
    }
    let decrit = lancer_git(racine, &[
            "describe",
            "--tags",
            "--match",
            MOTIF_ETIQUETTE,
            "--exclude",
            MOTIF_EXCLU,
            "--dirty",
        ])?;
    if !est_une_release(&decrit) {
        return Err(format!("git describe dit « {decrit} », qui n'est pas de la forme vAAAA.MM.N"));
    }
    Ok(decrit)
}

fn lancer_git(dossier: &Path, arguments: &[&str]) -> Result<String, String> {
    let sortie = Command::new("git")
        .arg("-C")
        .arg(dossier)
        .args(arguments)
        .output()
        .map_err(|e| format!("git introuvable ({e})"))?;
    if !sortie.status.success() {
        let message = String::from_utf8_lossy(&sortie.stderr).trim().to_string();
        return Err(format!("git {} a échoué : {message}", arguments.join(" ")));
    }
    Ok(String::from_utf8_lossy(&sortie.stdout).trim().to_string())
}

/// La release retenue et les avertissements à dire, à partir de ce que dit git et de la valeur
/// de `SYLVIGENESE_RELEASE` (`None` si elle n'est pas posée). Erreur si la variable est posée
/// mais n'a pas la forme d'une release (jamais de valeur devinée).
pub fn choisir(git: Result<String, String>, variable: Option<String>) -> Result<(String, Vec<String>), String> {
    match git {
        Ok(decrit) => {
            let mut avertissements = Vec::new();
            if let Some(valeur) = variable {
                if valeur != decrit {
                    avertissements.push(format!(
                        "{VARIABLE}=« {valeur} » ignorée : git dit {decrit}, qui prime"
                    ));
                }
            }
            Ok((decrit, avertissements))
        }
        Err(raison) => match variable {
            Some(valeur) => {
                if est_une_release(&valeur) {
                    let avertissement =
                        format!("release prise de {VARIABLE} ({valeur}), git ne la dit pas : {raison}");
                    Ok((valeur, vec![avertissement]))
                } else {
                    Err(format!(
                        "{VARIABLE}=« {valeur} » n'est pas une release (attendu vAAAA.MM.N, \
                         au besoin suivi de -K-g<empreinte> et de -dirty)"
                    ))
                }
            }
            None => {
                let avertissement = format!(
                    "release inconnue : {raison} ; run.json dira « {INCONNUE} » (poser {VARIABLE} pour la dire)"
                );
                Ok((INCONNUE.to_string(), vec![avertissement]))
            }
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn les_formes_de_git_describe_sont_des_releases() {
        for texte in [
            "v2026.11.17",
            "v2026.11.17-dirty",
            "v2026.11.17-3-gabc1234",
            "v2026.11.17-107-gb452f8c-dirty",
            "v2026.12.1",
        ] {
            assert!(est_une_release(texte), "{texte}");
        }
    }

    #[test]
    fn le_reste_n_est_pas_une_release() {
        for texte in [
            "",
            "inconnue",
            "2026.11.17",
            "v2026.11",
            "v2026.13.1",
            "v2026.1.1",
            "v26.11.1",
            "v2026.11.5-rc1",
            "v2026.11.17-3",
            "v2026.11.17-3-abc1234",
            "v2026.11.17-3-gABC1234",
            "v2026.11.17-x-gabc1234",
            "v2026.11.17-dirty-dirty",
            "v0.0.1",
        ] {
            assert!(!est_une_release(texte), "{texte}");
        }
    }

    #[test]
    fn git_prime_et_une_variable_differente_est_signalee() {
        let (valeur, avert) = choisir(Ok("v2026.11.17-3-gabc1234".into()), None).unwrap();
        assert_eq!(valeur, "v2026.11.17-3-gabc1234");
        assert!(avert.is_empty());
        let (valeur, avert) =
            choisir(Ok("v2026.11.17".into()), Some("v2026.11.18".into())).unwrap();
        assert_eq!(valeur, "v2026.11.17");
        assert_eq!(avert.len(), 1);
        assert!(avert[0].contains("ignorée"), "{avert:?}");
    }

    #[test]
    fn sans_git_la_variable_est_prise_et_signalee() {
        let (valeur, avert) = choisir(Err("pas de dépôt".into()), Some("v2026.11.18".into())).unwrap();
        assert_eq!(valeur, "v2026.11.18");
        assert!(avert[0].contains(VARIABLE) && avert[0].contains("pas de dépôt"), "{avert:?}");
    }

    #[test]
    fn sans_git_une_variable_mal_formee_est_refusee() {
        for valeur in ["", "0.0.1", "2026.11.18", "inconnue"] {
            let erreur = choisir(Err("pas de dépôt".into()), Some(valeur.into())).unwrap_err();
            assert!(erreur.contains(VARIABLE), "{erreur}");
        }
    }

    #[test]
    fn sans_git_ni_variable_la_release_est_inconnue_et_signalee() {
        let (valeur, avert) = choisir(Err("pas de dépôt".into()), None).unwrap();
        assert_eq!(valeur, INCONNUE);
        assert!(avert[0].contains("inconnue") && avert[0].contains("pas de dépôt"), "{avert:?}");
    }
}
