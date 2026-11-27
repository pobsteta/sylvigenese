// Tests de tools/ci/valider_gltf.mjs (mission 075) : node --test tools/ci/valider_gltf.test.mjs
// Des .glb minimaux sont fabriqués ici : valide, avertissement seul (propriété inconnue), erreur (version 3.0).
import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync, mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const SCRIPT = fileURLToPath(new URL("./valider_gltf.mjs", import.meta.url));

function glb(json) {
  let j = Buffer.from(JSON.stringify(json), "utf-8");
  j = Buffer.concat([j, Buffer.alloc((4 - (j.length % 4)) % 4, 0x20)]);
  const total = 12 + 8 + j.length;
  const h = Buffer.alloc(20);
  h.write("glTF", 0, "latin1"); h.writeUInt32LE(2, 4); h.writeUInt32LE(total, 8);
  h.writeUInt32LE(j.length, 12); h.write("JSON", 16, "latin1");
  return Buffer.concat([h, j]);
}

function lance(...args) {
  return spawnSync(process.execPath, [SCRIPT, ...args], { encoding: "utf-8", env: { ...process.env, GITHUB_STEP_SUMMARY: "" } });
}

function dossier(contenus) {
  const d = mkdtempSync(join(tmpdir(), "gltf-"));
  for (const [nom, buf] of Object.entries(contenus)) {
    mkdirSync(join(d, nom, ".."), { recursive: true });
    writeFileSync(join(d, nom), buf);
  }
  return d;
}

test("un .glb valide : code 0, zéro erreur", () => {
  const d = dossier({ "a/ok.glb": glb({ asset: { version: "2.0" } }) });
  try {
    const r = lance(d);
    assert.equal(r.status, 0, r.stdout + r.stderr);
    assert.match(r.stdout, /1 \.glb validés : 0 erreur\(s\), 0 avertissement\(s\)/);
  } finally { rmSync(d, { recursive: true }); }
});

test("un avertissement est compté et dit, sans faire échouer", () => {
  const d = dossier({ "w.glb": glb({ asset: { version: "2.0" }, propriete_inconnue: 1 }) });
  try {
    const r = lance(d);
    assert.equal(r.status, 0, r.stdout + r.stderr);
    assert.match(r.stdout, /0 erreur\(s\), 1 avertissement\(s\)/);
    assert.match(r.stdout, /avertissement UNEXPECTED_PROPERTY/);
  } finally { rmSync(d, { recursive: true }); }
});

test("une erreur (severity 0) fait échouer, même à côté de fichiers valides", () => {
  const d = dossier({ "ok.glb": glb({ asset: { version: "2.0" } }), "sous/mauvais.glb": glb({ asset: { version: "3.0" } }) });
  try {
    const r = lance(d);
    assert.equal(r.status, 1, r.stdout + r.stderr);
    assert.match(r.stdout, /ECHEC .*mauvais\.glb : 1 erreur\(s\)/);
    assert.match(r.stdout, /2 \.glb validés : 1 erreur\(s\)/);
  } finally { rmSync(d, { recursive: true }); }
});

test("un fichier qui n'est pas un .glb lisible est un échec, pas un saut", () => {
  const d = dossier({ "casse.glb": Buffer.from("pas du glTF") });
  try {
    const r = lance(d);
    assert.equal(r.status, 1, r.stdout + r.stderr);
    assert.match(r.stdout + r.stderr, /ECHEC|illisible/);
  } finally { rmSync(d, { recursive: true }); }
});

test("aucun .glb, chemin absent ou aucun argument : code 2 (jamais un succès à vide)", () => {
  const d = dossier({ "lisez.txt": Buffer.from("x") });
  try {
    assert.equal(lance(d).status, 2);
    assert.equal(lance(join(d, "absent")).status, 2);
    assert.equal(lance().status, 2);
  } finally { rmSync(d, { recursive: true }); }
});
