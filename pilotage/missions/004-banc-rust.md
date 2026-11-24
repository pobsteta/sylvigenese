# Mission 004 — banc d'essai : implémentation Rust

## Mission

**En une phrase (quoi, et pourquoi) :** implémenter en Rust l'algorithme de `bench/SPEC.md`, à la lettre, pour que l'on mesure au même algorithme ce que ce langage tient à l'échelle d'une SER (décision de Pascal du 24/11/2026, ADR 0001, point B3).

**Redite par l'agent :** _à compléter par l'agent avant d'agir._

## Les trois questions (règle de staffing)

| Question | Réponse | Conséquence |
|---|---|---|
| Peut-il redire la mission en une phrase, avec son but ? | oui | |
| Sait-il comment faire ? | oui | `bench/SPEC.md` fixe l'algorithme, l'aléa et les sorties |
| A-t-il les moyens ? | oui | rustc et cargo 1.97.0 ; crates rustfft, rayon (et ndarray au besoin) depuis crates.io |

**Temps de la main :** donner. **Degré de la main :** le chef tranche (la spec est imposée ; une ambiguïté remonte à l'orchestrateur).

## Ma réponse d'abord

_Rempli par Pascal seul._

## L'Homme

- **Agent :** `dev` — **Modèle :** sonnet
- **Ce qui ne lui est pas demandé :** optimiser au-delà de l'usage courant du langage, mesurer à grande échelle (mission de mesure séparée), toucher aux autres langages.

## Harnais

- **Peut (périmètre) :** `bench/rust/` seulement.
- **Câblé :** pas de `main`, journal en ajout seul.
- **Ne doit pas :** modifier `bench/SPEC.md`, changer l'algorithme, faire une convolution directe pour la dispersion, corriger une valeur en silence, faire un commit git.
- **Sources autorisées :** `bench/SPEC.md`, documentation officielle du langage et des bibliothèques.

## Valeur provisoire

- Aucune : les paramètres du banc sont synthétiques et fixés par la spec.

## Dépend de / rouge attendu jusqu'à

- **Dépend de :** `bench/SPEC.md`. **CI rouge attendue :** aucune.

## Tests

- cargo test : valeurs de référence de l'aléa, noyau normalisé, FFT contre convolution directe, arrêt sur `--inject-nan` et `--hmax-zero`, identité au bit près entre 1 et 4 fils sur `N = 200`, `Y = 5`.

## Terrain

- **Échantillon que Pascal vérifiera :** `summary.csv` de `N = 500`, `Y = 100`, comparé à celui des deux autres langages.

## Qui veille, qui tranche

- **Relecteur :** `relecteur` (relecture croisée : il n'a pas écrit ce code), puis Pascal.
- **Critère d'arrêt de la relecture :** 3 allers-retours. **Qui tranche :** Pascal.

## Comment saura-t-on que ça marche ?

Les tests passent, et `summary.csv` pour `N = 500`, `Y = 100` concorde avec celui des deux autres langages à la tolérance de la spec.
