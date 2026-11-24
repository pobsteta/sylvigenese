# Moteurs existants : TreeMig, LANDIS-II, iLand

- **Source :** pages GitHub et fichiers bruts du dépôt iLand et des dépôts LANDIS-II Foundation (lus), résumés de recherche web (pour TreeMig et pour les publications). Détail, ligne par ligne, dans `moteurs-existants.csv`.
- **Date de consultation :** 2026-11-24
- **Propriétaire :** Pascal
- **Produit par :** agent `acquereur`, mission 001 (décision éclairée : ADR 0001, option G)
- **Statut :** collecte partielle. Voir « Limites » : plusieurs sites sont bloqués par le réseau de la session.

## Redite de la mission

Établir, sources à l'appui, ce que TreeMig, LANDIS-II et iLand permettent de réutiliser pour sylvigenese, afin que Pascal décide de l'option G de l'ADR 0001 (réutiliser ou adapter un moteur, le garder comme référence de validation, ou l'écarter).

## Limites de la collecte (à lire d'abord)

- **Lus directement :** `github.com` (pages de dépôt, versions, étiquettes, arborescences) et `raw.githubusercontent.com` (fichiers de documentation du dépôt iLand, README de Density Succession).
- **Non lus, hôte bloqué (« ENOTFOUND ») :** treemig.wsl.ch, www.wsl.ch, gitlabext.wsl.ch, www.envidat.ch, b2find.eudat.eu, www.landis-ii.org, landis-ii-foundation.github.io, iland-model.org, research.fs.usda.gov, andrewsforest.oregonstate.edu, mediatum.ub.tum.de, portal.fis.tum.de, pdxscholar.library.pdx.edu, ideas.repec.org, gmd.copernicus.org, pmc.ncbi.nlm.nih.gov, www.frontiersin.org, zenodo.org, hal.inrae.fr. L'interface de programmation de GitHub (`api.github.com`) a répondu 403.
- **Conséquence pour TreeMig :** tout ce qui le concerne vient de résumés de la recherche web, sans ouverture de la page ni du dépôt. **Sa licence n'a pas été lue dans le dépôt** (exigence de la mission non remplie).
- **Conséquence pour les chiffres de performance :** aucun temps de calcul, aucune mémoire ni machine n'a pu être obtenu pour les trois moteurs.
- Les dates de dernier commit n'ont pu être lues pour aucun dépôt.

## Tableau comparatif court

