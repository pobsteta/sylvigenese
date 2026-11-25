# Plan du module `post` : volume, biomasse et carbone (25/11/2026)

> Plan rendu par un `dev` (temps « prendre »), **à valider** par l'orchestrateur, et par Pascal pour
> les questions Q1 à Q6. Les choix techniques T1 à T10 sont ceux que le `dev` propose de trancher, avec
> leur raison. Pascal peut défaire chacun d'eux.
> Sources lues : CLAUDE.md ; BRIEF §1, §4, §6, §10, §11 ; spec §1, §2, §3, §9, §10, §11 ; ADR 0001 à 0004 ;
> `python/sylvigenese/post.py`, `import_tarif.py` et leurs tests ; Makefile ; contrats `params`,
> `sim.*`, `cell_sheet`, `run`, `catalog.yml` ; `docs/referentiels/entrees-externes.md` et `.csv`,
> `species.md` ; plan `m4a-suite-temps.md` ; fin du journal. **Lus en plus, sans rien copier** : le
> clone local de tarif-nemeton (`../tarif-nemeton`, commit 0f51b96, celui de la mission 008) et la
> documentation IFN de `../ref-externes/ifn_doc_2025`.

**En une phrase :** faire calculer par `post`, à partir des arbres de `sim/trees` et d'un tarif cité,
le volume, la biomasse et le carbone par cellule, année et essence, puis pour le massif, et les
faire afficher dans la fiche de cellule, pour que la vue dise enfin « combien de bois et de carbone »
au lieu de « volume et carbone non calculés » (décision de Pascal, Q2 du 25/11/2026).

## 1. Ce qui existe, ce qui manque

**Ce qui existe :**
- `post.py` : **squelette** de la mission 012. Il lit `config.yml`, le fait valider, rend 0 ou 2.
  Seuls tests : `python/tests/test_skeleton.py` (codes de sortie). Cible `make post`, placée entre
  `simulate` et `assets` dans `make all`.
- `import_tarif.py` lit tarif-nemeton (`external.tarif_nemeton_dir`), mais n'écrit que
  `params/allometry.parquet` (étage B, `hcb`, `cw`). **Il n'écrit pas `params/tarif.parquet`**, que
  la spec §2 lui attribue.
- Le contrat `import_tarif.tarif` (`params/tarif.parquet`) existe : format long `parameters.schema.json`,
  mais **aucun modèle de tarif n'y est décrit**.
- Le jeu fictif a un `params/tarif.parquet` **synthétique** : modèle `tarif_dbh_h`, V = a D^b H^c
  (`tools/fixtures/make_zone_fictive.py` l. 101). Personne ne le lit.
- Le contrat `post.summary` (`sim/summary.parquet`) existe en version 0.1. Sa clé est (cellule, année,
  essence), avec `volume_m3_ha`, `biomass_t_ha`, `carbon_t_ha` et `provisoire`. Le volume n'y est pas
  défini : bois fort, tige ou aérien total ?
- La fiche v2 porte `volume_m3_ha` et `carbon_t_ha`, toujours à `null`. Son contrat **exige** dans
  `notes` la phrase « volume et carbone non calculés ». La vue la dit (`viewer-web/src/temps.ts`
  l. 219).
- `sim/trees` donne, par arbre et par année : `species`, `d130` (cm), `h` (m) et `status`. Ce sont
  les seules entrées d'un tarif à deux entrées. Le jeu fictif sur 100 ans pèse 815 Mo, avec jusqu'à
  402 548 arbres vivants par année.

