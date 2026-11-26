// Tests de la fiche v3 (mission 054) : volume aérien total, carbone aérien, racines à part et provisoires, volume
// partiel, null avec sa raison, version des fiches déduite de l'index et des fiches.
import { test } from "node:test";
import assert from "node:assert/strict";
import { SheetError, indexSheets } from "../src/sheet.ts";
import {
  BELOW_PRECISION, MENTIONS_COURTES, SIGNAL_MISSING, amountText, formatEvolutionV3, missingMentionsV3, sheetNotesV3, sheetVersion, shareText,
  type CellV3, type Tarif, type TileSheetsV3, type YearSheetV3,
} from "../src/volume.ts";

const TARIF: Tarif = { name: "tarif NEMETON v5 (tarif-nemeton), provisoire", commit: "9821693", provisoire: true };
const RAISON = "aucune tige vivante de la cellule n'est calculée : toutes sont hors du domaine du tarif";

const year = (over: Partial<YearSheetV3>): YearSheetV3 => ({
  year: 2022, provisoire: true, stems_ha: 400, basal_area_m2_ha: 30, d130_mean_cm: 28.1, h_dom_m: 26.92,
  composition: [{ species: "09", stems_ha: 400, basal_area_m2_ha: 30, share: 1, volume_m3_ha: 312.44, carbon_t_ha: 85.06, basal_area_not_computed_share: 0 }],
  flags: [], volume_m3_ha: 312.44, carbon_t_ha: 85.06, stems_not_computed_ha: 0, basal_area_not_computed_share: 0,
  volume_partiel: false, ...over,
});

const cell = (roots = false): CellV3 => {
  const ys = [
    year({ year: 2032, volume_m3_ha: 401.26, carbon_t_ha: 110.3, stems_not_computed_ha: 40, basal_area_not_computed_share: 0.123, volume_partiel: true }),
    year({ year: 2022, h0_m: 26.9 }),
    year({ year: 2042, volume_m3_ha: null, carbon_t_ha: null, stems_not_computed_ha: 400, basal_area_not_computed_share: 1,
      volume_partiel: true, not_computed_reason: RAISON }),
  ];
  if (roots) {
    ys[0]!.root_carbon_t_ha = 22.04;
    ys[1]!.root_carbon_t_ha = 17.01;
    ys[2]!.root_carbon_t_ha = null;
  }
  return { cell_id: 0, x: 700012.5, y: 6500987.5, station_type: "type_humide", vegetation_type: "futaie", h_ceiling_m: 28, years: ys };
};

const NOTES = [
  "trajectoire technique, non validée écologiquement (décision du 25/11/2026)",
  "volume_m3_ha : volume aérien total (tige et branches)",
  "carbon_t_ha : carbone aérien",
  "sol et bois mort : non modélisés (hors v1)",
];
// Notes d'une fiche dont une année est partielle : le contrat y exige aussi « volume partiel ».
const NOTES_PARTIEL = [...NOTES, "volume partiel : une partie des tiges n'est pas calculée"];

test("v3 : volume aérien total et carbone aérien de chaque année, rangés, sans recalcul", () => {
  const f = formatEvolutionV3(cell(), 2022, NOTES, TARIF);
  assert.deepEqual(f.table.map((r) => r.year), [2022, 2032, 2042]);
  assert.deepEqual(f.table.map((r) => r.volume), ["312,4", "401,3", "non calculé"]);
  assert.deepEqual(f.table.map((r) => r.carbon), ["85,1", "110,3", "non calculé"]);
  assert.equal(f.headline, "2022 : volume aérien total 312,4 m³/ha · carbone aérien 85,1 tC/ha, provisoires");
  assert.match(f.context, /^2022 : G 30,0 m²\/ha · H_dom 26,9 m/);
  assert.equal(f.mentions, MENTIONS_COURTES);
  assert.equal(f.command, "viewer-massif -- --x 700012.5 --y 6500987.5 --year 2022");
  assert.equal(f.table[0]!.stems, "400"); // colonnes de la v2 gardées
});

test("v3 : « volume partiel » avec la part de surface terrière non calculée", () => {
  const f = formatEvolutionV3(cell(), 2032, NOTES_PARTIEL, TARIF);
  assert.equal(f.table[0]!.partial, "");
  assert.equal(f.table[1]!.partial, "volume partiel : 12 % de G non calculée");
  assert.equal(f.headline, "2032 : volume aérien total 401,3 m³/ha · carbone aérien 110,3 tC/ha, provisoires (volume partiel : 12 % de G non calculée)");
  assert.ok(f.notes.some((n) => n.includes("volume partiel")), "mention « volume partiel » absente des notes");
  assert.deepEqual(f.notes, NOTES_PARTIEL, "les notes affichées sont celles de la fiche, rien d'ajouté");
});

