// Fiche de cellule v3 : volume et carbone, année par année (mission 054 ; plan post-volume-carbone, mission E ;
// décisions de Pascal Q3 à Q5 du 26/11/2026). Sans navigateur ni iTowns : testée par node --test
// (test/volume.test.ts).
// Source unique des chiffres affichés : web/cells/<tuile>.json en version 3 (contrat cell_sheet, year_v3), écrite
// par assets à partir de sim/summary.parquet (post). Rien n'est recalculé ici : pas de somme, pas d'écart entre deux
// années, pas de valeur à la place d'un null. On choisit, on met en forme, on dit ce qui manque.
//   - volume_m3_ha : volume AÉRIEN TOTAL (tige et branches), seul volume affiché (Q3) ;
//   - carbon_t_ha : carbone AÉRIEN ; root_carbon_t_ha, s'il existe, à part et PROVISOIRE, jamais additionné (Q4) ;
//   - volume_partiel et basal_area_not_computed_share : « volume partiel » et la part de G non calculée (Q5) ;
//   - null : rien n'est calculé, la raison vient de not_computed_reason (jamais 0, jamais deviné).

import { SheetError, type Row } from "./sheet.ts";
import {
  MENTION_ECO, format0, format1, formatEvolution,
  type CellSim, type CompositionV2, type DisplayedEvolution, type EvolutionRow, type TilesIndex, type YearSheetSim,
} from "./temps.ts";

// ---------------------------------------------------------------- types (contrat cell_sheet v3)
export interface CompositionV3 extends CompositionV2 {
  volume_m3_ha: number | null;
  carbon_t_ha: number | null;
  basal_area_not_computed_share: number;
}

export interface YearSheetV3 extends YearSheetSim {
  composition: CompositionV3[];
  volume_m3_ha: number | null;
  carbon_t_ha: number | null;
  root_carbon_t_ha?: number | null;
  stems_not_computed_ha: number;
  basal_area_not_computed_share: number;
  volume_partiel: boolean;
  not_computed_reason?: string;
}

export type CellV3 = CellSim<YearSheetV3>;

export interface Tarif {
  name: string;
  commit: string;
  provisoire: true;
}

export interface TileSheetsV3 {
  schema_version: 3;
  tile: string;
  source: "sim";
  notes: string[];
  tarif: Tarif;
  cells: CellV3[];
}

// ---------------------------------------------------------------- version des fiches
// Phrase du contrat des fiches v2, interdite dans les notes de la v3 : si l'index la porte encore alors que les
// fiches sont en v3, index et fiches ne disent pas la même chose.
const PHRASE_V2 = "volume et carbone non calculés";

/** Version des fiches à lire. L'index dit s'il y a une simulation (source « sim » : v2 ou v3, sinon v1) ; les
 *  fiches disent laquelle des deux, et toutes la même. Toute contradiction est une erreur explicite. */
export function sheetVersion(index: Pick<TilesIndex, "source" | "notes"> | null, files: { schema_version: unknown; tile?: string }[]): 1 | 2 | 3 {
  if (index === null || index.source !== "sim") return 1;
  const versions = [...new Set(files.map((f) => f.schema_version))];
  if (versions.length === 0) throw new SheetError("aucune fiche de cellule (web/cells/) pour une zone simulée");
  if (versions.length > 1) {
    throw new SheetError(`fiches de cellule de versions différentes (${versions.join(", ")}) : assets n'a pas tout réécrit`);
  }
  const v = versions[0];
  if (v !== 2 && v !== 3) {
    throw new SheetError(`fiches de cellule : schema_version 2 ou 3 attendu avec sim/ (lu : ${String(v)})`);
  }
  if (v === 3 && (index.notes ?? []).some((n) => n.includes(PHRASE_V2))) {
    throw new SheetError("tiles/index.json dit « volume et carbone non calculés » mais les fiches sont en version 3 "
      + "(volume et carbone de post) : index et fiches ne viennent pas du même passage d'assets");
  }
  return v;
}

// ---------------------------------------------------------------- mentions (Q3, Q4, Q5)
export const MENTION_VOLUME = "volume aérien total (tige et branches) : le seul volume affiché, même définition pour toutes les essences";
export const MENTION_CARBONE = "carbone aérien en tC/ha ; les racines, quand elles sont données, sont à part et provisoires";
export const MENTION_SOL = "sol et bois mort non comptés (hors v1)";
export const MENTION_PARTIEL = "volume partiel : une part de la surface terrière n'est pas calculée (hors du domaine du tarif ou essence sans tarif)";
/** Ligne courte, toujours visible sous le chiffre principal. */
export const MENTIONS_COURTES = "volume aérien total · carbone aérien · sol et bois mort non comptés · non validée écologiquement";

/** Mentions de la fiche v3 : celles du fichier (source unique), complétées de celles exigées par Pascal si elles y
 *  manquaient (jamais retirées) ; aucun doublon ; jamais « volume et carbone non calculés ». */
