# Régénération : ce que la littérature publie, essence par essence (mission 059, mission A du plan M5a)

- **Propriétaire :** Pascal
- **Date de consultation :** 2026-11-26 (trois passes ; la troisième lit les documents téléchargés en local)
- **Produit par :** agent `acquereur`, mission 059 (`pilotage/missions/059-referentiel-regeneration.md`)
- **Mission redite :** relever, pour chaque essence de `contracts/species.csv` et pour sept grandeurs (dispersion, maturité, fécondité, tolérance à l'ombre, L d'Ellenberg, croissance et survie des semis sous couvert), ce que la littérature publie et où, pour que le contrat `params/regeneration` (mission 060) ne porte que des termes qui existent.
- **Décision éclairée :** les termes et les sources de `params/regeneration.parquet` (plan `docs/plans/m5a.md` §3 ; contrat `contracts/tables/params/regeneration.schema.json`), dans le cadre des réponses de Pascal du 26/11/2026 (journal l. 323-325) :
  - Q1 : passage calé sur le flux IFN, borné par le stock de semis ;
  - Q2 : stock initial « en régime » (flux IFN × temps de passage) ;
  - Q3 : survie par la seule lumière et la tolérance à l'ombre.
- **Fichier tabulaire :** `docs/referentiels/regeneration.csv`, 195 lignes de données. Ce sont :
  - les 44 lignes des passes 1 et 2, mises à jour ;
  - 140 lignes `T01-<espar>`, une par espar appariée à Niinemets et Valladares ;
  - une ligne `T01-ABS` pour les 51 taxons absents de Niinemets ;
  - 7 lignes `D01-C1` à `D01-C7` (classes de Lososová) ;
  - 2 lignes `D01-14` et `D01-15P` ;
  - une ligne `R01` (GIEC, pour `post`).
- **Colonnes du CSV :**
  - `statut` :
    - `lu` : la page ou la ligne a été ouverte dans le fichier téléchargé, l'emplacement est donné ;
    - `manquant` : la source qui publie la valeur est identifiée et lue en partie, mais le fichier qui porte les valeurs n'a pas pu être téléchargé ;
    - `publie` : vu dans un résumé de recherche (passes 1 et 2), page non ouverte ;
    - `couverture_non_lue` : source à large couverture, non téléchargée ;
    - `absent` : aucune source trouvée.
  - `valeur` : un nombre n'y est écrit que si la licence lue dans le document permet de le reprendre. C'est le cas des seules classes de Lososová (CC BY). Sinon : `lue, non recopiée`, `non lue` ou `absent`.
  - `lecture` : comment la ligne a été établie.

## 0. Historique des passes

1. **Passes 1 et 2 (26/11).** Recherche web seule. Tous les hôtes étaient refusés par la session, y compris après l'approbation de Pascal (journal l. 332). Aucune table n'a été lue.
2. **Passe 3 (26/11, cette version).** Un `dev` a téléchargé les documents publics par `curl` sous `data/sources/regeneration/`, hors dépôt. `INDEX.md` y donne, pour chaque fichier, l'URL, la date, le sha256 et la licence annoncée. Je les ai lus en local, avec l'outil Read.

| Fichier lu | Ce qui a été lu |
|---|---|
| `niinemets_appendixA.htm` | tout le tableau : 806 noms comptés ; 2 418 cellules de tolérance (806 × 3), toutes remplies ; appariement des 195 codes de `species.csv` par genre |
| `SpecParsMeanings.pdf` | p. 1 (unique) |
| `TreeMigDocu_251218_Model.pdf` | p. 1-4, 9-17, 19-20 |
| `TreeMigDocu_23_Code.pdf`, `InfosSettingsControlFileAndGUI.pdf` | p. 1-2 : aucune valeur d'espèce |
| `treemig_details.html`, `treemig_framework.html`, `treemig_starter-kit.html`, `treemig_core-model.html` | recherche des mots « licence », « Creative Commons », « EnviDat », « species param », et lecture des lignes trouvées |
| `lososova2023.pdf` | p. 1485-1492 (article entier sauf la bibliographie) |
| `ipcc_v4_ch4.pdf` | p. 4.1, 4.2, 4.49 (tableau 4.4), 4.50 |
| `frontiers_article.html` | mentions de licence, tableau 2, passages sur la dispersion, la maturité et la tolérance |

## 1. Licences, confirmées ou corrigées d'après les documents