**Ce que contient tarif-nemeton** (lu à 0f51b96 ; à faire confirmer par l'`acquereur`) :
- **Sorties.** `resultats/tarif_v5/tables_tarif_v5.csv` est une **grille** (essence × D de 10 à 80 cm
  par pas de 5 × H de 10 à 40 m par pas de 2). Elle donne `V_m3`, `V_aerien_total_m3`,
  `V_sup7/20/30_m3`, `rho_kg_m3`, `biomasse_t`, `biomasse_aerienne_t` et `carbone_t`.
  `coefficients_feuillus_v5.csv` donne les coefficients a, b et c des feuillus, et les fractions de
  découpe. La forme feuillue est écrite dans le `README.md` l. 18.
- **Constantes restées dans le code, sans fichier de résultats :**
  - les profils de tige et l'expansion E(D) des résineux (`code/nemeton_tarif_v5.py` l. 77-90) ;
  - les infradensités (`code/tarif_v0_src/nemeton_tarif_v0.py` l. 32, `nemeton_tarif_v5.py` l. 94) ;
  - la fraction de carbone, 0,488 pour les feuillus et 0,508 pour les conifères, d'après Thomas et
    Martin 2012 (`nemeton_tarif_v0.py` l. 43).
- **Onze essences.** Domaine des feuillus borné par essence : chênes dès 15 cm, charme jusqu'à 35 cm,
  frêne jusqu'à 45. Domaine des résineux : 40 ≤ H/D ≤ 160, avec D en mètres (`nemeton_tarif_v5.py`
  l. 297).
- **Statut :** « coefficients non stabilisés, ne pas utiliser en production » (`README.md` l. 8).
  Dépôt sans licence.
- **Trois écarts de définition, relevés dans le code :**
  1. pour les résineux, `carbone_t` et `biomasse_t` de la table sont calculés **sur la tige seule**
     (`B = V × rho`, avec V = tige, l. 297-307). La biomasse aérienne est dans une autre colonne ;
  2. `V_sup7` vaut la tige au-delà de 7 cm pour les résineux, mais une fraction du volume **aérien
     total** pour les feuillus, branches comprises ;
  3. aucune racine, ni rien sur le sol ou le bois mort.
- **Référence de validation.** La colonne IFN `V` est le volume **bois fort tige** : tige jusqu'à
  une découpe de 7 cm, volume réfacté, tarifs IGN à trois entrées dès 2014, avec HDEC
  (`IGN_DB_doc_arbre.pdf` p. 9 ; `metadonnees.csv` l. 174). Le contrat d'entrée `ifn_arbre` la lit,
  mais `prepare.ifn_trees` ne la garde pas.

**Ce qui manque :**
1. le choix du tarif qui fait foi et du volume affiché ;
2. la façon de faire entrer le tarif dans `params/` sans reprendre de code ;
3. les sources de l'infradensité, de la fraction de carbone et des racines ;
4. la règle pour les arbres hors du domaine du tarif ;
5. les contrats : summary 0.2, table du massif, provenance, fiche v3 ;
6. le code : `import_tarif`, `post`, la fiche d'`assets`, la vue ;
7. les tests d'acceptation.

## 2. Les grandeurs à produire

**Par cellule, année et essence** (`sim/summary.parquet`). On somme les arbres **vivants** de la
cellule, puis on divise par la surface de la cellule, 0,0625 ha à 25 m.

| Grandeur | Unité | Calcul | Source à citer | Type de donnée | Dans le dépôt ? |
|---|---|---|---|---|---|
| Volume aérien total sur écorce | m³/ha | tarif à deux entrées (d130, h) | tarif NEMETON v5 (BRIEF §6), ou EMERGE (Deleuze et al. 2014), ou Vallet et al. 2006 | coefficients par essence, ou profil de tige, ou grille | grille et coefficients feuillus : oui, hors dépôt ; constantes des résineux : dans le code seulement |
| Volume bois fort (découpe 7 cm) | m³/ha | fraction de découpe, ou profil de tige | idem ; définition IFN de `V` pour la comparaison | coefficients de fraction (fmax, m, s) ou profil | feuillus : fractions en CSV, mais sur le volume **total** ; résineux : code |
| Biomasse aérienne sèche | t/ha | volume aérien × infradensité (× facteur arbre entier) | XyloDensMap (IGN, non redistribuée) corrigée par tarif-nemeton ; à comparer à GIEC 2006 vol. 4, ch. 4, et aux densités de nemeton (`infradensite_espar.csv`) | valeur par essence, éventuellement fonction de D | code de tarif-nemeton seulement |
| Facteur d'expansion des branches | sans unité | inutile si le tarif donne l'aérien total ; nécessaire si l'on part du bois fort tige | résineux : E(D) de tarif-nemeton ; sinon facteurs nationaux (méthode CITEPA, Loustau 2004) | fonction de D par essence, ou constante par groupe | code de tarif-nemeton seulement |
| Carbone aérien | tC/ha | biomasse × fraction de carbone | Thomas et Martin 2012 (*Forests* 3 : 332-352), comme tarif-nemeton ; à comparer à la valeur par défaut du GIEC 2006 | constante par groupe (feuillu, résineux de `species.csv`) | code seulement |
| Racines (si Q4 les retient) | tC/ha | rapport racines/aérien × carbone aérien | GIEC 2006, vol. 4, tableau 4.4 ; Mokany et al. 2006 ; méthode du CITEPA (OMINEA) | rapport par groupe et par classe de biomasse | **non** |
| Tiges calculées, tiges non calculées | tiges/ha | comptes | — | compte | — |

