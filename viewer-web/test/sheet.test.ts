import { test } from "node:test";
import assert from "node:assert/strict";
import {
  yearOf, cellIdFromLambert, massifViewerCommand, SheetError, formatSheet, indexSheets,
  type Cell, type TileSheets, type Grid,
} from "../src/sheet.ts";

const GRID: Grid = { x0: 700000, y0: 6501000, resolution: 25, columns: 40, rows: 40 };

const cellule = (id: number, extra: Partial<Cell> = {}): Cell => ({
  cell_id: id, x: 700012.5, y: 6500487.5, station_type: "type_humide",
  vegetation_type: "type_humide_futaie_fictive_mature",
  years: [{
    year: 2021, provisoire: true, composition: [{ species: "09", share: 0.75 }, { species: "61", share: 0.25 }],
    volume_m3_ha: null, carbon_t_ha: null, h0_m: 26.92, density_trees_ha: 112, notes: ["résultat provisoire : essai"],
  }],
  ...extra,
});
const tile = (name: string, cells: Cell[]): TileSheets => ({ schema_version: 1, tile: name, cells });

test("les fiches de plusieurs tuiles sont indexées par cell_id", () => {
  const idx = indexSheets([tile("a", [cellule(1)]), tile("b", [cellule(2)])]);
  assert.deepEqual([...idx.keys()], [1, 2]);
});

test("une cellule présente dans deux tuiles est refusée", () => {
  assert.throws(() => indexSheets([tile("a", [cellule(1)]), tile("b", [cellule(1)])]), SheetError);
});

test("une version de schéma inconnue est refusée", () => {
  assert.throws(() => indexSheets([{ schema_version: 2, tile: "a", cells: [] }]), SheetError);
});

test("le rang de cellule suit grid.tif (ligne * colonnes + colonne)", () => {
  assert.equal(cellIdFromLambert(700012.5, 6500487.5, GRID), 800); // ligne 20, colonne 0
  assert.equal(cellIdFromLambert(700000.1, 6500999.9, GRID), 0);
  assert.equal(cellIdFromLambert(700999.9, 6500000.1, GRID), 1599);
});

test("hors de la grille, aucune cellule", () => {
  assert.equal(cellIdFromLambert(699999, 6500500, GRID), null);
  assert.equal(cellIdFromLambert(700500, 6501001, GRID), null);
  assert.equal(cellIdFromLambert(701000, 6500500, GRID), null);
});

test("la commande à copier suit la spec §1.5", () => {
  assert.equal(massifViewerCommand(700012.5, 6500487.5, 2021), "viewer-massif -- --x 700012.5 --y 6500487.5 --year 2021");
  assert.equal(massifViewerCommand(700000, 6500000, 2030), "viewer-massif -- --x 700000 --y 6500000 --year 2030");
});

test("la fiche dit « non calculé » pour volume et carbone, sans jamais mettre 0", () => {
  const f = formatSheet(cellule(800));
  const byLabel = Object.fromEntries(f.rows.map((l) => [l.label, l.value]));
  assert.match(byLabel["Volume"] as string, /non calculé/);
  assert.match(byLabel["Carbone"] as string, /non calculé/);
  assert.doesNotMatch(JSON.stringify(f.rows), /\b0 m³|\b0 t\/ha/);
});

test("la fiche donne station, type, H0, densité, composition, mention provisoire et commande", () => {
  const f = formatSheet(cellule(800));
  const byLabel = Object.fromEntries(f.rows.map((l) => [l.label, l.value]));
  assert.equal(byLabel["Station"], "type_humide");
  assert.equal(byLabel["Type de végétation"], "type_humide_futaie_fictive_mature");
  assert.match(byLabel["Hauteur dominante H0"] as string, /^26,9 m$/);
  assert.match(byLabel["Densité"] as string, /112 arbres\/ha/);
  assert.deepEqual(f.composition, ["09 : 75 %", "61 : 25 %"]);
  assert.equal(f.provisional, true);
  assert.equal(f.command, "viewer-massif -- --x 700012.5 --y 6500487.5 --year 2021");
});

test("un volume renseigné est affiché avec son unité", () => {
  const c = cellule(800);
  c.years[0]!.volume_m3_ha = 250.4;
  const byLabel = Object.fromEntries(formatSheet(c).rows.map((l) => [l.label, l.value]));
  assert.match(byLabel["Volume"] as string, /250,4 m³\/ha/);
});

test("une valeur absente est dite non renseignée, pas inventée", () => {
  const c = cellule(800);
  delete c.years[0]!.h0_m;
  const byLabel = Object.fromEntries(formatSheet(c).rows.map((l) => [l.label, l.value]));
  assert.equal(byLabel["Hauteur dominante H0"], "non renseignée");
});

test("une année absente de la fiche est une erreur explicite", () => {
  assert.throws(() => yearOf(cellule(1), 2050), /pas de fiche pour l'année 2050/);
});
