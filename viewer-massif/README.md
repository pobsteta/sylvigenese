# Nemeton 3D : exemple fictif (Godot 4)

Du massif à la petite plante dans un seul moteur. Tout est généré par code, aucune donnée réelle.

## Lancer
Ouvrir le dossier dans Godot 4.3 ou plus récent (testé en 4.5), puis F5.

- Molette : zoom continu de 7 km à 1,2 m
- Clic droit : tourner. Clic gauche ou flèches : se déplacer
- Curseur « Année » et bouton « Lecture » : croissance de 0 à 200 ans

## Niveaux d'échelle
| Distance | Ce qui est affiché |
|---|---|
| > 3 km | carte des types de station (F x R) |
| 3 km à 150 m | peuplement, un arbre = une instance MultiMesh |
| < 150 m | strate herbacée générée par dalles de 10 m autour du point visé |

## Où brancher les vraies données
| Fichier | Fictif ici | À remplacer par |
|---|---|---|
| `scripts/station.gd` | relief et gradients F, R, T en bruit | MNT LiDAR HD, rasters sylvostation |
| `data/essences.json` | optimums et tolérances inventés | valeurs Ellenberg / EIVE, typopeuplement |
| `scripts/forest.gd` | semis aléatoire, croissance Chapman-Richards dans le shader | arbres lidR, trajectoires GAMA |
| `scripts/herbs.gd` | lumière au sol déduite du couvert | relevés, indicateurs nemeton |

`scripts/biome.gd` contient la règle de biome : produit de réponses gaussiennes autour des optimums.

Captures automatiques : `godot --path . -- --shots` (images dans `user://`).