| Source | Ce que dit le document (emplacement) | Conséquence |
|---|---|---|
| **Niinemets et Valladares 2006, annexe A** | **aucune licence** dans la page ; seulement des liens vers l'annexe B et mobot.org (`INDEX.md`, et en-tête lu ligne 24) | Valeurs **lues mais non recopiées** dans le dépôt : sans licence dite, la redistribution n'est pas établie. Chaque espar porte sa ligne exacte dans le fichier (sha256 donné). Voir la question n° 2. |
| **TreeMig, code** | « This FORTRAN code is available on request, under licence CC-BY-NC-SA 4.0 » (`treemig_framework.html:478`) | **confirmé : NC.** On ne reprend rien du code. |
| **TreeMig, données de la page `details`** | « All data are available under the Creative Commons license CC BY 4.0 » (`treemig_details.html:883`), dans le paragraphe sur les scénarios climatiques suisses CH2018 | **Correction de la seconde passe.** Ce CC BY 4.0 vise CH2018, pas les données de TreeMig. |
| **TreeMig, paramètres d'espèces** | fichiers TreePars du dossier P de TMEnvironment (`TreeMigDocu_251218_Model.pdf` p. 19) ; exemples pour « the 30 most common tree species in Central Europe » (`treemig_details.html:589`), dans le zip du starter kit sur EnviDat (`treemig_starter-kit.html:438-439`) ; **aucune licence** dans les pages et PDF lus | Licence **inconnue**, fichiers non obtenus. Rien à reprendre ; à lire sur la notice EnviDat avant tout usage. La mention CC-BY-SA pour EnviDat (seconde passe, résumé de recherche) n'est **pas vérifiée**. |
| **TreeMig, documentation** (PDF) | aucune licence vue dans les pages lues | Seuls les noms de paramètres, les unités et les numéros d'équation sont cités ; aucune constante n'est recopiée. |
| **Lososová et al. 2023** | « This is an open access article under the terms of the Creative Commons Attribution License, which permits use, distribution and reproduction in any medium, provided the original work is properly cited » (p. 1485 ; version non précisée) | Article **CC BY confirmé** : les distances par classe (tableau 1, p. 1488) sont reprises avec citation. La licence du Supplement S1 et de FloraVeg.EU n'est pas lue. |
| **Suárez-Muñoz et al. 2021 (Frontiers)** | « Creative Commons Attribution License (CC BY) », copyright 2021 des auteurs (`frontiers_article.html:92`) | Article **CC BY confirmé** ; Data Sheet 1 non obtenu, licence non lue. |
| **GIEC 2006, vol. 4, chap. 4** | **aucune licence** dans les pages lues | Tableau 4.4 **lu, non recopié** (voir §6 et la question n° 10). |

## 2. Tableau de couverture (essence × grandeur)

Légende :
- **lu** : valeur ou classe lue dans un document téléchargé (ligne ou page dans le CSV) ;
- **manquant** : publiée dans un fichier identifié mais non obtenu (Data Sheet 1 de Frontiers ; TreePars de TreeMig ; S1 de Lososová ; thèse HAL de Gaudio) ;
- **résumé** : vu dans un résumé de recherche seulement (passes 1 et 2) ;
- **hors dépôt** : Tichý 2023, non recopié par décision de Pascal ;
- **—** : absent.

| espar | Essence | Dispersion | Maturité | Fécondité | Tolérance | L Ellenberg | Croissance semis | Survie semis |
|---|---|---|---|---|---|---|---|---|
| 09 | *Fagus sylvatica* | résumé (D04) ; manquant (S1) | manquant (TreeMig) | résumé* (F02, F03) | **lu** (T01-09) ; résumé (T04, T06, T07) | hors dépôt | résumé (G01, G02) | résumé (S01, S02) |
| 61 | *Abies alba* | résumé (D04, D05) ; manquant (S1) | résumé (M04) ; manquant | manquant (TreeMig) | **lu** (T01-61) ; résumé (T08) | hors dépôt | résumé (G03) | résumé (S03) |
| 52 | *Pinus sylvestris* | manquant (S1, Data Sheet 1) | manquant (Data Sheet 1) | manquant | **lu** (T01-52) ; manquant (T03) ; résumé (T04, T08) | hors dépôt | résumé (G03) ; manquant (G05, thèse HAL) | résumé (S03) |
| 58 | *Pinus mugo* subsp. *uncinata* | manquant (S1) | manquant | manquant | **lu, synonyme à valider** (T01-58) ; résumé (T08) | hors dépôt | résumé (G03) | résumé (S03) |
| 62 | *Picea abies* | manquant (S1) | manquant | résumé* (F02) | **lu** (T01-62) ; résumé (T04) | hors dépôt | — | — |
| 05 | *Quercus pubescens* | manquant (S1) | manquant | manquant | **lu** (T01-05) ; résumé (T07) | hors dépôt | résumé (G01) | résumé (S01) |
| 15S | *Acer pseudoplatanus* | manquant (S1) | manquant | manquant | **lu** (T01-15S) ; résumé (T06) | hors dépôt | résumé (G02) | résumé (S02) |
| 17C | *Fraxinus excelsior* | manquant (S1) | manquant | manquant | **lu** (T01-17C) ; résumé (T06) | hors dépôt | résumé (G02) | résumé (S02) |
| 15P | *Acer platanoides* | **lu : classe 4** (D01-15P) | manquant | manquant | **lu** (T01-15P) | hors dépôt | — | — |
| 14 | *Robinia pseudoacacia* | **lu : classe 7, ou 4 sans l'homme** (D01-14) | manquant | manquant | **lu** (T01-14) | hors dépôt | — | — |
| 57A | *Pinus halepensis* | manquant (Data Sheet 1, S1) | manquant (Data Sheet 1) | manquant | **lu** (T01-57A) ; manquant (T03) | hors dépôt | — | — |
| 69JC | *Juniperus communis* subsp. *communis* | manquant (Data Sheet 1, S1) | manquant (Data Sheet 1) | manquant | **lu** (T01-69JC) ; manquant (T03) | hors dépôt | — | — |
| 06, 07, 51, 53CA, 53CO, 53S, 54, 33N, 69JO | essences du tableau 2 de Frontiers | manquant (Data Sheet 1, S1) | manquant (Data Sheet 1) | manquant | **lu** pour 06, 54 ; **lu, rang espèce à valider** pour 33N, 53CA, 53CO, 53S ; **absent** de Niinemets pour 07, 51, 69JO (manquant au Data Sheet 1) | hors dépôt | — | — |
| les 122 autres espar appariées à Niinemets | voir les lignes `T01-<espar>` | manquant (S1) | manquant (TreeMig pour certaines, liste inconnue) | manquant (idem) | **lu** (dont 7 appariements à valider : 20X, 26E, 37, 23PC, 68CB, 49AE, 49AM) | hors dépôt | — | — |
| les 48 autres espar absentes de Niinemets | voir `T01-ABS` | manquant (S1) | manquant ou — | manquant ou — | **—** | hors dépôt | — | — |
| 19, 36 | *Populus*, *Eucalyptus* (genres) | — | — | — | — (T09) | — (L03) | — | — |
| 29AF, 68CE | autre feuillu, autre résineux | — | — | — | — (T09) | — (L03) | — | — |

