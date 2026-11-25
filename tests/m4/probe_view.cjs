// Sonde de la vue web (mission 030) : ouvre la page servie en local, attend le chargement, lit le compteur
// d'instances exposé par la page, ouvre des fiches de cellule et écrit un JSON sur la sortie standard.
//
// Interface attendue de la page (à implémenter par la vue, mission 029) :
//   window.sylvigenese.ready          booléen, vrai quand la tuile est chargée et dessinée
//   window.sylvigenese.error          null, ou une chaîne en français si le chargement a échoué
//   window.sylvigenese.instanceCount  nombre d'instances dessinées, compté par l'API (Σ InstancedMesh.count)
//   window.sylvigenese.year           année de la tuile affichée (entier)
//   window.sylvigenese.openCell(id)   ouvre la fiche de la cellule `id` (cell_id de la fiche JSON), comme le ferait un clic
//   élément [data-testid="cell-sheet"] visible, avec data-cell-id, dont le texte contient : type de station,
//   type de végétation, codes d'essence de la composition, « provisoire », volume et carbone (dits non calculés),
//   et la commande « viewer-massif -- --x <X> --y <Y> --year <A> »
//
// Usage : node probe_view.cjs <url> <id,id,...> [capture.png]
// Le navigateur est coupé du réseau : toute requête hors 127.0.0.1 / localhost est abandonnée (la vue doit
// s'afficher sans service extérieur, fiche 029).
const path = require("path");
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
  const [url, ids, shot] = process.argv.slice(2);
  const { chromium } = loadPlaywright();
  const out = { errors: [], blocked: [], sheets: {} };
  const browser = await chromium.launch({
    headless: true,
    args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--no-sandbox"],
  });
  try {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: 2 });
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
      null, { timeout: 240000 });
    out.state = await page.evaluate(() => ({
      ready: window.sylvigenese.ready, error: window.sylvigenese.error || null,
      instanceCount: window.sylvigenese.instanceCount, year: window.sylvigenese.year,
      hasOpenCell: typeof window.sylvigenese.openCell === "function",
    }));
    for (const id of (ids || "").split(",").filter(Boolean).map(Number)) {
      await page.evaluate((i) => window.sylvigenese.openCell(i), id);
      const sel = page.locator('[data-testid="cell-sheet"]');
      await sel.waitFor({ state: "visible", timeout: 30000 });
      out.sheets[id] = {
        text: await sel.innerText(),
        cellId: await sel.getAttribute("data-cell-id"),
      };
    }
    if (shot) await page.screenshot({ path: shot });
  } catch (e) {
    out.fatal = String(e && e.message ? e.message : e);
  } finally {
    await browser.close();
  }
  process.stdout.write(JSON.stringify(out));
})();