export function sheetNotesV3(fileNotes: string[], anyPartial: boolean): string[] {
  const out = [...new Set(fileNotes)];
  const need: [string, string][] = [
    ["non validée écologiquement", MENTION_ECO],
    ["volume aérien total", MENTION_VOLUME],
    ["carbone aérien", MENTION_CARBONE],
    ["sol et bois mort", MENTION_SOL],
  ];
  if (anyPartial) need.push(["volume partiel", MENTION_PARTIEL]);
  for (const [key, mention] of need) if (!out.some((n) => n.includes(key))) out.push(mention);
  return out;
}

// ---------------------------------------------------------------- nombres
const NOT_COMPUTED = "non calculé";

function valueText(v: number | null | undefined): string {
  if (v === null) return NOT_COMPUTED;
  if (v === undefined) return "absent de la fiche";
  return format1(v);
}

/** Part de G non calculée, en pour cent entiers ; jamais « 0 % » pour une part non nulle, jamais « 100 % » pour une
 *  part sous 1 (1 veut dire « rien n'est calculé »). */
export function shareText(share: number): string {
  const pct = share * 100;
  if (share > 0 && pct < 0.5) return "moins de 1 %";
  if (share < 1 && pct >= 99.5) return "plus de 99 %";
  return `${format0(pct)} %`;
}

export function partialText(y: YearSheetV3): string {
  return y.volume_partiel ? `volume partiel : ${shareText(y.basal_area_not_computed_share)} de G non calculée` : "";
}

// ---------------------------------------------------------------- mise en forme
export interface EvolutionRowV3 extends EvolutionRow {
  volume: string;
  carbon: string;
  roots: string | null; // null : pas de colonne racines (clé absente de toutes les années)
  partial: string;
  notComputed: boolean;
}

export interface NotComputedReason {
  years: number[];
  reason: string;
}

export interface DisplayedEvolutionV3 extends DisplayedEvolution {
  context: string; // l'ancien titre de la v2 (G, H_dom, plafond), en plus petit
  mentions: string;
  hasRoots: boolean;
  table: EvolutionRowV3[];
  reasons: NotComputedReason[];
}

function reasonOf(y: YearSheetV3): string {
  return y.not_computed_reason ?? "raison non donnée par la fiche (contrat cell_sheet : not_computed_reason manque)";
}

export function formatEvolutionV3(c: CellV3, year: number, fileNotes: string[], tarif: Tarif | null): DisplayedEvolutionV3 {
  const base = formatEvolution(c, year, []); // tableau v2 (tiges, G, d, H_dom, essences, signalements) et commande
  const a = c.years.find((y) => y.year === year) as YearSheetV3; // formatEvolution a déjà refusé une année absente
  const hasRoots = c.years.some((y) => "root_carbon_t_ha" in y);
  const byYear = new Map(c.years.map((y) => [y.year, y]));
  const table: EvolutionRowV3[] = base.table.map((r) => {
    const y = byYear.get(r.year) as YearSheetV3;
    return {
      ...r,
      volume: valueText(y.volume_m3_ha),
      carbon: valueText(y.carbon_t_ha),
      roots: hasRoots ? valueText(y.root_carbon_t_ha) : null,
      partial: partialText(y),
      notComputed: y.volume_m3_ha === null,
    };
  });
  const reasons: NotComputedReason[] = [];
  for (const y of [...c.years].sort((p, q) => p.year - q.year)) {
    if (y.volume_m3_ha !== null && y.carbon_t_ha !== null) continue;
    const reason = reasonOf(y);
    const same = reasons.find((r) => r.reason === reason);
    if (same) same.years.push(y.year);
    else reasons.push({ years: [y.year], reason });
  }

  let headline: string;
  if (a.volume_m3_ha === null || a.carbon_t_ha === null) {
    headline = `${a.year} : rien n'est calculé (volume et carbone) — ${reasonOf(a)}`;
  } else {
    headline = `${a.year} : volume aérien total ${format1(a.volume_m3_ha)} m³/ha · carbone aérien ${format1(a.carbon_t_ha)} tC/ha, provisoires`;
    if (a.volume_partiel) headline += ` (${partialText(a)})`;
  }

  const rows: Row[] = base.rows.filter((r) => r.label !== "Volume et carbone");
  if (hasRoots) {
    const v = a.root_carbon_t_ha;
    rows.push({ label: "Carbone des racines (à part, provisoire)", value: v === null || v === undefined ? valueText(v) : `${format1(v)} tC/ha` });
  }
  rows.push({ label: "Tarif (provisoire)", value: tarif === null ? "non dit par la fiche" : `${tarif.name}, commit ${tarif.commit}` });

  return {
    ...base,
    headline,
    context: base.headline,
    mentions: MENTIONS_COURTES,
    hasRoots,
    rows,
    table,
    reasons,
    notes: sheetNotesV3(fileNotes, c.years.some((y) => y.volume_partiel)),
  };
}
