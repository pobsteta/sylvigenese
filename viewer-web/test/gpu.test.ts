// Tests du garde-fou du relevé sur carte graphique (mission 088) : sans carte ni navigateur, ils tournent en CI.
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";

const gpu = createRequire(import.meta.url)("../scripts/gpu.cjs");

const QUADRO = { renderer: "ANGLE (NVIDIA Corporation, Quadro K5100M/PCIe/SSE2, OpenGL ES 3.2)", vendor: "Google Inc. (NVIDIA Corporation)" };
const INTEL = { renderer: "ANGLE (Intel, Mesa Intel(R) HD Graphics 4600 (HSW GT2), OpenGL ES 3.2)", vendor: "Google Inc. (Intel)" };
const SWIFT = { renderer: "ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver)", vendor: "Google Inc. (Google)" };

function dossierEgl(): string {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), "egl-"));
  fs.writeFileSync(path.join(d, "10_nvidia.json"), "{}");
  fs.writeFileSync(path.join(d, "50_mesa.json"), "{}");
  return d;
}

test("un moteur logiciel échoue en nommant le moteur, quelle que soit la carte demandée", () => {
  for (const carte of ["nvidia", "integree", "auto"]) {
    assert.throws(() => gpu.verifierMoteur(SWIFT, carte), (e: Error) => e.name === "ErreurGpu" && /logiciel/.test(e.message) && /SwiftShader/.test(e.message));
  }
  for (const r of ["llvmpipe (LLVM 17.0.6, 256 bits)", "Mesa Software Rasterizer", "Microsoft Basic Render Driver"]) {
    assert.throws(() => gpu.verifierMoteur({ renderer: r, vendor: "Mesa" }, "auto"), /logiciel/);
  }
});

test("un moteur illisible échoue", () => {
  for (const lu of [null, {}, { renderer: null, vendor: null }, { renderer: "   ", vendor: "x" }]) {
    assert.throws(() => gpu.verifierMoteur(lu, "auto"), /illisible/);
  }
});

test("un moteur matériel passe et renvoie son nom", () => {
  assert.deepEqual(gpu.verifierMoteur(QUADRO, "nvidia"), QUADRO);
  assert.deepEqual(gpu.verifierMoteur(INTEL, "integree"), INTEL);
  assert.deepEqual(gpu.verifierMoteur(QUADRO, "auto"), QUADRO);
});

test("la carte obtenue doit être la carte demandée", () => {
  assert.throws(() => gpu.verifierMoteur(INTEL, "nvidia"), /NVIDIA demandée/);
  assert.throws(() => gpu.verifierMoteur(QUADRO, "integree"), /intégrée demandée/);
});

test("carte demandée inconnue : refus, valeur absente : auto", () => {
  assert.throws(() => gpu.normaliserCarte("voodoo"), /inconnue/);
  assert.equal(gpu.normaliserCarte(undefined), "auto");
  assert.equal(gpu.normaliserCarte("intégrée"), "integree");
});

test("nvidia pose les variables PRIME et le fichier EGL de NVIDIA", () => {
  const d = dossierEgl();
  const env = gpu.environnementCarte("nvidia", { PATH: "/bin" }, d);
  assert.equal(env.__NV_PRIME_RENDER_OFFLOAD, "1");
  assert.equal(env.__GLX_VENDOR_LIBRARY_NAME, "nvidia");
  assert.equal(env.__EGL_VENDOR_LIBRARY_FILENAMES, path.join(d, "10_nvidia.json"));
  assert.equal(env.PATH, "/bin");
});

test("integree retire les variables NVIDIA et choisit le fichier EGL de Mesa", () => {
  const d = dossierEgl();
  const env = gpu.environnementCarte("integree", { PATH: "/bin", __NV_PRIME_RENDER_OFFLOAD: "1", __GLX_VENDOR_LIBRARY_NAME: "nvidia" }, d);
  assert.equal(env.__NV_PRIME_RENDER_OFFLOAD, undefined);
  assert.equal(env.__GLX_VENDOR_LIBRARY_NAME, undefined);
  assert.equal(env.__EGL_VENDOR_LIBRARY_FILENAMES, path.join(d, "50_mesa.json"));
});

test("l'environnement de base n'est pas modifié ; auto ne touche à rien", () => {
  const base = { PATH: "/bin" };
  gpu.environnementCarte("nvidia", base, dossierEgl());
  assert.deepEqual(base, { PATH: "/bin" });
  assert.deepEqual(gpu.environnementCarte("auto", base, "/inexistant"), base);
});

test("un fichier EGL introuvable est signalé, pas deviné", () => {
  assert.throws(() => gpu.environnementCarte("nvidia", {}, "/dossier/inexistant"), /Aucun fichier EGL/);
});

test("options de Chromium : matériel demandé, jamais SwiftShader ; la borne se coupe à la demande", () => {
  const o = gpu.optionsChromium();
  assert.ok(o.includes("--use-angle=gl-egl") && o.includes("--ignore-gpu-blocklist"));
  assert.ok(!o.some((x: string) => /swiftshader/i.test(x)));
  assert.ok(!o.includes("--disable-gpu-vsync"));
  assert.ok(gpu.optionsChromium({ sansBorne: true }).includes("--disable-gpu-vsync"));
});

test("peut-être bornée par la synchronisation verticale : près de 60 seulement", () => {
  assert.equal(gpu.peutEtreBorneeParVsync(60), true);
  assert.equal(gpu.peutEtreBorneeParVsync(59.8), true);
  assert.equal(gpu.peutEtreBorneeParVsync(30), false);
  assert.equal(gpu.peutEtreBorneeParVsync(144), false);
  assert.equal(gpu.peutEtreBorneeParVsync(null), false);
});