**À l'échelle du massif**, dans un nouveau fichier `sim/summary_zone.parquet`, par année, type de
végétation et essence :
- volume (m³), biomasse (t) et carbone (tC) totaux ;
- surface forestière (ha) et moyennes par hectare ;
- **volume et carbone des arbres morts dans l'année** : c'est un flux sortant du vivant, pas un stock
  de bois mort, car la décomposition n'est pas simulée ;
- part de la surface terrière non calculée.

On ne retient pas l'accroissement en volume. Il se lit par différence entre deux années, et l'ajouter
serait une colonne de plus à tenir.

**Rien n'est inventé.** Aucune valeur n'est écrite dans ce plan. Le jeu fictif reçoit des paramètres
**synthétiques** de la même forme que les vrais, marqués `provisoire: true`.

**Sources à faire chercher par l'`acquereur`** (mission A). Critères de choix communs :
1. les essences de `species.csv` couvertes ;
2. le domaine en D, **dès 7,5 cm**, et en H/D, face aux recrues de M3a (7,5 cm à 10-17 m) ;
3. le compartiment défini sans ambiguïté (tige, bois fort, aérien total) ;
4. les entrées disponibles : d130 et h seulement, ni HDEC ni âge ;
5. la licence et la réutilisation, référence et version citables ;
6. l'accord avec le `V` de l'IFN ;
7. l'origine française ou européenne des données de calage.

| Besoin | Sources à comparer |
|---|---|
| Tarif de volume | tarif NEMETON v5 (0f51b96, et son PDF de méthode v2.23) ; EMERGE (Deleuze et al. 2014, *Rendez-vous techniques* ONF 44) ; Vallet et al. 2006 (*For. Ecol. Manage.* 229 : 98-110), qui sert de prior à tarif-nemeton ; tarifs IGN de l'IFN (publiés ou non ? les tarifs à trois entrées demandent HDEC) ; tarifs à une entrée Algan et Schaeffer (`ifn_tarif_schaeffer_ser.csv` de nemeton), pour mémoire, car ils ignorent h ; `ifn_volume_equations.csv` de nemeton, que la mission 008 a signalé comme douteux |
| Infradensité | XyloDensMap (référence, licence) ; constantes de tarif-nemeton ; `infradensite_espar.csv` de nemeton (source ? Salix mal classés, `species.md` l. 49) ; GIEC 2006, tableau 4.14 ; base mondiale de densité du bois (Zanne et al. 2009) |
| Expansion des branches | E(D) de tarif-nemeton (résineux) ; facteurs nationaux utilisés pour l'inventaire des gaz à effet de serre (CITEPA, OMINEA ; projet CARBOFOR, Loustau 2004) ; Longuetaud et al., si une publication française de facteurs existe |
| Fraction de carbone | Thomas et Martin 2012 ; valeurs par défaut du GIEC 2006 ; valeur du CITEPA |
| Racines | GIEC 2006, tableau 4.4 ; Mokany et al. 2006 (*Global Change Biology* 12) ; valeurs du CITEPA |

L'`acquereur` doit en outre établir, fichier et ligne à l'appui, les trois écarts de définition du §1,
ainsi que le domaine de validité exact par essence.

## 3. Découpage proposé (5 missions, plus 1 conditionnelle ; numéros à donner par l'orchestrateur)

