# Mission 028 — assets-etat-initial

## Mission

**En une phrase (quoi, et pourquoi) :** Écrire le module `assets` (Python) pour l'état initial : à partir de trees_init/, params/allometry.parquet, vegetation_map et des sorties de prepare, produire des modèles glTF génériques par groupe d'essences (feuillu, résineux), une tuile 3D Tiles 1.1 de l'année de départ avec instanciation (`EXT_mesh_gpu_instancing`), les fiches de cellule `web/cells/<tuile>.json` et les rasters web en COG, aux contrats, pour que la vue iTowns montre l'état initial avant la simulation (décision de Pascal du 25/11/2026).

**Redite par l'agent :** _à compléter par l'agent avant d'agir._

## Les trois questions

| Question | Réponse | Conséquence |
|---|---|---|
| Redire la mission ? | oui | |
| Sait-il faire ? | oui : spec §2, §9, ADR 0002, docs/referentiels/itowns-instancing.md (contenu en .gltf, pas .glb, à cause du gestionnaire d'iTowns) | |
| A-t-il les moyens ? | oui : Python 3.13, numpy, pyarrow, schémas 3D Tiles 1.1 vendus dans contracts/json/vendor, contrats cell_sheet et tileset | |

**Temps de la main :** donner. **Degré de la main :** le chef tranche (orchestrateur, par délégation de Pascal).

## Ma réponse d'abord

_Rempli par Pascal seul._

## L'Homme

- **Agent :** `dev` — **Modèle :** sonnet
- **Ce qui ne lui est pas demandé :** la simulation (M3) ; les arbres du générateur (M6) ; le volume et le carbone (post, après M3) : la fiche les laisse vides et le dit.

## Harnais

- **Peut (périmètre) :** `python/sylvigenese/assets.py` et un sous-paquet `python/sylvigenese/assets_lib/` si utile, `python/tests/test_assets*.py`, `contracts/json/cell_sheet.schema.json` et les contrats `assets.*` de `contracts/catalog.yml` (avec leurs cas dans `contracts/tests/`), la cible `assets` du Makefile.
- **Câblé :** pas de `main`, pas de « terminé » sans tests verts, journal en ajout seul ; aucune commande git qui écrit (l'orchestrateur commite).
- **Ne doit pas :** importer le code d'un autre module ; dessiner une essence précise (modèles génériques par groupe, marqués génériques) ; écrire un .glb comme contenu de tuile (référentiel iTowns, point A).
- **Sources autorisées :** docs/spec.md §1, §2, §9, §10 ; docs/adr/0002 ; docs/referentiels/itowns-instancing.md ; contracts/json/ (tileset, cell_sheet, vendor) ; contracts/tables/prepare/trees_init.schema.json ; contracts/species.csv (groupe).

## Journal

- **Ce que l'agent inscrit :** une ligne par rendu et par aller-retour, proposée à l'orchestrateur.

## Valeur provisoire (chiffre, réglage)

- formes des modèles génériques (hauteur et houppier proportionnels à h et crown_area de l'arbre) : provisoires, remplacées en M6 par les arbres du générateur.

## Dépend de / rouge attendu jusqu'à

- aucune mission en cours ; précède 029 (vue) ; 030 (tests) l'accompagne.

## Tests

- tileset et contenu conformes (validateur et schémas 3D Tiles 1.1) ; nombre d'instances = nombre d'arbres de trees_init ; positions en EPSG:2154 converties correctement vers le repère des tuiles (test sur un arbre de coordonnées connues) ; fiches de cellule conformes ; COG conformes au profil.

## Terrain

- **Échantillon que Pascal vérifiera :** `tiles/<année>/tileset.json` ouvert dans la vue (029) ; une fiche de cellule lue à la main.

## Qui veille, qui tranche

- **Relecteur :** `relecteur`, puis Claude par délégation (validation du jalon et fusion déléguées le 25/11/2026). **Arrêt :** 3 allers-retours. **Qui tranche :** Claude par délégation, Pascal peut défaire.

## Comment saura-t-on que ça marche ?

`make assets ZONE=zone_fictive` écrit une tuile de 14 080 instances, des fiches et des COG conformes, rejouables à l'identique.