| Point | iLand | LANDIS-II (avec Density Succession) | TreeMig |
|---|---|---|---|
| 1. Licence | GPL-3.0, lue dans `COPYING` | Apache 2.0, lue dans les dépôts ; compatibilité GPL-3 non vérifiée ici | CC-BY-NC-SA 4.0 pour le noyau « sur demande » (résumé de recherche) ; **non lue dans le dépôt** ; licence du paquet R non remplie |
| 2. Langage, activité | C++ et Qt ; v2.2 du 28 juil. 2026 ; 1 244 commits | C# / .NET (déduit) ; noyau v8 sans version GitHub ; Density Succession v2.0-beta du 9 mai 2025 | Fortran et paquet R 0.3.1 ; dépôt GitLab ; auteur principal retraité ; activité non vue |
| 3. Niveau | arbre à arbre ; jeunes plants (< 4 m) en cohortes | cohortes (densité de tiges et dbh par cohorte d'âge) par cellule | classes de hauteur par essence et par cellule (25 m à 1 km) |
| 4. Processus spatiaux | dispersion exponentielle sur grille de 20 m, lumière par arbre (10 m), compétition | dispersion par distances efficace et maximale ; lumière non documentée dans ce qui a été lu | dispersion courte et longue distance, FFT optionnelle, lumière par classe de hauteur |
| 5. Échelle, performance | « 10,000+ ha » (README) ; temps non obtenus | aucun chiffre pour LANDIS-II ; LANDIS PRO : jusqu'à 100 millions de cellules de 0,09 ha ; temps non obtenus | Suisse à 200 m ; temps non obtenus |
| 6. Entrées, sorties | ESRI ASCII, SQLite, texte ; ni GeoTIFF, ni parquet, ni EPSG:2154 vus | non vérifié | non vérifié (texte et paquet R) |
| 7. Paramétrage | équations propres (3PG) ; pas de plafond de hauteur de station vu ; modifier le C++ | extension C# possible ; modèle de diamètre « défini par l'utilisateur » ; plafond non vu | équations propres ; modification du Fortran « difficile et sujette aux erreurs » (WSL) |
| 8. Reproductibilité | mode console ; graine **inopérante en multifil** | non vérifié | non vérifié |
| 9. Usage en France | aucun trouvé (Alpes seulement) | aucun trouvé | chêne vert dans l'ouest de la France (Delzon et al. 2013, via résumé WSL) |

## Écarts relevés entre sources

- **Dernière version d'iLand :** v2.2 du 28 juil. 2026 (GitHub) contre « 0.6.9, 2011 » (page de wiki périmée). La page de wiki est écartée.
- **Échelle d'iLand :** 10^4 ha (README) contre « 105 hectares », lu 10^5 ha (résumé de recherche d'un article, non confirmé).
- **LANDIS PRO :** un résumé dit « plus de 10^8 ha », mais les essais décrits vont jusqu'à 10^8 cellules de 0,09 ha, soit environ 9 millions d'ha (calcul). Coquille probable.
- **Density Succession :** la page de documentation dit « v1.0 beta » sur LANDIS-II v7.0 ; l'étiquette la plus récente est v2.0-beta (mai 2025). La compatibilité avec le noyau v8 n'est pas établie.
- **Noyau de dispersion de LANDIS-II :** double exponentielle (page iLand) contre noyau de Ward (documentation LandR). Aucune lecture de la documentation LANDIS-II.
- **Vocabulaire :** l'ADR et sa critique écrivent « cohortes par cellule » pour TreeMig ; les sources parlent de **classes de hauteur**.
- **Licence du paquet R de TreeMig :** champ non rempli dans le manuel, contre « libre d'usage » sur le site.

## Avis (non sourcé comme fait : à trancher par Pascal)

> Ce qui suit est un avis de l'`acquereur`. Il tire les conséquences des faits ci-dessus ; il ne remplace pas la décision de Pascal.

