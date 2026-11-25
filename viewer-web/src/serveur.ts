// Serveur statique local de la vue web (mission 029) : `make viewer ZONE=<zone>`.
// Sert la page et son script (construit par esbuild à chaque lancement), ainsi que, en lecture seule,
// tiles/, web/ et dtm.tif de la zone sous /zone/. Aucun service extérieur. Range pris en charge (COG).
// Usage : node src/serveur.ts --zone-dir <dossier> [--port N] [--zone nom]
//
// Interface interne /api/config.json (lue par la page au chargement, non documentée ailleurs ; pas un
// contrat entre modules) : objet JSON { zone, years, has_dtm, fictitious }.
//   - years      : années proposées dans la page, soit les sous-dossiers de tiles/ nommés par quatre chiffres
//                  qui portent un tileset.json (tableau de nombres, vide si tiles/ est absent) ;
//   - has_dtm    : true si dtm.tif existe dans le dossier de la zone ;
//   - fictitious : true si zone.yml de la zone porte « fictive: true » (false si le fichier manque ou est
//                  illisible) ; sert à signaler le jeu fictif, pour ne pas le confondre avec un massif réel.
//   - zone       : nom de la zone passé par --zone.

import { createServer } from "node:http";
import { existsSync, readFileSync, readdirSync, statSync, createReadStream, mkdirSync } from "node:fs";
import { dirname, extname, join, normalize, resolve, sep } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { buildSync } from "esbuild";
import { parse } from "yaml";

const HERE = dirname(fileURLToPath(import.meta.url));
const VIEWER_ROOT = resolve(HERE, "..");
const DIST = join(VIEWER_ROOT, "dist");

const MIME_TYPES: Record<string, string> = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json",
  ".gltf": "model/gltf+json",
  ".bin": "application/octet-stream",
  ".tif": "image/tiff",
  ".png": "image/png",
};

// Seuls ces chemins de la zone sont servis (liste blanche).
export function isAllowedPath(relatif: string): boolean {
  const p = normalize(relatif).split(sep).join("/");
  if (p.startsWith("..") || p.includes("/../")) return false;
  return p === "dtm.tif" || p.startsWith("tiles/") || p.startsWith("web/");
}

// Années disponibles : sous-dossiers de tiles/ qui portent un tileset.json.
export function availableYears(zoneDir: string): number[] {
  const tiles = join(zoneDir, "tiles");
  if (!existsSync(tiles)) return [];
  return readdirSync(tiles)
    .filter((n) => /^\d{4}$/.test(n) && existsSync(join(tiles, n, "tileset.json")))
    .map(Number)
    .sort((a, b) => a - b);
}

// Marqueur de zone fictive : <zone>/zone.yml avec `fictive: true`. Absent ou illisible : zone réelle (comportement par défaut).
export function isFictitiousZone(zoneDir: string): boolean {
  const f = join(zoneDir, "zone.yml");
  if (!existsSync(f)) return false;
  try {
    const c = parse(readFileSync(f, "utf-8")) as { fictive?: unknown } | null;
    return c?.fictive === true;
  } catch {
    return false;
  }
}

export function buildPage(): void {
  mkdirSync(DIST, { recursive: true });
  buildSync({
    entryPoints: [join(VIEWER_ROOT, "src", "page", "page.ts")],
    bundle: true,
    format: "esm",
    outfile: join(DIST, "app.js"),
    sourcemap: false,
    minify: false,
    target: "es2022",
    logLevel: "warning",
  });
}

function serveFile(path: string, req: import("node:http").IncomingMessage, res: import("node:http").ServerResponse): void {
  const size = statSync(path).size;
  const type = MIME_TYPES[extname(path)] ?? "application/octet-stream";
  const range = /^bytes=(\d*)-(\d*)$/.exec(req.headers.range ?? "");
  if (range) {
    let rangeStart = range[1] === "" ? Math.max(0, size - Number(range[2])) : Number(range[1]);
    let rangeEnd = range[1] === "" || range[2] === "" ? size - 1 : Math.min(Number(range[2]), size - 1);
    if (rangeStart > rangeEnd || rangeStart >= size) {
      res.writeHead(416, { "Content-Range": `bytes */${size}` }).end();
      return;
    }
    res.writeHead(206, {
      "Content-Type": type, "Accept-Ranges": "bytes", "Content-Length": rangeEnd - rangeStart + 1,
      "Content-Range": `bytes ${rangeStart}-${rangeEnd}/${size}`,
    });
    createReadStream(path, { start: rangeStart, end: rangeEnd }).pipe(res);
    return;
  }
  res.writeHead(200, { "Content-Type": type, "Accept-Ranges": "bytes", "Content-Length": size, "Cache-Control": "no-cache" });
  createReadStream(path).pipe(res);
}

export function createViewerServer(zoneDir: string, zone: string) {
  const zoneAbs = resolve(zoneDir);
  return createServer((req, res) => {
    const url = new URL(req.url ?? "/", "http://127.0.0.1");
    const path = decodeURIComponent(url.pathname);
    if (path === "/" || path === "/index.html") {
      serveFile(join(VIEWER_ROOT, "src", "page", "index.html"), req, res);
    } else if (path === "/app.js") {
      serveFile(join(DIST, "app.js"), req, res);
    } else if (path === "/api/config.json") {
      const body = JSON.stringify({ zone, years: availableYears(zoneAbs), has_dtm: existsSync(join(zoneAbs, "dtm.tif")), fictitious: isFictitiousZone(zoneAbs) });
      res.writeHead(200, { "Content-Type": MIME_TYPES[".json"] }).end(body);
    } else if (path.startsWith("/zone/") && isAllowedPath(path.slice(6))) {
      const file = join(zoneAbs, path.slice(6));
      if (existsSync(file) && statSync(file).isFile()) serveFile(file, req, res);
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
  if (availableYears(zoneDir).length === 0) {
    console.error(`[viewer] erreur : aucune tuile 3D dans ${zoneDir}/tiles/<année>/ ; lancer make assets d'abord.`);
    return 2;
  }
  try {
    buildPage();
  } catch (e) {
    console.error(`[viewer] erreur : construction de la page impossible (npm ci dans viewer-web ?) : ${(e as Error).message}`);
    return 2;
  }
  const port = Number(opt.get("--port") ?? 8080);
  createViewerServer(zoneDir, opt.get("--zone") ?? "zone").listen(port, "127.0.0.1", () => {
    console.error(`[viewer] vue disponible sur http://127.0.0.1:${port}/ (Ctrl-C pour arrêter)`);
  });
  return -1; // le serveur reste au premier plan
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  const code = main(process.argv.slice(2));
  if (code >= 0) process.exit(code);
}