\* F02 et F03 mesurent la **fructification** (fréquence et intensité des glandées), pas une fécondité par arbre.

**Décomptes (195 codes = 191 taxons + 2 genres + 2 génériques) :**
- **Tolérance à l'ombre (Niinemets), 140 taxons sur 191 appariés et lus** :
  - 111 au nom identique ;
  - 1 au nom identique mais à parenté à vérifier : 74H ;
  - 16 autonymes ramenés à l'espèce : 02, 03, 13B, 17F, 18M, 20G, 21O, 22G, 23SO, 25D, 49BO, 49SR, 54, 62, 63, 69JC ;
  - 5 au rang de l'espèce seulement : 33N, 53CA, 53CO, 53S, 68CB ;
  - 5 par synonymie ou par un autre rang : 20X, 26E, 37, 58, 23PC ;
  - 2 à un agrégat : 49AE, 49AM.

  **51 taxons sont absents** (liste dans `T01-ABS`). Parmi eux : *Quercus suber*, *Q. pyrenaica*, *Pinus pinaster*, *P. pinea*, *Cedrus atlantica*, *Celtis australis*, *Juniperus oxycedrus*, *J. thurifera*, *Abies pinsapo*, *Olea europaea*, et *Pinus contorta* (68PC), dont seules deux sous-espèces sont listées.
- **Dispersion :**
  - classe lue pour 2 espar (15P, 14), dans le texte de l'article ;
  - pour toutes les autres, la classe est dans le Supplement S1, non obtenu ;
  - les distances des 7 classes sont lues (D01-C1 à D01-C7).
- **Maturité, fécondité :** **0 valeur lue.** TreeMig (30 essences, liste inconnue) et le Data Sheet 1 (10 essences) sont manquants.
- **L d'Ellenberg :** hors dépôt par décision ; non téléchargé.
- **Croissance et survie des semis :** **0 valeur lue.**
  - Sources à l'essence : résumés seulement, pour 7 espar (09, 05, 15S, 17C, 61, 52, 58).
  - TreeMig publie les **formes** (équations lues), mais pas les valeurs d'espèces.

## 3. Les sources au CQQCOQP (ce que la lecture a changé)

Le **Pourquoi** est le même pour toutes : choisir les termes et les sources de `params/regeneration`. Les sources qui n'ont pas été téléchargées (Vittoz, Bullock, Sagnard, Amm, 4C, Kulha, Kunstler, Petriţan, Ameztegui, SORTIE-ND, Atlas JRC, LANDIS-II Roumanie) restent décrites dans le CSV comme aux passes 1 et 2.