1. **Aucun des trois moteurs n'apparaît, sur ces faits, comme réutilisable tel quel pour `simulate`.** Aucun n'accepte, d'après ce qui a été lu, nos modèles IFN d'accroissement, de mortalité et de recrutement, ni une hauteur bornée par `site_potential.tif` (BRIEF §6). Chacun impose ses équations ; pour les utiliser il faudrait modifier le code (C++, C#, Fortran).
2. **La donnée qui décide manque pour les trois : le temps et la mémoire à l'échelle d'une SER.** Sans elle, l'option « réutiliser » ne peut être ni retenue ni écartée sur le critère de rapidité.
3. **iLand** est le seul dont la licence (GPL-3) est identique à la nôtre, lue dans le dépôt, et il est actif (v2.2, juillet 2026). Il couvre notre niveau massif (arbre à arbre, lumière, dispersion). Son échelle publiée (10^4 à 10^5 ha) reste inférieure à une SER moyenne (environ 640 000 ha, ADR), et sa graine ne fonctionne pas en multifil. Pour le massif, il se prête à une **référence de validation** de l'ordre de grandeur plutôt qu'à un remplacement.
4. **TreeMig** est le plus proche du niveau SER dans sa conception (distribution par cellule, dispersion avec FFT, grilles de 25 m à 1 km, Suisse à 200 m). Mais sa licence annoncée (NC-SA, sur demande) ne paraît pas conciliable avec la GPL-3 (la clause « non commercial » ; **à vérifier sur le texte**, non consulté ici), et WSL déconseille de modifier le code. Il se prête surtout à une **référence de conception et de validation** du niveau SER.
5. **LANDIS-II** (Apache 2.0) offre la structure « cohortes par cellule » avec densité de tiges et dbh, et une architecture d'extensions. Il ajoute un troisième écosystème de langage (C# / .NET), et les faits manquent sur ses formats, sa vitesse et sa compatibilité avec le noyau v8. Il peut servir de **référence de validation** du niveau SER.
6. **En résumé de l'avis :** les faits soutiennent « référence de validation » plus que « réutiliser ou adapter », pour chacun. Une vérification courte (points au sol 1 et 2) pourrait changer cet avis pour TreeMig ou iLand.

## Les trois points au sol (à vérifier par Pascal)

1. **La licence de TreeMig, qui conditionne toute réutilisation.** Ouvrir https://treemig.wsl.ch/en/core-model/ et le dépôt GitLab du paquet R (fichier `DESCRIPTION`, fichier de licence) ; ou demander à WSL. Nous avons seulement un résumé « CC-BY-NC-SA 4.0, sur demande ». Décision sensible : une licence « non commerciale » exclurait la réutilisation sous GPL-3.
2. **La performance d'iLand à grande échelle.** Lire la section sur l'évolutivité de Seidl et al. 2012 (Ecological Modelling 231:87-100) et le résumé de Rammer et al. 2024 (10^4 ou 10^5 ha, temps, machine), ou interroger l'équipe iLand (Discord, lié au README). C'est le chiffre qui dit si le moteur peut approcher une SER.
3. **L'état réel de Density Succession.** Vérifier que l'extension (v2.0-beta, mai 2025) tourne sur le noyau LANDIS-II v8, ce qu'elle lit et écrit, et sa vitesse. Faire préciser la part d'héritage de PnET-Succession relevée dans son code source (fichiers `Hydrology.cs`, `ClimateRegionPnETVariables.cs`). Essai d'installation ou question à Jacob Fraser (contact cité par la page de l'extension).

## Liste de contrôle passée

1. **Sources, pages, version, date : partiellement cochée.** Chaque ligne du CSV porte sa date (2026-11-24) et ses URL. Les URL réellement ouvertes et les URL seulement vues dans des résultats de recherche sont distinguées dans le CSV (« résumé de recherche »). Pas de numéro de ligne : les pages GitHub et fichiers de documentation sont cités par adresse. Les versions sont datées quand elles existent (iLand v2.2, Core-Model 6.2.1, Density Succession v2.0-beta, paquet R TreeMig 0.3.1). Non cochée : toute valeur de TreeMig et les chiffres d'échelle venant de résumés, non ouverts à la source.
2. **Décomptes : cochée.** 3 moteurs × 9 points = 27 lignes dans le CSV ; les cases non établies sont écrites « non vérifié », pas omises.
3. **Termes exacts, limites dites : cochée**, sous réserve des écarts de vocabulaire notés (« classes de hauteur » et non « cohortes » pour TreeMig).
4. **Statut dit tel qu'il est : cochée.** Ce qui est lu, ce qui vient de résumés, et ce qui manque sont séparés ci-dessus. Non cochés : licence de TreeMig dans son dépôt ; toute performance ; formats d'entrée et de sortie de LANDIS-II et de TreeMig ; reproductibilité de LANDIS-II et de TreeMig ; compatibilité Apache 2.0 et GPL-3 (connaissance générale, non consultée).

## Question de contrôle

*Quelle décision cette donnée va-t-elle éclairer ?* L'option G de l'ADR 0001 : réutiliser ou adapter TreeMig, LANDIS-II ou iLand pour `simulate`, les garder comme références de validation, ou les écarter.

## Ligne de journal proposée

`2026-11-24 | acquereur | mission 001 : moteurs existants (iLand GPL-3, LANDIS-II Apache 2.0, TreeMig CC-BY-NC-SA annoncée, non lue) consignés dans docs/referentiels/moteurs-existants.{md,csv} ; aucune performance à l'échelle SER obtenue, plusieurs hôtes bloqués ; décision sur l'option G à Pascal.`
