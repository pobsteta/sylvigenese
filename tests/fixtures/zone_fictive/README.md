# Jeu d'essai fictif `zone_fictive`

> **TOUT EST SYNTHÉTIQUE.** Aucune valeur de ce dossier n'est écologique ni ne vient d'une
> source réelle : essences, hauteurs, densités, gradients, fertilités, coefficients de tarif et
> d'allométrie, placettes et arbres de l'IFN sont tirés d'un générateur à graine fixée. Ne rien
> en conclure sur une forêt réelle. Les paramètres sont marqués `provisoire: true`, avec
> `source = synthetique_jeu_fictif`.

Il a les formats, les noms de colonnes et les mailles des sources réelles (spec §3), pour que
les modules tournent sans données réelles. Il est produit, et rejoué au bit près, par
`tools/fixtures/make_zone_fictive.py` (graine 42) ; ne pas le modifier à la main.

```
python3 tools/fixtures/make_zone_fictive.py          # régénère ce dossier
contracts/validate --zone tests/fixtures/zone_fictive # code 0 attendu (entrées seulement)
python3 -m pytest tools/fixtures/tests
```

## Massif fictif

Carré de 1 000 m de côté, EPSG:2154 : coin sud-ouest (700 000 ; 6 500 000), coin nord-est
(701 000 ; 6 501 000). Taille provisoire. Rasters tous ancrés au coin nord-ouest.

| Zone (m locaux, x ; y) | Contenu |
|---|---|
| S01 (0-350 ; 0-500) | essence 09, 27 m, `source = inventaire` |
| S02 (0-350 ; 500-1000) | essence 61, 28 m, `inventaire` |
| S03 (350-650 ; 500-1000) | essence 62, 36 m : **au-dessus de `h_pot`** (cas pour `rapport_hauteur.html`) |
| S04 (650-1000 ; 0-500) | essence 03, 22 m, `source = synthetic_ml` (MNH déjà compté, spec §4.5) ; placettes vidéo |
| S05 (650-1000 ; 500-1000) | essence 64, 32 m, `inventaire` |
| (350-650 ; 0-500) | forêt **sans polygone nemeton** (arbres de 18 m) : cas « hors polygone » (spec §4.2) |
| (400-600 ; 100-300) | trouée non forestière : trou du masque forestier, MNH nul |

## Fichiers

| Fichier | Contrat | Maille ou contenu |
|---|---|---|
| `inputs/chm.tif` | `inputs.chm` | MNH 0,5 m, Float32, nodata -9999 |
| `inputs/dtm.tif` | `inputs.dtm` | MNT 25 m |
| `inputs/station_gradients.tif` | `inputs.station_gradients` | 20 m, 3 bandes `trophic`, `hydric`, `bioclim` |
| `inputs/station_type.tif` | `inputs.station_type` | 20 m, UInt16, nodata 65535, codes 1 à 4 |
| `inputs/types.csv` | (aucun contrat) | légende des codes de `station_type.tif`, colonnes de `types.csv` de sylvostation |
| `inputs/h_pot.tif` | `inputs.h_pot` | 26,6 m, 1 bande (plafond unique : pas de famille d'essences) |
| `inputs/fertilite.csv` | `inputs.fertilite` | 5 essences × 4 types, séparé par `;` |
| `inputs/nemeton_stands.gpkg` | `inputs.nemeton_stands` | 5 polygones, couche `stands` |
| `inputs/inventaire_video.gpkg` | `inputs.inventaire_video` | 3 placettes de 15 m dans S04 (code libre `chene_sessile`) |
| `inputs/lidar_tiles.gpkg` | `inputs.lidar_tiles` | 4 dalles de 500 m, deux dates de vol (2021-08-03, 2022-06-21) |
| `inputs/forest_mask.gpkg` | `inputs.forest_mask` | massif moins la trouée |
| `inputs/ser.gpkg` | `inputs.ser` | `ser_code = H10` partout ; `alluvium_code = L3` sur un couloir, NULL ailleurs (3 polygones sans recouvrement) |
| `inputs/ifn/PLACETTE.csv`, `ARBRE.csv`, `FLORE.csv` | `inputs.ifn_*` | 40 placettes ; `C13` en mm ; coordonnées floutées (écart ≤ 700 m) |
| `params/tarif.parquet`, `params/allometry.parquet` | `import_tarif.*` | format long, `provisoire: true` |

Les `CD_REF` de `FLORE.csv` sont ceux de `contracts/species.csv` (arbres), faute de table de
flore ; ils sont en v18 alors que l'IFN réel est en v13.
