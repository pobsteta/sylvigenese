// Sonde de la fiche v3 dans le navigateur (mission 057) : ouvre la page servie en local (make viewer), et pour
// chaque année de window.sylvigenese.years et chaque cellule demandée, ouvre la fiche, relève son texte (et les
// lignes de ses tableaux, cellule par cellule) et prend les captures demandées.
//
// Interface de la page : celle de tests/m4/probe_view.cjs et tests/m4/probe_temps.cjs (ready, error, years,
// setYear(a), year, openCell(id) ; fiche [data-testid="cell-sheet"] visible avec data-cell-id).
//
// Usage : node probe_fiche_v3.cjs <url> <json>  avec json = {"cells": [id, ...], "dsf": 2,
//         "shots": {"<année>:<cellule>": "<chemin.png>"}}
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
  const out = { errors: [], blocked: [], sheets: {}, shots: [] };
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
      hasSetYear: typeof window.sylvigenese.setYear === "function",
    }));
    const years = Array.isArray(out.state.years) ? out.state.years : [];
    for (const a of years) {
      out.sheets[a] = {};
      try {
        await page.evaluate((y) => Promise.resolve(window.sylvigenese.setYear(y)), a);
        await page.waitForFunction(
          (y) => window.sylvigenese.year === y && (window.sylvigenese.ready === true || !!window.sylvigenese.error),
          a, { timeout: 300000 });
      } catch (e) {
        out.sheets[a].fatal = String(e && e.message ? e.message : e);
        continue;
      }
      for (const c of opts.cells || []) {
        const rec = {};
        try {
          await page.evaluate((i) => window.sylvigenese.openCell(i), c);
          const sel = page.locator('[data-testid="cell-sheet"]');
          await sel.waitFor({ state: "visible", timeout: 30000 });
          await page.waitForFunction(
            (i) => { const e = document.querySelector('[data-testid="cell-sheet"]'); return e && e.getAttribute("data-cell-id") === String(i); },
            c, { timeout: 30000 });
          rec.cellId = await sel.getAttribute("data-cell-id");
          rec.year = await page.evaluate(() => window.sylvigenese.year);
          rec.text = await sel.innerText();
          rec.rows = await sel.evaluate((el) => Array.from(el.querySelectorAll("tr")).map(
            (tr) => Array.from(tr.querySelectorAll("th,td")).map((td) => td.innerText.trim())));
          const shot = (opts.shots || {})[`${a}:${c}`];
          if (shot) {
            await page.screenshot({ path: shot, timeout: 180000 });
            out.shots.push(shot);
          }
        } catch (e) {
          rec.fatal = String(e && e.message ? e.message : e);
        }
        out.sheets[a][c] = rec;
      }
    }
  } catch (e) {
    out.fatal = String(e && e.message ? e.message : e);
  } finally {
    await browser.close();
  }
  process.stdout.write(JSON.stringify(out));
})();
