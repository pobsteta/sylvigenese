import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { isAllowedPath, isFictitiousZone } from "../src/serveur.ts";

test("seuls tiles/, web/ et dtm.tif de la zone sont servis", () => {
  assert.equal(isAllowedPath("tiles/2021/tileset.json"), true);
  assert.equal(isAllowedPath("web/cells/t.json"), true);
  assert.equal(isAllowedPath("dtm.tif"), true);
  assert.equal(isAllowedPath("stands.parquet"), false);
  assert.equal(isAllowedPath("inputs/ser.gpkg"), false);
});

test("la remontée de dossier est refusée", () => {
  assert.equal(isAllowedPath("tiles/../inputs/x"), false);
  assert.equal(isAllowedPath("../config.yml"), false);
});

test("zone.yml avec fictive: true marque une zone fictive ; sans marqueur, la zone est réelle", () => {
  const d = mkdtempSync(join(tmpdir(), "zone-"));
  assert.equal(isFictitiousZone(d), false);
  writeFileSync(join(d, "zone.yml"), "schema_version: 1\nfictive: true\n");
  assert.equal(isFictitiousZone(d), true);
  writeFileSync(join(d, "zone.yml"), "schema_version: 1\nfictive: false\n");
  assert.equal(isFictitiousZone(d), false);
  writeFileSync(join(d, "zone.yml"), ": : illisible [");
  assert.equal(isFictitiousZone(d), false);
});
