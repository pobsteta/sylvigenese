//! État des arbres simulés, rangé en colonnes (plan M3a : « le pas annuel », « aléa et
//! identité entre fils »).
//!
//! Étape du BRIEF codée ici : BRIEF §6 et §8, l'état de la forêt que le pas annuel fait
//! évoluer (diamètre, hauteur, mort, recrues), un arbre par rang.
//!
//! - Une colonne par grandeur (`Vec<f64>` pour x, y, d130, h) : le pas annuel lit l'état figé
//!   au 1er janvier et écrit ses mises à jour dans des colonnes séparées (mission 037).
//! - Ordre des axes : `x` = est, `y` = nord, en mètres, **EPSG:2154** (Lambert-93).
//! - **Numéro stable** : les arbres initiaux sont triés par `tree_id` (ordre des octets) et
//!   numérotés 0, 1, 2… ; les recrues d'une année reçoivent les numéros suivants par une somme
//!   de préfixes séquentielle sur les comptes par cellule ([`premiers_numeros`]), en ordre fixe.
//!   Le numéro sert d'`entité` à l'aléa ([`crate::alea`]) : il ne dépend jamais du nombre de fils.
//!   Un numéro n'est jamais réattribué, même après le retrait des morts.
//! - Toute réservation passe par `try_reserve_exact` : un manque de mémoire donne le code 4,
//!   jamais un arrêt brutal du noyau (spec §6).
//!
//! Règle de lisibilité (CLAUDE.md) : une structure concrète, des colonnes nommées, aucune macro
//! maison ni générique.

use std::collections::HashSet;

use crate::alea::packer_essence;
use crate::erreurs::Erreur;
use crate::memoire;

/// Octets fixes d'un arbre dans l'état : sept colonnes de 8 octets (numéro, essence packée,
/// cellule, x, y, d130, h), un booléen (vivant) et deux en-têtes de chaîne (tree_id, essence).
/// Le texte des chaînes s'y ajoute ([`EtatArbres::octets_texte`]).
pub const OCTETS_FIXES_PAR_ARBRE: u64 =
    (7 * std::mem::size_of::<u64>() + 1 + 2 * std::mem::size_of::<String>()) as u64;

/// Un arbre à ajouter à l'état (initial, lu dans `trees_init`, ou recrue).
#[derive(Debug, Clone, PartialEq)]
pub struct ArbreNouveau {
    pub tree_id: String,
    /// Code espar (contracts/species.csv).
    pub espece: String,
    /// `cell_id` de la grille (affecté par la lecture des entrées, mission 036).
    pub cellule: u64,
    /// Est, en m, EPSG:2154.
    pub x: f64,
    /// Nord, en m, EPSG:2154.
    pub y: f64,
    /// Diamètre à 1,30 m, en cm.
    pub d130: f64,
    /// Hauteur, en m.
    pub h: f64,
}

/// L'état des arbres en colonnes ; toutes les colonnes ont la même longueur.
#[derive(Debug, Clone, PartialEq, Default)]
pub struct EtatArbres {
    pub numero: Vec<u64>,
    pub tree_id: Vec<String>,
    pub espece: Vec<String>,
    /// L'essence packée pour l'aléa ([`crate::alea::packer_essence`]).
    pub espece_packee: Vec<u64>,
    pub cellule: Vec<u64>,
    pub x: Vec<f64>,
    pub y: Vec<f64>,
    pub d130: Vec<f64>,
    pub h: Vec<f64>,
    pub vivant: Vec<bool>,
    /// Le numéro que recevra le prochain arbre ajouté.
    prochain: u64,
}

impl EtatArbres {
    /// Un état vide ; le premier arbre ajouté aura le numéro 0.
    pub fn vide() -> EtatArbres {
        EtatArbres::default()
    }

    /// Construit l'état initial : tri par `tree_id`, numéros 0 … n − 1, tous vivants.
    ///
    /// Code 2 si un `tree_id` est vide ou en double, ou si un code d'essence est hors motif ;
    /// code 4 si la mémoire manque.
    pub fn depuis_initiaux(mut arbres: Vec<ArbreNouveau>) -> Result<EtatArbres, Erreur> {
        arbres.sort_by(|a, b| a.tree_id.as_bytes().cmp(b.tree_id.as_bytes()));
        for paire in arbres.windows(2) {
            if paire[0].tree_id == paire[1].tree_id {
                return Err(Erreur::entree_refusee(format!(
                    "tree_id « {} » en double dans l'état initial",
                    paire[0].tree_id
                )));
            }
        }
        let mut etat = EtatArbres::vide();
        etat.reserver(arbres.len())?;
        for arbre in arbres {
            let numero = etat.prochain;
            etat.ajouter(numero, arbre)?;
        }
        Ok(etat)
    }

