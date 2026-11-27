# Régénération : ce que la littérature publie, essence par essence (mission 059, mission A du plan M5a)

- **Propriétaire :** Pascal
- **Date de consultation :** 2026-11-26 (quatre passes ; la troisième lit les documents téléchargés en local, la quatrième lit les deux documents déposés par Pascal : voir §13) ; 2026-11-27 (cinquième passe, mission 079 : licence de TreePars et tolérance à l'ombre `klighs`, voir §14 ; 6 lignes ajoutées au CSV : L01 à L03, T02-KL, T02-LUM, T02-ESP ; sixième passe, mission 083 : C01 et T02-L29, §15 ; **septième passe, mission 084a : classes de lumière, alpha, arrondi de klighs, mortalité de stress, voir §16 ; 4 lignes ajoutées : T02-CLS, T02-ALP, T02-RND, T02-STR**. **Total : 218 lignes de données** : 195 + 11 (passe 4) + 6 (passe 5) + 2 (passe 6) + 4 (passe 7). L'en-tête disait 212 ; il omettait C01 et T02-L29, comptées ici)
- **Produit par :** agent `acquereur`, mission 059 (`pilotage/missions/059-referentiel-regeneration.md`)
- **Mission redite :** relever, pour chaque essence de `contracts/species.csv` et pour sept grandeurs (dispersion, maturité, fécondité, tolérance à l'ombre, L d'Ellenberg, croissance et survie des semis sous couvert), ce que la littérature publie et où, pour que le contrat `params/regeneration` (mission 060) ne porte que des termes qui existent.
- **Décision éclairée :** les termes et les sources de `params/regeneration.parquet` (plan `docs/plans/m5a.md` §3 ; contrat `contracts/tables/params/regeneration.schema.json`), dans le cadre des réponses de Pascal du 26/11/2026 (journal l. 323-325) :
  - Q1 : passage calé sur le flux IFN, borné par le stock de semis ;
  - Q2 : stock initial « en régime » (flux IFN × temps de passage) ;
  - Q3 : survie par la seule lumière et la tolérance à l'ombre.
- **Fichier tabulaire :** `docs/referentiels/regeneration.csv`, 195 lignes de données aux passes 1 à 3, **206 avec la quatrième passe** (11 lignes ajoutées en fin de fichier, §13). Les 195 sont :
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
| **Suárez-Muñoz et al. 2021 (Frontiers)** | « Creative Commons Attribution License (CC BY) », copyright 2021 des auteurs (`frontiers_article.html:92`) | Article **CC BY confirmé** ; Data Sheet 1 obtenu à la quatrième passe : **aucune licence dite dans le document** (§13). |
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
| 52 | *Pinus sylvestris* | **lu, non recopiée** (D07-1, D11) ; manquant (S1) | **lu, non recopiée** (M06) | absent (F05) ; TreeMig lu hors dépôt (D06-TP2) | **lu** (T01-52) ; **lu, non recopiée** (T03, T10) ; résumé (T04, T08) | hors dépôt | résumé (G03) ; **lu, non recopiée** (G05, G08-G10) | résumé (S03) ; **lu, non recopiée** (S07) |
| 58 | *Pinus mugo* subsp. *uncinata* | manquant (S1) | manquant | manquant | **lu, synonyme à valider** (T01-58) ; résumé (T08) | hors dépôt | résumé (G03) | résumé (S03) |
| 62 | *Picea abies* | manquant (S1) | manquant | résumé* (F02) | **lu** (T01-62) ; résumé (T04) | hors dépôt | — | — |
| 05 | *Quercus pubescens* | manquant (S1) | manquant | manquant | **lu** (T01-05) ; résumé (T07) | hors dépôt | résumé (G01) | résumé (S01) |
| 15S | *Acer pseudoplatanus* | manquant (S1) | manquant | manquant | **lu** (T01-15S) ; résumé (T06) | hors dépôt | résumé (G02) | résumé (S02) |
| 17C | *Fraxinus excelsior* | manquant (S1) | manquant | manquant | **lu** (T01-17C) ; résumé (T06) | hors dépôt | résumé (G02) | résumé (S02) |
| 15P | *Acer platanoides* | **lu : classe 4** (D01-15P) | manquant | manquant | **lu** (T01-15P) | hors dépôt | — | — |
| 14 | *Robinia pseudoacacia* | **lu : classe 7, ou 4 sans l'homme** (D01-14) | manquant | manquant | **lu** (T01-14) | hors dépôt | — | — |
| 57A | *Pinus halepensis* | **lu, non recopiée** (D07-1) ; manquant (S1) | **lu, non recopiée** (M06) | absent (F05) | **lu** (T01-57A) ; **lu, non recopiée** (T03, T10) | hors dépôt | — | — |
| 69JC | *Juniperus communis* subsp. *communis* | **lu, non recopiée** (D07-1) ; manquant (S1) | **lu, non recopiée** (M06) | absent (F05) | **lu** (T01-69JC) ; **lu, non recopiée** (T03, T10) | hors dépôt | — | — |
| 06, 07, 51, 53CA, 53CO, 53S, 54, 33N, 69JO | essences du tableau 2 de Frontiers | **lu, non recopiée** (D07-1) ; manquant (S1) | **lu, non recopiée** (M06) | absent (F05) | **lu** pour 06, 54 ; **lu, rang espèce à valider** pour 33N, 53CA, 53CO, 53S ; **absent** de Niinemets pour 07, 51, 69JO, mais valeur d'emprunt au Data Sheet 1 (T10, **lu, non recopiée**) | hors dépôt | — | — |
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
| **Data Sheet 1, Suárez-Muñoz et al. 2021 (obtenu à la passe 4, §13)** | dispersion, maturité, tolérance pour 10 essences : 06, 07, 33N, 51, 52, 53*/54, 57A, 69JC, 69JO, et *Q. faginea* | le lien redirige vers `public-pages-files-2025.frontiersin.org`, refusé par le proxy (trois essais) | D07, M02, T03 |
| **Thèse HAL de Gaudio (tel-00587487) (obtenue à la passe 4, §13 ; D05, Amm 2012, reste manquant)** | croissance des semis de pin sylvestre selon la lumière | `hal.inrae.fr` et `hal.science` servent un défi anti-robot, non contourné ; `api.archives-ouvertes.fr` est refusé par le proxy | G05 (et D05, Amm 2012, sur HAL aussi) |
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

## 13. Quatrième passe : Data Sheet 1 de Frontiers et thèse de Gaudio (déposés par Pascal le 26/11/2026)

### 13.1 Ce qui a été lu, et les droits

| Document | Pages lues | Droits lus dans le document | Conséquence |
|---|---|---|---|
| `frontiers_Data_Sheet_1.pdf` (21 p.) | les 21 | **aucune licence dite** : ni Creative Commons ni copyright (seul le logo Frontiers, p. 13 et 15). Le CC BY de la page de l'article (`frontiers_article.html:92`) ne vise que l'article. | Valeurs **lues, non recopiées**, comme Niinemets. Le CC BY du Data Sheet est **non confirmé** (question n° 12). |
| `gaudio_these_tel-00587487.pdf` (197 p. ; pagination imprimée = pagination du PDF moins 1) | sommaire ; partie 2 (article 1, p. 87-104) ; partie 4 (p. 135-147) ; partie 5 (p. 149-162) ; chapitre V §2 (p. 164-168) ; résumé final | **aucune licence Creative Commons dite** : la page de garde porte seulement le logo « Autorisation HAL » (« HAL Authorization »). | Valeurs **décrites, non recopiées**. Une seule citation courte, p. 156, pour comparer les distances de dispersion. |

