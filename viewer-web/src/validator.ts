// Appel du validateur des contrats en sous-processus (spec §2, ADR 0002).
// Aucun import du code du validateur : c'est un passage par fichiers.

import { existsSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { ModuleError } from "./config.ts";

// SYLVIGENESE_VALIDATE si elle existe, sinon contracts/validate depuis le dossier courant.
export function validatorPath(): string {
  const env = process.env["SYLVIGENESE_VALIDATE"];
  return env ? env : "contracts/validate";
}

// Lance `python3 <validateur> <arguments>` ; rend son code (0 conforme, 2 impossible, 3 non conforme).
export function callValidator(validatorArguments: string[]): number {
  const validator = validatorPath();
  if (!existsSync(validator)) {
    throw new ModuleError(`validateur introuvable : ${validator} (mission 009)`);
  }
  const result = spawnSync("python3", [validator, ...validatorArguments], { stdio: "inherit" });
  if (result.status === null) {
    throw new ModuleError("le validateur n'a pas pu être lancé ou a été interrompu");
  }
  return result.status;
}