| # | Agent | Mission en une phrase (quoi, pourquoi) | Peut | Ne doit pas | Tests |
|---|---|---|---|---|---|
| A | `acquereur` | **Référentiel volume et carbone** : comparer les sources du §2 selon leurs critères, pour que Pascal tranche Q1 à Q4 sur pièces et que rien ne soit inventé. | `docs/referentiels/tarif-volume-carbone.md` et `.csv` (source, fichier et ligne, domaine, compartiment, licence) | copier une valeur ou un fichier de tarif-nemeton ou de XyloDensMap dans le dépôt ; choisir à la place de Pascal | contrôle du `relecteur` : chaque affirmation a son fichier et sa ligne, ou son URL ; trois cas terrain proposés (§ « Échantillon ») |
| B | `dev` | **Contrats de `post`**, posés avant le code pour que C et D visent la même cible. Contenu : modèles du tarif dans `params/tarif`, summary 0.2, `summary_zone`, `post.json`, fiche v3 (§4). Le jeu fictif reçoit des paramètres synthétiques de cette forme. | `contracts/` (schémas, `catalog.yml`, `README.md`, `tests/`) ; `tools/fixtures/make_zone_fictive.py` (paramètres de tarif seuls) ; projet d'ADR 0005 (représentation du tarif), à faire trancher par l'orchestrateur | toucher `python/sylvigenese/`, `viewer-web/`, `simulate/` ; affaiblir un contrat existant ; mettre une valeur écologique dans un schéma | un cas conforme et un cas fautif par règle nouvelle ; `make validate` vert ; fiche v2 toujours acceptée |
| C | `testeur` | **Tests d'acceptation de `post`** (`tests/post/`), écrits sans lire le code, pour que le calcul ne se juge pas lui-même (détail ci-dessous). | `tests/post/` ; ajout dans `tests/m4/` pour la fiche v3 ; section dans `tools/ci/run_tests.sh` | lire `python/sylvigenese/` ; sauter un test ; affaiblir une assertion de 045 | chaque règle a un test discriminant ; rouge attendu jusqu'à D |
| D | `dev` | **`import_tarif` écrit `params/tarif.parquet` et `post` écrit le summary**, pour que chaque arbre simulé reçoive son volume, sa biomasse et son carbone (BRIEF §6). `assets` remplit la fiche v3 avec ces valeurs. | `python/sylvigenese/{import_tarif,post}.py`, `python/sylvigenese/post_lib/` (nouveau), `assets_lib/cell_sheets.py` (lecture du summary seulement), `python/tests/test_{import_tarif,post}*.py`, cible `post` du Makefile | importer `simulate` ou `assets` depuis `post` ; reprendre du code de tarif-nemeton ; extrapoler hors du domaine sans la réponse à Q5 ; écrire un fichier par arbre | tests unitaires ; l'arbre de l'échantillon (est 700 012,5 ; nord 6 500 987,5, EPSG:2154) tombe dans la bonne cellule et son volume se recalcule à la main ; rejeu identique à l'octet près ; tests de C verts ; durée de `post` relevée sur 100 ans |
| E | `afficheur` | **La vue affiche le volume et le carbone**, pour que Pascal les lise dans la fiche, année par année (spec §1, point 4). | `viewer-web/` (src, test) | afficher un chiffre sans sa définition (bois fort ou aérien) ni « provisoire » ; afficher 0 quand la valeur est « non calculée » | `node --test` (mise en forme, cas null et partiel) ; tests de vue de C verts ; capture de la fiche |
| F *(si Q6 = oui)* | `dev` | **`prepare` garde le `V` de l'IFN** dans `ifn/trees.parquet`, pour comparer le tarif au volume bois fort de l'IFN sur des arbres mesurés. | `contracts/tables/prepare/ifn_trees.schema.json`, `R/prepare_ifn*.R`, ses tests, jeu fictif IFN | croiser une placette IFN avec un raster (garde IFN) | testthat ; `V` repris sans conversion, en m³ |

