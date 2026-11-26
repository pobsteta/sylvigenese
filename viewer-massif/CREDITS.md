# Crédits et licences de viewer-massif

Projet sous licence GPL-3 (voir le dépôt). Ce qui suit est repris d'ailleurs, avec son avis. Rien d'autre n'est copié.

## Shader d'herbe : SimpleGrassTextured (MIT)

- **Auteur :** IcterusGames, « Copyright (c) 2023 IcterusGames », licence **MIT**. Projet amont : `IcterusGames/SimpleGrassTextured`.
- **Source de la copie :** `GamesNotDeveloped/godot-forest-demo`, commit **`623212f`** (clone superficiel du 26/11/2026, lu seulement, rien exécuté).
- **Fichiers copiés tels quels** (avis de copyright et texte MIT gardés en tête de chaque fichier) :
  `shaders/grass.gdshader` et `shaders/grass.gdshaderinc` (origine : `grass/shaders/` de la démonstration).
- **Uniforms globaux** (`sgt_*`) : déclarés dans `project.godot` (`[shader_globals]`) ; leurs textures sont fabriquées au
  démarrage par `scripts/massif_view.gd` (aucune texture de la démonstration, hors celle ci-dessous).
- **Non repris :** les autres shaders (mouvement, flou, distance, variantes), `normal.png`, `motion.png`, `wind_pattern.png`,
  `grass.mesh` (origine non établie) et tout le reste de la démonstration (dépôt en CC BY 4.0). Le maillage du brin
  (`blade_mesh`) et la texture de normales sont fabriqués par la vue.

## Texture d'herbe : grassbushcc008.png (CC0)

- **Auteur :** FabinhoSC, « Stylized Grass and Bush Textures », OpenGameArt, licence **CC0** (domaine public) ; page lue le
  26/11/2026 (`data/sources/m6a/INDEX.md`). Fichier : `textures/grassbushcc008.png`
  (sha256 `b09c287f65e5c2ced9aeec591674241d5cf846619c26dababfaba81a1fe29982`), copié de la démonstration au même commit `623212f`.

## Tests : GUT 9.6.1 (MIT)

- **GUT** (Godot Unit Test), de Butch Wesley, **MIT**, version 9.6.1, dépôt `bitwes/Gut`, commit
  `c80954f47bed74a0a2c471d472c0389f98e0a8f6`. Copié tel quel dans `addons/gut/`, avec son `LICENSE.md` : l'agent ne peut pas
  le télécharger, et les tests doivent tourner partout. Passer à une version de Godot 4.7 demande GUT 9.7.1 (décision à part).

## Moteur : Godot 4.6.3-stable (MIT)

- « Copyright (c) 2014-present Godot Engine contributors », « Copyright (c) 2007-2014 Juan Linietsky, Ariel Manzur ». Le
  binaire exporté embarque des composants tiers avec leurs propres avis (`COPYRIGHT.txt` du dépôt Godot) : à joindre à la
  première livraison d'un binaire (mission 073, export).
