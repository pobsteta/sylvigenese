// Tests de la vue dans le temps (mission 048) : choix de l'année, index, mise en forme de l'évolution, échelle fixe.
import { test } from "node:test";
import assert from "node:assert/strict";
import { SheetError, indexSheets } from "../src/sheet.ts";
import {
  chooseYear, format1, formatEvolution, indexTiles, indexYear, indexYears, legendTicks, neighbourYear,
  positionOfYear, rampColor, readTilesIndex, sheetNotes, TreeLayerSlots, yearAtPosition, yearLabel,
  type CellV2, type TileSheetsV2,
} from "../src/temps.ts";

const index = (over: Record<string, unknown> = {}) => ({
  schema_version: 1, source: "sim", t0: 2022, year_step: 10, provisoire: true,
  run_config_sha256: "0".repeat(64),
  notes: ["trajectoire technique, non validée écologiquement (décision du 25/11/2026)"],
  basal_area_map: { unit: "m2/ha", scale_min_m2_ha: 0, scale_max_m2_ha: 350, mention: "surface terrière, non validée écologiquement" },
  years: [
    { year: 2022, instances: 14080, dead: 0, tileset: "2022/tileset.json", tiles: [{ tile: "t_700000_6500000", instances: 9000 }, { tile: "t_700500_6500000", instances: 5080 }] },
    { year: 2032, instances: 45954, dead: 12, tileset: "2032/tileset.json", tiles: [{ tile: "t_700000_6500000", instances: 40000 }, { tile: "t_700500_6500500", instances: 5954 }] },
    { year: 2037, instances: 60000, dead: 3, tileset: "2037/tileset.json", tiles: [{ tile: "t_700000_6500000", instances: 60000 }] },
  ],
  ...over,
});

const YEARS = [2022, 2032, 2037];

test("les années de la vue sont celles de l'index, dans son ordre", () => {
  const ix = readTilesIndex(index());
  assert.deepEqual(indexYears(ix), YEARS);
  assert.equal(indexYear(ix, 2032).instances, 45954);
  assert.throws(() => indexYear(ix, 2030), /2030 absente/);
});

test("les fiches à lire sont toutes les tuiles de toutes les années, sans doublon", () => {
  assert.deepEqual(indexTiles(readTilesIndex(index())), ["t_700000_6500000", "t_700500_6500000", "t_700500_6500500"]);
});

test("un index mal formé est refusé, jamais complété", () => {
  assert.throws(() => readTilesIndex({ ...index(), schema_version: 2 }), SheetError);
  assert.throws(() => readTilesIndex(index({ years: [] })), /aucune année/);
  assert.throws(() => readTilesIndex(index({ source: "autre" })), /source inconnue/);
  assert.throws(() => readTilesIndex(index({ basal_area_map: undefined })), /basal_area_map/);
  assert.throws(() => readTilesIndex(index({ basal_area_map: { unit: "m2/ha", scale_min_m2_ha: 5, scale_max_m2_ha: 5, mention: "x" } })), /échelle/);
  const desordre = index();
  desordre.years = [desordre.years[1], desordre.years[0]] as typeof desordre.years;
  assert.throws(() => readTilesIndex(desordre), /non rangées/);
});

test("l'index de l'état initial (trees_init) se lit sans carte de surface terrière", () => {
  const ix = readTilesIndex({ schema_version: 1, source: "trees_init", t0: 2022, provisoire: true, notes: ["x"],
    years: [{ year: 2022, instances: 14080, tileset: "2022/tileset.json", tiles: [{ tile: "t_1_2", instances: 14080 }] }] });
  assert.deepEqual(indexYears(ix), [2022]);
});

test("seule une année de l'index se choisit : pas d'année interpolée", () => {
  assert.equal(chooseYear(YEARS, 2032), 2032);
  assert.throws(() => chooseYear(YEARS, 2030), /2030 non disponible/);
  assert.throws(() => chooseYear(YEARS, "2032"), SheetError);
});