**Mission C (`testeur`), ce qu'elle couvre** (sur le tarif synthétique du jeu fictif, recalculé
indépendamment) :
- le volume d'un arbre, recalculé à la main depuis `params/tarif.parquet` ;
- la somme d'une cellule égale à la somme de ses arbres vivants divisée par 0,0625 ha ;
- les morts exclus du stock et comptés dans le flux de mortalité ;
- aucune ligne pour une cellule sans arbre vivant ;
- t0 présent ;
- l'arbre de coordonnées connues (EPSG:2154, x est puis y nord) dans la bonne `cell_id` ;
- le hors domaine compté et non extrapolé, sauf décision contraire en Q5 ;
- une essence sans tarif traitée selon Q5 ;
- `provisoire` propagé ;
- `summary_zone` égal à la somme des cellules ;
- `post.json` cohérent avec `run.json` ;
- les refus en code 2 : `run.json` absent ou différent, `params/tarif.parquet` absent ;
- la fiche v3 égale au summary ;
- la vue : la fiche montre la définition du volume.

**Ordre des vagues :**
1. Vague 0 : A.
2. Pascal répond à Q1, puis Q2, Q3, Q4, Q5 et Q6, une à la fois, sur les pièces de A.
3. Vague 1 : B, puis C en parallèle de D. C part des schémas de B, comme 045 est parti de 044.
4. Vague 2 : E, et F si elle est décidée.

## 4. Contrats à ajouter ou à modifier

