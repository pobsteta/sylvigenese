# Volume, biomasse et carbone : sources comparées pour le module `post` (mission A du plan `post-volume-carbone`)

- **Propriétaire :** Pascal
- **Date de consultation :** 2026-11-25
- **Mission redite :** comparer, grandeur par grandeur, les sources possibles du tarif de volume, de l'infradensité, de l'expansion des branches, de la fraction de carbone et des racines. Il faut aussi confirmer, fichier et ligne à l'appui, les trois écarts de définition de tarif-nemeton.
- **Décisions éclairées :** les questions Q1 à Q4 du plan `docs/plans/post-volume-carbone.md` (§6), et en partie Q5 (domaine) et Q6 (accord avec le `V` de l'IFN). Elles disent quel tarif fait foi, comment il entre dans `params/`, quel volume la fiche affiche et quels compartiments du carbone on garde.
- **Fichier tabulaire :** `docs/referentiels/volume-carbone.csv`, une ligne par couple (grandeur, source), 17 colonnes. La colonne `fichier_ligne` donne l'endroit exact où l'on a lu. La colonne `lecture` dit comment : `lue` (fichier ou page ouverts), `recherche web seule` (vu dans un résumé de moteur, page non ouverte) ou `non lue`.
- **Nom des fichiers :** la consigne de l'orchestrateur nomme `volume-carbone.*`, le plan (§3, mission A) nommait `tarif-volume-carbone.*`. J'ai suivi la consigne.
- **Règle suivie :** **aucun coefficient, aucune densité, aucune fraction de carbone n'est recopié ici**, ni de tarif-nemeton (dépôt sans licence) ni d'une source non ouverte. On ne trouve ici que des références, des domaines, des définitions de compartiments et des rapports de contrôle, chacun avec son fichier et sa ligne. Les valeurs entreront dans `params/` par `import_tarif`, depuis la source unique que Pascal aura choisie.
- **Méthode :** lecture seule de tarif-nemeton, de la documentation IFN et des référentiels de sylvigenese. Rien n'a été exécuté. Les contrôles arithmétiques (écart 1) ont été faits à la main sur une ligne de la table.

## 1. Sources consultées, versions, accès

| Source | Version vérifiée | Accès dans cette session |
|---|---|---|
| tarif-nemeton | clone `/home/user/tarif-nemeton`, commit 0f51b96 (celui de la mission 008, non revérifié dans `.git`) ; méthodologie v2.23 du 3 octobre 2026 (`README.md:8`) | lu |
| Documentation IFN | `IGN_DB_doc_arbre.pdf` v2.4 du 14/10/2025 ; `metadonnees.csv` de l'archive 2025 | lu |
| nemeton (`emerge_coefficients.csv`, `infradensite_espar.csv`, `ifn_volume_equations.csv`, `ifn_tarif_schaeffer_ser.csv`) | bd6fbe5 (mission 008) | **non relu** : aucun clone de nemeton sous `/home/user`. Je ne cite que ce que les missions 008 et 011 en ont écrit. |
| Pages en ligne | — | **`hal.inrae.fr` et `hal.science` non résolus** (hôtes hors des domaines permis). Comme la consigne le demande, je n'ai plus tenté d'autre hôte ensuite. Les autres informations en ligne viennent de résumés du moteur de recherche, qui n'ont pas valeur de lecture. Pour lire les articles, il faut autoriser `hal.inrae.fr`, `hal.science`, `www.ipcc-nggip.iges.or.jp`, `cran.r-project.org`, `entrepot.recherche.data.gouv.fr` et `www.inrae.fr`. |

## 2. Le CQQCOQP de chaque source retenue pour la comparaison

Les sources que je ne compte pas proposer (V08 Schaeffer, V09 `ifn_volume_equations.csv`, D03, D05, C03) ne sont que dans le CSV. Le **Pourquoi** est le même pour toutes : choisir la source d'une grandeur de `post` (Q1 à Q4).

| Source | Qui, dans quel but | Quoi | Comment | Où | Quand | Combien (précision, coût) |
|---|---|---|---|---|---|---|
| **V01-V03 tarif NEMETON v5** | Pascal, pour succéder à EMERGE (`README.md:3-6`) | feuillus : volume aérien total ; résineux : volume de tige, plus E(D) | feuillus : QSM TLS corrigés, modèle bayésien, niveau calé sur des arbres abattus (`README.md:13-23`). Résineux : profil de tige calé sur sections mesurées (`nemeton_tarif_v5.py:65-76`) | forme : Allemagne (BioDiv) ; niveau : Belgique, Allemagne ; contrôles : France (Hesse), Suisse (EFM) | méthodologie v2.23, 3 oct. 2026 ; état « recherche en cours » | gratuit et déjà lu. Mais pas de licence, « ne pas utiliser en production » (`README.md:8-9`), et il évolue encore. |
| **V04-V05 Vallet 2006, via GCubeR** | INRA et IFN, équations nationales de volume aérien total (titre) | VTA (aérien total) et vc22 (bois fort tige) | régression sur arbres cubés, entrées c130 et htot (résumé) | France : Landes, nord, montagnes de l'Est (résumé) | publié en 2006 ; GCubeR 0.1.3 en 2026 | 4 619 arbres (résumé) ; GCubeR est sous licence MIT, donc redistribuable |
| **V06 EMERGE** | ONF, INRA, FCBA : bois énergie, volume à toute découpe, biomasse (`TARIF_NEMETON_v2.23.pdf` p. 3) | volume total par coefficient de forme ; découpes en cascade | modèle « spécifique sinon feuillus/résineux » (p. 3) | France, fonds Oudin, environ 8 000 arbres (p. 3) | 2009-2013 | données sur demande (`nemeton_fetch_densite.py:213-217`) ; coefficients non lus |
| **REF `V` de l'IFN** | IGN, pour la statistique nationale | bois fort tige à 7 cm, réfacté | tarifs IGN : à 2 entrées de 2005 à 2013, à 3 entrées (avec HDEC) dès 2014 (`IGN_DB_doc_arbre.pdf` p. 9) | France | campagnes annuelles | équations non trouvées publiées ; Etalab 2.0 |
| **D01 XyloDensMap** | IGN et INRAE (Leban et al. 2025) | infradensité d'une carotte à 1,30 m, 156 espèces | carottes IFN, retrait de littérature ou mesuré (`sources-infradensite-point1.md:9,21`) | France, placettes IFN à la maille de 1 km | 2016-2019 | 110 763 arbres ; Etalab 2.0 (trois sources concordantes) |
| **D02 constantes de tarif-nemeton** | Pascal | densité de carotte × facteur arbre entier | XDM corrigée, littérature, TapeS selon l'essence (`nemeton_tarif_v0.py:32-42` ; `nemeton_tarif_v5.py:94-96`) | comme leurs sources | sept. et oct. 2026 | dans le code seulement, sauf le facteur bayésien (`resultats/bayes/coefficients_forme.csv`) |
| **D06 Billard 2020** | INRAE (Silva), densité par compartiment | rapports densité du compartiment / densité à 1,30 m | tomographie RX (`sources-infradensite-point1.md:11`) | France, peuplements ONF | 2020 | 8 arbres par essence ; trois résineux seulement |
| **E01 E(D) résineux de tarif-nemeton** | Pascal | rapport aérien total / tige | calé sur arbres mesurés ou pesés (`nemeton_tarif_v5.py:85-90`) | Suisse, Belgique, Finlande | oct. 2026 | sapin, mélèze et douglas « PROVISOIRES » |
| **E03 Longuetaud et al. 2013** | INRA, ONF (base EMERGE) | facteur d'expansion de volume, fonction de D et H (résumé) | 8 192 arbres abattus, 19 essences (résumé) | France | 2013 | article non ouvert |
| **C01 Thomas et Martin 2012** | Université de Toronto, synthèse mondiale | teneur en carbone des tissus | méta-analyse : 253 relevés de bois de tige, 34 d'autres tissus (résumé) | monde | 2012 | accès ouvert ; données sur Dryad |
| **R01-R02 GIEC 2006, tab. 4.4, et Mokany 2006** | GIEC, pour les inventaires nationaux ; Mokany : méta-analyse | rapport R racines / aérien, par type de forêt et classe de biomasse | Mokany : 786 observations, dont 62 % écartées (résumé) | monde, zone tempérée | 2006 (le tableau a été mis à jour en 2019) | valeurs **non lues** |

**Deuxième source qui se tromperait pour une autre raison.** J'en ai cherché une pour chaque grandeur :

- **Volume.** Vallet 2006 se tromperait autrement que NEMETON : il vient d'arbres cubés français et non de nuages TLS allemands. Le `V` de l'IFN se tromperait autrement encore : il est réfacté, et ses tarifs IGN demandent HDEC.
- **Infradensité.** Billard 2020 et les mesures destructives (`resultats/densite/LISEZMOI.md:35-40`) se trompent autrement que XyloDensMap : disque ou arbre entier, contre carotte.
- **Expansion des branches.** La seconde source est Longuetaud 2013 (EMERGE, France), face à E(D) (Suisse, Belgique).
- **Carbone.** La seconde source est la valeur du GIEC.
- **Racines.** GIEC 2006 et Mokany ne sont pas indépendants (le tableau 4.4 est réputé tiré de Mokany, lien non vérifié). Le Goff 2019 (hêtres de Hesse, mesurés) en serait une, mais pour le hêtre seulement.

## 3. Les trois écarts de définition de tarif-nemeton : confirmés

Les numéros de ligne du plan (§1, « l. 297-307 ») sont décalés de 3 lignes : le filtre H/D des résineux est à la **l. 300**, non 297.

**Écart 1 : pour les résineux, `biomasse_t` et `carbone_t` sont calculés sur la tige seule. Confirmé.**
- `code/nemeton_tarif_v5.py:300-302` : pour un conifère, `V = tige_resineux(sp, D, H)` et `comp = "tige"`.
- `:307` : `B = V * r / 1000 ; Cc = B * V0.CFRAC[typ]`. La biomasse `B` et le carbone `Cc` partent donc de la tige.
- `:310-311` et `:316` : l'aérien total `V_aer = V × E(D)` ne sert qu'à la colonne `biomasse_aerienne_t`, et aucun carbone aérien n'est écrit pour les résineux.
- **Contrôle sur la table** (`resultats/tarif_v5/tables_tarif_v5.csv:768`, épicéa, D = 10 cm, H = 10 m) : `biomasse_t` est égal à `V_m3 × rho_kg_m3 / 1000`, et `biomasse_aerienne_t` à `V_aerien_total_m3 × rho_kg_m3 / 1000`. `carbone_t` est égal à `biomasse_t × 0,508`, la fraction des conifères (`nemeton_tarif_v0.py:43`). Calcul fait à la main.
- Pour les feuillus, `V` est l'aérien total (`:298`). La même colonne `carbone_t` porte donc **deux compartiments selon le groupe**.
- Une réserve de plus : la densité appliquée aux branches des résineux est celle de la tige (`:316`). Billard 2020 trouve pourtant les branches d'épicéa plus denses que la tige (`sources-infradensite-point1.md:54`).

**Écart 2 : `V_sup7` n'a pas la même définition selon le groupe. Confirmé.**
- **Feuillus** (`:296`) : `Vc[cut] = V × min(frac(sp, cut, D) / corr_menu_bois(sp, D), 1)`, avec `V` = aérien total. Les fractions sont ajustées sur `V_sup{cut} / V_cor`, où `V_cor` est le volume QSM de l'arbre entier (`:193`, `:237`). C'est donc la part de l'arbre entier au-delà de 7 cm, **grosses branches comprises**.
- **Résineux** (`:301`) : `Vc[cut] = tige_resineux(sp, D, H, cut / 100)`, c'est-à-dire la **tige** au-delà de la découpe.
- Le dépôt le dit lui-même : « NEMETON > 7 cm (branches comprises) » (`resultats/etage_b/LISEZMOI.md:15-16`).

**Écart 3 : ni racines, ni sol, ni bois mort. Confirmé.**
- L'en-tête de la table (`tables_tarif_v5.csv:1`) n'a aucune colonne de racines, de sol ou de bois mort.
- `nemeton_tarif_v5.py` ne calcule aucun compartiment souterrain. Attention à un homonyme : la variable `RACINE` (l. 138) désigne le dossier racine du dépôt, pas les racines de l'arbre.
- `README.md:3` annonce « l'arbre entier (tige et branches) ».

## 4. Autres écarts relevés entre sources

1. **XyloDensMap est redistribuable, contrairement à ce que dit le plan.** Le plan dit « XyloDensMap n'est pas redistribuable » (l. 86 et 334), en s'appuyant sur `README.md:75,79` de tarif-nemeton : « non redistribué ici ». Mais trois sources donnent pour les **données** la licence **Etalab 2.0** : la note `documents/notes/sources-infradensite-point1.md:9-10`, la méthodologie `TARIF_NEMETON_v2.23.pdf` p. 35, et la notice b2find vue en recherche web. « Non redistribué ici » est un choix du dépôt, non une interdiction. Seul l'**article** est noté CC BY-NC-ND (`nemeton_fetch_densite.py:244`). Je n'ai pas pu ouvrir la page de Recherche Data Gouv pour le confirmer à la source.
2. **L'infradensité de tarif-nemeton ne vient pas toute de XyloDensMap.**
   - Pour l'érable, le charme et le bouleau, la valeur vient de « littérature (GCubeR) » (`nemeton_tarif_v0.py:36-38`), alors que le dépôt a leurs valeurs XyloDensMap (`donnees/xdm_essences_secondaires.csv:2,5,6`).
   - Pour le douglas, elle est « équivalente TapeS » (`nemeton_tarif_v5.py:75-76,95-96`).
   - Pour l'épicéa, elle est multipliée par un facteur de Billard (`nemeton_tarif_v0.py:42`).
3. **Deux définitions du `V` de l'IFN.**
   - `IGN_DB_doc_arbre.pdf` p. 9 : « tige principale jusqu'à la découpe bois fort (7 cm fin bout) », volume « réfacté », non actualisé.
   - `metadonnees.csv:174` : « volume du tronc […] du sol jusqu'à une découpe de 7 cm, **incluant l'écorce et une branche maîtresse** ».
   - Le plan (l. 63-64) ne retient que la première.
4. **Le `V` de l'IFN est sous Vallet.** Sur les mêmes arbres à Fontainebleau, `V` IFN = 0,80 à 0,86 × Vallet bois fort tige (`resultats/etage_b/LISEZMOI.md:15`). Un tarif calé au niveau de Vallet ou d'EFM tombera donc au-dessus du `V` IFN, sans être faux pour autant : réfaction, tarifs IGN différents. Cela pèse sur le critère b de Q6.
5. **Vallet 2006 : sept essences ou six équations ?** Le titre dit sept essences, le résumé HAL six équations (pins maritime et sylvestre réunis ; vu en recherche web). tarif-nemeton juge par ailleurs le VTA de l'épicéa (via GCubeR) « incohérent » : il est inférieur au vc22 (`archives/obsolete/tarif-v0-et-controle-externe_26-09.md:28`).
6. **La publication de Longuetaud existe**, contrairement à ce que laissait supposer le plan (« si une publication française existe ») : *For. Ecol. Manage.* 292 : 111-121 (2013), d'après la recherche web, et non *Ann. For. Sci.*
7. **Les bornes de calage du v5 ne sont dans aucun fichier de résultats.** Le code filtre la grille sur `dbh_min × 0,9`, `dbh_max × 1,1` et `h_min − 2`, `h_max + 2` (`nemeton_tarif_v5.py:294`). Ces bornes sont calculées sur les données (`nemeton_tarif_v0.py:81-82`) et écrites seulement pour le **v0** (`code/tarif_v0_src/tarif_v0/coefficients_tarif_v0.csv:2-7`). La grille v5 lue à H = 20 m concorde avec ces bornes v0 : hêtre, frêne et bouleau dès 10 cm ; chênes, érable et charme dès 15 cm ; maximum charme 35, bouleau 40, frêne 45, érable 60 cm. C'est ce que disait le plan, mais rien ne garantit que les bornes v5 soient celles du v0.
8. **Le domaine des feuillus sous 10 cm n'est pas établi.** La grille commence à 10 cm (`:290`). Les bornes v0 descendent à 8 cm pour le hêtre et à 7 cm pour le frêne (`coefficients_tarif_v0.csv:2,6`). La formule couvre peut-être les recrues de 7,5 cm pour ces deux essences, mais aucun fichier v5 ne le dit.

## 5. Les critères du plan, source par source

Les critères sont ceux du plan (§2) :
1. essences couvertes ;
2. domaine dès 7,5 cm ;
3. compartiment sans ambiguïté ;
4. entrées limitées à d130 et h ;
5. licence ;
6. accord avec le `V` de l'IFN ;
7. calage français ou européen.

| Source | 1. Essences (espar) | 2. Dès 7,5 cm ? | 3. Compartiment | 4. d130 et h seuls ? | 5. Licence | 6. Accord `V` IFN | 7. Calage |
|---|---|---|---|---|---|---|---|
| V01-V02 NEMETON v5 | 13 sur 195 (02, 03, 09, 11, 12P, 12V, 15S, 17C ; 52, 61, 62, 63, 64) | non établi (grille dès 10 ; chênes dès 15 ; résineux bornés en H/D) | défini mais **mêlé dans la grille** (écarts 1 et 2) | oui | aucune | aérien total = 1,37-1,50 × `V` ; « > 7 cm » = 1,24-1,29 × `V` (Fontainebleau) | Europe (DE, BE, CH), contrôles en France |
| V04-V05 Vallet via GCubeR | 7 d'après le résumé (03, 09, 51, 52, 61, 62, 64) ; 02 absent | non lu | VTA et vc22 nets | oui (c130 = π·d130) | article de l'éditeur ; GCubeR sous MIT | `V` = 0,80-0,86 × vc22 | France |
| V06 EMERGE | toutes, par repli feuillus/résineux | non lu | volume total et découpes | h_dec peut-être nécessaire | données sur demande | non connu | France |
| REF `V` IFN | toutes | oui (> 7,5 cm) | bois fort tige réfacté (deux libellés, §4.3) | **non** (HDEC) | Etalab 2.0 | — | France |

## 6. Recommandation par grandeur (l'IA propose, Pascal tranche)

1. **Tarif de volume.**
   - Proposition : le tarif NEMETON v5, figé au commit 0f51b96 et marqué `provisoire`, comme le BRIEF §6 et la proposition Q1 du plan. Les feuillus se lisent dans `coefficients_feuillus_v5.csv`. Pour les résineux, il faut un fichier de résultats que Pascal ajouterait à tarif-nemeton (Q2).
   - Source de contrôle : **Vallet 2006 via GCubeR** (MIT, donc redistribuable, calage français), dans son domaine. C'est la seule seconde source lisible sans demande d'accès. EMERGE reste hors d'atteinte (données sur demande, coefficients non lus).
   - Les tarifs IGN sont écartés comme tarif : ils demandent HDEC.
2. **Volume affiché (bois fort).**
   - Résineux : la tige au-delà de 7 cm de NEMETON est comparable au `V` IFN.
   - Feuillus : NEMETON ne donne **pas** de bois fort tige. Il y a trois voies :
     - (a) afficher « bois > 7 cm, branches comprises », avec sa définition ;
     - (b) prendre le vc22 de Vallet pour les feuillus qu'il couvre ;
     - (c) attendre la lecture de Longuetaud 2013.
   - Je propose (a), en écrivant l'écart de définition dans la fiche, et de garder l'aérien total comme volume de référence du carbone. C'est à trancher en Q3.
3. **Infradensité.**
   - Proposition : **XyloDensMap comme source unique** de la densité à 1,30 m. Elle est sous Etalab 2.0, couvre 156 espèces, vient de France, et `import_tarif` peut la lire directement : une seule source de vérité pour la valeur.
   - Le facteur arbre entier vient de `resultats/bayes/coefficients_forme.csv` pour le hêtre, les chênes et le frêne, et de Billard 2020 pour les résineux qu'il couvre.
   - Les valeurs « littérature » et « TapeS » de tarif-nemeton (érable, charme, bouleau, douglas) ne sont pas reprises sans décision de Pascal.
4. **Expansion des branches.**
   - Feuillus : inutile, le tarif donne l'aérien total.
   - Résineux : l'E(D) de tarif-nemeton, à sortir du code vers un fichier de résultats (Q2). Il faut l'appliquer à la tige NEMETON et à elle seule (`nemeton_tarif_v5.py:125-126`).
   - Longuetaud 2013 est à lire avant de décider s'il doit servir de seconde source.
5. **Fraction de carbone.**
   - Proposition : Thomas et Martin 2012, par groupe feuillu ou résineux de `species.csv`, **valeurs relues dans l'article** et non reprises du code de tarif-nemeton. La valeur par défaut du GIEC 2006 (tableau 4.3) sert de comparaison.
   - Il faut corriger l'écart 1 dans `post` : le carbone se calcule sur l'aérien total pour les deux groupes.
6. **Racines.**
   - Proposition : le rapport R du **GIEC 2006, tableau 4.4**, par groupe et par classe de biomasse aérienne, dans une colonne à part marquée `provisoire` (Q4). Mokany 2006 sert à expliquer le tableau, pas de seconde source indépendante. Le Goff 2019 sert de contrôle pour le hêtre.
   - **Je n'ai pas pu chiffrer la part des racines** : aucune valeur n'a été lue.

## 7. Ce qui reste incertain

- **Aucune page d'article n'a été ouverte** (HAL non résolu). Les références de Vallet, EMERGE, Longuetaud, Thomas et Martin, Mokany, du GIEC et de GCubeR ne sont vérifiées que par des résumés de recherche.
- Les valeurs du GIEC (tableaux 4.3, 4.4 et 4.14) n'ont pas été lues, pas plus que celles de Thomas et Martin dans l'article.
- Les **bornes de calage du v5** ne sont écrites nulle part. Il reste aussi à savoir si la formule des feuillus vaut entre 7,5 et 10 cm.
- La licence de XyloDensMap n'est pas lue sur sa page de dépôt (trois sources concordent, mais aucune n'est le dépôt lui-même).
- Les essences et les bornes de Vallet dans GCubeR, et le domaine de Vallet 2006 (étendue de c130), sont inconnus.
- EMERGE : on ne sait pas si la hauteur de décrochement est une entrée. Les coefficients du `emerge_coefficients.csv` de nemeton ne sont pas relus.
- La définition exacte du facteur de Longuetaud 2013 (volume total / bois fort tige ?) et ses 19 essences sont inconnues.
- On ne sait pas si le `V` de l'IFN inclut ou non une branche maîtresse (§4.3).
- Le rapport OMINEA du CITEPA n'a pas été trouvé, et rien n'a été trouvé sur CARBOFOR (Loustau 2004).
- On ne connaît pas l'accord arbre par arbre entre NEMETON résineux et le `V` de l'IFN.

