# Régénération : ce que la littérature publie, essence par essence (mission 059, mission A du plan M5a)

- **Propriétaire :** Pascal
- **Date de consultation :** 2026-11-26
- **Produit par :** agent `acquereur`, mission 059 (`pilotage/missions/059-referentiel-regeneration.md`)
- **Mission redite :** relever, pour chaque essence de `contracts/species.csv` et pour sept grandeurs (dispersion, maturité, fécondité, tolérance à l'ombre, L d'Ellenberg, croissance et survie des semis sous couvert), ce que la littérature publie et où. Le but : que le contrat `params/regeneration` (mission 060) ne porte que des termes qui existent.
- **Décision éclairée :** les termes de `params/regeneration.parquet` (plan `docs/plans/m5a.md` §3), dans le cadre des réponses de Pascal du 26/11/2026 (journal l. 323-325) :
  - Q1 : passage calé sur le flux IFN, borné par le stock de semis ;
  - Q2 : stock initial « en régime » (flux IFN × temps de passage) ;
  - Q3 : survie par la seule lumière et la tolérance à l'ombre.
- **Fichier tabulaire :** `docs/referentiels/regeneration.csv`, 44 lignes, une par couple (grandeur, source), plus une ligne `absent` par grandeur pour les essences qu'aucune source ne nomme. Colonnes : `statut`, `valeur` et `lecture`, définies ci-dessous.
  - `statut` :
    - `publie` : la source nomme l'essence pour cette grandeur ;
    - `couverture_non_lue` : la source couvre beaucoup d'espèces, mais sa liste n'a pas été ouverte ;
    - `absent` : aucune source trouvée.
  - `valeur` : `non recopiée`, `non lue` ou `absent`. **Aucune valeur numérique n'est écrite**, car aucune page n'a été ouverte (voir plus bas).
  - `lecture` : `recherche web seule` (vu dans un résumé du moteur de recherche, page non ouverte, ce qui n'a pas valeur de lecture).

## 0. Seconde passe du 26/11/2026 (demandée par Pascal) : aucune table ouverte

- **Pourquoi :** Pascal a approuvé neuf hôtes publics (journal l. 332) pour que les tables soient lues.
- **Ce qui a été fait :** chaque hôte a été essayé deux fois, avec un délai entre les deux essais :
  - `esapubs.org` ;
  - `figshare.com` (et `wiley.figshare.com`, une fois) ;
  - `zenodo.org` ;
  - `treemig.wsl.ch` ;
  - `www.frontiersin.org` ;
  - `hal.inrae.fr` ;
  - `hal.science` ;
  - `www.ipcc-nggip.iges.or.jp` ;
  - `www.sci.muni.cz`.
- **Résultat :** les neuf refusent les deux fois, avec la même erreur de résolution de nom (« ENOTFOUND, hors des domaines autorisés de la session »). L'approbation n'est pas encore appliquée au réseau de cette session.
- **Conséquence :**
  - aucune ligne ne passe au statut `lu` ;
  - aucune valeur n'est écrite ;
  - l'appariement de `species.csv` aux listes des sources n'est pas fait ;
  - le tableau de couverture du §3 reste valable tel quel ;
  - le tableau 4.4 du GIEC 2006 (pour `post`) n'est pas lu non plus.
- **Seule information nouvelle**, tirée d'un résumé de recherche et non d'une page ouverte : **la licence de TreeMig n'est pas une seule licence.** D'après le résumé :
  - le code FORTRAN serait sous CC-BY-NC-SA 4.0 (page `treemig.wsl.ch/en/treemig-framework/`) ;
  - les données d'entrée seraient sous CC BY 4.0 (page `treemig.wsl.ch/en/details/`) ;
  - le paquet sur EnviDat serait sous CC-BY-SA ;
  - aucune licence propre aux fichiers de paramètres d'espèces n'apparaît.

  C'est un écart avec `moteurs-existants.md:25`, qui donnait CC-BY-NC-SA pour TreeMig en bloc. La question reste ouverte jusqu'à ce que la page soit lue (CSV, ligne D06).
- **Pages à ouvrir dès que le réseau suit**, dans l'ordre de valeur pour la décision :
  1. annexe A de Niinemets et Valladares 2006 (T01) ;
  2. `treemig.wsl.ch/en/details/` et `SpecParsMeanings.pdf` : licence, puis paramètres (D06, M01, F01, T02) ;
  3. le PDF de Lososová 2023 sur `www.sci.muni.cz` : tableau des classes (D01) ;
  4. le Data Sheet 1 sur Frontiers (D07, M02, T03) ;
  5. HAL : thèse de Gaudio et Amm 2012 (G05, D05) ;
  6. le tableau 4.4 du GIEC (pour `post`).

## 1. Limites de la collecte (à lire d'abord)

- **Hôtes bloqués dans cette session :**
  - `esapubs.org`, qui porte l'annexe A de Niinemets et Valladares 2006 ;
  - `figshare.com`, son miroir.

  Les deux échouent par « ENOTFOUND ». La consigne de l'outil est de ne plus essayer d'autre site après deux échecs : **aucune autre page n'a donc été ouverte.**
- **Déjà relevés comme bloqués le 24/11** (`moteurs-existants.md:16`), et non réessayés ici :
  - `zenodo.org` (Tichý 2023) ;
  - `treemig.wsl.ch` (paramètres de TreeMig) ;
  - `hal.inrae.fr` (thèse à l'origine de RReShar) ;
  - `www.landis-ii.org` ;
  - `www.frontiersin.org` (LANDIS-II en Sierra Nevada) ;
  - `pmc.ncbi.nlm.nih.gov`, `gmd.copernicus.org`.
- **Conséquence : aucune table de paramètres n'a été lue.** Tout ce qui suit vient des résumés de la recherche web. On sait quelles sources existent, ce qu'elles publient, et parfois quelles essences elles nomment. Ni les valeurs, ni la liste complète des essences de chaque source ne sont lues.
- **Dépôts non lus :**
  - `/home/user/tarif-nemeton`, dépôt privé, par l'interdit de la mission ;
  - `sylvostation` : je ne cite que ce que `ifn-dynamique.md` en a écrit.
- **Tichý 2023 n'est pas recopié, par règle.** Pascal a décidé le 25/11 que ses valeurs sont utilisées sans redistribution, lues hors dépôt par une clé `external.*` (journal l. 203).

## 2. Les sources au CQQCOQP

Le **Pourquoi** est le même pour toutes : choisir les termes et les sources de `params/regeneration`.

| Source (lignes du CSV) | Qui, dans quel but | Quoi | Comment | Où | Quand | Combien (précision, coût, licence) |
|---|---|---|---|---|---|---|
| **Niinemets et Valladares 2006** (T01) | écophysiologistes, pour comparer les tolérances | tolérance à l'ombre, à la sécheresse et à l'engorgement de 806 espèces ligneuses | synthèse de la littérature et d'avis d'experts sur une échelle commune ; pour l'Europe, fondée en partie sur des valeurs indicatrices de lumière (résumé) | hémisphère Nord tempéré | 2006 | une moyenne et un écart-type par espèce ; ESA, licence non lue ; **annexe non ouverte (hôtes bloqués)** |
| **Tichý et al. 2023** (L01) | phytosociologues, pour harmoniser les valeurs indicatrices européennes | L (lumière) et cinq autres valeurs, 8 908 espèces, dont 8 168 avec L | moyenne de 13 jeux régionaux de type Ellenberg | Europe, noms Euro+Med | v2.0 du 2022-11-07 (`ifn-dynamique.md:145`) | indice ordinal ; CC BY 4.0, avec une réserve CC BY-SA 2.0 sur Julve ; non redistribué (décision de Pascal) |
| **Lososová et al. 2023** (D01) | écologues, pour la biogéographie et les modèles de végétation | classe de distance de dispersion (7 classes) et mode de dispersion | règles : mode, diaspore, forme de vie, hauteur, masse des graines, habitat | Europe, 10 327 espèces | 2023 | une classe, pas un noyau propre à l'espèce ; article CC BY 4.0 ; licence des données non lue |
| **Vittoz et Engler 2007** (D02) | botanistes suisses, pour une typologie | distance à 50 % et à 99 % des graines par type | 80e centile des distances publiées par type | flore suisse, 1 262 espèces | 2007 | les distances varient d'un facteur 5 000 entre types et de moins de 50 au sein d'un type |
| **Bullock et al. 2017** (D03) | synthèse mondiale de noyaux | 168 noyaux ajustés, 144 espèces | 11 lois ajustées sur des données publiées | monde | 2017 | Dryad ; essences de `species.csv` non vérifiées |
| **Sagnard 2007, Amm 2012** (D04, D05) | généticiens et écologues (France), pour la recolonisation | distance médiane de dispersion du sapin et du hêtre | modélisation inverse sur pièges à graines ou sur semis | sud-est de la France (Mont Ventoux pour Amm) | 2007, 2012 | quelques peuplements ; Elsevier ou HAL |
| **TreeMig** (D06, M01, F01, T02, G06, S05) | WSL, pour la migration des essences à l'échelle du paysage | `alfa1`, `alfa2`, `dispFac`, `minmat` (hauteur), `maxseed`, paramètres de lumière des semis et des adultes | paramètres de modèle (Lischke et al. 2006 ; conifères revus d'après Rickebusch et al. 2007) | 30 essences d'Europe centrale | 2006, puis révisions | **liste et valeurs non lues** ; licence CC-BY-NC-SA annoncée, non lue (`moteurs-existants.md:25`) ; d'après la recherche du 26/11, elle viserait le code seul, et les données seraient sous CC BY 4.0 (voir §0) |
| **LANDIS-II, Sierra Nevada** (D07, M02, T03) | université de Grenade, pour caler PnET-Succession | dispersion efficace et maximale, maturité, tolérance (100-300) | TRY et littérature, puis calage sur la biomasse | Espagne méditerranéenne | 2021 | CC BY ; seules deux lignes vues (57A, 69JC) |
| **LANDIS-II, Roumanie** (D08, M03) | modélisateurs roumains (Fagaraş) | paramètres LANDIS-II (§2.4) | calage, non lu | Carpates | 2021 | MDPI, non ouvert |
| **4C** (T04, L02) | PIK Potsdam | tolérance en 5 classes, tirée d'Ellenberg 1986 | dérivation qualitative | Allemagne | projet de 1999 | trois essences ; non indépendant de Tichý |
| **Kunstler 2005, Petriţan 2007, Ameztegui et Coll 2011** (T06-T08, G01-G03, S01-S03) | écologues forestiers : coexistence et tolérance des jeunes arbres | croissance et mortalité des jeunes arbres selon la lumière | mesures de terrain le long d'un gradient de lumière | sud de la France ; Allemagne ; Pyrénées espagnoles | 2005-2011 | 2 ou 3 essences par article ; textes non ouverts |
| **SORTIE-ND Pyrénées** (G04, S04) | Ameztegui, Coll et Messier | paramètres de croissance et de mortalité juvéniles | modèle individuel calé sur le terrain | Pyrénées | 2015 | annexe non lue |
| **RReShar** (D09, G05) | Balandier et Gaudio (Irstea) | concurrence pour la lumière et l'eau entre strates ; croissance des semis de pin sylvestre | thèse et expériences en pépinière ; Beer-Lambert pour le sous-bois | chênaie-pinède, France | vers 2010-2019 | **aucune table de paramètres d'espèces trouvée** ; la classe « espèce » de Capsis doit fournir croissance et survie (page technique) |

**Une deuxième source qui se tromperait pour une autre raison :**

- **Tolérance à l'ombre.** Niinemets et Valladares (synthèse, en partie fondée sur des valeurs indicatrices) contre les mesures de croissance et de survie des jeunes arbres : Kunstler, Petriţan, Ameztegui. Les mesures se tromperaient autrement : un site, quelques années. TreeMig, 4C et Kulha ne sont **pas** indépendants : 4C vient d'Ellenberg, et Kulha reprend Niinemets.
- **L d'Ellenberg.** Aucune seconde source indépendante. Ellenberg 1986 (via 4C) est l'un des 13 jeux que Tichý harmonise (déjà relevé dans `ifn-dynamique.md:152`).
- **Dispersion.** Les classes à règles (Lososová, Vittoz) contre les noyaux mesurés (Sagnard, Amm). Une règle par trait se trompe autrement qu'une mesure sur un site.
- **Maturité, fécondité, croissance, survie.** Je n'ai pas trouvé de seconde source pour une même essence, sauf pour le hêtre : Kunstler et Petriţan pour la croissance et la survie.

## 3. Tableau de couverture (essence × grandeur)

Légende :
- **S** : sourcé, une source nomme l'essence (résumé seul, page non ouverte) ;
- **L** : une source à large couverture existe, mais sa liste n'a pas été lue, donc à lire ;
- **—** : absent.

Les numéros renvoient aux lignes du CSV.

| espar | Essence | Dispersion | Maturité | Fécondité | Tolérance | L Ellenberg | Croissance semis | Survie semis |
|---|---|---|---|---|---|---|---|---|
| 09 | *Fagus sylvatica* | S (D04) + L | L (M01) | S* (F02, F03) | S (T04, T06, T07) + L | S (L02) + L | S (G01, G02) | S (S01, S02) |
| 61 | *Abies alba* | S (D04, D05) + L | S (M04) + L | L (F01) | S (T08) + L | L | S (G03) | S (S03) |
| 52 | *Pinus sylvestris* | L | L | L | S (T04, T08) + L | S (L02) + L | S (G03, G05) | S (S03) |
| 58 | *Pinus mugo* subsp. *uncinata* | L | L | L | S (T08) + L | L | S (G03) | S (S03) |
| 62 | *Picea abies* | L | L | S* (F02) | S (T04) + L | S (L02) + L | — | — |
| 05 | *Quercus pubescens* | L | L | L | S (T07) + L | L | S (G01) | S (S01) |
| 15S | *Acer pseudoplatanus* | L | L | L | S (T06) + L | L | S (G02) | S (S02) |
| 17C | *Fraxinus excelsior* | L | L | L | S (T06) + L | L | S (G02) | S (S02) |
| 57A | *Pinus halepensis* | S (D07) + L | S (M02) | L | S (T03) + L | L | — | — |
| 69JC | *Juniperus communis* subsp. *communis* | S (D07) + L | S (M02) | L | S (T03) + L | L | — | — |
| 181 autres espar à taxon | (voir `species.csv`) | L (D01-D03, D06) | L, TreeMig et LANDIS-II Roumanie seulement (M01, M03) | L, TreeMig seulement (F01) | L (T01) | L (L01) | — (G07) | — (S06) |
| 19, 36 | *Populus*, *Eucalyptus* (genres) | — | — | — | — (T09) | — (L03) | — | — |
| 29AF, 68CE | autre feuillu, autre résineux | — | — | — | — (T09) | — (L03) | — | — |

\* F02 et F03 mesurent la **fructification** (fréquence et intensité des glandées), pas une fécondité par arbre.

**Décomptes.** `species.csv` compte 195 codes :
- 191 taxons d'espèce ou de rang inférieur ;
- 2 codes de genre (19, 36) ;
- 2 codes génériques sans taxon (29AF, 68CE).

Avec une source qui nomme l'essence :
- **dispersion :** 4 espar (09, 61, 57A, 69JC) ;
- **maturité :** 3 (61, 57A, 69JC) ;
- **fécondité par arbre :** 0 ; fructification seulement : 2 (09, 62) ;
- **tolérance :** 10 ;
- **L :** 3 ;
- **croissance des semis :** 7 ;
- **survie des semis :** 7.

Remarques sur les 181 autres espar :
- elles ne sont **sourcées essence par essence pour aucune grandeur** ;
- pour la croissance et la survie des semis, elles sont **absentes** ;
- pour la tolérance et L, elles dépendent de deux tables (Niinemets, Tichý) à lire et à apparier.

## 4. Écarts relevés entre sources

1. **Trois sens d'échelle pour une même idée :**
   - Niinemets : 1 = très intolérante, 5 = très tolérante ;
   - TreeMig : 1 = tolérante, 9 = intolérante ;
   - 4C : 5 = tolérante, à l'inverse d'Ellenberg, dont il dérive ;
   - LANDIS-II PnET : 100 à 300.

   Toute reprise doit dire son sens. Le contrat devra fixer le sien et citer la source.
2. **Échelle de Niinemets et Valladares :** 1-5 selon Kulha et al. 2023, 0-5 selon d'autres articles citants. À lire dans l'annexe A.
3. **Le BRIEF et la spec ne nomment pas le même indice de tolérance.** BRIEF §7.3 : « tolérance à l'ombre (indice L d'Ellenberg) ». Spec §8 (`docs/spec.md:259-260`) : « Tolérance à l'ombre : Niinemets et Valladares 2006 ». Or Q3 ne fait entrer que la lumière et la tolérance. L est une valeur d'habitat de la plante adulte, la tolérance une aptitude de l'espèce : il faut savoir lequel entre dans la survie.
4. **Maturité : deux grandeurs.** TreeMig l'exprime par une hauteur minimale (`minmat`, m), LANDIS-II par un âge (ans). Aucune source trouvée ne donne un **diamètre** de maturité.
5. **Dispersion du sapin :** le résumé attribue des médianes voisines à Sagnard 2007 et à Amm 2012, deux articles et deux méthodes différents. Il y a peut-être eu un mélange dans le résumé ; aucune valeur n'est reprise.
6. **Noyau de LANDIS-II :** double exponentielle (page d'iLand) ou noyau de Ward (LandR) ; repris de `moteurs-existants.md:41`, non tranché.
7. **TreeMig a au moins deux jeux de paramètres :** Lischke 2006, et des conifères revus d'après Rickebusch et al. 2007 (supplément GMD 8 : 3563, 2015). Il faudra dire lequel on lit.
8. **Petriţan 2007** est publié dans *Forestry* 80 : 397-412, et non dans *Annals of Forest Science* : l'article des Annales de ce premier auteur date de 2010.
9. **RReShar n'est pas une source de paramètres d'espèces.** C'est une référence de conception (BRIEF §7), calée sur le pin sylvestre de chênaie-pinède. Sa classe « espèce » doit recevoir des fonctions de croissance et de survie ; elle n'en publie pas pour nos essences.
10. **Fructification et fécondité :** les jeux de glandée (Ascoli 2017, hêtre 2024) mesurent l'intermittence, ce que le BRIEF §7 range dans les scénarios, reportés par Q3. Ils ne donnent pas un nombre de graines par semencier.

## 5. Recommandation par grandeur (l'IA propose, Pascal tranche)

Rappel du cadre posé par Pascal :
- par Q1, sous couvert, le flux de passage est celui de l'IFN : dispersion, maturité et fécondité n'agissent qu'en trouée, ou quand le stock manque ;
- par Q2, le stock initial vaut flux IFN × temps de passage : **la croissance des semis est donc nécessaire pour toute essence qui recrute à l'IFN** ;
- par Q3, la survie dépend de la lumière et de la tolérance : **la tolérance est nécessaire pour toutes les essences**.

1. **Dispersion.**
   - Proposition :
     - les **classes de Lososová et al. 2023** comme source unique : CC BY 4.0, Europe, 10 327 espèces, appariement par nom latin comme sylvostation le fait pour Tichý ;
     - un noyau par classe, avec les distances publiées pour chaque classe, à lire dans l'article ;
     - un terme `dispersal_class` par essence, et un noyau par classe.
   - Contrôle : Sagnard 2007 et Amm 2012 pour le sapin et le hêtre.
   - TreeMig (`alfa1`, `alfa2`, `dispFac`) seulement si sa licence le permet, après lecture.
2. **Maturité.**
   - Proposition : un **seuil de hauteur** à la manière de TreeMig (`minmat`). `simulate` connaît les hauteurs, et aucune source ne donne de diamètre.
   - Valeurs à lire dans le fichier d'espèces de TreeMig (hôte bloqué). D'ici là :
     - terme `absent`, et code 2 sur une zone réelle ;
     - `provisoire: true` sur le jeu fictif.
3. **Fécondité.**
   - **Aucune source par essence.** Trois voies :
     - (a) `maxseed` de TreeMig, après lecture et vérification de sa licence ;
     - (b) un terme provisoire non sourcé, signalé ;
     - (c) pas de fécondité absolue : l'arrivée de graines est relative (noyau × semenciers mûrs), et le nombre de semis installés en trouée se règle sur le stock « en régime » de Q2, déduit des modèles comme lui.
   - Je propose (c), qui n'invente aucune valeur, à condition que Pascal accepte que l'abondance des semis en trouée soit déduite et non observée.
4. **Tolérance à l'ombre.**
   - **Niinemets et Valladares 2006, annexe A, source unique**, comme la spec §8. Lecture à faire, en autorisant `esapubs.org` ou `figshare.com`.
   - Contrôle : les mesures de terrain (T06-T08). TreeMig et 4C, non indépendants, ne servent pas de contrôle.
   - Les codes de genre et les codes génériques n'ont pas de valeur sans une règle de rattachement décidée par Pascal.
5. **L d'Ellenberg.**
   - Tichý 2023, colonne `LIGHT`, lue hors dépôt (décision du 25/11), jamais recopiée.
   - Proposition : L **ne multiplie pas** la survie en plus de la tolérance. Elle sert de contrôle à Niinemets, pour lever l'écart n° 3 entre BRIEF et spec. Sinon, la lumière compterait deux fois.
6. **Croissance en hauteur des semis sous couvert.**
   - **Absente pour 181 espar sur 191**, et sourcée pour 7 seulement (09, 05, 15S, 17C, 61, 52, 58), sans valeurs lues.
   - Or Q2 en a besoin pour toutes. Trois voies :
     - (a) code 2 pour toute essence sans source ;
     - (b) des courbes par classe de tolérance, empruntées aux 7 essences sourcées et marquées provisoires ;
     - (c) des essences regroupées.
   - Le risque n° 6 du plan interdit tout emprunt « de la même famille » sans décision de Pascal. Je propose de lire d'abord Kunstler 2005, Petriţan 2007 et Ameztegui et Coll 2011, puis de poser (b) à Pascal, avec la liste des essences concernées.
7. **Survie des semis sous couvert.**
   - Même couverture que la croissance.
   - Proposition : une seule forme fonctionnelle, de la lumière et de la tolérance de Niinemets (Q3). Elle est à prendre dans un modèle publié et cité (TreeMig ou SORTIE-ND, à lire), pas écrite par le `dev`. Les mesures des 7 essences servent de contrôle.
   - Kunstler 2005 relie la mortalité à la croissance, et non directement à la lumière : c'est une autre forme possible, à soumettre à Pascal.

## 6. Ce qui reste à décider par Pascal (une question à la fois, dans cet ordre)

1. Quel indice entre dans la survie : Niinemets (spec §8) ou L d'Ellenberg (BRIEF §7.3) ? L'autre sert de contrôle (écart n° 3).
2. Pour les essences sans croissance ni survie publiées (181 sur 191), quelle voie : code 2, emprunt par classe de tolérance marqué provisoire, ou regroupement ? Cela touche tout le stock « en régime » de Q2.
3. Fécondité : accepter la voie (c), où l'abondance en trouée est déduite du stock en régime ?
4. Maturité exprimée par une hauteur (TreeMig) plutôt que par un âge ou un diamètre ?
5. Dispersion : accepter un noyau par classe (Lososová), commun à toutes les essences d'une classe ?
6. Hôtes à autoriser : **approuvés par Pascal le 26/11 (journal l. 332)**, mais encore refusés par le réseau de la session lors de la seconde passe (§0). Ce n'est plus une question pour Pascal, c'est un réglage de l'environnement à vérifier par l'orchestrateur. Il faut toujours lire la licence de TreeMig avant d'en reprendre une valeur : elle diffère entre code et données (§0).
7. Règle de rattachement des codes de genre (19 *Populus*, 36 *Eucalyptus*) et des codes génériques (29AF, 68CE) pour la tolérance et L.

## 7. Trois points au sol (à vérifier par Pascal)

1. **Une trouée de hêtraie-sapinière (61, 09), bordée de semenciers.** Relever la distance des semis au semencier le plus proche, et comparer au noyau de classe (Lososová) et aux médianes mesurées (Sagnard, Amm). C'est là que la dispersion décide, par Q1, de la recolonisation, et que les sources peuvent diverger.
2. **Un sous-étage de chêne pubescent sous hêtre (05, 09), dans le sud de la France**, comme le site de Kunstler 2005. Compter les semis vivants des deux essences sous couvert dense. C'est là que le rang de tolérance de Niinemets, la valeur L de Tichý et la mesure peuvent se contredire (écart n° 3).
3. **Érable sycomore et frêne sous hêtraie fermée (15S, 17C, 09).** Ce sont des essences mi-tolérantes d'après Petriţan. Avec Q3, leur survie ne dépendra que de l'indice de tolérance : voir si elles persistent sous couvert, ou seulement en trouée. C'est le cas où une erreur d'un cran sur l'échelle change la composition des recrues.

## 8. Question de contrôle

*Quelle décision cette donnée va-t-elle éclairer ?* Les termes et les sources du contrat `params/regeneration` (mission 060), et ce que Pascal doit trancher avant les missions 061 et 062 : quel indice de tolérance, quelle règle pour les essences sans croissance ni survie publiées, quelle fécondité, quelle maturité.

## 9. Ligne de journal proposée

`2026-11-26 · acquereur · 059 · rendu : docs/referentiels/regeneration.{md,csv} (44 lignes, 7 grandeurs, 20 sources) ; aucune table ouverte (esapubs.org et figshare.com bloqués, puis arrêt ; zenodo, treemig.wsl.ch, hal.inrae.fr déjà bloqués le 24/11) ; aucune valeur recopiée ; croissance et survie des semis sourcées pour 7 espar sur 191, absentes ailleurs ; aucune fécondité par arbre ; maturité en hauteur (TreeMig) ou en âge (LANDIS-II), jamais en diamètre ; écart BRIEF §7.3 (L d'Ellenberg) / spec §8 (Niinemets) sur l'indice de tolérance ; 7 questions pour Pascal.`

Seconde passe :

`2026-11-26 · acquereur · 059 (seconde passe) · les 9 hôtes approuvés par Pascal (esapubs.org, figshare.com, zenodo.org, treemig.wsl.ch, www.frontiersin.org, hal.inrae.fr, hal.science, www.ipcc-nggip.iges.or.jp, www.sci.muni.cz) refusés deux fois chacun (ENOTFOUND) : approbation non appliquée au réseau de la session ; aucune table lue, aucune valeur ni appariement écrit, couverture inchangée ; seul ajout : la licence de TreeMig différerait entre code (CC-BY-NC-SA) et données (CC BY 4.0) selon un résumé de recherche, écart avec moteurs-existants.md:25 ; rendu : regeneration.{md,csv} (§0, colonnes lecture et licence).`

## 10. Liste de contrôle

**Aucune liste de contrôle n'était jointe à la consigne.** J'ai passé les trois points génériques de ma fiche.

1. **Sources et emplacements : coché avec réserves.**
   - Chaque ligne du CSV porte une référence et une URL (ou un DOI), ou bien `absent`.
   - Non coché :
     - aucune page n'a été ouverte ; aucun numéro de page ni de ligne de tableau n'est donné, faute d'avoir lu ;
     - trois DOI ne sont pas lus : Kunstler 2005, Petriţan 2007, et le titre de la thèse RReShar. Ils sont écrits « non lu » plutôt que reconstitués ;
     - le DOI de Niinemets et Valladares est repris d'un lien Google Scholar dont la fin était tronquée.
2. **Décomptes complets : coché.**
   - Les 195 codes de `species.csv` sont couverts : 10 lignes du tableau de couverture, plus une ligne pour les 181 autres taxons et deux lignes pour les 4 codes de genre ou génériques (10 + 181 + 4 = 195).
   - Le CSV compte 44 lignes : 10 pour la dispersion, 5 pour la maturité, 4 pour la fécondité, 9 pour la tolérance, 3 pour L, 7 pour la croissance, 6 pour la survie.
   - Non coché : l'appariement des 191 taxons aux listes de Niinemets, de Tichý, de Lososová et de TreeMig, faute de les avoir ouvertes.
3. **Termes exacts : coché.**
   - Les noms de paramètres sont ceux des sources : `minmat`, `maxseed`, `alfa1`, `alfa2`, `dispFac`, `LIGHT`, la feuille `Tab-IVs-Tichy-et-al2023`.
   - Les codes sont les `espar` de `species.csv`.
   - Les sens d'échelle sont dits (écart n° 1).
