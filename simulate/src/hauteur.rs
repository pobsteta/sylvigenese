//! Hauteur dominante de la cellule, hauteur des arbres et houppiers (plan M3a, pas annuel,
//! point 3 ; spec §4 point 4 et §5).
//!
//! Étape du BRIEF codée ici : BRIEF §6, « Hauteur » : la hauteur dominante d'une cellule évolue
//! selon une courbe de croissance paramétrée par `site_potential.tif`, et la hauteur d'un arbre se
//! déduit de la hauteur dominante et de son rang en diamètre. S'y ajoutent `hcb` et `cw` (BRIEF
//! §4, contrat `sim.trees`), déduits par les allométries de houppier (contrat `parameters`).
//!
//! # Hauteur dominante H_dom d'une cellule
//!
//! - Elle part de `h0.tif` (date de vol) et avance **exactement** de la durée voulue (un an pour
//!   un pas, la durée de la date de vol à t0 pour l'état initial) sur la courbe de l'essence de
//!   plus forte surface terrière de la cellule (T5).
//! - **Chapman-Richards** H(t) = A (1 − e^(−k t))^p, sous forme autonome (sans âge, spec §5) :
//!   avec r = (H / A)^(1/p), H(t + Δ) = A (1 − e^(−k Δ) (1 − r))^p ; **A = `site_potential`**
//!   (plan M3a ; une bande vaut pour toutes les essences, sinon table explicite, T4) ; k et p
//!   viennent de `chapman_richards` ; les termes `A_class1` à `A_class5` ne servent pas ici.
//! - **Korf** pour le hêtre 09 (décision de Pascal, Q1 du 25/11/2026 ; contrat, point 3) :
//!   avec X = [ln(a / H)]^(−1/c), X(t + Δ) = X + p_f · b · Δ et H = a · exp(−X^(−c)) ; pour Δ = 1
//!   c'est la forme récursive du contrat. L'asymptote a est fixe ; la classe de fertilité p_f est
//!   **celle dont la hauteur à l'âge de référence de nemeton est la plus proche de
//!   `site_potential`** (décision de l'orchestrateur sur 033, provisoire, dite au rapport) ; à
//!   égalité, la classe de plus petit numéro. Cette hauteur part de l'âge et de la hauteur de
//!   départ de nemeton ([`ReferenceKorf`]), qui sont des termes provisoires du contrat depuis la
//!   mission 040 (`t_ref0`, `h_ref0`, `age_ref` du modèle `korf`) : sans eux, le moteur refuse
//!   (code 2), il ne les devine pas.
//! - **dH ≥ 0** : on écrit « si dH < 0 alors dH = 0 », sans fonction `min` (spec §5) ; une H_dom
//!   au plafond ou au-dessus est comptée (`cells_at_height_ceiling`) et, au-dessus, signalée,
//!   jamais corrigée. Avec Chapman-Richards, H_dom ne dépasse donc jamais un plafond qu'elle
//!   n'avait pas déjà dépassé ; avec Korf, la courbe continue vers a et le dépassement est signalé.
//!   Une H_dom de Korf qui atteint l'asymptote a n'avance plus (la forme n'y est pas définie) et
//!   est signalée.
//!
//! # Hauteur d'un arbre (décision de Pascal, Q2 du 25/11/2026)
//!
//! La hauteur mesurée par le MNH reste l'ancre : l'arbre grandit de **sa part** de ΔH_dom,
//! dh = f(rel_d) × ΔH_dom, où f est `relative_height_gam` (h / H_dom, lien identité) et
//! rel_d = d130 / d_dom ; « si dh < 0 alors dh = 0 », compté et signalé. d_dom est le diamètre
//! quadratique moyen des 100 plus gros arbres par hectare de la cellule, le dernier comptant pour
//! la part de son poids qui complète les 100 tiges : la définition de `dyn_dominant` de
//! `R/dynamics.R` (`DYN_HDOM_STEMS_HA`, provisoire), qui a servi à l'ajustement.
//!
//! # De la date de vol à t0
//!
//! L'état initial est l'état **à la fin de l'année t0** (le pas de l'année Y part de l'état figé
//! au 1er janvier de Y et rend celui de la fin de Y, écrit sous `year=Y`) : la durée de la date de
//! vol (`chm_date.tif`, jours depuis le 1970-01-01) au 1er janvier de t0 + 1, en années de
//! 365,2425 jours (année grégorienne moyenne). Une date de vol après la fin de t0 est refusée
//! (code 2) : reculer la hauteur serait deviner.
//!
//! Règle de lisibilité (CLAUDE.md) : une énumération et des structures concrètes, fonctions libres,
//! aucune macro maison ni générique.

