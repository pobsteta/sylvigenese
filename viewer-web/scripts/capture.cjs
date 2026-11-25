// Relevé de la vue (mission 029) : ouvre la page, attend le chargement, relève les instances et les images
// par seconde (référence locale, sans seuil), ouvre une fiche, écrit la capture à deviceScaleFactor 2.
// Usage : node viewer-web/scripts/capture.cjs [url] [capture.png] [copie.png] [oblique.png]
// (la 4e capture est une vue oblique rasante, pour juger le terrain autour de la zone)
// Sans GPU, Chromium rend en logiciel (SwiftShader) : les images par seconde sont alors très basses.
const path = require("path");
const fs = require("fs");
const { execSync } = require("child_process");

function loadPlaywright() {
  const roots = [process.env.NODE_PATH, "/opt/node-tools/node_modules"];
  try { roots.push(execSync("npm root -g", { encoding: "utf8" }).trim()); } catch (e) { /* ignoré */ }
  for (const r of roots.filter(Boolean).flatMap((x) => x.split(path.delimiter))) {
    try { return require(path.join(r, "playwright")); } catch (e) { /* suivant */ }
  }
  return require("playwright");
}

(async () => {
  const url = process.argv[2] || "http://127.0.0.1:8080/";
  const png = process.argv[3] || "tests/fixtures/zone_fictive/web/capture_vue.png";
  const copy = process.argv[4];
  const oblique = process.argv[5];
  const { chromium } = loadPlaywright();
  const browser = await chromium.launch({
    headless: true,
    args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--no-sandbox"],
  });
  const report = { errors: [], console: [] };
  try {
    const page = await (await browser.newContext({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: 2 })).newPage();
    page.on("pageerror", (e) => report.errors.push(String(e)));
    page.on("console", (m) => { const t = m.text(); if (["error", "warning"].includes(m.type()) && !/GL Driver|willReadFrequently/.test(t) && !report.console.includes(t)) report.console.push(t.slice(0, 300)); });
    const t0 = Date.now();
    await page.goto(url, { waitUntil: "load" });
    await page.waitForFunction(() => window.sylvigenese && (window.sylvigenese.ready || window.sylvigenese.error), null, { timeout: 300000 });
    report.attenteMs = Date.now() - t0;
    report.etat = await page.evaluate(() => {
      const s = window.sylvigenese;
      return { ready: s.ready, error: s.error, year: s.year, instanceCount: s.instanceCount, instancesChargees: s.instancesChargees,
               instancesAttendues: s.instancesAttendues, meshesInstancies: s.meshesInstancies, chargementMs: s.chargementMs,
               terrain: s.terrain, fond: s.fond };
    });
    report.fps = await page.evaluate(() => window.sylvigenese.mesurerFps(5000));
    // Fiche : clic réel au centre de la vue, puis repli sur openCell si le clic ne tombe sur aucune cellule.
    await page.mouse.click(640, 400);
    await page.waitForTimeout(1500);
    let visible = await page.locator('[data-testid="cell-sheet"]').isVisible();
    if (!visible) await page.evaluate(() => window.sylvigenese.openCell(820));
    report.ficheParClic = visible;
    report.fiche = await page.locator('[data-testid="cell-sheet"]').innerText();
    await page.waitForTimeout(1500);
    fs.mkdirSync(path.dirname(png), { recursive: true });
    await page.screenshot({ path: png, timeout: 180000 });
    if (oblique) {
      await page.evaluate(() => { document.getElementById("fiche").hidden = true; return window.sylvigenese.placer(1500, 10, 200); });
      await page.waitForTimeout(12000);
      await page.screenshot({ path: oblique, timeout: 180000 });
    }
    if (copy) { fs.mkdirSync(path.dirname(copy), { recursive: true }); fs.copyFileSync(png, copy); }
  } catch (e) {
    report.fatal = String(e && e.message ? e.message : e);
  } finally {
    await browser.close();
  }
  process.stdout.write(JSON.stringify(report, null, 1) + "\n");
})();
