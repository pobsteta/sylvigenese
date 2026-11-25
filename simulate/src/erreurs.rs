//! Erreurs de `simulate` et codes de sortie (spec §6, « Codes de sortie » ; plan M3a).
//!
//! Étape du BRIEF codée ici : BRIEF §6 et §13, « signaler plutôt que deviner » : toute
//! impossibilité devient une erreur explicite, avec un code de sortie et un message en
//! français ; jamais de valeur par défaut silencieuse.
//!
//! Les codes (docs/plans/m3a-simulate.md, « Sorties, contrôles, codes ») :
//!
//! | Code | Sens | Exemple |
//! |---|---|---|
//! | 0 | tout va bien | (pas d'erreur : [`crate::SORTIE_OK`]) |
//! | 1 | erreur interne : un invariant du programme est rompu (une anomalie de `simulate`, pas des données) | colonnes de l'état de longueurs différentes |
//! | 2 | entrée refusée | paramètres absents pour une essence, fichier illisible |
//! | 3 | contrôle échoué | NaN, valeur non finie, d130 ≤ 0 |
//! | 4 | mémoire insuffisante, refusée **avant** toute écriture | estimation au-delà de 0,9 × `MemAvailable` |
//!
//! Le code 1 n'est pas nommé par la spec §6, qui ne liste que 2, 3 et 4 ; il est repris du plan
//! M3a pour ne jamais confondre une anomalie du programme avec une entrée refusée.
//!
//! Règle de lisibilité (CLAUDE.md) : pas de macros maison ni de génériques ; une énumération et
//! une structure concrètes.

use std::fmt;

use crate::geotiff::ErreurGeotiff;

/// Les quatre causes d'arrêt de `simulate`, chacune avec son code de sortie.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CodeSortie {
    /// 1 : invariant rompu dans le programme.
    ErreurInterne,
    /// 2 : entrée refusée.
    EntreeRefusee,
    /// 3 : contrôle échoué.
    ControleEchoue,
    /// 4 : mémoire insuffisante.
    MemoireInsuffisante,
}

impl CodeSortie {
    /// Le code de sortie du processus (1, 2, 3 ou 4).
    pub fn valeur(self) -> i32 {
        match self {
            CodeSortie::ErreurInterne => 1,
            CodeSortie::EntreeRefusee => 2,
            CodeSortie::ControleEchoue => 3,
            CodeSortie::MemoireInsuffisante => 4,
        }
    }

    /// Le libellé en français, mis en tête du message d'erreur.
    pub fn libelle(self) -> &'static str {
        match self {
            CodeSortie::ErreurInterne => "erreur interne",
            CodeSortie::EntreeRefusee => "entrée refusée",
            CodeSortie::ControleEchoue => "contrôle échoué",
            CodeSortie::MemoireInsuffisante => "mémoire insuffisante",
        }
    }
}

/// Une erreur : sa cause (donc son code de sortie) et un message en français.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Erreur {
    pub code: CodeSortie,
    pub message: String,
}

impl Erreur {
    /// Code 1 : un invariant du programme est rompu.
    pub fn interne(message: String) -> Erreur {
        Erreur {
            code: CodeSortie::ErreurInterne,
            message,
        }
    }

    /// Code 2 : une entrée est refusée.
    pub fn entree_refusee(message: String) -> Erreur {
        Erreur {
            code: CodeSortie::EntreeRefusee,
            message,
        }
    }

    /// Code 3 : un contrôle a échoué.
    pub fn controle_echoue(message: String) -> Erreur {
        Erreur {
            code: CodeSortie::ControleEchoue,
            message,
        }
    }

    /// Code 4 : la mémoire manque.
    pub fn memoire_insuffisante(message: String) -> Erreur {
        Erreur {
            code: CodeSortie::MemoireInsuffisante,
            message,
        }
    }

    /// Le code de sortie du processus.
    pub fn code_sortie(&self) -> i32 {
        self.code.valeur()
    }
}

/// Affiche « <libellé> (code N) : <message> », par exemple
/// « entrée refusée (code 2) : aucun paramètre growth_gam pour l'essence 09 ».
impl fmt::Display for Erreur {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(
            f,
            "{} (code {}) : {}",
            self.code.libelle(),
            self.code.valeur(),
            self.message
        )
    }
}

impl std::error::Error for Erreur {}

/// Reprise d'une erreur du lecteur GeoTIFF (codes 2 ou 4) ; tout autre code devient une
/// erreur interne, sans deviner.
impl From<ErreurGeotiff> for Erreur {
    fn from(erreur: ErreurGeotiff) -> Erreur {
        match erreur.code {
            2 => Erreur::entree_refusee(erreur.message),
            4 => Erreur::memoire_insuffisante(erreur.message),
            autre => Erreur::interne(format!(
                "code {autre} inattendu du lecteur GeoTIFF : {}",
                erreur.message
            )),
        }
    }
}
