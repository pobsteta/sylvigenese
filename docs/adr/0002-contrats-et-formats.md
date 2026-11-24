# ADR 0002 — contrats de fichiers et formats d'échange

- **Date :** 2026-11-24
- **Statut :** acceptée par délégation de Pascal (`pilotage/equipe.md`), après critique du
  `contradicteur`
- **Proposée par :** Claude (orchestrateur)
- **Tranchée par :** Claude (orchestrateur, par délégation de Pascal)

## La décision en une phrase

Les modules se parlent par des fichiers ouverts :
- GeoTIFF au profil fermé, en EPSG:2154 sur la grille de 25 m ;
- Parquet partitionné par année ;
- glTF 2.0 et 3D Tiles 1.1.

Chaque fichier est décrit par un schéma Frictionless versionné dans `contracts/`. Le détail est
dans `docs/spec.md` §2, §3 et §9.

## Contexte

Le BRIEF §0.2 impose des modules reliés par des fichiers. Deux critiques ont montré qu'il
manquait un profil de fichiers commun :
- la critique de l'ADR 0001 (point I3, GDAL inutile au moteur) ;
- la critique du brief (points I6 et I7).

La mission 008 a montré que les entrées réelles ont trois mailles différentes et plusieurs
nomenclatures.

**Options envisagées :**
- GeoPackage partout ;
- Zarr ;
- NetCDF ;
- un format maison ;
- GeoTIFF et Parquet avec un profil fermé (retenu) ;
- pour la 3D, i3dm et b3dm (dépréciés par 3D Tiles 1.1) ou glTF instancié (retenu, avec repli
  i3dm).

## Le crible FRANCE

| Lettre | Réponse | Ce que ça coûte | Prêts à payer ? |
|---|---|---|---|
| **F**rugale | Deux formats tabulaires et raster, déjà lus par R, Python et Rust | Un profil à faire respecter par les validateurs | oui |
| **R**esponsable | Chaque module valide ses sorties ; `prepare` valide les entrées externes | Un validateur par contrat | oui |
| **A**nticiper | Le `schema_version` permet de faire évoluer les contrats ; repli i3dm si l'instanciation glTF n'est pas prise en charge | Un essai au début de M4 | oui |
| **N**ovateur | Zarr et NetCDF ont été envisagés | — | — |
| **C**oût | Pas de GDAL dans le moteur Rust : moins de dépendances natives | Le profil GeoTIFF exclut certaines compressions (ZSTD, JPEG) | oui |
| **É**cologique | Formats ouverts, lisibles par QGIS, `sf`/`terra`, `pyarrow`, iTowns et Godot ; schémas Frictionless réutilisables | — | oui |

## Valeurs sacrifiées

- **La souplesse des entrées.** Tout est rééchantillonné sur une grille unique de 25 m, ce qui
  fait perdre la finesse des mailles de 20 m.
- **Une partie de la compression.** Deflate seulement.

## Sources

- `docs/spec.md` ;
- `docs/critique-brief-contradicteur.md` (I6, I7) ;
- `docs/adr/0001-critique-contradicteur.md` (I3) ;
- `docs/referentiels/entrees-externes.md` ;
- spécification 3D Tiles (CesiumGS) ;
- crate `tiff` (docs.rs).

## Question de contrôle

Cette décision tient-elle nos six valeurs, et que sommes-nous prêts à payer pour cela ?
