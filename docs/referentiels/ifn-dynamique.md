# IFN, données brutes : colonnes de la dynamique (mission 022)

- **Propriétaire :** Pascal
- **Date de consultation :** 2026-11-25
- **Mission redite :** établir, sources lues et citées (fichier et page, ou ligne de `metadonnees.csv`), les tables et colonnes des données brutes IFN qui servent à ajuster (1) l'accroissement radial sur 5 ans, (2) la mortalité à 5 ans d'après les placettes revisitées, (3) le recrutement (arbres franchissant 7,5 cm de diamètre), avec unités, codes, années de validité et règles de revisite, et la source des valeurs indicatrices de la flore pour le gradient trophique.
- **Décision éclairée :** BRIEF §6 (« les noms exacts des variables IFN sont à vérifier dans la documentation des données brutes avant tout ajustement ») ; les missions 023 à 026 (contrats, jeu fictif, `dynamics`) ne nomment ainsi aucune variable de mémoire. Elles renvoient à une ligne de ce référentiel ou de `ifn-dynamique-colonnes.csv`.
- **Tableau des colonnes en CSV :** `docs/referentiels/ifn-dynamique-colonnes.csv` (même contenu en table plate, sans accents, une ligne par colonne).

## Sources réellement lues

Export officiel du 2026-10-07, dossier local `/home/user/ref-externes/ifn_doc_2025/` (archive `https://inventaire-forestier.ign.fr/dataifn/data/export_dataifn_doc_2025.zip`).

