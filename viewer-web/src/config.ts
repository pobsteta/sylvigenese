// Lecture de config.yml (spec §2). Le contrôle des clés est fait par le validateur
// (contracts/json/config.schema.json), pas ici : ce fichier ne fait que lire.

import { readFileSync } from "node:fs";
import { parse } from "yaml";

export class ErreurModule extends Error {}

export interface Config {
  schema_version: number;
  zone: string;
  crs: string;
  grid: { resolution_m: number };
  management: string;
}

export function lireConfig(chemin: string): Config {
  let texte: string;
  try {
    texte = readFileSync(chemin, "utf-8");
  } catch {
    throw new ErreurModule(`config.yml introuvable : ${chemin}`);
  }
  let contenu: unknown;
  try {
    contenu = parse(texte);
  } catch (erreur) {
    throw new ErreurModule(`config.yml illisible (${chemin}) : ${(erreur as Error).message}`);
  }
  if (contenu === null || typeof contenu !== "object" || Array.isArray(contenu)) {
    throw new ErreurModule(`config.yml vide ou mal formé : ${chemin}`);
  }
  return contenu as Config;
}
