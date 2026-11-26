//! Régénération par cohortes de semis : paramètres, état, croissance, survie et passage à la
//! futaie (mission 062 ; plan m5a, mission D ; ADR 0006, choix 6 ; décisions de Pascal Q1 à Q4
//! du 26/11/2026 et de l'orchestrateur du même jour).
//!
//! Étape du BRIEF codée ici : BRIEF §7, la chaîne de la régénération, points 2 à 4 :
//! installation, croissance et survie, passage à la futaie. Le point 1 (arrivée des graines) est
//! dans [`crate::dispersion`]. Ce module est le **même pour les deux niveaux** (Q4) : il travaille
//! sur des densités par hectare ; le niveau massif arrondit en arbres (voir [`passage_massif`]),
//! le niveau SER garde les espérances (T4).
//!
//! # Paramètres (contrat `params/regeneration`, aucune valeur ici)
//!
//! Par essence, chaque terme est cherché dans les lignes propres de l'essence, sinon dans celles
//! de son groupe (`groupe` de `contracts/species.csv`), sinon dans `toutes_essences`. Un terme
//! introuvable est une **erreur de code 2** qui nomme l'essence et le terme : aucune valeur
//! d'emprunt (décision de Pascal du 26/11/2026). L'unité de chaque ligne doit être celle du
//! contrat (sinon code 2 : on ne convertit pas en silence).
//!
//! # Semenciers et graines
//!
//! Un arbre vivant est **semencier** si sa hauteur atteint `maturity_height_m` (maturité en
//! hauteur, forme de TreeMig, éq. 13, décision de l'orchestrateur du 26/11/2026). Les graines
//! d'une cellule et d'une essence : `fecundity_seeds_per_m2_ba_yr` × surface terrière des
//! semenciers (m²). Elles sont dispersées ([`crate::dispersion`]), puis une part
//! `establishment_share` des graines arrivées s'installe en semis (installation et première année).
//!
//! # Les cohortes d'une cellule et d'une essence
//!
//! La croissance en hauteur d'un semis est `seedling_height_growth_m_yr` (g, m/an) ; la hauteur de
//! passage est `passage_height_m` (H_p). Le nombre de classes A est le plus petit entier tel que
//! A × g ≥ H_p. Les semis sont rangés en A classes annuelles :
//!
//! - classe k (k = 0 … A − 2) : les semis installés il y a k + 1 ans, hauteur (k + 1) × g ;
//! - classe A − 1 : le **stock à la hauteur de passage** (hauteur A × g ≥ H_p), qui attend son
//!   passage à la futaie.
//!
//! Chaque année ([`avancer`]) : toutes les classes survivent (taux s), montent d'une classe, la
//! classe A − 2 rejoint le stock, les nouveaux semis entrent en classe 0. La croissance ne dépend
//! pas de la lumière en M5a : seule la survie en dépend (Q3, « lumière et ombre seules ») ; un semis
//! du stock ne grandit plus dans ce modèle, son passage est réglé par la règle de Q1.
//!
//! # Survie (Q3 ; forme de TreeMig, éq. 37, 39 et 40, décision de l'orchestrateur du 26/11/2026)
//!
//! - l'**ombre** sur la cellule : o = `light_extinction_coef` × indice de couvert, l'indice étant
//!   la surface des houppiers projetés de la cellule divisée par sa surface (sans unité) ;
//! - le **seuil** est la tolérance à l'ombre de l'essence, `shade_tolerance`, sur l'échelle de
//!   Niinemets et Valladares 2006 (0 à 5), sans règle de conversion vers l'échelle de TreeMig :
//!   c'est le coefficient d'extinction, paramètre provisoire, qui porte l'ombre sur cette échelle ;
//! - mortalité de stress μ̃ = 1 si o > seuil, 0 sinon (TreeMig éq. 39, une seule classe de
//!   lumière par cellule), comptée pour `stress_mortality` × μ̃ (éq. 40) : `stress_mortality` est un
//!   terme du contrat `params/regeneration` (TreeMig éq. 40, p. 16 ; aucune valeur dans le code,
//!   mission 066) ;
//! - survie annuelle s = max(0, `seedling_survival_full_light_yr` − `stress_mortality` × μ̃) : les
//!   mortalités s'additionnent et sont bornées à 1 (éq. 37). Gibier, sous-bois et fructification ne sont pas
//!   simulés (Q3) : `run.json` le dit.
//!
//! # Passage à la futaie (Q1, option a)
//!
//! - **sous couvert** (H_dom de la cellule non nulle) : le flux de recrues est celui du modèle IFN
//!   (`recruitment_gam`, exp(η) tiges/ha/an), **borné par le stock** à la hauteur de passage ; un
//!   manque est compté (`seedling_stock_limited`), jamais comblé ;
//! - **en trouée** (H_dom nulle) : le modèle IFN ne s'applique pas ; tout le stock à la hauteur de
//!   passage passe.
//!
//! # Stock initial « en régime » (Q2, état stationnaire de la dynamique ci-dessus)
//!
//! À t0, sous couvert, le stock est celui d'un **état stationnaire** : avec un flux de passage
//! constant F (flux IFN de t0, tiges/ha/an) et la survie annuelle s de la cellule, une année de
//! [`avancer`] puis de passage de F redonne exactement les mêmes classes. Avec T_p = H_p / g et
//! W = F × (T_p − (A − 1)) le semis qui attend dans le stock après le passage (la part du temps de
//! passage au-delà des A − 1 classes annuelles) :
//!
//! - stock (classe A − 1) : W ;
//! - classe A − 2 : E = (F + W) / s − W (elle rejoint le stock en survivant : (W + E) × s = F + W,
//!   dont F passe et W reste) ;
//! - classe k < A − 2 : c_k = c_{k+1} / s, soit c_k = E × s^−(A − 2 − k).
//!
//! Le total vaut W + E × Σ_{j=0}^{A−2} s^−j. À s = 1, c'est F × T_p, la formule de la décision de
//! Pascal (flux × temps de passage) ; à s < 1, il faut plus de jeunes semis pour qu'il en reste F
//! à la hauteur de passage (c'est la correction de la reprise de 062 : sans elle, le stock partait
//! trop bas pour la survie, et bornait le flux dès les premières années). La première année n'est
//! donc jamais bornée par le stock initial : (W + E) × s = F + W ≥ F. Au niveau massif, où le
//! passage se fait en arbres entiers et où l'arrondi aléatoire du flux IFN peut demander ⌈λ⌉
//! arbres (λ = F × aire de la cellule), le régime est calculé pour F' = ⌈λ⌉ / aire
//! ([`crate::pas::etat_semis_initial`]) : sans cela, un λ de 0,7 donnait un stock de 0,875 arbre et
//! un tirage de 1 était borné dès la première année. Si A = 1 (une seule classe,
//! où les semis installés dans l'année passent l'année même), le stock vaut (F + W) / s, ce qui
//! garantit encore la première année sans connaître les graines de l'année. Si s = 0, aucun état
//! stationnaire n'existe (tout semis meurt dans l'année) : le stock initial est nul, et le manque
//! est compté (`seedling_stock_limited`), jamais comblé. Le stock est **déduit des modèles, non
//! observé** ; il est provisoire et le rapport doit le dire. En trouée, le flux IFN ne s'applique
//! pas : pas de stock initial.
//!
//! Règle de lisibilité (CLAUDE.md) : structures concrètes et fonctions libres, aucune macro maison
//! ni générique.

