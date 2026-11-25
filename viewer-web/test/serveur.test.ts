import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { cheminAutorise, zoneFictive } from "../src/serveur.ts";

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

test("zone.yml avec fictive: true marque une zone fictive ; sans marqueur, la zone est réelle", () => {
  const d = mkdtempSync(join(tmpdir(), "zone-"));
  assert.equal(zoneFictive(d), false);
  writeFileSync(join(d, "zone.yml"), "schema_version: 1\nfictive: true\n");
  assert.equal(zoneFictive(d), true);
  writeFileSync(join(d, "zone.yml"), "schema_version: 1\nfictive: false\n");
  assert.equal(zoneFictive(d), false);
  writeFileSync(join(d, "zone.yml"), ": : illisible [");
  assert.equal(zoneFictive(d), false);
});
