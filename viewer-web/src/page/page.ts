// Page de la vue web (mission 029) : GlobeView iTowns centrée sur la zone, tuile 3D des arbres,
// carte des types de végétation (COG), terrain local (dtm.tif), fiche de cellule au clic.
// Code navigateur : bundlé par esbuild. La logique pure est dans ../sheet.ts (testée par node --test).
import * as THREE from "three";
import * as itowns from "itowns";
import { fromUrl } from "geotiff";
import proj4 from "proj4";
import {
  cellIdFromLambert, formatSheet, indexSheets,
  type Cell, type TileSheets, type Grid,
} from "../sheet.ts";

interface State {
  ready: boolean;
  error: string | null;
  year: number | null;
  instanceCount: number;
  instancesChargees: number;
  instancesAttendues: number | null;
  meshesInstancies: number;
  fps: number;
  chargementMs: number | null;
  terrain: string;
  fond: string;
  openCell: (id: number) => boolean;
  mesurerFps: (ms?: number) => Promise<number>;
  placer: (range: number, tilt: number, heading: number) => Promise<void>;
}

const state: State = {
  ready: false, error: null, year: null, instanceCount: 0, instancesChargees: 0, instancesAttendues: null,
  meshesInstancies: 0, fps: 0, chargementMs: null, terrain: "", fond: "", openCell: () => false,
  mesurerFps: async () => 0,
  placer: async () => {},
};
(window as unknown as { sylvigenese: State }).sylvigenese = state;

const $ = (id: string) => document.getElementById(id) as HTMLElement;
const L93 = "+proj=lcc +lat_1=49 +lat_2=44 +lat_0=46.5 +lon_0=3 +x_0=700000 +y_0=6600000 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs";
itowns.CRS.defs("EPSG:2154", L93);
const toL93 = proj4("EPSG:4326", L93);

function say(text: string, error = false): void {
  const m = $("message");
  m.hidden = false;
  m.className = error ? "erreur" : "";
  m.textContent = text;
}

async function json<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} : HTTP ${r.status}`);
  return (await r.json()) as T;
}

// ---------------------------------------------------------------- rasters locaux (COG, MNT)
interface Raster {
  grid: Grid;
  values: ArrayLike<number>;
  nodata: number | null;
}

async function readRaster(url: string): Promise<Raster> {
  const tiff = await fromUrl(url);
  const image = await tiff.getImage();
  const [x0, y0] = image.getOrigin() as [number, number];
  const [rx] = image.getResolution() as [number, number];
  const values = (await image.readRasters({ interleave: true })) as unknown as ArrayLike<number>;
  const nodata = image.getGDALNoData();
  return { grid: { x0, y0, resolution: Math.abs(rx), columns: image.getWidth(), rows: image.getHeight() }, values, nodata };
}

// Palette : une teinte par valeur (au plus 16 types ici) ; la légende est tirée des mêmes valeurs.
function colorOf(value: number, total: number): string {
  return `hsl(${Math.round((360 * value) / Math.max(total, 1)) % 360} 65% 50%)`;
}

// Sources de tuiles locales : l'adresse porte l'emprise (w,s,e,n en degrés), le chargeur dessine la tuile.
function extentUrl(tile: { toExtent: (crs: string) => itowns.Extent }): string {
  const e = tile.toExtent("EPSG:4326");
  return `local://tuile?w=${e.west}&s=${e.south}&e=${e.east}&n=${e.north}`;
}
function extentOf(url: string) {
  const p = new URL(url.replace("local://", "http://x/")).searchParams;
  return { w: Number(p.get("w")), s: Number(p.get("s")), e: Number(p.get("e")), n: Number(p.get("n")) };
}
const DIM = 256;
const MAP_OPACITY = 0.5;
// Limites des tuiles du MNT IGN (RGE ALTI) sur la France, reprises de l'exemple d'iTowns (layers/JSONLayers/IGN_MNT_HIGHRES.json).
const IGN_DEM_LIMITS = {
  "11": { minTileRow: 442, maxTileRow: 1267, minTileCol: 1344, maxTileCol: 2683 },
  "12": { minTileRow: 885, maxTileRow: 2343, minTileCol: 3978, maxTileCol: 5126 },
  "13": { minTileRow: 1770, maxTileRow: 4687, minTileCol: 7957, maxTileCol: 10253 },
  "14": { minTileRow: 3540, maxTileRow: 9375, minTileCol: 15914, maxTileCol: 20507 },
};