use crate::erreurs::Erreur;
use crate::parametres::{Referentiel, TOUTES_ESSENCES};

/// Tolérance relative de l'arrondi des arbres offerts par le stock au niveau massif (erreur
/// d'arrondi des f64, sans sens écologique).
pub const TOLERANCE_ARRONDI: f64 = 1e-12;

/// Plus grand nombre de classes annuelles admis (H_p / g) : au-delà, la croissance est sûrement
/// mal saisie (unités) et c'est refusé (code 2).
pub const CLASSES_MAX: usize = 1000;

/// Les termes du contrat `params/regeneration` lus par le moteur, avec leur unité.
pub const TERMES: [(&str, &str); 11] = [
    ("kernel_scale_m", "m"),
    ("kernel_shape", "1"),
    ("maturity_height_m", "m"),
    ("fecundity_seeds_per_m2_ba_yr", "graines/m2/an"),
    ("establishment_share", "1"),
    ("seedling_height_growth_m_yr", "m/an"),
    ("shade_tolerance", "1"),
    ("light_extinction_coef", "1"),
    ("seedling_survival_full_light_yr", "1"),
    ("passage_height_m", "m"),
    ("stress_mortality", "1/an"),
];

/// Une ligne de `params/regeneration.parquet` (contrat `dynamics.regeneration`).
#[derive(Debug, Clone, PartialEq)]
pub struct LigneRegeneration {
    pub species: Option<String>,
    pub species_group: Option<String>,
    pub term: String,
    pub value: f64,
    pub unit: String,
    pub provisoire: bool,
    pub source: String,
}