use crate::erreurs::Erreur;
use crate::parametres::JeuDeParametres;

/// Tiges par hectare de la définition de H_dom et d_dom (`DYN_HDOM_STEMS_HA` de `R/dynamics.R`,
/// provisoire, la même qu'à l'ajustement de `relative_height_gam`).
pub const TIGES_DOMINANTES_HA: f64 = 100.0;

/// Jours d'une année grégorienne moyenne.
pub const JOURS_PAR_AN: f64 = 365.2425;

/// La courbe de hauteur dominante d'une essence.
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum Courbe {
    /// Chapman-Richards : k (1/an) et p ; l'asymptote est `site_potential`.
    ChapmanRichards { k: f64, p: f64 },
    /// Korf : asymptote a (m), b (1/an), exposant c, fertilités des classes 1 à 5.
    Korf {
        a: f64,
        b: f64,
        c: f64,
        p_f: [f64; 5],
    },
}

impl Courbe {
    /// La courbe d'un jeu `chapman_richards` ou `korf`. Code 2 si un terme manque, n'est pas
    /// strictement positif, ou si le modèle n'est pas une courbe de hauteur.
    pub fn depuis_jeu(jeu: &JeuDeParametres) -> Result<Courbe, Erreur> {
        if jeu.modele == "chapman_richards" {
            let k = terme_positif(jeu, "k")?;
            let p = terme_positif(jeu, "p")?;
            return Ok(Courbe::ChapmanRichards { k, p });
        }
        if jeu.modele == "korf" {
            let a = terme_positif(jeu, "a")?;
            let b = terme_positif(jeu, "b")?;
            let c = terme_positif(jeu, "c")?;
            let mut p_f = [0.0; 5];
            for (rang, valeur) in p_f.iter_mut().enumerate() {
                *valeur = terme_positif(jeu, &format!("p_f_class{}", rang + 1))?;
            }
            return Ok(Courbe::Korf { a, b, c, p_f });
        }
        Err(Erreur::entree_refusee(format!(
            "le modèle {} n'est pas une courbe de hauteur (chapman_richards ou korf)",
            jeu.modele
        )))
    }
}

fn terme_positif(jeu: &JeuDeParametres, terme: &str) -> Result<f64, Erreur> {
    let valeur = jeu.scalaire(terme)?;
    if !(valeur > 0.0) {
        return Err(Erreur::entree_refusee(format!(
            "paramètre « {terme} » du modèle {} : {valeur}, il doit être strictement positif",
            jeu.modele
        )));
    }
    Ok(valeur)
}

/// Le point de départ de nemeton pour situer les classes de Korf : âge et hauteur de départ, âge
/// de référence (pour le hêtre chez nemeton : 6 ans, 1,40 ou 1,35 m selon la région, 100 ans).
/// Ce sont les termes `t_ref0`, `h_ref0` et `age_ref` du modèle `korf` du contrat (mission 040,
/// provisoires), lus par `sorties.rs` ; sans eux le moteur refuse (code 2).
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct ReferenceKorf {
    pub age_depart: f64,
    pub hauteur_depart: f64,
    pub age_reference: f64,
}

