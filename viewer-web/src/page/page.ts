// Page de la vue web (missions 029 et 048) : GlobeView iTowns centrée sur la zone, tuile 3D des arbres de l'année
// choisie, carte au sol (surface terrière de l'année, à échelle fixe, ou types de végétation de l'état initial),
// terrain local (dtm.tif), fiche de cellule au clic avec l'évolution de la cellule.
// Code navigateur : bundlé par esbuild. La logique pure est dans ../sheet.ts et ../temps.ts (testées par node --test).
// Les années viennent de tiles/index.json (contrat tiles_index) ; un seul tileset est gardé en mémoire, l'ancien
// reste affiché jusqu'à ce que le nouveau soit chargé (plan m4a-suite-temps T7).
import * as THREE from "three";
import * as itowns from "itowns";
import { fromUrl } from "geotiff";
import proj4 from "proj4";
import {
  cellIdFromLambert, formatSheet, indexSheets,
  type Cell, type TileSheets, type Grid,
} from "../sheet.ts";
import {
  chooseYear, formatEvolution, indexTiles, indexYear, legendTicks, neighbourYear, positionOfYear, rampColor, rampCss,
  readTilesIndex, yearAtPosition, yearLabel, MENTION_ECO, TreeLayerSlots,
  type CellV2, type TileSheetsV2, type TilesIndex,
} from "../temps.ts";

interface YearRecord {
  instanceCount: number;
  chargementMs: number | null;
  fps: number | null;
}

interface State {
  ready: boolean;
  error: string | null;
  year: number | null;
  years: number[];
  instanceCount: number;
  instancesChargees: number;
  instancesAttendues: number | null;
  meshesInstancies: number;
  tilesetsEnMemoire: number;
  fps: number;
  chargementMs: number | null;
  parAnnee: Record<string, YearRecord>;
  terrain: string;
  fond: string;
  setYear: (a: number) => Promise<void>;
  openCell: (id: number) => boolean;
  mesurerFps: (ms?: number) => Promise<number>;
  placer: (range: number, tilt: number, heading: number) => Promise<void>;
}

const state: State = {
  ready: false, error: null, year: null, years: [], instanceCount: 0, instancesChargees: 0, instancesAttendues: null,
  meshesInstancies: 0, tilesetsEnMemoire: 0, fps: 0, chargementMs: null, parAnnee: {}, terrain: "", fond: "",
  setYear: async () => {}, openCell: () => false,
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

// ---------------------------------------------------------------- carte de surface terrière (Q3)
// Une couleur par cellule, lue dans g_<année>.tif, sur l'échelle FIXE de tiles/index.json (mêmes couleurs pour toutes
// les années). Hors forêt (nodata) : rien n'est dessiné.
function basalAreaTextureLoader(r: Raster, min: number, max: number) {
  const g = r.grid;
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
        if (v === r.nodata || Number.isNaN(v)) continue;
        const c = rampColor(v, min, max).rgb;
        const k = 4 * (j * DIM + i);
        rgba[k] = c[0]; rgba[k + 1] = c[1]; rgba[k + 2] = c[2]; rgba[k + 3] = 220;
      }
    }
    ctx.putImageData(img, 0, 0);
    return new THREE.CanvasTexture(canvas);
  };
}

// Cellules hors de l'échelle fixe : ne devrait pas arriver (échelle calculée sur toutes les années) ; dit si c'est le cas.
function countOutside(r: Raster, min: number, max: number): number {
  let k = 0;
  for (let i = 0; i < r.values.length; i++) {
    const v = r.values[i] as number;
    if (v !== r.nodata && !Number.isNaN(v) && rampColor(v, min, max).outside) k++;
  }
  return k;
}

function esc(t: string): string {
  return t.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c] as string);
}

const LOAD_TIMEOUT_MS = 280000;

// ---------------------------------------------------------------- démarrage
interface ServerConfig { zone: string; years: number[]; has_dtm: boolean; has_index?: boolean; fictitious: boolean }
interface Tileset { root: { boundingVolume: { region: number[] }; children?: { extras?: { tile?: string } }[] }; extras?: { instances?: number } }

async function readIndexIfAny(cfg: ServerConfig): Promise<TilesIndex | null> {
  if (cfg.has_index === false) return null;
  const r = await fetch("/zone/tiles/index.json");
  if (r.status === 404) return null; // zone d'avant la mission 047 : une seule année, lue dans tiles/<année>/
  if (!r.ok) throw new Error(`/zone/tiles/index.json : HTTP ${r.status}`);
  return readTilesIndex(await r.json());
}