/// Les paramètres de semis d'une essence, tous présents.
#[derive(Debug, Clone, PartialEq)]
pub struct ParametresSemis {
    pub espece: String,
    /// a du noyau k(r) ∝ exp(−(r / a)^b), m.
    pub echelle_noyau_m: f64,
    /// b du noyau, sans unité.
    pub forme_noyau: f64,
    /// Hauteur à partir de laquelle un arbre est semencier, m.
    pub hauteur_maturite_m: f64,
    /// Graines par m² de surface terrière semencière et par an.
    pub fecondite: f64,
    /// Part des graines arrivées qui s'installent, 0 à 1.
    pub part_installation: f64,
    /// Croissance en hauteur d'un semis, m/an.
    pub croissance_m_an: f64,
    /// Tolérance à l'ombre (Niinemets et Valladares 2006, 0 à 5).
    pub tolerance_ombre: f64,
    /// Coefficient d'extinction de la lumière sous couvert, sans unité.
    pub coef_extinction: f64,
    /// Survie annuelle à pleine lumière, 0 à 1.
    pub survie_pleine_lumiere: f64,
    /// Hauteur de passage à la classe des 7,5 cm, m.
    pub hauteur_passage_m: f64,
    /// Mortalité annuelle de stress d'un semis sous son seuil de lumière, 0 à 1 (TreeMig, éq. 40).
    pub mortalite_stress: f64,
    /// Vrai si au moins un terme lu est provisoire.
    pub provisoire: bool,
}

impl ParametresSemis {
    /// Nombre de classes annuelles A : le plus petit entier ≥ 1 tel que A × g ≥ H_p.
    pub fn classes(&self) -> usize {
        nombre_de_classes(self.hauteur_passage_m, self.croissance_m_an)
    }

    /// Temps de passage T_p = H_p / g, en années (Q2).
    pub fn temps_de_passage(&self) -> f64 {
        self.hauteur_passage_m / self.croissance_m_an
    }

    /// Hauteur des semis de la classe k (k = 0 … A − 1), m.
    pub fn hauteur_classe(&self, k: usize) -> f64 {
        (k + 1) as f64 * self.croissance_m_an
    }
}

/// Le plus petit entier A ≥ 1 tel que A × g ≥ H_p (calcul en f64, dans l'ordre des entiers).
pub fn nombre_de_classes(hauteur_passage_m: f64, croissance_m_an: f64) -> usize {
    let mut a = 1;
    while (a as f64) * croissance_m_an < hauteur_passage_m && a < CLASSES_MAX {
        a += 1;
    }
    a
}

