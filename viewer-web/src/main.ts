// Module `viewer-web` (spec §2) : squelette de la mission 012.
//
// Étape visée plus tard : page web locale (iTowns) sur `tiles/` et `web/`.
// Pour l'instant : lit config.yml et le fait valider.
// Usage : node src/main.ts [--config <chemin>]   Code de sortie : 0 ou 2.

import { pathToFileURL } from "node:url";
import { ErreurModule, lireConfig } from "./config.ts";
import { appelerValidateur } from "./validateur.ts";

export const SORTIE_OK = 0;
export const SORTIE_IMPOSSIBLE = 2;

export function executer(cheminConfig: string): number {
  try {
    lireConfig(cheminConfig);
    const code = appelerValidateur(["config", cheminConfig]);
    if (code !== 0) {
      throw new ErreurModule(`config.yml non conforme (validateur, code ${code})`);
    }
  } catch (erreur) {
    if (!(erreur instanceof ErreurModule)) throw erreur;
    console.error(`[viewer-web] erreur : ${erreur.message}`);
    return SORTIE_IMPOSSIBLE;
  }
  console.error("[viewer-web] config.yml lu et conforme ; rien d'autre à faire (squelette).");
  return SORTIE_OK;
}

export function main(argv: string[]): number {
  if (argv.length === 0) return executer("config.yml");
  if (argv.length === 2 && argv[0] === "--config") return executer(argv[1] as string);
  console.error("usage : main.ts [--config <chemin>]");
  return SORTIE_IMPOSSIBLE;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exit(main(process.argv.slice(2)));
}
