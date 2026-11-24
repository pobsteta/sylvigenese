# Critique du brief par le `contradicteur` (24/11/2026), et arbitrages

> Critique rendue le 24/11/2026 sur `docs/BRIEF.md`. Les arbitrages ont été rendus le même
> jour par Claude (orchestrateur), **par délégation de Pascal** (`pilotage/equipe.md`), et sont
> inscrits au journal. Pascal peut défaire chacun d'eux.

**Question de contrôle du contradicteur.** Quel problème résout-on, et pour qui : montrer aux
utilisateurs de nemeton un futur chiffré de leurs peuplements, ou remplacer un outil de rendu
à 100 € par an ?

## Bloquant

| N° | Objection (résumé) | Arbitrage (par délégation) |
|---|---|---|
| B1 | « nemeton, entrée principale » n'est dans aucun contrat. L'état initial a trois sources concurrentes : lidR, le biome et nemeton. | Mission 008 : décrire, d'après leurs dépôts, les sorties réelles de nemeton, sylvostation, typopeuplement et tarif-nemeton. Ajouter au §4 un bloc « Entrées externes » avec un schéma pour chacun. Règle de priorité pour l'état initial : nemeton, puis le MNH pour `h`, puis le biome seulement pour combler, chaque comblement étant signalé. |
| B2 | Le MNH ne donne ni l'essence ni le `d130`. Les arbres dominés manquent. | `trees_init.parquet` porte `species_source` et `d130_source`. L'essence vient de nemeton, sinon elle est signalée. En v1, le niveau massif est déclaré « arbres détectés seulement ». Les arbres dominés relèvent des cohortes de la cellule, et le rapport le signale. |
| B3 | L'ordre des jalons ne tient pas : M4 a besoin d'`assets`, et M3 n'a pas de recrutement. | M3 utilise le recrutement IFN direct (`params/recruitment.parquet`), que M5 remplace en le calant. M4 inclut un `assets` minimal (glTF génériques à l'échelle de `h` et `cw`). M6 se limite au générateur et à `viewer-massif`. |
| B4 | Les critères d'acceptation ne sont pas mesurables, et ceux de M3 sont biaisés par l'absence de gestion. | Critères chiffrés dans `docs/spec.md`. M2 : validation croisée par blocs, comparée à un modèle nul. M3 : validation à 5 ans sur les placettes revisitées, et plausibilité à 100 ans entre les quantiles 5 et 95 % de l'IFN. M4 : images par seconde mesurées par script. M5 : recrutement dans l'intervalle de confiance IFN sur 10 ans. |
| B5 | Les agents seuls ne peuvent pas accepter la v1 : données, réseau, PC et Godot manquent. | Chaque jalon est découpé en « a » (code et tests sur jeu fictif, par les agents) et « b » (acceptation sur données réelles, avec Pascal). La v1 livrée par délégation est M0 et M1a à M6a. |
| B6 | Le modèle de hauteur est mal posé : la fertilité n'est pas une asymptote, H0 n'est pas défini, les dates de vol varient. | Dans la spec : sens de `site_potential` (à lire dans typopeuplement et sylvostation, mission 008), règle de calcul de H0 par cellule, contrat `chm_date`, accroissement nul au-dessus du plafond avec une ligne de rapport, courbe `provisoire: true` affichée comme telle. |

## Important

| N° | Objection (résumé) | Arbitrage |
|---|---|---|
| I1 | NDunes 3D est un éditeur de paysages, pas un simulateur. Son remplacement est un bénéfice, pas le problème, et le coût réel est le temps de Pascal. | La ligne « coût complet » est réécrite : licence 100 €/an (source : Pascal), temps passé aujourd'hui « inconnu », aucune trajectoire chiffrée possible aujourd'hui. Le remplacement de la part « donner à voir » de NDunes passe dans les bénéfices. |
| I2 | Sans gestion, la v1 ne sert pas les aménagistes. | La valeur sacrifiée est écrite : la v1 ne sert pas une décision d'aménagement, elle montre une évolution libre (`management: none`). Cela suit le hors-périmètre retenu par Pascal (sylviculture exclue). |
| I3 | `provisoire: true` peut tromper. | Le statut provisoire est propagé jusqu'à `sim/summary.parquet`, aux tuiles et aux deux vues (mention visible, part des paramètres provisoires). |
| I4 | Les variables diffèrent entre l'ajustement et la simulation. | Même définition des variables dans les deux. Voisinage de concurrence : disque de même surface que la placette IFN (à sourcer, mission 008). Raster fin : toute résolution inférieure à 1 km. |
| I5 | Des nomenclatures sont réinventées. | Essences en code `espar` de l'IFN et toutes les plantes en CD_REF TAXREF, avec la version figée. Valeurs indicatrices EIVE 1.0, tolérance à l'ombre de Niinemets et Valladares 2006. « Biome » est renommé `vegetation_type` dans les contrats ; le mot reste dans le texte. Les stades suivent une classification IFN. La forêt suit la définition de l'IFN. |
| I6 | Les versions et les repères ne sont pas fixés pour iTowns et Godot. | 3D Tiles 1.1 avec glTF, essai au début de M4, repli i3dm. CRS vertical NGF-IGN69, converti dans `assets` seulement. Un fichier glb par niveau de détail. `viewer-massif` lit un contrat préparé par `assets` (blocs, origine locale), pas le parquet. |
| I7 | Côté Rust, le profil de fichiers et des paramètres manquent. | Profil GeoTIFF fermé (tuilé, Deflate ou sans compression, Float32 ou UInt16, nodata explicite, aligné sur `grid.tif`). Séparation `station_gradients.tif` / `station_type.tif`. `site_potential.csv`. `sim/trees/year=AAAA/`. `params/allometry.parquet` et `params/tarif.parquet`, appliqués en post-traitement par un module dédié. `schema_version` et unités partout. Schémas en Frictionless Table Schema. |
| I8 | La grille, la zone tampon et les alluvions ne sont pas réglées. | Grille unique à 25 m, massif compris. Zone tampon de la largeur du noyau : ses cellules sont sources de graines seulement, avec un bord absorbant. En v1, les alluvions sont rattachées à la SER sous-jacente, avec un drapeau. |
| I9 | MARGOT (IGN) manque. | MARGOT est ajouté aux références de validation de M5. |

## Mineur

Tous les points m1 à m9 sont retenus :
- m1 : MNH plutôt que MNT au §1, signalement des trous ZICAD ;
- m2 : la vue web à l'échelle France reste hors v1 ; seuls le massif et la SER sont en v1 ;
- m3 : `c13` et documentation IFN citée ;
- m4 : EMERGE cité ;
- m5 : RReShar cité avec ses auteurs ;
- m6 : modèles d'architecture cités par essence ;
- m7 : point de départ du rejouable en 30 min ;
- m8 : attribution des données ;
- m9 : durée de l'intégration continue chiffrée à M0.

## Sources

Les sources de chaque point sont celles du rendu du contradicteur, résumé au journal du
24/11/2026 : BRIEF, ADR 0001 et sa critique, référentiels du dépôt, Bontemps et Duplat (AGRIS),
INRAE hal-02590355, MNH LiDAR HD (data.gouv.fr), 3DVF et CGPress (NDunes), TAXREF (MNHN),
EIVE 1.0 (doi:10.3897/VCS.98324), Niinemets et Valladares 2006, spécification 3D Tiles
(CesiumGS), iTowns PR #2415, Godot PR #112866, crate `tiff`, rapport IGN-FCBA (MARGOT).
Kaartinen et al. 2012 et Roberts et al. 2017 sont cités de mémoire et n'ont pas été relus.