| Source | Qui, dans quel but | Quoi | Comment | Où | Quand | Combien |
|---|---|---|---|---|---|---|
| **Niinemets et Valladares 2006**, annexe A (T01) | écophysiologistes, pour comparer les tolérances | tolérance à l'ombre, à la sécheresse et à l'engorgement de 806 espèces ligneuses | estimations tirées de la littérature, avec une erreur standard quand deux sources ou plus (ligne 24) ; noms W3TROPICOS 2005 | hémisphère Nord tempéré | 2006 | **0 à 5** (en-tête ligne 24) ; une valeur à 5,01 (ligne 77) ; licence non dite |
| **TreeMig** (D06, M01, F01, T02, G06, S05) | WSL (Lischke, Löffler, Zimmermann, Böhm), pour la migration des essences, du peuplement au continent (p. 20) | 28 paramètres d'espèces (tableau 1, p. 19) ; **formes** de la production de graines (éq. 13-14), du noyau (éq. 16), de l'installation (éq. 29-30), de la mortalité (éq. 37-40) et de la croissance (éq. 43, 47-49) | modèle à classes de hauteur et à classes de lumière | Europe centrale, 30 essences ; paramétrages aussi pour l'Amérique du Nord et la Chine (p. 20) | doc. du 18/12/2025 | valeurs non obtenues ; code NC ; licence des paramètres inconnue |
| **Lososová et al. 2023** (D01) | botanistes et écologues, pour la biogéographie et les modèles de végétation | classe de distance (1-7) et mode de dispersion de 10 327 espèces | arbre de décision (figure 1, p. 1489) sur le mode, la diaspore, la forme de vie, la hauteur, l'habitat ; contrôle par le modèle de Tamme et al. 2014 (R² = 0,75 sur six classes, p. 1490) | Europe ; noms Euro+Med, sous-espèces fusionnées (p. 1486) | 2023 | CC BY ; deux quantiles par classe (50 %, 99 %) |
| **Suárez-Muñoz et al. 2021** (D07, M02, T03) | université de Grenade, pour caler LANDIS-II PnET | 10 essences et 3 groupes d'arbustes (tableau 2) ; le tableau 2 ne porte que des paramètres de PnET (longévité, azote foliaire, photosynthèse) | TRY, littérature, calage | Sierra Nevada | 2021 | CC BY ; paramètres de régénération dans le Data Sheet 1, non obtenu |

**Une deuxième source qui se tromperait pour une autre raison :**
- **Tolérance.** Niinemets, une synthèse, contre les mesures de terrain, dont aucune n'est encore lue :
  - le hêtre au-dessus du chêne pubescent concorde avec le résumé de Kunstler 2005 (T07) ;
  - le pin à crochets sous le pin sylvestre chez Niinemets va **contre** le résumé d'Ameztegui et Coll 2011 (T08). C'est un écart à vérifier, voir le point au sol n° 3.
- **Dispersion.** Les classes de Lososová ne sont pas indépendantes de Vittoz et Engler 2007, que Lososová modifie (p. 1487). La seconde source reste une mesure (Sagnard, Amm), non lue.

## 4. Écarts relevés entre sources

1. **Sens des échelles de tolérance :**
   - Niinemets : 0 (« no tolerance ») à 5 (« maximal tolerance »), ligne 24 ;
   - TreeMig `klighs`/`kligha` : 1 (tolérante) à 9 (intolérante), SpecParsMeanings p. 1 et tableau 1 p. 19 ;
   - 4C : 1 à 5 (non lu) ;
   - LANDIS-II PnET : 100 à 300 (non lu).

   L'écart n° 2 de la première passe (« 1-5 ou 0-5 ? ») est **levé** : l'annexe dit 0-5. Kulha et al. 2023, qui disait 1-5 d'après le résumé, n'est pas lu.
