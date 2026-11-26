// Logique pure de la vue dans le temps (mission 048 ; plan m4a-suite-temps §2 mission D, T7, T9, T10 ;
// décisions de Pascal Q1, Q2 et Q3 du 25/11/2026). Sans navigateur ni iTowns : testée par node --test
// (test/temps.test.ts).
// Sources uniques des chiffres affichés :
//   - tiles/index.json (contrat tiles_index) : les années, les instances vivantes de chaque année, l'échelle fixe
//     de la carte de surface terrière ;
//   - web/cells/<tuile>.json en version 2 (contrat cell_sheet) : l'évolution de chaque cellule.
// Rien n'est recalculé ni interpolé ici : on choisit, on met en forme, on signale.

import { SheetError, massifViewerCommand, type Row } from "./sheet.ts";

// ---------------------------------------------------------------- index des années (tiles/index.json)
export interface IndexTile {
  tile: string;
  instances: number;
}

export interface IndexYear {
  year: number;
  instances: number;
  dead?: number;
  tileset: string;
  tiles: IndexTile[];
}

export interface BasalAreaMap {
  unit: string;
  scale_min_m2_ha: number;
  scale_max_m2_ha: number;
  mention: string;
}

export interface TilesIndex {
  schema_version: number;
  source: "sim" | "trees_init";
  t0: number;
  year_step?: number;
  provisoire: boolean;
  notes: string[];
  basal_area_map?: BasalAreaMap;
  years: IndexYear[];
}

const isObject = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);

// Contrôle ce dont la vue a besoin ; le contrat complet est vérifié par le validateur en fin de assets.
// Toute incohérence est une erreur explicite : la vue ne devine pas une année ni une échelle.
export function readTilesIndex(raw: unknown): TilesIndex {
  if (!isObject(raw) || raw["schema_version"] !== 1) throw new SheetError("tiles/index.json : schema_version 1 attendu");
  const source = raw["source"];
  if (source !== "sim" && source !== "trees_init") throw new SheetError(`tiles/index.json : source inconnue (${String(source)})`);
  const years = raw["years"];
  if (!Array.isArray(years) || years.length === 0) throw new SheetError("tiles/index.json : aucune année");
  let previous = -Infinity;
  for (const y of years) {
    if (!isObject(y) || !Number.isInteger(y["year"]) || !Number.isInteger(y["instances"]) || typeof y["tileset"] !== "string"
        || !Array.isArray(y["tiles"])) {
      throw new SheetError("tiles/index.json : année mal formée (year, instances, tileset, tiles)");
    }
    if ((y["year"] as number) <= previous) throw new SheetError("tiles/index.json : années non rangées de la plus ancienne à la plus récente");
    previous = y["year"] as number;
  }
  if (source === "sim") {
    const m = raw["basal_area_map"];
    if (!isObject(m) || typeof m["scale_min_m2_ha"] !== "number" || typeof m["scale_max_m2_ha"] !== "number"
        || typeof m["mention"] !== "string") {
      throw new SheetError("tiles/index.json : carte de surface terrière (basal_area_map) absente en mode sim");
    }
    if (!(m["scale_max_m2_ha"] > m["scale_min_m2_ha"])) {
      throw new SheetError("tiles/index.json : échelle de surface terrière vide (borne haute <= borne basse)");
    }
  }
  return raw as unknown as TilesIndex;
}

export function indexYears(index: TilesIndex): number[] {
  return index.years.map((y) => y.year);
}

export function indexYear(index: TilesIndex, year: number): IndexYear {
  const y = index.years.find((e) => e.year === year);
  if (!y) throw new SheetError(`année ${year} absente de tiles/index.json (années : ${indexYears(index).join(", ")})`);
  return y;
}

// Toutes les tuiles qui portent des fiches, toutes années confondues, sans doublon, dans l'ordre de l'index.
export function indexTiles(index: TilesIndex): string[] {
  const out: string[] = [];
  for (const y of index.years) for (const t of y.tiles) if (!out.includes(t.tile)) out.push(t.tile);
  return out;
}

