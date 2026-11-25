//! Aléa de `simulate` : générateur à compteur chaîné (spec §6, « Aléa » ; plan M3a, T1).
//!
//! Étape du BRIEF codée ici : BRIEF §6 (mortalité tirée selon le risque annuel, nombre et
//! position des recrues) et l'exigence « rejouable » de BRIEF §13 : un même `config.yml` (donc
//! une même graine) donne les mêmes sorties au bit près, **quel que soit le nombre de fils**.
//!
//! Un tirage ne dépend que de ses cinq clés, jamais de l'ordre des calculs :
//!
//! ```text
//! mix(x)  = SplitMix64 : x' = x + 0x9E3779B97F4A7C15 (modulo 2^64), puis
//!           z = (x' ⊕ (x' >> 30)) × 0xBF58476D1CE4E5B9
//!           z = (z  ⊕ (z  >> 27)) × 0x94D049BB133111EB
//!           mix(x) = z ⊕ (z >> 31)
//! z = mix(mix(mix(mix(mix(graine) ⊕ année) ⊕ entité) ⊕ essence) ⊕ sorte)
//! u = (z >> 11) × 2^-53        dans [0, 1)
//! ```
//!
//! - toute l'arithmétique est sur des entiers non signés de 64 bits, modulo 2^64 ;
//! - `année` est un `i32` converti en complément à deux sur 64 bits (−1 donne 2^64 − 1) ;
//! - `entité` est le numéro stable de l'arbre (module [`crate::etat`]) ou le `cell_id` ;
//! - `essence` est le code espar **packé** en u64 : ses octets ASCII lus de gauche à droite,
//!   en base 256 (« 09 » → 0x3039, « 53CA » → 0x35334341) ; voir [`packer_essence`] ;
//! - `sorte` : 1 MORT, 2 NB_RECRUES, 3 RECRUE_X, 4 RECRUE_Y ([`Sorte`]).
//!
//! Les constantes sont celles de SplitMix64 (Steele, Lea et Flood, « Fast splittable
//! pseudorandom number generators », OOPSLA 2014), déjà employées par le banc
//! (`bench/SPEC.md` §2) ; le chaînage remplace le simple « ou exclusif » du banc pour que deux
//! clés ne puissent pas s'annuler l'une l'autre. Contrôle : `mix(0)` vaut 0xE220A8397B1DCDAF,
//! la première sortie connue de SplitMix64 à l'état 0.
//!
//! # Table de référence
//!
//! Calculée indépendamment (Python, entiers exacts) le 25/11/2026 et vérifiée au bit près par
//! `tests/alea.rs` ; une autre implémentation (R, Python) doit la redonner à l'identique.
//!
//! | graine | année | entité | essence (packée) | sorte | u |
//! |---|---|---|---|---|---|
//! | 0 | 0 | 0 | 09 (0x3039) | 1 | 0.48056368115436876 |
//! | 42 | 2021 | 0 | 09 (0x3039) | 1 | 0.06895494909539879 |
//! | 42 | 2022 | 0 | 09 (0x3039) | 1 | 0.4503299362101849 |
//! | 42 | 2021 | 1 | 09 (0x3039) | 1 | 0.30124461246969614 |
//! | 42 | 2021 | 0 | 02 (0x3032) | 1 | 0.7497589962937468 |
//! | 42 | 2021 | 0 | 09 (0x3039) | 2 | 0.07547703664965388 |
//! | 42 | 2021 | 0 | 09 (0x3039) | 3 | 0.07052374013721907 |
//! | 42 | 2021 | 0 | 09 (0x3039) | 4 | 0.5321586419134955 |
//! | 20261125 | 2021 | 12345 | 61 (0x3631) | 1 | 0.27819323804150864 |
//! | 20261125 | 2021 | 12345 | 61 (0x3631) | 2 | 0.9476109114532498 |
//! | 20261125 | 2050 | 999999 | 53CA (0x35334341) | 3 | 0.29362229884891977 |
//! | 20261125 | 2050 | 999999 | 53CA (0x35334341) | 4 | 0.029784762073752136 |
//! | 1 | −1 | 0 | 09 (0x3039) | 1 | 0.8490581469247986 |
//! | 2^64 − 1 | 2100 | 2^64 − 1 | 62 (0x3632) | 1 | 0.9707035288058078 |
//! | 7 | 0 | 0 | 15S (0x313553) | 1 | 0.9040441808514458 |
//! | 123456789 | 2030 | 1535 | 17C (0x313743) | 2 | 0.008639326053565544 |
//! | 42 | 2021 | 7 | 05 (0x3035) | 1 | 0.6521829738191267 |
//! | 42 | 2021 | 8 | 05 (0x3035) | 1 | 0.7265085658991912 |
//! | 99 | 2025 | 2^32 | 52 (0x3532) | 4 | 0.5117011474945781 |
//! | 2^63 | 1999 | 31 | 10 (0x3130) | 3 | 0.3806009485614703 |
//! | 5 | 2040 | 77 | 23AB (0x32334142) | 2 | 0.018409045937601398 |
//!
//! Règle de lisibilité (CLAUDE.md) : des fonctions libres sur des `u64`, sans générique ni trait.

