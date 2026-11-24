# RAF20 : disponibilité de la grille `fr_ign_RAF20.tif` derrière le réseau de la session (mission 016)

- **Propriétaire :** Pascal
- **Date de consultation :** 2026-11-24
- **Mission redite :** dire si la grille RAF20 est joignable depuis data.geopf.fr ou cdn.proj.org depuis cette session, sans deviner ce qui est bloqué.
- **Décision éclairée :** spec §12 (« Disponibilité de la grille RAF20 ») : peut-on convertir des altitudes IGN69 en hauteurs ellipsoïdales (et inversement) dans la chaîne rejouable, et où la grille sera-t-elle prise.

## Résultats (URL réellement consultées)

| Site / URL | Résultat | Lecture |
|---|---|---|
| https://cdn.proj.org/fr_ign_RAF20.tif | erreur `getaddrinfo ENOTFOUND cdn.proj.org` | **bloqué** : l'hôte ne se résout pas dans cette session (hors des domaines autorisés). La grille n'a **pas** pu être testée sur ce site. |
| https://cdn.proj.org/ | même erreur | idem. cdn.proj.org doit être autorisé dans les réglages réseau de la session pour tester. |
| https://geodesie.ign.fr/index.php?page=grilles | `ENOTFOUND` | **bloqué** : c'est la source primaire nommée par PROJ-data ; non lue. |
| https://data.geopf.fr/ | HTTP 404 | **joignable** (le serveur répond), pas de page à la racine |
| https://data.geopf.fr/telechargement | HTTP 405 | joignable, méthode refusée |
| https://data.geopf.fr/telechargement/capabilities (pages 1 à 13) | lu | **joignable** ; catalogue de 122 entrées (10 par page ; 2 sur la page 13). Titres des 13 pages relus ; **aucune entrée RAF, quasi-géoïde ou grille de conversion**. Seule entrée proche : « DONNÉES DE GÉODÉSIE ET NIVELLEMENT » (ressource `https://data.geopf.fr/telechargement/resource/GEODESIE`, Shapefile, EPSG:4326, édition du 2026-10-02 : points géodésiques et repères de nivellement, **pas** une grille). « Archive -- BDALTI ELL » parle de hauteur ellipsoïdale, c'est un MNT. |
| https://github.com/OSGeo/PROJ-data/tree/master/fr_ign (et `fr_ign_README.txt`) | lu | **joignable** ; voir plus bas |

**Conclusion (limitée à ce qui a été vu) :**
1. **data.geopf.fr est joignable, mais son catalogue de téléchargement ne propose pas RAF20** (122 entrées, 13 pages, aucune ne la nomme). Je n'ai pas exploré d'autres services de data.geopf.fr (WMTS, WFS, `/altimetrie`, etc.) ni chaque fiche de ressource : « absente du catalogue de téléchargement » ne veut pas dire « absente de data.geopf.fr ».
2. **cdn.proj.org est bloqué** ici : disponibilité de `fr_ign_RAF20.tif` à cette adresse **non vérifiable** dans cette session.
3. **Autre source joignable :** le dépôt PROJ-data sur GitHub contient bien `fr_ign/fr_ign_RAF20.tif` (liste du répertoire lue ; chemin `https://github.com/OSGeo/PROJ-data/blob/master/fr_ign/fr_ign_RAF20.tif`). Je n'ai **pas** téléchargé le fichier : je ne peux donc pas dire son poids, son CRS ni sa somme de contrôle.

## Ce que dit la source sur la grille

- Description (page du répertoire, fiche `fr_ign_RAF20.tif`) : « Continental France, NGF-IGN 1969 to RGF93 (ETRS89), 2021 v2b version » ; format « GeoTIFF converted from GTX » ; convertisseur `build_french_vgrids.sh` ; source IGN (lien geodesie.ign.fr, bloqué) ; **licence ouverte v2.0 (Etalab)** (`fr_ign_README.txt`, groupe « French vertical grids », sans date propre).
- Définition EPSG (résultats de recherche, https://epsg.io/9876) : modèle de géoïde `fr_ign_RAF20.tif`, remplace RAF18b ; l'autre définition (https://epsg.io/9877) cite `RAF20.tac`. Non relu en détail : la précision (1 cm d'écart type sur environ 6800 points) vient d'un résultat de recherche.
- Emprise (isgeoid.polimi.it, résultat de recherche) : latitude 42° à 51,5°, longitude −5,5° à 8,5°, pas de 1,5' en latitude et 2' en longitude.
- Présentation IGN de 2023 (https://cnig.gouv.fr/IMG/pdf/20230323_geopos_matin_-_ogce-v1-1.pdf, résultat de recherche, non ouverte) : incompatibilité des altitudes NGF-IGN69 publiées avec (RGF93 + RAF20) ; à ne pas oublier avant d'ajouter une hauteur ellipsoïdale à un MNT.

## Écarts relevés

- Deux noms de fichier pour RAF20 selon l'EPSG : `fr_ign_RAF20.tif` (EPSG:9876, format GTG de PROJ) et `RAF20.tac` (EPSG:9877). Ce sont deux conditionnements de la même grille ; seul le premier a été vu dans un dépôt.
- La mission suppose que la grille soit chez data.geopf.fr ou cdn.proj.org ; la preuve n'existe pour aucun des deux ici.

## Limites

- Les contenus de GitHub et de recherche ont été lus par un outil qui résume la page, sans accès aux octets.
- Aucun téléchargement de la grille ; aucune lecture de ses métadonnées.
