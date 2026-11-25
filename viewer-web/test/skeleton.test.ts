// Tests du squelette viewer-web (mission 012). Lancés par `make test-web`.
// Le validateur est remplacé par un faux script pour les cas 0 / 3 / absent ; le test
// d'intégration appelle le vrai validateur (rouge tant que contracts/validate, mission 009,
// est absent de l'arbre, sauf si SYLVIGENESE_VALIDATE le désigne).

import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { ModuleError, readConfig } from "../src/config.ts";

const ROOT = resolve(import.meta.dirname, "..", "..");
const CONFIG = join(ROOT, "config.yml");
const MAIN = join(ROOT, "viewer-web", "src", "main.ts");

function fakeValidator(code: number): string {
  const path = join(mkdtempSync(join(tmpdir(), "vw-")), "validate");
  writeFileSync(path, `import sys\nsys.exit(${code})\n`);
  return path;
}

// Lance `node src/main.ts --config <config>` depuis la racine ; rend le code de sortie.
function launch(config: string, validator?: string): number {
  const env = { ...process.env };
  if (validator !== undefined) env["SYLVIGENESE_VALIDATE"] = validator;
  const r = spawnSync(process.execPath, [MAIN, "--config", config], { cwd: ROOT, env });
  assert.notEqual(r.status, null);
  return r.status as number;
}

test("lit config.yml du dépôt", () => {
  const config = readConfig(CONFIG);
  assert.equal(config.crs, "EPSG:2154");
  assert.equal(config.grid.resolution_m, 25);
  assert.equal(config.management, "none");
});

test("config.yml absent : erreur", () => {
  assert.throws(() => readConfig("/nulle/part/config.yml"), ModuleError);
});

test("sortie 0 si le validateur dit 0", () => {
  assert.equal(launch(CONFIG, fakeValidator(0)), 0);
});

test("sortie 2 si le validateur refuse", () => {
  assert.equal(launch(CONFIG, fakeValidator(3)), 2);
});

test("sortie 2 si le validateur est absent", () => {
  assert.equal(launch(CONFIG, "/nulle/part/validate"), 2);
});

test("sortie 2 si config.yml est absent", () => {
  assert.equal(launch("/nulle/part/config.yml", fakeValidator(0)), 2);
});

test("intégration : le vrai validateur accepte config.yml", () => {
  // Rouge tant que contracts/validate (mission 009) est absent de l'arbre.
  assert.equal(launch(CONFIG), 0);
});