/// Cherche un terme pour une essence : lignes propres, puis groupe, puis `toutes_essences`.
/// Rend (valeur, provisoire). Code 2 si le terme manque partout, s'il est en double à un niveau,
/// ou si son unité n'est pas celle du contrat.
pub fn chercher_terme(
    lignes: &[LigneRegeneration],
    espece: &str,
    referentiel: &Referentiel,
    terme: &str,
    unite: &str,
) -> Result<(f64, bool), Erreur> {
    let groupe = match referentiel.groupe(espece) {
        Some(groupe) => groupe.to_string(),
        None => {
            return Err(Erreur::entree_refusee(format!(
                "params/regeneration : essence {espece} absente de contracts/species.csv : pas de groupe, pas de paramètre de semis"
            )))
        }
    };
    let niveaux: [(Option<&str>, Option<&str>, String); 3] = [
        (Some(espece), None, format!("essence {espece}")),
        (None, Some(groupe.as_str()), format!("groupe {groupe}")),
        (None, Some(TOUTES_ESSENCES), TOUTES_ESSENCES.to_string()),
    ];
    for (essence_cherchee, groupe_cherche, nom_niveau) in &niveaux {
        let mut trouvees: Vec<&LigneRegeneration> = Vec::new();
        for ligne in lignes {
            if ligne.term != terme {
                continue;
            }
            let convient = match (essence_cherchee, groupe_cherche) {
                (Some(code), _) => ligne.species.as_deref() == Some(*code),
                (None, Some(g)) => ligne.species.is_none() && ligne.species_group.as_deref() == Some(*g),
                (None, None) => false,
            };
            if convient {
                trouvees.push(ligne);
            }
        }
        if trouvees.len() > 1 {
            return Err(Erreur::entree_refusee(format!(
                "params/regeneration : terme « {terme} » en double pour {nom_niveau}"
            )));
        }
        if let Some(ligne) = trouvees.first() {
            if ligne.unit != unite {
                return Err(Erreur::entree_refusee(format!(
                    "params/regeneration : terme « {terme} » de {nom_niveau} en « {} », attendu « {unite} » \
                     (aucune conversion n'est devinée)",
                    ligne.unit
                )));
            }
            if !ligne.value.is_finite() {
                return Err(Erreur::entree_refusee(format!(
                    "params/regeneration : terme « {terme} » de {nom_niveau} non fini ({})",
                    ligne.value
                )));
            }
            return Ok((ligne.value, ligne.provisoire));
        }
    }
    Err(Erreur::entree_refusee(format!(
        "params/regeneration : paramètre de semis « {terme} » absent pour l'essence {espece} : ni ses lignes \
         propres, ni le groupe {groupe}, ni {TOUTES_ESSENCES} ; aucune valeur d'emprunt (décision de Pascal du 26/11/2026)"
    )))
}

fn borne(espece: &str, terme: &str, valeur: f64, condition: bool, attendu: &str) -> Result<(), Erreur> {
    if condition {
        return Ok(());
    }
    Err(Erreur::entree_refusee(format!(
        "params/regeneration : essence {espece}, terme « {terme} » = {valeur} ; attendu : {attendu}"
    )))
}

