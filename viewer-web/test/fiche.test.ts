import { test } from "node:test";
import assert from "node:assert/strict";
import {
  anneeDe, cellIdDepuisLambert, commandeViewerMassif, ErreurFiche, formaterFiche, indexerFiches,
  type Cellule, type FichesTuile, type Grille,
} from "../src/fiche.ts";

const GRILLE: Grille = { x0: 700000, y0: 6501000, resolution: 25, colonnes: 40, lignes: 40 };

const cellule = (id: number, extra: Partial<Cellule> = {}): Cellule => ({
  cell_id: id, x: 700012.5, y: 6500487.5, station_type: "type_humide",
  vegetation_type: "type_humide_futaie_fictive_mature",
  years: [{
    year: 2021, provisoire: true, composition: [{ species: "09", share: 0.75 }, { species: "61", share: 0.25 }],
    volume_m3_ha: null, carbon_t_ha: null, h0_m: 26.92, density_trees_ha: 112, notes: ["résultat provisoire : essai"],
  }],
  ...extra,
});
const tuile = (nom: string, cells: Cellule[]): FichesTuile => ({ schema_version: 1, tile: nom, cells });

test("les fiches de plusieurs tuiles sont indexées par cell_id", () => {
  const idx = indexerFiches([tuile("a", [cellule(1)]), tuile("b", [cellule(2)])]);
  assert.deepEqual([...idx.keys()], [1, 2]);
});

test("une cellule présente dans deux tuiles est refusée", () => {
  assert.throws(() => indexerFiches([tuile("a", [cellule(1)]), tuile("b", [cellule(1)])]), ErreurFiche);
});

test("une version de schéma inconnue est refusée", () => {
  assert.throws(() => indexerFiches([{ schema_version: 2, tile: "a", cells: [] }]), ErreurFiche);
});

test("le rang de cellule suit grid.tif (ligne * colonnes + colonne)", () => {
  assert.equal(cellIdDepuisLambert(700012.5, 6500487.5, GRILLE), 800); // ligne 20, colonne 0
  assert.equal(cellIdDepuisLambert(700000.1, 6500999.9, GRILLE), 0);
  assert.equal(cellIdDepuisLambert(700999.9, 6500000.1, GRILLE), 1599);
});

test("hors de la grille, aucune cellule", () => {
  assert.equal(cellIdDepuisLambert(699999, 6500500, GRILLE), null);
  assert.equal(cellIdDepuisLambert(700500, 6501001, GRILLE), null);
  assert.equal(cellIdDepuisLambert(701000, 6500500, GRILLE), null);
});

test("la commande à copier suit la spec §1.5", () => {
  assert.equal(commandeViewerMassif(700012.5, 6500487.5, 2021), "viewer-massif -- --x 700012.5 --y 6500487.5 --year 2021");
  assert.equal(commandeViewerMassif(700000, 6500000, 2030), "viewer-massif -- --x 700000 --y 6500000 --year 2030");
});

test("la fiche dit « non calculé » pour volume et carbone, sans jamais mettre 0", () => {
  const f = formaterFiche(cellule(800));
  const par = Object.fromEntries(f.lignes.map((l) => [l.libelle, l.valeur]));
  assert.match(par["Volume"] as string, /non calculé/);
  assert.match(par["Carbone"] as string, /non calculé/);
  assert.doesNotMatch(JSON.stringify(f.lignes), /\b0 m³|\b0 t\/ha/);
});

test("la fiche donne station, type, H0, densité, composition, mention provisoire et commande", () => {
  const f = formaterFiche(cellule(800));
  const par = Object.fromEntries(f.lignes.map((l) => [l.libelle, l.valeur]));
  assert.equal(par["Station"], "type_humide");
  assert.equal(par["Type de végétation"], "type_humide_futaie_fictive_mature");
  assert.match(par["Hauteur dominante H0"] as string, /^26,9 m$/);
  assert.match(par["Densité"] as string, /112 arbres\/ha/);
  assert.deepEqual(f.composition, ["09 : 75 %", "61 : 25 %"]);
  assert.equal(f.provisoire, true);
  assert.equal(f.commande, "viewer-massif -- --x 700012.5 --y 6500487.5 --year 2021");
});

test("un volume renseigné est affiché avec son unité", () => {
  const c = cellule(800);
  c.years[0]!.volume_m3_ha = 250.4;
  const par = Object.fromEntries(formaterFiche(c).lignes.map((l) => [l.libelle, l.valeur]));
  assert.match(par["Volume"] as string, /250,4 m³\/ha/);
});

test("une valeur absente est dite non renseignée, pas inventée", () => {
  const c = cellule(800);
  delete c.years[0]!.h0_m;
  const par = Object.fromEntries(formaterFiche(c).lignes.map((l) => [l.libelle, l.valeur]));
  assert.equal(par["Hauteur dominante H0"], "non renseignée");
});

test("une année absente de la fiche est une erreur explicite", () => {
  assert.throws(() => anneeDe(cellule(1), 2050), /pas de fiche pour l'année 2050/);
});