/// Un pas exact de Chapman-Richards de durée `duree` (années) depuis `h`, asymptote `a`.
/// Rend la hauteur atteinte, sans la règle dH ≥ 0 (au-dessus de `a`, elle redescend vers `a`).
pub fn avance_chapman_richards(h: f64, a: f64, k: f64, p: f64, duree: f64) -> f64 {
    let r = (h / a).powf(1.0 / p);
    let r_suivant = 1.0 - (-k * duree).exp() * (1.0 - r);
    a * r_suivant.powf(p)
}

/// Un pas exact de Korf de durée `duree` (années) depuis `h`, fertilité `p_f`.
/// `None` si `h` n'est pas dans ]0 ; a[ (la forme n'y est pas définie).
pub fn avance_korf(h: f64, a: f64, b: f64, c: f64, p_f: f64, duree: f64) -> Option<f64> {
    if !(h > 0.0 && h < a) {
        return None;
    }
    let x = (a / h).ln().powf(-1.0 / c);
    let x_suivant = x + p_f * b * duree;
    Some(a * (-x_suivant.powf(-c)).exp())
}

/// La hauteur de Korf à l'âge de référence, en partant du point de départ de nemeton.
pub fn hauteur_korf_reference(a: f64, b: f64, c: f64, p_f: f64, reference: &ReferenceKorf) -> f64 {
    let duree = reference.age_reference - reference.age_depart;
    match avance_korf(reference.hauteur_depart, a, b, c, p_f, duree) {
        Some(h) => h,
        None => f64::NAN,
    }
}

/// La classe de Korf (1 à 5) dont la hauteur à l'âge de référence est la plus proche du plafond ;
/// à égalité, la plus petite. Rend la classe et sa fertilité. Code 2 si le point de départ ne
/// convient pas (hauteur de départ hors de ]0 ; a[, âge de référence avant l'âge de départ).
pub fn choisir_classe_korf(
    a: f64,
    b: f64,
    c: f64,
    p_f: &[f64; 5],
    reference: &ReferenceKorf,
    plafond: f64,
) -> Result<(usize, f64), Erreur> {
    let valide = reference.hauteur_depart > 0.0
        && reference.hauteur_depart < a
        && reference.age_reference >= reference.age_depart
        && reference.age_depart.is_finite()
        && reference.age_reference.is_finite();
    if !valide {
        return Err(Erreur::entree_refusee(format!(
            "point de départ de Korf invalide (âge {} ; hauteur {} m ; âge de référence {}) pour a = {a} m",
            reference.age_depart, reference.hauteur_depart, reference.age_reference
        )));
    }
    let mut meilleure = 0;
    let mut ecart_min = f64::INFINITY;
    for (rang, fertilite) in p_f.iter().enumerate() {
        let h = hauteur_korf_reference(a, b, c, *fertilite, reference);
        let ecart = (h - plafond).abs();
        if ecart < ecart_min {
            ecart_min = ecart;
            meilleure = rang;
        }
    }
    Ok((meilleure + 1, p_f[meilleure]))
}

/// Ce que donne l'avance de H_dom d'une cellule.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct AvanceeHdom {
    /// H_dom après l'avance, en m.
    pub h: f64,
    /// ΔH_dom ≥ 0, en m.
    pub delta: f64,
    /// H_dom de départ au plafond ou au-dessus (comptée).
    pub au_plafond: bool,
    /// H_dom de départ strictement au-dessus du plafond (signalée, jamais corrigée).
    pub au_dessus: bool,
    /// dH < 0 mis à 0 (Chapman-Richards au-dessus de l'asymptote).
    pub dh_mis_a_zero: bool,
    /// Korf : H_dom à l'asymptote a ou au-delà, elle n'avance plus (signalée).
    pub au_dela_asymptote: bool,
    /// Korf : la classe de fertilité retenue (1 à 5).
    pub classe_korf: Option<usize>,
}