    /// Le nombre d'arbres de l'état.
    pub fn len(&self) -> usize {
        self.numero.len()
    }

    /// Vrai si l'état n'a aucun arbre.
    pub fn is_empty(&self) -> bool {
        self.numero.is_empty()
    }

    /// Le numéro que recevra le prochain arbre ajouté.
    pub fn prochain_numero(&self) -> u64 {
        self.prochain
    }

    /// Réserve la place de `supplementaires` arbres dans chaque colonne. Code 4 si elle manque.
    pub fn reserver(&mut self, supplementaires: usize) -> Result<(), Erreur> {
        let quoi = "arbres de l'état";
        self.numero
            .try_reserve_exact(supplementaires)
            .map_err(|_| memoire::erreur_allocation(supplementaires, quoi))?;
        self.tree_id
            .try_reserve_exact(supplementaires)
            .map_err(|_| memoire::erreur_allocation(supplementaires, quoi))?;
        self.espece
            .try_reserve_exact(supplementaires)
            .map_err(|_| memoire::erreur_allocation(supplementaires, quoi))?;
        self.espece_packee
            .try_reserve_exact(supplementaires)
            .map_err(|_| memoire::erreur_allocation(supplementaires, quoi))?;
        self.cellule
            .try_reserve_exact(supplementaires)
            .map_err(|_| memoire::erreur_allocation(supplementaires, quoi))?;
        self.x
            .try_reserve_exact(supplementaires)
            .map_err(|_| memoire::erreur_allocation(supplementaires, quoi))?;
        self.y
            .try_reserve_exact(supplementaires)
            .map_err(|_| memoire::erreur_allocation(supplementaires, quoi))?;
        self.d130
            .try_reserve_exact(supplementaires)
            .map_err(|_| memoire::erreur_allocation(supplementaires, quoi))?;
        self.h
            .try_reserve_exact(supplementaires)
            .map_err(|_| memoire::erreur_allocation(supplementaires, quoi))?;
        self.vivant
            .try_reserve_exact(supplementaires)
            .map_err(|_| memoire::erreur_allocation(supplementaires, quoi))?;
        Ok(())
    }

    /// Ajoute un arbre vivant sous le numéro `numero`, qui doit être le prochain numéro
    /// (les recrues s'ajoutent en ordre fixe, après [`premiers_numeros`]).
    ///
    /// Code 1 si le numéro n'est pas le prochain ; code 2 si le `tree_id` est vide ou si
    /// l'essence est hors motif ; code 4 si la mémoire manque.
    pub fn ajouter(&mut self, numero: u64, arbre: ArbreNouveau) -> Result<(), Erreur> {
        if numero != self.prochain {
            return Err(Erreur::interne(format!(
                "numéro d'arbre {numero} ajouté alors que le prochain est {}",
                self.prochain
            )));
        }
        if arbre.tree_id.is_empty() {
            return Err(Erreur::entree_refusee("tree_id vide".to_string()));
        }
        let packee = packer_essence(&arbre.espece)?;
        // Croissance par doublement (au moins 16) : ajouter n arbres un à un reste en O(n).
        if self.numero.len() == self.numero.capacity() {
            let supplementaires = self.numero.len().max(16);
            self.reserver(supplementaires)?;
        }
        self.numero.push(numero);
        self.tree_id.push(arbre.tree_id);
        self.espece.push(arbre.espece);
        self.espece_packee.push(packee);
        self.cellule.push(arbre.cellule);
        self.x.push(arbre.x);
        self.y.push(arbre.y);
        self.d130.push(arbre.d130);
        self.h.push(arbre.h);
        self.vivant.push(true);
        self.prochain = numero
            .checked_add(1)
            .ok_or_else(|| Erreur::interne("numéros d'arbre épuisés (2^64)".to_string()))?;
        Ok(())
    }