2. **Une valeur au-dessus de l'échelle :** *Abies balsamea* vaut 5,01 (ligne 77), au-delà du 5 annoncé. Ce taxon est hors `species.csv`, mais le contrôle des bornes ne peut pas être strict à 5.
3. **BRIEF et spec ne nomment pas le même indice** (BRIEF §7.3 : L d'Ellenberg ; spec §8 et contrat : Niinemets). Inchangé (question n° 1).
4. **Maturité.**
   - TreeMig l'exprime en **hauteur** (`minmat`, éq. 13, p. 9), alors que le contrat attend `maturity_d130_cm`.
   - L'éq. (10) de TreeMig (p. 9) relie diamètre et hauteur. Convertir l'un en l'autre serait une dérivation (question n° 8).
5. **Fécondité.**
   - TreeMig : `maxseed` = nombre maximal de graines **par arbre** et par an (tableau 1, p. 19 ; éq. 14).
   - Contrat : graines par m² de **surface terrière** et par an. Ce n'est pas la même grandeur.
   - SpecParsMeanings ne donne pas l'unité de `maxseed` ; la doc du modèle la donne.
6. **Noyau de dispersion.**
   - TreeMig : somme pondérée de **deux** exponentielles négatives (éq. 16, p. 10).
   - Contrat (ADR 0006) : **une** exponentielle-puissance. Le noyau TreeMig ne s'écrit pas dans le contrat.
   - Lososová ne donne pas de noyau, mais deux quantiles par classe.
7. **Deux documents TreeMig se contredisent :**
   - unité de la croissance maximale : `G` en cm/an (SpecParsMeanings), `kG` en kg/an (tableau 1, p. 19) ;
   - `dispFac` : « [0-1] » d'un côté, « Either 0 or 0.001 » de l'autre ;
   - `sType/N` : « shading capability » d'un côté, « Foliage type » de l'autre.
8. **Licence de TreeMig :** la seconde passe donnait CC BY 4.0 aux « données d'entrée ». La page vise en fait **CH2018** (`treemig_details.html:883`). Corrigé.
9. **Classes de Lososová non monotones sur la distance à 50 % :** 40 m en classe 4, 10 m en classe 5 (tableau 1, p. 1488). L'ordre des classes suit plutôt la distance à 99 % de 1 à 6. Un noyau par classe doit utiliser les deux quantiles, pas le rang.
10. **Robinier (14), deux classes :** 4 par son mode naturel, 7 dans le schéma de 2023 parce qu'il est planté par l'homme (p. 1487). Six ou sept classes : les auteurs conseillent six à l'échelle du paysage (p. 1490).
11. **Frontiers, tolérance trop haute selon les auteurs eux-mêmes :** « species shade tolerances being higher than in reality » (Discussion). T03 est donc à prendre avec réserve, même une fois le Data Sheet obtenu.
12. **Appariements non exacts dans Niinemets** (question n° 3) :
    - *Pinus uncinata* est rangé au rang d'espèce, à part de *P. mugo* (58 ≠ 60) ;
    - *Tilia × vulgaris* pour *T. × europaea* ;
    - *Platanus × acerifolia* pour *P. × hispanica* ; sa ligne 5091 le dit en outre « Evergreen : Y », ce qu'il faut signaler ;
    - *Alnus viridis* pour *A. alnobetula* ;
    - *Pyrus pyraster* pour *P. communis* subsp. *pyraster* ;
    - *Larix × marschlinsii* donné comme *L. sibirica* × *L. kaempferi*, à côté d'un *L. × eurolepis* (*L. decidua* × *L. kaempferi*, ligne 3646). La parenté de 74H n'est pas vérifiée dans TAXREF.
13. **Tolérance (Niinemets) contre mesure (Ameztegui et Coll 2011, résumé) pour les pins :** voir le §3.
14. Inchangés depuis les passes 1 et 2, sources non téléchargées :
    - le sapin chez Sagnard et chez Amm ;
    - Petriţan 2007 dans *Forestry* ;
    - RReShar, qui n'est pas une source de paramètres ;
    - fructification n'est pas fécondité.

## 5. Recommandation par grandeur (l'IA propose, Pascal tranche)

Rappel du cadre : par Q1, la dispersion, la maturité et la fécondité n'agissent qu'en trouée ou quand le stock manque. Par Q2, la croissance des semis est nécessaire pour toute essence qui recrute à l'IFN. Par Q3, la tolérance est nécessaire pour toutes les essences.

1. **Tolérance à l'ombre (`shade_tolerance`).**
   - Niinemets et Valladares 2006, annexe A, **source unique**, conformément à la spec §8 et au contrat. Elle est lue pour 140 taxons sur 191.
   - Proposition : la lire **hors dépôt**, par une clé `external.*` pointant le fichier téléchargé et son sha256, comme Tichý. Ne pas la recopier tant que sa licence n'est pas connue (question n° 2).
   - Les 12 appariements non exacts et les 51 absents attendent la décision de Pascal (questions n° 3 et 4). D'ici là : code 2 sur zone réelle, `provisoire: true` sur le jeu fictif.
   - Les bornes du validateur : 0 à 5, avec la valeur 5,01 de la ligne 77 à signaler (écart n° 2).
2. **Survie des semis (`seedling_survival_full_light_yr` et l'effet de la lumière).**
   - TreeMig publie une forme de la mortalité qui ne dépend que de la lumière et d'un seuil de tolérance (éq. 39-40, p. 16 ; installation, éq. 29-30, p. 14). C'est exactement le cadre de Q3, et une forme publiée et citée plutôt qu'écrite par le `dev`.
   - Mais elle prend `klighs` sur l'échelle TreeMig 1-9, pas Niinemets 0-5. Deux voies, à poser à Pascal (question n° 5) :
     - (a) obtenir les `klighs` de TreeMig (EnviDat, licence à lire), pour 30 essences seulement ;
     - (b) passer de Niinemets à l'échelle TreeMig par une règle écrite et marquée provisoire.
3. **Croissance des semis (`seedling_height_growth_m_yr`).**
   - Aucune valeur lue. TreeMig donne la forme (éq. 35, 43, 49), pas les valeurs.
   - Kunstler, Petriţan, Ameztegui : 7 espar, à télécharger.
   - Pour les autres, la question n° 6 (voie de la passe 1 : code 2, emprunt par classe de tolérance marqué provisoire, ou regroupement) reste ouverte.
4. **Dispersion (`kernel_scale_m`, `kernel_shape`).**
   - Proposition : les **classes de Lososová**, source unique (CC BY).
   - Chaque classe donne **deux quantiles** (50 % et 99 %, tableau 1). Deux quantiles fixent deux paramètres : on peut en tirer `kernel_scale_m` et `kernel_shape` de l'exponentielle-puissance du contrat, par classe. C'est un calcul, pas une invention, mais c'est une dérivation : elle passe par Pascal (question n° 9).
   - Il faut S1 (FloraVeg.EU) pour la classe de chaque essence. Six classes plutôt que sept (p. 1490).
   - Le noyau de TreeMig (deux exponentielles) ne s'écrit pas dans le contrat : à n'utiliser qu'en contrôle.
5. **Maturité (`maturity_d130_cm`).**
   - Aucune valeur lue. La seule source de valeurs identifiée (TreeMig) parle en hauteur.
   - Proposition : soit changer le terme du contrat en hauteur, soit convertir par l'éq. (10) de TreeMig (question n° 8). Code 2 d'ici là.
6. **Fécondité (`fecundity_seeds_per_m2_ba_yr`).**
   - Aucune source par surface terrière. TreeMig donne un nombre par arbre, avec une fonction de hauteur et un cycle de glandée.
   - Proposition inchangée : la voie (c) de la passe 1 (abondance en trouée déduite du stock en régime), ou un terme par arbre sourcé TreeMig (question n° 7).
7. **L d'Ellenberg.** Inchangé : Tichý, hors dépôt. L sert de contrôle à Niinemets, pas de second facteur de survie (question n° 1).

## 6. GIEC 2006 et les racines (pour `post`, hors régénération)

- **Où :** vol. 4, chap. 4 « Forest Land », **tableau 4.4**, p. 4.49 : « Ratio of below-ground biomass to above-ground biomass (R) ».
- **Unité :** tonne de racines (matière sèche) par tonne de parties aériennes (matière sèche).
- **Licence :** **aucune n'est dite** dans les pages lues (4.1, 4.2, 4.49, 4.50). Les valeurs ne sont pas recopiées (ligne `R01` du CSV).
- **Ce que le tableau publie :**
  - un R moyen et sa plage, par domaine et zone écologique ;
  - pour la zone tempérée (« oceanic, continental, mountain systems »), quatre types :
    - conifères, en trois classes de biomasse aérienne (moins de 50, 50 à 150, plus de 150 t/ha) ;
    - *Quercus* spp., une seule classe (plus de 70 t/ha) ;
    - *Eucalyptus* spp., en trois classes ;
    - autres feuillus, en trois classes (moins de 75, 75 à 150, plus de 150 t/ha) ;
  - la source des lignes tempérées est **Mokany et al., 2006** ;
  - les zones subtropicales ont leurs propres lignes, et « Subtropical mountain systems » porte « no estimate available ».
- **Ce que `post` pourrait en tirer :**
  - une biomasse racinaire **par cellule ou par placette**, égale à R × biomasse aérienne par hectare ;
  - R se choisit par type, que `species.csv` donne par sa colonne `groupe` (feuillu/résineux), plus l'exception *Quercus* (codes 02 à 08S, 29CE, 29CM, 34) et le code 36 *Eucalyptus* ;
  - R se choisit aussi par classe de biomasse aérienne.
- **Réserves :**
  - R est un rapport de **peuplement**, défini sur une biomasse par hectare : il ne s'applique pas arbre par arbre ;
  - la ligne *Quercus* ne couvre pas les chênaies de moins de 70 t/ha ;
  - la France méditerranéenne pourrait relever des lignes subtropicales selon la carte des zones écologiques FAO du même chapitre (non lue ici) ;
  - la source primaire, Mokany et al. 2006, est à lire : elle aura peut-être une licence claire. C'est aussi la seconde source à comparer.

## 7. Questions pour Pascal (une à la fois, dans cet ordre)

Chaque question tient seule ; l'orchestrateur les pose une par une.

1. **Quel indice entre dans la survie des semis : Niinemets (spec §8, contrat) ou L d'Ellenberg (BRIEF §7.3) ?**
   - Contexte : Niinemets est maintenant lu pour 140 taxons sur 191 ; Tichý reste hors dépôt.
   - Proposition : Niinemets ; L en contrôle.
   - Ce que change la réponse : si c'est L, le terme `shade_tolerance` du contrat change de source et d'échelle.
2. **Niinemets ne dit pas sa licence : la lire hors dépôt (clé `external.*`, comme Tichý) ou la recopier dans le dépôt ?**
   - Proposition : hors dépôt, avec le sha256 du fichier.
   - Ce que change la réponse : recopier, c'est 140 valeurs dans `params/regeneration` ; hors dépôt, c'est un fichier de plus à fournir pour rejouer (règle des 30 minutes).
3. **Valider les 12 appariements non exacts :**
   - 5 synonymes ou autres rangs : 20X, 26E, 37, 58, 23PC ;
   - 5 au rang de l'espèce : 33N, 53CA, 53CO, 53S, 68CB ;
   - 2 agrégats : 49AE, 49AM ;
   - plus la parenté de 74H.

   Proposition : les accepter, sauf 58. Pour 58, Niinemets distingue *P. uncinata* de *P. mugo*, et le choix change la tolérance. Ce que change la réponse : 12 essences ont une valeur, ou un code 2.
4. **Règle pour les 51 taxons absents de Niinemets et les 4 codes de genre ou génériques (19, 36, 29AF, 68CE).**
   - Proposition : code 2 sur zone réelle, sans emprunt « de la même famille » (risque n° 6 du plan).
   - Ce que change la réponse : *Quercus suber*, *Q. pyrenaica*, *Pinus pinaster*, *P. pinea*, *Cedrus atlantica* sont des essences fréquentes du Sud ; un code 2 arrête `simulate` là où elles recrutent.
5. **Forme de la survie : celle de TreeMig (éq. 39-40), avec quelle échelle de tolérance ?**
   - (a) Les `klighs` de TreeMig, 30 essences, licence à lire sur EnviDat.
   - (b) Niinemets passé à l'échelle 1-9 par une règle écrite et provisoire.

   Proposition : (b), si Pascal accepte une règle de passage ; sinon (a), pour 30 essences seulement.
6. **Croissance des semis pour les essences sans source (184 sur 191) : code 2, emprunt par classe de tolérance marqué provisoire, ou regroupement ?** Ce que change la réponse : tout le stock « en régime » de Q2.
7. **Fécondité : voie (c), où l'abondance des semis en trouée est déduite du stock en régime, ou un terme en graines par arbre tiré de TreeMig (`maxseed`, à obtenir) à la place du terme par surface terrière du contrat ?** Proposition : (c), qui n'invente aucune valeur.
8. **Maturité : changer le terme du contrat en hauteur (comme TreeMig), ou garder le diamètre et convertir par l'éq. (10) de TreeMig ?** Proposition : la hauteur, que `simulate` connaît, sans dérivation.
9. **Dispersion : tirer, pour chacune des six classes naturelles de Lososová, l'échelle et la forme du noyau de ses deux quantiles (50 % et 99 %) ?** Proposition : oui, calcul documenté, une ligne par classe, avec Sagnard et Amm en contrôle. Ce que change la réponse : un noyau commun à toutes les essences d'une classe.
10. **Racines pour `post` : le tableau 4.4 du GIEC n'a pas de licence dite.** Faut-il le lire hors dépôt, ou aller à sa source, Mokany et al. 2006, et lire sa licence ?
11. **Demande d'effort : déposer à la main les trois fichiers que le proxy ou l'anti-robot refusent ?**
    - le Data Sheet 1 de Frontiers ;
    - la thèse HAL de Gaudio (tel-00587487) ;
    - le starter kit TreeMig sur EnviDat (1,5 Go, dont seuls les fichiers TreePars du dossier P servent).

    Ou bien l'orchestrateur fait autoriser les hôtes. La liste de S1 (FloraVeg.EU) est à ajouter à ces fichiers.

## 8. Ce qui manque (fichiers non obtenus)

| Manque | Ce qu'il porterait | Pourquoi il manque (`INDEX.md`) | Lignes du CSV |
|---|---|---|---|
| **Data Sheet 1, Suárez-Muñoz et al. 2021** | dispersion, maturité, tolérance pour 10 essences : 06, 07, 33N, 51, 52, 53*/54, 57A, 69JC, 69JO, et *Q. faginea* | le lien redirige vers `public-pages-files-2025.frontiersin.org`, refusé par le proxy (trois essais) | D07, M02, T03 |
| **Thèse HAL de Gaudio (tel-00587487)** | croissance des semis de pin sylvestre selon la lumière | `hal.inrae.fr` et `hal.science` servent un défi anti-robot, non contourné ; `api.archives-ouvertes.fr` est refusé par le proxy | G05 (et D05, Amm 2012, sur HAL aussi) |
| **Fichiers d'espèces TreeMig (TreePars, dossier P)** | `alfa1`, `alfa2`, `dispFac`, `minmat`, `maxseed`, `klighs`, `kligha`, `kG` pour 30 essences | aucun lien direct dans les pages ; ils sont dans le zip du starter kit sur EnviDat (`treemig_starter-kit.html:438`) et dans le GitLab du WSL, refusé par le proxy | D06, M01, F01, T02, G06, S05 |
| **Supplement S1 de Lososová 2023, ou FloraVeg.EU** | classe de dispersion de chaque espèce | non demandé à cette passe ; adresse donnée p. 1492 | D01 |
| Kunstler 2005, Petriţan 2007, Ameztegui et Coll 2011, SORTIE-ND 2015 | croissance et survie mesurées, 7 espar | non téléchargés (hors liste de cette passe) | T06-T08, G01-G04, S01-S04 |

## 9. Trois points au sol (à vérifier par Pascal)

1. **Une trouée de hêtraie-sapinière (61, 09), bordée de semenciers.**
   - Relever la distance des semis au semencier le plus proche.
   - La comparer aux quantiles de la classe Lososová de ces essences (classe dans S1, à obtenir) et aux médianes mesurées (Sagnard, Amm).
   - C'est là que la dispersion décide, par Q1, de la recolonisation, et qu'un noyau par classe peut s'écarter de la mesure.
2. **Un sous-étage de chêne pubescent sous hêtre (05, 09), dans le sud de la France**, comme le site de Kunstler 2005.
   - Compter les semis vivants des deux essences sous couvert dense.
   - Niinemets range le hêtre nettement au-dessus du chêne pubescent (lignes 2761 et 6193). Le terrain dira si l'écart de survie est aussi fort, et si L (Tichý) raconte la même chose (question n° 1).
3. **Pin à crochets et pin sylvestre sous couvert, en montagne (58, 52)**, dans les Pyrénées ou les Alpes du Sud.
   - Niinemets donne au pin à crochets (*P. uncinata*, ligne 4994) une tolérance plus basse qu'au pin sylvestre (ligne 4961), et plus basse que *P. mugo* (ligne 4807).
   - Le résumé d'Ameztegui et Coll 2011 dit l'inverse sous ombre forte.
   - Voir lequel persiste sous couvert. C'est le cas où l'appariement (question n° 3) et la source décident de la composition des recrues.

## 10. Question de contrôle

*Quelle décision cette donnée va-t-elle éclairer ?* Les termes et les sources du contrat `params/regeneration` (mission 060). D'abord la tolérance à l'ombre, maintenant lue pour 140 taxons. Puis ce que Pascal doit trancher avant les missions 061 et 062 : l'indice, la licence de Niinemets, les appariements, la forme de la survie, la croissance des essences sans source, la maturité et le noyau.

## 11. Lignes de journal proposées

Passes 1 et 2 (déjà proposées) :

`2026-11-26 · acquereur · 059 · rendu : docs/referentiels/regeneration.{md,csv} (44 lignes, 7 grandeurs, 20 sources) ; aucune table ouverte ; aucune valeur recopiée ; 7 questions pour Pascal.`

`2026-11-26 · acquereur · 059 (seconde passe) · les 9 hôtes approuvés refusés deux fois chacun (ENOTFOUND) ; aucune table lue ; licence de TreeMig différente entre code et données selon un résumé de recherche.`

Passe 3 :

`2026-11-26 · acquereur · 059 (troisième passe) · lecture locale de data/sources/regeneration/ (INDEX.md) ; Niinemets annexe A lue : échelle 0-5, 140 taxons de species.csv sur 191 appariés (12 à valider), 51 absents, valeurs non recopiées (licence non dite) ; Lososová 2023 lu (CC BY) : distances à 50 % et 99 % des 7 classes reprises, classes par espèce dans S1 non obtenu ; TreeMig : code CC-BY-NC-SA 4.0 confirmé, le CC BY 4.0 de la page details vise CH2018 (correction de la seconde passe), paramètres d'espèces sur EnviDat non obtenus, formes publiées (survie par lumière et seuil de tolérance, éq. 39-40) ; GIEC tableau 4.4 lu (R racines/aérien par type et classe de biomasse, Mokany 2006), licence non dite, non recopié ; maturité, fécondité, croissance, survie : 0 valeur lue ; manquent Data Sheet 1 Frontiers, thèse HAL Gaudio, TreePars TreeMig ; 11 questions pour Pascal ; rendu : regeneration.{md,csv} (195 lignes).`

## 12. Liste de contrôle

**Aucune liste de contrôle n'était jointe à la consigne de cette passe.** J'ai passé les trois points génériques de ma fiche.

1. **Sources et emplacements : coché, avec réserves.**
   - Chaque ligne `lu` porte le fichier local, la page ou la ligne, et le sha256 abrégé du fichier.
   - Non coché :
     - les lignes `publie` et `couverture_non_lue` restent fondées sur des résumés (passes 1 et 2) ;
     - les DOI de Kunstler 2005 et Petriţan 2007 ne sont toujours pas lus ;
     - le DOI de Niinemets reste repris d'un lien tronqué ; l'en-tête de l'annexe (ligne 23) confirme la référence : *Ecological Monographs* 76 : 521-547.
2. **Décomptes complets : coché.**
   - 195 codes = 140 appariés + 51 absents + 4 genres ou génériques.
   - Niinemets : 806 noms, 2 418 cellules de tolérance.
   - CSV : 195 lignes de données.
   - Non coché : l'appariement à Lososová (S1), à TreeMig et au Data Sheet 1, dont les listes ne sont pas obtenues.
3. **Termes exacts : coché.**
   - Noms de paramètres et intitulés repris des documents : `minmat`, `maxseed`, `klighs`, `kligha`, `alfa1`, `alfa2`, `dispFac`, `kG`, « Shade tolerance », « Ratio of below-ground biomass to above-ground biomass (R) ».
   - Noms latins de Niinemets recopiés tels quels, avec les signes d'hybride.
   - Codes : `espar` de `species.csv`.
