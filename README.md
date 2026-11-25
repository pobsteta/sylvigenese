# sylvigenese

[![CI](https://github.com/pobsteta/sylvigenese/actions/workflows/ci.yml/badge.svg)](https://github.com/pobsteta/sylvigenese/actions/workflows/ci.yml)
[![Release](https://github.com/pobsteta/sylvigenese/actions/workflows/release.yml/badge.svg)](https://github.com/pobsteta/sylvigenese/actions/workflows/release.yml)
[![Version](https://img.shields.io/github/v/release/pobsteta/sylvigenese?label=version)](https://github.com/pobsteta/sylvigenese/releases)
![R](https://img.shields.io/badge/R-targets%20%C2%B7%20lidR-276DC3?logo=r&logoColor=white)
![Rust](https://img.shields.io/badge/Rust-simulate-000000?logo=rust&logoColor=white)
![Python](https://img.shields.io/badge/Python-glTF%20%C2%B7%203D%20Tiles-3776AB?logo=python&logoColor=white)
![iTowns](https://img.shields.io/badge/iTowns-TypeScript-3178C6?logo=typescript&logoColor=white)
![Godot](https://img.shields.io/badge/Godot-4-478CBF?logo=godotengine&logoColor=white)
![Méthode](https://img.shields.io/badge/m%C3%A9thode-Imp%C3%A9ratrice-8d6e63)
[![Licence](https://img.shields.io/badge/licence-GPL--3.0-blue)](LICENSE)

`sylvigenese` simule et donne à voir la construction d'une forêt dans le temps, de la
sylvoécorégion (SER) jusqu'à la plante du sous-bois : une chaîne de cinq modules reliés par
des fichiers (R, Rust, Python), dont le dernier maillon est une consultation web (iTowns) et
immersive (Godot 4).

Le cahier des charges est [`docs/BRIEF.md`](docs/BRIEF.md) ; il fait foi. Le projet est piloté
selon la méthode de l'Impératrice ([`CLAUDE.md`](CLAUDE.md), [`pilotage/`](pilotage/)).

---

## État

- **M0** (squelette du dépôt, contrats, validateur, jeu d'essai fictif, CI) : livré.
- **M1a** (`prepare`, `biomes`, arbres initiaux avec leur houppier) : rempli sur le jeu fictif.
- **M2a** (`dynamics` : accroissement, mortalité, recrutement et hauteur ajustés sur l'IFN
  fictif, validation croisée par blocs, rapport par essence) : rempli sur le jeu fictif.
- **Vue iTowns de l'état initial** (M4a, première partie) : livrée.
- **M3a** (moteur `simulate` en Rust : 100 ans sur le massif fictif, identité au bit près quel
  que soit le nombre de fils, contrôles) : rempli sur son critère technique. **La trajectoire
  n'est pas encore celle d'une forêt** (référence technique, non validée écologiquement).
- **Vue iTowns dans le temps** (suite de M4a) : livrée. Un curseur fait défiler les années
  simulées ; la fiche d'une cellule montre son évolution, et le sol la surface terrière de
  l'année. Chiffres provisoires, trajectoire non validée écologiquement.
- Suivant : `post` (volume et carbone), puis **M5a** et **M6a** (vue Godot). M3b attend les
  données réelles.
- En attente de Pascal (données réelles) : M1b, M2b.

L'avancement détaillé est dans [`pilotage/kanban.md`](pilotage/kanban.md).

## Voir l'état initial dans iTowns

La vue web (mission 029) affiche les arbres de l'état initial, la carte des types de végétation et la fiche d'une
cellule, sur le jeu fictif. **Résultat provisoire** : valeurs fictives, rien d'écologique à en conclure.

```
cd viewer-web && npm ci && cd ..                      # une fois (versions figées dans package-lock.json)
make prepare biomes trees assets ZONE=zone_fictive    # produit tiles/, web/cells/ et web/rasters/
make viewer ZONE=zone_fictive                         # serveur local au premier plan
```

Ouvrir http://127.0.0.1:8080/ (autre port : `PORT=8090`). Pour une capture d'écran (Playwright, Chromium) :
`node viewer-web/scripts/capture.cjs http://127.0.0.1:8080/ capture.png`.

Ce qu'on doit voir :
- un bandeau « Résultat provisoire » ; au centre, les arbres (14 080 sur le jeu fictif, compteur en pied de page) posés sur
  la carte colorée des types de végétation, avec sa légende ; un curseur règle l'opacité de la carte ;
- un clic sur une cellule ouvre sa fiche : station, type de végétation, composition, H0, densité ; volume et carbone
  « non calculés » ; la commande `viewer-massif -- --x <X> --y <Y> --year <A>` à copier ;
- le curseur des années est désactivé (une seule année).

Avec ou sans réseau : tout est servi en local, la page s'affiche sans réseau. Terrain : MNT local sur son emprise.
- **Zone réelle** (pas de `zone.yml`, ou `fictive: false`) : si `data.geopf.fr` est joignable, la page ajoute l'orthophoto
  IGN en fond et le terrain IGN hors de l'emprise du MNT ; sinon elle le dit en pied de page (ellipsoïde, altitude 0).
- **Zone fictive** (`zone.yml` avec `fictive: true`, cas du jeu d'essai) : ni orthophoto ni terrain IGN, pour ne pas
  mêler de vraies données aux données fictives ; hors de l'emprise, un plan neutre à l'altitude minimale du MNT, dit en
  pied de page (« hors zone : plan neutre pour l'affichage, jeu fictif »).

Le chargement complet prend environ 20 s en jeu fictif (plus avec le fond IGN d'une zone réelle). Sans GPU, le navigateur dessine en logiciel : moins d'une image par seconde, sans rapport avec une machine normale.
Les tests de la vue sont `cd viewer-web && npm test` (logique) et `tests/m4/test_m4_vue.py` (navigateur).

## Versions des outils

Figées au jalon M0 (mission 012) :

| Outil | Version |
|---|---|
| R | 4.3.3 (testthat 3.2.1, yaml 2.3.8) |
| Rust | 1.97.0, édition 2021 |
| Python | 3.13 (PyYAML 6.0.3, pytest 9.1.1, pyarrow 26.0.1, frictionless 5.21.0, jsonschema 4.26.0) |
| Node | 22.23.5, npm 10.9.9, TypeScript 7.0.2 |
| Godot | 4.6 (projet déclaré, pas encore installé dans la CI) |

En CI, les paquets R (`testthat`, `yaml`, `terra`, `sf`, `targets`, `arrow`) viennent de r2u.

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