| Sigle | Fichier | Lu |
|---|---|---|
| MD | `metadonnees.csv` (6 101 lignes : en-tête l.1-18 ; 162 définitions l.19-180 ; 199 lignes d'unités l.185-383 ; 5 714 lignes de modalités l.388-6101) | définitions et unités **en entier** ; modalités des unités utiles (grep par unité) |
| REC | `recapitulatif_donnees.csv` (160 données × campagnes 2005 à 2025) | en entier |
| PRE | `precision-donnees_2020-2024.csv` (WINDOWS-1252) | lignes utiles |
| GEN | `IGN_DB_documentation_generale.pdf` v3.0, 14/10/2025 | 9 pages sur 9 |
| ARB | `IGN_DB_doc_arbre.pdf` v2.4, 14/10/2025 | 12 pages sur 12 |
| PLA | `IGN_DB_doc_placette.pdf` v2.5, 07/10/2026 | 12 pages sur 12 |
| FLO | `IGN_DB_doc_flore.pdf` v2.0, 18/10/2022 | 3 pages sur 3 |
| ECO | `IGN_DB_doc_ecologie.pdf` v2.3, 14/10/2025 | pages 1 à 4 sur 10 (préambule, sommaire, IDP, DATEECO, TOPO) |
| ESP | `espar-cdref13.csv` | lignes utiles |
| SYL | sylvostation, commit 2864d70 : `R/placettes.R`, `R/indicateurs.R`, `inst/extdata/SOURCES.md`, `ifn_*.csv` ; `docs/referentiels.md` §7, §14, §35 | lus |
| M23 | IGN, « Méthodologie 2023, pour bien comprendre les résultats publiés 2018-2022 » (`https://inventaire-forestier.ign.fr/IMG/pdf/methodologie-2023.pdf`) | pages 3, 4, 9, 19, 20, 21 lues en image. **Source hors liste**, ajoutée pour avoir une seconde source sur les règles de revisite (trouvée par recherche web, PDF récupéré par WebFetch) |
| PLQ | `docs/referentiels/ifn-placettes.md`, `docs/spec.md` §6 et §12, `docs/BRIEF.md` §6, fixtures `tests/fixtures/zone_fictive/inputs/ifn/` | lus |

## 1. Structure des fichiers et clés

Sept tables CSV, séparateur `;`, NULL = rien entre deux `;` (GEN p.4) : `ARBRE`, `BOIS_MORT`, `COUVERT`, `ECOLOGIE`, `FLORE`, `HABITAT`, `PLACETTE`. Une ligne d'`ARBRE` est un arbre à une campagne ; une ligne de `PLACETTE`, `ECOLOGIE` ou `FLORE` est un point (ou une espèce) à une campagne (GEN p.4). Le lien se fait par `IDP` (GEN p.4 ; ARB p.3).

| Clé | Règle | Sources |
|---|---|---|
| `CAMPAGNE` | Année des opérations de terrain ; la campagne C commence à l'automne C-1 et finit à l'automne C | MD l.39 ; ARB p.3 ; PLA p.3 |
| `IDP` | Identifiant du **point**. Préfixe = campagne de la 1re visite (2005=0, 2006=1, …) + 5 chiffres. Le point revu **garde l'IDP de sa 1re visite** | ARB p.3 ; PLA p.3 ; FLO p.2 ; ECO p.3 (quatre fiches concordantes) ; MD l.80 |
| `A` | Numéro unique de l'arbre, « à associer avec IDP » | MD l.19 ; ARB p.3 |
| (`IDP`, `CAMPAGNE`, `A`) | Unique. (`IDP`, `A`) seuls : unique par arbre, mais un arbre peut figurer **deux fois** (deux campagnes) | ARB p.1 |
| `VISITE` (table `PLACETTE`) | 1 = protocole de 1re visite (complet) ; 2 = protocole de 2e visite (partiel, pas d'écologie) | MD l.179, l.382, l.6100-6101 ; PLA p.3 ; GEN p.3 |
| `DATEPOINT` | Date de validation de la placette, quelle que soit la visite (jj/mm/aaaa) | MD l.47, l.223 ; PLA p.3 |

`VISITE` n'est **pas** une colonne d'`ARBRE.csv` (liste ARB p.2 et en-tête réel cité par SYL `docs/referentiels.md` l.160) : elle se lit dans `PLACETTE.csv` par (`CAMPAGNE`, `IDP`).

Séries d'IDP (PLA p.3, recopié par ARB p.3, FLO p.2, ECO p.3) : de 2010 à 2015, deux séries d'IDP par campagne (0 à 99 999 pour des points de 2005 revisités en 2010, `VISITE`=2 ; 500 000 à 599 999 pour les nouveaux points de 2010, `VISITE`=1). Depuis 2016, trois séries (exemple 2016 : 600 000 à 699 999 avec `VISITE`=1, points de 2011 vus non forêt puis forêt ; 600 000 à 699 999 avec `VISITE`=2, points levés en 2011 et revisités ; 1 100 000 à 1 199 999 nouveaux points, `VISITE`=1). **Conséquence :** la campagne d'une 2e visite est celle de la 1re visite plus 5 (vérifiable : préfixe de l'IDP + 2005 + 5).

## 2. Règles de revisite

| Période | Quelles placettes revisitées | Quels arbres | Sources (au moins deux) |
|---|---|---|---|
| 2010 à 2014 | Points vus 5 campagnes plus tôt **portant au moins un arbre recensable** en 1re visite | Seule la coupe (ou non) des arbres présents est notée ; `VEGET5` n'est saisi que si une souche existe : arbres initialement vivants ou chablis | GEN p.3 ; ARB p.4 (`VEGET5`) ; M23 p.9 |
| 2015 | Idem | **Tous** les arbres mesurés en 1re visite sont remesurés (ou notés coupés ou morts) ; les **nouveaux arbres recensables sur une placette de 5 m** sont inventoriés | GEN p.3 ; M23 p.9 ; ARB p.1 et p.4 (« depuis 2015, l'ensemble des arbres, quel que soit leur état initial, font l'objet d'un levé ») |
| 2016 et après | **Tous** les points levés une première fois sont revisités (écologie et flore non reprises) | Mesures sur les arbres + couverture, usage du sol, plantation, coupe… | GEN p.3 ; M23 p.9 ; PLA p.1 (« depuis 2010, plus de 12 000 placettes observées annuellement ») |

- **Pas de temps :** 5 campagnes (« proximité des mailles des échantillons n et n-5 », M23 p.9 ; « séparées de 5 ans », PLA p.3 ; « cinq ans environ », M23 p.21). Les deux visites ont lieu à une date quelconque de leur campagne (M23 p.20 : « les deux visites ayant lieu tout au long d'une campagne annuelle ») : l'écart réel est `DATEPOINT` (visite 2) moins `DATEPOINT` (visite 1), pas exactement 5,00 an.
- **Jointure d'un arbre à son relevé 5 ans après :** même `IDP`, même `A`, `CAMPAGNE` de la ligne 2e visite = `CAMPAGNE` de la ligne 1re visite + 5. ARB p.1 : « Quand un point fait l'objet d'une 2e visite, les informations fournies dans `ARBRE.csv` ne reprennent que les valeurs actualisées et on ne retrouve pas les données collectées lors de la première visite » : les deux visites sont donc **deux lignes**, une par campagne. Seconde source : M23 p.20 (« les mêmes arbres des mêmes points »). **Contenu exact d'une ligne de 2e visite non vérifié** (voir §6, Q3).
- **Arbres jamais appariés :** `VEGET5`=`N` (non retrouvé) et `T` (cassé sous C13, ou non retrouvé à cause d'un incident), `6`/`7` (coupé) : voir §4.
- **Recrutement :** les arbres qui franchissent le seuil entre les deux visites sont des lignes de 2e visite **sans ligne de 1re visite** de même (`IDP`, `A`). En 2015 ils sont cherchés sur la placette de 5 m seulement (GEN p.3 ; M23 p.9). **Pour 2016 et après, le rayon de recherche n'est dit dans aucune des sources lues** (M23 p.9 : « cette deuxième visite complète »). IGN définit son recrutement (en volume) comme celui des arbres « ayant atteint le diamètre de 7,5 cm durant les cinq dernières années, c'est-à-dire les arbres devenus recensables » (M23 p.19).

## 3. Accroissement radial sur 5 ans

| Table | Colonne | Libellé | Type | Unité (export) | Modalités | Années | Source |
|---|---|---|---|---|---|---|---|
| ARBRE | `IR5` | Accroissement radial sur 5 ans | réel | **m**, cumul sur 5 ans | — | 2005- | MD l.87, l.274 ; ARB p.9 ; M23 p.19 |
| ARBRE | `IR1` | Accroissement radial sur 1 an | réel | m | — | 2007- | MD l.86, l.273 ; **absent de ARB** |
| ARBRE | `C13` | Circonférence à 1,30 m | réel | **m** | seuil 0,235 | 2005- | MD l.35, l.203 ; ARB p.7 ; REC l.18 |
| ARBRE | `MES_C13` | Mesure de circonférence | qualitatif | `MES_C13` | 1 niveau théorique ; 2 moyenne ; 3 niveau décalé ; 4 estimation | 2016- | MD l.95, l.282, l.5211-5214 ; ARB p.7 |
| ARBRE | `SIMPLIF` | Arbre simplifié (mesures allégées) | qualitatif | `SIMPLIF` | 0 ; 1 | 2009- | MD l.152, l.340, l.5652-5653 ; ARB p.7 |
| ARBRE | `ESPAR` | Espèce arborée | chaîne | `ESPAR1` (2009-) | `09`, `25M`, `27C`… | 2005- | MD l.65, l.245-247 ; GEN p.5 |
| ARBRE | `VEGET` | État de végétation (1re visite) | qualitatif | `DOM8M2` (2019-) | 0 vivant ; 1 chablis vivant ; 5 mort sur pied ; C mort cassé (`DOM8M1` 2008-2018 : 0, A, 5, C) | 2005- | MD l.175, l.372-375, l.6067-6074 ; ARB p.3 |
| ARBRE | `W` | Poids de l'arbre | réel | tiges/ha (sans unité, 10⁻²) | 88,4 ; 39,3 ; 14,1 sans limite | 2005- | MD l.180, l.383 ; ARB p.9 ; GEN p.9 |
| ARBRE | `CIBLE` | Peuplement cible | qualitatif | `CIBLE` | 0 hors ; 1 cible | 2009- | MD l.41, l.4157-4158 ; ARB p.5 |
| ARBRE | `LIB` | Couvert libre de l'arbre (3 classes) | qualitatif | `DOM3` | 0 nul ; 1 < 2/3 ; 2 > 2/3 | 2005- | MD l.90, l.5202-5204 ; ARB p.6 |
| ARBRE | `ORI` | Origine | qualitatif | `DOM1M0` | 0 rejet ; 1 semence ; 2 autre | 2005- | MD l.118, l.5337-5339 |
| ARBRE | `AGE13` | Âge à 1,30 m | entier | an | — | 2006- | MD l.26, l.190 ; ARB p.6 |

Règles d'application :
- **`IR5` est une épaisseur de 5 cernes** : « épaisseur cumulée des 5 derniers cernes annuels entièrement formés, mesurée en dixièmes de millimètre […] sur une carotte à la tarière de Pressler […] exprimé en mètres » (ARB p.9). Pour une campagne `t`, ce sont les cernes `t-5` à `t-1` ; le cerne de l'année `t` n'est pas compté (M23 p.19).
- **`IR5` n'est pas mesuré** sur les arbres simplifiés (`SIMPLIF`=1), ni sur les noyers (`ESPAR`=27C), ni sur les chênes verts (`ESPAR`=6, depuis 2015) (ARB p.9). Depuis 2014, seule une partie des arbres vivants est carottée : « 1 arbre par essence et catégorie de dimension ainsi que les gros bois » (M23 p.19, note) ; « les données non prises sur le terrain sont issues de modélisation » (M23 p.19) : **les valeurs absentes sont absentes, pas modélisées dans l'export** (ARB p.1 : « les arbres simplifiés ne font pas l'objet de la mesure de […] l'accroissement radial »). Jeu réel de sylvostation (campagne la plus récente de 100 placettes, 1 550 arbres, toutes en 1re visite) : `IR5` renseigné sur 826 lignes (53 %), `SIMPLIF`=1 sur 624 (40 %).
- Arbre à moins de 5 cernes à 1,30 m : `IR5` calculé au prorata (largeur moyenne d'un cerne × 5) (ARB p.9).
- `IR5` n'a pas besoin de revisite : il se lit sur la ligne d'une visite quelconque. L'accroissement entre deux visites se calcule aussi par différence de `C13` (voir Q5).
- **`C13` en mètres** : MD l.35 (« en m »), l.203 (unité `M`), ARB p.7 (« exprimé en mètres »), REC l.18, et les 1 550 lignes de `ifn_arbre.csv` de sylvostation (toutes entre 0,235 et 3,0 ; exemples 0,300 ; 1,030). Le diamètre : `d130_cm = C13_m × 100 / π`. Voir §7, écart 1.
- Seuil de recensabilité : `C13` ≥ 0,235 m (ARB p.1 et p.7), soit D13 ≥ 7,5 cm (GEN p.3).

## 4. Mortalité à 5 ans

| Table | Colonne | Libellé | Type | Unité | Modalités | Années | Source |
|---|---|---|---|---|---|---|---|
| ARBRE | `VEGET5` | État de végétation à la 2e visite | qualitatif | selon l'année de la ligne : `VEGET5` 2010-14, `VEGET56` 2015-16, `VEGET57` 2017-18, `VEGET59` 2019- | voir tableau ci-dessous | 2010- | MD l.176, l.376-379, l.6075-6099 ; ARB p.4 ; REC l.157 |
| ARBRE | `DATEMORT` | Date de mort estimée (arbre mort sur pied en 1re visite) | qualitatif | `DATEMORT` | 1 mort depuis ≤ 5 ans ; 2 depuis > 5 ans | 2008- | MD l.46, l.4226-4227 ; ARB p.4 (renseigné si `VEGET`=5 ou C) |
| ARBRE | `ACCI` | Accident de l'arbre vivant | qualitatif | `ACCI` | 0 aucun ; 1 cassé ; 2 penché ; 3 courbé ; 4 brûlé | 2007- | MD l.22, l.393-397 ; ARB p.7 |
| ARBRE | `MORTB` | Mortalité de branches | qualitatif | `MORTB3` (2021-) | voir MD | 2006- | MD l.96, l.283-285 ; ARB p.10 |
| ARBRE | `DEGGIB` | Dégât de gibier | qualitatif | `DEGGIB` | voir MD | 2015- | MD l.56, l.236 ; ARB p.11 |
| PLACETTE | `PRELEV5` | Coupe entre les deux visites (arbres levés en 1re visite et souches) | qualitatif | **aucune unité ni modalité dans MD** | — | 2010-2014 seulement (REC l.115) | MD l.134 ; PLA p.7 ; REC l.115 |
| PLACETTE | `DEF5` | Défrichement entre les deux visites | qualitatif | `DEF5` | 0 aucun ; 1 à 5 (partiel > 15 m ; partiel < 15 m piquet non touché ; piquet touché ; total 15 m ; total 25 m) | 2017- | MD l.55, l.235, l.4646-4651 ; PLA p.7 |
| PLACETTE | `INSTP5` | Installation de peuplement (plantation, semis) entre les deux visites | qualitatif | `INSTP5` (2015-23), `INSTP52` (2024-) | 0 pas de travaux ; 1 plantation ou semis | 2015- | MD l.83, l.267-268, l.5174-5175 ; PLA p.7 |
| PLACETTE | `NINCID` | Nature d'un incident des 5 ans **avant** la 1re visite | qualitatif | `NINCID` | 0 aucun ; 1 incendie ; 2 mortalité ; 3 mouvement de terrain ; 4 tempête ; 5 autre | 2015- | MD l.100, l.5239-5244 ; PLA p.5 |
| PLACETTE | `INCID` | Intensité de cet incident | qualitatif | `INCID2` | 0 ; 1 < 25 % ; 2 25-50 % ; 3 50-75 % ; 4 > 75 % du couvert | 2009- | MD l.81, l.5161-5165 ; PLA p.5 |
| PLACETTE | `NLISI5` | Modification de lisière entre les deux visites | qualitatif | `NLISI5` | 0 ; 1 route ; 2 bâti ; 3 limite | 2015- | MD l.101, l.5245-5248 ; PLA p.11 |
| PLACETTE | `GEST` | Traces de gestion | qualitatif | `GEST` | 0 ; 1 faibles ; 2 manifestes | 2009- | MD l.72, l.4924-4926 ; PLA p.7 |

Codes de `VEGET5` selon l'unité (MD) :

| Unité (années de la ligne 2e visite) | Codes | Lignes MD |
|---|---|---|
| `VEGET5` (2010-2014) | 0 vivant ; 6 coupé ; A chablis ; 5 mort sur pied ; C mort cassé | l.6075-6079 |
| `VEGET56` (2015-2016) | 0 vivant ; M mort sur pied ; A chablis ; 6 coupé ; N non retrouvé | l.6080-6084 |
| `VEGET57` (2017-2018) | 0 vivant ; 6 coupé vidangé ; 7 coupé non vidangé ; A chablis (accident < 10 ans) ; M mort sur pied ; N non retrouvé ; T cassé sous C13 | l.6085-6091 |
| `VEGET59` (2019-) | 0 vivant ; 6 coupé vidangé ; 7 coupé non vidangé ; 1 chablis vivant ; 2 chablis mort ; M mort sur pied ; N non retrouvé ; T cassé sous C13 **ou non retrouvé à cause d'un incident** | l.6092-6099 |

**Piège de codage :** « mort sur pied » est `5` dans `VEGET` (1re visite) mais `M` dans `VEGET5` à partir de 2015 (`5` seulement en 2010-2014). Les codes d'une même colonne changent de nomenclature selon la campagne (GEN p.5 ; SYL `docs/referentiels.md` l.162) : toujours lire `VEGET5` comme chaîne et la joindre aux modalités **avec la période**.

Définition d'IGN de la mortalité (M23 p.21) : flux de tous les arbres vus **vivants au premier passage et vus morts au second** (« stricto sensu »). Limites écrites par IGN : la date de mort est inconnue dans l'intervalle (effet de lissage) ; **sous-estimée** quand des arbres morts ont été prélevés avant le second passage (ils apparaissent comme coupés) ; avant 2019 les chablis vus à la 1re visite sont vivants ou morts sans qu'on le sache (« uniquement des chablis vivants à partir de 2019 »). Avant la publication 2020 : calcul depuis `DATEMORT` (mort depuis moins ou plus de 5 ans) observé à la 1re visite seule (M23 p.21). Les arbres déjà morts à la 1re visite sont exclus de la population à risque (par définition) ; si un arbre déjà mort est coupé, `PRELEV5`=0 (PLA p.7).

## 5. Recrutement (franchissement de 7,5 cm)

| Table | Colonne | Rôle | Unité | Source |
|---|---|---|---|---|
| ARBRE | `C13` | seuil 0,235 m (D13 ≥ 7,5 cm) ; classe de dimension PB 0,235 ≤ C13 < 0,705 ; MB 0,705 ≤ C13 < 1,175 ; GB ≥ 1,175 | m | ARB p.1, p.7 ; MD l.341-342 |
| ARBRE | `A`, `IDP`, `CAMPAGNE` | repérer une ligne de 2e visite sans ligne de 1re visite | — | ARB p.1, p.3 |
| PLACETTE | `VISITE` | distinguer les deux visites | 1, 2 | MD l.6100-6101 ; PLA p.3 |
| ARBRE | `W` | poids de la recrue | tiges/ha | ARB p.9 : disque de 6, 9 ou 15 m selon la classe, ou limites. **Poids d'une recrue cherchée sur 5 m : non documenté** (voir Q4) |
| ARBRE | `ESPAR` | essence de la recrue | `ESPAR1` | MD l.245-247 |
| PLACETTE | `DEF5`, `INSTP5`, `PRELEV5` | placettes où le flux est perturbé (voir §4) | — | MD |

Cercles de placette par classe (`ifn-placettes.md` §1, IMOT 2025 p.61) confirmés par ARB p.1 (« 6 m : tous PB, MB, GB ; 9 m : MB, GB ; 15 m : GB ») et GEN p.7 et p.9 (poids 88,4 ; 39,3 ; 14,1). Le décompte `W` dans le jeu réel de sylvostation : 1 393 des 1 550 lignes ont `W` entre 88 et 89, 39 et 40 ou 14 et 15 ; les autres portent une correction de lisière (ARB p.9 : « la position d'une ou deux limites sur la placette de 15 et 25 m »).

Ce que l'export ne donne pas : un statut « recrue » (à déduire), la date de franchissement du seuil, le poids de point (GEN p.2 : « les données brutes ne peuvent absolument pas permettre de recalculer des résultats d'inventaire car l'utilisateur ne dispose ni du poids des points, ni des règles de post-stratification »).

## 6. Station à la placette et valeurs indicatrices

| Table | Colonne | Libellé | Unité | Modalités | Années | Source |
|---|---|---|---|---|---|---|
| FLORE | `CD_REF` | Taxon de référence, **TAXREF v13.0**, disque de 15 m (700 m²) | `CDREF13` | libellé dans MD (bloc `CDREF13`, 3 659 taxons selon SYL l.161) | 2005- | MD l.40, l.210 ; FLO p.2 ; SYL `docs/referentiels.md` l.161 |
| FLORE | `ABOND` | Abondance-dominance (inspirée de Braun-Blanquet) | `ABOND` | 1 < 5 % présence faible ; 2 < 25 % présence nette ; 3 25-50 % ; 4 50-75 % ; 5 ≥ 75 % | 2005- | MD l.20, l.186, l.388-392 ; FLO p.3 |
| FLORE | `INCO_FLOR` | Incohérence floristique | `INCO_FLOR` | voir MD | 2016- | MD l.82, l.266 ; FLO p.3 |
| ECOLOGIE | `DATEECO` | Date du levé écologique et floristique | jj/mm/aaaa | — | 2005- | MD l.45 ; ECO p.3 |
| PLACETTE | `SER`, `GRECO` | Sylvoécorégion, grande région écologique (calculées par croisement avec les coordonnées réelles) | codes | 86 SER ; 11 GRECO | 2005- | MD l.73, l.145 ; PLA p.4 |
| PLACETTE | `XL`, `YL` | Centre de la maille kilométrique, Lambert-93 (point réel à 700 m au plus) | m | — | 2005- | PLA p.3 ; GEN p.2 note 1 |
| ESPAR→TAXREF | `espar-cdref13.csv` | colonnes `espar;lib_espar;cd_ref;lib_cdref` (ex. `9;Hêtre;97947;Fagus sylvatica`) | — | — | — | ESP l.42 |

Pour le sol (réserve utile, engorgement), sylvostation lit dans `ECOLOGIE` : `TEXT1`, `TEXT2`, `PROF1`, `PROF2`, `CAILLOUX`, `OBSPEDO`, `PGLEY`, `POX`, `PPSEUDO` (`R/placettes.R` l.380-413). Leur définition n'a pas été relue ici (fiche ECOLOGIE lue sur 4 pages sur 10).

- **Flore et écologie ne sont relevées qu'à la 1re visite** : FLO p.2 (« Les données relatives à la flore ne sont actuellement collectées que sur les points où s'applique le protocole 1re visite »), ECO p.3 (idem pour l'écologie), PLA p.3 (2e visite : « pas d'écologie notamment »), SYL `docs/referentiels.md` l.1675 (« la 2e visite n'a ni écologie ni flore »). Pour un arbre revu, le gradient trophique vient donc de la ligne `FLORE` de la **campagne de 1re visite** (même `IDP`, campagne = celle de la 1re visite), pas de la campagne de la ligne 2e visite.
- **Seule clé de sylvostation : (`CAMPAGNE`, `IDP`)** (`R/placettes.R` l.92, l.98-107 : `id_placette = CAMPAGNE_IDP`, arrêt si doublon). Les deux visites d'un point portent donc deux `id_placette` différents : aucun lien entre elles n'existe dans ce paquet.
- **Les valeurs indicatrices ne sont pas dans l'IFN.** Les trois fiches (FLO, ECO, GEN) ne décrivent aucune colonne de valeur indicatrice ; `FLORE.csv` ne porte que `CD_REF`, `ABOND`, `INCO_FLOR` (SYL `docs/referentiels.md` l.159 : en-tête lu). Comment sylvostation les obtient :
  - **source retenue :** Tichý L., Axmanová I., Dengler J. et al. (2023), « Ellenberg-type indicator values for European vascular plant species », *J. Veg. Sci.* 34, e13168 ; Zenodo `10.5281/zenodo.7427088`, v2.0 du 2022-11-07, CC BY 4.0 (SYL `inst/extdata/SOURCES.md` l.110-123 ; `R/indicateurs.R` l.1-3) ;
  - **colonnes lues** (feuille `Tab-IVs-Tichy-et-al2023`) : `Taxon`, `MOISTURE`, `REACTION`, `NUTRIENTS` ; `ph` = `REACTION`, `azote` = `NUTRIENTS`, `humidite` = `MOISTURE` (`R/indicateurs.R` l.46-56, l.89-90). Les valeurs sont des **indices ordinaux, pas des mesures de pH** (réaction et nutriments 1 à 9, humidité 1 à 12 ; `R/indicateurs.R` l.103-105) ;
  - **jointure :** les noms de Tichý sont Euro+Med, pas TAXREF ; sylvostation résout chaque `CD_REF` de la flore (TAXREF v13) comme `CD_NOM` de TAXREF v18, prend le nom du `CD_REF` v18, l'apparie par nom latin, puis (repli signalé) par binôme, synonyme ou agrégat « aggr. » (`R/indicateurs.R` l.98-229). Les non-appariés sont conservés en attribut, jamais supprimés ;
  - **indice trophique :** `grad_trophique` = moyenne de `grad_ph` et `grad_azote` ; chacun = moyenne par placette des valeurs des espèces présentes, pondérée en option par `ABOND` (milieux de classes 2,5 ; 15 ; 37,5 ; 62,5 ; 87,5 %, marqués « à vérifier ») ; option d'exclusion des essences arborées (`R/placettes.R` l.420-450, l.485-489, l.504-520) ;
  - **filtre préalable :** `filter_releves()` garde les relevés « en saison » (mois de `DATEECO` entre avril et septembre par défaut), sans incident récent (`NINCID` 1 à 5 ou `INCID` ≥ 1) et sans espèce à `INCO_FLOR` renseigné (`R/placettes.R` l.141-199) ;
  - **autres sources écartées par sylvostation :** Baseflor (Julve ; HTTP 403, colonnes non lues) et EcoPlant (AgroParisTech, sur demande, non déposable) (`R/indicateurs.R` l.149-156 ; `docs/referentiels.md` §14). Réserve de licence non tranchée : le jeu Tichý reprend les valeurs de Julve pour la France, annoncées CC BY-SA 2.0 (`SOURCES.md` l.124-128).
  - La spec de sylvigenese (§8) retient déjà « Tichý et al. 2023 » ; le jeu d'extraits de sylvostation `tichy_2023_extrait.csv` ne couvre que 189 taxons de la zone test (SOURCES.md l.117).
- **Seconde source sur les valeurs indicatrices : aucune indépendante.** Baseflor reprend Julve comme Tichý pour la France (SYL `docs/referentiels.md` l.331-333). Non comparé.

## 7. Écarts et contradictions entre sources

1. **Unité de `C13` : mètre (export) contre millimètre (saisie, jeu fictif, spec).** Export : mètres (MD l.35 et l.203 ; ARB p.7 ; REC l.18 ; 1 550 lignes réelles de sylvostation). Saisie de terrain : millimètres (IMOT 2025 p.71, selon `ifn-placettes.md` §2) ; `PRE` l.15-16 donne la **précision** de `C13` en `mm`. Le jeu fictif de sylvigenese (`tests/fixtures/zone_fictive/inputs/ifn/ARBRE.csv`, colonne `C13` : 387, 2513, 1184) est en **millimètres**, et `docs/spec.md` §12 l.239 demande de « confirmer que `c13` y est en millimètres » : **la réponse est non**. Le décalage est de facteur 1 000. Non corrigé ici : décision de Pascal (Q1).
2. **`IR5` : « moyen » (MD l.87) contre « cumulé » (ARB p.9, M23 p.19).** Définition de `metadonnees.csv` : « Accroissement radial **moyen** de l'arbre lors des 5 dernières années » ; fiche ARBRE : « épaisseur **cumulée** des 5 derniers cernes ». Les valeurs réelles (SYL `ifn_arbre.csv`, 1re ligne : `C13` 1,030 m, `IR5` 0,0300 m ; `C13` 0,300 m, `IR5` 0,0090 m) sont compatibles avec un cumul (3 cm et 9 mm de rayon en 5 ans), pas avec une moyenne annuelle (3 cm/an). Retenu comme **cumul sur 5 ans**, avec deux sources concordantes, mais à confirmer sur le terrain (Q5).
3. **Nom des coordonnées : `XL`, `YL` (PLA p.3 ; en-tête réel) contre `GEOM93` (MD l.71 et en-tête l.14).** Le fichier réel porte `XL;YL` (SYL `docs/referentiels.md` l.157).
4. **`PRELEV5` listé sans unité ni modalité.** Défini en MD l.134 et PLA p.7, présent dans l'en-tête de `PLACETTE.csv` (SYL l.157), valide 2010-2014 seulement selon REC l.115, mais **aucune ligne d'unité ni de modalité dans MD** (aucune occurrence en dehors de l.134). Ses codes sont inconnus.
5. **Colonnes de 2e visite collectées mais non exportées.** `PRE` cite des données de 2e visite : `C135`, `MES_C135`, `INCID5`, `NINCID5`, `CSA5`, `DC5`, `AUTUT5`, `BOIS5`, `UTIP5`, `PEUPNR5`, `TPLANT5`, `LIGN15`… (lignes 9, 11, 17, 25, 31, 56, 58, 74, 81, 108, 142…). L'export ne porte qu'une colonne `C13` (valeur actualisée, ARB p.1) et `NINCID`/`INCID` sont étiquetés « 1re visite » (MD l.81, l.100). **Un incident survenu entre les deux visites (tempête, sécheresse) n'a donc pas de colonne d'export**, sauf traces indirectes (`VEGET5`=T, `DEF5`, `PRELEV5`).
6. **`VEGET` à la 2e visite.** PRE l.148-149 donne une précision de `VEGET` en visite 1 **et** en visite 2, et de `VEGET5` en visite 2 ; ARB p.1 dit que les lignes 2e visite ne reprennent que les valeurs actualisées. Ce que contient `VEGET` sur une ligne `VISITE`=2 n'est dit nulle part (Q3).
7. **`W` : « poids de l'arbre à l'hectare » (ARB p.9, GEN p.9) contre « rapport de la surface d'extension de deuxième phase du point à la surface de la placette de mesure » (MD l.180).** Les valeurs réelles (88,41 ; 39,29 ; 14,14) sont celles de la première définition ; la définition de MD est incompatible (ce ne serait pas un nombre de tiges par ha).
8. **Définitions de `DOM3` (`LIB`) recopiées de `ORI` dans MD** (l.5202-5204 : « Couvert libre nul ; Arbre provenant d'un rejet de souche »). Les libellés suivent ARB p.6 ; les définitions de MD sont fausses.
9. **`ARB` cite `VEGET` = « 0 ou Z »** (pages 5 et 6, `LIB`, `FORME`) ; MD ne contient aucun code Z (DOM8M0, DOM8M1, DOM8M2, l.6063-6074).
10. **`CSA` :** MD l.43 « Couverture du sol (1e visite) » contre PLA p.9 « de 1re ou de 2e visite ».
11. **Rayon de la placette écologique/flore :** 15 m (700 m²) dans FLO p.1, ECO p.1, MD l.20, contre 25 m (20 ares) pour `TOPO` et la plupart des variables de placette (ECO p.4, PLA p.1). Pas de contradiction : deux placettes différentes ; à ne pas confondre dans la documentation de `dynamics`.
12. **Millésimes des fiches :** PLA v2.5 du 07/10/2026 ; ARB v2.4 et GEN v3.0 du 14/10/2025 ; ECO v2.3 du 14/10/2025 ; FLO v2.0 du 18/10/2022 (TAXREF v13.0). La mise à jour de l'export du 2026-10-07 n'a donc pas relancé toutes les fiches.
13. **Placette de 5 m (2015) et seuils.** GEN p.3 et M23 p.9 la citent pour 2015 seulement ; ARB p.1 écrit « pour chaque nouvelle campagne annuelle, 70 000 à 80 000 nouveaux arbres recensables » sans rayon.
14. **`ifn-placettes.md` (mission 016)** déclarait `c13` « non vérifié pour l'export » et l'archive « non lue » : levé ici (écart 1). Son flou « 700 m » concorde avec GEN p.2 note 1 et PLA p.3.

## 8. Questions à trancher (sans les trancher)

- **Q1. Unité de `C13` dans les contrats et le jeu fictif.** L'export est en mètres ; le fixture et la spec §12 supposent des millimètres. Faut-il garder le mètre de l'export dans `contracts/` (formule `d130_cm = C13_m × 100 / π`), ou convertir à l'entrée de `prepare` et le dire ? À décider avant 023 (contrats) et 024 (jeu fictif).
- **Q2. Définition de la population à risque pour la mortalité.** Arbres `VEGET`=0 (ou 1, chablis vivant depuis 2019) à la 1re visite, revus à `VEGET5`=0, M, 2, A, 1 ? Que faire de `6`/`7` (coupés : censure ou exclusion de la placette ?), de `N` (non retrouvé) et de `T` (cassé sous C13, ou perdu pour incident) ? Quelles placettes écarter (`PRELEV5`, `DEF5` ≥ 1, `INSTP5`=1, `NINCID` ≠ 0, `NLISI5` ≠ 0, `PEUPNR` ≠ 0, `CIBLE`=0, peupleraies `CSA`=5) ? IGN note que la mortalité est sous-estimée quand des morts sont coupés avant la 2e visite (M23 p.21).
- **Q3. Contenu d'une ligne `VISITE`=2.** Quelles colonnes d'`ARBRE.csv` sont renseignées (`VEGET`, `VEGET5`, `C13`, `IR5`, `HTOT`, `W`) ? Faut-il jointer `ARBRE` et `PLACETTE` par (`CAMPAGNE`, `IDP`) pour porter `VISITE` sur chaque arbre ? À vérifier sur l'export réel avant tout ajustement (point au sol n° 1).
- **Q4. Recrutement : domaine et poids.** Pour 2016 et après, quel rayon cherche les recrues (5 m comme en 2015, ou le dispositif complet 6/9/15 m) ? Quel `W` pour une recrue cherchée sur 5 m (10 000 / (π × 5²) = 127,3 serait un calcul de l'acquéreur, non documenté) ? Le recrutement s'ajuste-t-il sur les seules lignes 2e visite sans ligne 1re visite, et sur quelle plage de campagnes (2015 à 2025 ?) ?
- **Q5. Accroissement : `IR5` (carottes, partielles : 53 % des arbres du jeu de sylvostation) ou différence de `C13` entre visites (pour les arbres revus) ?** Les deux se recoupent-ils ? Pas de choix de modèle ici.
- **Q6. Intervalle réel.** Utiliser 5 ans nominaux ou `DATEPOINT`(visite 2) − `DATEPOINT`(visite 1) pour mettre les taux à l'année ?
- **Q7. Gradient trophique d'un arbre revu.** Prendre la flore du relevé de 1re visite (seule disponible), à 5 ans de la 2e visite ; accepter ce décalage et l'écrire dans `rapport_dynamics.html` ?
- **Q8. Clé de placette.** `dynamics` doit-il joindre les deux visites par `IDP` (pas par `id_placette` = `CAMPAGNE_IDP` de sylvostation) ? Qui tient cette jointure (R, `prepare`) ?
- **Q9. Licence des valeurs de Tichý** : CC BY 4.0 annoncée, réserve CC BY-SA 2.0 sur les valeurs de Julve ; reprise de la question non tranchée de sylvostation.
- **Q10. Fiches ou export de 2e visite plus précis.** Faut-il demander à l'IGN (ou lire l'IMOT, instructions de 2e visite) la règle de recrutement 2016+, `PRELEV5` et le contenu d'une ligne 2e visite ?

## 9. Trois points au sol (à vérifier sur un export réel de Pascal)

1. **Une ligne de 2e visite d'`ARBRE.csv`.** Prendre un `IDP` avec `VISITE`=1 en 2015 à 2020 dans `PLACETTE.csv` et son `VISITE`=2 cinq campagnes plus tard : le même `A` existe-t-il aux deux campagnes ? Quelles colonnes sont vides sur la ligne 2e visite (`VEGET` ? `VEGET5` ? `IR5` ? `HTOT` ?) ? Les nouveaux arbres ont-ils un `A` absent de la 1re visite ? C'est la jointure de la mortalité et du recrutement.
2. **`C13` et `IR5`.** Une valeur courante de `C13` doit valoir 0,3 à 2 (mètres) ; `IR5` doit être de l'ordre de 0,005 à 0,05 (mètres, cumul 5 ans) et vide pour une part importante des arbres. Comparer `IR5` d'un arbre carotté en 1re visite au `C13` revu : `(C13_visite2 − C13_visite1) / (2π)` doit être du même ordre.
3. **Mortalité : un arbre `VEGET5` = N ou T, et un point avec `DEF5` ou `PRELEV5`.** Compter, sur une SER, la part d'arbres 1re visite vivants dont `VEGET5` est 0, M, 2, A, 1, 6, 7, N, T. Si `N` et `T` dépassent quelques pour cent, la définition de la population à risque (Q2) est à poser avant l'ajustement. Vérifier aussi que `PRELEV5` est vide pour 2015 et après.

## 10. Ce que je n'ai pas pu lire

- **Aucun fichier `ARBRE.csv` ni `PLACETTE.csv` de 2e visite** n'était disponible : seuls l'extrait de sylvostation (100 placettes de la campagne la plus récente, toutes en 1re visite) et le fixture fictif. Les règles de revisite viennent de la documentation, non de la donnée. Aucun chiffre sur la part d'arbres revus, perdus ou recrutés.
- **IMOT** (instructions de terrain) : la partie « deuxième visite » (rayon de recherche des recrues, 2016 et après) n'a pas été lue ; seule la page 61 l'avait été en mission 016.
- **`IGN_DB_doc_ecologie.pdf`** : pages 5 à 10 non lues (humus, sol, texture, roche, hydromorphie). Les définitions de `TEXT1`, `TEXT2`, `PROF1`, `PROF2`, `CAILLOUX`, `PGLEY`, `POX`, `PPSEUDO` sont connues seulement par MD (libellés et unités) et par l'usage de sylvostation.
- **Modalités de `ESPAR1`** (≈ 120 essences) et de `CDREF13` (3 659 taxons) : non reprises ; à lire dans MD et `espar-cdref13.csv` au moment du contrat des essences.
- **Autres documents de l'archive** (`IGN_DB_doc_bois_mort.pdf`, `couvert`, `habitat`, `ecologie_annexes`) : hors périmètre, non lus.
- **Tichý et al. (2023)** : classeur Zenodo non ouvert ici ; ce qui en est dit vient de sylvostation. Valeurs indicatrices : aucune seconde source indépendante.
- **M23** : lu seulement aux pages 3, 4, 9, 19, 20, 21 ; page 22 (« état de végétation ») et la partie « placettes semi-permanentes » complète n'ont pas été vues.
- **Liste de contrôle de l'orchestrateur :** non reçue dans la consigne. Pointage fait sur les critères de la fiche de mission (colonne = fichier et page ou ligne ; deux sources pour les règles de revisite ; non-trouvé dit).

## Liste de contrôle (critères de la fiche de mission 022)

- [x] Chaque colonne a sa source (fichier, page ou ligne de `metadonnees.csv`).
- [x] Règles de revisite : au moins deux sources (documentation générale, fiche ARBRE/PLACETTE, Méthodologie IGN 2023).
- [x] Source des valeurs indicatrices (sylvostation, Tichý et al. 2023) décrite avec fichiers et lignes.
- [x] Ce qui manque ou se contredit : §7 (14 écarts). Ce qui n'a pas été lu : §10.
- [ ] Liste de contrôle propre de l'orchestrateur : non reçue.
- [ ] Une seconde source indépendante pour les valeurs indicatrices : non trouvée.
- [ ] Vérification sur un export réel avec 2e visite : à faire par Pascal (§9).