test("v3 : une part non nulle n'est jamais dite 0 %, une part sous 1 jamais 100 %", () => {
  assert.equal(shareText(0.001), "moins de 1 %");
  assert.equal(shareText(0.999), "plus de 99 %");
  assert.equal(shareText(1), "100 %");
  assert.equal(shareText(0.5), "50 %");
});

test("v3 : null veut dire « non calculé », avec la raison de la fiche, jamais 0", () => {
  const f = formatEvolutionV3(cell(), 2042, NOTES, TARIF);
  const r = f.table[2]!;
  assert.equal(r.notComputed, true);
  assert.equal(r.volume, "non calculé");
  assert.equal(r.partial, "volume partiel : 100 % de G non calculée");
  assert.deepEqual(f.reasons, [{ years: [2042], reason: RAISON }]);
  assert.equal(f.headline, `2042 : rien n'est calculé (volume et carbone) — ${RAISON}`);
  assert.doesNotMatch(f.headline, /\b0 m³|\b0 tC/);
});

test("v3 : un null sans raison est signalé, pas complété", () => {
  const c = cell();
  delete c.years[2]!.not_computed_reason;
  const f = formatEvolutionV3(c, 2022, NOTES, TARIF);
  assert.match(f.reasons[0]!.reason, /raison non donnée par la fiche/);
});

test("v3 : sans root_carbon_t_ha, ni colonne ni ligne racines", () => {
  const f = formatEvolutionV3(cell(false), 2022, NOTES, TARIF);
  assert.equal(f.hasRoots, false);
  assert.ok(f.table.every((r) => r.roots === null));
  assert.ok(!f.rows.some((r) => /racines/i.test(r.label)));
});

test("v3 : avec root_carbon_t_ha, racines à part, marquées provisoires, jamais additionnées", () => {
  const f = formatEvolutionV3(cell(true), 2022, NOTES, TARIF);
  assert.equal(f.hasRoots, true);
  assert.deepEqual(f.table.map((r) => r.roots), ["17,0", "22,0", "non calculé"]);
  assert.deepEqual(f.table.map((r) => r.carbon), ["85,1", "110,3", "non calculé"]); // carbone aérien inchangé
  const racines = f.rows.find((r) => /racines/i.test(r.label));
  assert.ok(racines && /provisoire/.test(racines.label), "ligne racines sans « provisoire »");
  assert.equal(racines.value, "17,0 tC/ha");
});

test("v3 : les notes affichées sont celles de la fiche, sans doublon et sans rien ajouter", () => {
  assert.deepEqual(sheetNotesV3(NOTES, false), NOTES);
  assert.deepEqual(sheetNotesV3([...NOTES, NOTES[0]!], false), NOTES); // pas de doublon
  assert.deepEqual(missingMentionsV3(NOTES, false), []);
  assert.ok(!sheetNotesV3(NOTES, false).some((x) => x.includes("volume et carbone non calculés")));
  for (const k of ["volume aérien total", "carbone aérien", "sol et bois mort non comptés", "non validée écologiquement"]) {
    assert.ok(MENTIONS_COURTES.includes(k), `ligne courte sans « ${k} »`);
  }
});

test("v3 : une mention exigée absente de la fiche est signalée, jamais écrite à sa place (mission 056)", () => {
  // fiche sans aucune mention : quatre signalements, aucune mention inventée par la vue
  const vide = sheetNotesV3([], false);
  assert.equal(vide.length, 4);
  assert.ok(vide.every((n) => n.startsWith(SIGNAL_MISSING)), `ligne qui n'est pas un signalement : ${vide.join(" | ")}`);
  assert.deepEqual(missingMentionsV3([], false), ["non validée écologiquement", "volume aérien total", "carbone aérien", "sol et bois mort"]);
  // une année partielle sans « volume partiel » dans la fiche : les notes de la fiche, puis un seul signalement
  const partiel = sheetNotesV3(NOTES, true);
  assert.deepEqual(partiel.slice(0, NOTES.length), NOTES);
  assert.equal(partiel.length, NOTES.length + 1);
  assert.ok(partiel.at(-1)!.startsWith(SIGNAL_MISSING) && partiel.at(-1)!.includes("« volume partiel »"));
  // même chose par la fiche affichée
  const f = formatEvolutionV3(cell(), 2032, NOTES, TARIF);
  assert.deepEqual(f.notes.filter((n) => !n.startsWith(SIGNAL_MISSING)), NOTES, "mention ajoutée par la vue");
  assert.equal(f.notes.filter((n) => n.startsWith(SIGNAL_MISSING)).length, 1);
});

