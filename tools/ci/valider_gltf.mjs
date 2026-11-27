#!/usr/bin/env node
// glTF-Validator de Khronos (paquet npm « gltf-validator », version figée dans tools/ci/package.json, licence
// Apache-2.0 lue dans le paquet installé) sur tous les .glb d'un ou plusieurs dossiers (mission 075 ; plan m6a T4 et §6).
//
//   node tools/ci/valider_gltf.mjs <dossier ou fichier.glb> [...]
//
// Code de sortie : 0 si aucun .glb n'a d'erreur (severity 0) ; 1 s'il y en a (ou si un fichier est illisible) ;
// 2 si l'appel est mal formé ou si AUCUN .glb n'est trouvé (une validation qui ne valide rien n'est pas un succès).
// Les avertissements (severity 1) sont comptés et dits, jamais filtrés ni transformés en erreurs ; aucune erreur n'est
// filtrée. Les informations et indices (severity 2 et 3) sont comptés dans le résumé.
// En CI, un tableau est ajouté au résumé du job ($GITHUB_STEP_SUMMARY).
import { readFileSync, readdirSync, statSync, appendFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";

const require = createRequire(import.meta.url);
const validator = require("gltf-validator");
const SEVERITES = ["erreur", "avertissement", "information", "indice"];

// Tous les .glb sous le chemin, triés (ordre stable) ; un chemin qui n'existe pas est une erreur d'appel.
export function trouverGlb(chemin) {
  const s = statSync(chemin);
  if (s.isFile()) return chemin.endsWith(".glb") ? [chemin] : [];
  const out = [];
  for (const e of readdirSync(chemin, { withFileTypes: true }).sort((a, b) => (a.name < b.name ? -1 : 1))) {
    const p = join(chemin, e.name);
    if (e.isDirectory()) out.push(...trouverGlb(p));
    else if (e.isFile() && e.name.endsWith(".glb")) out.push(p);
  }
  return out;
}

// Valide un fichier : { fichier, erreurs, avertissements, informations, indices, messages (sévérité 0 et 1, + extensions non vérifiées) }.
export async function validerFichier(fichier) {
  const octets = new Uint8Array(readFileSync(fichier));
  const rapport = await validator.validateBytes(octets, { uri: fichier, maxIssues: 0 });
  const n = [0, 0, 0, 0];
  for (const m of rapport.issues.messages) n[m.severity] += 1;
  // Le décompte du validateur et le nôtre doivent concorder : sinon on ne devine pas, on échoue.
  if (n[0] !== rapport.issues.numErrors || n[1] !== rapport.issues.numWarnings) {
    throw new Error(`${fichier} : décompte incohérent (messages ${n[0]}/${n[1]}, rapport ${rapport.issues.numErrors}/${rapport.issues.numWarnings})`);
  }
  return {
    fichier, erreurs: n[0], avertissements: n[1], informations: n[2], indices: n[3],
    // UNSUPPORTED_EXTENSION (information) est gardée : elle dit ce que le validateur ne vérifie PAS (ex. MSFT_lod).
    messages: rapport.issues.messages.filter((m) => m.severity <= 1 || m.code === "UNSUPPORTED_EXTENSION"),
  };
}

export async function main(argv, env = process.env, sortie = console) {
  if (argv.length === 0) {
    sortie.error("usage : node tools/ci/valider_gltf.mjs <dossier ou fichier.glb> [...]");
    return 2;
  }
  const fichiers = [];
  for (const a of argv) {
    try {
      fichiers.push(...trouverGlb(resolve(a)));
    } catch (e) {
      sortie.error(`valider_gltf : chemin illisible « ${a} » (${e.code ?? e.message})`);
      return 2;
    }
  }
  if (fichiers.length === 0) {
    sortie.error(`valider_gltf : aucun .glb sous ${argv.join(", ")} : rien n'a été validé, c'est un échec.`);
    return 2;
  }
  const racine = process.cwd();
  const rel = (f) => (f.startsWith(racine + "/") ? f.slice(racine.length + 1) : f);
  let erreurs = 0, avertissements = 0, informations = 0, indices = 0, illisibles = 0;
  const lignes = [];
  for (const f of fichiers) {
    let r;
    try {
      r = await validerFichier(f);
    } catch (e) {
      illisibles += 1;
      sortie.error(`ECHEC ${rel(f)} : ${e.message ?? e}`);
      lignes.push(`| \`${rel(f)}\` | illisible | | | ${String(e.message ?? e).replace(/\|/g, "/")} |`);
      continue;
    }
    erreurs += r.erreurs; avertissements += r.avertissements; informations += r.informations; indices += r.indices;
    sortie.log(`${r.erreurs ? "ECHEC" : "ok   "} ${rel(f)} : ${r.erreurs} erreur(s), ${r.avertissements} avertissement(s), ${r.informations} information(s), ${r.indices} indice(s)`);
    for (const m of r.messages) sortie.log(`    ${SEVERITES[m.severity]} ${m.code} ${m.pointer ?? ""} : ${m.message}`);
    lignes.push(`| \`${rel(f)}\` | ${r.erreurs} | ${r.avertissements} | ${r.informations + r.indices} | ${r.messages.slice(0, 3).map((m) => m.code).join(", ")} |`);
  }
  const verdict = erreurs === 0 && illisibles === 0 ? "vert" : "ROUGE";
  const total = `${fichiers.length} .glb validés : ${erreurs} erreur(s), ${avertissements} avertissement(s), ${informations} information(s), ${indices} indice(s), ${illisibles} illisible(s) : ${verdict}`;
  sortie.log(total);
  if (env.GITHUB_STEP_SUMMARY) {
    const version = require("gltf-validator/package.json").version;
    appendFileSync(env.GITHUB_STEP_SUMMARY, [
      `### glTF-Validator de Khronos ${version} (licence ${require("gltf-validator/package.json").license})`,
      `- ${total}`,
      `- Les avertissements sont comptés, non filtrés ; seule une erreur (severity 0) fait échouer.`,
      "", "| fichier | erreurs | avertissements | infos et indices | codes (3 premiers) |", "|---|---|---|---|---|", ...lignes, "",
    ].join("\n"));
  }
  return erreurs === 0 && illisibles === 0 ? 0 : 1;
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  process.exitCode = await main(process.argv.slice(2));
}
