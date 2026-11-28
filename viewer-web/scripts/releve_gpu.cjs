// Relevé des images par seconde de la vue web SUR LA CARTE GRAPHIQUE (mission 088 ; BRIEF §11, critère b de M4).
// À côté de capture.cjs et des sondes de m4, qui forcent SwiftShader sans écran pour tourner pareil en CI : ici,
// Chromium de Playwright s'ouvre À L'ÉCRAN, accélération matérielle demandée, et la carte est choisie (PRIME).
//
// Usage : node viewer-web/scripts/releve_gpu.cjs [--carte nvidia|integree|auto] [--zone m4_charge] [--duree 5000]
//                                                [--sortie data/releves_m4/gpu_<carte>_<date>.json] [--sans-borne]
//   --carte      nvidia (Quadro, par défaut), integree (Intel/AMD) ou auto (le choix du système)
//   --zone       zone servie par `make viewer` (par défaut m4_charge ; elle est préparée si absente)
//   --duree      durée de chaque mesure en ms (mesurerFps de la page)
//   --sans-borne relever aussi sans synchronisation verticale, même si la première mesure n'est pas près de 60
// Sans --sans-borne, la mesure sans borne n'est faite que si une première valeur tombe entre 55 et 62 images par seconde.
//
// « Signaler plutôt que deviner » : le moteur de rendu est lu dans WebGL ; logiciel, illisible ou différent de la carte
// demandée : échec nommé (code 2), AUCUN chiffre écrit. Un écran est nécessaire (DISPLAY).
const path = require("path");
const os = require("os");
const fs = require("fs");
const net = require("net");
const http = require("http");
const { spawn, spawnSync, execSync } = require("child_process");
const gpu = require("./gpu.cjs");

const ROOT = path.resolve(__dirname, "../..");

function loadPlaywright() {
  const roots = [process.env.NODE_PATH, path.resolve(__dirname, "../node_modules"), "/opt/node-tools/node_modules"];
  try { roots.push(execSync("npm root -g", { encoding: "utf8" }).trim()); } catch (e) { /* ignoré */ }
  for (const r of roots.filter(Boolean).flatMap((x) => x.split(path.delimiter))) {
    try { return require(path.join(r, "playwright")); } catch (e) { /* suivant */ }
  }
  return require("playwright");
}

function lireArguments(argv) {
  const o = { carte: "nvidia", zone: "m4_charge", duree: 5000, sortie: null, sansBorne: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--sans-borne") o.sansBorne = true;
    else if (["--carte", "--zone", "--duree", "--sortie"].includes(a)) {
      if (i + 1 >= argv.length) throw new gpu.ErreurGpu(`Option ${a} sans valeur.`);
      o[a.slice(2)] = argv[++i];
    } else throw new gpu.ErreurGpu(`Option inconnue : ${a}`);
  }
  o.carte = gpu.normaliserCarte(o.carte);
  o.duree = Number(o.duree);
  if (!Number.isFinite(o.duree) || o.duree < 1000) throw new gpu.ErreurGpu("--duree : au moins 1000 ms.");
  return o;
}

function portLibre() {
  return new Promise((ok, ko) => {
    const s = net.createServer();
    s.once("error", ko);
    s.listen(0, "127.0.0.1", () => { const p = s.address().port; s.close(() => ok(p)); });
  });
}

function repond(url) {
  return new Promise((ok) => {
    const r = http.get(url, (res) => { res.resume(); ok(res.statusCode === 200); });
    r.on("error", () => ok(false));
    r.setTimeout(2000, () => { r.destroy(); ok(false); });
  });
}