test("le curseur va de rang en rang, même si les années ne sont pas régulières", () => {
  assert.equal(yearAtPosition(YEARS, 0), 2022);
  assert.equal(yearAtPosition(YEARS, 2), 2037);
  assert.equal(yearAtPosition(YEARS, 9), 2037);
  assert.equal(yearAtPosition(YEARS, -1), 2022);
  assert.equal(positionOfYear(YEARS, 2032), 1);
  assert.equal(neighbourYear(YEARS, 2032, 1), 2037);
  assert.equal(neighbourYear(YEARS, 2037, 1), 2037);
  assert.equal(neighbourYear(YEARS, 2022, -1), 2022);
  assert.equal(yearLabel(2022, 2022), "2022 (t0, début de la simulation)");
  assert.equal(yearLabel(2052, 2022), "2052 (t0 + 30 ans, simulé)");
});

test("une décimale à la française, arrondie comme %.1f (demi au pair sur une vraie égalité)", () => {
  assert.equal(format1(26.74), "26,7");
  assert.equal(format1(26.75), "26,8");
  assert.equal(format1(26.25), "26,2");
  assert.equal(format1(0.15), "0,1"); // 0,15 vaut 0,1499… en binaire
  assert.equal(format1(31), "31,0");
});

test("l'échelle de couleurs de G est fixe : même valeur, même couleur, quelle que soit l'année", () => {
  assert.deepEqual(rampColor(0, 0, 350).rgb, [255, 255, 204]);
  assert.deepEqual(rampColor(350, 0, 350).rgb, [128, 0, 38]);
  assert.deepEqual(rampColor(175, 0, 350).rgb, [253, 141, 60]);
  assert.equal(rampColor(400, 0, 350).outside, true);
  assert.deepEqual(rampColor(400, 0, 350).rgb, [128, 0, 38]);
  assert.equal(rampColor(10, 0, 350).outside, false);
  assert.deepEqual(legendTicks(0, 350), ["0", "175", "350"]);
});

const cell = (): CellV2 => ({
  cell_id: 820, x: 700012.5, y: 6500487.5, station_type: "type_humide", vegetation_type: "type_humide_futaie_fictive_mature",
  h_ceiling_m: 28,
  years: [
    { year: 2032, provisoire: true, stems_ha: 480, basal_area_m2_ha: 40.25, d130_mean_cm: 30.04, h_dom_m: 29.26,
      composition: [{ species: "09", stems_ha: 360, basal_area_m2_ha: 30, share: 0.75 }, { species: "61", stems_ha: 120, basal_area_m2_ha: 10.25, share: 0.25 }],
      flags: [{ kind: "hdom_au_dessus_du_plafond", message: "H_dom 29,3 m > plafond 28 m", value: 29.26 }], volume_m3_ha: null, carbon_t_ha: null },
    { year: 2022, provisoire: true, stems_ha: 400, basal_area_m2_ha: 30, d130_mean_cm: 28.1, h_dom_m: 26.92, h0_m: 26.9,
      composition: [{ species: "09", stems_ha: 400, basal_area_m2_ha: 30, share: 1 }], flags: [], volume_m3_ha: null, carbon_t_ha: null },
    { year: 2037, provisoire: true, stems_ha: 0, basal_area_m2_ha: 0, d130_mean_cm: null, h_dom_m: null,
      composition: [], flags: [{ kind: "trouee_sans_recrue", message: "trouée sans recrue" }], volume_m3_ha: null, carbon_t_ha: null },
  ],
});

test("la fiche de l'année montre toute l'évolution, rangée par année, l'année choisie en évidence", () => {
  const f = formatEvolution(cell(), 2032, ["résultat provisoire"]);
  assert.deepEqual(f.table.map((r) => r.year), [2022, 2032, 2037]);
  assert.deepEqual(f.table.map((r) => r.selected), [false, true, false]);
  const r = f.table[1]!;
  assert.equal(r.stems, "480");
  assert.equal(r.basalArea, "40,2");
  assert.equal(r.d130, "30,0");
  assert.equal(r.hdom, "29,3");
  assert.equal(r.aboveCeiling, true);
  assert.equal(r.composition, "09 75 % · 61 25 %");
  assert.deepEqual(r.flags, ["H_dom au-dessus du plafond"]);
  assert.equal(f.table[0]!.aboveCeiling, false);
  assert.equal(f.headline, "2032 : G 40,2 m²/ha · H_dom 29,3 m (plafond 28,0 m), au-dessus du plafond");
  assert.equal(f.command, "viewer-massif -- --x 700012.5 --y 6500487.5 --year 2032");
  assert.equal(f.provisional, true);
});