// ---------------------------------------------------------------- choix de l'année
// Seules les années de l'index se choisissent : pas d'interpolation (T3), donc pas d'année « entre deux ».
export function chooseYear(years: number[], year: unknown): number {
  if (typeof year !== "number" || !years.includes(year)) {
    throw new SheetError(`année ${String(year)} non disponible (années : ${years.join(", ")})`);
  }
  return year;
}

// Le curseur porte sur le rang de l'année (les années ne sont pas forcément régulières : 2022, 2032, 2037).
export function yearAtPosition(years: number[], position: number): number {
  const i = Math.min(years.length - 1, Math.max(0, Math.round(position)));
  return years[i] as number;
}

export function positionOfYear(years: number[], year: number): number {
  const i = years.indexOf(year);
  if (i < 0) throw new SheetError(`année ${year} non disponible`);
  return i;
}

// Année voisine (boutons précédente / suivante) ; reste sur place au bord.
export function neighbourYear(years: number[], year: number, step: -1 | 1): number {
  return yearAtPosition(years, positionOfYear(years, year) + step);
}

export function yearLabel(year: number, t0: number): string {
  return year === t0 ? `${year} (t0, début de la simulation)` : `${year} (t0 + ${year - t0} ans, simulé)`;
}

// ---------------------------------------------------------------- nombres
// Une décimale, virgule française. Arrondi de la valeur binaire exacte, et demi au pair sur les vraies égalités
// (x,x25 et x,x75 sont exactement représentables) : même chiffre que l'écriture « %.1f » des rapports Python.
export function format1(v: number): string {
  let s = v.toFixed(1);
  const quarter = v * 4; // exact (puissance de 2)
  if (Number.isInteger(quarter) && Math.abs(quarter % 2) === 1) {
    const tenth = v * 10; // exact pour un multiple impair de 0,25 : n,5
    const low = Math.floor(tenth);
    s = ((low % 2 === 0 ? low : low + 1) / 10).toFixed(1);
  }
  return s.replace(".", ",");
}

const FR0 = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
export function format0(v: number): string {
  return FR0.format(v);
}

// ---------------------------------------------------------------- carte de surface terrière (Q3)
// Rampe séquentielle à trois jalons (jaune pâle, orange, bordeaux) : lisible sous les houppiers verts et par un
// daltonien (pas de rouge contre vert). Échelle FIXE sur toutes les années, lue dans l'index.
export const RAMP: [number, number, number][] = [[255, 255, 204], [253, 141, 60], [128, 0, 38]];

export interface ScaledColor {
  rgb: [number, number, number];
  outside: boolean; // valeur hors de l'échelle fixe : signalée, dessinée à la borne
}

export function rampColor(value: number, min: number, max: number): ScaledColor {
  const outside = value < min || value > max;
  const t = Math.min(1, Math.max(0, (value - min) / (max - min)));
  const k = t * (RAMP.length - 1);
  const i = Math.min(RAMP.length - 2, Math.floor(k));
  const f = k - i;
  const a = RAMP[i] as [number, number, number], b = RAMP[i + 1] as [number, number, number];
  const rgb = [0, 1, 2].map((c) => Math.round((a[c] as number) + f * ((b[c] as number) - (a[c] as number)))) as [number, number, number];
  return { rgb, outside };
}

export function rampCss(): string {
  return `linear-gradient(to right, ${RAMP.map(([r, g, b], i) => `rgb(${r} ${g} ${b}) ${Math.round((100 * i) / (RAMP.length - 1))}%`).join(", ")})`;
}

// Trois repères de légende : borne basse, milieu, borne haute (m²/ha).
export function legendTicks(min: number, max: number): string[] {
  return [min, (min + max) / 2, max].map((v) => format0(v));
}

// ---------------------------------------------------------------- fiche de cellule v2 (évolution)
export interface CompositionV2 {
  species: string;
  stems_ha: number;
  basal_area_m2_ha: number;
  share: number;
}

export interface FlagV2 {
  kind: string;
  message: string;
  value?: number | null;
}