async function startViewer(): Promise<void> {
  const startedAt = performance.now();
  const cfg = await json<ServerConfig>("/api/config.json");
  const index = await readIndexIfAny(cfg);
  const sim = index?.source === "sim";
  const years = index ? index.years.map((y) => y.year) : [cfg.years[cfg.years.length - 1] as number];
  const t0 = index?.t0 ?? (years[0] as number);
  state.years = years;
  const tilesetUrlOf = (a: number) => (index ? `/zone/tiles/${indexYear(index, a).tileset}` : `/zone/tiles/${a}/tileset.json`);
  const firstYear = years[0] as number;

  document.title = sim ? "sylvigenese — futur simulé (provisoire)" : "sylvigenese — état initial";
  if (sim) {
    $("bandeau-texte").innerHTML = `<small>trajectoire technique, <b>non validée écologiquement</b> (décision du 25/11/2026) ; modèles d'arbres génériques</small>`;
  }
  $("etat-source").textContent = `Source : tiles/${index ? "index.json" : `${firstYear}/`} et web/ de la zone « ${cfg.zone} », lues le ${new Date().toLocaleDateString("fr-FR")}`;

  const firstTileset = await json<Tileset>(tilesetUrlOf(firstYear));
  const tileNames = index ? indexTiles(index)
    : (firstTileset.root.children ?? []).map((c) => c.extras?.tile).filter((t): t is string => !!t);
  // Fiches : v2 dès que sim/ existe (la version 1 est alors refusée), v1 pour l'état initial.
  const files = await Promise.all(tileNames.map((t) => json<TileSheets | TileSheetsV2>(`/zone/web/cells/${t}.json`)));
  const sheetsV1 = sim ? new Map<number, Cell>() : indexSheets(files as TileSheets[], 1);
  const sheetsV2 = sim ? indexSheets(files as TileSheetsV2[], 2) : new Map<number, CellV2>();
  const sheetNotesOfFiles = sim ? (files as TileSheetsV2[]).flatMap((f) => f.notes ?? []) : [];
  const vegetationOf = (id: number) => (sim ? sheetsV2.get(id)?.vegetation_type : sheetsV1.get(id)?.vegetation_type);

  const cog = await readRaster("/zone/web/rasters/vegetation_map.tif");
  // Légende des types : la valeur du COG et le nom du type viennent des fiches (source unique : web/).
  const vegetationNames = new Map<number, string>();
  for (let id = 0; id < cog.values.length; id++) {
    const v = cog.values[id] as number;
    const name = vegetationOf(id);
    if (v !== cog.nodata && name && !vegetationNames.has(v)) vegetationNames.set(v, name);
  }
  const values = [...vegetationNames.keys()].sort((a, b) => a - b);
  const colors = new Map(values.map((v) => [v, colorOf(v, Math.max(...values) + 1)]));
  $("legende-corps").innerHTML = values
    .map((v) => `<div><i style="background:${colors.get(v)}"></i>${esc((vegetationNames.get(v) ?? "").replace(/^type_|_fictive/g, "").replace(/_/g, " "))}</div>`)
    .join("");
  if (sim) $("legende-titre").textContent = "Types de végétation (état initial)";

  const [w, s, e, n] = firstTileset.root.boundingVolume.region as [number, number, number, number];
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

  // ------------------------------------------------------------ cartes au sol
  // La carte des types est une couche du sol (sous les arbres), d'opacité réglable ; défaut modéré. En mode sim,
  // la carte montrée d'abord est celle de la surface terrière de l'année ; les types restent à un clic (état initial).
  const vegetationMap = new itowns.ColorLayer("types-vegetation", {
    source: localSource(mapTextureLoader(cog, colors), 19), transparent: true, opacity: MAP_OPACITY,
  } as never);
  await view.addLayer(vegetationMap);
  const slider = $("opacite") as HTMLInputElement;
  slider.value = String(MAP_OPACITY);
  const groundChoice = $("carte-sol") as HTMLSelectElement;
  let basalLayer: itowns.ColorLayer | null = null;
  const basalScale = index?.basal_area_map;
  const applyGround = () => {
    const showG = sim && groundChoice.value === "g";
    vegetationMap.visible = !showG;
    vegetationMap.opacity = Number(slider.value);
    if (basalLayer) { basalLayer.visible = showG; basalLayer.opacity = Number(slider.value); }
    $("legende-types").hidden = showG;
    $("legende-g").hidden = !showG;
    view.notifyChange(vegetationMap);
  };
  slider.addEventListener("input", applyGround);
  if (sim && basalScale) {
    $("choix-carte").hidden = false;
    groundChoice.value = "g";
    groundChoice.addEventListener("change", applyGround);
    const [lo, mid, hi] = legendTicks(basalScale.scale_min_m2_ha, basalScale.scale_max_m2_ha);
    $("legende-g-barre").style.background = rampCss();
    $("legende-g-reperes").innerHTML = `<span>${lo}</span><span>${mid}</span><span>${hi}</span>`;
    $("legende-g-mention").textContent = `Échelle fixe : ${lo} à ${hi} m²/ha. Source : ${basalScale.mention}`;
  }
  const basalRasters = new Map<number, Raster>();
  async function swapBasalArea(a: number, token: number): Promise<void> {
    if (!sim || !basalScale) return;
    let r = basalRasters.get(a);
    if (!r) { r = await readRaster(`/zone/web/rasters/g_${a}.tif`); basalRasters.set(a, r); }
    if (token !== loadToken) return;
    const outside = countOutside(r, basalScale.scale_min_m2_ha, basalScale.scale_max_m2_ha);
    const layer = new itowns.ColorLayer(`surface-terriere-${a}-${token}`, {
      source: localSource(basalAreaTextureLoader(r, basalScale.scale_min_m2_ha, basalScale.scale_max_m2_ha), 19),
      transparent: true, opacity: Number(slider.value),
    } as never);
    await view.addLayer(layer);
    const old = basalLayer;
    basalLayer = layer;
    if (old) view.removeLayer(old.id, true);
    $("legende-g-titre").textContent = `Surface terrière G en ${a} (m²/ha), provisoire`;
    $("legende-g-hors").textContent = outside > 0 ? `${outside} cellule(s) hors de l'échelle fixe, dessinées à la borne.` : "";
    applyGround();
  }

  // ------------------------------------------------------------ fiche d'une cellule
  let openedCell: number | null = null;
  function openSheet(id: number): boolean {
    const el = $("fiche");
    const year = state.year as number;
    let html: string;
    let command: string;
    if (sim) {
      const c = sheetsV2.get(id);
      if (!c) { el.hidden = true; openedCell = null; return false; }
      const f = formatEvolution(c, year, sheetNotesOfFiles);
      command = f.command;
      html = `<h2>${f.title} <small>(${f.year})</small></h2>` +
        `<div class="prov">Résultat provisoire : ${esc(MENTION_ECO)}</div>` +
        `<div class="tete">${esc(f.headline)}</div>` +
        `<dl>${f.rows.map((l) => `<dt>${esc(l.label)}</dt><dd>${esc(l.value)}</dd>`).join("")}</dl>` +
        `<table class="evolution"><caption>Évolution de la cellule, chiffres provisoires (H_dom ↑ : au-dessus du plafond, signalé, jamais corrigé)</caption>` +
        `<thead><tr><th>Année</th><th>Tiges/ha</th><th>G m²/ha</th><th>d moyen cm</th><th>H_dom m (${esc(f.ceiling)})</th><th>Essences (part des tiges)</th><th>Signalements</th></tr></thead><tbody>` +
        f.table.map((r) => `<tr${r.selected ? ' class="choisie"' : ""}><td>${r.year}</td><td>${r.stems}</td><td>${r.basalArea}</td><td>${r.d130}</td>` +
          `<td${r.aboveCeiling ? ' class="haut"' : ""}>${r.hdom}${r.aboveCeiling ? " ↑" : ""}</td><td>${esc(r.composition)}</td><td>${esc(r.flags.join(" ; "))}</td></tr>`).join("") +
        `</tbody></table>` +
        `<ul>${f.notes.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`;
    } else {
      const c = sheetsV1.get(id);
      if (!c) { el.hidden = true; openedCell = null; return false; }
      const f = formatSheet(c, year);
      command = f.command;
      html = `<h2>${f.title} <small>(${f.year})</small></h2>` +
        (f.provisional ? `<div class="prov">Résultat provisoire</div>` : "") +
        `<dl>${f.rows.map((l) => `<dt>${esc(l.label)}</dt><dd>${esc(l.value)}</dd>`).join("")}</dl>` +
        `<div>Composition (essences) : ${f.composition.join(" ; ") || "aucune"}</div>` +
        `<ul>${f.notes.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`;
    }
    openedCell = id;
    el.hidden = false;
    el.classList.toggle("large", sim);
    el.setAttribute("data-cell-id", String(id));
    el.innerHTML = `<button class="fermer" type="button">×</button>` + html +
      `<div>Commande à copier pour la vue massif :</div><code>${command}</code>` +
      `<button class="copier" type="button">Copier la commande</button>`;
    el.querySelector(".fermer")?.addEventListener("click", () => { el.hidden = true; openedCell = null; });
    el.querySelector(".copier")?.addEventListener("click", () => { void navigator.clipboard?.writeText(command); });
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

  // Mesure des images par seconde : force un rendu par image pendant la durée demandée ; rangée sous l'année affichée.
  let images = 0;
  view.addFrameRequester(itowns.MAIN_LOOP_EVENTS.AFTER_RENDER, () => { images++; });
  state.mesurerFps = (ms = 3000) => new Promise((ok) => {
    const t0m = performance.now(), i0 = images;
    const frame = () => {
      view.notifyChange(view.camera3D);
      if (performance.now() - t0m < ms) requestAnimationFrame(frame);
      else {
        state.fps = Math.round(((images - i0) * 10000) / (performance.now() - t0m)) / 10;
        const rec = state.year === null ? undefined : state.parAnnee[String(state.year)];
        if (rec) rec.fps = state.fps;
        ok(state.fps);
      }
    };
    frame();
  });

  // ------------------------------------------------------------ arbres : une couche par année, une seule gardée
  type TreesLayer = itowns.OGC3DTilesLayer & { tilesRenderer: { group: THREE.Object3D; stats: Record<string, number> } };
  const slots = new TreeLayerSlots<TreesLayer>(); // jamais plus de deux couches : l'affichée et celle en chargement
  let adding: Promise<unknown> = Promise.resolve();
  let loadToken = 0;
  const sched = (view as unknown as { mainLoop: { scheduler: { commandsWaitingExecutionCount: () => number; commandsRunningCount: () => number } } }).mainLoop.scheduler;
  const groundLoaded = () => sched.commandsWaitingExecutionCount() + sched.commandsRunningCount() === 0;
  const expectedOf = async (a: number): Promise<number | null> => {
    if (index) return indexYear(index, a).instances;
    return (a === firstYear ? firstTileset : await json<Tileset>(tilesetUrlOf(a))).extras?.instances ?? null;
  };
  const refreshCount = () => {
    const c = slots.shown ? countInstances(slots.shown.tilesRenderer.group) : { drawn: 0, loaded: 0, meshes: 0 };
    state.instanceCount = c.drawn;
    state.meshesInstancies = c.meshes;
    $("etat-arbres").textContent = `Arbres dessinés : ${c.drawn.toLocaleString("fr-FR")}${state.ready ? "" : " (chargement…)"}`;
  };
  setInterval(refreshCount, 500);

  // Retire une couche d'arbres et libère sa mémoire : tuiles (3d-tiles-renderer), tampons d'instances (three),
  // et son groupe dans la scène (removeLayer d'iTowns ne l'en retire pas).
  function dropTrees(layer: TreesLayer): void {
    const meshes: THREE.InstancedMesh[] = [];
    layer.tilesRenderer.group.traverse((o: THREE.Object3D) => { if ((o as THREE.InstancedMesh).isInstancedMesh) meshes.push(o as THREE.InstancedMesh); });
    view.removeLayer(layer.id, true);
    for (const m of meshes) m.dispose();
    (layer as unknown as { object3d: THREE.Object3D }).object3d.removeFromParent();
  }

  function showYearInPage(a: number): void {
    const label = sim ? yearLabel(a, t0) : `${a} (état initial, une seule année disponible)`;
    $("annee-texte").textContent = label;
    $("annee-grand").textContent = String(a);
    const range = $("annee") as HTMLInputElement;
    range.value = String(positionOfYear(years, a));
  }

  // Charge l'année a ; l'ancienne couche reste dessinée jusqu'à ce que la nouvelle soit entièrement chargée, puis
  // elle est retirée et sa mémoire libérée. Un nouvel appel abandonne le chargement en cours (le dernier gagne).
  async function loadYear(a: number): Promise<void> {
    const token = ++loadToken;
    const started = performance.now();
    state.ready = false;
    state.error = null;
    state.year = a;
    showYearInPage(a);
    say(`Chargement de ${a}…`);
    if (openedCell !== null) openSheet(openedCell);
    const expected = await expectedOf(a);
    state.instancesAttendues = expected;
    await swapBasalArea(a, token);
    if (token !== loadToken) return;
    await adding.catch(() => undefined); // une couche encore en train de s'ajouter ne se retire pas en cours de route
    if (token !== loadToken) return;
    for (const abandoned of slots.beforeAdd()) dropTrees(abandoned); // retirée avant d'en ajouter une autre
    const layer = new itowns.OGC3DTilesLayer(`arbres-${a}-${token}`, {
      source: new itowns.OGC3DTilesSource({ url: tilesetUrlOf(a) }), sseThreshold: 2,
    } as never) as TreesLayer;
    const group = layer.tilesRenderer.group;
    if (slots.shown) group.visible = false; // chargée en retrait : l'ancienne année reste à l'écran
    slots.added(layer);
    adding = view.addLayer(layer);
    await adding;
    state.tilesetsEnMemoire = slots.count;
    let stable = 0;
    await new Promise<void>((done, fail) => {
      const timer = setInterval(() => {
        if (token !== loadToken) { clearInterval(timer); done(); return; }
        const c = countInstances(group);
        state.instancesChargees = c.loaded;
        const st = layer.tilesRenderer.stats;
        const busy = (st["downloading"] ?? 0) + (st["parsing"] ?? 0) + (st["queued"] ?? 0);
        if ((st["failed"] ?? 0) > 0) { clearInterval(timer); fail(new Error(`${st["failed"]} tuile(s) de ${a} illisible(s)`)); return; }
        const complete = expected === null ? c.loaded > 0 : c.loaded === expected;
        if (!busy && groundLoaded() && complete) stable++;
        else stable = 0;
        if (stable >= 3) { clearInterval(timer); done(); return; }
        if (performance.now() - started > LOAD_TIMEOUT_MS) {
          clearInterval(timer);
          fail(new Error(`Arbres de ${a} : ${c.loaded} instances chargées sur ${expected ?? "?"} attendues après ${LOAD_TIMEOUT_MS / 1000} s ; voir la console du navigateur.`));
        }
      }, 300);
    });
    if (token !== loadToken) { for (const l of slots.abandon(layer)) dropTrees(l); return; }
    group.visible = true;
    for (const old of slots.commit(layer)) dropTrees(old);
    state.tilesetsEnMemoire = slots.count;
    view.notifyChange(view.camera3D);
    refreshCount();
    state.chargementMs = Math.round(performance.now() - started);
    state.parAnnee[String(a)] = { instanceCount: state.instanceCount, chargementMs: state.chargementMs, fps: null };
    state.ready = true;
    $("message").hidden = true;
    refreshCount();
  }

  let pending: Promise<void> = Promise.resolve();
  state.setYear = (a: number) => {
    let year: number;
    try {
      year = chooseYear(years, a);
    } catch (err) {
      state.error = (err as Error).message;
      say(state.error, true);
      return Promise.resolve();
    }
    if (year === state.year && state.error === null) return pending; // déjà affichée, ou en cours de chargement
    pending = loadYear(year).catch((err: Error) => {
      state.error = err.message;
      say(state.error, true);
    });
    return pending;
  };

  // Curseur d'années : un cran par année de l'index ; boutons voisins pour avancer d'un cran.
  const range = $("annee") as HTMLInputElement;
  range.min = "0";
  range.max = String(years.length - 1);
  range.step = "1";
  range.disabled = years.length < 2;
  ($("annee-prec") as HTMLButtonElement).disabled = years.length < 2;
  ($("annee-suiv") as HTMLButtonElement).disabled = years.length < 2;
  $("annees-liste").innerHTML = years.map((y, i) => `<option value="${i}" label="${y}"></option>`).join("");
  range.addEventListener("input", () => {
    const a = yearAtPosition(years, Number(range.value));
    $("annee-texte").textContent = sim ? yearLabel(a, t0) : String(a);
  });
  range.addEventListener("change", () => { void state.setYear(yearAtPosition(years, Number(range.value))); });
  $("annee-prec").addEventListener("click", () => { if (state.year !== null) void state.setYear(neighbourYear(years, state.year, -1)); });
  $("annee-suiv").addEventListener("click", () => { if (state.year !== null) void state.setYear(neighbourYear(years, state.year, 1)); });

  await state.setYear(firstYear);
  state.chargementMs = Math.round(performance.now() - startedAt);
}

startViewer().catch((err: Error) => {
  state.error = `La vue n'a pas pu démarrer : ${err.message}`;
  say(state.error, true);
});
