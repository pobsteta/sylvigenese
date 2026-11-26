// Logique pure de la vue (mission 029) : lecture des fiches de cellule, formatage, commande à copier.
// Sans navigateur ni iTowns : testée avec `node --test` (test/sheet.test.ts).
// Source unique des chiffres affichés : web/cells/<tuile>.json (contrat cell_sheet, mission 028).

export interface Composition {
  species: string;
  share: number;
}

export interface YearSheet {
  year: number;
  provisoire: boolean;
  composition: Composition[];
  volume_m3_ha: number | null;
  carbon_t_ha: number | null;
  h0_m?: number;
  density_trees_ha?: number;
  notes?: string[];
}

export interface Cell {
  cell_id: number;
  x: number;
  y: number;
  station_type: string;
  vegetation_type: string;
  years: YearSheet[];
}

export interface TileSheets {
  schema_version: number;
  tile: string;
  cells: Cell[];
}

export interface Grid {
  x0: number; // bord ouest, Lambert-93, m
  y0: number; // bord nord, Lambert-93, m
  resolution: number; // m
  columns: number;
  rows: number;
}

export class SheetError extends Error {}

// Rassemble les fiches de plusieurs tuiles ; refuse un cell_id en double (deux tuiles ne partagent pas de cellule).
// La version attendue est dictée par tiles/index.json : 1 pour l'état initial, 2 dès que sim/ existe (mission 048 ;
// la vue refuse alors la version 1, plan m4a-suite-temps §3), 3 quand post a tourné (mission 054 : voir
// sheetVersion dans volume.ts, qui la déduit de l'index et des fiches).
export function indexSheets<C extends { cell_id: number }>(
  tiles: { schema_version: number; tile: string; cells: C[] }[], version: 1 | 2 | 3 = 1,
): Map<number, C> {
  const index = new Map<number, C>();
  for (const tile of tiles) {
    if (tile.schema_version !== version || !Array.isArray(tile.cells)) {
      throw new SheetError(`fiches de la tuile ${tile.tile ?? "?"} : schema_version ${version} attendu`);
    }
    for (const c of tile.cells) {
      if (index.has(c.cell_id)) {
        throw new SheetError(`cellule ${c.cell_id} présente dans deux tuiles (${tile.tile})`);
      }
      index.set(c.cell_id, c);
    }
  }
  return index;
}

// Rang de la cellule (ligne * colonnes + colonne, comme grid.tif) pour un point Lambert-93 ; null hors grille.
export function cellIdFromLambert(x: number, y: number, g: Grid): number | null {
  const col = Math.floor((x - g.x0) / g.resolution);
  const row = Math.floor((g.y0 - y) / g.resolution);
  if (col < 0 || row < 0 || col >= g.columns || row >= g.rows) return null;
  return row * g.columns + col;
}

// Centre de la cellule : valeur de la fiche (x, y), pas un recalcul.
export function massifViewerCommand(x: number, y: number, year: number): string {
  return `viewer-massif -- --x ${formatNumber(x)} --y ${formatNumber(y)} --year ${year}`;
}

export function formatNumber(v: number): string {
  return Number.isInteger(v) ? String(v) : String(Math.round(v * 1000) / 1000);
}

const FR = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 });

export interface Row {
  label: string;
  value: string;
}

export interface DisplayedSheet {
  title: string;
  provisional: boolean;
  rows: Row[];
  composition: string[];
  notes: string[];
  command: string;
  year: number;
}

// Choisit l'année demandée, sinon la première (fiche v1 : une seule année, l'état initial).
export function yearOf(c: Cell, year?: number): YearSheet {
  const a = year === undefined ? c.years[0] : c.years.find((y) => y.year === year);
  if (!a) throw new SheetError(`cellule ${c.cell_id} : pas de fiche pour l'année ${year}`);
  return a;
}

// Une valeur absente est dite « non calculé » : jamais 0 ni une valeur par défaut silencieuse.
function valueOrNotComputed(v: number | null | undefined, unit: string): string {
  return v === null || v === undefined ? "non calculé (après la simulation)" : `${FR.format(v)} ${unit}`;
}

export function formatSheet(c: Cell, year?: number): DisplayedSheet {
  const a = yearOf(c, year);
  const rows: Row[] = [
    { label: "Station", value: c.station_type },
    { label: "Type de végétation", value: c.vegetation_type },
    { label: "Hauteur dominante H0", value: a.h0_m === undefined ? "non renseignée" : `${FR.format(a.h0_m)} m` },
    { label: "Densité", value: a.density_trees_ha === undefined ? "non renseignée" : `${FR.format(a.density_trees_ha)} arbres/ha` },
    { label: "Volume", value: valueOrNotComputed(a.volume_m3_ha, "m³/ha") },
    { label: "Carbone", value: valueOrNotComputed(a.carbon_t_ha, "t/ha") },
  ];
  const composition = a.composition.map((e) => `${e.species} : ${FR.format(e.share * 100)} %`);
  return {
    title: `Cellule ${c.cell_id}`,
    provisional: a.provisoire,
    rows,
    composition,
    notes: a.notes ?? [],
    command: massifViewerCommand(c.x, c.y, a.year),
    year: a.year,
  };
}
