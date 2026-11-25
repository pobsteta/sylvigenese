// Logique pure de la vue (mission 029) : lecture des fiches de cellule, formatage, commande à copier.
// Sans navigateur ni iTowns : testée avec `node --test` (test/fiche.test.ts).
// Source unique des chiffres affichés : web/cells/<tuile>.json (contrat cell_sheet, mission 028).

export interface Composition {
  species: string;
  share: number;
}

export interface FicheAnnee {
  year: number;
  provisoire: boolean;
  composition: Composition[];
  volume_m3_ha: number | null;
  carbon_t_ha: number | null;
  h0_m?: number;
  density_trees_ha?: number;
  notes?: string[];
}

export interface Cellule {
  cell_id: number;
  x: number;
  y: number;
  station_type: string;
  vegetation_type: string;
  years: FicheAnnee[];
}

export interface FichesTuile {
  schema_version: number;
  tile: string;
  cells: Cellule[];
}

export interface Grille {
  x0: number; // bord ouest, Lambert-93, m
  y0: number; // bord nord, Lambert-93, m
  resolution: number; // m
  colonnes: number;
  lignes: number;
}

export class ErreurFiche extends Error {}

// Rassemble les fiches de plusieurs tuiles ; refuse un cell_id en double (deux tuiles ne partagent pas de cellule).
export function indexerFiches(tuiles: FichesTuile[]): Map<number, Cellule> {
  const index = new Map<number, Cellule>();
  for (const tuile of tuiles) {
    if (tuile.schema_version !== 1 || !Array.isArray(tuile.cells)) {
      throw new ErreurFiche(`fiches de la tuile ${tuile.tile ?? "?"} : schema_version 1 attendu`);
    }
    for (const c of tuile.cells) {
      if (index.has(c.cell_id)) {
        throw new ErreurFiche(`cellule ${c.cell_id} présente dans deux tuiles (${tuile.tile})`);
      }
      index.set(c.cell_id, c);
    }
  }
  return index;
}

// Rang de la cellule (ligne * colonnes + colonne, comme grid.tif) pour un point Lambert-93 ; null hors grille.
export function cellIdDepuisLambert(x: number, y: number, g: Grille): number | null {
  const col = Math.floor((x - g.x0) / g.resolution);
  const ligne = Math.floor((g.y0 - y) / g.resolution);
  if (col < 0 || ligne < 0 || col >= g.colonnes || ligne >= g.lignes) return null;
  return ligne * g.colonnes + col;
}

// Centre de la cellule : valeur de la fiche (x, y), pas un recalcul.
export function commandeViewerMassif(x: number, y: number, annee: number): string {
  return `viewer-massif -- --x ${nombre(x)} --y ${nombre(y)} --year ${annee}`;
}

export function nombre(v: number): string {
  return Number.isInteger(v) ? String(v) : String(Math.round(v * 1000) / 1000);
}

const FR = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 });

export interface Ligne {
  libelle: string;
  valeur: string;
}

export interface FicheAffichee {
  titre: string;
  provisoire: boolean;
  lignes: Ligne[];
  composition: string[];
  notes: string[];
  commande: string;
  annee: number;
}

// Choisit l'année demandée, sinon la première ; la vue n'a qu'une année pour l'instant.
export function anneeDe(c: Cellule, annee?: number): FicheAnnee {
  const a = annee === undefined ? c.years[0] : c.years.find((y) => y.year === annee);
  if (!a) throw new ErreurFiche(`cellule ${c.cell_id} : pas de fiche pour l'année ${annee}`);
  return a;
}

// Une valeur absente est dite « non calculé » : jamais 0 ni une valeur par défaut silencieuse.
function valeurOuNonCalcule(v: number | null | undefined, unite: string): string {
  return v === null || v === undefined ? "non calculé (après la simulation)" : `${FR.format(v)} ${unite}`;
}

export function formaterFiche(c: Cellule, annee?: number): FicheAffichee {
  const a = anneeDe(c, annee);
  const lignes: Ligne[] = [
    { libelle: "Station", valeur: c.station_type },
    { libelle: "Type de végétation", valeur: c.vegetation_type },
    { libelle: "Hauteur dominante H0", valeur: a.h0_m === undefined ? "non renseignée" : `${FR.format(a.h0_m)} m` },
    { libelle: "Densité", valeur: a.density_trees_ha === undefined ? "non renseignée" : `${FR.format(a.density_trees_ha)} arbres/ha` },
    { libelle: "Volume", valeur: valeurOuNonCalcule(a.volume_m3_ha, "m³/ha") },
    { libelle: "Carbone", valeur: valeurOuNonCalcule(a.carbon_t_ha, "t/ha") },
  ];
  const composition = a.composition.map((e) => `${e.species} : ${FR.format(e.share * 100)} %`);
  return {
    titre: `Cellule ${c.cell_id}`,
    provisoire: a.provisoire,
    lignes,
    composition,
    notes: a.notes ?? [],
    commande: commandeViewerMassif(c.x, c.y, a.year),
    annee: a.year,
  };
}