// Le service IGN est-il joignable (3 s) ? Sinon la vue s'affiche sans lui.
async function probeIgn(): Promise<boolean> {
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 3000);
    const r = await fetch("https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetCapabilities", { signal: ctrl.signal });
    clearTimeout(t);
    return r.ok;
  } catch {
    return false;
  }
}

function localSource(fetcher: (url: string) => Promise<THREE.Texture>, zoomMax: number): itowns.TMSSource {
  const src = new itowns.TMSSource({
    url: "local://${z}/${y}/${x}", crs: "EPSG:4326", format: "image/png", fetcher,
    zoom: { min: 0, max: zoomMax }, attribution: { name: "sylvigenese" },
  } as never);
  (src as unknown as { urlFromExtent: unknown }).urlFromExtent = extentUrl;
  return src;
}

function mapTextureLoader(r: Raster, colors: Map<number, string>) {
  const g = r.grid;
  const tmp = document.createElement("canvas").getContext("2d", { willReadFrequently: true }) as CanvasRenderingContext2D;
  const rgb = new Map<number, [number, number, number]>();
  for (const [v, c] of colors) {
    tmp.fillStyle = c; tmp.fillRect(0, 0, 1, 1);
    const d = tmp.getImageData(0, 0, 1, 1).data;
    rgb.set(v, [d[0] as number, d[1] as number, d[2] as number]);
  }
  return async (url: string): Promise<THREE.Texture> => {
    const { w, s, e, n } = extentOf(url);
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = DIM;
    const ctx = canvas.getContext("2d") as CanvasRenderingContext2D;
    const img = ctx.createImageData(DIM, DIM);
    const rgba = new Uint8ClampedArray(img.data.buffer);
    for (let j = 0; j < DIM; j++) {
      const lat = n - ((j + 0.5) / DIM) * (n - s);
      for (let i = 0; i < DIM; i++) {
        const lon = w + ((i + 0.5) / DIM) * (e - w);
        const [x, y] = toL93.forward([lon, lat]) as [number, number];
        const id = cellIdFromLambert(x, y, g);
        if (id === null) continue;
        const v = r.values[id] as number;
        const c = v === r.nodata ? undefined : rgb.get(v);
        if (!c) continue;
        const k = 4 * (j * DIM + i);
        rgba[k] = c[0]; rgba[k + 1] = c[1]; rgba[k + 2] = c[2]; rgba[k + 3] = 200;
      }
    }
    ctx.putImageData(img, 0, 0);
    return new THREE.CanvasTexture(canvas);
  };
}

const DEM_NODATA = -9999;

// Nombre de cellules du MNT sans valeur (nodata), pour le dire à l'écran.
function minAltitude(r: Raster): number {
  let m = Infinity;
  for (let i = 0; i < r.values.length; i++) {
    const v = r.values[i] as number;
    if (v !== r.nodata && v < m) m = v;
  }
  return m;
}

function countNodata(r: Raster): number {
  let n = 0;
  for (let i = 0; i < r.values.length; i++) if (r.values[i] === r.nodata) n++;
  return n;
}