// Ce qu'une année simulée porte en v2 comme en v3 (contrat cell_sheet, year_v2 et year_v3).
export interface YearSheetSim {
  year: number;
  provisoire: boolean;
  stems_ha: number;
  basal_area_m2_ha: number;
  d130_mean_cm: number | null;
  h_dom_m: number | null;
  h0_m?: number;
  composition: CompositionV2[];
  flags: FlagV2[];
}

export interface YearSheetV2 extends YearSheetSim {
  volume_m3_ha: null;
  carbon_t_ha: null;
}

// Cellule simulée, v2 ou v3 : la v3 ne change que ses années (voir volume.ts).
export interface CellSim<Y extends YearSheetSim = YearSheetSim> {
  cell_id: number;
  x: number;
  y: number;
  station_type: string;
  vegetation_type: string;
  h_ceiling_m: number | null;
  years: Y[];
}

export type CellV2 = CellSim<YearSheetV2>;

export interface TileSheetsV2 {
  schema_version: 2;
  tile: string;
  source: "sim";
  notes: string[];
  cells: CellV2[];
}

export const MENTION_ECO = "trajectoire technique, non validée écologiquement (décision de Pascal du 25/11/2026)";
export const MENTION_VC = "volume et carbone non calculés (post, mission à part après M4a)";

const FLAG_LABELS: Record<string, string> = {
  hdom_au_dessus_du_plafond: "H_dom au-dessus du plafond",
  trouee_sans_recrue: "trouée sans recrue",
};
export function flagLabel(kind: string): string {
  return FLAG_LABELS[kind] ?? kind.replace(/_/g, " ");
}

export interface EvolutionRow {
  year: number;
  selected: boolean;
  stems: string;
  basalArea: string;
  d130: string;
  hdom: string;
  aboveCeiling: boolean;
  composition: string;
  flags: string[];
}

export interface DisplayedEvolution {
  title: string;
  year: number;
  provisional: boolean;
  headline: string;
  ceiling: string;
  rows: Row[];
  table: EvolutionRow[];
  notes: string[];
  command: string;
}

function hdomText(h: number | null): string {
  return h === null ? "aucun arbre vivant" : format1(h);
}

// Mentions de la fiche : celles du fichier (source unique), complétées des deux mentions exigées par Pascal si
// elles y manquaient (jamais retirées). Aucun doublon.
export function sheetNotes(fileNotes: string[]): string[] {
  const out = [...new Set(fileNotes)];
  if (!out.some((n) => n.includes("non validée écologiquement"))) out.push(MENTION_ECO);
  if (!out.some((n) => n.includes("volume et carbone non calculés"))) out.push(MENTION_VC);
  return out;
}

export function formatEvolution(c: CellSim, year: number, fileNotes: string[]): DisplayedEvolution {
  const a = c.years.find((y) => y.year === year);
  if (!a) throw new SheetError(`cellule ${c.cell_id} : pas de fiche pour l'année ${year}`);
  const ceiling = c.h_ceiling_m === null ? "plafond inconnu" : `plafond ${format1(c.h_ceiling_m)} m`;
  const above = (h: number | null) => h !== null && c.h_ceiling_m !== null && h > c.h_ceiling_m;
  const table: EvolutionRow[] = [...c.years].sort((p, q) => p.year - q.year).map((y) => ({
    year: y.year,
    selected: y.year === year,
    stems: format0(y.stems_ha),
    basalArea: format1(y.basal_area_m2_ha),
    d130: y.d130_mean_cm === null ? "sans tige" : format1(y.d130_mean_cm),
    hdom: hdomText(y.h_dom_m),
    aboveCeiling: above(y.h_dom_m),
    composition: y.composition.map((e) => `${e.species} ${format0(e.share * 100)} %`).join(" · ") || "aucune",
    flags: y.flags.map((f) => flagLabel(f.kind)),
  }));
  const hd = a.h_dom_m === null ? "H_dom : aucun arbre vivant" : `H_dom ${format1(a.h_dom_m)} m`;
  return {
    title: `Cellule ${c.cell_id}`,
    year: a.year,
    provisional: c.years.some((y) => y.provisoire),
    headline: `${a.year} : G ${format1(a.basal_area_m2_ha)} m²/ha · ${hd} (${ceiling})${above(a.h_dom_m) ? ", au-dessus du plafond" : ""}`,
    ceiling,
    rows: [
      { label: "Station", value: c.station_type },
      { label: "Type de végétation (état initial)", value: c.vegetation_type },
      { label: "Plafond de hauteur (station)", value: c.h_ceiling_m === null ? "inconnu" : `${format1(c.h_ceiling_m)} m` },
      { label: "Volume et carbone", value: "non calculés" },
    ],
    table,
    notes: sheetNotes(fileNotes),
    command: massifViewerCommand(c.x, c.y, a.year),
  };
}

