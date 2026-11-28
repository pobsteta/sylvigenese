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

// ------------------------------------------------------------------ mesures répétées, arguments, aucun JSON en cas d'échec
const releve = createRequire(import.meta.url)("../scripts/releve_gpu.cjs");

test("résumé des mesures : médiane, extrêmes, écart ; instable au-delà de 10 %", () => {
  const ok = gpu.resumerMesures([50, 51, 52]);
  assert.equal(ok.fps, 51);
  assert.equal(ok.min, 50);
  assert.equal(ok.max, 52);
  assert.equal(ok.instable, false);
  const mauvais = gpu.resumerMesures([35, 50, 51]);
  assert.equal(mauvais.fps, 50);
  assert.equal(mauvais.instable, true);
  assert.equal(gpu.resumerMesures([50, 55]).instable, false);      // 5 / 52,5 < 10 %
});

test("résumé des mesures : moins de deux valeurs ou une valeur invalide : refus", () => {
  assert.throws(() => gpu.resumerMesures([50]), /au moins deux/);
  assert.throws(() => gpu.resumerMesures([50, null]), /au moins deux/);
});

test("lireArguments : valeurs par défaut, options, refus", () => {
  const d = releve.lireArguments([]);
  assert.equal(d.carte, "nvidia");
  assert.equal(d.zone, "m4_charge");
  assert.equal(d.mesures, 3);
  assert.equal(d.garderZone, false);
  const o = releve.lireArguments(["--carte", "integree", "--mesures", "4", "--chauffe", "2000", "--duree", "1500", "--garder-zone", "--sans-borne", "--sortie", "x.json"]);
  assert.deepEqual([o.carte, o.mesures, o.chauffe, o.duree, o.garderZone, o.sansBorne, o.sortie], ["integree", 4, 2000, 1500, true, true, "x.json"]);
  assert.throws(() => releve.lireArguments(["--carte"]), /sans valeur/);
  assert.throws(() => releve.lireArguments(["--bidon"]), /inconnue/);
  assert.throws(() => releve.lireArguments(["--carte", "voodoo"]), /inconnue/);
  assert.throws(() => releve.lireArguments(["--mesures", "1"]), /au moins 2/);
  assert.throws(() => releve.lireArguments(["--duree", "10"]), /1000/);
});

function depsEssai(session: unknown) {
  const arrets: string[] = [];
  return {
    arrets,
    deps: {
      session, dossierEgl: dossierEgl(), preparerZone: () => true,
      servir: async () => ({ url: "http://x/", arreter: () => arrets.push("serveur") }),
    },
  };
}

test("garde qui échoue : aucun JSON écrit, serveur arrêté", async () => {
  const sortie = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "rel-")), "gpu.json");
  const { deps, arrets } = depsEssai(async () => gpu.verifierMoteur(SWIFT, "nvidia"));
  const opts = releve.lireArguments(["--sortie", sortie]);
  await assert.rejects(() => releve.executer(opts, deps), /logiciel/);
  assert.equal(fs.existsSync(sortie), false);
  assert.deepEqual(arrets, ["serveur"]);
});

test("mesure réussie : JSON écrit avec toutes les mesures, la zone refaite et l'instabilité", async () => {
  const sortie = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "rel-")), "gpu.json");
  const annee = (m: number[]) => ({ instances: 10, ...gpu.resumerMesures(m), mesures_retenues: m, chauffe_jetee: 1 });
  const { deps } = depsEssai(async () => ({
    moteur: { ...QUADRO, version_webgl: "x" }, navigateur: { nom: "c", version: "1" }, fenetre: { largeur: 1, hauteur: 1, ratio: 1 },
    erreurs_page: [], annees: { 2022: annee([35, 50, 51]), 2023: annee([50, 51, 52]) },
  }));
  const { res } = await releve.executer(releve.lireArguments(["--sortie", sortie]), deps);
  const lu = JSON.parse(fs.readFileSync(sortie, "utf8"));
  assert.equal(lu.zone_refaite_pour_ce_releve, true);
  assert.equal(lu.instable, true);
  assert.equal(res.mesures.length, 1);
  assert.deepEqual(lu.mesures[0].annees["2022"].mesures_retenues, [35, 50, 51]);
  assert.equal(lu.fenetre.largeur, 1);
  assert.equal("ecran" in (lu.fenetre ?? {}), false);
});

// ------------------------------------------------------------------ interruption : codes de sortie des signaux (mission 090)
test("SIGINT sort en 130 et SIGTERM en 143, après l'arrêt du serveur et du navigateur", async () => {
  const ecouteurs: Record<string, () => Promise<void>> = {};
  const proc = { on: (sig: string, f: () => Promise<void>) => { ecouteurs[sig] = f; } };
  const journal: string[] = [];
  releve.installerArretSignaux(proc, async () => { journal.push("arret"); }, (c: number) => { journal.push(`sortie ${c}`); });
  assert.deepEqual(Object.keys(ecouteurs).sort(), ["SIGINT", "SIGTERM"]);
  const muet = console.error; console.error = () => {};
  try {
    await ecouteurs.SIGINT();
    await ecouteurs.SIGTERM();
  } finally { console.error = muet; }
  assert.deepEqual(journal, ["arret", "sortie 130", "arret", "sortie 143"]);
});

test("vrai processus : SIGTERM -> code 143, SIGINT -> code 130", async () => {
  const { spawn } = await import("node:child_process");
  const script = path.resolve(import.meta.dirname ?? path.dirname(new URL(import.meta.url).pathname), "../scripts/releve_gpu.cjs");
  for (const [sig, code] of [["SIGTERM", 143], ["SIGINT", 130]] as const) {
    const enfant = spawn(process.execPath, ["-e", `const r = require(${JSON.stringify(script)}); r.installerArretSignaux(); console.log("pret"); setInterval(() => {}, 1000);`], { stdio: ["ignore", "pipe", "pipe"] });
    await new Promise<void>((ok, ko) => { enfant.stdout.on("data", (d) => { if (String(d).includes("pret")) ok(); }); enfant.on("error", ko); enfant.on("exit", () => ko(new Error("sorti avant d'être prêt"))); });
    enfant.removeAllListeners("exit");
    const fin = new Promise<number | null>((ok) => enfant.on("exit", (c) => ok(c)));
    enfant.kill(sig);
    assert.equal(await fin, code, `${sig} doit sortir en ${code}`);
  }
});