## 8. Ce que Pascal doit décider

Ces questions sont à poser une par une, dans l'ordre du plan :
- **Q1.** Quel tarif fait foi ? Les pièces : §5 et V01-V06.
- **Q2.** Comment le tarif NEMETON entre-t-il dans sylvigenese ? Les constantes des résineux, E(D) et les densités ne sont que dans le code.
- **Q3.** Quel volume affiche la fiche ? Pour les feuillus, il n'y a pas de bois fort tige dans NEMETON (écart 2).
- **Q4.** Quels compartiments du carbone ? Les racines par le GIEC 2006, tableau 4.4, valeurs à lire.

Trois points nouveaux sont à joindre à ces questions :
- **Q2 (XyloDensMap).** Accepter que `import_tarif` lise XyloDensMap directement, sous Etalab 2.0. Le plan la croyait non redistribuable (§4.1).
- **Q4 (carbone de la table).** Refuser la colonne `carbone_t` de la grille, pour cause de compartiments mêlés (écart 1).
- **Q6 (référence IFN).** Retenir comme référence le `V` réfacté de l'IFN, en sachant qu'il est sous Vallet de 14 à 20 % (§4.4).

## 9. Trois points au sol (à vérifier par Pascal)

1. **Un perchis résineux, épicéa ou douglas, à tiges de 7,5 à 15 cm pour 10 à 17 m de haut.** Le H/D y dépasse 160 pour une part des tiges, qui sortent du domaine du tarif résineux (`nemeton_tarif_v5.py:300`). Il s'agit de relever, sur une placette, la part de la surface terrière hors domaine. C'est le cas le plus sensible pour Q5 : une fiche « volume partiel » pourrait y devenir la règle.
2. **Une placette IFN de hêtre ou de chêne.** On compare, sur les mêmes arbres, le `V` IFN au « > 7 cm, branches comprises » de NEMETON (attendu de 1,24 à 1,29 × `V`, `etage_b/LISEZMOI.md:15-16`) et à l'aérien total (1,37 à 1,50 × `V`). C'est l'écart de définition de Q3, vu en vrai.
3. **Un charme de plus de 35 cm, ou un chêne de 10 à 15 cm, dans un taillis-sous-futaie.** Ils sont hors du domaine des feuillus. De plus, le charme reçoit une densité « littérature » et non XyloDensMap (§4.2). C'est le point où domaine et densité divergent ensemble.

