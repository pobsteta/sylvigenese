// Serveur statique local de la vue web (mission 029) : `make viewer ZONE=<zone>`.
// Sert la page et son script (construit par esbuild à chaque lancement), ainsi que, en lecture seule,
// tiles/, web/ et dtm.tif de la zone sous /zone/. Aucun service extérieur. Range pris en charge (COG).
// Usage : node src/serveur.ts --zone-dir <dossier> [--port N] [--zone nom]

import { createServer } from "node:http";
import { existsSync, readFileSync, readdirSync, statSync, createReadStream, mkdirSync } from "node:fs";
import { dirname, extname, join, normalize, resolve, sep } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { buildSync } from "esbuild";
import { parse } from "yaml";

const ICI = dirname(fileURLToPath(import.meta.url));
const RACINE_VUE = resolve(ICI, "..");
const DIST = join(RACINE_VUE, "dist");

const TYPES: Record<string, string> = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json",
  ".gltf": "model/gltf+json",
  ".bin": "application/octet-stream",
  ".tif": "image/tiff",
  ".png": "image/png",
};

// Seuls ces chemins de la zone sont servis (liste blanche).
export function cheminAutorise(relatif: string): boolean {
  const p = normalize(relatif).split(sep).join("/");
  if (p.startsWith("..") || p.includes("/../")) return false;
  return p === "dtm.tif" || p.startsWith("tiles/") || p.startsWith("web/");
}

// Années disponibles : sous-dossiers de tiles/ qui portent un tileset.json.
export function anneesDisponibles(zoneDir: string): number[] {
  const tiles = join(zoneDir, "tiles");
  if (!existsSync(tiles)) return [];
  return readdirSync(tiles)
    .filter((n) => /^\d{4}$/.test(n) && existsSync(join(tiles, n, "tileset.json")))
    .map(Number)
    .sort((a, b) => a - b);
}

// Marqueur de zone fictive : <zone>/zone.yml avec `fictive: true`. Absent ou illisible : zone réelle (comportement par défaut).
export function zoneFictive(zoneDir: string): boolean {
  const f = join(zoneDir, "zone.yml");
  if (!existsSync(f)) return false;
  try {
    const c = parse(readFileSync(f, "utf-8")) as { fictive?: unknown } | null;
    return c?.fictive === true;
  } catch {
    return false;
  }
}

export function construirePage(): void {
  mkdirSync(DIST, { recursive: true });
  buildSync({
    entryPoints: [join(RACINE_VUE, "src", "page", "page.ts")],
    bundle: true,
    format: "esm",
    outfile: join(DIST, "app.js"),
    sourcemap: false,
    minify: false,
    target: "es2022",
    logLevel: "warning",
  });
}

function servirFichier(chemin: string, req: import("node:http").IncomingMessage, res: import("node:http").ServerResponse): void {
  const taille = statSync(chemin).size;
  const type = TYPES[extname(chemin)] ?? "application/octet-stream";
  const range = /^bytes=(\d*)-(\d*)$/.exec(req.headers.range ?? "");
  if (range) {
    let debut = range[1] === "" ? Math.max(0, taille - Number(range[2])) : Number(range[1]);
    let fin = range[1] === "" || range[2] === "" ? taille - 1 : Math.min(Number(range[2]), taille - 1);
    if (debut > fin || debut >= taille) {
      res.writeHead(416, { "Content-Range": `bytes */${taille}` }).end();
      return;
    }
    res.writeHead(206, {
      "Content-Type": type, "Accept-Ranges": "bytes", "Content-Length": fin - debut + 1,
      "Content-Range": `bytes ${debut}-${fin}/${taille}`,
    });
    createReadStream(chemin, { start: debut, end: fin }).pipe(res);
    return;
  }
  res.writeHead(200, { "Content-Type": type, "Accept-Ranges": "bytes", "Content-Length": taille, "Cache-Control": "no-cache" });
  createReadStream(chemin).pipe(res);
}

export function creerServeur(zoneDir: string, zone: string) {
  const zoneAbs = resolve(zoneDir);
  return createServer((req, res) => {
    const url = new URL(req.url ?? "/", "http://127.0.0.1");
    const chemin = decodeURIComponent(url.pathname);
    if (chemin === "/" || chemin === "/index.html") {
      servirFichier(join(RACINE_VUE, "src", "page", "index.html"), req, res);
    } else if (chemin === "/app.js") {
      servirFichier(join(DIST, "app.js"), req, res);
    } else if (chemin === "/api/config.json") {
      const corps = JSON.stringify({ zone, annees: anneesDisponibles(zoneAbs), a_dtm: existsSync(join(zoneAbs, "dtm.tif")), fictive: zoneFictive(zoneAbs) });
      res.writeHead(200, { "Content-Type": TYPES[".json"] }).end(corps);
    } else if (chemin.startsWith("/zone/") && cheminAutorise(chemin.slice(6))) {
      const fichier = join(zoneAbs, chemin.slice(6));
      if (existsSync(fichier) && statSync(fichier).isFile()) servirFichier(fichier, req, res);
      else res.writeHead(404).end("introuvable");
    } else {
      res.writeHead(404).end("introuvable");
    }
  });
}

export function main(argv: string[]): number {
  const opt = new Map<string, string>();
  for (let i = 0; i < argv.length; i += 2) opt.set(argv[i] as string, argv[i + 1] ?? "");
  const zoneDir = opt.get("--zone-dir");
  if (!zoneDir || !existsSync(zoneDir)) {
    console.error(`[viewer] erreur : dossier de zone introuvable (${zoneDir ?? "--zone-dir absent"})`);
    return 2;
  }
  if (anneesDisponibles(zoneDir).length === 0) {
    console.error(`[viewer] erreur : aucune tuile 3D dans ${zoneDir}/tiles/<année>/ ; lancer make assets d'abord.`);
    return 2;
  }
  try {
    construirePage();
  } catch (e) {
    console.error(`[viewer] erreur : construction de la page impossible (npm ci dans viewer-web ?) : ${(e as Error).message}`);
    return 2;
  }
  const port = Number(opt.get("--port") ?? 8080);
  creerServeur(zoneDir, opt.get("--zone") ?? "zone").listen(port, "127.0.0.1", () => {
    console.error(`[viewer] vue disponible sur http://127.0.0.1:${port}/ (Ctrl-C pour arrêter)`);
  });
  return -1; // le serveur reste au premier plan
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  const code = main(process.argv.slice(2));
  if (code >= 0) process.exit(code);
}
