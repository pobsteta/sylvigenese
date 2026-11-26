# IFN : ordres de grandeur de la surface terrière et des tiges/ha (critère M3b)

- **Propriétaire :** Pascal
- **Date de consultation :** 2026-11-26
- **Mission redite :** donner des bornes sourcées de G (m²/ha) et de tiges/ha des peuplements français, d'après l'IFN. Il faut deux sources : un calcul par placette sur les données brutes DataIFN, et les résultats publiés par l'IGN.
- **Décision éclairée :** (1) les bornes du critère M3b (`docs/spec.md` §11, ligne M3 : « surface terrière et tiges par hectare entre les quantiles 5 et 95 % de l'IFN ») ; (2) les ordres de grandeur pour recaler le jeu fictif. Aujourd'hui, ce jeu part de 91 m²/ha et monte à 352 m²/ha en 100 ans (`docs/spec.md` §6, l. 224 ; `tests/m3/reference/nominal.json`).
- **Fichier tabulaire :** `docs/referentiels/ifn-g-tiges.csv`. Une ligne par (périmètre, peuplement, grandeur, statistique), avec la source, l'effectif, la période, l'URL et la page.
- **Script :** `tools/referentiels/ifn_g_tiges.py` (Python, bibliothèque standard seule). **Il n'a jamais été exécuté** : il n'y avait aucun outil d'exécution dans la session de l'acquéreur. Le script réécrit ses propres lignes dans le CSV et garde celles des autres sources.
- **Règle suivie :** aucune valeur de mémoire. Chaque nombre du CSV a été lu à la page citée, ou compté sur le fichier cité. Les seuls calculs de l'acquéreur sont les Dg tirés des moyennes publiées (§4) et les comptes de `grep` (S3) ; ils sont signalés comme tels.

## 0. État en une phrase

**Les quantiles 5-95 % demandés ne sont pas encore calculés.** Il faut lancer le script sur l'export DataIFN. Ce référentiel donne aujourd'hui les **moyennes publiées par l'IGN** (campagnes 2009 à 2013), par GRECO et par composition, ainsi que la queue de distribution d'un échantillon local de 221 placettes. Ces moyennes suffisent pour **recaler le jeu fictif**, mais pas pour fixer les bornes de M3b.

## 1. Sources, versions, accès

| Id | Source | Version, date | Licence | Accès dans cette session |
|---|---|---|---|---|
| S1 | **DataIFN, données brutes** : `export_dataifn_2005_2025.zip` (`PLACETTE.csv`, `ARBRE.csv`) | mise à jour du 07/10/2026 ; dernière campagne 2025, donc dernière période de 5 campagnes **2021-2025** | « Licence Ouverte / Open Licence Etalab Version 2.0 » (page DataIFN) | page lue (https://inventaire-forestier.ign.fr/dataifn/). **Archive non téléchargée** : sans outil d'exécution, impossible de télécharger ou de décompresser |
| S1-doc | Documentation DataIFN locale `/home/user/ref-externes/ifn_doc_2025/` | `IGN_DB_documentation_generale.pdf` v3.0 du 14/10/2025 ; `metadonnees.csv` | Etalab 2.0 | lue : documentation générale p. 1-9 en entier ; `metadonnees.csv` aux lignes ESPAR1, CSG13, DOM1M0, DOM8M2, GRECO, PEUPNR ; `recapitulatif_donnees.csv` en entier |
| S2 | **IGN, Résultats standards, tome national « La France par zonage écoforestier », campagnes 2009 à 2013** | sans date imprimée ; période 2009-2013 | **non lue** (aucune mention vue dans les pages ouvertes) | lu en image : couverture, sommaire, p. 106-107, 112-113, 119, 124-125 (https://inventaire-forestier.ign.fr/IMG/pdf/RS_0913_FR_GRECO.pdf) |
| S3 | tarif-nemeton (Pascal) : `resultats/etage_b/ifn_placettes.csv`, G/ha et N/ha par placette, calculés sur l'export IFN 2005-2023 | fichier local, LISEZMOI du 29/09/2026 | dépôt sans licence (voir `volume-carbone.md` §1) | lu en partie : en-tête et lignes extraites par `grep` |
| S4 | Tableaux standards 2021-2025 (France, GRECO, SER), ZIP de xlsx | en ligne le 07/10/2026 | non lue | **liens relevés, fichiers non ouverts** : https://inventaire-forestier.ign.fr/IMG/zip/ts_2021-2025_france-2.zip et `…/ts_2021-2025_greco.zip`. Ce sont des ZIP de xlsx, sans lecteur dans cette session. C'est la seconde source qui manque pour la période 2021-2025 |

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

**La médiane et les quantiles 5 et 95 % ne sont pas encore disponibles** : ils viendront de S1, une fois le script exécuté. Le tableau donne donc la moyenne publiée de S2.

| Périmètre ou type (S2, 2009-2013) | G moyen (m²/ha) | Tiges/ha moyennes | Dg tiré des deux moyennes (cm, calcul de l'acquéreur) | Médiane, q05, q95 (S1) |
|---|---|---|---|---|
| France, forêt de production (tab. 7.3 et 8.3) | 22,0 ± 0,2 | 723 ± 9 | 19,7 | à calculer |
| France, couvert recensable (tab. 7.7 et 8.6) | 23,7 ± 0,2 | 778 ± 10 | 19,7 | à calculer |
| Chênaies pures : pédonculé, rouvre, pubescent, vert | 22,4 ; 24,7 ; 16,9 ; 16,2 | 574 ; 658 ; 932 ; 1 292 | — | à calculer |
| Hêtraie pure | 27,3 ± 1,5 | 712 ± 61 | 22,1 | à calculer |
| Sapinière pure ; pessière pure | 37,2 ± 2,4 ; 36,9 ± 2,7 | 702 ± 67 ; 811 ± 74 | 26,0 ; — | à calculer |
| Pinèdes pures : maritime, sylvestre, noir-laricio-Alep | 20,1 ; 24,0 ; 21,5 | 540 ; 726 ; 674 | — | à calculer |
| Douglas pur | 32,1 ± 2,7 | 619 ± 50 | — | à calculer |
| Châtaigneraie pure (souvent en taillis) | 29,6 ± 2,3 | 1 200 ± 110 | — | à calculer |
| Taillis (structure) | non lu (le tome ne donne pas G par structure) | non lu | — | à calculer (S1 : ORI = 0 pour au moins 75 % des tiges) |
| GRECO, minimum et maximum de G | J Méditerranée 13,7 ; D Vosges 28,6 | F Sud-Ouest 603 ; K Corse 853 | — | à calculer |
| **Jeu fictif, an 0 → an 100** (`nominal.json`) | **91 → 352** | **141 → 4 024** | **90,6 → 33,4** | — |

Dg = 100 × √(4 G / (π N)), calculé ici à partir des **moyennes** : c'est un ordre de grandeur, pas une valeur publiée. Pour le jeu fictif à l'an 0, le d130 moyen est de 88,6 cm (`somme_d130` / `lignes` = 1 246 918 / 14 080, `nominal.json`).

### 3.2 Queue de distribution locale (S3, comptée par l'acquéreur)

Sur les 221 placettes de Fontainebleau (2005-2023) :
- G : maximum **68,4 m²/ha** ; 7 placettes à 40 m²/ha ou plus (3,2 %) ; 2 à 50 ou plus ; 27 sous 10 m²/ha (12,2 %) ;
- tiges : maximum **3 006/ha** ; 2 placettes à 2 000/ha ou plus.

C'est le seul aperçu de quantiles extrêmes disponible aujourd'hui. Il vient d'un seul massif.

## 4. Comparaisons et écarts

1. **Deux moyennes « France » dans le même tome : 22,0 et 23,7 m²/ha.** Ce n'est pas une erreur de mesure, c'est le champ qui diffère. Le tableau 7.7 exclut les forêts temporairement non boisées et celles dont le couvert absolu des recensables est inférieur à 15 % (note du tableau, p. 113). Il en va de même pour les tiges : 723 contre 778. **Le périmètre de M3b doit donc être choisi** (Q1).
2. **Moyenne et médiane.** S2 publie des moyennes. La distribution de G par placette est asymétrique : à Fontainebleau, 12 % des placettes sont sous 10 m²/ha et le maximum atteint 68 m²/ha. La médiane de S1 sera donc différente de la moyenne de S2, sans qu'aucune des deux soit fausse.
3. **Période : 2009-2013 (S2) contre 2021-2025 (S1).** L'écart attendu (tempêtes, scolytes, sécheresses depuis 2018) **n'est pas chiffré**. La comparaison sur la même période passera par S4 (tableaux standards 2021-2025), à ouvrir.
4. **Poids de point.** Les quantiles de S1 ne seront pas pondérés. Les points forêt sont tirés sur la grille de niveau 2, à poids égal en général. Mais les allègements de grille (S1-doc p. 9) et la post-stratification peuvent déplacer les moyennes. **Contrôle prévu** : la moyenne non pondérée de S1 (colonne `moyenne` du script) contre la moyenne de S4. L'écart toléré reste à fixer par Pascal.
5. **Jeu fictif hors d'échelle, et pourquoi.** À l'an 0, 91 m²/ha est environ 4 fois la moyenne française (22-24) et au-dessus du maximum local de S3 (68,4). Le nombre de tiges, lui, est bas : 141/ha contre 723 à 778. **L'excès de G vient des diamètres** : Dg d'environ 91 cm, contre environ 20 cm en moyenne nationale. À l'an 100, 352 m²/ha est environ 15 fois la moyenne, et 4 024 tiges/ha dépassent le maximum local de 3 006.
6. **Le douglas est le code `64`, pas `52`** (`metadonnees.csv` l. 4539 et 4554) : `52` est le pin sylvestre. Le script utilise les codes de `metadonnees.csv`.
7. **Codes ESPAR sans zéro initial** (`espar-cdref13.csv` écrit `9;Hêtre`, voir `ifn-dynamique.md` §6) : le script normalise `9` en `09`.

## 5. Recommandation (l'IA propose, Pascal tranche)

**Pour le critère M3b :**
- Prendre les **quantiles 5 et 95 % par placette de S1** (2021-2025, VISITE = 1, CSA 1 ou 3, PEUPNR = 0, arbres vivants avec C13 ≥ 0,235 m), produits par `tools/referentiels/ifn_g_tiges.py`.
- Les prendre **par GRECO du massif**, ou par SER si l'effectif atteint 30 placettes (seuil provisoire). La ligne « France, tous_types » sert de repli.
- **Comparer à la même échelle** : la distribution des cellules de 25 m (625 m²), une valeur par cellule et par année, face à la distribution des placettes (disque de 15 m, 706,9 m², pour les gros bois). Ne pas comparer la moyenne du massif aux quantiles de placettes.
- **Compter dans la simulation les seuls arbres d'au moins 7,48 cm** (spec §6, l. 208-209), pour rester au seuil de recensabilité de l'IFN.
- Tant que S1 n'est pas exécuté, **ne fixer aucune borne chiffrée** pour M3b (« signaler plutôt que deviner »).

**Pour recaler le jeu fictif** (valeurs à marquer `provisoire: true`, source S2) :
- **G de départ autour de 20 à 30 m²/ha**. C'est l'étendue des moyennes de GRECO hors Méditerranée (16,4 à 28,6) et de la plupart des compositions. Jusqu'à 37 m²/ha pour une sapinière ou une pessière pure.
- **Autour de 600 à 900 tiges/ha** (moyennes de GRECO de 603 à 853).
- **Dg de 20 à 26 cm**, au lieu des 89 cm de d130 moyen actuels. C'est le levier principal : le nombre de tiges et les diamètres du jeu fictif sont à revoir ensemble.
- Les bornes exactes du recalage (q25-q75 de S1 ?) se décident après l'exécution du script.

## 6. Ce qui reste incertain

- **Aucun quantile calculé.** Le script n'a jamais tourné, pas même son `--self-test`. Il faut le lancer d'abord avec `--self-test` (contrôle à la main : 1 placette, G = 3,472 m²/ha, N = 127,71 tiges/ha), puis sur l'export. Il faut aussi un test `pytest` pour respecter « pas de code sans tests ». Il n'est pas écrit, car la fiche n'autorisait que ce fichier.
- **Contenu de l'export réel non vérifié** : présence de `CSA`, `PEUPNR`, `GRECO`, `SER` dans `PLACETTE.csv` ; de `ORI`, `VEGET`, `W` dans `ARBRE.csv` ; encodage ; séparateur décimal. Le script s'arrête avec un message (code 2) si une colonne manque.
- **VISITE = 2 exclu par défaut**, parce que le contenu d'une ligne de 2e visite n'est pas vérifié (`ifn-dynamique.md` Q3). L'effectif de 2021-2025 en est réduit d'autant, dans une proportion inconnue.
- **Effectifs par SER inconnus** avant exécution : certaines SER passeront sans doute sous 30 placettes.
- **Les types de peuplement sont une convention de l'acquéreur** (part de G d'au moins 75 % ; taillis = rejets d'au moins 75 % des tiges). Ce n'est pas la règle IGN, qui travaille sur le couvert libre relatif. Les types de S1 et de S2 ne se recouvrent donc qu'à peu près.
- **Licence du tome S2** non lue ; **S4** (2021-2025) non ouvert.
- **Définition de `G_ha` dans S3** (chablis, seuil, lisière) non relue dans le code.
- **Mémentos 2024 à 2026** non lus (hôtes bloqués ou fichiers trop gros). Je ne sais pas s'ils publient G ou des tiges/ha.

## 7. Questions pour Pascal (à poser une par une)

- **Q1. Périmètre de M3b** : toutes les placettes de forêt de production (y compris G = 0 après coupe rase), ou seulement les placettes avec des arbres recensables ? Proposition : placettes avec au moins un arbre vivant recensable (ligne `tous_types`), puisque le moteur ne simule que des cellules boisées. Les deux sont calculées.
- **Q2. Échelle des bornes** : France, GRECO ou SER du massif ? Proposition : la GRECO, avec la France en repli.
- **Q3. Types de peuplement** : accepter la convention provisoire (75 % de G, taillis à 75 % de rejets), ou lire le couvert libre (`TCL` de `COUVERT.csv`) pour imiter la règle IGN ?
- **Q4. Exécution** : qui télécharge `export_dataifn_2005_2025.zip` sous `data/ifn/` et lance le script ? Il faut un agent avec un outil d'exécution, ou l'orchestrateur, comme pour `surfaces-ser.md`.

## 8. Trois points au sol

1. **Une sapinière ou une pessière pure du Jura ou des Vosges** (moyennes publiées de 37 m²/ha, les plus fortes). C'est là que le q95 sera le plus haut et que le seuil M3b est le plus sensible : un G de 50 à 60 m²/ha y est-il courant ? À vérifier au relascope sur une placette mûre.
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
