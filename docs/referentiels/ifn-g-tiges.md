# IFN : ordres de grandeur de la surface terrière et des tiges/ha (critère M3b)

- **Propriétaire :** Pascal
- **Date de consultation :** 2026-11-26
- **Mission redite :** donner des bornes sourcées de G (m²/ha) et de tiges/ha des peuplements français, d'après l'IFN. Il faut deux sources : un calcul par placette sur les données brutes DataIFN, et les résultats publiés par l'IGN.
- **Décision éclairée :** (1) les bornes du critère M3b (`docs/spec.md` §11, ligne M3 : « surface terrière et tiges par hectare entre les quantiles 5 et 95 % de l'IFN ») ; (2) les ordres de grandeur pour recaler le jeu fictif. Aujourd'hui, ce jeu part de 91 m²/ha et monte à 352 m²/ha en 100 ans (`docs/spec.md` §6, l. 224 ; `tests/m3/reference/nominal.json`).
- **Fichier tabulaire :** `docs/referentiels/ifn-g-tiges.csv`. Une ligne par (périmètre, peuplement, grandeur, statistique), avec la source, l'effectif, la période, l'URL et la page.
- **Script :** `tools/referentiels/ifn_g_tiges.py` (Python, bibliothèque standard seule). Écrit par l'acquéreur, **exécuté pour la première fois le 2026-11-26 (mission 058)** sur l'export DataIFN du 07/10/2026. Le script réécrit ses propres lignes dans le CSV et garde celles des autres sources. Test : `tools/referentiels/tests/test_ifn_g_tiges.py`, lancé par la section `contrats` de `tools/ci/run_tests.sh`.
- **Règle suivie :** aucune valeur de mémoire. Chaque nombre du CSV a été lu à la page citée, ou compté sur le fichier cité. Les seuls calculs de l'acquéreur sont les Dg tirés des moyennes publiées (§4) et les comptes de `grep` (S3) ; ils sont signalés comme tels.

## 0. État en une phrase

**Les quantiles 5-95 % sont calculés (mission 058)** : sur 28 089 placettes de 2021-2025 portant au moins un arbre vivant recensable, G va de **3,8 à 50,3 m²/ha** (médiane 23,6) et les tiges de **96 à 1 778 /ha** (médiane 602), France entière ; par GRECO et par SER au §3.3 et au §3.4. Les moyennes non pondérées du calcul sont proches des moyennes publiées : 727 tiges/ha contre 687 ± 9 pour l'IGN en 2021-2025 (+6 %, écart de champ expliqué au §4) ; 24,9 m²/ha contre 23,7 ± 0,2 pour l'IGN en 2009-2013 (l'IGN ne publie pas G pour 2021-2025). Les bornes de M3b restent à **choisir par Pascal** (§7, Q1 à Q3) : le référentiel les donne, il ne les fixe pas.

*Avant le 2026-11-26, ce paragraphe disait : « Les quantiles 5-95 % demandés ne sont pas encore calculés » ; ce qui suit l'a été écrit dans cet état et reste valable pour S2 et S3.*

## 1. Sources, versions, accès

| Id | Source | Version, date | Licence | Accès dans cette session |
|---|---|---|---|---|
| S1 | **DataIFN, données brutes** : `export_dataifn_2005_2025.zip` (`PLACETTE.csv`, `ARBRE.csv`) | mise à jour du 07/10/2026 ; dernière campagne 2025, donc dernière période de 5 campagnes **2021-2025** | « Licence Ouverte / Open Licence Etalab Version 2.0 » (page DataIFN) | page lue (https://inventaire-forestier.ign.fr/dataifn/). **Archive téléchargée le 2026-11-26 (mission 058)** sous `data/ifn/export_dataifn_2005_2025.zip`, hors dépôt : 71 136 669 octets, SHA-256 `be583e7eb01d43d4e74cc46097b8900092f1dcbfbe355c0ee3080001157c5b70`, membres datés du 07/10/2026 (`metadonnees.csv` : « Export des données brutes du 2026-10-07 ») ; en-tête HTTP `last-modified` du 24/11/2026 |
| S1-doc | Documentation DataIFN locale (dossier `ifn_doc_2025/`, hors dépôt) | `IGN_DB_documentation_generale.pdf` v3.0 du 14/10/2025 ; `metadonnees.csv` | Etalab 2.0 | lue : documentation générale p. 1-9 en entier ; `metadonnees.csv` aux lignes ESPAR1, CSG13, DOM1M0, DOM8M2, GRECO, PEUPNR ; `recapitulatif_donnees.csv` en entier |
| S2 | **IGN, Résultats standards, tome national « La France par zonage écoforestier », campagnes 2009 à 2013** | sans date imprimée ; période 2009-2013 | **non lue** (aucune mention vue dans les pages ouvertes) | lu en image : couverture, sommaire, p. 106-107, 112-113, 119, 124-125 (https://inventaire-forestier.ign.fr/IMG/pdf/RS_0913_FR_GRECO.pdf) |
| S3 | tarif-nemeton (Pascal) : `resultats/etage_b/ifn_placettes.csv`, G/ha et N/ha par placette, calculés sur l'export IFN 2005-2023 | fichier local, LISEZMOI du 29/09/2026 | dépôt sans licence (voir `volume-carbone.md` §1) | lu en partie : en-tête et lignes extraites par `grep` |
| S4 | Tableaux standards 2021-2025 (France, GRECO, SER), ZIP de xlsx | fichiers créés le 07/07/2026 (France) et le 08/07/2026 (GRECO), d'après l'onglet « Lisez-moi » et l'archive | non lue | **ouverts le 2026-11-26 (mission 058)**, rangés sous `data/ifn/ts_2021-2025/` : https://inventaire-forestier.ign.fr/IMG/zip/ts_2021-2025_france-2.zip (`TS_2021-2025_Tiges.xlsx`, `…_Surface`, `…_Volume`, `…_Flux`) et `…/ts_2021-2025_greco.zip` (un ZIP par GRECO, mêmes classeurs). **Ils ne publient pas la surface terrière** : seuls les tiges/ha (onglets « BV … ») se comparent au calcul (§4) |

**Hôtes bloqués** (erreur `getaddrinfo ENOTFOUND`, hôtes hors des domaines permis de la session) :
- `draaf.nouvelle-aquitaine.agriculture.gouv.fr` (« kit données PRFB », section Surface terrière) ;
- `www.ign.fr` (mémento 2024).

Après ce second blocage, comme la consigne de l'outil le demande, je n'ai plus essayé de nouvel hôte : ni `www.calameo.com` (mémentos 2025 et 2026), ni `inventif.ign.fr`, ni `ocre-gp.ign.fr`. Seul `inventaire-forestier.ign.fr` répondait. Le mémento 2024 et la publication « La forêt française » 2012-2016 dépassent 10 Mo, la taille maximale que l'outil peut lire.

## 2. CQQCOQP de chaque source

| | S1 DataIFN, calcul par placette (script) | S2 Résultats standards IGN 2009-2013 | S3 Fontainebleau (tarif-nemeton) |
|---|---|---|---|
| **Pourquoi** | bornes q05-q95 de M3b, par placette, à l'échelle d'une cellule | ordre de grandeur moyen, par GRECO et par composition ; recalage du jeu fictif | contrôle local de la queue de distribution |
| **Qui, dans quel but** | IGN, enquête statistique IFN (labellisée CNIS) ; données brutes mises en ligne pour l'analyse (S1-doc p. 1-2) | IGN, statistique officielle par zonage | Pascal, calage LiDAR × IFN (étage B) |
| **Quoi** | arbres recensables (C13 ≥ 0,235 m), poids `W` par arbre, par placette | moyennes à l'hectare (estimateurs d'inventaire, avec IC), forêt de production | G_ha et N_ha par placette ; définition dans `code/etage_b_ifn.py`, non relue |
| **Comment** | placettes concentriques de 6, 9 et 15 m ; `W` = 88,4, 39,3 ou 14,1 tiges/ha selon la classe, corrigé en lisière (S1-doc p. 9) | même dispositif, plus poids de point et post-stratification (non publiés : S1-doc p. 2) | même dispositif, sans poids de point |
| **Où** | France métropolitaine, 11 GRECO, 86 SER | France, 11 GRECO, SER | 221 placettes à moins de 12 km de Fontainebleau (B41 surtout) |
| **Quand** | campagnes 2021-2025 (novembre n-1 à octobre n) | campagnes 2009-2013 | campagnes 2005-2023 |
| **Combien** | environ 6 000 points forêt levés par an (S1-doc p. 3) ; effectif en VISITE = 1 inconnu avant exécution. Coût : un téléchargement et une exécution | IC à 95 % publiés : ± 0,2 m²/ha et ± 9 à 10 tiges/ha pour la France | 221 placettes, une seule région |

**Deux sources qui se tromperaient pour des raisons différentes.**
- S1 se tromperait par l'**absence de poids de point** : les quantiles par placette ne sont pas des estimations d'inventaire (S1-doc p. 2 : « ne peuvent absolument pas permettre de recalculer des résultats d'inventaire »). Elle se tromperait aussi par la **convention de type** de l'acquéreur, qui classe sur la part de G et non sur le couvert.
- S2 se tromperait par sa **période** (2009-2013, avant les tempêtes et les sécheresses récentes) et parce qu'elle publie des **moyennes** et non des quantiles.
- S3 se tromperait par sa **zone** (un massif).

## 3. Résultats

### 3.1 Tableau résumé (France et grands types)

Tableau mis à jour le 2026-11-26 (mission 058) : la dernière colonne donne S1 (2021-2025, calcul par placette non pondéré, types selon la convention de l'acquéreur), sous la forme « q05 / médiane / q95 (effectif) ». Les types de S1 ne recouvrent ceux de S2 qu'à peu près (§6).

| Périmètre ou type (S2, 2009-2013) | G moyen (m²/ha) | Tiges/ha moyennes | Dg tiré des deux moyennes (cm, calcul de l'acquéreur) | Médiane, q05, q95 (S1) |
|---|---|---|---|---|
| France, forêt de production (tab. 7.3 et 8.3) | 22,0 ± 0,2 | 723 ± 9 | 19,7 | `toutes_placettes` : G 2,3 / 23,2 / 50,1 ; N 68 / 585 / 1 768 (28 799) |
| France, couvert recensable (tab. 7.7 et 8.6) | 23,7 ± 0,2 | 778 ± 10 | 19,7 | `tous_types` : G 3,8 / 23,6 / 50,3 ; N 96 / 602 / 1 778 (28 089) ; Dg 10,6 / 21,9 / 45,0 cm |
| Chênaies pures : pédonculé, rouvre, pubescent, vert | 22,4 ; 24,7 ; 16,9 ; 16,2 | 574 ; 658 ; 932 ; 1 292 | — | `chenaie` : G 3,7 / 21,8 / 42,7 ; N 63 / 473 / 1 592 (5 094) ; `chenaie_sempervirente` : G 1,4 / 14,0 / 40,9 ; N 88 / 994 / 2 741 (594) |
| Hêtraie pure | 27,3 ± 1,5 | 712 ± 61 | 22,1 | `hetraie` : G 5,3 / 26,5 / 56,2 ; N 70 / 454 / 1 974 (1 047) |
| Sapinière pure ; pessière pure | 37,2 ± 2,4 ; 36,9 ± 2,7 | 702 ± 67 ; 811 ± 74 | 26,0 ; — | `sapiniere_pessiere` : G 11,3 / 37,5 / 64,2 ; N 127 / 534 / 1 496 (1 380) |
| Pinèdes pures : maritime, sylvestre, noir-laricio-Alep | 20,1 ; 24,0 ; 21,5 | 540 ; 726 ; 674 | — | `pinede` : G 2,8 / 21,7 / 50,1 ; N 71 / 495 / 1 437 (2 961) |
| Douglas pur | 32,1 ± 2,7 | 619 ± 50 | — | `douglas` : G 5,9 / 31,7 / 61,5 ; N 141 / 426 / 1 238 (606) |
| Châtaigneraie pure (souvent en taillis) | 29,6 ± 2,3 | 1 200 ± 110 | — | pas de type châtaigneraie dans S1 (le châtaignier, code 10, tombe dans `melange_ou_autre`) |
| Taillis (structure) | non lu (le tome ne donne pas G par structure) | non lu | — | `taillis` (ORI = 0 pour au moins 75 % des tiges) : G 2,4 / 21,8 / 46,7 ; N 172 / 923 / 2 476 (3 597) |
| GRECO, minimum et maximum de G | J Méditerranée 13,7 ; D Vosges 28,6 | F Sud-Ouest 603 ; K Corse 853 | — | médianes de G : J 14,2 à G 27,7 ; q95 de G : B 45,6 à K 69,0 ; q95 de N : D 1 692 à K 2 438 (§3.3) |
| **Jeu fictif, an 0 → an 100** (`nominal.json`) | **91 → 352** | **141 → 4 024** | **90,6 → 33,4** | an 0 : G au-dessus du q95 de la France (50,3) et de toutes les GRECO (69,0 au plus) ; N entre le q05 (96) et le q25 (323). An 100 : G 7 fois le q95, N plus de 2 fois le q95 (1 778) |

Dg = 100 × √(4 G / (π N)), calculé ici à partir des **moyennes** : c'est un ordre de grandeur, pas une valeur publiée. Pour le jeu fictif à l'an 0, le d130 moyen est de 88,6 cm (`somme_d130` / `lignes` = 1 246 918 / 14 080, `nominal.json`).

### 3.2 Queue de distribution locale (S3, comptée par l'acquéreur)

Sur les 221 placettes de Fontainebleau (2005-2023) :
- G : maximum **68,4 m²/ha** ; 7 placettes à 40 m²/ha ou plus (3,2 %) ; 2 à 50 ou plus ; 27 sous 10 m²/ha (12,2 %) ;
- tiges : maximum **3 006/ha** ; 2 placettes à 2 000/ha ou plus.

C'est le seul aperçu de quantiles extrêmes disponible aujourd'hui. Il vient d'un seul massif.

### 3.3 Quantiles par placette, 2021-2025 (S1, mission 058)

**Source :** S1, export du 07/10/2026, calcul de `tools/referentiels/ifn_g_tiges.py` (lignes `source = DataIFN calcul` de `ifn-g-tiges.csv`, colonne `filtre`). Campagnes 2021 à 2025, VISITE = 1, CSA 1 ou 3, PEUPNR = 0 ; arbres VEGET = 0 et C13 ≥ 0,235 m ; G en m²/ha, N en tiges/ha ; quantiles de type 7, **sans poids de point** (§4, point 4). Seuil de publication : 30 placettes. Les valeurs sont arrondies à 0,1 dans le CSV.

**Effectifs du filtre** (sortie du script, 2026-11-26) :

| Étape | Effectif |
|---|---:|
| placettes des campagnes 2021-2025 | 59 384 |
| écartées : 2e visite (VISITE = 2) | 28 027 |
| écartées : CSA hors {1, 3} (toutes en peupleraie, CSA = 5) | 679 |
| écartées : PEUPNR différent de 0 (1 : non recensable ; 2 : momentanément déboisé ; vide pour 38 placettes) | 1 647 |
| placettes retenues | 29 031 |
| écartées et signalées : un arbre vivant sans W (232 placettes, tous leurs arbres vivants sans W) | 232 |
| **placettes calculées** (`toutes_placettes`) | **28 799** |
| dont au moins un arbre vivant recensable (`tous_types`) | 28 089 |
| arbres vivants retenus | 345 274 |
| arbres non vivants écartés ; arbres vivants sans W | 32 679 ; 1 356 |

`toutes_placettes` garde les 710 placettes recensables sans arbre vivant recensable sur les cercles de mesure (G = 0) ; `tous_types` les retire. Les lignes `dg_cm` du CSV donnent le diamètre quadratique moyen ; France, `tous_types` : q05 10,6, médiane 21,9, q95 45,0 cm.

**France, par type de peuplement** (convention provisoire de l'acquéreur, en-tête du script) :

| France, peuplement | n placettes | G moy. | G q05 | G q25 | G q50 | G q75 | G q95 | N moy. | N q05 | N q25 | N q50 | N q75 | N q95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `toutes_placettes` | 28 799 | 24,3 | 2,3 | 14,1 | 23,2 | 32,8 | 50,1 | 709,1 | 67,6 | 303,3 | 584,7 | 972,6 | 1768,2 |
| `tous_types` | 28 089 | 24,9 | 3,8 | 14,9 | 23,6 | 33,1 | 50,3 | 727,0 | 95,9 | 322,6 | 602,3 | 986,6 | 1777,8 |
| `chenaie` | 5 094 | 22,2 | 3,7 | 13,9 | 21,8 | 29,3 | 42,7 | 603,4 | 63,0 | 233,4 | 472,9 | 849,1 | 1591,5 |
| `chenaie_sempervirente` | 594 | 16,4 | 1,4 | 6,0 | 14,0 | 23,5 | 40,9 | 1163,9 | 88,4 | 448,8 | 993,9 | 1679,8 | 2740,8 |
| `hetraie` | 1 047 | 28,3 | 5,3 | 18,5 | 26,5 | 36,5 | 56,2 | 652,8 | 69,9 | 218,8 | 453,8 | 864,2 | 1974,4 |
| `sapiniere_pessiere` | 1 380 | 37,8 | 11,3 | 27,5 | 37,5 | 47,5 | 64,2 | 647,3 | 127,3 | 333,4 | 534,4 | 868,5 | 1496,3 |
| `pinede` | 2 961 | 23,3 | 2,8 | 12,6 | 21,7 | 31,6 | 50,1 | 597,5 | 70,7 | 264,0 | 495,4 | 834,9 | 1437,3 |
| `douglas` | 606 | 32,5 | 5,9 | 21,5 | 31,7 | 41,8 | 61,5 | 514,1 | 141,4 | 258,5 | 425,7 | 677,9 | 1237,7 |
| `melange_ou_autre` | 16 407 | 24,8 | 4,2 | 15,1 | 23,6 | 32,8 | 49,2 | 792,3 | 130,8 | 378,4 | 672,3 | 1061,0 | 1856,6 |
| `taillis` | 3 597 | 22,7 | 2,4 | 12,0 | 21,8 | 31,1 | 46,7 | 1071,1 | 171,9 | 530,5 | 923,4 | 1453,8 | 2476,4 |

**Par GRECO** (11 sur 11, toutes au-dessus de 30 placettes ; les quantiles par GRECO et par type sont dans le CSV) :

| GRECO (`tous_types`) | n placettes | G moy. | G q05 | G q25 | G q50 | G q75 | G q95 | N moy. | N q05 | N q25 | N q50 | N q75 | N q95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 1 610 | 25,8 | 3,9 | 16,1 | 24,9 | 34,2 | 50,7 | 674,6 | 88,4 | 276,1 | 520,9 | 928,7 | 1754,1 |
| B | 6 257 | 24,3 | 4,7 | 16,0 | 23,5 | 31,3 | 45,6 | 665,2 | 88,4 | 284,4 | 539,1 | 898,3 | 1689,2 |
| C | 4 519 | 23,0 | 5,3 | 15,1 | 22,0 | 29,6 | 44,0 | 702,7 | 106,9 | 312,7 | 577,2 | 972,5 | 1681,9 |
| D | 1 162 | 30,5 | 8,1 | 21,1 | 29,3 | 39,1 | 54,9 | 677,9 | 113,2 | 308,4 | 522,5 | 923,3 | 1692,2 |
| E | 1 050 | 27,6 | 5,3 | 17,1 | 26,5 | 36,9 | 52,7 | 757,5 | 143,7 | 375,1 | 672,8 | 990,6 | 1699,8 |
| F | 3 837 | 22,3 | 3,4 | 13,1 | 21,5 | 30,0 | 44,0 | 746,1 | 93,2 | 353,6 | 636,9 | 1023,8 | 1747,6 |
| G | 5 015 | 28,9 | 4,5 | 17,2 | 27,7 | 39,1 | 57,3 | 760,6 | 116,7 | 373,3 | 652,6 | 1005,8 | 1788,5 |
| H | 1 590 | 26,9 | 3,0 | 13,6 | 25,0 | 37,8 | 58,1 | 765,0 | 95,9 | 362,2 | 639,8 | 1056,8 | 1799,1 |
| I | 985 | 26,9 | 4,2 | 16,2 | 25,7 | 36,3 | 52,0 | 740,4 | 88,4 | 319,2 | 615,3 | 984,3 | 1945,1 |
| J | 1 631 | 16,1 | 1,6 | 6,8 | 14,2 | 23,1 | 37,4 | 858,5 | 82,8 | 284,1 | 676,6 | 1237,8 | 2237,0 |
| K | 433 | 27,6 | 2,2 | 11,3 | 23,7 | 39,6 | 69,0 | 904,9 | 42,4 | 315,1 | 714,7 | 1237,8 | 2437,7 |

### 3.4 Quantiles par SER, 2021-2025 (S1)

86 SER présentes ; **85 au-dessus du seuil de 30 placettes**. F13 (12 placettes) n'est pas publiée : la ligne existe dans le CSV avec son effectif et la note « effectif < 30 : non publié ». Seule la ligne `tous_types` est calculée par SER.

| SER (`tous_types`) | n placettes | G moy. | G q05 | G q25 | G q50 | G q75 | G q95 | N moy. | N q05 | N q25 | N q50 | N q75 | N q95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A11 | 512 | 25,1 | 3,0 | 14,2 | 23,9 | 34,5 | 51,7 | 697,8 | 56,6 | 303,9 | 548,7 | 956,2 | 1838,8 |
| A12 | 147 | 27,9 | 4,6 | 18,4 | 27,1 | 36,9 | 52,8 | 668,8 | 124,2 | 261,4 | 531,3 | 966,3 | 1554,3 |
| A13 | 308 | 26,9 | 5,5 | 16,7 | 26,1 | 34,5 | 51,9 | 577,5 | 61,5 | 209,2 | 401,1 | 795,9 | 1560,6 |
| A21 | 222 | 27,8 | 4,6 | 17,0 | 25,8 | 38,3 | 55,0 | 622,9 | 107,0 | 301,0 | 510,3 | 769,4 | 1575,1 |
| A22 | 226 | 24,6 | 4,0 | 16,7 | 24,3 | 31,3 | 43,6 | 646,1 | 106,8 | 266,7 | 486,6 | 882,4 | 1668,5 |
| A30 | 195 | 23,5 | 4,0 | 15,4 | 23,0 | 32,3 | 43,0 | 862,8 | 88,4 | 372,8 | 713,2 | 1136,9 | 2094,3 |
| B10 | 462 | 24,8 | 4,4 | 15,7 | 23,9 | 32,3 | 45,7 | 585,9 | 70,7 | 222,4 | 435,9 | 818,5 | 1632,5 |
| B21 | 64 | 22,1 | 1,9 | 14,0 | 19,6 | 28,4 | 46,3 | 645,3 | 145,6 | 265,2 | 423,6 | 809,5 | 1864,3 |
| B22 | 73 | 24,0 | 7,1 | 14,6 | 23,8 | 30,8 | 42,9 | 716,1 | 87,5 | 255,0 | 532,7 | 976,8 | 2094,0 |
| B23 | 83 | 23,8 | 5,1 | 16,9 | 21,8 | 27,9 | 42,2 | 442,0 | 121,0 | 207,6 | 339,5 | 552,8 | 1037,2 |
| B31 | 116 | 27,3 | 3,5 | 16,0 | 24,3 | 37,6 | 57,2 | 718,8 | 85,4 | 266,0 | 588,1 | 924,2 | 1788,8 |
| B32 | 309 | 24,2 | 6,0 | 16,6 | 23,8 | 30,9 | 43,4 | 645,1 | 88,4 | 269,6 | 540,2 | 912,4 | 1564,2 |
| B33 | 291 | 28,3 | 5,5 | 19,6 | 27,6 | 36,0 | 51,5 | 697,9 | 115,1 | 314,5 | 549,7 | 947,7 | 1735,8 |
| B41 | 728 | 23,9 | 5,1 | 15,7 | 22,8 | 30,6 | 45,8 | 560,7 | 78,9 | 229,4 | 442,1 | 779,2 | 1372,1 |
| B42 | 422 | 23,7 | 6,9 | 15,6 | 22,6 | 30,0 | 43,6 | 643,0 | 88,4 | 318,9 | 573,8 | 838,2 | 1464,7 |
| B43 | 163 | 19,2 | 2,0 | 8,3 | 17,6 | 27,7 | 42,2 | 713,6 | 89,2 | 343,8 | 648,3 | 967,4 | 1483,2 |
| B44 | 79 | 22,9 | 4,6 | 14,2 | 22,6 | 27,4 | 51,2 | 829,6 | 223,2 | 442,0 | 746,6 | 1143,4 | 1604,1 |
| B51 | 359 | 24,5 | 6,4 | 17,0 | 23,6 | 31,3 | 43,7 | 669,7 | 134,8 | 334,4 | 559,9 | 897,9 | 1565,4 |
| B52 | 294 | 25,7 | 8,2 | 19,0 | 24,6 | 32,8 | 43,3 | 752,8 | 127,5 | 320,5 | 646,0 | 1015,5 | 1841,1 |
| B53 | 325 | 24,8 | 5,3 | 18,3 | 24,6 | 31,6 | 41,9 | 716,6 | 113,1 | 318,7 | 587,0 | 908,9 | 1933,0 |
| B61 | 331 | 26,1 | 4,1 | 16,9 | 25,1 | 34,3 | 50,6 | 684,7 | 95,9 | 317,8 | 550,8 | 886,0 | 1719,1 |
| B62 | 377 | 26,0 | 5,4 | 17,9 | 24,9 | 33,4 | 46,3 | 685,9 | 101,8 | 316,3 | 560,1 | 915,5 | 1640,3 |
| B70 | 767 | 21,6 | 4,5 | 13,7 | 21,1 | 28,2 | 40,8 | 639,3 | 82,5 | 270,2 | 514,0 | 854,6 | 1608,1 |
| B81 | 121 | 25,4 | 4,1 | 16,6 | 23,6 | 33,2 | 54,6 | 788,6 | 88,4 | 373,3 | 669,9 | 1055,2 | 1855,0 |
| B82 | 293 | 23,2 | 4,1 | 13,0 | 22,9 | 31,5 | 43,2 | 781,2 | 78,6 | 324,1 | 648,2 | 1083,7 | 1993,0 |
| B91 | 335 | 24,5 | 4,4 | 17,9 | 24,4 | 30,2 | 42,3 | 710,2 | 99,0 | 312,0 | 592,5 | 972,5 | 1768,5 |
| B92 | 265 | 24,4 | 6,6 | 18,0 | 24,0 | 30,9 | 42,3 | 686,2 | 145,8 | 353,7 | 590,8 | 852,3 | 1721,8 |
| C11 | 153 | 23,7 | 3,6 | 17,0 | 23,1 | 30,7 | 42,4 | 639,0 | 99,5 | 262,3 | 506,1 | 917,8 | 1603,8 |
| C12 | 92 | 23,9 | 11,3 | 17,4 | 23,8 | 29,7 | 38,2 | 582,1 | 120,8 | 265,0 | 455,4 | 783,3 | 1387,1 |
| C20 | 2 304 | 21,8 | 5,3 | 14,3 | 21,1 | 28,2 | 40,8 | 712,1 | 124,1 | 321,8 | 595,1 | 972,5 | 1679,9 |
| C30 | 749 | 23,6 | 4,6 | 16,1 | 22,9 | 29,9 | 44,4 | 628,2 | 88,4 | 273,4 | 491,9 | 856,6 | 1598,4 |
| C41 | 171 | 20,8 | 4,3 | 12,7 | 19,1 | 26,4 | 42,5 | 559,1 | 60,9 | 269,0 | 510,7 | 748,7 | 1335,3 |
| C42 | 86 | 25,7 | 7,5 | 18,2 | 24,1 | 31,2 | 46,5 | 542,8 | 145,0 | 251,8 | 404,1 | 790,5 | 1348,2 |
| C51 | 530 | 23,1 | 5,6 | 15,9 | 22,1 | 29,4 | 41,3 | 665,7 | 90,3 | 297,8 | 542,3 | 925,4 | 1559,1 |
| C52 | 434 | 28,1 | 5,0 | 17,5 | 26,8 | 37,0 | 53,2 | 963,4 | 134,8 | 524,7 | 874,1 | 1326,1 | 2077,5 |
| D11 | 810 | 31,7 | 8,0 | 22,1 | 30,8 | 40,6 | 56,4 | 680,2 | 113,1 | 312,2 | 533,2 | 924,9 | 1675,4 |
| D12 | 352 | 27,9 | 8,6 | 19,5 | 26,1 | 34,8 | 53,3 | 672,5 | 115,4 | 301,5 | 487,1 | 903,9 | 1741,2 |
| E10 | 531 | 24,3 | 4,8 | 14,9 | 23,4 | 31,9 | 47,7 | 811,3 | 134,0 | 412,8 | 728,3 | 1070,6 | 1792,7 |
| E20 | 519 | 31,1 | 5,9 | 20,2 | 30,3 | 40,6 | 57,6 | 702,4 | 167,0 | 361,1 | 616,5 | 900,7 | 1562,9 |
| F11 | 110 | 23,9 | 4,4 | 14,9 | 22,7 | 30,6 | 44,5 | 1123,3 | 134,7 | 528,3 | 982,3 | 1480,7 | 2496,9 |
| F12 | 154 | 23,2 | 3,2 | 13,7 | 22,2 | 32,5 | 47,6 | 1115,3 | 173,5 | 599,7 | 1060,9 | 1486,8 | 2364,4 |
| F13 | 12 | — | — | — | — | — | — | — | — | — | — | — | — |
| F14 | 113 | 26,6 | 4,7 | 17,1 | 25,9 | 35,7 | 53,4 | 974,9 | 185,4 | 512,8 | 891,5 | 1363,5 | 1956,9 |
| F15 | 531 | 24,7 | 4,7 | 14,9 | 24,2 | 33,0 | 47,1 | 863,0 | 136,8 | 442,0 | 741,0 | 1162,1 | 1926,9 |
| F21 | 756 | 19,9 | 3,0 | 12,2 | 19,2 | 27,2 | 37,8 | 647,2 | 99,0 | 304,5 | 556,4 | 972,5 | 1371,5 |
| F22 | 211 | 23,0 | 3,9 | 14,7 | 22,3 | 30,8 | 44,2 | 514,9 | 90,6 | 236,5 | 392,9 | 640,0 | 1427,5 |
| F23 | 342 | 22,4 | 3,8 | 13,0 | 21,9 | 29,6 | 44,4 | 660,8 | 80,4 | 305,0 | 580,6 | 847,7 | 1711,9 |
| F30 | 776 | 23,7 | 4,3 | 13,8 | 23,0 | 31,3 | 46,5 | 758,8 | 88,4 | 392,9 | 666,8 | 1001,9 | 1764,0 |
| F40 | 437 | 18,0 | 2,1 | 8,6 | 16,6 | 23,9 | 39,9 | 798,1 | 91,9 | 438,9 | 736,7 | 1090,4 | 1628,6 |
| F51 | 187 | 24,7 | 5,8 | 16,9 | 23,9 | 30,7 | 44,6 | 542,7 | 85,9 | 255,4 | 488,8 | 726,7 | 1277,0 |
| F52 | 208 | 22,7 | 5,2 | 13,9 | 21,7 | 30,5 | 41,9 | 613,7 | 88,4 | 290,3 | 484,3 | 888,1 | 1502,5 |
| G11 | 469 | 27,0 | 4,8 | 16,1 | 26,3 | 36,6 | 53,2 | 849,2 | 96,3 | 391,7 | 706,0 | 1104,6 | 2122,5 |
| G12 | 180 | 27,0 | 6,5 | 17,3 | 26,1 | 34,0 | 53,6 | 709,0 | 142,1 | 392,0 | 582,4 | 936,4 | 1572,6 |
| G13 | 673 | 28,4 | 6,6 | 18,3 | 27,3 | 36,4 | 52,6 | 754,9 | 141,4 | 383,1 | 660,0 | 992,8 | 1707,2 |
| G21 | 261 | 27,4 | 3,5 | 16,6 | 27,0 | 37,5 | 51,5 | 645,3 | 127,7 | 309,6 | 536,3 | 877,3 | 1446,3 |
| G22 | 933 | 32,9 | 5,2 | 19,6 | 32,0 | 43,7 | 62,2 | 749,2 | 115,3 | 390,5 | 655,0 | 1006,2 | 1696,6 |
| G23 | 302 | 28,1 | 6,5 | 18,0 | 27,2 | 35,3 | 52,7 | 659,6 | 109,8 | 304,1 | 563,6 | 834,3 | 1578,1 |
| G30 | 347 | 33,7 | 5,2 | 21,3 | 32,3 | 45,6 | 63,4 | 741,3 | 125,1 | 372,5 | 626,3 | 911,9 | 1806,9 |
| G41 | 164 | 27,3 | 2,8 | 13,4 | 25,4 | 39,5 | 56,1 | 669,0 | 145,3 | 356,9 | 628,4 | 914,3 | 1414,6 |
| G42 | 282 | 30,5 | 4,4 | 17,2 | 28,1 | 42,4 | 60,3 | 761,8 | 128,0 | 389,2 | 685,2 | 949,9 | 1729,5 |
| G50 | 448 | 28,1 | 6,4 | 17,4 | 27,1 | 36,8 | 52,1 | 738,8 | 152,8 | 393,7 | 655,0 | 972,5 | 1569,8 |
| G60 | 179 | 19,9 | 2,5 | 8,9 | 18,0 | 28,2 | 45,7 | 778,5 | 87,7 | 304,5 | 588,2 | 1228,8 | 1745,5 |
| G70 | 273 | 27,7 | 3,4 | 13,5 | 26,4 | 39,0 | 58,4 | 857,2 | 91,0 | 386,2 | 726,9 | 1152,4 | 2201,3 |
| G80 | 273 | 29,4 | 3,4 | 16,8 | 28,1 | 40,1 | 59,3 | 936,1 | 157,7 | 411,7 | 761,4 | 1237,8 | 2564,0 |
| G90 | 231 | 24,4 | 3,6 | 14,5 | 22,9 | 32,4 | 47,9 | 744,7 | 123,9 | 355,8 | 633,8 | 1012,1 | 1752,7 |
| H10 | 372 | 35,5 | 9,0 | 23,3 | 33,9 | 46,0 | 64,4 | 757,0 | 197,4 | 409,0 | 651,9 | 1066,8 | 1716,3 |
| H21 | 144 | 32,4 | 10,3 | 19,5 | 31,2 | 44,3 | 62,1 | 653,9 | 135,6 | 345,9 | 570,7 | 896,7 | 1444,6 |
| H22 | 108 | 28,2 | 2,2 | 13,2 | 27,4 | 41,1 | 56,6 | 716,9 | 74,9 | 332,2 | 622,8 | 1016,5 | 1683,0 |
| H30 | 623 | 21,2 | 2,2 | 9,7 | 18,9 | 28,8 | 47,7 | 836,3 | 88,4 | 372,0 | 710,4 | 1192,9 | 1935,2 |
| H41 | 211 | 27,3 | 2,9 | 13,9 | 27,0 | 38,9 | 53,6 | 792,4 | 92,7 | 367,8 | 662,5 | 1051,8 | 2047,5 |
| H42 | 132 | 22,0 | 2,3 | 11,7 | 21,1 | 31,6 | 42,8 | 567,5 | 58,0 | 271,7 | 499,2 | 746,5 | 1241,1 |
| I11 | 200 | 25,4 | 6,2 | 16,3 | 23,6 | 32,7 | 49,4 | 590,1 | 88,1 | 240,0 | 471,7 | 756,0 | 1496,6 |
| I12 | 138 | 27,3 | 4,1 | 15,4 | 26,8 | 39,4 | 53,1 | 759,1 | 88,4 | 417,3 | 678,6 | 1039,9 | 1771,2 |
| I13 | 60 | 24,5 | 3,8 | 13,7 | 23,8 | 31,7 | 58,2 | 1239,0 | 203,4 | 484,8 | 972,5 | 1746,1 | 2977,3 |
| I21 | 464 | 28,5 | 4,2 | 18,6 | 28,4 | 37,4 | 51,9 | 706,5 | 85,4 | 294,6 | 547,3 | 928,4 | 1916,3 |
| I22 | 123 | 24,3 | 2,6 | 14,1 | 20,8 | 34,4 | 50,2 | 848,8 | 129,1 | 414,1 | 736,6 | 1146,5 | 1777,3 |
| J10 | 312 | 15,8 | 1,2 | 6,3 | 14,2 | 22,8 | 38,6 | 1119,6 | 88,4 | 364,7 | 972,6 | 1679,8 | 2740,8 |
| J21 | 77 | 13,7 | 1,2 | 4,3 | 11,8 | 21,0 | 33,7 | 899,2 | 78,6 | 279,4 | 785,9 | 1355,6 | 2235,8 |
| J22 | 363 | 16,0 | 1,6 | 5,6 | 14,2 | 23,7 | 37,5 | 809,4 | 81,7 | 263,2 | 618,9 | 1198,9 | 2119,8 |
| J23 | 498 | 15,9 | 1,9 | 7,7 | 14,5 | 21,9 | 35,7 | 771,4 | 88,4 | 265,2 | 571,3 | 1066,5 | 2033,5 |
| J24 | 37 | 18,5 | 1,9 | 8,4 | 20,7 | 24,6 | 36,9 | 754,8 | 39,3 | 196,4 | 414,5 | 1277,0 | 2184,6 |
| J30 | 119 | 15,4 | 1,4 | 5,6 | 12,7 | 20,5 | 41,6 | 582,7 | 39,3 | 177,5 | 392,9 | 891,2 | 1808,5 |
| J40 | 225 | 18,2 | 2,6 | 9,2 | 16,2 | 26,4 | 38,2 | 917,3 | 95,4 | 397,5 | 795,7 | 1298,6 | 2244,5 |
| K11 | 107 | 17,5 | 1,7 | 6,8 | 15,0 | 24,0 | 44,7 | 947,4 | 88,4 | 353,7 | 923,4 | 1340,9 | 2145,5 |
| K12 | 208 | 33,9 | 4,9 | 17,6 | 30,5 | 46,1 | 72,8 | 869,5 | 74,6 | 332,0 | 709,4 | 1120,0 | 2687,2 |
| K13 | 118 | 25,7 | 2,2 | 9,9 | 22,5 | 37,9 | 61,0 | 928,8 | 23,0 | 216,6 | 590,9 | 1402,3 | 2510,8 |

## 4. Comparaisons et écarts

1. **Deux moyennes « France » dans le même tome : 22,0 et 23,7 m²/ha.** Ce n'est pas une erreur de mesure, c'est le champ qui diffère. Le tableau 7.7 exclut les forêts temporairement non boisées et celles dont le couvert absolu des recensables est inférieur à 15 % (note du tableau, p. 113). Il en va de même pour les tiges : 723 contre 778. **Le périmètre de M3b doit donc être choisi** (Q1).
2. **Moyenne et médiane.** S2 publie des moyennes. La distribution de G par placette est asymétrique : à Fontainebleau, 12 % des placettes sont sous 10 m²/ha et le maximum atteint 68 m²/ha. La médiane de S1 sera donc différente de la moyenne de S2, sans qu'aucune des deux soit fausse.
3. **Période : 2009-2013 (S2) contre 2021-2025 (S1).** L'écart attendu (tempêtes, scolytes, sécheresses depuis 2018) **n'est pas chiffré**. La comparaison sur la même période passera par S4 (tableaux standards 2021-2025), à ouvrir.
4. **Poids de point.** Les quantiles de S1 ne seront pas pondérés. Les points forêt sont tirés sur la grille de niveau 2, à poids égal en général. Mais les allègements de grille (S1-doc p. 9) et la post-stratification peuvent déplacer les moyennes. **Contrôle prévu** : la moyenne non pondérée de S1 (colonne `moyenne` du script) contre la moyenne de S4. L'écart toléré reste à fixer par Pascal.
5. **Jeu fictif hors d'échelle, et pourquoi.** À l'an 0, 91 m²/ha est environ 4 fois la moyenne française (22-24) et au-dessus du maximum local de S3 (68,4). Le nombre de tiges, lui, est bas : 141/ha contre 723 à 778. **L'excès de G vient des diamètres** : Dg d'environ 91 cm, contre environ 20 cm en moyenne nationale. À l'an 100, 352 m²/ha est environ 15 fois la moyenne, et 4 024 tiges/ha dépassent le maximum local de 3 006.
6. **Le douglas est le code `64`, pas `52`** (`metadonnees.csv` l. 4539 et 4554) : `52` est le pin sylvestre. Le script utilise les codes de `metadonnees.csv`.
7. **Codes ESPAR sans zéro initial** (`espar-cdref13.csv` écrit `9;Hêtre`, voir `ifn-dynamique.md` §6) : le script normalise `9` en `09`.

8. **S1 (2021-2025) face aux publications de l'IGN** (mission 058). Moyennes non pondérées de S1, `tous_types`, face à S2 (tome 2009-2013, tab. 7.3 et 8.3, forêt de production) et S4 (tableaux standards 2021-2025, onglet « BV Propriété », ligne Total, forêt de production **avec** peupleraies). S4 ne publie pas G.

| Périmètre | G S1 2021-2025 | G S2 2009-2013 | écart S1 - S2 | N S1 2021-2025 | N S4 2021-2025 (± IC) | écart S1 - S4 | N S2 2009-2013 |
|---|---:|---:|---:|---:|---:|---:|---:|
| France (`tous_types`) | 24,9 | 22,0 (23,7 en tab. 7.7) | +2,9 (+1,2) | 727 | 687 ± 9 | +40 (+6 %) | 723 (778) |
| France (`toutes_placettes`) | 24,3 | 22,0 | +2,3 | 709 | 687 ± 9 | +22 (+3 %) | 723 |
| A | 25,8 | 23,7 | +2,1 | 675 | 620 ± 37 | +55 | 710 |
| B | 24,3 | 22,3 | +2,0 | 665 | 622 ± 16 | +43 | 670 |
| C | 23,0 | 22,3 | +0,7 | 703 | 671 ± 20 | +32 | 736 |
| D | 30,5 | 28,6 | +1,9 | 678 | 655 ± 37 | +23 | 719 |
| E | 27,6 | 28,0 | −0,4 | 758 | 726 ± 41 | +32 | 813 |
| F | 22,3 | 16,4 | **+5,9** | 746 | 648 ± 22 | **+98 (+15 %)** | 603 |
| G | 28,9 | 25,6 | +3,3 | 761 | 715 ± 21 | +46 | 764 |
| H | 26,9 | 25,2 | +1,7 | 765 | 722 ± 40 | +43 | 799 |
| I | 26,9 | 23,9 | +3,0 | 740 | 758 ± 54 | −18 | 727 |
| J | 16,1 | 13,7 | +2,4 | 859 | 793 ± 50 | +66 | 822 |
| K | 27,6 | 22,6 | **+5,0** | 905 | 799 ± 125 | +106 | 853 |

Lecture (écarts constatés ; les causes sont des hypothèses, non vérifiées) :
- **Tiges/ha, même période (S1 contre S4)** : S1 est plus haut dans 10 GRECO sur 11, de 3 à 15 %. Sens attendu : S4 compte dans la surface les peupleraies et les placettes non recensables ou momentanément déboisées (PEUPNR 1 ou 2), à peu de tiges, que S1 écarte ; S4 applique aussi les poids de point et la post-stratification. L'écart le plus fort est en F (Sud-Ouest océanique : 145 points de peupleraie et, par hypothèse, des coupes rases de pin maritime). Seule I (Massif central) est sous S4, dans l'intervalle de confiance. **Aucun écart toléré n'avait été fixé** (§4, point 4) : c'est à Pascal de dire si 6 % au niveau France suffit.
- **G, périodes différentes (S1 contre S2)** : S1 est plus haut de 0,7 à 3,3 m²/ha dans 9 GRECO, sauf E (−0,4). Deux causes se mêlent sans qu'on puisse les séparer ici : le champ (S2, tab. 7.3, inclut coupes rases et peupleraies) et la période (capitalisation sur pied depuis 2009-2013). Les deux écarts forts, F (+5,9) et K (+5,0), sont à vérifier ; pour F, la tempête Klaus de janvier 2009, dans la période de S2, est une hypothèse.
- **Par type** (§3.1) : G de S1 proche de S2 pour la hêtraie (28,3 contre 27,3), la sapinière-pessière (37,8 contre 37,2 et 36,9) et le douglas (32,5 contre 32,1), mais **moins de tiges** (653 contre 712 ; 647 contre 702 et 811 ; 514 contre 619). Même G avec moins de tiges, c'est un Dg plus fort en 2021-2025. Ce peut être un vieillissement réel ou un effet de la convention de type (part de G au lieu du couvert libre) : non tranché.
- **Médiane et moyenne** : la médiane de G est sous la moyenne (23,6 contre 24,9 en France) et celle des tiges bien au-dessous (602 contre 727) : la queue des tiges/ha est longue (q95 1 778), comme annoncé au point 2.

## 5. Recommandation (l'IA propose, Pascal tranche)

**Pour le critère M3b :**
- Prendre les **quantiles 5 et 95 % par placette de S1** (2021-2025, VISITE = 1, CSA 1 ou 3, PEUPNR = 0, arbres vivants avec C13 ≥ 0,235 m), produits par `tools/referentiels/ifn_g_tiges.py`.
- Les prendre **par GRECO du massif**, ou par SER si l'effectif atteint 30 placettes (seuil provisoire). La ligne « France, tous_types » sert de repli.
- **Comparer à la même échelle** : la distribution des cellules de 25 m (625 m²), une valeur par cellule et par année, face à la distribution des placettes (disque de 15 m, 706,9 m², pour les gros bois). Ne pas comparer la moyenne du massif aux quantiles de placettes.
- **Compter dans la simulation les seuls arbres d'au moins 7,48 cm** (spec §6, l. 208-209), pour rester au seuil de recensabilité de l'IFN.
- S1 est exécuté (mission 058). Les bornes chiffrées possibles sont au §3.3 et au §3.4 ; **aucune n'est fixée tant que Pascal n'a pas répondu à Q1, Q2 et Q3** (« signaler plutôt que deviner »). À titre d'exemple seulement, pour la France en `tous_types` : G entre 3,8 et 50,3 m²/ha, tiges entre 96 et 1 778 /ha.

**Pour recaler le jeu fictif** (valeurs à marquer `provisoire: true`, source S2) :
- **G de départ autour de 20 à 30 m²/ha**. C'est l'étendue des moyennes de GRECO hors Méditerranée (16,4 à 28,6) et de la plupart des compositions. Jusqu'à 37 m²/ha pour une sapinière ou une pessière pure.
- **Autour de 600 à 900 tiges/ha** (moyennes de GRECO de 603 à 853).
- **Dg de 20 à 26 cm**, au lieu des 89 cm de d130 moyen actuels. C'est le levier principal : le nombre de tiges et les diamètres du jeu fictif sont à revoir ensemble.
- Les bornes exactes du recalage restent à décider. Pour information, le q25-q75 de S1 en France (`tous_types`) est de 14,9 à 33,1 m²/ha, de 323 à 987 tiges/ha, et de 16,3 à 29,3 cm de Dg.

## 6. Ce qui reste incertain

- **Levé le 2026-11-26 (mission 058) : quantiles calculés.** `--self-test` passe (G = 3,472 m²/ha, N = 127,71 tiges/ha) ; le test `pytest` existe (`tools/referentiels/tests/test_ifn_g_tiges.py`, 10 tests, valeurs recalculées à la main).
- **Levé le 2026-11-27 (mission 076) : rejeu prouvé.** Sur l'export du 07/10/2026, le script réécrit les lignes `DataIFN calcul` de `ifn-g-tiges.csv` octet pour octet : la valeur de toutes ces lignes remplacée par 999 dans une copie, le rejeu (14 s) rend le fichier du dépôt sans un octet d'écart, et les comptes du filtre sont ceux du §3.3 (59 384 placettes de la période, 232 écartées sans W, 28 799 calculées). Le test `test_replay_rewrites_the_csv_byte_for_byte` fait la même preuve sur le jeu d'essai (rejeu deux fois, lignes des autres sources intactes) ; `test_committed_csv_has_no_local_path` garde le CSV sans chemin local.
- **Levé : contenu de l'export vérifié.** Toutes les colonnes attendues sont dans `PLACETTE.csv` et `ARBRE.csv` ; encodage UTF-8 avec BOM (lu par `utf-8-sig`, défaut du script) ; séparateur de champs « ; », point décimal, ligne terminée par un « ; » (colonne vide sans nom, sans effet). Les codes CSA, PEUPNR, VEGET (DOM8M2), ORI (DOM1M0), VISITE et les codes ESPAR du script sont ceux de `metadonnees.csv`.
- **Levé : VISITE = 2 n'est pas utilisable pour G.** Dans l'export, **aucun arbre de 2e visite n'a de W** (366 201 lignes en 2021-2025), et 48 563 n'ont pas de C13. L'exclusion par défaut est donc nécessaire, pas seulement prudente ; elle retire 28 027 placettes (47 % des placettes de la période). L'option `--with-second-visits` ne produit que des placettes écartées et signalées.
- **Nouveau : 232 placettes de 1re visite sans W.** Tous leurs arbres vivants (1 356) ont C13 mais pas W ; la documentation (`IGN_DB_doc_arbre.pdf` v2.4, p. 9) n'en donne pas la raison. Elles sont surreprésentées en lisière : PLISI = 1 pour 111 des 235 placettes dont aucun arbre n'a de W (47 %), contre 18 % des autres ; BORD 1 ou 2 pour 17 %, contre 4 %. Le script les écarte en entier et les compte (sans cela, elles auraient compté comme des G = 0). C'est le seul changement de comportement du script (mission 058) ; la méthode est inchangée. Biais possible : un léger manque de placettes de lisière, à G sans doute plus bas.
- **Levé : effectifs par SER.** 85 SER sur 86 atteignent 30 placettes ; F13 en a 12.
- **Écart S1 - S4 non toléré ni refusé** : aucun seuil n'a été fixé (§4, point 8).
- **Pas de G 2021-2025 publié** : S4 ne donne que les tiges et les volumes. La seule comparaison de G reste avec S2 (2009-2013), où période et champ se mêlent.
- **Les types de peuplement sont une convention de l'acquéreur** (part de G d'au moins 75 % ; taillis = rejets d'au moins 75 % des tiges). Ce n'est pas la règle IGN, qui travaille sur le couvert libre relatif. Les types de S1 et de S2 ne se recouvrent donc qu'à peu près.
- **Licence du tome S2** non lue ; licence de **S4** non lue (l'onglet « Lisez-moi » n'en mentionne pas).
- **Définition de `G_ha` dans S3** (chablis, seuil, lisière) non relue dans le code.
- **Mémentos 2024 à 2026** non lus (hôtes bloqués ou fichiers trop gros). Je ne sais pas s'ils publient G ou des tiges/ha.

## 7. Questions pour Pascal (à poser une par une)

- **Q1. Périmètre de M3b** : toutes les placettes de forêt de production (y compris G = 0 après coupe rase), ou seulement les placettes avec des arbres recensables ? Proposition : placettes avec au moins un arbre vivant recensable (ligne `tous_types`), puisque le moteur ne simule que des cellules boisées. Les deux sont calculées.
- **Q2. Échelle des bornes** : France, GRECO ou SER du massif ? Proposition : la GRECO, avec la France en repli.
- **Q3. Types de peuplement** : accepter la convention provisoire (75 % de G, taillis à 75 % de rejets), ou lire le couvert libre (`TCL` de `COUVERT.csv`) pour imiter la règle IGN ?
- **Q4. Exécution** : qui télécharge `export_dataifn_2005_2025.zip` sous `data/ifn/` et lance le script ? Il faut un agent avec un outil d'exécution, ou l'orchestrateur, comme pour `surfaces-ser.md`. *Réglée le 2026-11-26 : confiée à un dev par l'orchestrateur (mission 058), faite.*
- **Q5. Écart toléré entre S1 et S4** (nouvelle, mission 058) : S1 dépasse S4 de 6 % pour les tiges/ha en France (de −2 à +15 % par GRECO). Proposition : accepter l'écart comme écart de champ (peupleraies et PEUPNR 1-2 exclus de S1) et ne pas pondérer ; sinon, il faut reconstituer les poids de point, que l'IGN ne publie pas.
- **Q6. Placettes sans W** (nouvelle) : accepter l'exclusion des 232 placettes de 1re visite sans W (signalées), ou demander à l'IGN pourquoi W manque ?

## 8. Trois points au sol

1. **Une sapinière ou une pessière pure du Jura ou des Vosges** (moyennes publiées de 37 m²/ha, les plus fortes). C'est là que le q95 sera le plus haut et que le seuil M3b est le plus sensible : un G de 50 à 60 m²/ha y est-il courant ? À vérifier au relascope sur une placette mûre. *Mission 058 : en 2021-2025, le q95 de `sapiniere_pessiere` est de 64,2 m²/ha et le q75 de 47,5 ; le q95 de la GRECO D (Vosges) de 54,9 et celui de la GRECO E (Jura) de 52,7.*
2. **Un taillis de châtaignier ou de chêne vert** (1 200 et 1 292 tiges/ha en moyenne, les plus fortes). Ici les tiges/ha sont le critère sensible, et la convention « taillis » de l'acquéreur (rejets d'au moins 75 %) est à confronter au terrain : compter les cépées et les brins de plus de 7,5 cm.
3. **Une placette de Fontainebleau à plus de 40 m²/ha** (S3, par exemple IDP 378806, campagne 2008, chênaie, 68,4 m²/ha et 1 405 tiges/ha). Est-ce un peuplement réel ou un effet de poids de lisière (`W` corrigé) ? Cette queue fixe le q95 local.

## 9. Question de contrôle

*Quelle décision cette donnée va-t-elle éclairer ?* Les bornes chiffrées du critère M3b (G et tiges/ha simulés entre les quantiles 5 et 95 % de l'IFN), et les valeurs de départ du jeu fictif à recaler.

## 10. Ligne de journal proposée

`2026-11-26 | acquéreur | M3b : docs/referentiels/ifn-g-tiges.md et .csv (moyennes IGN 2009-2013 lues : France 22,0 m²/ha et 723 tiges/ha, 23,7 et 778 sur couvert recensable ; 11 GRECO ; 24 compositions ; queue locale de Fontainebleau max 68,4 m²/ha et 3 006 tiges/ha). Script tools/referentiels/ifn_g_tiges.py écrit, jamais exécuté : quantiles q05-q95 2021-2025 à calculer. Jeu fictif : G 4 fois la moyenne à l'an 0, porté par un Dg de 91 cm contre 20 cm. Hôtes bloqués : www.ign.fr, draaf.nouvelle-aquitaine.agriculture.gouv.fr.`

## 11. Liste de contrôle

**Aucune liste de contrôle n'était jointe à la consigne.** J'ai passé les trois points génériques de ma fiche.

1. **Sources et emplacements : coché avec réserves.** Chaque ligne du CSV porte son URL et son tableau, ou son fichier et sa ligne. Non coché : S1 et S4 ne sont pas ouverts, et la licence de S2 n'est pas lue.
2. **Décomptes complets : coché pour ce qui a été lu.** 11 GRECO sur 11 (G et tiges) ; 24 compositions et la ligne France des tableaux 7.7 et 8.6 ; 2 lignes de France entière (7.3, 8.3). Non coché : les quantiles et les effectifs de S1.
3. **Termes exacts : coché.** Les libellés de composition, de GRECO et de codes sont ceux du tome et de `metadonnees.csv` ; les codes du CSV sont des translittérations sans accents.

**Mise à jour du 2026-11-26 (mission 058, dev) :**
1. **Sources et emplacements :** S1 et S4 ouverts ; empreinte de l'archive S1 au §1. Licences de S2 et de S4 toujours non lues.
2. **Décomptes complets :** 1 ligne France, 11 GRECO sur 11, 86 SER sur 86 (85 publiées, F13 sous le seuil), 10 lignes de type pour la France ; effectifs de chaque étape du filtre au §3.3. S4 : 11 GRECO sur 11 et la ligne France, onglet « BV Propriété », lus pour les tiges/ha.
3. **Termes exacts :** codes de filtre vérifiés dans `metadonnees.csv` de l'export (CSG13, PEUPNR, DOM8M2, DOM1M0, VISITE, ESPAR1).
