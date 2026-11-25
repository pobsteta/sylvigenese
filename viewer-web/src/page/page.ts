// Page de la vue web (mission 029) : GlobeView iTowns centrée sur la zone, tuile 3D des arbres,
// carte des types de végétation (COG), terrain local (dtm.tif), fiche de cellule au clic.
// Code navigateur : bundlé par esbuild. La logique pure est dans ../fiche.ts (testée par node --test).
import * as THREE from "three";
import * as itowns from "itowns";
import { fromUrl } from "geotiff";
import proj4 from "proj4";
import {
  cellIdDepuisLambert, formaterFiche, indexerFiches,
  type Cellule, type FichesTuile, type Grille,
} from "../fiche.ts";

interface Etat {
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

const etat: Etat = {
  ready: false, error: null, year: null, instanceCount: 0, instancesChargees: 0, instancesAttendues: null,
  meshesInstancies: 0, fps: 0, chargementMs: null, terrain: "", fond: "", openCell: () => false,
  mesurerFps: async () => 0,
  placer: async () => {},
};
(window as unknown as { sylvigenese: Etat }).sylvigenese = etat;

const $ = (id: string) => document.getElementById(id) as HTMLElement;
const L93 = "+proj=lcc +lat_1=49 +lat_2=44 +lat_0=46.5 +lon_0=3 +x_0=700000 +y_0=6600000 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs";
itowns.CRS.defs("EPSG:2154", L93);
const vers93 = proj4("EPSG:4326", L93);

function dire(texte: string, erreur = false): void {
  const m = $("message");
  m.hidden = false;
  m.className = erreur ? "erreur" : "";
  m.textContent = texte;
}

async function json<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} : HTTP ${r.status}`);
  return (await r.json()) as T;
}

// ---------------------------------------------------------------- rasters locaux (COG, MNT)
interface Raster {
  grille: Grille;
  valeurs: ArrayLike<number>;
  nodata: number | null;
}

async function lireRaster(url: string): Promise<Raster> {
  const tiff = await fromUrl(url);
  const image = await tiff.getImage();
  const [x0, y0] = image.getOrigin() as [number, number];
  const [rx] = image.getResolution() as [number, number];
  const valeurs = (await image.readRasters({ interleave: true })) as unknown as ArrayLike<number>;
  const nodata = image.getGDALNoData();
  return { grille: { x0, y0, resolution: Math.abs(rx), colonnes: image.getWidth(), lignes: image.getHeight() }, valeurs, nodata };
}

// Palette : une teinte par valeur (au plus 16 types ici) ; la légende est tirée des mêmes valeurs.
function couleurDe(valeur: number, total: number): string {
  return `hsl(${Math.round((360 * valeur) / Math.max(total, 1)) % 360} 65% 50%)`;
}

// Sources de tuiles locales : l'adresse porte l'emprise (w,s,e,n en degrés), le chargeur dessine la tuile.
function urlEmprise(tile: { toExtent: (crs: string) => itowns.Extent }): string {
  const e = tile.toExtent("EPSG:4326");
  return `local://tuile?w=${e.west}&s=${e.south}&e=${e.east}&n=${e.north}`;
}
function empriseDe(url: string) {
  const p = new URL(url.replace("local://", "http://x/")).searchParams;
  return { w: Number(p.get("w")), s: Number(p.get("s")), e: Number(p.get("e")), n: Number(p.get("n")) };
}
const DIM = 256;
const OPACITE_CARTE = 0.5;
// Limites des tuiles du MNT IGN (RGE ALTI) sur la France, reprises de l'exemple d'iTowns (layers/JSONLayers/IGN_MNT_HIGHRES.json).
const LIMITES_IGN_MNT = {
  "11": { minTileRow: 442, maxTileRow: 1267, minTileCol: 1344, maxTileCol: 2683 },
  "12": { minTileRow: 885, maxTileRow: 2343, minTileCol: 3978, maxTileCol: 5126 },
  "13": { minTileRow: 1770, maxTileRow: 4687, minTileCol: 7957, maxTileCol: 10253 },
  "14": { minTileRow: 3540, maxTileRow: 9375, minTileCol: 15914, maxTileCol: 20507 },
};