use crate::erreurs::Erreur;

const GAMMA: u64 = 0x9E37_79B9_7F4A_7C15;
const MULT_1: u64 = 0xBF58_476D_1CE4_E5B9;
const MULT_2: u64 = 0x94D0_49BB_1331_11EB;

/// La sorte de tirage : une même entité tire des nombres indépendants pour chaque usage.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Sorte {
    /// 1 : l'arbre meurt-il cette année ?
    Mort,
    /// 2 : arrondi aléatoire du nombre de recrues d'une cellule et d'une essence.
    NbRecrues,
    /// 3 : abscisse (est) d'une recrue dans sa cellule.
    RecrueX,
    /// 4 : ordonnée (nord) d'une recrue dans sa cellule.
    RecrueY,
}

impl Sorte {
    /// Le numéro de la sorte dans la formule (1 à 4).
    pub fn valeur(self) -> u64 {
        match self {
            Sorte::Mort => 1,
            Sorte::NbRecrues => 2,
            Sorte::RecrueX => 3,
            Sorte::RecrueY => 4,
        }
    }
}

/// Une étape de SplitMix64 : ajout de la constante d'or, puis mélange des bits.
pub fn mix(x: u64) -> u64 {
    let x = x.wrapping_add(GAMMA);
    let z = (x ^ (x >> 30)).wrapping_mul(MULT_1);
    let z = (z ^ (z >> 27)).wrapping_mul(MULT_2);
    z ^ (z >> 31)
}

/// Le code espar packé en u64 (octets ASCII en base 256, de gauche à droite).
///
/// Refuse (code 2) un code hors du motif du contrat `[0-9]{2}[A-Z0-9]{0,3}` : on ne devine pas.
pub fn packer_essence(code: &str) -> Result<u64, Erreur> {
    let octets = code.as_bytes();
    let longueur_admise = octets.len() >= 2 && octets.len() <= 5;
    let mut conforme = longueur_admise;
    if longueur_admise {
        for (rang, octet) in octets.iter().enumerate() {
            let chiffre = octet.is_ascii_digit();
            let majuscule = octet.is_ascii_uppercase();
            if rang < 2 && !chiffre {
                conforme = false;
            }
            if rang >= 2 && !(chiffre || majuscule) {
                conforme = false;
            }
        }
    }
    if !conforme {
        return Err(Erreur::entree_refusee(format!(
            "code d'essence « {code} » hors du motif espar [0-9]{{2}}[A-Z0-9]{{0,3}} (contracts/species.csv)"
        )));
    }
    let mut valeur: u64 = 0;
    for octet in octets {
        valeur = (valeur << 8) | u64::from(*octet);
    }
    Ok(valeur)
}

/// Le nombre aléatoire u dans [0, 1) des clés (graine, année, entité, essence packée, sorte).
pub fn u(graine: u64, annee: i32, entite: u64, essence: u64, sorte: Sorte) -> f64 {
    let annee_u64 = i64::from(annee) as u64;
    let mut z = mix(graine);
    z = mix(z ^ annee_u64);
    z = mix(z ^ entite);
    z = mix(z ^ essence);
    z = mix(z ^ sorte.valeur());
    // 2^-53, exact en f64.
    let deux_puissance_moins_53 = 1.0 / 9_007_199_254_740_992.0;
    ((z >> 11) as f64) * deux_puissance_moins_53
}
