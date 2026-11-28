# viewer-massif : la vue massif (Godot 4.6)

Consultation immersive d'un bloc de massif (BRIEF §10, M6a). Elle lit `massif/index.json` et `massif/<année>/<bloc>.json`
(contrat `assets.massif_block`, version 2) et les `.glb` de `assets/trees/` de la zone, **par fichiers** : elle ne lit ni
`sim/` ni Parquet.

## Lancer

    godot --path viewer-massif -- --zone data/<zone> --x <X> --y <Y> --year <A>

`X` et `Y` en EPSG:2154 (mètres). Repli si Vulkan manque : ajouter `--rendering-method gl_compatibility` avant `--` (la
preuve visuelle du repli est M6b). Commandes : souris (clic pour la capturer, Échap pour la rendre), W A S D (Z Q S D sur un clavier AZERTY), Q et E pour descendre et monter, Maj pour aller vite, flèches pour tourner la tête
sans souris (vitesse `viewer.camera.key_turn_rad_s`).

`--selftest` (même commande) : charge la zone sans rendu, écrit une ligne `SELFTEST {json}` et sort à 0. Sortie non nulle
avec la cause en français : 2 arguments, 3 `config.yml`, 4 zone, année ou point (années disponibles, emprise), 5 modèles ou blocs.

`config.yml` (bloc `viewer`, constantes d'affichage provisoires « illustration, non mesurée ») est cherché dans la zone, à
deux niveaux au-dessus de la zone (`data/<zone>/../../`), dans le dossier courant, à côté de `viewer-massif/`, à côté de
l'exécutable. Sans lui la vue s'arrête : aucune valeur de repli. Toutes les constantes d'affichage y sont (rayon des blocs
voisins, caméra, sol, soleil, textes, herbe, case de 25 m) ; aucune n'est écrite dans les scripts, et
`contracts/tests/test_m6b_affichage.py` échoue si un littéral de ce genre revient (mission 077).

## Ce qu'on voit

- Repère : x est, y haut, z = -nord (le nord est devant). Terrain : MNT de la grille de 25 m, lisse (pas le LiDAR).
- Arbres : un `MultiMeshInstance3D` par bloc, case de 25 m, modèle et niveau de détail (`visibility_range`). Niveaux lus
  dans `MSFT_lod` et `extras.MSFT_screencoverage` du `.glb` (Godot ne lit pas `MSFT_lod`).
- Herbe et semis autour de la caméra, recentrés au-delà de `viewer.grass.recenter_distance_m`, calculés dans un fil ; densité
  tirée du couvert de la cellule et des semis du bloc ; plafond d'instances dit à l'écran quand il tronque.
- Semis dessinés par un modèle générique : le bloc ne donne aucune largeur de houppier pour un semis ; le générique (1 m de haut,
  1 m de rayon) est mis à l'échelle (r, h, r) avec r = h x `viewer.seedlings.generic_radius_over_height` (0,25 : valeur
  d'illustration **sans source**, provisoire) et l'écran le dit (« semis génériques : largeur non connue, rayon = 0,25 x la
  hauteur »). Un semis du générateur garde sa forme (échelle uniforme h / hauteur du modèle). Une essence à semis sans modèle
  `young` n'est pas dessinée : l'index (`notes`) et l'écran le disent.
- Bandeau : provisoire, semis non simulés, modèles génériques, stade de l'arbre, sol à 25 m.

## Tests

    godot --headless --path viewer-massif --import
    godot --headless --path viewer-massif -s addons/gut/gut_cmdln.gd -gdir=res://tests -gexit

Licences et provenances : `CREDITS.md`.