/// Avance H_dom de `duree` années sur la courbe, avec le plafond `site_potential`.
///
/// Code 3 si H_dom n'est pas finie ou n'est pas strictement positive ; code 2 si le plafond
/// n'est pas fini ou pas strictement positif, ou si la courbe est de Korf sans point de départ.
pub fn avancer_hdom(
    courbe: &Courbe,
    h: f64,
    plafond: f64,
    reference_korf: Option<&ReferenceKorf>,
    duree: f64,
) -> Result<AvanceeHdom, Erreur> {
    if !h.is_finite() || h <= 0.0 {
        return Err(Erreur::controle_echoue(format!(
            "hauteur dominante {h} m non finie ou non strictement positive"
        )));
    }
    if !plafond.is_finite() || plafond <= 0.0 {
        return Err(Erreur::entree_refusee(format!(
            "plafond de hauteur (site_potential) {plafond} m absent ou non strictement positif"
        )));
    }
    let mut resultat = AvanceeHdom {
        h,
        delta: 0.0,
        au_plafond: h >= plafond,
        au_dessus: h > plafond,
        dh_mis_a_zero: false,
        au_dela_asymptote: false,
        classe_korf: None,
    };
    let mut dh = 0.0;
    match courbe {
        Courbe::ChapmanRichards { k, p } => {
            dh = avance_chapman_richards(h, plafond, *k, *p, duree) - h;
        }
        Courbe::Korf { a, b, c, p_f } => {
            let reference = match reference_korf {
                Some(reference) => reference,
                None => return Err(Erreur::entree_refusee(
                    "courbe de Korf sans point de départ de nemeton (âge et hauteur de départ, \
                         âge de référence) : la classe de fertilité ne peut pas être choisie"
                        .to_string(),
                )),
            };
            let (classe, fertilite) = choisir_classe_korf(*a, *b, *c, p_f, reference, plafond)?;
            resultat.classe_korf = Some(classe);
            match avance_korf(h, *a, *b, *c, fertilite, duree) {
                Some(h_suivant) => dh = h_suivant - h,
                None => resultat.au_dela_asymptote = true,
            }
        }
    }
    if dh < 0.0 {
        dh = 0.0;
        resultat.dh_mis_a_zero = true;
    }
    resultat.delta = dh;
    resultat.h = h + dh;
    Ok(resultat)
}

/// Le diamètre dominant d'une cellule : diamètre quadratique moyen des 100 plus gros arbres par
/// hectare, chaque arbre pesant 1 / aire (ha) tiges/ha, le dernier pour la part qui complète les
/// 100 tiges ; à diamètre égal, l'ordre donné (celui de l'état). `None` si la liste est vide.
pub fn diametre_dominant(d130: &[f64], aire_cellule_ha: f64) -> Option<f64> {
    if d130.is_empty() {
        return None;
    }
    let mut ordre: Vec<usize> = (0..d130.len()).collect();
    // Tri stable par diamètre décroissant (comme order(-d130, method = "radix") de R).
    ordre.sort_by(|i, j| d130[*j].total_cmp(&d130[*i]));
    let poids = 1.0 / aire_cellule_ha;
    let mut avant = 0.0;
    let mut somme_poids = 0.0;
    let mut somme_d2 = 0.0;
    for rang in ordre {
        let reste = TIGES_DOMINANTES_HA - avant;
        if reste <= 0.0 {
            break;
        }
        let pris = if poids < reste { poids } else { reste };
        somme_poids += pris;
        somme_d2 += pris * d130[rang] * d130[rang];
        avant += poids;
    }
    Some((somme_d2 / somme_poids).sqrt())
}

/// La hausse de hauteur d'un arbre : f(rel_d) × ΔH_dom, avec « si dh < 0 alors dh = 0 ».
/// Rend la hausse et vrai si elle a été mise à 0.
pub fn hausse_arbre(part: f64, delta_hdom: f64) -> (f64, bool) {
    let dh = part * delta_hdom;
    if dh < 0.0 {
        return (0.0, true);
    }
    (dh, false)
}

