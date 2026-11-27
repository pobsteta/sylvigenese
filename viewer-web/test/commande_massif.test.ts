// Commande à copier de la fiche web = arguments acceptés par la vue Godot (décision Q7, plan m6a T7 ; mission 073).
// Deux étages :
//  1. toujours : la commande, découpée comme un shell, respecte la grammaire de viewer_args.gd
//     (`--zone <dossier> --x <X> --y <Y> --year <A>`, + `--selftest`) ; un miroir de ses règles, en TypeScript ;
//  2. en CI (SYLVIGENESE_VIEWER_BIN = binaire Godot exporté) : la vraie vue reçoit ces arguments sur la zone d'essai
//     viewer-massif/tests/fixtures/zone_m6 et sort à 0 en écrivant ses comptes (--selftest).
import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { resolve, join } from "node:path";
import { mkdtempSync, writeFileSync, chmodSync, rmSync, accessSync, constants } from "node:fs";
import { tmpdir } from "node:os";
import { formatSheet, withZone, zoneDirOf, SheetError, type Cell } from "../src/sheet.ts";

const RACINE = resolve(import.meta.dirname, "../..");
const ZONE_ESSAI = resolve(import.meta.dirname, "../../viewer-massif/tests/fixtures/zone_m6");

const cell: Cell = {
  cell_id: 1, x: 700250, y: 6500250, station_type: "s", vegetation_type: "v",
  years: [{ year: 2022, provisoire: true, composition: [] , volume_m3_ha: null, carbon_t_ha: null }],
};

// Miroir des règles de viewer_args.gd : quatre options à valeur, --selftest seul, rien d'autre.
function acceptedByViewer(args: string[]): { zone: string; x: number; y: number; year: number } {
  const vals = new Map<string, string>();
  for (let i = 0; i < args.length; i++) {
    const a = args[i]!;
    if (a === "--selftest") continue;
    assert.ok(["--zone", "--x", "--y", "--year"].includes(a), `option inconnue ${a}`);
    const v = args[++i];
    assert.ok(v !== undefined && !v.startsWith("--"), `valeur manquante pour ${a}`);
    vals.set(a, v);
  }
  for (const k of ["--zone", "--x", "--y", "--year"]) assert.ok(vals.has(k), `option manquante ${k}`);
  const x = Number(vals.get("--x")), y = Number(vals.get("--y")), year = Number(vals.get("--year"));
  assert.ok(Number.isFinite(x) && Number.isFinite(y) && Number.isInteger(year), "valeur non numérique");
  return { zone: vals.get("--zone")!, x, y, year };
}

function argsOf(command: string): string[] {
  const t = command.split(/\s+/);
  assert.deepEqual(t.slice(0, 2), ["tools/viewer-massif", "--"]);
  return t.slice(2);
}

test("la commande de la fiche dit la zone, puis x, y, année, et la vue l'accepte", () => {
  const f = formatSheet(cell, 2022);
  const full = withZone(f.command, zoneDirOf("zone_fictive"));
  assert.equal(full, "tools/viewer-massif -- --zone data/zone_fictive --x 700250 --y 6500250 --year 2022");
  const r = acceptedByViewer(argsOf(full));
  assert.deepEqual(r, { zone: "data/zone_fictive", x: 700250, y: 6500250, year: 2022 });
});

test("sans zone, ou avec une zone vide ou à espace, la commande est refusée (pas de valeur par défaut)", () => {
  const f = formatSheet(cell, 2022);
  assert.throws(() => withZone(f.command, ""), SheetError);
  assert.throws(() => withZone(f.command, "ma zone"), SheetError);
  assert.throws(() => withZone("autre-commande --x 1 --y 2", "z"), /inattendue/);
});

test("withZone ne double pas --zone", () => {
  const f = formatSheet(cell, 2022);
  const once = withZone(f.command, "data/z");
  assert.throws(() => withZone(once, "data/z"), SheetError);
});

test("la vraie vue exportée accepte la commande de la fiche (CI : SYLVIGENESE_VIEWER_BIN)", { skip: !process.env.SYLVIGENESE_VIEWER_BIN }, () => {
  const full = withZone(formatSheet(cell, 2022).command, ZONE_ESSAI);
  const r = spawnSync(process.env.SYLVIGENESE_VIEWER_BIN!, ["--headless", "--", "--selftest", ...argsOf(full)], { encoding: "utf-8" });
  assert.equal(r.status, 0, `${r.stdout}\n${r.stderr}`);
  assert.match(r.stdout, /^SELFTEST \{.*"trees":\s*4/m);
});

test("la commande de la fiche, collée telle quelle depuis la racine du dépôt, lance le script avec les bons arguments", () => {
  // Le moteur est remplacé par un faux « godot » qui écrit ses arguments : on voit ce que la vue recevrait.
  accessSync(join(RACINE, "tools/viewer-massif"), constants.X_OK);
  const d = mkdtempSync(join(tmpdir(), "faux-godot-"));
  try {
    const faux = join(d, "godot");
    writeFileSync(faux, '#!/bin/sh\nfor a in "$@"; do echo "ARG:$a"; done\n');
    chmodSync(faux, 0o755);
    const full = withZone(formatSheet(cell, 2022).command, "viewer-massif/tests/fixtures/zone_m6");
    assert.ok(full.startsWith("tools/viewer-massif -- --zone "), full);
    // Découpage comme un shell sur cette commande simple, puis exécution depuis la racine : le chemin « tools/... » est relatif.
    const [prog, ...args] = full.split(/\s+/);
    const r = spawnSync(prog!, args, { cwd: RACINE, encoding: "utf-8", env: { ...process.env, GODOT: faux, PATH: "/usr/bin:/bin" } });
    assert.equal(r.status, 0, `${r.stdout}\n${r.stderr}`);
    const lus = r.stdout.trim().split("\n").map((l) => l.replace(/^ARG:/, ""));
    assert.deepEqual(lus.slice(0, 3), ["--path", join(RACINE, "viewer-massif"), "--"]);
    assert.deepEqual(lus.slice(3), ["--zone", ZONE_ESSAI, "--x", "700250", "--y", "6500250", "--year", "2022"]);
  } finally {
    rmSync(d, { recursive: true, force: true });
  }
});
