// Sonde de la vue dans le temps (mission 045) : ouvre la page servie en local, parcourt les années, compte les
// instances dessinées et relève les images par seconde pour chaque année, ouvre une fiche, prend des captures.
//
// Interface attendue de la page (plan m4a-suite-temps §2 mission D ; fiche 048), en plus de celle de probe_view.cjs :
//   window.sylvigenese.years          années de tiles/index.json, dans l'ordre (tableau d'entiers)
//   window.sylvigenese.setYear(a)     affiche l'année a (peut rendre une promesse) ; ensuite `year` vaut a, et
//                                     `ready` redevient vrai quand la tuile de l'année est chargée et dessinée
//   window.sylvigenese.instanceCount  instances dessinées de l'année affichée, comptées par l'API (Σ InstancedMesh.count)
//   window.sylvigenese.mesurerFps(ms) images par seconde mesurées pendant ms (sinon : propriété `fps`) ; relevées, sans seuil
//
// Usage : node probe_temps.cjs <url> <json>  avec json = {"cell": <id ou null>, "shots": {"<année>": "<chemin.png>"},
//         "dsf": <deviceScaleFactor>}
// Le navigateur est coupé du réseau (seuls 127.0.0.1, localhost, data: et blob: passent).
const path = require("path");
const { execSync } = require("child_process");

function loadPlaywright() {
  const roots = [process.env.NODE_PATH, path.resolve(__dirname, "../../viewer-web/node_modules"), path.resolve(__dirname, "../../node_modules"), "/opt/node-tools/node_modules"];
  try { roots.push(execSync("npm root -g", { encoding: "utf8" }).trim()); } catch (e) { /* ignoré */ }
  for (const r of roots.filter(Boolean).flatMap((x) => x.split(path.delimiter))) {
    try { return require(path.join(r, "playwright")); } catch (e) { /* suivant */ }
  }
  return require("playwright");
}

(async () => {
  const [url, optsJson] = process.argv.slice(2);
  const opts = JSON.parse(optsJson || "{}");
  const { chromium } = loadPlaywright();
  const out = { errors: [], blocked: [], perYear: {}, sheets: {} };
  const browser = await chromium.launch({
    headless: true,
    args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--no-sandbox"],
  });
  try {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: opts.dsf || 1 });
    const page = await ctx.newPage();
    page.on("pageerror", (e) => out.errors.push(String(e)));
    await page.route("**/*", (route) => {
      const u = new URL(route.request().url());
      if (["127.0.0.1", "localhost", "[::1]"].includes(u.hostname) || u.protocol === "data:" || u.protocol === "blob:") {
        return route.continue();
      }
      out.blocked.push(u.href);
      return route.abort();
    });
    await page.goto(url, { waitUntil: "load", timeout: 120000 });
    await page.waitForFunction(
      () => window.sylvigenese && (window.sylvigenese.ready === true || !!window.sylvigenese.error),
      null, { timeout: 300000 });
    out.state = await page.evaluate(() => ({
      ready: window.sylvigenese.ready, error: window.sylvigenese.error || null,
      years: Array.isArray(window.sylvigenese.years) ? window.sylvigenese.years.slice() : window.sylvigenese.years,
      year: window.sylvigenese.year, instanceCount: window.sylvigenese.instanceCount,
      hasSetYear: typeof window.sylvigenese.setYear === "function",
    }));
    const years = Array.isArray(out.state.years) ? out.state.years : [];
    for (const a of years) {
      const rec = {};
      try {
        await page.evaluate((y) => Promise.resolve(window.sylvigenese.setYear(y)), a);
        await page.waitForFunction(
          (y) => window.sylvigenese.year === y && (window.sylvigenese.ready === true || !!window.sylvigenese.error),
          a, { timeout: 300000 });
        // le compte est lu quand il ne bouge plus (deux lectures à 1 s d'écart)
        let prev = -1;
        for (let k = 0; k < 30; k++) {
          const c = await page.evaluate(() => window.sylvigenese.instanceCount);
          if (c === prev) break;
          prev = c;
          await page.waitForTimeout(1000);
        }
        rec.instanceCount = prev;
        rec.year = await page.evaluate(() => window.sylvigenese.year);
        rec.error = await page.evaluate(() => window.sylvigenese.error || null);
        rec.fps = await page.evaluate(async () => (typeof window.sylvigenese.mesurerFps === "function"
          ? await window.sylvigenese.mesurerFps(3000) : window.sylvigenese.fps));
        if (opts.cell !== null && opts.cell !== undefined) {
          await page.evaluate((i) => window.sylvigenese.openCell(i), opts.cell);
          const sel = page.locator('[data-testid="cell-sheet"]');
          await sel.waitFor({ state: "visible", timeout: 30000 });
          out.sheets[a] = { text: await sel.innerText(), cellId: await sel.getAttribute("data-cell-id") };
        }
        const shot = (opts.shots || {})[String(a)];
        if (shot) await page.screenshot({ path: shot, timeout: 180000 });
      } catch (e) {
        rec.fatal = String(e && e.message ? e.message : e);
      }
      out.perYear[a] = rec;
    }
    out.bodyText = await page.evaluate(() => document.body.innerText);
  } catch (e) {
    out.fatal = String(e && e.message ? e.message : e);
  } finally {
    await browser.close();
  }
  process.stdout.write(JSON.stringify(out));
})();