test("une année sans arbre vivant le dit, sans inventer de hauteur ni de diamètre", () => {
  const f = formatEvolution(cell(), 2037, []);
  const r = f.table[2]!;
  assert.equal(r.hdom, "aucun arbre vivant");
  assert.equal(r.d130, "sans tige");
  assert.equal(r.composition, "aucune");
  assert.deepEqual(r.flags, ["trouée sans recrue"]);
  assert.match(f.headline, /H_dom : aucun arbre vivant/);
});

test("un plafond inconnu est dit, jamais remplacé", () => {
  const c = cell();
  c.h_ceiling_m = null;
  const f = formatEvolution(c, 2032, []);
  assert.equal(f.ceiling, "plafond inconnu");
  assert.equal(f.table[1]!.aboveCeiling, false);
});

test("les mentions « non validée écologiquement » et « volume et carbone non calculés » sont toujours là", () => {
  const n = sheetNotes(["résultat provisoire", "résultat provisoire"]);
  assert.equal(n.filter((x) => x === "résultat provisoire").length, 1);
  assert.ok(n.some((x) => x.includes("non validée écologiquement")));
  assert.ok(n.some((x) => x.includes("volume et carbone non calculés")));
  const deja = sheetNotes(["X non validée écologiquement", "volume et carbone non calculés (post)"]);
  assert.equal(deja.length, 2);
  const byLabel = Object.fromEntries(formatEvolution(cell(), 2022, []).rows.map((l) => [l.label, l.value]));
  assert.equal(byLabel["Volume et carbone"], "non calculés");
});

test("une année absente de la fiche est une erreur explicite", () => {
  assert.throws(() => formatEvolution(cell(), 2050, []), /pas de fiche pour l'année 2050/);
});

test("dès que sim/ existe, la vue n'accepte que des fiches v2", () => {
  const v2: TileSheetsV2 = { schema_version: 2, tile: "t", source: "sim", notes: ["n"], cells: [cell()] };
  assert.equal(indexSheets([v2], 2).get(820)?.h_ceiling_m, 28);
  assert.throws(() => indexSheets([{ schema_version: 1, tile: "t", cells: [] }], 2), /schema_version 2 attendu/);
  assert.throws(() => indexSheets([v2], 1), /schema_version 1 attendu/);
});

// Revue de la PR n° 9, M1 : jamais plus de deux couches d'arbres, même lors d'un changement d'année rapide.
test("couches d'arbres : une année abandonnée est retirée avant que la suivante soit ajoutée", () => {
  const slots = new TreeLayerSlots<string>();
  const alive = new Set<string>(); // ce que la scène garde réellement
  let peak = 0;
  const load = (name: string) => {
    for (const d of slots.beforeAdd()) alive.delete(d);
    slots.added(name);
    alive.add(name);
    peak = Math.max(peak, alive.size);
    assert.equal(alive.size, slots.count);
  };
  load("2022");
  for (const d of slots.commit("2022")) alive.delete(d); // 2022 affichée
  load("2032"); // en chargement
  load("2037"); // changement d'année rapide : 2032 abandonnée, retirée avant l'ajout de 2037
  load("2042");
  assert.ok(peak <= 2, `pic de ${peak} couches`);
  assert.deepEqual([...alive].sort(), ["2022", "2042"]);
  // le tail de la charge abandonnée ne retire rien une seconde fois ni ne remplace la couche affichée
  assert.deepEqual(slots.abandon("2032"), []);
  assert.deepEqual(slots.commit("2037"), []);
  assert.equal(slots.shown, "2022");
  // la dernière gagne : 2042 remplace 2022, qui est rendue pour être retirée
  assert.deepEqual(slots.commit("2042"), ["2022"]);
  assert.equal(slots.shown, "2042");
  assert.equal(slots.count, 1);
});

test("couches d'arbres : une couche en échec est rendue une seule fois", () => {
  const slots = new TreeLayerSlots<string>();
  slots.added("2032");
  assert.deepEqual(slots.abandon("2032"), ["2032"]);
  assert.deepEqual(slots.abandon("2032"), []);
  assert.equal(slots.count, 0);
});
