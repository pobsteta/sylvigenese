# Crédits et licences de viewer-massif

Projet sous licence GPL-3 (voir le dépôt). Ce qui suit est repris d'ailleurs, avec son avis (shader, texture, GUT et ses polices). Rien d'autre n'est copié.

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

- **Auteur :** FabinhoSC, « Stylized Grass and Bush Textures », OpenGameArt, licence **CC0** (domaine public). **Preuve,
  lue le 26/11/2026 :** page `https://opengameart.org/content/stylized-grass-and-bush-textures-0`, champ « License(s) » =
  « CC0 » (`http://creativecommons.org/publicdomain/zero/1.0/`) et mention « Copyright/Attribution Notice » : « They are in
  the public domain (CC0). » La page liste `grassbushcc008.png`. (Copie de la page hors dépôt, `data/sources/m6a/` ; l'URL
  et la phrase ci-dessus suffisent à la refaire.) Fichier : `textures/grassbushcc008.png`
  (sha256 `b09c287f65e5c2ced9aeec591674241d5cf846619c26dababfaba81a1fe29982`), copié de la démonstration au même commit `623212f`.

## Tests : GUT 9.6.1 (MIT)

- **GUT** (Godot Unit Test), de Butch Wesley, **MIT**, version 9.6.1, dépôt `bitwes/Gut`, commit
  `c80954f47bed74a0a2c471d472c0389f98e0a8f6`. Copié tel quel dans `addons/gut/`, avec son `LICENSE.md` : l'agent ne peut pas
  le télécharger, et les tests doivent tourner partout. Passer à une version de Godot 4.7 demande GUT 9.7.1 (décision à part).
- **Polices de GUT** (`addons/gut/fonts/`, 12 fichiers `.ttf`, 3 familles en 4 graisses, avec leurs `.import`), sous **SIL Open
  Font License 1.1** (OFL), texte dans `addons/gut/fonts/OFL.txt` ; licence lue dans la table de noms de chaque famille
  (26/11/2026) :
  - **Anonymous Pro** : « Copyright (c) 2009, Mark Simonson », nom réservé « Anonymous Pro » (c'est l'avis qui ouvre `OFL.txt`) ;
  - **Courier Prime** : « Copyright 2015 The Courier Prime Project Authors » (`quoteunquoteapps/CourierPrime`) ;
  - **Lobster Two** : « Copyright (c) 2011, Pablo Impallari », nom réservé « Lobster ».
  `OFL.txt` ne porte que l'avis d'Anonymous Pro : les deux autres avis ne sont lus que dans les polices. Les polices ne sont
  ni modifiées ni vendues seules ; la vue ne les utilise pas (elles servent à l'interface de GUT).

## Moteur : Godot 4.6.3-stable (MIT)

- « Copyright (c) 2014-present Godot Engine contributors », « Copyright (c) 2007-2014 Juan Linietsky, Ariel Manzur ». Le
  binaire exporté embarque des composants tiers avec leurs propres avis (`COPYRIGHT.txt` du dépôt Godot) : à joindre à la
  première livraison d'un binaire (mission 073, export).
