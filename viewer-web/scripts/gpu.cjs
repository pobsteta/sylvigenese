// Relevé sur carte graphique (mission 088) : parties pures, sans navigateur, testées dans viewer-web/test/gpu.test.ts.
// Principe : « signaler plutôt que deviner ». Le moteur de rendu réellement utilisé est lu dans WebGL
// (WEBGL_debug_renderer_info) ; s'il est logiciel, illisible, ou différent de la carte demandée, on échoue en le
// nommant et aucun chiffre n'est écrit.
const fs = require("fs");
const path = require("path");

const LOGICIEL = /swiftshader|subzero|llvmpipe|softpipe|lavapipe|software|logiciel|basic render|microsoft basic/i;
const NVIDIA = /nvidia|quadro|geforce|\brtx\b|\bgtx\b|tesla/i;
const INTEGREE = /intel|\bamd\b|radeon|\bati\b/i;
const CARTES = ["nvidia", "integree", "auto"];
const DOSSIER_EGL = "/usr/share/glvnd/egl_vendor.d";
const VARIABLES_NVIDIA = ["__NV_PRIME_RENDER_OFFLOAD", "__GLX_VENDOR_LIBRARY_NAME", "__VK_LAYER_NV_optimus"];

class ErreurGpu extends Error {
  constructor(message) { super(message); this.name = "ErreurGpu"; }
}

function normaliserCarte(carte) {
  const c = String(carte === undefined || carte === null || carte === "" ? "auto" : carte).toLowerCase()
    .replace("intégrée", "integree");
  if (!CARTES.includes(c)) throw new ErreurGpu(`Carte demandée inconnue : « ${carte} » (valeurs : ${CARTES.join(", ")}).`);
  return c;
}

// Fichier EGL glvnd d'un fabricant (« nvidia » ou « mesa »), cherché dans le dossier des fournisseurs.
function fichierEgl(fabricant, dossier = DOSSIER_EGL) {
  let noms = [];
  try { noms = fs.readdirSync(dossier).filter((n) => n.endsWith(".json")).sort(); } catch (e) { /* signalé ci-dessous */ }
  const nom = noms.find((n) => n.toLowerCase().includes(fabricant));
  if (!nom) throw new ErreurGpu(`Aucun fichier EGL « ${fabricant} » dans ${dossier} : impossible de choisir la carte avec EGL.`);
  return path.join(dossier, nom);
}

// Environnement du navigateur pour la carte demandée (PRIME). Renvoie une copie de `base`.
function environnementCarte(carte, base = process.env, dossier = DOSSIER_EGL) {
  const c = normaliserCarte(carte);
  const env = { ...base };
  if (c === "auto") return env;
  if (c === "nvidia") {
    env.__NV_PRIME_RENDER_OFFLOAD = "1";
    env.__GLX_VENDOR_LIBRARY_NAME = "nvidia";
    env.__VK_LAYER_NV_optimus = "NVIDIA_only";
    env.__EGL_VENDOR_LIBRARY_FILENAMES = fichierEgl("nvidia", dossier);
  } else {
    for (const v of VARIABLES_NVIDIA) delete env[v];
    env.__VK_LAYER_NV_optimus = "non_NVIDIA_only";
    env.__EGL_VENDOR_LIBRARY_FILENAMES = fichierEgl("mesa", dossier);
  }
  return env;
}

// Options de Chromium : accélération matérielle par ANGLE sur EGL (c'est elle qui obéit au choix de fichier EGL ;
// sans elle, avec la Quadro, Chromium retombe en silence sur SwiftShader : voir le rendu de la mission 088).
// `sansBorne` coupe la synchronisation verticale et la limite d'images.
function optionsChromium({ sansBorne = false } = {}) {
  const o = ["--ignore-gpu-blocklist", "--enable-gpu-rasterization", "--use-gl=angle", "--use-angle=gl-egl"];
  if (sansBorne) o.push("--disable-gpu-vsync", "--disable-frame-rate-limit");
  return o;
}

// Contrôle du moteur lu. `lu` = { renderer, vendor } (null ou chaînes vides si illisible). Lève ErreurGpu.
function verifierMoteur(lu, carte) {
  const c = normaliserCarte(carte);
  const renderer = lu && typeof lu.renderer === "string" ? lu.renderer.trim() : "";
  const vendor = lu && typeof lu.vendor === "string" ? lu.vendor.trim() : "";
  if (!renderer) {
    throw new ErreurGpu("Moteur de rendu illisible (WEBGL_debug_renderer_info absent ou vide) : on ne sait pas sur quoi la " +
      "mesure aurait tourné ; aucun chiffre n'est écrit.");
  }
  if (LOGICIEL.test(renderer) || LOGICIEL.test(vendor)) {
    throw new ErreurGpu(`Rendu logiciel obtenu (« ${renderer} ») : ce n'est pas une carte graphique ; aucun chiffre n'est écrit.`);
  }
  const texte = `${renderer} ${vendor}`;
  if (c === "nvidia" && !NVIDIA.test(texte)) {
    throw new ErreurGpu(`Carte NVIDIA demandée, autre obtenue (« ${renderer} ») ; aucun chiffre n'est écrit.`);
  }
  if (c === "integree" && (NVIDIA.test(texte) || !INTEGREE.test(texte))) {
    throw new ErreurGpu(`Carte intégrée demandée, autre obtenue (« ${renderer} ») ; aucun chiffre n'est écrit.`);
  }
  return { renderer, vendor };
}

// Une mesure est peut-être bornée par la synchronisation verticale si elle tombe près de 60 images par seconde.
function peutEtreBorneeParVsync(fps) {
  return typeof fps === "number" && fps >= 55 && fps <= 62;
}

module.exports = {
  ErreurGpu, CARTES, LOGICIEL, normaliserCarte, fichierEgl, environnementCarte, optionsChromium, verifierMoteur,
  peutEtreBorneeParVsync,
};