// ---------------------------------------------------------------- images par seconde (relevé sans seuil)
// Sous SwiftShader (CI sans GPU), une image de 100 000 instances peut prendre plus de 3 s : une mesure de durée fixe
// comptait alors 0 ou 1 image, et l'arrondi à 0,1 rendait 0 (run 45777046842). Règle : la mesure dure au moins la
// durée demandée ET jusqu'à FPS_MIN_FRAMES images rendues, sans dépasser FPS_MAX_MS (60 s : au-delà, la vue est de
// toute façon inutilisable, et la sonde ne doit pas attendre sans fin). Pas d'arrondi à une décimale : trois chiffres
// significatifs. Aucune image au plafond : null, jamais 0 en silence (le code navigateur le dit dans state.error).
export const FPS_MIN_FRAMES = 2;
export const FPS_MAX_MS = 60000;

/** Vrai quand la mesure peut s'arrêter : durée demandée atteinte avec au moins FPS_MIN_FRAMES images, ou plafond. */
export function fpsMeasureDone(elapsedMs: number, frames: number, requestedMs: number): boolean {
  return (elapsedMs >= requestedMs && frames >= FPS_MIN_FRAMES) || elapsedMs >= FPS_MAX_MS;
}

/** Images par seconde, à trois chiffres significatifs ; null si aucune image n'a été rendue. */
export function fpsValue(frames: number, elapsedMs: number): number | null {
  if (frames <= 0 || !(elapsedMs > 0)) return null;
  return Number(((frames * 1000) / elapsedMs).toPrecision(3));
}

// ---------------------------------------------------------------- couches d'arbres (revue de la PR n° 9, M1)
// Règle : jamais plus de deux couches d'arbres en mémoire : celle qui est affichée, et celle en cours de chargement.
// Quand un nouvel appel abandonne un chargement en cours, la couche abandonnée est retirée AVANT d'en ajouter une autre
// (avant, elle n'était retirée qu'au tick suivant, 300 ms plus tard : trois couches possibles).
// Le code navigateur appelle ces méthodes et retire (dispose) les couches rendues ; rien d'autre ici que du comptage.
export class TreeLayerSlots<L> {
  shown: L | null = null;
  loading: L | null = null;

  /** À appeler juste avant d'ajouter une nouvelle couche : rend la couche abandonnée à retirer d'abord (ou rien). */
  beforeAdd(): L[] {
    const dropped = this.loading === null ? [] : [this.loading];
    this.loading = null;
    return dropped;
  }

  /** La nouvelle couche est ajoutée (en cours de chargement). */
  added(layer: L): void {
    if (this.loading !== null) throw new Error("beforeAdd() doit être appelé et ses couches retirées avant added()");
    this.loading = layer;
  }

  /** Le chargement de `layer` est fini : elle devient la couche affichée ; rend l'ancienne à retirer. Une couche
   *  déjà abandonnée ne remplace rien (rend alors elle-même, si elle n'a pas été retirée). */
  commit(layer: L): L[] {
    if (this.loading !== layer) return [];
    const old = this.shown;
    this.shown = layer;
    this.loading = null;
    return old === null ? [] : [old];
  }

  /** Le chargement de `layer` est abandonné ou en échec : rend la couche à retirer si elle ne l'a pas déjà été. */
  abandon(layer: L): L[] {
    if (this.loading !== layer) return [];
    this.loading = null;
    return [layer];
  }

  /** Nombre de couches d'arbres actuellement gardées. */
  get count(): number {
    return (this.shown === null ? 0 : 1) + (this.loading === null ? 0 : 1);
  }
}