/// Jours depuis le 1970-01-01 du 1er janvier d'une année (calendrier grégorien proleptique ;
/// algorithme « days_from_civil » de H. Hinnant).
pub fn jours_au_premier_janvier(annee: i32) -> i64 {
    // Le 1er janvier est compté dans l'année précédente qui commence en mars.
    let y = i64::from(annee) - 1;
    let ere = if y >= 0 { y / 400 } else { (y - 399) / 400 };
    let annee_de_l_ere = y - ere * 400;
    let jour_de_l_annee = 306; // du 1er mars au 1er janvier
    let jour_de_l_ere =
        annee_de_l_ere * 365 + annee_de_l_ere / 4 - annee_de_l_ere / 100 + jour_de_l_annee;
    ere * 146_097 + jour_de_l_ere - 719_468
}

/// La durée, en années, de la date de vol (jours depuis le 1970-01-01) à la fin de l'année t0.
/// Code 2 si la date n'est pas finie ou tombe après la fin de t0.
pub fn annees_de_vol_a_t0(chm_date_jours: f64, t0: i32) -> Result<f64, Erreur> {
    if !chm_date_jours.is_finite() {
        return Err(Erreur::entree_refusee(format!(
            "date de vol (chm_date) absente ou non finie ({chm_date_jours})"
        )));
    }
    let fin_t0 = jours_au_premier_janvier(t0 + 1) as f64;
    let jours = fin_t0 - chm_date_jours;
    if jours < 0.0 {
        return Err(Erreur::entree_refusee(format!(
            "date de vol {chm_date_jours} (jours depuis le 1970-01-01) après la fin de l'année t0 = {t0} : \
             la hauteur ne se recule pas"
        )));
    }
    Ok(jours / JOURS_PAR_AN)
}

/// Allométrie de la base du houppier (contrat `parameters`, modèle `hcb`) :
/// hcb = h × (1 − CR), CR = CR_a + CR_b × ln(d130) borné à [CR_min ; CR_max].
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct AllometrieHcb {
    pub cr_a: f64,
    pub cr_b: f64,
    pub cr_min: f64,
    pub cr_max: f64,
}

impl AllometrieHcb {
    /// Lit les termes CR_a, CR_b, CR_min, CR_max ; code 2 s'il en manque un ou si CR_min > CR_max.
    pub fn depuis_jeu(jeu: &JeuDeParametres) -> Result<AllometrieHcb, Erreur> {
        let allometrie = AllometrieHcb {
            cr_a: jeu.scalaire("CR_a")?,
            cr_b: jeu.scalaire("CR_b")?,
            cr_min: jeu.scalaire("CR_min")?,
            cr_max: jeu.scalaire("CR_max")?,
        };
        if allometrie.cr_min > allometrie.cr_max {
            return Err(Erreur::entree_refusee(format!(
                "allométrie hcb : CR_min ({}) au-dessus de CR_max ({})",
                allometrie.cr_min, allometrie.cr_max
            )));
        }
        Ok(allometrie)
    }

    /// hcb (m) d'un arbre de hauteur h (m) et de diamètre d130 (cm).
    pub fn hcb(&self, h: f64, d130: f64) -> f64 {
        let mut cr = self.cr_a + self.cr_b * d130.ln();
        if cr < self.cr_min {
            cr = self.cr_min;
        }
        if cr > self.cr_max {
            cr = self.cr_max;
        }
        h * (1.0 - cr)
    }
}

/// Allométrie de la largeur du houppier (contrat `parameters`, modèle `cw`) :
/// cw = 2 × E, ln(E) = R_a + R_b × ln(d130).
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct AllometrieCw {
    pub r_a: f64,
    pub r_b: f64,
}

impl AllometrieCw {
    /// Lit les termes R_a et R_b ; code 2 s'il en manque un.
    pub fn depuis_jeu(jeu: &JeuDeParametres) -> Result<AllometrieCw, Erreur> {
        Ok(AllometrieCw {
            r_a: jeu.scalaire("R_a")?,
            r_b: jeu.scalaire("R_b")?,
        })
    }

    /// cw (m) d'un arbre de diamètre d130 (cm).
    pub fn cw(&self, d130: f64) -> f64 {
        2.0 * (self.r_a + self.r_b * d130.ln()).exp()
    }
}