test("v3 : une valeur non nulle sous la précision affichée s'écrit « < 0,1 », jamais 0,0 (mission 056)", () => {
  assert.equal(amountText(0.0197), "< 0,1");     // racines de la cellule 4 de la zone échantillon du testeur
  assert.equal(amountText(0.049), "< 0,1");
  assert.equal(amountText(0.05), "0,1");
  assert.equal(amountText(0), "0,0");             // zéro est un fait (cellule sans arbre vivant)
  assert.equal(amountText(312.44), "312,4");
  const c = cell(true);
  c.years[1] = { ...c.years[1]!, volume_m3_ha: 0.03, carbon_t_ha: 0.004, root_carbon_t_ha: 0.0197 };
  const f = formatEvolutionV3(c, 2022, NOTES, TARIF);
  assert.equal(f.table[0]!.volume, BELOW_PRECISION);
  assert.equal(f.table[0]!.carbon, BELOW_PRECISION);
  assert.equal(f.table[0]!.roots, BELOW_PRECISION);
  assert.equal(f.rows.find((r) => /racines/i.test(r.label))!.value, "< 0,1 tC/ha");
  assert.equal(f.headline, "2022 : volume aérien total < 0,1 m³/ha · carbone aérien < 0,1 tC/ha, provisoires");
});

test("v3 : le tarif est dit, provisoire, et la ligne « Volume et carbone : non calculés » de la v2 disparaît", () => {
  const f = formatEvolutionV3(cell(), 2022, NOTES, TARIF);
  const byLabel = Object.fromEntries(f.rows.map((l) => [l.label, l.value]));
  assert.equal(byLabel["Tarif (provisoire)"], "tarif NEMETON v5 (tarif-nemeton), provisoire, commit 9821693");
  assert.equal(byLabel["Volume et carbone"], undefined);
  assert.equal(formatEvolutionV3(cell(), 2022, NOTES, null).rows.at(-1)!.value, "non dit par la fiche");
});

test("v3 : une année absente est une erreur explicite", () => {
  assert.throws(() => formatEvolutionV3(cell(), 2050, NOTES, TARIF), /pas de fiche pour l'année 2050/);
});

// ---------------------------------------------------------------- version déduite de l'index et des fiches
const SIM = { source: "sim" as const, notes: ["trajectoire technique, non validée écologiquement"] };

test("version : état initial 1, sim avec fiches v2 2, sim avec fiches v3 3", () => {
  assert.equal(sheetVersion(null, [{ schema_version: 1 }]), 1);
  assert.equal(sheetVersion({ source: "trees_init", notes: ["x"] }, [{ schema_version: 1 }]), 1);
  assert.equal(sheetVersion({ ...SIM, notes: [...SIM.notes, "volume et carbone non calculés (post)"] }, [{ schema_version: 2 }]), 2);
  assert.equal(sheetVersion(SIM, [{ schema_version: 3 }, { schema_version: 3 }]), 3);
});

test("version : fiches mêlées, v1 avec sim, ou index qui contredit la v3 sont refusés", () => {
  assert.throws(() => sheetVersion(SIM, [{ schema_version: 2 }, { schema_version: 3 }]), /versions différentes/);
  assert.throws(() => sheetVersion(SIM, [{ schema_version: 1 }]), /schema_version 2 ou 3 attendu/);
  assert.throws(() => sheetVersion(SIM, []), SheetError);
  assert.throws(() => sheetVersion({ ...SIM, notes: ["volume et carbone non calculés"] }, [{ schema_version: 3 }]),
    /pas du même passage d'assets/);
});

test("version : indexSheets accepte la v3 et refuse une autre version", () => {
  const v3: TileSheetsV3 = { schema_version: 3, tile: "t", source: "sim", notes: NOTES, tarif: TARIF, cells: [cell()] };
  assert.equal(indexSheets([v3], 3).get(0)?.years.length, 3);
  assert.throws(() => indexSheets([v3], 2), /schema_version 2 attendu/);
});
