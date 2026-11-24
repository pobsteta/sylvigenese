// Appel du validateur des contrats en sous-processus (spec §2, ADR 0002).
// Aucun import du code du validateur : c'est un passage par fichiers.

import { existsSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { ErreurModule } from "./config.ts";

// SYLVIGENESE_VALIDATE si elle existe, sinon contracts/validate depuis le dossier courant.
export function cheminValidateur(): string {
  const env = process.env["SYLVIGENESE_VALIDATE"];
  return env ? env : "contracts/validate";
}

// Lance `python3 <validateur> <arguments>` ; rend son code (0 conforme, 2 impossible, 3 non conforme).
export function appelerValidateur(argumentsValidateur: string[]): number {
  const validateur = cheminValidateur();
  if (!existsSync(validateur)) {
    throw new ErreurModule(`validateur introuvable : ${validateur} (mission 009)`);
  }
  const resultat = spawnSync("python3", [validateur, ...argumentsValidateur], { stdio: "inherit" });
  if (resultat.status === null) {
    throw new ErreurModule("le validateur n'a pas pu être lancé ou a été interrompu");
  }
  return resultat.status;
}