Non lu dans la thèse : chapitre II (état de l'art), chapitre III (matériel et méthodes), partie 1 (concept RReShar), partie 3 (articles 2 et 3, pépinière sous ombrières, sur la callune, la molinie et la fougère), bibliographie. Le sha256 et la taille sont ceux de la consigne : cette passe n'a pas de shell et rien n'a été recalculé (`INDEX.md`).

### 13.2 Paramètres « manquant » : lu, absent ou à valider

| Paramètre | Source | État | Où |
|---|---|---|---|
| Dispersion, 10 essences | Data Sheet 1 | **lu, non recopiée**. **À valider** : valeurs d'emprunt (pin de Sierra Nevada pris sur *P. sylvestris* d'Écosse, genévriers sur une espèce nord-américaine), « effective distance » non définie | tableau S2 p. 4 ; sources p. 5 (D07-1) |
| Dispersion, pin sylvestre | thèse de Gaudio | **lu** : une phrase, valeur reprise de deux sources non lues ; la thèse n'a acquis aucune donnée | p. 156 (D11) |
| Maturité, 10 essences | Data Sheet 1 | **lu, non recopiée**. **À valider** : c'est un âge ; le texte dit « decreased » pour les *Pinus* | tableau S2 p. 4 (Sex Mat) ; p. 5 (M06) |
| Âge par classe de diamètre | Data Sheet 1 | **lu, non recopiée** (nouveau) | Table S1, p. 1-3 (M07) |
| Fécondité | Data Sheet 1 ; thèse | **absent** : « Veg. Repr. Prob » est un rejet de souche ; la thèse n'a pas de donnée | p. 4-6 ; p. 156 (F05) |
| Tolérance à l'ombre, 10 essences | Data Sheet 1 | **lu, non recopiée** : paramètre HalfSat, **dérivé de Niinemets** (pas une source indépendante) | tableau S2 p. 4 ; p. 6 (T03, T10) |
| Croissance des gaules et des semis, pin sylvestre | thèse de Gaudio | **lu, non recopiée** : régressions sur la lumière, un site | p. 94, 96 (G08) ; p. 140-146 (G09) ; p. 158 (G10) |
| Survie des semis, pin sylvestre | thèse de Gaudio | **lu, non recopiée**. **À valider** : la lumière explique peu cette survie | p. 141, 146, 164-165 (S07) |
| Mortalité par la lumière | thèse de Gaudio | **absent** comme taux : « La mortalité n'a pas été quantifiée » ; une hauteur critique, seuil présumé de mort | p. 159 (G10) |
| Dispersion, Amm et al. 2012 (D05) | — | **toujours manquant** : article distinct, pas dans la thèse | — |

### 13.3 Ce que disent les documents (sans valeurs recopiées)

- **Data Sheet 1.**
  - Il porte le paramétrage de LANDIS-II PnET-Succession pour 10 essences et 3 groupes d'arbustes : tableau S2 (p. 4-5), définitions et sources (p. 5-7), tableau S1 d'âge par classe de taille (p. 1-3), figures de simulation et de croissance (p. 8-17), références (p. 18-21).
  - Dispersion, maturité et tolérance sont lues. Aucune fécondité, aucune croissance ni survie de semis.
  - Les valeurs sont presque toutes **d'emprunt** : Écosse pour la dispersion des pins, espèce nord-américaine pour les genévriers, valeur de *Q. ilex* pour la maturité des trois chênes, valeurs de *P. nigra* ou moyenne de quatre chênes pour la tolérance de *P. pinaster* et de *Q. pyrenaica*. Les auteurs l'écrivent p. 5 et 6.
  - Les pins sont des plantations de Sierra Nevada : la longévité et la maturité sont ajustées pour en tenir compte.
