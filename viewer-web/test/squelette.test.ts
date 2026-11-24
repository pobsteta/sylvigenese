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
import { ErreurModule, lireConfig } from "../src/config.ts";

const RACINE = resolve(import.meta.dirname, "..", "..");
const CONFIG = join(RACINE, "config.yml");
const MAIN = join(RACINE, "viewer-web", "src", "main.ts");

function fauxValidateur(code: number): string {
  const chemin = join(mkdtempSync(join(tmpdir(), "vw-")), "validate");
  writeFileSync(chemin, `import sys\nsys.exit(${code})\n`);
  return chemin;
}

// Lance `node src/main.ts --config <config>` depuis la racine ; rend le code de sortie.
function lancer(config: string, validateur?: string): number {
  const env = { ...process.env };
  if (validateur !== undefined) env["SYLVIGENESE_VALIDATE"] = validateur;
  const r = spawnSync(process.execPath, [MAIN, "--config", config], { cwd: RACINE, env });
  assert.notEqual(r.status, null);
  return r.status as number;
}

test("lit config.yml du dépôt", () => {
  const config = lireConfig(CONFIG);
  assert.equal(config.crs, "EPSG:2154");
  assert.equal(config.grid.resolution_m, 25);
  assert.equal(config.management, "none");
});

test("config.yml absent : erreur", () => {
  assert.throws(() => lireConfig("/nulle/part/config.yml"), ErreurModule);
});

test("sortie 0 si le validateur dit 0", () => {
  assert.equal(lancer(CONFIG, fauxValidateur(0)), 0);
});

test("sortie 2 si le validateur refuse", () => {
  assert.equal(lancer(CONFIG, fauxValidateur(3)), 2);
});

test("sortie 2 si le validateur est absent", () => {
  assert.equal(lancer(CONFIG, "/nulle/part/validate"), 2);
});

test("sortie 2 si config.yml est absent", () => {
  assert.equal(lancer("/nulle/part/config.yml", fauxValidateur(0)), 2);
});

test("intégration : le vrai validateur accepte config.yml", () => {
  // Rouge tant que contracts/validate (mission 009) est absent de l'arbre.
  assert.equal(lancer(CONFIG), 0);
});
