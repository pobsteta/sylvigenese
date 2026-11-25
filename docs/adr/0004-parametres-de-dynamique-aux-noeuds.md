# ADR 0004 — paramètres de la dynamique écrits en valeurs aux nœuds

- **Date :** 2026-11-25
- **Statut :** acceptée par délégation de Pascal
- **Proposée par :** `dev` de la mission 025 (plan du 25/11/2026), relevée par le `relecteur`
  (relecture de M2a, point important n° 4)
- **Tranchée par :** Claude (orchestrateur, par délégation de Pascal)

## La décision en une phrase

`dynamics` (R, mgcv) écrit chaque modèle dans `params/{growth,mortality,recruitment,height_curve}.parquet`
sous la forme d'un **intercept, d'effets de niveaux (SER) et, pour chaque terme lisse, des
couples (nœud, valeur de la fonction au nœud)** ; `simulate` (Rust) relit ces termes par une
**spline cubique naturelle** passant par ces nœuds, bornée aux nœuds extrêmes, puis applique le
lien et le décalage du modèle. Ni R ni mgcv ne sont nécessaires pour relire les paramètres.

## Contexte

Un GAM ne se résume pas à quelques coefficients. Le moteur `simulate` est en Rust (ADR 0001) et
ne peut pas appeler `predict.gam`. Les modules ne se parlent que par fichiers, aux formats
ouverts (ADR 0002).

## Options pesées

| Option | Pour | Contre |
|---|---|---|
| **A. Valeurs aux nœuds** (retenue) | exacte : les splines `cr` de mgcv sont des splines cubiques naturelles sur leurs nœuds, la relecture égale `predict.gam` à 1e-10 sur la plage des données (test de `R/tests/testthat/test-dynamics.R`) ; légère ; lisible ligne à ligne ; recodable en une vingtaine de lignes de Rust sans générique | interdit les interactions lisses entre deux variables (`te()`) ; modèles additifs seulement |
| B. Table de prédiction sur une grille de covariables | indépendante de la forme du modèle | environ un million de lignes par essence pour 6 covariables à 10 points ; interpolation multilinéaire approchée |
| C. Objet R sérialisé (`.rds`) | fidèle | format fermé à R, contraire à l'ADR 0002 et au test du successeur |

## Conséquences

- Contrat : `contracts/tables/params/dynamics_params.schema.json` (colonnes `species`,
  `species_group`, `model`, `term`, `variable`, `x`, `value`, `provisoire`, `source`). La
  description du contrat donne l'algorithme de relecture, les liens et les décalages par modèle.
- Hors de la plage des nœuds, la valeur est bornée au nœud extrême ; `simulate` compte et
  signale les sorties de domaine (spec §6, contrôles).
- Si un jour une interaction lisse devient nécessaire, cet ADR est à rouvrir (option B pour le
  seul terme concerné).

## Ce que Pascal peut défaire

Tout : la représentation ne touche que le dépôt.