- **Thèse de Gaudio.**
  - Elle repose sur un site (forêt d'Orléans, sol pauvre, peuplements mixtes chêne sessile-pin sylvestre) et une essence.
  - Elle donne la croissance et la survie du pin sylvestre selon la lumière relative, pour les gaules de 0,4 à 6 m (article 1) et les semis de deux ans plantés (partie 4).
  - Son apport principal est une **dimension critique** : la hauteur maximale atteinte augmente avec la lumière (tableau 2 p. 96 ; p. 98-99). Ce seuil est présumé de mort, non observé (p. 99).
  - La partie 5 en tire des équations pour RReShar (p. 158-159). Elles ne sont pas une seconde source : ce sont les régressions des parties 2 et 4.

### 13.4 Comparaison avec les sources déjà lues

| Sujet | Résultat | Accord ou écart |
|---|---|---|
| Tolérance : HalfSat contre Niinemets (7 taxons communs) | même ordre, du chêne vert au pin d'Alep | **accord attendu** : HalfSat dérive de Niinemets (p. 6), ce n'est pas un contrôle |
| Tolérance : TreeMig (`klighs`, TreePars2.txt) contre Niinemets | même ordre pour sapin, hêtre, épicéa, chênes, pin sylvestre, pin à crochets | **accord**, avec deux petites inversions (tremble contre chêne pubescent ; épicéa contre sapin et hêtre) |
| Tolérance du pin sylvestre : Gaudio contre Niinemets | tous deux disent la lenteur à l'ombre ; Gaudio dit que le pin survit et pousse sous faible lumière, et que sa tolérance dépend de la taille | **accord sur le rang, écart d'usage** : un indice unique ne dit pas ce seuil de taille |
| Dispersion du pin sylvestre : Frontiers, Gaudio, Lososová, TreeMig | Frontiers : centaine de mètres (efficace) et de l'ordre du kilomètre (maximale) ; Gaudio : quinzaine de mètres ; TreeMig : même valeur que Frontiers ; Lososová, si la classe est 4 : 40 m à 50 % et 150 m à 99 % | **écart** : facteur de l'ordre de 7 entre Gaudio et Frontiers/TreeMig ; la distance maximale de Frontiers dépasse la classe 4. Accord Frontiers/TreeMig non indépendant : les deux sont des conventions de modèle. |
| Dispersion du peuplier noir : Frontiers, TreeMig | même ordre de grandeur, à moins d'un quart près | **accord** |
| Dispersion des chênes : Frontiers, Lososová | quelques centaines de mètres ; classe 6 si c'est la leur (classe non lue) | **à vérifier dans S1** |
| Maturité du pin sylvestre : Frontiers, TreeMig, Gaudio | âge d'environ vingt ans, hauteur de quelques mètres, quelques mètres au plus à 15 ans sous couvert | **non comparable** sans dérivation (âge, hauteur, diamètre) |
| Survie des semis : Gaudio contre TreeMig (S05) et le cadre de Q3 | pour le pin, la lumière explique peu la survie ; végétation concurrente et attaques biotiques dominent | **écart** avec une survie par la seule lumière |
| Fécondité | aucune source nouvelle | **absent** |

Couverture : TreeMig (TreePars2.txt) couvre 30 essences d'Europe centrale. Frontiers couvre les essences méditerranéennes. Ils ne se recouvrent que pour le pin sylvestre et le peuplier noir. Ni l'un ni l'autre ne couvre *P. uncinata* (58). La thèse ne couvre que le pin sylvestre.

### 13.5 Corrections à des phrases des passes précédentes

- §5.1 et §8 disaient le Data Sheet « manquant » : il est lu.
- Le CSV disait les paramètres TreeMig « non obtenus » alors que `TreePars2.txt` était dans `INDEX.md` depuis la seconde passe : il est lu à cette passe, pour comparaison, valeurs non recopiées (ligne `D06-TP2`). Les lignes `D06`, `M01`, `F01`, `T02`, `G06`, `S05` gardent « manquant » : elles visent le fichier du starter kit, dont ce modèle n'est pas prouvé identique.
- Le Data Sheet ne donne pas la tolérance de *Q. faginea* (hors `species.csv`) comme valeur propre : elle vaut celle de *Q. pyrenaica* (même moyenne de chênes).

### 13.6 Questions de sens pour Pascal (non tranchées ; l'orchestrateur les pose une par une, à la suite des n° 1 à 11)

12. **Droits : le Data Sheet et la thèse ne disent aucune licence. Les lire hors dépôt, comme Niinemets (question n° 2) ?**
    - Contexte : le CC BY lu vise l'article, pas le Data Sheet. La thèse n'a que le logo « Autorisation HAL ».
    - Proposition : même réponse que la question n° 2 : clé `external.*` avec le sha256, aucune valeur dans le dépôt. Si Pascal veut recopier, lire d'abord les conditions de la page Frontiers du Data Sheet, ou écrire à Frontiers et à l'autrice.
    - Ce que change la réponse : sans recopie, `params/regeneration` cite ces valeurs sans les porter ; avec, le contrat porte 10 lignes de dispersion, de maturité et de tolérance.
13. **Survie du semis de pin sylvestre : garder Q3 (la lumière et la tolérance seules), alors que la thèse dit que la lumière explique peu cette survie et que la végétation concurrente et les attaques biotiques dominent ?**
    - Contexte : une essence, un site, deux ans de semis plantés, année sèche (p. 141, 146, 164-165).
    - Proposition : garder Q3 et inscrire cette limite dans le rapport de `params/regeneration`, sans terme de recouvrement du sous-bois, faute de source pour les autres essences.
    - Ce que change la réponse : la survie sous couvert des pins peut être surestimée sous un sous-bois de callune, molinie ou fougère.
14. **La dimension critique de Gaudio (hauteur maximale selon la lumière, tableau 2 p. 96 ; p. 159) : s'en servir comme contrôle indépendant de la survie du pin sylvestre (52), lu hors dépôt ?**
    - Contexte : seuil présumé de mort, non observé ; un site ; ne vaut que pour cette essence.
    - Proposition : contrôle seulement, pas un terme du contrat.
    - Ce que change la réponse : un test sur 52 qui n'existerait pas sinon.
15. **Maturité : le Data Sheet donne un âge, TreeMig une hauteur, le contrat un diamètre (complète la question n° 8). Quelle grandeur retenir ?**
    - Contexte : la Table S1 du Data Sheet (M07) relie classes de diamètre et âge pour dix espèces, en Sierra Nevada. La conversion par cette table serait une dérivation hors France.
    - Proposition : la hauteur, comme à la question n° 8, sans conversion.
    - Ce que change la réponse : les valeurs de Frontiers ne servent que si l'on garde l'âge ou convertit.
16. **Essences absentes de Niinemets (07, 51, 69JO) : accepter la règle d'emprunt du Data Sheet (complète la question n° 4) ?**
    - Contexte : *Q. pyrenaica* reçoit une moyenne de quatre chênes ; *P. pinaster* la valeur de *P. nigra* (constat sur le tableau, la règle n'est pas écrite pour lui) ; *J. oxycedrus* celle du genévrier commun. Ce sont des règles d'auteurs, pas des mesures ; les auteurs jugent leurs tolérances trop hautes.
    - Proposition : ne pas les accepter (code 2), comme à la question n° 4.
    - Ce que change la réponse : trois essences du Sud gardent une valeur ou un arrêt de `simulate`.
17. **Dispersion du pin sylvestre : quelle ancre, avec trois nombres qui diffèrent d'un facteur de l'ordre de 7 (Gaudio, Frontiers/TreeMig, Lososová) ?**
    - Proposition : les classes de Lososová (question n° 9), une fois S1 obtenu ; Gaudio et Frontiers en contrôle, vérifiés au sol (point au sol n° 1 ci-dessous).
    - Ce que change la réponse : la portée de la recolonisation en trouée pour le pin.

### 13.7 Trois points au sol (passe 4)

1. **Distance de dispersion du pin sylvestre, en lisière de trouée.**
   - Relever la distance des semis de l'année au plus proche semencier de pin.
   - L'écart à vérifier : une quinzaine de mètres selon Gaudio, une centaine selon Frontiers et TreeMig.
2. **Survie des semis de pin sous sous-bois de callune, molinie ou fougère, avec et sans végétation.**
   - Compter les semis vivants à lumière comparable, avec et sans végétation concurrente.
   - La thèse trouve une survie moyenne bien plus basse avec végétation, et peu d'effet de la lumière seule. Le terrain dira si Q3 tient.
3. **Âge de première fructification du pin sylvestre et du pin d'Alep (52, 57A).**
   - Relever l'âge et le diamètre du plus jeune arbre portant des cônes, en peuplement et non en plantation.
   - Le Data Sheet fixe un âge pour des plantations de Sierra Nevada et le dit ajusté. Le contrat attend un diamètre.

### 13.8 Question de contrôle

*Quelle décision cette donnée va-t-elle éclairer ?* Les termes, les sources et les droits des paramètres de dispersion, de maturité, de croissance et de survie des semis dans `params/regeneration` (mission 060). Elle dit aussi ce que la thèse de Gaudio retire à Q3 (survie par la lumière et la tolérance seules) pour le pin sylvestre.

### 13.9 Ligne de journal proposée

`2026-11-26 · acquereur · 059 (quatrième passe) · lus Data Sheet 1 de Frontiers (21 p., aucune licence dite) et thèse de Gaudio (parties 2, 4, 5, chap. V ; seule la mention « Autorisation HAL ») ; valeurs non recopiées ; Frontiers : dispersion, maturité et tolérance (HalfSat, dérivé de Niinemets) pour 10 essences, valeurs d'emprunt, aucune fécondité, croissance ni survie ; Gaudio : croissance et survie du pin sylvestre selon la lumière, un site, la lumière explique peu la survie des semis (écart avec Q3), mortalité non quantifiée ; dispersion du pin : écart d'un facteur d'environ 7 entre Gaudio et Frontiers/TreeMig ; TreePars2.txt lu pour comparaison ; D05 (Amm 2012) toujours manquant ; CSV 206 lignes ; 6 questions pour Pascal (n° 12 à 17).`

### 13.10 Liste de contrôle

**Aucune liste de contrôle n'était jointe à la consigne de cette passe.** J'ai passé les trois points génériques de ma fiche.

1. **Sources et emplacements : coché, avec réserves.** Chaque ligne ajoutée donne le fichier local, la page imprimée (thèse) ou la page du PDF (Data Sheet), et le sha256 abrégé. Non coché : sha256 et tailles repris de la consigne (aucun shell, rien recalculé) ; plus de la moitié de la thèse non lue (§13.1).
2. **Décomptes complets : coché.** 21 pages sur 21 du Data Sheet ; 10 essences et 3 groupes d'arbustes au tableau S2 ; 11 lignes ajoutées au CSV (206 en tout) ; 30 essences dans `TreePars2.txt`. Non coché : la liste des essences de la thèse (une seule) ne vaut pas décompte.
3. **Termes exacts : coché.** `HalfSat`, `Sex Mat`, `Effect. Seed Disp.`, `Max Dist.`, `Veg. Repr. Prob`, « dimension critique », « Autorisation HAL », `minmat`, `maxseed`, `alfa1`, `dispFac`, `klighs` repris tels quels.

## 14. Cinquième passe (27/11/2026, mission 079) : licence de TreePars et tolérance à l'ombre `klighs`

**Décision éclairée :** comment passer l'ombre des semis de `simulate` (extinction × couvert, comparée à la tolérance de Niinemets 0-5) à l'échelle de TreeMig (décision de Pascal du 27/11/2026), et à quelles conditions on peut reprendre les valeurs. Aucun fichier nouveau n'est lu : `envidat_starter-kit_package_show.json`, `TreePars2.txt`, `SpecParsMeanings.pdf` et `TreeMigDocu_251218_Model.pdf` étaient déjà dans `INDEX.md`. Pages du PDF citées par leur rang dans le PDF (comme les passes précédentes). Lignes ajoutées au CSV : `L01`, `L02`, `L03`, `T02-KL`, `T02-LUM`, `T02-ESP`.

### 14.1 Les trois licences

| Objet | Mot pour mot | Emplacement | Portée |
|---|---|---|---|
| **Code FORTRAN de TreeMig** | « This FORTRAN code is available on request, under licence CC-BY-NC-SA 4.0 » | `treemig_framework.html:478` (CSV `L03`) | le code seul ; NC : rien n'en est repris |
| **Jeu de données EnviDat « Starter Kit for the TreeMig framework v1 … »** (DOI 10.16904/envidat.533, version 1.0, publié en 2024) | `"license_id": "cc-by-sa"` ; `"license_title": "Creative Commons Attribution Share-Alike (CC-BY-SA)"` ; `"license_url": "https://creativecommons.org/licenses/by-sa/4.0/"` ; `"isopen": true` | `envidat_starter-kit_package_show.json`, champs `result.license_id`, `result.license_title`, `result.license_url`, `result.isopen` (CSV `L01`) | le **jeu** entier. Aucune des 7 ressources n'a de champ de licence. Le zip `tmenvandinputdata.zip` (1 612 103 870 octets) « contains … species parameters (in folder P) » d'après la description de la ressource. La version 4.0 se déduit de l'URL ; le titre ne la dit pas. |
| **Fichier `TreePars2.txt`** (celui qu'on a lu) | **aucune licence dite** : ni ligne de commentaire dans le fichier (31 lignes), ni `LICENSE` dans le dépôt GitLab, ni dans son `DESCRIPTION` (champ laissé au texte du gabarit R) | `TreePars2.txt` ; `treemig_gitlab_DESCRIPTION` ; `INDEX.md` seconde passe (CSV `L02`) | rien ne dit que ce fichier du GitLab est un fichier du zip EnviDat : **identité non établie** |

Reste étranger à tout cela : « All data are available under the Creative Commons license CC BY 4.0 » (`treemig_details.html:883`) vise les scénarios CH2018 (déjà corrigé en §1).

### 14.2 Ce que la licence permet (à lire avec les réserves)

- **Lire hors dépôt par une clé `external.*`** : aucun obstacle de licence, puisque rien n'est redistribué. Il faut seulement que le fichier soit fourni pour rejouer (règle des 30 minutes) : un fichier de 4 311 octets, ou le dossier P du zip.
- **Recopier des valeurs dans un dépôt GPL-3 public** :
  - la licence qui s'applique est CC-BY-SA, **à condition** que le fichier recopié soit bien un fichier du jeu EnviDat. Pour `TreePars2.txt` du GitLab, ce n'est **pas établi** (L02). Pas de recopie tant que le dossier P du zip n'a pas été lu et comparé (URL en §14.6).
  - Une fois établie : CC-BY-SA 4.0 exige la mention des auteurs (Lischke, Schmatz, Psomas, Böhm, Scherrer, WSL), du titre, de la licence avec son lien, du DOI, et l'indication des modifications ; les adaptations restent sous CC-BY-SA (partage dans les mêmes conditions). Les valeurs recopiées resteraient donc **sous leur propre licence** dans le dépôt, avec une mention en tête du fichier : elles ne passent pas en GPL-3 par le seul fait d'être dans le dépôt.
  - **Compatibilité avec la GPL-3 : non vérifiée ici.** Je crois que Creative Commons tient la CC BY-SA 4.0 pour compatible avec la GPLv3 dans un seul sens (une adaptation de matériel BY-SA 4.0 peut être publiée sous GPLv3), mais je n'ai pas pu lire la page (creativecommons.org n'est pas joignable de cette session). À lire avant de trancher.
  - Un jeu de valeurs numériques peut ne pas relever du droit d'auteur : je ne le tranche pas.

### 14.3 `klighs` : signification et unité

- **Définition :** « Sapling light parameter: shadetolerant [1] to shade-intolerant [9] » (`SpecParsMeanings.pdf` p. 1, qui l'écrit `lighs`). La colonne « Unit » est vide : **classe ordinale sans unité**, de 1 (tolérante) à 9 (intolérante). Les valeurs du fichier sont des entiers de cet intervalle.
- **`kligha`** : même échelle pour les arbres adultes (« Adult light parameter … »).
- **Tableau 1 (Docu p. 19) :** « Shade tolerance young | - | Class [1,9], for establishment » (`klighs`) ; « Shade tolerance adults | - | Class [1,9], for growth and survival » (`kligha`).
- **Usage réel :** la p. 15 (sous l'éq. 35) dit que les semis de la classe de hauteur 0 vivent comme les arbres, la seule différence étant le paramètre de lumière ; la p. 17 (sous l'éq. 43) pose `shadesens = klighs` pour la classe 0 et `kligha` pour les classes 1 et plus. Donc `klighs` sert à l'installation, mais aussi à la croissance et à la mortalité des semis, ce que le tableau 1 ne dit pas.
- **Sens inverse de Niinemets** (0 à 5, 5 = tolérante). Les deux ordres concordent (passe 4, `D06-TP2`).
- **À ne pas confondre :** `sType/N`, échelle 1-5, « shading capability low [1] to high [5] » (SpecParsMeanings) ou « Foliage type » (tableau 1) : autre grandeur (écart n° 7 du §4).
- **Où sont les valeurs :** colonne `klighs` de `TreePars2.txt`, lignes 2 à 31. **Non recopiées** (L02).

### 14.4 Classes de lumière et ombre d'une cellule dans TreeMig

Source : `TreeMigDocu_251218_Model.pdf`, §1.2.3.2.1 (p. 6 à 8), éq. (3) à (9) ; CSV `T02-LUM`.

1. **Grandeur :** la lumière relative *l* entre 0 et 1 (1 = pleine lumière), par classe de hauteur *i* (0 à 15 ; la classe 0 est celle des semis) et par **classe de lumière** ξ = 0 à 9 : **10 classes** (éq. 8, p. 8 ; éq. 36, p. 15). Les bornes des 10 classes ne sont pas dans les pages lues.
2. **Indice foliaire au-dessus de la classe *i* :** somme, sur toutes les essences, des feuilles des arbres des classes plus hautes, divisée par la taille de la placette ζ = **833 m²** (éq. 4, p. 7).
3. **Distribution :** les arbres sont répartis au hasard dans la placette ; Poisson approchée par une loi normale ; l'indice foliaire est une variable normale (éq. 5). Le document imprime l'éq. (5) avec une racine sur la moyenne de l'indice : cela ressemble à une coquille, à vérifier dans Lischke et al. 2006 (non lu).
4. **Extinction :** Beer-Lambert, *l* = exp(−α × indice foliaire), α étant le coefficient d'extinction des feuilles (éq. 6, p. 8). **La valeur de α n'est pas dans les pages lues.**
5. **Lumière-seuil de l'essence :** tirée de `klighs` (éq. 29, p. 14) par une loi à deux branches, selon que `klighs` atteint 5 ou non ; plus `klighs` est haut, plus la lumière exigée est haute.
6. **Mortalité de stress :** par classe de lumière, 0 si la borne basse de la classe dépasse le seuil, 1 si la borne haute est sous le seuil, une fraction entre les deux (éq. 39, p. 16) ; multipliée par une constante du modèle (éq. 40, déjà reprise comme terme `stress_mortality`). Résultat moyenné sur les 10 classes pondérées par leur fréquence (éq. 8, 52).
7. **Croissance et vitalité :** fonction continue de la lumière, interpolée entre deux formes extrêmes selon `klighs` (éq. 30 et 43), puis racine cubique avec les facteurs degrés-jours, sécheresse et azote (éq. 42, p. 16).

Les constantes des équations ne sont pas recopiées : la licence de la documentation n'est pas dite.

### 14.5 Correspondance avec `contracts/species.csv`

Détail ligne par ligne dans le CSV `T02-ESP` (lignes 2 à 31 de `TreePars2.txt`). **30 essences, 30 codes**.

| Cas | Nombre | Codes |
|---|---|---|
| même nom latin (orthographes anciennes *Fagus silvatica*, *Pinus silvestris* comprises) | 22 | 61, 62, 59, 52, 67, 21C, 15P, 15S, 13G, 12V, 11, 10, 31, 09, 17C, 24, 05, 02, 25B, 23AB, 20P, 20G |
| code d'une sous-espèce pour un nom d'espèce | 5 | 63, 13B, 33N, 03, 23SO |
| synonyme à valider | 3 | 60 (*Pinus montana* pour *P. mugo*), 37 (*Alnus viridis* pour *A. alnobetula*), 18M (*Ulmus scabra* pour *U. glabra*) |
| **absent** de TreePars2.txt | **165 des 195 codes** | dont 58 (*P. uncinata*, pas de ligne propre), 06, 07, 08S, 51, 53CA, 53CO, 53S, 54, 55, 57A, 65, 66, 69, 69JC, 69JO, 14, 12P, 19, 36, 29AF, 68CE |

Contre Niinemets : 140 taxons lus (§2) ; TreeMig en couvre 30. Le sud méditerranéen n'a aucun `klighs`.

### 14.6 Ce que cela demande au moteur (`simulate/src/semis.rs`)

**Aujourd'hui :** `ombre = light_extinction_coef × indice de couvert` (indice = surface des houppiers projetés ÷ surface de la cellule) ; stress si `ombre > shade_tolerance` (Niinemets, 0-5, haut = tolérante) ; une seule classe de lumière par cellule (éq. 39 réduite à 0 ou 1).

**Lecture :** si l'indice de couvert tient le rôle d'un indice foliaire, « ombre > seuil » revient à « exp(−ombre) < exp(−seuil) » : le moteur compare déjà une lumière à un seuil, mais le seuil est exp(−classe de Niinemets), pas la loi de `klighs`. C'est une lecture de ma part, pas un texte.

**Grandeurs nécessaires pour l'échelle TreeMig :**
1. `klighs` par essence (1-9, sens inverse), et la loi lumière-seuil de l'éq. (29) ; le seuil est une lumière relative, pas une classe de tolérance.
2. Une lumière relative *l* au niveau des semis : exp(−α × indice foliaire des arbres plus hauts).
3. Pour cela, un indice foliaire, donc une surface foliaire par arbre (allométries de l'éq. 10-12, coefficients posés dans `GetSpc`, non lus), et α.
4. Une règle pour la distribution de *l* dans la cellule : 10 classes avec la loi de l'éq. 3-9, ou une classe unique (cas actuel). Les cellules de la grille SER font 25 m (625 m²), la placette de TreeMig 833 m².
5. Le sens inverse change les bornes du validateur (`shade_tolerance` ≥ 0 dans `semis.rs`) et le contrat `params/regeneration` (échelle et source du terme). Je n'y touche pas.

**Ce qui manque :**
- `klighs` pour 165 codes sur 195 (30 couverts) ; les 140 de Niinemets n'ont pas d'équivalent sans règle de passage (question ci-dessous) ;
- α, les bornes des classes de lumière, les coefficients d'allométrie foliaire (pages non lues, ou dans le code non obtenu) ;
- la surface foliaire des arbres dans les sorties de nemeton (je n'ai pas lu les contrats : à demander à l'orchestrateur) ;
- la confirmation du fichier (L02) avant toute recopie.

### 14.7 Questions de sens pour Pascal (non tranchées ; l'orchestrateur les pose une par une, à la suite des n° 1 à 17)

18. **Échelle de l'ombre : `klighs` de TreeMig (30 essences) ou Niinemets (140 taxons), éventuellement passé à l'échelle 1-9 par une règle écrite et provisoire ?**
    - Proposition : garder Niinemets comme source du contrat, `klighs` en contrôle sur 30 essences (même ordre, passe 4). Une règle de passage serait une dérivation, à écrire seulement si Pascal la veut.
    - Ce que change la réponse : couverture (30 contre 140), sens de l'échelle, et la loi du seuil du moteur.
19. **Recopier les `klighs` dans le dépôt sous CC-BY-SA, ou les lire hors dépôt (clé `external.*`) ?**
    - Proposition : hors dépôt tant que le dossier P du zip n'est pas lu et comparé à `TreePars2.txt`, et tant que la compatibilité CC-BY-SA 4.0 / GPL-3 n'est pas lue. Même réponse que les questions n° 2 et 12.
    - Ce que change la réponse : un fichier de plus à fournir pour rejouer, ou une mention de licence distincte dans le dépôt.
20. **L'ombre sous couvert : indice foliaire (comme TreeMig, avec α et une surface foliaire par arbre) ou couvert projeté des houppiers (comme aujourd'hui) ?**
    - Ce que change la réponse : de nouvelles grandeurs à fournir par nemeton, ou un seuil qui reste une convention du modèle.

### 14.8 URL à télécharger (réseau autorisé, mais ce `WebFetch` ne les voit pas)

Ce `WebFetch` n'a pas résolu `envidat.ch`, `gitlabext.wsl.ch` ni `creativecommons.org` ; je n'ai pas de shell. À télécharger :
1. Dossier P du zip du starter kit (pour comparer à `TreePars2.txt` et lire d'éventuels fichiers de licence ou de lisez-moi) : `https://envidat.ch/dataset/516d259a-3b10-419c-a033-980bedf6ade1/resource/5eef16d1-80af-442b-9da2-f64b4fa94671/download/tmenvandinputdata.zip` (1,6 Go ; l'URL du JSON porte `www.envidat.ch`, refusé en passe 2) ; si le serveur accepte les requêtes `Range`, ne lire que le dossier P.
2. Tutoriel du starter kit : `https://envidat.ch/dataset/516d259a-3b10-419c-a033-980bedf6ade1/resource/a1dec65a-30ba-4688-90ac-50df5db73d4c/download/treemig_tutorial_2025-05-02.pdf` (2,1 Mo) ; et `…/resource/3db8ca57-2838-4b26-82a9-9770b75b7096/download/readme_descriptioninputdata.pdf` (263 Ko).
3. Notice EnviDat « Code of TreeMig Package version 1 » (CC-BY-SA d'après `INDEX.md`, non relue) : `https://envidat.ch/api/action/package_search?q=treemig`.
4. Texte de la CC BY-SA 4.0 et page de compatibilité avec la GPL-3 : `https://creativecommons.org/licenses/by-sa/4.0/` ; `https://creativecommons.org/share-your-work/licensing-considerations/compatible-licenses/` (hôte à autoriser).
5. Arbre du GitLab, autres fichiers TreePars : `https://gitlabext.wsl.ch/boehmd/treemig/-/tree/main/inst/extdata`.
6. Lischke et al. 2006, *Ecological Modelling* 199 : 409-420 (déjà cité en `D06`), pour l'éq. (5) et les constantes de lumière, source citable à la place de la documentation.

### 14.9 Trois points au sol

1. **Un semis de hêtre (09) et de sapin (61) sous couvert dense de hêtraie-sapinière.** `klighs` les classe tous deux du même côté, tolérants (milieu bas de l'échelle) ; relever s'ils survivent sous un couvert très fermé, et à quelle lumière relative (mesure au fisheye).
2. **Un semis de pin sylvestre (52) sous chêne, en limite de tolérance** (comme chez Gaudio) : `klighs` le classe intolérant, mais la thèse dit qu'il survit sous faible lumière : voir quelle hauteur de semis tient.
3. **Pin à crochets (58) : pas de ligne propre dans TreeMig** (seulement *Pinus montana*, 60). Comparer, en montagne, la survie sous couvert de 58 et de 52 : c'est le cas où le synonyme et la source décident.

### 14.10 Question de contrôle

*Quelle décision cette donnée va-t-elle éclairer ?* Le passage de l'ombre des semis à l'échelle de TreeMig et le droit de reprendre ses valeurs (questions n° 18 à 20).

### 14.11 Ligne de journal proposée

`2026-11-27 · acquereur · 079 · licence : code TreeMig CC-BY-NC-SA 4.0 (rien repris) ; jeu EnviDat du starter kit CC-BY-SA (license_id cc-by-sa, URL 4.0, niveau dataset, aucune ressource ne porte de licence) ; TreePars2.txt du GitLab : aucune licence dite, appartenance au zip EnviDat non établie, valeurs non recopiées ; compatibilité BY-SA/GPL-3 non lue (creativecommons.org injoignable) ; klighs : classe 1 (tolérante) à 9 (intolérante), sans unité, sens inverse de Niinemets ; lumière relative en 10 classes (Beer-Lambert sur un indice foliaire, placette de 833 m²) ; 30 essences = 30 codes (22 noms identiques, 5 infraspécifiques, 3 synonymes), 165 codes absents ; regeneration.{md,csv} (212 lignes), questions n° 18 à 20.`

### 14.12 Liste de contrôle

**Aucune liste de contrôle n'était jointe à la consigne de cette passe.** Trois points génériques de ma fiche.
1. **Sources et emplacements : coché, avec réserves.** Licences citées avec fichier et champ ou ligne ; pages du PDF données par rang dans le PDF. Non coché : `WebFetch` n'a atteint aucun hôte, donc rien de nouveau n'a été téléchargé ; CC BY-SA 4.0 / GPL-3 non lu ; version 4.0 déduite de l'URL ; je n'ai pas relu `TreeMigDocu_23_Code.pdf` ni `InfosSettingsControlFileAndGUI.pdf` au-delà des pages de la passe 3 (α peut y être).
2. **Décomptes complets : coché.** 30 lignes de `TreePars2.txt` = 22 + 5 + 3 ; 195 − 30 = 165 absents ; CSV : 212 lignes de données.
3. **Termes exacts : coché.** `klighs`, `kligha`, `lighs`, `ligha`, `sType/N`, « Sapling light parameter: shadetolerant [1] to shade-intolerant [9] », `license_id`, `license_title`, `license_url`.


## 15. Sixième passe (27/11/2026, mission 083) : correspondance Niinemets → klighs et loi lumière-seuil (éq. 29)

**Décision éclairée :** comment obtenir un `klighs` (1 à 9, TreeMig) pour les 140 taxons lus dans Niinemets (0 à 5), afin de passer l'ombre des semis de M5b à la forme de TreeMig (décisions de Pascal du 27/11/2026 : Niinemets en tolérance, `klighs` lu hors dépôt pour l'ajustement seulement, correspondance provisoire, erreur dite). **Aucune valeur de `klighs` ni de Niinemets par essence n'entre au dépôt** ; seuls la méthode, l'effectif, les coefficients et l'erreur. Le détail par essence est écrit hors dépôt (`data/sources/regeneration/derive/`) par le script.

### 15.1 Méthode et rejeu

- Script : `bench/m5b/correspondance_klighs.py` (`python3 -I bench/m5b/correspondance_klighs.py`, numpy et scipy). Il lit hors dépôt l'annexe A de Niinemets, `TreePars2.txt` et la documentation de TreeMig, **vérifie leurs sha256 de `data/sources/regeneration/INDEX.md` et refuse de tourner** si un fichier manque ou diffère.
- Appariement par **code de `contracts/species.csv`** : la correspondance T02-ESP (§14.5), 30 essences, 30 codes, chacune avec sa ligne Niinemets. Les 30 sont appariées des deux côtés.
- **Jeu principal : 27 essences** (22 au même nom, dont 52 et 09 par orthographe ancienne, et 5 sur un code infraspécifique : 63, 13B, 33N, 03, 23SO, ramenées au rang de l'espèce). **Analyse de sensibilité : 30**, avec les 3 synonymes à valider (60, 37, 18M), qui ne sont **pas** dans l'ajustement principal tant que Pascal n'a pas tranché la question n° 3.
- Trois modèles, tous monotones : **régression linéaire**, **régression isotone** (PAV, non croissante), **logistique bornée à [1, 9]** (`klighs = 1 + 8 / (1 + exp(-(a + b·N)))`). Erreur : RMSE d'ajustement, résidu maximal, et validation croisée par exclusion d'une essence (RMSE et résidu maximal hors échantillon).

### 15.2 Résultats (27 essences ; entre parenthèses, 30 essences avec les 3 synonymes)

| Modèle | Coefficients | RMSE | résidu max | RMSE par exclusion d'une essence | résidu max par exclusion |
|---|---|---|---|---|---|
| **linéaire** | pente -1,238 ; ordonnée 9,091 (30 : -1,311 ; 9,328) | 1,01 (0,99) | 2,46 (2,43) | **1,09 (1,05)** | 2,56 (2,52) |
| isotone | 8 paliers (30 : 9) | 0,86 (0,86) | 2,29 (2,29) | 1,21 (1,19) | 2,67 (2,67) |
| logistique bornée | a = 2,148 ; b = -0,649 (30 : 2,289 ; -0,693) | 1,01 (0,99) | 2,44 (2,41) | 1,09 (1,06) | 2,55 (2,51) |

- Corrélation de rang de Spearman entre Niinemets et `klighs` : -0,75 (27) ; -0,73 (30). Le sens est inverse, comme prévu (§3).
- Les valeurs de Niinemets du jeu principal vont de 1,46 à 4,60 (26 valeurs distinctes) ; celles de `klighs`, de 2 à 8 (7 classes). La correspondance n'est donc **pas testée** hors de 1,5 à 4,6 (aucune essence de tolérance Niinemets très basse ou très haute) : les extrapolations sont à dire au rapport.
- **Essences les plus mal prédites** (par exclusion d'une essence, linéaire, par code) : **59, 15P, 17C, 25B, 62** (mêmes cinq pour la logistique ; l'isotone ajoute 31 avec les 30). Résidu maximal d'environ 2,5 classes : **la correspondance donne la classe à ± 1 classe en moyenne quadratique, et jusqu'à ± 2,5 pour les cas extrêmes.**

### 15.3 Choix : la régression linéaire (provisoire)

- L'isotone ajuste mieux (0,86) mais **généralise moins bien** (1,21 contre 1,09 par exclusion d'une essence) : elle épouse le bruit sur 27 points et 7 classes. La logistique bornée **ne gagne rien** (RMSE identiques à 0,01 près) parce que les données restent au milieu de l'échelle : la borne n'est jamais active sur l'intervalle ajusté.
- La droite a deux coefficients, est monotone par construction, se lit sans ambiguïté et se rejoue. **Règle d'emploi :** `klighs = clamp(9,091 - 1,238 × N, 1, 9)` avec N la tolérance de Niinemets (0 à 5), **provisoire** (`provisoire: true`), à signaler au rapport (« klighs dérivé de Niinemets, erreur ± 1,1 classe »). Le résultat est **continu** : `klighs` n'est pas entier (TreeMig attend une classe entière dans le fichier, mais les deux branches de la loi ci-dessous acceptent une valeur réelle ; à confirmer dans le code de TreeMig, non lu).
- Ce qui peut changer le choix : une réponse de Pascal sur les 3 synonymes (le jeu à 30 donne -1,311 et 9,328, écart de 0,1 à 0,3 classe), ou l'arrivée des `klighs` d'autres essences (165 codes sur 195 n'en ont pas) pour valider hors échantillon.

### 15.4 Loi lumière-seuil de TreeMig (Docu p. 14, après l'éq. 29)

Lue dans `TreeMigDocu_251218_Model.pdf` p. 14 (sha256 dans INDEX.md). La loi **n'a pas de numéro propre** : elle suit l'éq. (29) de l'établissement β_s et précède l'éq. (30) ; le document la rattache à la routine `GetSpc`. Avec `shadesens_sap,s = klighs` de l'essence s (p. 17, sous l'éq. 43) :

- `l_thresh = 0,1 × klighs − 0,4` si `klighs ≥ 5` ;
- `l_thresh = max(0, 0,025 × (klighs − 1))` si `klighs < 5`.

`l_thresh` est une **lumière relative** (0 à 1, 1 = pleine lumière). La loi est **continue** en `klighs = 5` (0,1 des deux côtés) ; elle va de 0 (`klighs` = 1) à 0,5 (`klighs` = 9). Elle sert ensuite, dans le même passage, à l'éq. (30) : `f_Lgerm(l) = gl1 + (l_thresh − 1)/8 × (gl9 − gl1)`, interpolation entre deux formes extrêmes de lumière (`gl1` et `gl9`, exponentielles saturantes ; constantes imprimées p. 14, **non recopiées ici**). Les bornes des 10 classes de lumière et le coefficient d'extinction `alpha` **ne sont pas dans les pages lues** (voir T02-LUM).

- **Réserve de droits :** la documentation de TreeMig ne dit aucune licence dans les pages lues (§14.1). Les constantes de la loi (0,1 ; 0,4 ; 0,025 ; 5) sont recopiées parce que la mission les demande et qu'elles décrivent la **forme**, non une valeur d'essence ; Pascal peut demander de les retirer (question n° 21).
- **Ce qui manque** : les classes de lumière (bornes) et `alpha` ; le code de `GetSpc` (non lu) pour savoir si `klighs` est arrondi avant l'emploi ; la mesure qui justifie la forme (Lischke et al. 2006, non lu) ; aucune validation hors des 30 essences.

### 15.5 Question de sens pour Pascal (une seule, n° 21)

**Les constantes de la loi p. 14 (0,1 ; 0,4 ; 0,025 ; seuil 5) peuvent-elles figurer dans le dépôt, la documentation de TreeMig n'ayant pas de licence dite ?** Proposition de l'IA : oui, ce sont des constantes d'une forme publiée et citée avec sa page, au même titre que les formes d'éq. (13) à (49) déjà décrites. Si non, M5b les lit hors dépôt, comme `klighs`.

### 15.6 Ligne de journal proposée

`2026-11-27 · analyste · 083 · correspondance Niinemets → klighs (bench/m5b/correspondance_klighs.py, sha256 vérifiés) : 30 essences appariées par code, 27 dans le jeu principal (3 synonymes à valider en sensibilité) ; linéaire retenue, klighs = clamp(9,091 − 1,238 N, 1, 9), RMSE 1,01, 1,09 par exclusion d'une essence, résidu max 2,5 classes, codes les plus mal prédits 59, 15P, 17C, 25B, 62 ; isotone et logistique bornée n'améliorent pas hors échantillon ; non testée hors N de 1,5 à 4,6 ; loi p. 14 : seuil = 0,1 klighs − 0,4 (klighs ≥ 5), max(0, 0,025 (klighs − 1)) sinon ; manquent bornes des classes de lumière et alpha ; question n° 21 (constantes au dépôt).`

## 16. Septième passe (27/11/2026, mission 084a) : classes de lumière, alpha, arrondi de klighs, mortalité de stress

**Mission redite :** relever dans les 5 PDF de TreeMig déjà téléchargés quatre faits (bornes des 10 classes de lumière ; coefficient d'extinction alpha ; arrondi de klighs dans GetSpc ; comparaison seuil/classes en mortalité de stress). **Décision éclairée :** la forme du moteur des semis de M5b (reprise de la forme de TreeMig : lumière relative par classe, seuil tiré de klighs, mortalité de stress). Pages citées par leur rang dans le PDF (aucune page imprimée dans ces documents). Lignes CSV : `T02-CLS`, `T02-ALP`, `T02-RND`, `T02-STR`.

### 16.1 Ce qui a été lu

| Fichier | Pages lues cette passe |
|---|---|
| `TreeMigDocu_251218_Model.pdf` (24 p.) | 5 à 9, 14 à 24 (les pages 10 à 13 : lues aux passes 3 et 5) |
| `TreeMigDocu_23_Code.pdf` (9 p.) | 1 à 9 (tout) |
| `InfosSettingsControlFileAndGUI.pdf` | 1 à 16 (la fin du fichier n'a pas été demandée ; le tableau des réglages va jusqu'à la p. 10, puis ce sont des pages d'interface graphique et de tracés) |
| `SpecParsMeanings.pdf` | p. 1 (unique) |
| `TreeMigPackageRoxygenDoku.pdf` | 1 à 12, 29-30, 45-46 (non lu : 13 à 28, 31 à 44, 47-48 ; enveloppe R) |
| `treemig_details.html:665` | la ligne sur `writeLightDistr` |

### 16.2 Les quatre faits

| N° | Question | Réponse | Page, équation | État |
|---|---|---|---|---|
| 1 | Bornes des 10 classes de lumière : égales ? lesquelles ? | **Absentes.** Le texte dit : « light intensity was discretized into 10 light classes ξ » (Docu p. 8, après l'éq. 7). L'éq. (8) somme ξ = 0 à 9 avec l_ξ et l_ξ+1 (donc 11 bornes, déduit). L'éq. (39) p. 16 utilise « the upper and lower bounds of the current light class, l_low and l_up ». Aucune valeur, aucune règle de largeur (égale ou non), aucun sens de ξ. | Docu p. 8 éq. (8)-(9) ; p. 15 éq. (36) ; p. 16 éq. (39) ; Code, Infos, SpecPars, Roxygen lus : rien | absent |
| 2 | Coefficient d'extinction α : valeur, unité, grandeur | **Valeur absente. Unité non écrite.** Grandeur : **l'indice foliaire** (LAI), l_i = exp(−α · LAI_i), LAI_i = −ln(l_i)/α. LAI_i = somme de (surface foliaire par arbre × nombre d'arbres) des classes de hauteur plus hautes, ÷ 833 m² (éq. 4). LAI en m²/m², « double sided leaf area index » (Infos p. 10). Comme α multiplie un indice foliaire sous une exponentielle, il est sans dimension (déduction, non écrite). | Docu p. 8 : « α the extinction coefficient of leaves », éq. (6), (7), (9) ; p. 7 éq. (4) | forme lue ; valeur absente |
| 3 | klighs arrondi ou utilisé tel quel dans la loi lumière-seuil (GetSpc) ? | **Le texte ne le dit pas.** Les équations impriment `shadesens = klighs` sans arrondi ni partie entière : 0,1·klighs − 0,4 si klighs ≥ 5 ; max(0 ; 0,025·(klighs − 1)) sinon. Elles sont continues (0,1 en 5). Le tableau 1 dit « Class [1,9] ». Le Code p. 2 renvoie à GetSpc sans le détailler. Un éventuel arrondi serait dans le code FORTRAN, non lu. | Docu p. 14 (loi sous l'éq. 29), p. 17 éq. (43), p. 19 tableau 1 ; Code p. 2 étape 4 | absent (arrondi) ; formules lues |
| 4 | Comment la mortalité de stress compare le seuil aux classes | La lumière-seuil de l'essence est comparée aux **bornes** de chaque classe de lumière, non à une lumière moyenne. Brute : **0** si l_low > l_thresh ; **1** si l_up < l_thresh ; **(l_thresh − l_low)/(l_up − l_low)** si l_low < l_thresh ≤ l_up. Puis × **0,184** (éq. 40). Résultat moyenné sur les 10 classes, pondérées par F(l_ξ+1) − F(l_ξ). | Docu p. 16 éq. (39)-(40) ; p. 5 éq. (1) ; p. 8 éq. (8) ; p. 18 éq. (52) | lu |

Écarts et réserves relevés dans le document (détail dans les lignes du CSV) :
1. **Homonyme.** `alpha` du fichier de contrôle (Infos p. 6, exemple 200 m, « mean dispersal distance ») est le noyau de dispersion. Ce n'est pas l'extinction. Aucun réglage de contrôle n'est nommé extinction : la valeur est sans doute posée dans le code (hypothèse).
2. **Éq. (30) p. 14 :** elle s'écrit (l_thresh − 1)/8, alors que l_thresh va de 0 à 0,5 ; l'éq. (43) p. 17 écrit (shadesens − 1)/8. Coquille probable, que la ligne `T02-L29` (§15.4) n'avait pas relevée. À vérifier dans Lischke et al. 2006 ou dans le code.
3. **Éq. (39) :** « if if » imprimé ; le cas l_low = l_thresh n'est couvert par aucune ligne (inégalités strictes en lignes 1 et 3). La fraction donnerait 0 : la forme est continue.
4. **Texte p. 15 contre éq. (39) :** le texte dit que la mortalité de stress agit « if vitality (42) is reduced below 10% by these factors ». L'éq. (39) ne compare que la lumière-seuil aux bornes. Le lien entre les deux n'est pas écrit. Le texte ajoute une mortalité liée à la croissance (« the more severe of both is chosen »), sans équation dans ces pages.
5. **Agrégation.** `facvar` (Infos p. 2 point 22, p. 8 : `fcvarInit`, `fcvarDyn`) règle la largeur de la distribution de la lumière ; « normalement 1 » (répartition aléatoire). L'éq. (5) du Docu ne le montre pas.
6. **Cohérence avec l'existant :** §14.4 (points 1, 4, 6) et `T02-L29` restent justes ; cette passe confirme que les pages lues ne portent ni bornes de classes ni α. Aucune constante de plus n'est recopiée : 0,184 l'était déjà (décision du 27/11/2026).

### 16.3 Ce que cela change pour le moteur (à titre d'information, l'IA ne tranche pas)

- **Sans les bornes ni α, la forme complète ne peut pas être reprise telle quelle** : la mortalité de stress par classe (éq. 39) exige l_low et l_up.
- Pour M5b, une classe unique par cellule (cas actuel, §14.6) n'a besoin que d'une borne : la lumière de la cellule, comparée à l_thresh. Ce qui reste de l'éq. (39) est alors un 0 ou un 1, sans la fraction.
- α reste le seul coefficient à poser pour passer d'un indice foliaire à une lumière relative. Tant qu'il est absent, il se pose par un fichier de paramètres `provisoire: true`, avec sa source dite absente. Pascal tranche.

**Suite (mission 084b, 27/11/2026) :** la forme de TreeMig (loi lumière-seuil, correspondance du §15, comparaison par classe de l'éq. 39, × 0,184) est reprise dans `simulate/src/semis.rs` avec des classes de lumière de largeur égale et une seule lumière par cellule (décisions de Pascal du 27/11/2026) ; voir l'ADR 0006, choix 13. Les dix constantes sont des termes de `params/regeneration` (contrat 0.4).

### 16.4 URL à télécharger, sans présumer de leur contenu

Aucun fichier n'a été téléchargé à cette passe (pas de shell). Une recherche web a donné les adresses suivantes, **non ouvertes** :
1. Lischke et al. 2006, *Ecological Modelling* 199 : 409-420 : citation confirmée par la liste de références du Docu (p. 22). **DOI non trouvé** ; à chercher sur ScienceDirect ou Crossref. Une notice existe sur `https://data.zhenzhi.com/details/1/906762281` (non ouverte).
2. Version « 23 » de la documentation du modèle, peut-être plus ancienne ou plus détaillée : `https://treemig.wsl.ch/fileadmin/user_upload/WSL/Microsite/TreeMig/TreeMigDocu_23_Model.pdf`. Rien n'indique qu'elle porte α ni les bornes.
3. Tutoriels WSL : `https://treemig.wsl.ch/fileadmin/user_upload/WSL/Microsite/TreeMig/TreeMig_Tutorial.pdf` et `https://treemig.wsl.ch/fileadmin/user_upload/WSL/Microsite/TreeMig/TreeMig_Tutorial_2025-08-25.pdf`.
4. Tutoriel EnviDat du starter kit (déjà en §14.8, point 2) : `https://envidat.ch/dataset/516d259a-3b10-419c-a033-980bedf6ade1/resource/a1dec65a-30ba-4688-90ac-50df5db73d4c/download/treemig_tutorial_2025-05-02.pdf`.
5. Page de description du modèle : `https://treemig.wsl.ch/en/core-model/`.
6. Code FORTRAN de `GetSpc` et `Lfcalc` : sur demande aux auteurs (CC-BY-NC-SA 4.0, `treemig_framework.html:478`). C'est la seule source sûre de l'arrondi de klighs, de α et des bornes.

### 16.5 Corrections faites au CSV et au md

- **Ligne T03 (CSV l. 173) :** elle avait **15 colonnes au lieu de 14**. La cause : le champ `unite_ou_echelle` contenait une virgule non protégée (« … « to allow their growth under the canopy »), plus l'essence est tolérante … »), qui le coupait en deux. Je l'ai entouré de guillemets. Rien d'autre n'a changé dans la ligne.
- **En-tête du md (l. 4) :** le décompte disait 212 lignes ; le fichier en comptait 214 avant cette passe (C01 et T02-L29 de la mission 083 n'étaient pas comptées). Il dit maintenant 218.
- Je n'ai pas de shell : le nombre de colonnes des autres lignes n'a pas été recompté ; seules les quatre lignes ajoutées et T03 ont été comptées à la main (14 chacune).

### 16.6 Trois points au sol (passe 7)

1. **Lumière sous un couvert dense de hêtraie-sapinière (09, 61).** Mesurer au fisheye la lumière relative au niveau des semis. C'est la grandeur que l'éq. (6) tire de α × indice foliaire : l'écart entre la mesure et exp(−α × LAI) dira quel α est plausible. Sans α publié, c'est la seule vérification possible.
2. **Cellule de 25 m en lisière de trouée.** La lumière y varie d'un mètre à l'autre (placette TreeMig de 833 m², cellule SER de 625 m²). Relever la part de la cellule sous un seuil de lumière donné : c'est ce que la fraction de l'éq. (39) calcule, et ce qu'une classe unique par cellule perd.
3. **Seuil de survie d'un semis de pin sylvestre (52) sous chêne.** la loi p. 14 donne, pour un klighs élevé (intolérant), une lumière-seuil jusqu'à 0,5 de lumière relative (klighs = 9) ; Gaudio dit que le pin survit plus bas (§13). Relever la lumière minimale où les semis vivants persistent. C'est le cas où le seuil de la forme TreeMig et la mesure peuvent diverger.

### 16.7 Question de contrôle

*Quelle décision cette donnée va-t-elle éclairer ?* La forme du moteur des semis de M5b : ce qu'on peut reprendre de TreeMig tel quel (loi du seuil, comparaison par classe, 0,184) et ce qu'il faut poser à part, faute de source lue (bornes des classes, α, arrondi de klighs).

### 16.8 Ligne de journal proposée

`2026-11-27 · acquereur · 084a · TreeMig, 5 PDF relus (Docu 24 p., Code 9 p., Infos 16 p., SpecPars 1 p., Roxygen 17 p. sur 48) : bornes des 10 classes de lumière absentes (10 classes, ξ = 0 à 9, l_low et l_up à l'éq. 39 p. 16, éq. 8 p. 8 ; ni valeurs ni largeurs) ; α = coefficient d'extinction des feuilles sur l'indice foliaire (LAI, éq. 4 p. 7, éq. 6 p. 8), valeur absente, unité non écrite ; « alpha » du fichier de contrôle = noyau de dispersion, homonyme ; klighs sans arrondi dans les équations (p. 14, 17), arrondi éventuel dans GetSpc non lu ; éq. 30 p. 14 écrit (l_thresh − 1)/8 contre (shadesens − 1)/8 éq. 43, coquille probable ; mortalité de stress : seuil comparé aux bornes de chaque classe, 0 / 1 / fraction, × 0,184 (éq. 39-40 p. 16) ; CSV : T03 corrigée (15 → 14 colonnes), 4 lignes ajoutées (T02-CLS, T02-ALP, T02-RND, T02-STR), 218 lignes, en-tête du md corrigé (212 → 218) ; valeurs manquantes : code FORTRAN ou Lischke et al. 2006, URL au md §16.4.`

### 16.9 Liste de contrôle

**Aucune liste de contrôle n'était jointe à la consigne.** Trois points génériques de ma fiche.
1. **Sources et emplacements : coché, avec réserves.** Chaque fait donne le fichier, la page et l'équation. Non coché : Roxygen p. 13-28, 31-44 et 47-48 non lues ; Infos au-delà de la p. 16 non lues ; sha256 non recalculés (pas de shell, ceux de `INDEX.md` sont repris) ; aucune URL de §16.4 ouverte.
2. **Décomptes complets : coché, avec réserves.** 10 classes, 11 bornes (déduit) ; 218 lignes = 214 comptées + 4 ; 4 faits sur 4 traités. Non coché : colonnes des autres lignes du CSV non recomptées.
3. **Termes exacts : coché.** « the extinction coefficient of leaves », « light intensity was discretized into 10 light classes », `shadesens`, `l_thresh`, `l_low`, `l_up`, « Class [1,9] », `writeLightDistr`, `facvar`, `estabEqHC0`, `contLightDepGerm`.