/// Les paramètres de semis d'une essence (tous les termes du contrat). Code 2 si un terme manque
/// ou sort de son domaine (échelle, forme, croissance et hauteur de passage strictement positives ;
/// maturité, fécondité, tolérance et extinction positives ; parts, survie et mortalité de stress entre 0 et 1).
pub fn parametres_de(
    lignes: &[LigneRegeneration],
    espece: &str,
    referentiel: &Referentiel,
) -> Result<ParametresSemis, Erreur> {
    let mut valeurs = [0.0_f64; 11];
    let mut provisoire = false;
    for (rang, (terme, unite)) in TERMES.iter().enumerate() {
        let (valeur, p) = chercher_terme(lignes, espece, referentiel, terme, unite)?;
        valeurs[rang] = valeur;
        provisoire = provisoire || p;
    }
    let p = ParametresSemis {
        espece: espece.to_string(),
        echelle_noyau_m: valeurs[0],
        forme_noyau: valeurs[1],
        hauteur_maturite_m: valeurs[2],
        fecondite: valeurs[3],
        part_installation: valeurs[4],
        croissance_m_an: valeurs[5],
        tolerance_ombre: valeurs[6],
        coef_extinction: valeurs[7],
        survie_pleine_lumiere: valeurs[8],
        hauteur_passage_m: valeurs[9],
        mortalite_stress: valeurs[10],
        provisoire,
    };
    borne(espece, "kernel_scale_m", p.echelle_noyau_m, p.echelle_noyau_m > 0.0, "> 0")?;
    borne(espece, "kernel_shape", p.forme_noyau, p.forme_noyau > 0.0, "> 0")?;
    borne(espece, "maturity_height_m", p.hauteur_maturite_m, p.hauteur_maturite_m >= 0.0, "≥ 0")?;
    borne(espece, "fecundity_seeds_per_m2_ba_yr", p.fecondite, p.fecondite >= 0.0, "≥ 0")?;
    borne(
        espece,
        "establishment_share",
        p.part_installation,
        (0.0..=1.0).contains(&p.part_installation),
        "entre 0 et 1",
    )?;
    borne(espece, "seedling_height_growth_m_yr", p.croissance_m_an, p.croissance_m_an > 0.0, "> 0")?;
    borne(espece, "shade_tolerance", p.tolerance_ombre, p.tolerance_ombre >= 0.0, "≥ 0")?;
    borne(espece, "light_extinction_coef", p.coef_extinction, p.coef_extinction >= 0.0, "≥ 0")?;
    borne(
        espece,
        "seedling_survival_full_light_yr",
        p.survie_pleine_lumiere,
        (0.0..=1.0).contains(&p.survie_pleine_lumiere),
        "entre 0 et 1",
    )?;
    borne(espece, "passage_height_m", p.hauteur_passage_m, p.hauteur_passage_m > 0.0, "> 0")?;
    borne(
        espece,
        "stress_mortality",
        p.mortalite_stress,
        (0.0..=1.0).contains(&p.mortalite_stress),
        "entre 0 et 1",
    )?;
    if p.temps_de_passage() >= CLASSES_MAX as f64 {
        return Err(Erreur::entree_refusee(format!(
            "params/regeneration : essence {espece} : passage_height_m / seedling_height_growth_m_yr = {} ans, \
             plus de {CLASSES_MAX} classes annuelles (unités ?)",
            p.temps_de_passage()
        )));
    }
    Ok(p)
}

// ------------------------------------------------------------------------------------------
// Survie

/// L'ombre sur une cellule : coefficient d'extinction × indice de couvert (sans unité).
pub fn ombre(coef_extinction: f64, indice_couvert: f64) -> f64 {
    coef_extinction * indice_couvert
}

/// La survie annuelle d'un semis (forme de TreeMig, éq. 37, 39, 40) : s_pleine − `stress_mortality`
/// si l'ombre dépasse la tolérance, s_pleine sinon ; bornée à 0.
pub fn survie(parametres: &ParametresSemis, ombre_cellule: f64) -> f64 {
    let stress = if ombre_cellule > parametres.tolerance_ombre { 1.0 } else { 0.0 };
    (parametres.survie_pleine_lumiere - parametres.mortalite_stress * stress).max(0.0)
}

// ------------------------------------------------------------------------------------------
// Cohortes

/// Le stock initial « en régime » d'une cellule (Q2) pour un flux IFN F (tiges/ha/an), à la survie
/// à pleine lumière de l'essence (`seedling_survival_full_light_yr`). Voir
/// [`en_regime_avec_survie`] ; à préférer quand la survie de la cellule (son ombre) est connue.
pub fn en_regime(parametres: &ParametresSemis, flux_ha: f64, classes: &mut [f64]) {
    en_regime_avec_survie(parametres, flux_ha, parametres.survie_pleine_lumiere, classes);
}

/// Le stock initial « en régime » d'une cellule (Q2) : l'état stationnaire de [`avancer`] suivi du
/// passage d'un flux constant F, à la survie annuelle `survie_annuelle` (voir la documentation du
/// module pour la formule). `classes` reçoit les A valeurs. Survie nulle (ou non finie) : classes
/// nulles, aucun état stationnaire n'existe.
pub fn en_regime_avec_survie(parametres: &ParametresSemis, flux_ha: f64, survie_annuelle: f64, classes: &mut [f64]) {
    let a = classes.len();
    for valeur in classes.iter_mut() {
        *valeur = 0.0;
    }
    if a == 0 || !(survie_annuelle > 0.0) || !survie_annuelle.is_finite() {
        return;
    }
    let attente = flux_ha * (parametres.temps_de_passage() - (a - 1) as f64).max(0.0);
    if a == 1 {
        classes[0] = (flux_ha + attente) / survie_annuelle;
        return;
    }
    classes[a - 1] = attente;
    classes[a - 2] = (flux_ha + attente) / survie_annuelle - attente;
    let mut k = a - 2;
    while k > 0 {
        classes[k - 1] = classes[k] / survie_annuelle;
        k -= 1;
    }
}