## 10. Question de contrôle

*Quelle décision cette donnée va-t-elle éclairer ?* Le choix, par Pascal, de la source unique de chaque grandeur de `post` : tarif, volume affiché, infradensité, expansion des branches, fraction de carbone et racines. Ce sont les questions Q1 à Q4 du plan, avant que les missions B (contrats) et D (code) ne commencent.

## 11. Ligne de journal proposée

`2026-11-25 | acquéreur | mission A (post) : docs/referentiels/volume-carbone.md et .csv (30 lignes, 5 grandeurs + V de l'IFN). Trois écarts de tarif-nemeton confirmés (nemeton_tarif_v5.py:296,300-302,307 ; tables_tarif_v5.csv:1,768). XyloDensMap sous Etalab 2.0 (3 sources), contrairement au plan. V IFN = 0,80-0,86 × Vallet bois fort. Aucune page d'article ouverte (HAL non résolu) : valeurs du GIEC et de Thomas et Martin non lues. Aucune valeur copiée.`

## 12. Liste de contrôle

**Aucune liste de contrôle n'était jointe à la consigne.** J'ai passé les trois points génériques de ma fiche.

1. **Sources et emplacements : coché avec réserves.** Chaque ligne du CSV porte un fichier et une ligne, ou une URL. Non coché :
   - aucune URL n'a été ouverte (deux hôtes non résolus, puis arrêt) ;
   - nemeton n'a pas été relu (clone absent) ;
   - le commit 0f51b96 n'a pas été revérifié dans `.git` ;
   - la méthodologie v2.23 n'a été lue qu'aux pages 1-3 et 34-35.
2. **Décomptes complets : coché avec réserves.** 30 lignes : 10 de volume, 1 de référence IFN, 6 d'infradensité, 5 d'expansion des branches, 3 de carbone, 5 de racines (seconde source de carbone et de racines : voir §2). Le compte des essences couvertes vient de `species.csv` (13 espar pour NEMETON, 7 pour Vallet d'après le résumé). Non coché : le domaine des feuillus a été lu sur la grille à H = 20 m seulement, et le rattachement espar des 156 espèces de XyloDensMap n'a pas été fait.
3. **Termes exacts : coché.** Les noms de colonnes et de compartiments sont ceux des fichiers (`V_sup7_m3`, `biomasse_aerienne_t`, « bois fort tige », « réfacté »). Les citations sont entre guillemets, avec leur ligne.
