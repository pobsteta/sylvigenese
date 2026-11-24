# sylvigenese

[![CI](https://github.com/pobsteta/sylvigenese/actions/workflows/ci.yml/badge.svg)](https://github.com/pobsteta/sylvigenese/actions/workflows/ci.yml)
[![Release](https://github.com/pobsteta/sylvigenese/actions/workflows/release.yml/badge.svg)](https://github.com/pobsteta/sylvigenese/actions/workflows/release.yml)
[![Version](https://img.shields.io/github/v/release/pobsteta/sylvigenese?label=version)](https://github.com/pobsteta/sylvigenese/releases)
![R](https://img.shields.io/badge/R-targets%20%C2%B7%20lidR-276DC3?logo=r&logoColor=white)
![GAMA](https://img.shields.io/badge/GAMA-headless-6A1B9A)
![Python](https://img.shields.io/badge/Python-glTF%20%C2%B7%203D%20Tiles-3776AB?logo=python&logoColor=white)
![iTowns](https://img.shields.io/badge/iTowns-TypeScript-3178C6?logo=typescript&logoColor=white)
![Godot](https://img.shields.io/badge/Godot-4-478CBF?logo=godotengine&logoColor=white)
![Méthode](https://img.shields.io/badge/m%C3%A9thode-Imp%C3%A9ratrice-8d6e63)
[![Licence](https://img.shields.io/badge/licence-GPL--3.0-blue)](LICENSE)

`sylvigenese` simule et donne à voir la construction d'une forêt dans le temps, de la
sylvoécorégion (SER) jusqu'à la plante du sous-bois : une chaîne de cinq modules reliés par
des fichiers (R, GAMA, Python), dont le dernier maillon est une consultation web (iTowns) et
immersive (Godot 4).

Le cahier des charges est [`docs/BRIEF.md`](docs/BRIEF.md) ; il fait foi. Le projet est piloté
selon la méthode de l'Impératrice ([`CLAUDE.md`](CLAUDE.md), [`pilotage/`](pilotage/)).

---

## État

Jalon en cours : **M0** (squelette du dépôt, contrats, jeu d'essai fictif), pas encore
commencé : le brief et la spec attendent la validation de Pascal (`/imperatrice:brief`).

## Versions des outils

À figer au jalon M0 (BRIEF §13) : R, GAMA, Python, Node, Godot.

---

## Versionnement & releases automatiques

Versions **calendaires** `vAAAA.MM.N` : année, mois (UTC), puis un compteur du mois qui repart
à 1 chaque mois (`v2026.11.1`, `v2026.11.2`, …, `v2026.12.1`). Même règle que `marculus`.

Au **merge d'une PR sur `main`** :

1. `ci.yml` lance les tests (scripts de release, puis `.claude/test-command` quand il existe) ;
2. **seulement s'ils sont verts**, `release.yml` (déclenché par `workflow_run`) décide s'il faut
   publier avec [`.github/scripts/release-necessaire.sh`](.github/scripts/release-necessaire.sh) ;
3. si oui, il calcule le tag avec
   [`.github/scripts/version-calendaire.sh`](.github/scripts/version-calendaire.sh), pose un tag
   annoté sur le commit testé et crée la **release GitHub** avec ses notes générées.

**Pas de release quand le produit ne change pas** : si, depuis le dernier tag `v*`, seuls
`pilotage/`, `docs/`, des fichiers `*.md`, `.github/badges/` ou des tests (`tests/`,
`.github/scripts/test-*.sh`) ont changé, aucun tag n'est posé. Pas de release non plus si le
commit n'est plus la tête de `main` (une CI relancée sur un ancien commit ne publie rien). Dans le
doute, on publie.

Jamais de push direct sur `main` : tout passe par une pull request.

Tester les scripts en local :

```bash
.github/scripts/test-version-calendaire.sh
.github/scripts/test-release-necessaire.sh
```

---

## Licence

GPL-3.0, cohérente avec `lidR`, `lasR` et GAMA. Voir [`LICENSE`](LICENSE).