// Tuile d'altitudes à partir du MNT local. Hors de l'emprise du MNT, et sur ses cellules sans valeur, la tuile porte
// NODATA_MNT : iTowns reprend alors la valeur de la tuile parente (terrain IGN si joint, sinon ellipsoïde).
// Aucune altitude n'est inventée ni étendue au-delà du bord. Seule exception, demandée pour un jeu fictif : `plan` =
// altitude minimale du MNT, plan neutre hors emprise (dit à l'écran).
function dtmTextureLoader(r: Raster, flatLevel: number | null) {
  const g = r.grid;
  const east = g.x0 + g.columns * g.resolution, south = g.y0 - g.rows * g.resolution;
  const raw = (c: number, l: number): number | null => {
    if (c < 0 || l < 0 || c >= g.columns || l >= g.rows) return null;
    const v = r.values[l * g.columns + c] as number;
    return v === r.nodata ? null : v;
  };
  return async (url: string): Promise<THREE.Texture> => {
    const { w, s, e, n } = extentOf(url);
    const data = new Float32Array(DIM * DIM).fill(DEM_NODATA);
    for (let j = 0; j < DIM; j++) {
      const lat = n - ((j + 0.5) / DIM) * (n - s);
      for (let i = 0; i < DIM; i++) {
        const lon = w + ((i + 0.5) / DIM) * (e - w);
        const [x, y] = toL93.forward([lon, lat]) as [number, number];
        if (x < g.x0 || x >= east || y <= south || y > g.y0) { // hors emprise : nodata, ou plan neutre (jeu fictif)
          if (flatLevel !== null) data[j * DIM + i] = flatLevel;
          continue;
        }
        if (raw(Math.floor((x - g.x0) / g.resolution), Math.floor((g.y0 - y) / g.resolution)) === null) continue; // cellule sans valeur
        // bilinéaire entre centres de cellules, poids renormalisés sur les voisins valides
        const fc = (x - g.x0) / g.resolution - 0.5, fl = (g.y0 - y) / g.resolution - 0.5;
        const c0 = Math.floor(fc), l0 = Math.floor(fl), tx = fc - c0, ty = fl - l0;
        let sum = 0, weight = 0;
        for (const [dc, dl, p] of [[0, 0, (1 - tx) * (1 - ty)], [1, 0, tx * (1 - ty)], [0, 1, (1 - tx) * ty], [1, 1, tx * ty]] as const) {
          const v = raw(c0 + dc, l0 + dl);
          if (v !== null) { sum += v * p; weight += p; }
        }
        if (weight > 0) data[j * DIM + i] = sum / weight;
      }
    }
    const t = new THREE.DataTexture(data, DIM, DIM, THREE.RedFormat, THREE.FloatType);
    (t as unknown as { internalFormat: string }).internalFormat = "R32F";
    t.needsUpdate = true;
    return t;
  };
}

// ---------------------------------------------------------------- comptage des instances (API three)
function countInstances(root: THREE.Object3D) {
  let meshes = 0, loaded = 0, drawn = 0;
  const units = new Set<THREE.Object3D>();
  root.traverse((o) => {
    const m = o as THREE.InstancedMesh;
    if (!m.isInstancedMesh) return;
    // Un noeud glTF à plusieurs primitives (tronc, houppier) donne un groupe de InstancedMesh de même effectif :
    // c'est un seul jeu d'arbres, compté une fois.
    const p = m.parent;
    const group = p && (p as THREE.Group).isGroup && p.children.every((c) => (c as THREE.InstancedMesh).isInstancedMesh);
    const unit = group ? (p as THREE.Object3D) : m;
    meshes += m.count;
    if (units.has(unit)) return;
    units.add(unit);
    loaded += m.count;
    let visible = true;
    for (let a: THREE.Object3D | null = m; a; a = a.parent) if (!a.visible) { visible = false; break; }
    if (visible) drawn += m.count;
  });
  return { meshes, loaded, drawn };
}

