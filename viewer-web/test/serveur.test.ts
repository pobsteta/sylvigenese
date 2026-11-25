import { test } from "node:test";
import assert from "node:assert/strict";
import { cheminAutorise } from "../src/serveur.ts";

test("seuls tiles/, web/ et dtm.tif de la zone sont servis", () => {
  assert.equal(cheminAutorise("tiles/2021/tileset.json"), true);
  assert.equal(cheminAutorise("web/cells/t.json"), true);
  assert.equal(cheminAutorise("dtm.tif"), true);
  assert.equal(cheminAutorise("stands.parquet"), false);
  assert.equal(cheminAutorise("inputs/ser.gpkg"), false);
});

test("la remontée de dossier est refusée", () => {
  assert.equal(cheminAutorise("tiles/../inputs/x"), false);
  assert.equal(cheminAutorise("../config.yml"), false);
});