async function servir(zone) {
  const port = await portLibre();
  const proc = spawn("make", ["viewer", `ZONE=${zone}`, `PORT=${port}`], { cwd: ROOT, stdio: ["ignore", "pipe", "pipe"], detached: true });
  let sortie = "";
  proc.stdout.on("data", (d) => { sortie += d; });
  proc.stderr.on("data", (d) => { sortie += d; });
  const url = `http://127.0.0.1:${port}/`;
  const fin = Date.now() + 120000;
  while (Date.now() < fin) {
    if (proc.exitCode !== null) throw new gpu.ErreurGpu(`make viewer s'est arrêté (code ${proc.exitCode}) :\n${sortie.slice(-1500)}`);
    if (await repond(url)) return { url, arreter: () => { try { process.kill(-proc.pid, "SIGTERM"); } catch (e) { /* déjà arrêté */ } } };
    await new Promise((r) => setTimeout(r, 500));
  }
  try { process.kill(-proc.pid, "SIGTERM"); } catch (e) { /* ignoré */ }
  throw new gpu.ErreurGpu(`La page ${url} ne répond pas après 120 s.`);
}

// Moteur de rendu réellement utilisé, lu par le navigateur lui-même.
async function lireMoteur(page) {
  return page.evaluate(() => {
    const c = document.createElement("canvas");
    const g = c.getContext("webgl2") || c.getContext("webgl");
    if (!g) return { renderer: null, vendor: null, version: null };
    const e = g.getExtension("WEBGL_debug_renderer_info");
    return { renderer: e ? g.getParameter(e.UNMASKED_RENDERER_WEBGL) : null, vendor: e ? g.getParameter(e.UNMASKED_VENDOR_WEBGL) : null,
             version: g.getParameter(g.VERSION) };
  });
}

// Une session : un navigateur, une valeur d'options (avec ou sans borne). Renvoie la mesure par année.
async function session(opts, chromium, env, urlPage, sansBorne) {
  const browser = await chromium.launch({ headless: false, env, args: gpu.optionsChromium({ sansBorne }) });
  try {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: 1 });
    const page = await ctx.newPage();
    const erreurs = [];
    page.on("pageerror", (e) => erreurs.push(String(e)));
    await page.goto("about:blank");
    const lu = await lireMoteur(page);
    const moteur = gpu.verifierMoteur(lu, opts.carte);       // échec nommé avant toute mesure
    await page.goto(urlPage, { waitUntil: "load", timeout: 120000 });
    await page.waitForFunction(() => window.sylvigenese && (window.sylvigenese.ready === true || !!window.sylvigenese.error),
      null, { timeout: 300000 });
    const etat = await page.evaluate(() => ({ error: window.sylvigenese.error || null,
      years: Array.isArray(window.sylvigenese.years) ? window.sylvigenese.years.slice() : [] }));
    if (etat.error || !etat.years.length) throw new gpu.ErreurGpu(`La page n'est pas prête : ${etat.error || "aucune année"}.`);
    const annees = {};
    for (const a of etat.years) {
      await page.evaluate((y) => Promise.resolve(window.sylvigenese.setYear(y)), a);
      await page.waitForFunction((y) => window.sylvigenese.year === y && (window.sylvigenese.ready === true || !!window.sylvigenese.error),
        a, { timeout: 300000 });
      let prec = -1;
      for (let k = 0; k < 30; k++) {
        const c = await page.evaluate(() => window.sylvigenese.instanceCount);
        if (c === prec) break;
        prec = c;
        await page.waitForTimeout(1000);
      }
      const fps = await page.evaluate((ms) => window.sylvigenese.mesurerFps(ms), opts.duree);
      const err = await page.evaluate(() => window.sylvigenese.error || null);
      if (fps === null || err) throw new gpu.ErreurGpu(`Année ${a} : mesure impossible (${err || "aucune image rendue"}) ; aucun chiffre n'est écrit.`);
      annees[a] = { instances: prec, fps };
    }
    // Le moteur est relu à la fin : il n'a pas dû changer pendant la mesure (perte de contexte, repli).
    const fin = gpu.verifierMoteur(await lireMoteur(page), opts.carte);
    if (fin.renderer !== moteur.renderer) throw new gpu.ErreurGpu(`Le moteur de rendu a changé pendant la mesure (« ${moteur.renderer} » puis « ${fin.renderer} »).`);
    const taille = await page.evaluate(() => ({ largeur: window.innerWidth, hauteur: window.innerHeight, ratio: window.devicePixelRatio,
      ecran: { largeur: screen.width, hauteur: screen.height } }));
    return { moteur: { ...moteur, version_webgl: lu.version }, navigateur: { nom: "chromium (Playwright)", version: browser.version() },
             resolution: taille, erreurs_page: erreurs, annees };
  } finally {
    await browser.close();
  }
}

