// Lecture de config.yml (spec §2). Le contrôle des clés est fait par le validateur
// (contracts/json/config.schema.json), pas ici : ce fichier ne fait que lire.

import { readFileSync } from "node:fs";
import { parse } from "yaml";

export class ModuleError extends Error {}

export interface Config {
  schema_version: number;
  zone: string;
  crs: string;
  grid: { resolution_m: number };
  management: string;
}

export function readConfig(path: string): Config {
  let text: string;
  try {
    text = readFileSync(path, "utf-8");
  } catch {
    throw new ModuleError(`config.yml introuvable : ${path}`);
  }
  let content: unknown;
  try {
    content = parse(text);
  } catch (error) {
    throw new ModuleError(`config.yml illisible (${path}) : ${(error as Error).message}`);
  }
  if (content === null || typeof content !== "object" || Array.isArray(content)) {
    throw new ModuleError(`config.yml vide ou mal formé : ${path}`);
  }
  return content as Config;
}
