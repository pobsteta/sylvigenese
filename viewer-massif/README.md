# viewer-massif : la vue massif (Godot 4.6)

Consultation immersive d'un bloc de massif (BRIEF §10, M6a). Elle lit `massif/index.json` et `massif/<année>/<bloc>.json`
(contrat `assets.massif_block`, version 2) et les `.glb` de `assets/trees/` de la zone, **par fichiers** : elle ne lit ni
`sim/` ni Parquet.

## Lancer

    godot --path viewer-massif -- --zone data/<zone> --x <X> --y <Y> --year <A>

`X` et `Y` en EPSG:2154 (mètres). Repli si Vulkan manque : ajouter `--rendering-method gl_compatibility` avant `--` (la
preuve visuelle du repli est M6b). Commandes : souris (clic pour la capturer, Échap pour la rendre), W A S D, Q et E, Maj.

`--selftest` (même commande) : charge la zone sans rendu, écrit une ligne `SELFTEST {json}` et sort à 0. Sortie non nulle
avec la cause en français : 2 arguments, 3 `config.yml`, 4 zone, année ou point (années disponibles, emprise), 5 modèles ou blocs.

`config.yml` (bloc `viewer`, constantes d'affichage provisoires « illustration, non mesurée ») est cherché dans la zone, à
deux niveaux au-dessus de la zone (`data/<zone>/../../`), dans le dossier courant, à côté de `viewer-massif/`, à côté de
l'exécutable. Sans lui la vue s'arrête : aucune valeur de repli.

## Ce qu'on voit

- Repère : x est, y haut, z = -nord (le nord est devant). Terrain : MNT de la grille de 25 m, lisse (pas le LiDAR).
- Arbres : un `MultiMeshInstance3D` par bloc, case de 25 m, modèle et niveau de détail (`visibility_range`). Niveaux lus
  dans `MSFT_lod` et `extras.MSFT_screencoverage` du `.glb` (Godot ne lit pas `MSFT_lod`).
- Herbe et semis autour de la caméra, recentrés au-delà de `viewer.grass.recenter_distance_m`, calculés dans un fil ; densité
  tirée du couvert de la cellule et des semis du bloc ; plafond d'instances dit à l'écran quand il tronque.
- Bandeau : provisoire, semis non simulés, modèles génériques, stade de l'arbre, sol à 25 m.

## Tests

    godot --headless --path viewer-massif --import
    godot --headless --path viewer-massif -s addons/gut/gut_cmdln.gd -gdir=res://tests -gexit

Licences et provenances : `CREDITS.md`.