async function main() {
  const opts = lireArguments(process.argv.slice(2));
  if (!process.env.DISPLAY && !process.env.WAYLAND_DISPLAY) {
    throw new gpu.ErreurGpu("Aucun écran (ni DISPLAY ni WAYLAND_DISPLAY) : ce relevé ouvre Chromium à l'écran, à lancer depuis la session graphique.");
  }
  const env = gpu.environnementCarte(opts.carte);          // lève si la carte demandée n'a pas de fichier EGL
  const zoneDir = path.join(ROOT, "data", opts.zone);
  if (!fs.existsSync(path.join(zoneDir, "web"))) {
    if (opts.zone !== "m4_charge") throw new gpu.ErreurGpu(`Zone ${zoneDir} absente ou sans web/ : lancer « make assets ZONE=${opts.zone} ».`);
    console.error("Zone m4_charge absente : préparation (quelques minutes).");
    const p = spawnSync("python3", [path.join(__dirname, "preparer_charge.py")], { cwd: ROOT, stdio: "inherit" });
    if (p.status !== 0) throw new gpu.ErreurGpu("La préparation de la zone de charge a échoué (voir ci-dessus).");
  }
  const { chromium } = loadPlaywright();
  const serveur = await servir(opts.zone);
  const date = new Date();
  try {
    const mesures = [];
    const a = await session(opts, chromium, env, serveur.url, false);
    mesures.push({ synchro_verticale: "active (réglage par défaut du navigateur)", annees: a.annees });
    const maxFps = Math.max(...Object.values(a.annees).map((r) => r.fps));
    const borne = Object.values(a.annees).some((r) => gpu.peutEtreBorneeParVsync(r.fps));
    let b = null;
    if (borne || opts.sansBorne) {
      b = await session(opts, chromium, env, serveur.url, true);
      if (b.moteur.renderer !== a.moteur.renderer) throw new gpu.ErreurGpu("Le moteur de rendu diffère entre les deux sessions ; aucun chiffre n'est écrit.");
      mesures.push({ synchro_verticale: "coupée (--disable-gpu-vsync --disable-frame-rate-limit)", annees: b.annees });
    }
    const res = {
      date: date.toISOString(),
      machine: { hote: os.hostname(), systeme: `${os.type()} ${os.release()}`, processeur: (os.cpus()[0] || {}).model || null, ram_go: Math.round(os.totalmem() / 2 ** 30) },
      navigateur: a.navigateur,
      moteur_de_rendu: a.moteur,
      carte_demandee: opts.carte,
      options_chromium: gpu.optionsChromium(),
      variables_carte: Object.fromEntries(Object.entries(env).filter(([k]) => /^(__NV_|__GLX_|__VK_|__EGL_)/.test(k))),
      zone: opts.zone,
      resolution: a.resolution,
      duree_mesure_ms: opts.duree,
      mesures,
      borne_par_synchro_verticale: borne,
      note: borne ? "Une valeur de la première série est proche de 60 : elle peut être bornée par la synchronisation verticale ; voir la seconde série."
                  : `Aucune valeur proche de 60 (maximum ${maxFps}) : la première série n'est pas bornée par la synchronisation verticale.`,
      erreurs_page: a.erreurs_page,
    };
    const stamp = date.toISOString().slice(0, 10);
    const sortie = path.resolve(ROOT, opts.sortie || path.join("data", "releves_m4", `gpu_${opts.carte}_${stamp}.json`));
    fs.mkdirSync(path.dirname(sortie), { recursive: true });
    fs.writeFileSync(sortie, JSON.stringify(res, null, 1) + "\n");
    console.log(JSON.stringify({ moteur: res.moteur_de_rendu.renderer, resolution: res.resolution, mesures, sortie }, null, 1));
  } finally {
    serveur.arreter();
  }
}

main().catch((e) => {
  console.error(e instanceof gpu.ErreurGpu ? `ÉCHEC : ${e.message}` : `ÉCHEC inattendu : ${e && e.stack ? e.stack : e}`);
  process.exit(2);
});
