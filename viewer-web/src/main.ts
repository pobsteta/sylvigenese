// Module `viewer-web` (spec §2) : squelette de la mission 012.
//
// Étape visée plus tard : page web locale (iTowns) sur `tiles/` et `web/`.
// Pour l'instant : lit config.yml et le fait valider.
// Usage : node src/main.ts [--config <chemin>]   Code de sortie : 0 ou 2.

import { pathToFileURL } from "node:url";
import { ModuleError, readConfig } from "./config.ts";
import { callValidator } from "./validator.ts";

export const EXIT_OK = 0;
export const EXIT_IMPOSSIBLE = 2;

export function run(configPath: string): number {
  try {
    readConfig(configPath);
    const code = callValidator(["config", configPath]);
    if (code !== 0) {
      throw new ModuleError(`config.yml non conforme (validateur, code ${code})`);
    }
  } catch (error) {
    if (!(error instanceof ModuleError)) throw error;
    console.error(`[viewer-web] erreur : ${error.message}`);
    return EXIT_IMPOSSIBLE;
  }
  console.error("[viewer-web] config.yml lu et conforme ; rien d'autre à faire (squelette).");
  return EXIT_OK;
}

export function main(argv: string[]): number {
  if (argv.length === 0) return run("config.yml");
  if (argv.length === 2 && argv[0] === "--config") return run(argv[1] as string);
  console.error("usage : main.ts [--config <chemin>]");
  return EXIT_IMPOSSIBLE;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exit(main(process.argv.slice(2)));
}