// Le service IGN est-il joignable (3 s) ? Sinon la vue s'affiche sans lui.
async function sonderIgn(): Promise<boolean> {
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

function sourceLocale(fetcher: (url: string) => Promise<THREE.Texture>, zoomMax: number): itowns.TMSSource {
  const src = new itowns.TMSSource({
    url: "local://${z}/${y}/${x}", crs: "EPSG:4326", format: "image/png", fetcher,
    zoom: { min: 0, max: zoomMax }, attribution: { name: "sylvigenese" },
  } as never);
  (src as unknown as { urlFromExtent: unknown }).urlFromExtent = urlEmprise;
  return src;
}

function texteurCarte(r: Raster, couleurs: Map<number, string>) {
  const g = r.grille;
  const tmp = document.createElement("canvas").getContext("2d", { willReadFrequently: true }) as CanvasRenderingContext2D;
  const rgb = new Map<number, [number, number, number]>();
  for (const [v, c] of couleurs) {
    tmp.fillStyle = c; tmp.fillRect(0, 0, 1, 1);
    const d = tmp.getImageData(0, 0, 1, 1).data;
    rgb.set(v, [d[0] as number, d[1] as number, d[2] as number]);
  }
  return async (url: string): Promise<THREE.Texture> => {
    const { w, s, e, n } = empriseDe(url);
    const toile = document.createElement("canvas");
    toile.width = toile.height = DIM;
    const ctx = toile.getContext("2d") as CanvasRenderingContext2D;
    const img = ctx.createImageData(DIM, DIM);
    const rgba = new Uint8ClampedArray(img.data.buffer);
    for (let j = 0; j < DIM; j++) {
      const lat = n - ((j + 0.5) / DIM) * (n - s);
      for (let i = 0; i < DIM; i++) {
        const lon = w + ((i + 0.5) / DIM) * (e - w);
        const [x, y] = vers93.forward([lon, lat]) as [number, number];
        const id = cellIdDepuisLambert(x, y, g);
        if (id === null) continue;
        const v = r.valeurs[id] as number;
        const c = v === r.nodata ? undefined : rgb.get(v);
        if (!c) continue;
        const k = 4 * (j * DIM + i);
        rgba[k] = c[0]; rgba[k + 1] = c[1]; rgba[k + 2] = c[2]; rgba[k + 3] = 200;
      }
    }
    ctx.putImageData(img, 0, 0);
    return new THREE.CanvasTexture(toile);
  };
}

const NODATA_MNT = -9999;

// Nombre de cellules du MNT sans valeur (nodata), pour le dire à l'écran.
function altitudeMin(r: Raster): number {
  let m = Infinity;
  for (let i = 0; i < r.valeurs.length; i++) {
    const v = r.valeurs[i] as number;
    if (v !== r.nodata && v < m) m = v;
  }
  return m;
}

function compterNodata(r: Raster): number {
  let n = 0;
  for (let i = 0; i < r.valeurs.length; i++) if (r.valeurs[i] === r.nodata) n++;
  return n;
}

// Tuile d'altitudes à partir du MNT local. Hors de l'emprise du MNT, et sur ses cellules sans valeur, la tuile porte
// NODATA_MNT : iTowns reprend alors la valeur de la tuile parente (terrain IGN si joint, sinon ellipsoïde).
// Aucune altitude n'est inventée ni étendue au-delà du bord. Seule exception, demandée pour un jeu fictif : `plan` =
// altitude minimale du MNT, plan neutre hors emprise (dit à l'écran).
function texteurMnt(r: Raster, plan: number | null) {
  const g = r.grille;
  const est = g.x0 + g.colonnes * g.resolution, sud = g.y0 - g.lignes * g.resolution;
  const brut = (c: number, l: number): number | null => {
    if (c < 0 || l < 0 || c >= g.colonnes || l >= g.lignes) return null;
    const v = r.valeurs[l * g.colonnes + c] as number;
    return v === r.nodata ? null : v;
  };
  return async (url: string): Promise<THREE.Texture> => {
    const { w, s, e, n } = empriseDe(url);
    const data = new Float32Array(DIM * DIM).fill(NODATA_MNT);
    for (let j = 0; j < DIM; j++) {
      const lat = n - ((j + 0.5) / DIM) * (n - s);
      for (let i = 0; i < DIM; i++) {
        const lon = w + ((i + 0.5) / DIM) * (e - w);
        const [x, y] = vers93.forward([lon, lat]) as [number, number];
        if (x < g.x0 || x >= est || y <= sud || y > g.y0) { // hors emprise : nodata, ou plan neutre (jeu fictif)
          if (plan !== null) data[j * DIM + i] = plan;
          continue;
        }
        if (brut(Math.floor((x - g.x0) / g.resolution), Math.floor((g.y0 - y) / g.resolution)) === null) continue; // cellule sans valeur
        // bilinéaire entre centres de cellules, poids renormalisés sur les voisins valides
        const fc = (x - g.x0) / g.resolution - 0.5, fl = (g.y0 - y) / g.resolution - 0.5;
        const c0 = Math.floor(fc), l0 = Math.floor(fl), tx = fc - c0, ty = fl - l0;
        let somme = 0, poids = 0;
        for (const [dc, dl, p] of [[0, 0, (1 - tx) * (1 - ty)], [1, 0, tx * (1 - ty)], [0, 1, (1 - tx) * ty], [1, 1, tx * ty]] as const) {
          const v = brut(c0 + dc, l0 + dl);
          if (v !== null) { somme += v * p; poids += p; }
        }
        if (poids > 0) data[j * DIM + i] = somme / poids;
      }
    }
    const t = new THREE.DataTexture(data, DIM, DIM, THREE.RedFormat, THREE.FloatType);
    (t as unknown as { internalFormat: string }).internalFormat = "R32F";
    t.needsUpdate = true;
    return t;
  };
}

// ---------------------------------------------------------------- comptage des instances (API three)
function compter(racine: THREE.Object3D) {
  let meshes = 0, charges = 0, dessines = 0;
  const unites = new Set<THREE.Object3D>();
  racine.traverse((o) => {
    const m = o as THREE.InstancedMesh;
    if (!m.isInstancedMesh) return;
    // Un noeud glTF à plusieurs primitives (tronc, houppier) donne un groupe de InstancedMesh de même effectif :
    // c'est un seul jeu d'arbres, compté une fois.
    const p = m.parent;
    const groupe = p && (p as THREE.Group).isGroup && p.children.every((c) => (c as THREE.InstancedMesh).isInstancedMesh);
    const unite = groupe ? (p as THREE.Object3D) : m;
    meshes += m.count;
    if (unites.has(unite)) return;
    unites.add(unite);
    charges += m.count;
    let visible = true;
    for (let a: THREE.Object3D | null = m; a; a = a.parent) if (!a.visible) { visible = false; break; }
    if (visible) dessines += m.count;
  });
  return { meshes, charges, dessines };
}

// ---------------------------------------------------------------- démarrage
async function demarrer(): Promise<void> {
  const debut = performance.now();
  const cfg = await json<{ zone: string; annees: number[]; a_dtm: boolean; fictive: boolean }>("/api/config.json");
  const annee = cfg.annees[cfg.annees.length - 1] as number;
  etat.year = annee;
  $("annee-texte").textContent = `${annee} (une seule année disponible)`;
  $("etat-source").textContent = `Source : tiles/${annee}/ et web/ de la zone « ${cfg.zone} », lues le ${new Date().toLocaleDateString("fr-FR")}`;

  const urlTuiles = `/zone/tiles/${annee}/tileset.json`;
  const tileset = await json<{ root: { boundingVolume: { region: number[] }; children?: { extras?: { tile?: string } }[] }; extras?: { instances?: number } }>(urlTuiles);
  etat.instancesAttendues = tileset.extras?.instances ?? null;
  const noms = (tileset.root.children ?? []).map((c) => c.extras?.tile).filter((t): t is string => !!t);
  const fiches = indexerFiches(await Promise.all(noms.map((t) => json<FichesTuile>(`/zone/web/cells/${t}.json`))));

  const cog = await lireRaster("/zone/web/rasters/vegetation_map.tif");
  // Légende : la valeur du COG et le nom du type viennent des fiches (source unique : web/).
  const noms93 = new Map<number, string>();
  for (let id = 0; id < cog.valeurs.length; id++) {
    const v = cog.valeurs[id] as number;
    const f = fiches.get(id);
    if (v !== cog.nodata && f && !noms93.has(v)) noms93.set(v, f.vegetation_type);
  }
  const valeurs = [...noms93.keys()].sort((a, b) => a - b);
  const couleurs = new Map(valeurs.map((v) => [v, couleurDe(v, Math.max(...valeurs) + 1)]));
  $("legende-corps").innerHTML = valeurs
    .map((v) => `<div><i style="background:${couleurs.get(v)}"></i>${(noms93.get(v) ?? "").replace(/^type_|_fictive/g, "").replace(/_/g, " ")}</div>`)
    .join("");

  const [w, s, e, n] = tileset.root.boundingVolume.region as [number, number, number, number];
  const rad = 180 / Math.PI;
  const centre = new itowns.Coordinates("EPSG:4326", ((w + e) / 2) * rad, ((s + n) / 2) * rad, 0);
  const vue = new itowns.GlobeView($("vue") as HTMLDivElement,
    { coord: centre, range: 2600, tilt: 45, heading: 0 } as never,
    { controls: { minDistance: 50 } } as never);

  // Les matériaux glTF sont physiques : sans lumière les arbres sont noirs. Soleil bas du sud-ouest, repéré dans le
  // repère local de la zone (haut, est, nord), pour que les houppiers aient un côté éclairé et un côté sombre.
  const lon = centre.longitude * Math.PI / 180, lat = centre.latitude * Math.PI / 180;
  const haut = new THREE.Vector3(Math.cos(lat) * Math.cos(lon), Math.cos(lat) * Math.sin(lon), Math.sin(lat));
  const estV = new THREE.Vector3(-Math.sin(lon), Math.cos(lon), 0);
  const nordV = new THREE.Vector3().crossVectors(haut, estV);
  const hauteurSoleil = (35 * Math.PI) / 180;
  const soleilDir = new THREE.Vector3()
    .addScaledVector(haut, Math.sin(hauteurSoleil))
    .addScaledVector(estV, -Math.cos(hauteurSoleil) * 0.6)
    .addScaledVector(nordV, -Math.cos(hauteurSoleil) * 0.8);
  vue.scene.add(new THREE.AmbientLight(0xffffff, 1.0));
  const soleil = new THREE.DirectionalLight(0xfff2dd, 2.8);
  soleil.position.copy(soleilDir.normalize().multiplyScalar(1e7));
  vue.scene.add(soleil);

  // Terrain : MNT local sur son emprise ; hors emprise, terrain IGN si joignable, sinon ellipsoïde. Dit dans la page.
  // Zone fictive (zone.yml) : aucune donnée réelle mêlée aux données fictives, donc ni terrain ni orthophoto IGN.
  const ign = cfg.fictive ? false : await sonderIgn();
  let terrainIgn = false;
  if (ign) {
    try {
      const src = new itowns.WMTSSource({
        url: "https://data.geopf.fr/wmts?", crs: "EPSG:4326", format: "image/x-bil;bits=32",
        name: "ELEVATION.ELEVATIONGRIDCOVERAGE.HIGHRES", tileMatrixSet: "WGS84G", attribution: { name: "IGN" },
        tileMatrixSetLimits: LIMITES_IGN_MNT,
      } as never);
      await vue.addLayer(new itowns.ElevationLayer("mnt-ign", { source: src, noDataValue: -99999, clampValues: { min: 0 } } as never));
      terrainIgn = true;
    } catch { /* repli : ellipsoïde */ }
  }
  const horsEmprise = cfg.fictive ? "hors zone : plan neutre pour l'affichage, jeu fictif"
    : terrainIgn ? "hors emprise : terrain IGN (RGE ALTI)" : "hors emprise : ellipsoïde, altitude 0";
  if (cfg.a_dtm) {
    try {
      const mnt = await lireRaster("/zone/dtm.tif");
      const sansValeur = compterNodata(mnt);
      const couche = new itowns.ElevationLayer("mnt-local", {
        source: sourceLocale(texteurMnt(mnt, cfg.fictive ? altitudeMin(mnt) : null), 17), scale: 1, noDataValue: NODATA_MNT,
      } as never);
      await vue.addLayer(couche);
      etat.terrain = `Terrain : MNT local (dtm.tif, 25 m) sur son emprise, altitudes NGF sans conversion RAF20 ; ${horsEmprise}${cfg.fictive ? ` (altitude ${Math.round(altitudeMin(mnt) * 10) / 10} m)` : ""}.` +
        (sansValeur > 0 ? ` ${sansValeur} cellule(s) du MNT sans valeur : terrain du niveau parent.` : "");
    } catch (err) {
      etat.terrain = `Terrain : ${terrainIgn ? "IGN" : "ellipsoïde"} (MNT local illisible : ${(err as Error).message}).`;
    }
  } else {
    etat.terrain = `Terrain : ${terrainIgn ? "terrain IGN (RGE ALTI)" : "ellipsoïde"} (pas de dtm.tif dans la zone) ; les arbres peuvent flotter ou s'enfoncer.`;
  }
  $("etat-terrain").textContent = etat.terrain;

  // Fond IGN : facultatif, seulement s'il est joignable.
  etat.fond = cfg.fictive ? "Fond : aucun (jeu fictif : pas de données réelles mêlées)." : "Fond : IGN injoignable, la vue s'affiche sans fond.";
  if (ign) {
    try {
      const src = new itowns.WMTSSource({
        url: "https://data.geopf.fr/wmts", name: "ORTHOIMAGERY.ORTHOPHOTOS", tileMatrixSet: "PM",
        format: "image/jpeg", crs: "EPSG:3857", attribution: { name: "IGN" },
      } as never);
      await vue.addLayer(new itowns.ColorLayer("fond-ign", { source: src } as never));
      etat.fond = "Fond : orthophoto IGN (data.geopf.fr).";
    } catch { /* message de repli ci-dessus */ }
  }
  $("etat-fond").textContent = etat.fond;

  // La carte des types est une couche du sol (sous les arbres), d'opacité réglable ; défaut modéré.
  const carte = new itowns.ColorLayer("types-vegetation", {
    source: sourceLocale(texteurCarte(cog, couleurs), 19), transparent: true, opacity: OPACITE_CARTE,
  } as never);
  await vue.addLayer(carte);
  const curseur = $("opacite") as HTMLInputElement;
  curseur.value = String(OPACITE_CARTE);
  curseur.addEventListener("input", () => {
    carte.opacity = Number(curseur.value);
    vue.notifyChange(carte);
  });

  const arbres = new itowns.OGC3DTilesLayer("arbres", {
    source: new itowns.OGC3DTilesSource({ url: urlTuiles }), sseThreshold: 2,
  } as never);
  await vue.addLayer(arbres);

  // Fiche d'une cellule
  function ouvrirFiche(id: number): boolean {
    const c: Cellule | undefined = fiches.get(id);
    const el = $("fiche");
    if (!c) { el.hidden = true; return false; }
    const f = formaterFiche(c, annee);
    el.hidden = false;
    el.setAttribute("data-cell-id", String(c.cell_id));
    el.innerHTML = `<button class="fermer" type="button">×</button><h2>${f.titre} <small>(${f.annee})</small></h2>` +
      (f.provisoire ? `<div class="prov">Résultat provisoire</div>` : "") +
      `<dl>${f.lignes.map((l) => `<dt>${l.libelle}</dt><dd>${l.valeur}</dd>`).join("")}</dl>` +
      `<div>Composition (essences) : ${f.composition.join(" ; ") || "aucune"}</div>` +
      `<ul>${f.notes.map((x) => `<li>${x}</li>`).join("")}</ul>` +
      `<div>Commande à copier pour la vue massif :</div><code>${f.commande}</code>` +
      `<button class="copier" type="button">Copier la commande</button>`;
    el.querySelector(".fermer")?.addEventListener("click", () => { el.hidden = true; });
    el.querySelector(".copier")?.addEventListener("click", () => { void navigator.clipboard?.writeText(f.commande); });
    return true;
  }
  etat.openCell = ouvrirFiche;
  $("vue").addEventListener("click", (ev) => {
    const mouse = vue.eventToViewCoords(ev as MouseEvent);
    const c = vue.pickTerrainCoordinates(mouse);
    if (!c) return;
    const p = c.as("EPSG:2154") as itowns.Coordinates;
    const id = cellIdDepuisLambert(p.x, p.y, cog.grille);
    if (id !== null) ouvrirFiche(id);
  });

  // Placement de la caméra (contrôle des tests : vue oblique rasante, etc.).
  etat.placer = async (range, tilt, heading) => {
    await (vue as unknown as { controls: { lookAtCoordinate: (o: unknown, anim: boolean) => Promise<void> } })
      .controls.lookAtCoordinate({ coord: centre, range, tilt, heading }, false);
    vue.notifyChange(vue.camera3D);
  };

  // Mesure continue des images par seconde : force un rendu par image pendant la durée demandée.
  let images = 0;
  vue.addFrameRequester(itowns.MAIN_LOOP_EVENTS.AFTER_RENDER, () => { images++; });
  etat.mesurerFps = (ms = 3000) => new Promise((ok) => {
    const t0 = performance.now(), i0 = images;
    const tour = () => {
      vue.notifyChange(vue.camera3D);
      if (performance.now() - t0 < ms) requestAnimationFrame(tour);
      else { etat.fps = Math.round(((images - i0) * 10000) / (performance.now() - t0)) / 10; ok(etat.fps); }
    };
    tour();
  });

  // Instances : relevé par l'API three sur les objets de la couche (champ vivant).
  const racine = (arbres as unknown as { tilesRenderer: { group: THREE.Object3D } }).tilesRenderer.group;
  const maj = () => {
    const c = compter(racine);
    etat.instanceCount = c.dessines;
    etat.instancesChargees = c.charges;
    etat.meshesInstancies = c.meshes;
    $("etat-arbres").textContent = `Arbres dessinés : ${c.dessines.toLocaleString("fr-FR")}`;
  };
  const tr = (arbres as unknown as { tilesRenderer: { stats: Record<string, number> } }).tilesRenderer;
  let stable = 0;
  const veille = setInterval(() => {
    maj();
    const s = tr.stats;
    const occupe = (s["downloading"] ?? 0) + (s["parsing"] ?? 0) + (s["queued"] ?? 0);
    const attendu = etat.instancesAttendues;
    // Les couches du sol (carte, terrain, fond) doivent aussi avoir fini : plus aucune commande iTowns en attente.
    const planif = (vue as unknown as { mainLoop: { scheduler: { commandsWaitingExecutionCount: () => number; commandsRunningCount: () => number } } }).mainLoop.scheduler;
    const solCharge = planif.commandsWaitingExecutionCount() + planif.commandsRunningCount() === 0;
    if (!occupe && solCharge && etat.instancesChargees > 0 && (attendu === null || etat.instancesChargees === attendu)) stable++;
    else stable = 0;
    if (stable >= 3 && !etat.ready) {
      etat.chargementMs = Math.round(performance.now() - debut);
      etat.ready = true;
      $("message").hidden = true;
    }
    if (performance.now() - debut > 150000 && !etat.ready) {
      etat.error = `Arbres : ${etat.instancesChargees} instances chargées sur ${attendu ?? "?"} attendues après 150 s ; voir la console du navigateur.`;
      dire(etat.error, true);
      clearInterval(veille);
    }
  }, 300);
  dire("Chargement des arbres…");
}

demarrer().catch((err: Error) => {
  etat.error = `La vue n'a pas pu démarrer : ${err.message}`;
  dire(etat.error, true);
});