- **`import_tarif.tarif` (`params/tarif.parquet`).** Le format long de `parameters.schema.json` est
  gardé (précédent de l'ADR 0004). La description du contrat nomme les modèles et leurs formes, sans
  aucune valeur :
  - feuillus, `ln V = ln(π/4·D²H) + a + b ln(D/30) + c ln(H/25)`, avec fractions de découpe ;
  - résineux, profil de tige et E(D) ;
  - infradensité ;
  - fraction de carbone ;
  - racines, selon Q4 ;
  - domaine par essence : `dbh_min`, `dbh_max`, `h_min`, `h_max`, `hd_min`, `hd_max`.

  C'est le projet d'ADR 0005, à trancher par l'orchestrateur. Le jeu fictif remplace `tarif_dbh_h` par
  ces mêmes modèles, avec des valeurs synthétiques.
- **`post.summary` 0.2** :
  - `volume_m3_ha` est redéfini selon Q3, avec son compartiment dans la description ;
  - colonnes ajoutées : `volume_total_m3_ha` (aérien total), `carbon_roots_t_ha` (si Q4), `stems_ha`
    (tiges calculées) et `stems_not_computed_ha` ;
  - même règle d'existence des lignes que `sim/cells` : une ligne par couple (cellule, essence)
    vivant ;
  - clé inchangée.
- **Nouveau `post.summary_zone`** (`sim/summary_zone.parquet`) :
  - clé (year, vegetation_type, species) ;
  - totaux en m³, t et tC, `forest_area_ha`, moyennes par hectare ;
  - `dead_volume_m3` et `dead_carbon_t`, flux de l'année ;
  - `basal_area_not_computed_share` ;
  - `provisoire`.
- **Nouveau `post.run`** (`sim/post.json`, JSON Schema) : `run_config_sha256`, copié de `run.json` ;
  source et commit de chaque modèle du tarif ; comptes des arbres hors domaine et sans tarif, par
  essence ; `provisional_share`.
- **`cell_sheet`, version 3**, écrite quand `sim/summary.parquet` existe. La v2 reste pour un `sim/`
  sans `post`.
  - Chaque année : `volume_m3_ha`, `volume_total_m3_ha`, `carbon_t_ha` (nombres), et
    `stems_not_computed_ha`.
  - Chaque entrée de composition : `volume_m3_ha` et `carbon_t_ha`.
  - `notes` exige la définition du volume et des compartiments du carbone, à la place de « volume et
    carbone non calculés ». Il exige « volume partiel » dès qu'une tige n'est pas calculée.
  - `null` n'est permis que pour « non calculé », avec sa raison.
- **`tiles_index`** : pas de changement. **`config`** : pas de changement, car
  `external.tarif_nemeton_dir` existe déjà.
- **Spec** : §1 ajoute `rapport_post.html` ; §2 donne à `post` les sorties `summary_zone` et
  `post.json`. Un écart à noter : le BRIEF §4 dit « summary par biome et année », la spec §2 dit
  « par cellule, année, essence ». Le plan garde la spec pour `summary` et sert le BRIEF par
  `summary_zone`, qui agrège par type de végétation.

## 5. Choix techniques (le `dev` propose de trancher, avec sa raison)

- **T1. Le calcul se fait par arbre, en mémoire, sans fichier par arbre.** Le BRIEF §6 demande un
  volume par arbre ; il est calculé, puis agrégé. Un `sim/trees` enrichi doublerait les 815 Mo, et
  aucun lecteur n'en a besoin avant M6.
- **T2. Le tarif est réécrit dans `post` par ses formules, avec citation** (précédent : l'étage B
  réécrit dans `prepare`, spec §4.3). Les coefficients sont lus par `import_tarif` dans des fichiers
  de résultats, jamais dans le code.
  - Si Q2 refuse cette voie, le repli est la grille `tables_tarif_v5.csv`, interpolée en (ln D, ln H)
    à l'intérieur de la grille seulement.
  - Raison : la grille ne couvre ni 7,5 à 10 cm, ni les chênes sous 15 cm.
- **T3. Le profil de tige des résineux est intégré numériquement**, une fois par essence, sur une
  grille fine (D, H), puis interpolé.
  - Le test borne l'écart à l'intégration directe.
  - Raison : environ 20 millions d'arbres-années sur 100 ans, et une intégration à 400 points par arbre
    ne tiendrait pas les 30 minutes.
- **T4. Toutes les années sont calculées** (le contrat le dit), partition par partition, vectorisées
  avec numpy et pyarrow. Aucune dépendance nouvelle : pas de pandas, comme pour `tests/m3`.
- **T5. Surface d'une cellule = `grid.resolution_m`² de `config.yml`**, soit 0,0625 ha. Elle n'est
  jamais écrite en dur.
- **T6. Stock = arbres `alive` seulement.** Les arbres `dead` de l'année alimentent le flux de
  mortalité de `summary_zone`. Il n'y a pas de stock de bois mort, car la décomposition n'est pas
  simulée.
- **T7. Une cellule sans arbre vivant n'a pas de ligne**, comme dans `sim/cells`. La fiche y écrit 0,
  qui est un fait arithmétique et non une valeur devinée. `null` veut dire « non calculé », jamais
  « zéro ».
- **T8. `post` refuse (code 2) dans quatre cas :**
  - `run.json` absent ;
  - `run.json` différent de `config.yml` ;
  - `params/tarif.parquet` absent ;
  - une unité douteuse (d130 en cm vérifié comme dans `import_tarif`).

  Il écrit dans `sim/.post_en_cours/`, fait valider, puis publie. Il n'appelle le validateur que sur
  ses sorties.
- **T9. Pas de colonne CO₂.** Le CO₂ vaut C × 44/12 ; une seule grandeur de carbone (tC) évite deux
  sources. La vue peut convertir si Pascal le demande.
- **T10. Les signalements vont dans `rapport_post.html`**, comme pour les autres modules : arbres hors
  domaine par essence et par année, essences sans tarif, part provisoire. Chaque valeur du summary
  porte `provisoire = vrai` dès qu'un paramètre provisoire a servi, ce qui est toujours le cas en v1.

## 6. Questions pour Pascal (une par une, dans cet ordre)

**Q1. Quel tarif fait foi ?**
- *Contexte.* Votre BRIEF (§6) dit « le tarif NEMETON ». Son dépôt dit pourtant « coefficients non
  stabilisés, ne pas utiliser en production ». Il n'a pas de licence et couvre 11 essences. EMERGE
  (Deleuze et al. 2014) est publié, mais il n'est pas le vôtre.
- *Proposition.* Le tarif NEMETON v5, figé à un commit cité, marqué provisoire dans la fiche. EMERGE ne
  sert que de point de comparaison dans le référentiel de A.
- *Si oui :* la suite du plan tel quel. Chaque nouvelle version de tarif-nemeton se reprend par
  `import_tarif`.
- *Si EMERGE :* A cherche ses coefficients et sa licence, et la mission D change de lecteur. Le BRIEF
  §6 est à corriger.

**Q2. Comment le tarif NEMETON entre-t-il dans sylvigenese ?**
- *Contexte.* Les coefficients des feuillus sont dans des fichiers de résultats. Ceux des résineux,
  les infradensités et la fraction de carbone ne sont que dans le code (`nemeton_tarif_v5.py`,
  `nemeton_tarif_v0.py`). `import_tarif` s'interdit de reprendre du code.
- *Proposition.* Vous ajoutez à tarif-nemeton (votre dépôt) un fichier de résultats, par exemple
  `resultats/tarif_v5/parametres_tarif_v5.csv`, qui porte toutes ces constantes. `post` réécrit les
  formules, en les citant (T2).
- *Si oui :* tous les arbres du domaine se calculent exactement, et la mise à jour se fait sans code.
- *Si vous préférez ne rien changer à tarif-nemeton :* on se replie sur la grille
  `tables_tarif_v5.csv`, interpolée. Les arbres sous 10 cm, et sous 15 cm pour les chênes, ne sont pas
  calculés.
- *Si vous autorisez la lecture des constantes dans le code :* il faut une lecture par motifs, comme
  pour `CR_min`. Elle est fragile au premier changement du script.

**Q3. Quel volume la fiche affiche-t-elle ?**
- *Contexte.* Le volume familier des gestionnaires, et celui de l'IFN (`V`), est le bois fort tige à la
  découpe de 7 cm. Le carbone, lui, se calcule sur l'aérien total. Or tarif-nemeton ne donne pas le
  bois fort tige des feuillus : son `V_sup7` y est une fraction de l'arbre entier, branches comprises.
- *Proposition.* Le summary porte les deux volumes : aérien total, et bois fort à 7 cm. La fiche
  affiche le **bois fort à 7 cm**, avec sa définition exacte par groupe, et l'aérien total en
  seconde ligne.
- *Si bois fort :* la comparaison avec l'IFN est possible, sous réserve de l'écart de définition
  des feuillus, qui sera écrit.
- *Si aérien total :* une seule définition pour toutes les essences, mais un chiffre plus grand que
  ce qu'attend un aménagiste.

**Q4. Quels compartiments du carbone ?**
- *Contexte.* tarif-nemeton donne l'aérien. Les racines demandent une source de plus, que A cherchera.
  Le sol et le bois mort n'ont aucun modèle dans sylvigenese.
- *Proposition.* Carbone aérien dans `carbon_t_ha`, et carbone des racines dans une colonne à part si
  A trouve un rapport cité. Le sol et le bois mort restent hors v1, et la fiche le dit.
- *Si aérien seul :* une source de moins, mais un carbone « arbre » sous-estimé de la part des
  racines. A chiffrera cette part d'après ses sources, et la fiche devra la dire.
- *Si sol compris :* il faut un modèle de sol, qui n'existe pas : ce serait une mission de recherche,
  hors v1.

**Q5. Que faire d'un arbre hors du domaine du tarif ?**
- *Contexte.* Le tarif commence à 10 cm (15 cm pour les chênes). Les résineux exigent un H/D entre 40
  et 160. Les recrues de M3a ont 7,5 cm pour 10 à 17 m, soit un H/D de 133 à 227. Une essence absente
  du tarif peut venir de nemeton. Avec 4 000 tiges/ha en fin de run, une grande part des tiges serait
  hors domaine.
- *Proposition.* Pas d'extrapolation. L'arbre n'est pas calculé ; il est compté par essence, et la
  fiche dit « volume partiel » avec la part de la surface terrière non calculée. Une essence sans
  tarif est traitée de la même façon, sans emprunt de tarif.
- *Si oui :* des chiffres sûrs, mais incomplets. Le biais est visible et chiffré.
- *Si vous préférez extrapoler la formule (Q2 = oui) :* des chiffres complets, marqués « extrapolé »,
  dont la justesse sous 10 cm n'est garantie par aucune source.
- *Si vous préférez emprunter le tarif de l'essence la plus proche :* il faut une table d'emprunt que
  vous validez, essence par essence.

**Q6. Quel critère d'acceptation pour `post` ?**
- *Contexte.* `post` n'a pas de ligne dans les jalons (BRIEF §11). Sur le jeu fictif, on ne peut juger
  que l'exactitude du calcul. Sur données réelles, le `V` de l'IFN est la seule mesure indépendante
  disponible.
- *Proposition.*
  - Critère a : recalcul exact sur le tarif synthétique (tests de C).
  - Critère b, avec vous : appliquer le tarif aux arbres IFN de la SER pilote (d130 et HTOT
    mesurés, aucun raster) et relever l'écart au `V` de l'IFN, par essence et par classe de
    diamètre, sans seuil fixé d'avance (mission F).
- *Si oui :* la mission F s'ajoute, en R, sans risque pour la garde IFN.
- *Si non :* le critère b est la comparaison à l'étage B de tarif-nemeton sur Fontainebleau
  (253 tCO₂/ha, `README.md`). Elle n'est pas indépendante, car c'est le même tarif.

## 7. Risques

- **Les chiffres seront invraisemblables avant M3b.** Avec une surface terrière de 350 m²/ha en fin
  de run, le volume sera énorme. La mention « non validée écologiquement » doit accompagner chaque
  volume. Sans elle, la vue dirait plus que ce que M3a prouve.
- **Sous-estimation structurelle.** Seuls les arbres détectés sont simulés : les dominés manquent
  (spec §4.6), alors que les 140 à 160 plus gros arbres par hectare ne portent que 80 à 92 % du volume
  de l'IFN (tarif-nemeton, `resultats/etage_b/LISEZMOI.md` l. 19-20). Le d130 de l'étage B est
  sous-estimé pour les feuillus en vol hors feuilles. tarif-nemeton corrige ces biais par strate ; pas
  `post`. Le rapport doit le dire.
- **Source instable et sans licence.** Le tarif v5 peut changer, et le commit est cité. Les paramètres
  dérivés vivent sous `data/`, hors dépôt. Le jeu fictif reste synthétique. Toute diffusion des
  valeurs est réservée à Pascal (spec §10).
- **XyloDensMap n'est pas redistribuable.** Les infradensités qui en dérivent n'entrent jamais dans le
  dépôt.
- **Définitions mêlées dans la source** (§1) : carbone de la table calculé sur la tige pour les
  résineux, `V_sup7` défini différemment selon le groupe. Reprendre la table sans les relever
  donnerait un carbone faux pour les résineux. Les tests de C doivent les rendre visibles.
- **Durée.** `post` sur 100 ans doit tenir dans le budget de 30 min du massif test. T3 et T4 le
  visent, et D relève la durée. La CI gagne une section `post` : elle se range dans un job existant
  (m4) ou un nouveau job parallèle (043).
- **Taille de la fiche.** La v3 ajoute environ six nombres par année et par essence, soit 10 à 20 %
  de plus que les 12,4 Mo actuels.
- **Écart entre le BRIEF et la spec** sur la clé du summary. Le plan le résout par `summary_zone`
  (§4). Si l'orchestrateur préfère corriger le BRIEF, c'est à dire à Pascal.

## Échantillon terrain que Pascal pourra vérifier (après D)

1. **Une cellule du jeu fictif à t0** (celle de l'arbre à est 700 012,5 ; nord 6 500 987,5,
   EPSG:2154) : refaire à la calculette le volume d'un de ses arbres depuis `params/tarif.parquet`, et
   la somme par hectare.
2. **Sur le massif réel, une placette IFN de hêtre et une de chêne** : comparer le volume bois fort
   calculé par `post` au `V` de l'IFN des mêmes arbres, à d130 et HTOT mesurés (Q6).
3. **Un peuplement d'épicéa connu de Pascal** : le carbone aérien par hectare de la fiche contre son
   ordre de grandeur de terrain, ou contre l'étage B de tarif-nemeton (319 à 357 tCO₂/ha cités pour
   des résineux, `README.md`), après conversion de tC en tCO₂.