/// Une année de croissance et de survie des classes d'une cellule : chaque classe survit (s),
/// monte d'une classe, la classe A − 2 rejoint le stock (classe A − 1), `nouveaux` (semis/ha
/// installés dans l'année) entrent en classe 0 (ou dans le stock si A = 1).
pub fn avancer(classes: &mut [f64], survie_annuelle: f64, nouveaux: f64) {
    let a = classes.len();
    if a == 0 {
        return;
    }
    if a == 1 {
        classes[0] = classes[0] * survie_annuelle + nouveaux;
        return;
    }
    classes[a - 1] = (classes[a - 1] + classes[a - 2]) * survie_annuelle;
    let mut k = a - 2;
    while k > 0 {
        classes[k] = classes[k - 1] * survie_annuelle;
        k -= 1;
    }
    classes[0] = nouveaux;
}

/// Le stock à la hauteur de passage d'une cellule (semis/ha).
pub fn stock(classes: &[f64]) -> f64 {
    match classes.last() {
        Some(valeur) => *valeur,
        None => 0.0,
    }
}

/// Le total des semis d'une cellule (semis/ha), en ordre fixe.
pub fn total(classes: &[f64]) -> f64 {
    let mut somme = 0.0;
    for valeur in classes {
        somme += *valeur;
    }
    somme
}

/// La hauteur moyenne des semis d'une cellule, pondérée par les densités ; `None` sans semis.
pub fn hauteur_moyenne(parametres: &ParametresSemis, classes: &[f64]) -> Option<f64> {
    let mut somme = 0.0;
    let mut poids = 0.0;
    for (k, valeur) in classes.iter().enumerate() {
        somme += *valeur * parametres.hauteur_classe(k);
        poids += *valeur;
    }
    if poids > 0.0 {
        Some(somme / poids)
    } else {
        None
    }
}

/// Passage en espérance (niveau SER, T4) : sous couvert, R = min(F, stock) ; en trouée, tout le
/// stock passe. Rend (recrues/ha, vrai si le stock a borné le flux). Le stock est diminué d'autant.
pub fn passage_esperance(classes: &mut [f64], flux_ha: Option<f64>) -> (f64, bool) {
    let a = classes.len();
    if a == 0 {
        return (0.0, false);
    }
    let disponible = classes[a - 1];
    match flux_ha {
        Some(flux) => {
            if disponible < flux {
                classes[a - 1] = 0.0;
                (disponible, true)
            } else {
                classes[a - 1] = disponible - flux;
                (flux, false)
            }
        }
        None => {
            classes[a - 1] = 0.0;
            (disponible, false)
        }
    }
}

/// Passage au niveau massif, en arbres entiers : `demandees` est le nombre tiré du flux IFN
/// (arrondi aléatoire, sous couvert) ou `None` en trouée. Le stock offre ⌊stock × aire⌋ arbres ;
/// sous couvert, n = min(demandées, offertes), et le manque est signalé par le booléen rendu ; en
/// trouée, n = offertes. Le stock est diminué de n / aire (jamais sous 0).
pub fn passage_massif(classes: &mut [f64], aire_ha: f64, demandees: Option<u64>) -> (u64, bool) {
    let a = classes.len();
    if a == 0 {
        return (0, demandees.unwrap_or(0) > 0);
    }
    let disponible = classes[a - 1];
    // Tolérance d'arrondi (calcul, pas écologie) : un stock de 2,9999999999999996 arbres en offre 3.
    let offertes = (disponible * aire_ha * (1.0 + TOLERANCE_ARRONDI)).floor().max(0.0) as u64;
    let (n, borne) = match demandees {
        Some(d) => {
            if offertes < d {
                (offertes, true)
            } else {
                (d, false)
            }
        }
        None => (offertes, false),
    };
    classes[a - 1] = (disponible - n as f64 / aire_ha).max(0.0);
    (n, borne)
}