// ---------------------------------------------------------------- démarrage
async function startViewer(): Promise<void> {
  const startedAt = performance.now();
  const cfg = await json<{ zone: string; years: number[]; has_dtm: boolean; fictitious: boolean }>("/api/config.json");
  const year = cfg.years[cfg.years.length - 1] as number;
  state.year = year;
  $("annee-texte").textContent = `${year} (une seule année disponible)`;
  $("etat-source").textContent = `Source : tiles/${year}/ et web/ de la zone « ${cfg.zone} », lues le ${new Date().toLocaleDateString("fr-FR")}`;

  const tilesetUrl = `/zone/tiles/${year}/tileset.json`;
  const tileset = await json<{ root: { boundingVolume: { region: number[] }; children?: { extras?: { tile?: string } }[] }; extras?: { instances?: number } }>(tilesetUrl);
  state.instancesAttendues = tileset.extras?.instances ?? null;
  const names = (tileset.root.children ?? []).map((c) => c.extras?.tile).filter((t): t is string => !!t);
  const sheets = indexSheets(await Promise.all(names.map((t) => json<TileSheets>(`/zone/web/cells/${t}.json`))));

  const cog = await readRaster("/zone/web/rasters/vegetation_map.tif");
  // Légende : la valeur du COG et le nom du type viennent des fiches (source unique : web/).
  const vegetationNames = new Map<number, string>();
  for (let id = 0; id < cog.values.length; id++) {
    const v = cog.values[id] as number;
    const f = sheets.get(id);
    if (v !== cog.nodata && f && !vegetationNames.has(v)) vegetationNames.set(v, f.vegetation_type);
  }
  const values = [...vegetationNames.keys()].sort((a, b) => a - b);
  const colors = new Map(values.map((v) => [v, colorOf(v, Math.max(...values) + 1)]));
  $("legende-corps").innerHTML = values
    .map((v) => `<div><i style="background:${colors.get(v)}"></i>${(vegetationNames.get(v) ?? "").replace(/^type_|_fictive/g, "").replace(/_/g, " ")}</div>`)
    .join("");

  const [w, s, e, n] = tileset.root.boundingVolume.region as [number, number, number, number];
  const rad = 180 / Math.PI;
  const center = new itowns.Coordinates("EPSG:4326", ((w + e) / 2) * rad, ((s + n) / 2) * rad, 0);
  const view = new itowns.GlobeView($("vue") as HTMLDivElement,
    { coord: center, range: 2600, tilt: 45, heading: 0 } as never,
    { controls: { minDistance: 50 } } as never);

  // Les matériaux glTF sont physiques : sans lumière les arbres sont noirs. Soleil bas du sud-ouest, repéré dans le
  // repère local de la zone (haut, est, nord), pour que les houppiers aient un côté éclairé et un côté sombre.
  const lon = center.longitude * Math.PI / 180, lat = center.latitude * Math.PI / 180;
  const up = new THREE.Vector3(Math.cos(lat) * Math.cos(lon), Math.cos(lat) * Math.sin(lon), Math.sin(lat));
  const eastV = new THREE.Vector3(-Math.sin(lon), Math.cos(lon), 0);
  const northV = new THREE.Vector3().crossVectors(up, eastV);
  const sunElevation = (35 * Math.PI) / 180;
  const sunDirection = new THREE.Vector3()
    .addScaledVector(up, Math.sin(sunElevation))
    .addScaledVector(eastV, -Math.cos(sunElevation) * 0.6)
    .addScaledVector(northV, -Math.cos(sunElevation) * 0.8);
  view.scene.add(new THREE.AmbientLight(0xffffff, 1.0));
  const sun = new THREE.DirectionalLight(0xfff2dd, 2.8);
  sun.position.copy(sunDirection.normalize().multiplyScalar(1e7));
  view.scene.add(sun);

  // Terrain : MNT local sur son emprise ; hors emprise, terrain IGN si joignable, sinon ellipsoïde. Dit dans la page.
  // Zone fictive (zone.yml) : aucune donnée réelle mêlée aux données fictives, donc ni terrain ni orthophoto IGN.
  const ign = cfg.fictitious ? false : await probeIgn();
  let terrainIgn = false;
  if (ign) {
    try {
      const src = new itowns.WMTSSource({
        url: "https://data.geopf.fr/wmts?", crs: "EPSG:4326", format: "image/x-bil;bits=32",
        name: "ELEVATION.ELEVATIONGRIDCOVERAGE.HIGHRES", tileMatrixSet: "WGS84G", attribution: { name: "IGN" },
        tileMatrixSetLimits: IGN_DEM_LIMITS,
      } as never);
      await view.addLayer(new itowns.ElevationLayer("mnt-ign", { source: src, noDataValue: -99999, clampValues: { min: 0 } } as never));
      terrainIgn = true;
    } catch { /* repli : ellipsoïde */ }
  }
  const outsideExtent = cfg.fictitious ? "hors zone : plan neutre pour l'affichage, jeu fictif"
    : terrainIgn ? "hors emprise : terrain IGN (RGE ALTI)" : "hors emprise : ellipsoïde, altitude 0";
  if (cfg.has_dtm) {
    try {
      const mnt = await readRaster("/zone/dtm.tif");
      const withoutValue = countNodata(mnt);
      const layer = new itowns.ElevationLayer("mnt-local", {
        source: localSource(dtmTextureLoader(mnt, cfg.fictitious ? minAltitude(mnt) : null), 17), scale: 1, noDataValue: DEM_NODATA,
      } as never);
      await view.addLayer(layer);
      state.terrain = `Terrain : MNT local (dtm.tif, 25 m) sur son emprise, altitudes NGF sans conversion RAF20 ; ${outsideExtent}${cfg.fictitious ? ` (altitude ${Math.round(minAltitude(mnt) * 10) / 10} m)` : ""}.` +
        (withoutValue > 0 ? ` ${withoutValue} cellule(s) du MNT sans valeur : terrain du niveau parent.` : "");
    } catch (err) {
      state.terrain = `Terrain : ${terrainIgn ? "IGN" : "ellipsoïde"} (MNT local illisible : ${(err as Error).message}).`;
    }
  } else {
    state.terrain = `Terrain : ${terrainIgn ? "terrain IGN (RGE ALTI)" : "ellipsoïde"} (pas de dtm.tif dans la zone) ; les arbres peuvent flotter ou s'enfoncer.`;
  }
  $("etat-terrain").textContent = state.terrain;

  // Fond IGN : facultatif, seulement s'il est joignable.
  state.fond = cfg.fictitious ? "Fond : aucun (jeu fictif : pas de données réelles mêlées)." : "Fond : IGN injoignable, la vue s'affiche sans fond.";
  if (ign) {
    try {
      const src = new itowns.WMTSSource({
        url: "https://data.geopf.fr/wmts", name: "ORTHOIMAGERY.ORTHOPHOTOS", tileMatrixSet: "PM",
        format: "image/jpeg", crs: "EPSG:3857", attribution: { name: "IGN" },
      } as never);
      await view.addLayer(new itowns.ColorLayer("fond-ign", { source: src } as never));
      state.fond = "Fond : orthophoto IGN (data.geopf.fr).";
    } catch { /* message de repli ci-dessus */ }
  }
  $("etat-fond").textContent = state.fond;

  // La carte des types est une couche du sol (sous les arbres), d'opacité réglable ; défaut modéré.
  const vegetationMap = new itowns.ColorLayer("types-vegetation", {
    source: localSource(mapTextureLoader(cog, colors), 19), transparent: true, opacity: MAP_OPACITY,
  } as never);
  await view.addLayer(vegetationMap);
  const slider = $("opacite") as HTMLInputElement;
  slider.value = String(MAP_OPACITY);
  slider.addEventListener("input", () => {
    vegetationMap.opacity = Number(slider.value);
    view.notifyChange(vegetationMap);
  });

  const trees = new itowns.OGC3DTilesLayer("arbres", {
    source: new itowns.OGC3DTilesSource({ url: tilesetUrl }), sseThreshold: 2,
  } as never);
  await view.addLayer(trees);

  // Fiche d'une cellule
  function openSheet(id: number): boolean {
    const c: Cell | undefined = sheets.get(id);
    const el = $("fiche");
    if (!c) { el.hidden = true; return false; }
    const f = formatSheet(c, year);
    el.hidden = false;
    el.setAttribute("data-cell-id", String(c.cell_id));
    el.innerHTML = `<button class="fermer" type="button">×</button><h2>${f.title} <small>(${f.year})</small></h2>` +
      (f.provisional ? `<div class="prov">Résultat provisoire</div>` : "") +
      `<dl>${f.rows.map((l) => `<dt>${l.label}</dt><dd>${l.value}</dd>`).join("")}</dl>` +
      `<div>Composition (essences) : ${f.composition.join(" ; ") || "aucune"}</div>` +
      `<ul>${f.notes.map((x) => `<li>${x}</li>`).join("")}</ul>` +
      `<div>Commande à copier pour la vue massif :</div><code>${f.command}</code>` +
      `<button class="copier" type="button">Copier la commande</button>`;
    el.querySelector(".fermer")?.addEventListener("click", () => { el.hidden = true; });
    el.querySelector(".copier")?.addEventListener("click", () => { void navigator.clipboard?.writeText(f.command); });
    return true;
  }
  state.openCell = openSheet;
  $("vue").addEventListener("click", (ev) => {
    const mouse = view.eventToViewCoords(ev as MouseEvent);
    const c = view.pickTerrainCoordinates(mouse);
    if (!c) return;
    const p = c.as("EPSG:2154") as itowns.Coordinates;
    const id = cellIdFromLambert(p.x, p.y, cog.grid);
    if (id !== null) openSheet(id);
  });

  // Placement de la caméra (contrôle des tests : vue oblique rasante, etc.).
  state.placer = async (range, tilt, heading) => {
    await (view as unknown as { controls: { lookAtCoordinate: (o: unknown, anim: boolean) => Promise<void> } })
      .controls.lookAtCoordinate({ coord: center, range, tilt, heading }, false);
    view.notifyChange(view.camera3D);
  };

  // Mesure continue des images par seconde : force un rendu par image pendant la durée demandée.
  let images = 0;
  view.addFrameRequester(itowns.MAIN_LOOP_EVENTS.AFTER_RENDER, () => { images++; });
  state.mesurerFps = (ms = 3000) => new Promise((ok) => {
    const t0 = performance.now(), i0 = images;
    const frame = () => {
      view.notifyChange(view.camera3D);
      if (performance.now() - t0 < ms) requestAnimationFrame(frame);
      else { state.fps = Math.round(((images - i0) * 10000) / (performance.now() - t0)) / 10; ok(state.fps); }
    };
    frame();
  });

  // Instances : relevé par l'API three sur les objets de la couche (champ vivant).
  const root = (trees as unknown as { tilesRenderer: { group: THREE.Object3D } }).tilesRenderer.group;
  const update = () => {
    const c = countInstances(root);
    state.instanceCount = c.drawn;
    state.instancesChargees = c.loaded;
    state.meshesInstancies = c.meshes;
    $("etat-arbres").textContent = `Arbres dessinés : ${c.drawn.toLocaleString("fr-FR")}`;
  };
  const tr = (trees as unknown as { tilesRenderer: { stats: Record<string, number> } }).tilesRenderer;
  let stable = 0;
  const watcher = setInterval(() => {
    update();
    const s = tr.stats;
    const busy = (s["downloading"] ?? 0) + (s["parsing"] ?? 0) + (s["queued"] ?? 0);
    const expected = state.instancesAttendues;
    // Les couches du sol (carte, terrain, fond) doivent aussi avoir fini : plus aucune commande iTowns en attente.
    const sched = (view as unknown as { mainLoop: { scheduler: { commandsWaitingExecutionCount: () => number; commandsRunningCount: () => number } } }).mainLoop.scheduler;
    const groundLoaded = sched.commandsWaitingExecutionCount() + sched.commandsRunningCount() === 0;
    if (!busy && groundLoaded && state.instancesChargees > 0 && (expected === null || state.instancesChargees === expected)) stable++;
    else stable = 0;
    if (stable >= 3 && !state.ready) {
      state.chargementMs = Math.round(performance.now() - startedAt);
      state.ready = true;
      $("message").hidden = true;
    }
    if (performance.now() - startedAt > 150000 && !state.ready) {
      state.error = `Arbres : ${state.instancesChargees} instances chargées sur ${expected ?? "?"} attendues après 150 s ; voir la console du navigateur.`;
      say(state.error, true);
      clearInterval(watcher);
    }
  }, 300);
  say("Chargement des arbres…");
}

startViewer().catch((err: Error) => {
  state.error = `La vue n'a pas pu démarrer : ${err.message}`;
  say(state.error, true);
});
