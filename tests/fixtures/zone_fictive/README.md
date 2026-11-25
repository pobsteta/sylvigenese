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
| `inputs/types.csv` | `inputs.station_types` | légende des codes de `station_type.tif`, colonnes de `types.csv` de sylvostation |
| `inputs/h_pot.tif` | `inputs.h_pot` | 26,6 m, 1 bande (plafond unique : pas de famille d'essences) |
| `inputs/fertilite.csv` | `inputs.fertilite` | 5 essences × 4 types, séparé par `;` |
| `inputs/nemeton_stands.gpkg` | `inputs.nemeton_stands` | 5 polygones, couche `stands` |
| `inputs/inventaire_video.gpkg` | `inputs.inventaire_video` | 3 placettes de 15 m dans S04 (code libre `chene_sessile`) |
| `inputs/lidar_tiles.gpkg` | `inputs.lidar_tiles` | 4 dalles de 500 m, deux dates de vol (2021-08-03, 2022-06-21) |
| `inputs/forest_mask.gpkg` | `inputs.forest_mask` | massif moins la trouée |
| `inputs/ser.gpkg` | `inputs.ser` | forme brute de l'IGN : `ser_code` seul ; `H10` sur deux polygones, `L3` (alluvions) sur un couloir de 100 m entre eux (3 polygones sans recouvrement) |
| `inputs/ifn/PLACETTE.csv`, `ARBRE.csv`, `FLORE.csv` | `inputs.ifn_*` | 120 placettes de 1re visite et 108 revisites 5 ans après ; `C13` et `IR5` en **mètres** comme l'export réel ; positions vraies dans le massif, coordonnées floutées (écart ≤ 700 m) ; voir « IFN fictif pour la dynamique » |
| `params/indicator_values.csv` | `params.indicator_values` | valeurs indicatrices (réaction, nutriments) de 17 des 18 taxons de `FLORE.csv` ; **synthétiques** (`synthetic = true`, `provisoire = true`), produites par le générateur ; `CD_REF` 125816 laissé sans valeur (cas du comptage de prepare) |
| `params/tarif.parquet`, `params/allometry.parquet` | `import_tarif.*` | format long, `provisoire: true` ; `allometry` porte les termes a, b et c (houppier), tous fictifs |

Les `CD_REF` de `FLORE.csv` sont de deux sortes (18 taxons, 4 à 8 par placette, 1re visite seule) :
les 8 des essences de `contracts/species.csv` (v18 alors que l'IFN réel est en v13), et 10 taxons du
sous-bois forestier, `CD_REF` réels de TAXREF v18 lus dans l'extrait `taxref_v18_extrait.csv` de
sylvostation : 100787 *Hedera helix*, 128345 *Vaccinium myrtillus*, 108361 *Mercurialis perennis*,
111859 *Oxalis acetosella*, 106863 *Luzula sylvatica*, 116265 *Pteridium aquilinum*, 82637 *Anemone
nemorosa*, 119097 *Rubus fruticosus*, 99488 *Galium odoratum*, 88905 *Carex sylvatica*. Les valeurs
indicatrices associées sont tirées au hasard (graine 42) : elles n'ont aucun sens écologique.

**Placettes IFN et station (mission 023, aller-retour 1).** La position vraie de chaque placette est
tirée dans le massif (marge de 20 m), puis floutée de 700 m au plus : le point flouté reste à moins de
700 m du raster `station_gradients.tif`, donc le disque de 700 m de chaque placette contient des mailles
de station et `prepare` renseigne `trophic`, `coarse_*_700m` et `ser_code` sur les 120 placettes.

## IFN fictif pour la dynamique (mission 023)

**Tout est synthétique et provisoire** (taux de mort, de coupe, croissances, recrues : inventés par
`tools/fixtures/make_zone_fictive.py`, `provisoire: true` de fait, sans gel, remplacés par l'IFN
réel en M2b). Aucun de ces nombres n'est écologique. Les noms de colonnes et les codes sont ceux de
`docs/referentiels/ifn-dynamique-colonnes.csv` ; les unités sont celles de l'export : `C13` et `IR5` en
mètres (bornes des cercles 0,235 / 0,705 / 1,175 m ; des arbres sont exactement à 0,705 et 1,175 m).

- **Deux visites, deux lignes.** Une placette de 1re visite (campagne 2015 à 2020, `VISITE` = 1,
  `DATEPOINT` dans la campagne) est revisitée à la campagne + 5 (`VISITE` = 2, même `IDP`, mêmes
  coordonnées floutées, `DATEPOINT` de 4,0 à 6,0 ans après). 108 placettes sur 120 sont revisitées ;
  12 (une sur dix) ne le sont pas. Flore : 1re visite seule.
- **Un arbre = (`IDP`, `A`)**, `A` de 1 à n sur la 1re visite ; les recrues portent les numéros suivants.
  Ligne de 1re visite : `VEGET` (0 vivant ; 5 mort sur pied ; `A` chablis vivant avant 2019, `1` depuis),
  `IR5` sur la moitié des vivants (5 cernes avant la visite), `VEGET5` vide. Ligne de 2e visite : `VEGET5`
  (codes de VEGET59, campagnes 2019 et après : 0 vivant, 6 et 7 coupé, 2 chablis mort, M mort sur pied,
  N non retrouvé, T cassé ou perdu après incident), `VEGET` vide, `HTOT` et `V` vides, `W` de l'export.
  **Hypothèses non vérifiées sur l'export réel (spec §6, vérification en M2b)** : le contenu d'une ligne de
  2e visite ; `C13` vide pour un arbre coupé (6, 7), non retrouvé (N) ou cassé (T) ; `VEGET5` = 0 pour une
  recrue ; `W` d'une recrue = poids du cercle de 6 m, ou vide sur 17 recrues (poids non documenté, à signaler).
- **Incidents** : 12 placettes (`NINCID` = 4, `INCID` = 2 en 1re visite) ont une mortalité triplée et des
  arbres cassés (T) ; 12 autres (`DEF5` = 2 en 2e visite) ont des coupes quintuplées. `PRELEV5` est vide
  partout (renseignée de 2010 à 2014 seulement dans l'export) ; `INSTP5` vaut 0.
- **IR5** : renseigné sur 1 054 lignes sur 2 286 (46 %), soit 1re visite et 2e visite, arbres vivants
  seulement, jamais sur un arbre coupé ou mort. Valeurs en m (de 0,005 à 0,033 pour 5 cernes).

Effectifs (les 5 essences, sur les 108 placettes revisitées ; entre parenthèses, hors placettes à
incident ou défrichement, c'est-à-dire ce que `dynamics` garde) :

| Essence | 1re visite | à risque (`VEGET` = 0, revus) | morts (M) | coupés (6, 7) | non retrouvés (N) | perdus (T) | recrues | `IR5` (toutes lignes) |
|---|---|---|---|---|---|---|---|---|
| 09 | 249 | 212 (139) | 25 (11) | 19 (9) | 2 (2) | 0 (0) | 37 (25) | 231 |
| 61 | 234 | 201 (165) | 29 (20) | 9 (6) | 4 (4) | 0 (0) | 36 (32) | 218 |
| 62 | 172 | 155 (112) | 32 (15) | 7 (2) | 5 (4) | 4 (0) | 35 (24) | 174 |
| 03 | 200 | 144 (119) | 21 (16) | 8 (4) | 1 (0) | 1 (0) | 23 (19) | 185 |
| 64 | 265 | 220 (175) | 32 (19) | 13 (10) | 3 (2) | 2 (0) | 37 (30) | 246 |

Tous les arbres à risque ne sont pas ceux de la 1re visite : 66 arbres vus morts ou chablis à la
1re visite (`VEGET` différent de 0) sont revus et doivent être écartés de la population à risque.


## Marqueur de zone

`zone.yml` (contrat `zone_marker`, `fictive: true` et sa raison) dit que le jeu est fictif. Les
copies de la zone en héritent. `assets` s'en sert : seule une zone marquée fictive peut se passer
de la grille RAF20 (ondulation prise égale à 0, annoncée et écrite dans les extras) ; une zone
réelle sans marqueur et sans RAF20 est une erreur (spec §9).