    /// Retire les arbres morts en gardant l'ordre (donc les numéros) des vivants.
    /// Le prochain numéro ne change pas : un numéro n'est jamais réattribué.
    pub fn retirer_morts(&mut self) {
        let mut garde = 0;
        for rang in 0..self.len() {
            if self.vivant[rang] {
                if garde != rang {
                    self.numero.swap(garde, rang);
                    self.tree_id.swap(garde, rang);
                    self.espece.swap(garde, rang);
                    self.espece_packee.swap(garde, rang);
                    self.cellule.swap(garde, rang);
                    self.x.swap(garde, rang);
                    self.y.swap(garde, rang);
                    self.d130.swap(garde, rang);
                    self.h.swap(garde, rang);
                    self.vivant.swap(garde, rang);
                }
                garde += 1;
            }
        }
        self.numero.truncate(garde);
        self.tree_id.truncate(garde);
        self.espece.truncate(garde);
        self.espece_packee.truncate(garde);
        self.cellule.truncate(garde);
        self.x.truncate(garde);
        self.y.truncate(garde);
        self.d130.truncate(garde);
        self.h.truncate(garde);
        self.vivant.truncate(garde);
    }

    /// Vérifie les invariants : colonnes de même longueur, numéros strictement croissants et
    /// inférieurs au prochain, `tree_id` uniques. Code 1 sinon (anomalie du programme).
    pub fn verifier(&self) -> Result<(), Erreur> {
        let n = self.numero.len();
        let longueurs = [
            self.tree_id.len(),
            self.espece.len(),
            self.espece_packee.len(),
            self.cellule.len(),
            self.x.len(),
            self.y.len(),
            self.d130.len(),
            self.h.len(),
            self.vivant.len(),
        ];
        for longueur in longueurs {
            if longueur != n {
                return Err(Erreur::interne(format!(
                    "colonnes de l'état de longueurs différentes ({longueur} contre {n})"
                )));
            }
        }
        for rang in 0..n {
            if rang > 0 && self.numero[rang] <= self.numero[rang - 1] {
                return Err(Erreur::interne(format!(
                    "numéros d'arbre non croissants au rang {rang}"
                )));
            }
            if self.numero[rang] >= self.prochain {
                return Err(Erreur::interne(format!(
                    "numéro d'arbre {} au-delà du prochain ({})",
                    self.numero[rang], self.prochain
                )));
            }
        }
        let mut vus: HashSet<&str> = HashSet::with_capacity(n);
        for identifiant in &self.tree_id {
            if !vus.insert(identifiant.as_str()) {
                return Err(Erreur::interne(format!(
                    "tree_id « {identifiant} » en double"
                )));
            }
        }
        Ok(())
    }

    /// Octets occupés par le texte des chaînes (capacités de `tree_id` et `espece`).
    pub fn octets_texte(&self) -> u64 {
        let mut total: u64 = 0;
        for texte in &self.tree_id {
            total += texte.capacity() as u64;
        }
        for texte in &self.espece {
            total += texte.capacity() as u64;
        }
        total
    }

    /// Octets occupés par l'état (capacités réservées des colonnes, plus le texte).
    pub fn octets_occupes(&self) -> u64 {
        let huit = std::mem::size_of::<u64>() as u64;
        let chaine = std::mem::size_of::<String>() as u64;
        let mut total: u64 = 0;
        total += self.numero.capacity() as u64 * huit;
        total += self.espece_packee.capacity() as u64 * huit;
        total += self.cellule.capacity() as u64 * huit;
        total += self.x.capacity() as u64 * huit;
        total += self.y.capacity() as u64 * huit;
        total += self.d130.capacity() as u64 * huit;
        total += self.h.capacity() as u64 * huit;
        total += self.vivant.capacity() as u64;
        total += self.tree_id.capacity() as u64 * chaine;
        total += self.espece.capacity() as u64 * chaine;
        total + self.octets_texte()
    }
}

/// Premiers numéros des recrues de chaque cellule : somme de préfixes séquentielle, dans
/// l'ordre des cellules donné. `comptes[c]` recrues pour la c-ième cellule ; la cellule c reçoit
/// les numéros `premiers[c]` … `premiers[c] + comptes[c] − 1`. Rend aussi le prochain numéro
/// après toutes les recrues. Code 1 si les numéros dépassent 2^64.
pub fn premiers_numeros(prochain: u64, comptes: &[u64]) -> Result<(Vec<u64>, u64), Erreur> {
    let mut premiers: Vec<u64> = Vec::new();
    premiers
        .try_reserve_exact(comptes.len())
        .map_err(|_| memoire::erreur_allocation(comptes.len(), "numéros des recrues"))?;
    let mut suivant = prochain;
    for compte in comptes {
        premiers.push(suivant);
        suivant = suivant.checked_add(*compte).ok_or_else(|| {
            Erreur::interne("numéros d'arbre épuisés (2^64) pendant le recrutement".to_string())
        })?;
    }
    Ok((premiers, suivant))
}
