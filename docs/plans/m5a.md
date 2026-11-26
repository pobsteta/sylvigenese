# Plan de M5a : le niveau SER en cohortes, la régénération et la mesure à l'échelle (26/11/2026)

> Plan rendu par un `dev` (temps « prendre »), **à valider** par l'orchestrateur, et par Pascal pour
> les questions Q1 à Q5, à poser une par une. Les choix T1 à T10 sont ceux que le `dev` propose de
> trancher lui-même, avec leur raison. Pascal peut défaire chacun d'eux.
> Sources lues : CLAUDE.md ; BRIEF §0, §3, §4, §7, §8, §11 et §14 ; spec §2, §4 à §7, §9 et §11 ;
> ADR 0001, 0002 et 0004 ; `bench/SPEC.md` ; `bench/results/RESULTATS.md` ;
> `simulate/src` (`memoire.rs`, `concurrence.rs`, `recrutement.rs`, `config.rs`, `controles.rs`,
> `lib.rs`, `main.rs`, `sorties.rs`, `pas.rs`) ; plans de M3a et de la suite de M4a ;
> `docs/referentiels/entrees-externes.md` (§ régénération) et `ifn-g-tiges.md` ; fin du journal ;
> kanban ; `.github/workflows/ci.yml` ; `tools/ci/run_tests.sh`.

**En une phrase :** il s'agit de donner à `simulate` un niveau SER, où chaque cellule porte des
cohortes par essence, et une régénération par cohortes de semis dont le passage à 7,5 cm est calé
sur le modèle IFN. Il faut ensuite mesurer ce moteur à N = 1 000, 2 000 et 4 000, l'extrapoler, et
vérifier son estimation de mémoire contre la mémoire résidente. Le but : savoir, chiffres en main,
si 100 ans d'une SER entière tiennent sur le PC de Pascal, et recoloniser enfin les trouées.

## 1. Ce que M5a doit atteindre, ce qui existe

**Les critères de M5a :**
- **BRIEF §11 :** « une SER fictive simulée ; recrutement calé sur le modèle IFN ».
- **Spec §11** (les seuils chiffrés) :
  - une mesure à N = 1 000, 2 000 et 4 000 (grille de N × N cellules de 25 m), puis une
    extrapolation par les lois de `RESULTATS.md` §6 : t(N) ∝ N² ln(N + 16) et RSS(N) = b × N² ;
  - une estimation de mémoire du moteur à moins de 10 % de la mémoire résidente mesurée.
- **Je lis les deux comme cumulatifs.** La spec chiffre ce que le BRIEF annonce, elle ne le remplace
  pas.

**Ce que le journal renvoie à M5 :**
- la recolonisation des trouées par les cohortes (décision de Pascal du 25/11, M3a) ;
- les colonnes de semis de `sim/cells`, facultatives jusqu'à M5 (décision de Pascal, Q3) ;
- les cohortes de semis initiales (spec §4, point 7, « à reprendre en M5 ») ;
- la règle |Q| (T10, « à revoir en M5 ») ;
- l'estimation de mémoire comparée à la mémoire résidente (`memoire.rs`, `sorties.rs`) ;
- le recrutement par « cohortes calées sur ce modèle », avec `tree_id` = (cellule, année, rang)
  (spec §6) ;
- la comparaison à iLand, LANDIS-II et TreeMig « à M3 ou M5 » (ADR 0001, option G). Je la renvoie
  à M5b, car elle demande des sorties réelles.

**Ce qui existe :**
- `simulate` au niveau massif : un agent par arbre ; recrutement IFN direct ; pas de recrue en
  trouée, ce qui est compté et signalé ; aléa à compteur ; identité au bit près de 1 à 7 fils ;
  codes de sortie 0 à 4 ; estimation de mémoire avant chaque pas, contre 0,9 × `MemAvailable`.
- `simulate.level: ser` est **lu et recopié dans `run.json`, mais n'a aucun effet** : le moteur
  simule toujours arbre par arbre. Le niveau SER est donc entièrement à écrire.
- La règle |Q| est codée et testée (`controles::mettre_a_zero`), mais rien ne l'appelle encore :
  aucune FFT n'existe.
- Le banc (`bench/rust`) a éprouvé la dispersion par FFT réelle ou appariée (rustfft 6.4.1, rayon),
  la zone tampon de 16 cellules et l'identité entre fils. C'est une exploration jetable, à ne pas
  copier telle quelle : elle peut servir de **modèle**, jamais de **paramètres**.
- `nemeton` (`regen_engines.R`) **ne fournit aucune densité ni hauteur de semis** (référentiel
  `entrees-externes.md`, point 12).
- Les types de végétation (`biomes/*.yml`) n'ont **aucune strate de semis**.
- La spec cite la tolérance à l'ombre de **Niinemets et Valladares 2006** et les valeurs
  indicatrices de **Tichý et al. 2023**. Aucun noyau de dispersion, aucune fécondité ni aucune
  croissance de semis n'est sourcée dans le dépôt.

**Ce qui manque :**
1. Des cohortes de semis par cellule et par essence (densité, hauteur), aux deux niveaux.
2. La dispersion par FFT, depuis les semenciers voisins, avec sa zone tampon à bord absorbant
   (spec §7).
3. L'installation filtrée par la station, puis la croissance et la survie sous couvert.
4. Le passage à 7,5 cm, calé sur le modèle IFN.
5. Les adultes en cohortes au niveau SER.
6. Les sorties du niveau SER.
7. Une estimation de mémoire propre au niveau SER, et la mémoire résidente relevée.
8. Une SER fictive à toute taille N.
9. Le protocole de mesure.
10. Les tests d'acceptation.

## 2. Découpage proposé (6 missions, numéros à donner par l'orchestrateur)

| # | Agent | Mission en une phrase (quoi, pourquoi) | Peut | Ne doit pas | Tests |
|---|---|---|---|---|---|
| A | `acquereur` | **Référentiel de la régénération** : relever, essence par essence de `contracts/species.csv`, ce que la littérature publie, avec sa source, pour que le contrat des paramètres ne contienne que des grandeurs qui existent. Grandeurs visées : noyau ou distance de dispersion, âge ou diamètre de maturité, fécondité, tolérance à l'ombre (Niinemets et Valladares 2006), L d'Ellenberg (Tichý 2023), croissance en hauteur et survie des semis sous couvert. Sources : paramètres d'espèces de LANDIS-II et de TreeMig, RReShar (Capsis). | `docs/referentiels/regeneration.{md,csv}` | écrire une valeur sans page ni ligne ; combler un manque ; lire un dépôt privé | chaque ligne du CSV porte une source vérifiable ou `absent` ; recommandation finale |
| B | `dev` | **Contrats de M5a et projet d'ADR 0006 (niveau SER)**, pour fixer les formats avant le code, comme 033 pour M3a (§3). | `contracts/` (schémas, `catalog.yml`, `README.md`, `tests/`), `config.yml`, `docs/adr/0006-niveau-ser.md` (statut « proposée ») | toucher `simulate/`, `python/`, `R/` ; affaiblir un contrat existant ; mettre une valeur écologique dans un schéma | un cas conforme et un cas fautif par règle nouvelle ; `make validate` vert |
| C | `testeur` | **Tests d'acceptation de M5a** (`tests/m5/`), écrits sans lire le code du moteur, et **générateur de SER fictive** en aide de test, pour que M5a ne se juge pas lui-même. Le générateur produit, à toute taille N, des sorties de `prepare` synthétiques conformes aux contrats, avec `zone.yml` à `fictive: true` et deux codes de SER. Détail ci-dessous. | `tests/m5/` (tests, aide, générateur en ligne de commande) | lire `simulate/src` ; sauter un test ; écrire une valeur présentée comme écologique ; toucher `tests/m3/reference/` | chaque critère a un test discriminant ; rouge attendu jusqu'à D et E ; générateur rejoué à l'octet près à graine égale |
| D | `dev` (Rust) | **Régénération par cohortes de semis, aux deux niveaux**, pour recoloniser les trouées et caler le passage à la futaie sur l'IFN (BRIEF §7, selon Q1 à Q4). Contenu : dispersion par FFT avec zone tampon ; règle \|Q\| appliquée (T3) ; installation, croissance et survie ; passage calé ; colonnes de semis dans `sim/cells`. Sont comprises les notes de la vue : la mention « semis non simulés » ne doit plus être écrite quand `run.json` dit l'inverse. | `simulate/src` (nouveaux `semis.rs` et `dispersion.rs` ; `pas.rs`, `sorties.rs`, `controles.rs`, `alea.rs`, `config.rs`, `entrees.rs`), `simulate/tests/`, `simulate/Cargo.{toml,lock}` (`rustfft`, `realfft` figées), `python/sylvigenese/assets_lib/` (notes seules) | coder une valeur écologique ; changer `tests/m3/reference/nominal.json` ; casser l'identité entre fils ; importer `bench/` | tests unitaires, dont FFT contre convolution directe à 1e-9 et somme du noyau égale à 1 à 1e-12 ; **une source de coordonnées connues** (est 700 012,5 ; nord 6 500 987,5 ; EPSG:2154) **ensemence les cellules attendues**, avec un cas asymétrique qui détecte une transposition ; SHA-256 identiques de 1 à 7 fils ; `cargo test --locked` et `tests/m3` (mode `ifn_direct`) verts |
| E | `dev` (Rust) | **Niveau SER** : des cohortes d'adultes par classe de diamètre, avec accroissement, mortalité et recrutement IFN appliqués par classe (T1, T4). S'y ajoutent les sorties du niveau, l'estimation de mémoire propre au niveau (T7), la mémoire résidente écrite dans `run.json`, le script de mesure et le job `m5` de la CI (T6), pour que `simulate --level ser` existe et se mesure. | `simulate/src` (nouveau `ser.rs` ; `memoire.rs`, `sorties.rs`, `lib.rs`, `entrees.rs`), `simulate/tests/`, `bench/m5/` (script), `tools/ci/run_tests.sh`, `.github/workflows/ci.yml` (job `m5`) | écrire `sim/trees` au niveau SER ; interpoler ; borner une estimation de mémoire par une constante non mesurée ; mettre la mesure à N = 4 000 dans la CI | tests unitaires (conservation des tiges dans les transferts entre classes ; bal exact sur un cas à trois classes) ; estimation de mémoire à moins de 10 % de la mémoire résidente, à N = 1 000, dans la CI ; tests de C verts |
| F | `analyste` | **Mesure et extrapolation** : lancer `bench/m5` à N = 1 000, 2 000 et 4 000, avec T = 1 et T = 4, sur Y = 10 ans, extrapolés à 100 ans comme au banc §9. Il compare l'estimation de mémoire à la mémoire résidente, extrapole à C20 (48 millions de cellules, N équivalent ≈ 6 930) et au-delà, et dit le verdict face à la cible de 5 jours et 31 Go (selon Q5). | `bench/results/M5.md`, `bench/results/m5_*.csv`, `bench/results/LANCER_CHEZ_SOI.md` (section M5) | modifier le code ; présenter une extrapolation comme une mesure ; transposer un temps du conteneur au PC de Pascal sans le dire | chaque chiffre renvoie à une ligne de CSV ; écart estimation / mémoire résidente par taille ; rejouable par un seul script |

**Mission C (`testeur`), ce qu'elle couvre :**
- **Calage du passage sur l'IFN**, selon Q1 :
  - au niveau SER, là où le stock de semis suffit, le flux de recrues d'une cellule et d'une
    essence égale exp(η) × aire, à 1e-9 près ;
  - au niveau massif, l'espérance de l'arrondi aléatoire égale le même flux ;
  - les couples (cellule, année) où le stock limite le flux sont comptés.
- **Trouées** : une cellule à H_dom nulle, proche de semenciers, reçoit des semis et finit par
  recruter ; une trouée hors de portée du noyau reste vide, et c'est signalé.
- **Dispersion** :
  - le noyau est normalisé ;
  - la FFT est comparée à une convolution directe, sur un oracle écrit d'après le contrat ;
  - le bord est absorbant ;
  - la zone tampon est source seulement : elle produit des graines, mais aucun semis n'y est
    simulé.
- **Règle |Q|** : des valeurs sous le seuil, positives et négatives, sont mises à zéro et comptées ;
  une valeur négative au-delà du seuil arrête le moteur (code 3).
- **Conservation** : tiges(t+1) = tiges(t) − morts + recrues, par cellule et par essence, au niveau
  SER.
- **Identité** de 1 à N fils, au niveau SER.
- **Codes de sortie** : 2 (bloc `ser` absent, paramètre de régénération manquant), 3, et 4 (par
  `--memoire-disponible`).
- **Mémoire** : l'estimation est à moins de 10 % de la mémoire résidente à N = 1 000 (lue par
  `/usr/bin/time -v`, et non par le moteur seul).
- **Non-régression de M3a**, en mode `ifn_direct` : `nominal.json` est inchangé.
- **SER fictive** sur 100 ans (environ 400 × 400 cellules) : l'exécution va à son terme. G et
  tiges/ha sont relevés face aux quantiles IFN de `ifn-g-tiges.csv`, sans être jugés.
- **Refus** : `assets` et `post` refusent un `sim/` de niveau SER par un code 2 au message clair,
  tant qu'ils ne le lisent pas.

**Ordre des vagues :**
1. Pascal répond à Q1, puis à Q2, Q3, Q4 et Q5, une question à la fois. Q1 à Q4 changent le contrat
   et la mission D ; Q5 change la clôture de M5a.
2. Vague 1 : A, la mission courte dont B a besoin.
3. Vague 2 : B. L'orchestrateur tranche l'ADR 0006 par délégation.
4. Vague 3 : C et D. C part des schémas de B, comme 039 était partie de 033.
5. Vague 4 : E. Il dépend de l'interface des semis de D. D et E écrivent dans les mêmes fichiers
   (`sorties.rs`, `pas.rs`) : on ne les lance pas en même temps.
6. Vague 5 : F, puis la relecture.

## 3. Contrats à ajouter ou à modifier (mission B)

- **`config` :**
  - `simulate.regeneration` : `ifn_direct` ou `cohorts`, **exigé**, sans valeur par défaut (T5) ;
  - un bloc `simulate.ser`, exigé si `level: ser` :
    - `diameter_class_width_cm` ;
    - `diameter_classes` ;
    - `write_step` : le pas des années écrites ;
  - `config.yml` du dépôt : `regeneration: cohorts` (selon Q4).
- **Nouveau `params/regeneration.parquet`**, au format long de `dynamics_params` :
  - colonnes `species`, `species_group`, `term`, `value`, `unit`, `provisoire`, `source` ;
  - termes fixés par A et par Q1 à Q3 : noyau, maturité, fécondité, installation, croissance,
    survie, hauteur de passage ;
  - **aucune valeur dans le schéma**. Sur le jeu fictif, les valeurs sont synthétiques et
    `provisoire: true`.
- **Nouveau `cohorts_init.parquet`** : l'état initial du niveau SER, avec `cell_id`, `species`,
  `d_class`, `stems_ha` et `source`. Le générateur de C l'écrit sur la SER fictive. Sur une SER
  réelle, `prepare` l'écrira (M5b, §6). L'état initial des semis suit Q2.
- **`sim.cells` :**
  - `seedlings_ha` et `seedling_h_mean` restent facultatifs dans le schéma, mais la description dit
    qu'ils sont **présents dès que `run.json` dit `regeneration: cohorts`** ;
  - le test vérifie cette cohérence entre les deux fichiers.
- **Nouveau `sim.cohorts`** (niveau SER, années de `write_step`) : `cell_id`, `species`, `d_class`,
  `stems_ha`. C'est ce qui permettra plus tard de tirer les arbres affichés (BRIEF §3).
- **`run` :**
  - `regeneration` ;
  - `memory_estimate_max_bytes`, la plus grande estimation faite avant les pas ;
  - `memory_peak_rss_bytes`, lu dans `VmHWM` de `/proc/self/status`, et `null` hors de Linux,
    jamais deviné ;
  - de nouveaux comptes : `zeroed_values` (enfin utilisé), `seedling_stock_limited`,
    `gaps_recolonised`, `buffer_cells`.
- **`simulate.flags`** : la sorte `semis_non_simules` n'est plus écrite en mode `cohorts`. Une
  sorte `trouee_hors_de_portee` s'y ajoute.
- **Biomes** : inchangés si Q2 vaut (a) ou (c). Si Q2 vaut (b), une strate `semis` facultative
  s'ajoute.
- **ADR 0006 (proposée par B, tranchée par l'orchestrateur)** : la représentation du niveau SER
  (T1), la dispersion (T2), les sorties (T8) et la mémoire (T7). Le BRIEF §3 pose les cohortes
  sans leur forme, et aucune ADR n'en décide. Je ne tranche donc pas seul : je propose.

## 4. Choix techniques (le `dev` propose de trancher, avec sa raison)

- **T1. Adultes du niveau SER en classes de diamètre fixes, f32, sur les seules cellules
  forestières.**
  - Options pesées :
    - (a) une cohorte moyenne par essence : 2 valeurs ;
    - (b) des classes fixes, par exemple 15 classes de 5 cm à partir de 7,48 cm, la dernière
      ouverte ;
    - (c) une liste de cohortes de longueur variable.
  - Raison :
    - le modèle d'accroissement IFN prend `bal`, la surface terrière des plus gros. En (a), bal
      n'existe pas et il faudrait l'inventer ;
    - (b) le donne exactement à la résolution d'une classe ;
    - (c) rend la mémoire imprévisible, alors que le critère des 10 % la veut prévisible.
  - Transfert entre classes : une fraction Δd / largeur passe à la classe suivante (matrice
    d'Usher). Δd suit le modèle IFN au centre de la classe.
  - Largeur et nombre de classes : `config.yml` (réglage numérique, non écologique). L'erreur de
    discrétisation est dite au rapport.
  - Mémoire : 4 × S × K octets par cellule forestière. À C20, avec 48 millions de cellules
    supposées toutes forestières, S = 8 essences et K = 15 classes : environ 23 Go, au bord des
    28 Go utilisables. C'est le risque n° 1 (§6).
- **T2. Dispersion par FFT réelle**, essence par essence, sur toute la grille, zone tampon comprise.
  - Crates : `realfft` et `rustfft`, figées par `=` et sous licence MIT/Apache, vérifiées par le
    test de licences.
  - La zone tampon a la largeur du noyau tronqué ; elle est source seulement et son bord est
    absorbant (spec §7).
  - Option écartée : la convolution directe. Pour un noyau de 33 × 33 cellules, elle coûte environ
    1 100 opérations par cellule et par essence, soit environ 4 jours pour C20 à S = 8 : elle
    mangerait toute la cible.
  - Le noyau est une loi par essence de `params/regeneration`, avec sa source.
- **T3. Règle |Q|, revue comme demandé par T10** :
  - on garde la mise à zéro **symétrique** de |Q| < 1e-9 × max|Q| ;
  - max|Q| est pris par (essence, année), sur toute la grille ;
  - une valeur négative au-delà du seuil donne le code 3 ;
  - chaque mise à zéro est comptée.
  - Raison :
    - le bruit d'une FFT en f64 est d'environ 1e-13 en relatif, très sous le seuil ;
    - ne mettre à zéro que les négatives garderait le bruit positif et créerait un biais de signe ;
    - les vraies valeurs positives sous 1e-9 × max représentent moins d'une graine par hectare
      dans tous les cas plausibles.
- **T4. Au niveau SER, les cohortes portent des espérances, sans tirage.**
  - L'accroissement, la mortalité (N × p) et le passage sont calculés en espérance.
  - Au niveau massif, on garde la mort tirée et l'arrondi aléatoire des recrues (décision de
    Pascal, Q4 du 25/11).
  - Raison : une classe est une densité. Un tirage par classe ajouterait du bruit sans
    information. C'est aussi ce qui rend exact le test du calage.
- **T5. Le mode `regeneration` est exigé** (`ifn_direct` ou `cohorts`).
  - Raison : garder la référence de M3a (`nominal.json`) jugeable telle quelle, sans la regeler ;
    une nouvelle référence `nominal_cohorts.json` juge le mode `cohorts`.
  - Prix : deux chemins de recrutement dans le moteur, testés tous les deux.
- **T6. Protocole de mesure** :
  - `bench/m5/mesurer.sh` appelle le générateur de C, puis `simulate --level ser` ;
  - Y = 10 ans, extrapolés à 100 ans par init + 100 × pas moyen, comme au banc §9 ;
  - T = 1 et T = 4 ;
  - mémoire résidente relevée par `/usr/bin/time -v` (« Maximum resident set size ») et par
    `memory_peak_rss_bytes` ;
  - les temps de calcul et d'écriture sont séparés ;
  - lois de `RESULTATS.md` §6, ajustées sur les trois points ;
  - la loi en N² ln N est confrontée aux rapports observés par doublement. Si elle les
    sous-estime, la version pessimiste du banc s'applique.
- **T7. Estimation de mémoire du niveau SER**, par une formule fermée :
  - classes, semis et couches f64 ;
  - tampons de FFT (une essence à la fois, plus un tampon complexe par fil) ;
  - tampon d'écriture d'une année écrite ;
  - plus une **part fixe du programme**, mesurée une fois sur une exécution à vide et écrite dans
    le code avec sa mesure. C'est une constante technique, pas écologique, et elle est dite.
  - Critère : |estimation − mémoire résidente| / mémoire résidente < 0,10 à N = 1 000, 2 000 et
    4 000. On compare la plus grande estimation à la mémoire résidente maximale.
  - La même comparaison est **relevée** sur le massif fictif, sans être jugée : son état grandit
    avec les recrues.
- **T8. Sorties du niveau SER** :
  - pas de `sim/trees` : il n'y a pas d'individus (BRIEF §3) ;
  - `sim/cells` et `sim/cohorts` sont écrits pour t0, puis tous les `write_step` ans, et pour la
    dernière année.
  - Raison : à N = 4 000, une année de `sim/cells` fait environ 50 millions de lignes, et 100
    années ne tiendraient ni sur le disque d'un portable ni dans la règle des 30 minutes.
  - Le validateur ne lit que les partitions écrites.
- **T9. SER fictive produite par un générateur, pas par la chaîne R.**
  - À N = 4 000, un MNH à 50 cm représenterait 1,6 milliard de pixels ;
  - le générateur écrit directement les sorties de `prepare` (grille, `h0`, gradients,
    `site_potential`, `ser.tif` avec deux SER, `cohorts_init`) et des paramètres synthétiques ;
  - il est déterministe à graine fixée, et ce qu'il écrit est hors dépôt (`data/ser_fictive_<N>/`).
  - Le massif fictif reste jugé par la chaîne complète (`tests/m3`).
- **T10. CI** :
  - un job `m5`, sous 15 min, qui lance :
    - la SER fictive moyenne sur 100 ans ;
    - N = 1 000 sur 5 ans, à T = 1 et T = 4 (identité et critère des 10 %) ;
    - le massif fictif en mode `cohorts` ;
  - N = 2 000 et N = 4 000 restent **hors CI**. Ils relèvent de la mission F, rejouable et
    versionnée.
  - Raison :
    - un relevé de temps sur un exécuteur partagé est bruité ;
    - à N = 4 000, il faut environ 6 Go et plusieurs minutes par essai ;
    - le plus long job dure déjà environ 12 min.

## 5. Questions pour Pascal (une par une, dans cet ordre)

**Q1. Que veut dire, en simulation, « passage à la futaie calé sur le recrutement observé par
l'IFN » (BRIEF §7.4 et §11) ?**
- *Contexte.*
  - Le modèle IFN donne un flux de recrues par hectare et par an, déjà utilisé par M3a.
  - La chaîne du BRIEF §7 compte quatre étapes : arrivée des graines, installation, croissance et
    survie, passage. Elle demande des paramètres dont presque aucun n'est sourcé aujourd'hui (la
    mission A dira lesquels existent).
- *Options :*
  - **(a) Flux IFN, borné par le stock.** Sous couvert, le flux de passage est celui du modèle IFN,
    tant que la cohorte de l'essence a assez de semis à la hauteur de passage. Sinon, le stock
    borne le flux, et c'est compté. En trouée, où le modèle IFN ne s'applique pas, le stock passe
    à mesure qu'il atteint la hauteur de passage.
  - **(b) Chaîne complète, puis calage.** La chaîne produit son propre flux, ramené au flux IFN
    par un facteur de calage par essence, ajusté hors du moteur.
  - **(c) IFN direct partout.** Les semis ne sont simulés que pour les trouées et pour l'affichage.
- *Proposition :* (a).
  - Le calage est exact par construction, là où l'IFN a observé quelque chose.
  - Les paramètres provisoires n'agissent que sur ce que l'IFN ne voit pas : les trouées et le
    manque de semis.
- *Si (a) :* le test du calage est exact au niveau SER. La recolonisation des trouées dépend des
  paramètres de semis, provisoires.
- *Si (b) :* c'est la lettre de RReShar. Mais le facteur de calage absorbe les erreurs des quatre
  étapes, et il faut une mission de plus pour l'ajuster.
- *Si (c) :* c'est le plus simple. Mais sous couvert, les semis ne servent à rien, et l'IFN peut
  « recruter » sans aucun semis.

**Q2. D'où vient l'état initial des semis ?**
- *Contexte.*
  - La spec §4.7 dit « tirées du type de végétation ». Or les types n'ont aucune strate de semis,
    et nemeton n'en fournit pas.
  - Partir de zéro priverait toute cellule de recrues pendant 10 à 20 ans, le temps que les semis
    atteignent 7,5 cm : une rupture nette avec M3a.
- *Options :*
  - (a) zéro partout, signalé ;
  - (b) une strate `semis` dans chaque type de végétation, provisoire et à sourcer type par type ;
  - (c) un stock « en régime », déduit des modèles eux-mêmes : flux IFN à t0 × temps de passage
    donné par la croissance des semis. Il est marqué provisoire et dit au rapport.
- *Proposition :* (c). Aucune valeur nouvelle n'est inventée, et il n'y a pas de rupture à t0.
- *Si (a) :* il y aura un creux de recrutement les premières années, visible dans la vue.
- *Si (b) :* une valeur par type et par essence, sans source aujourd'hui, et un contrat de biome
  modifié.

**Q3. Quels facteurs de survie des semis entrent dans M5a ?**
- *Contexte.* Le BRIEF §7.3 demande lumière × tolérance à l'ombre × concurrence du sous-bois
  (fougère aigle, molinie, ronce) × gibier. Gibier et fructification sont des scénarios (faible,
  moyen, fort), pas des constantes. Seules la tolérance à l'ombre (Niinemets et Valladares 2006) et
  L d'Ellenberg (Tichý 2023) ont une source dans la spec.
- *Proposition :*
  - en M5a : la lumière sous couvert et la tolérance à l'ombre ;
  - le sous-bois, le gibier et la fructification sont reportés après M5a ;
  - `run.json`, le rapport et la fiche disent « gibier, sous-bois et fructification non simulés ».
- *Si oui :* moins de paramètres sans source. Mais la régénération sera surestimée là où le gibier
  ou la ronce comptent, et la fiche le dira.
- *Si non :* les trois facteurs deviennent des clés de scénario exigées, avec des valeurs
  provisoires à sourcer par A, et il faut une mission de plus.

**Q4. La régénération par cohortes remplace-t-elle aussi le recrutement IFN direct au niveau
massif ?**
- *Contexte.* Votre décision du 25/11 renvoie la recolonisation des trouées du massif « en M5 par
  les cohortes ». Le faire change la trajectoire du massif fictif, figée comme référence technique.
- *Proposition :* oui.
  - Un seul module de semis sert les deux niveaux.
  - Le mode `ifn_direct` est gardé dans `config.yml` pour que `nominal.json` reste jugé tel quel.
  - Le mode `cohorts` reçoit sa propre référence, elle aussi « technique, non validée
    écologiquement ».
- *Si oui :* les trouées du massif se referment, et la vue le montrera.
- *Si non :* les cohortes ne servent que le niveau SER. Le massif garde ses trouées sans recrue
  jusqu'à une décision ultérieure.

**Q5. Si l'extrapolation dit que C20 ne tient pas en 5 jours et 31 Go, M5a est-il rempli ?**
- *Contexte.*
  - Le critère a demande une mesure et une extrapolation, pas un verdict.
  - Avec 8 essences et 15 classes, la mémoire de C20 frôle 28 Go (T1). Le temps, lui, devrait
    rester loin de la cible : le banc Rust donne une marge d'environ 400 à N = 8 000
    (1 065 s contre 432 000 s). Cette marge est à diviser par le surcoût de notre moteur, qui
    n'est pas encore mesuré.
- *Proposition :*
  - M5a est rempli sur la mesure, l'extrapolation et l'estimation de mémoire à moins de 10 % ;
  - le verdict face à la cible est écrit dans `M5.md` ;
  - **un verdict négatif vous est porté comme une mauvaise nouvelle avant M5b**, avec ses leviers
    chiffrés : moins de classes, essences regroupées, cellules forestières seules, découpage de la
    SER en blocs.
- *Si oui :* M5a se clôt par délégation. La cible se tranche avec vous.
- *Si non :* M5a reste ouvert jusqu'à ce qu'un levier tienne la cible. L'un d'eux (le nombre
  d'essences) touche au sens de vos résultats.

## 6. Risques

- **Mémoire à l'échelle de C20 (risque n° 1).** Une SER à 100 % forestière demande 4 × S × K octets
  par cellule, plus les tampons. Le taux de boisement de C20 n'est pas connu du dépôt : il est à
  relever par l'`acquereur` (`surfaces-ser.csv`). On ne peut le tenir que par S, K et le stockage
  des seules cellules forestières (Q5).
- **Durée de la CI.** Il y a aujourd'hui 10 jobs, et le plus long dure environ 12 min.
  - Une mesure à N = 4 000 durerait plusieurs minutes par essai, et il faut 6 essais (3 tailles,
    T = 1 et T = 4). Elle demanderait environ 6 Go, alors que l'exécuteur en a 16, et sa mémoire
    résidente y serait bruitée par le partage.
  - D'où T10 : seul N = 1 000 tourne en CI, dans un job `m5` à part, avec un délai de 20 min.
  - `tests/m3` passe en plus une référence `cohorts`, soit environ 2 min de plus dans le job `m3`.
    Si ce job approche 15 min, la nouvelle référence va dans `m5`.
  - Relever un délai de la CI se dit au journal, jamais en silence.
- **Ne rien inventer d'écologique.**
  - Sur le jeu fictif, tous les paramètres de régénération sont synthétiques et `provisoire: true`.
  - Sur une zone réelle, une essence sans paramètre sourcé donne le **code 2**, jamais une valeur
    d'emprunt, même « de la même famille », sans décision de Pascal.
  - Deux pièges :
    - la largeur des classes (T1) est un réglage numérique, mais elle change les résultats : on
      la dit ;
    - le stock « en régime » de Q2 (c) est déduit des modèles, et le rapport doit le dire déduit,
      non observé.
- **Le calage peut masquer.** Avec Q1 (a), le flux sous couvert égale l'IFN par construction. Un
  test vert ne prouve donc rien sur les semis. La vraisemblance des trouées refermées se jugera
  en M5b, face aux quantiles IFN et à MARGOT.
- **Trajectoire du massif.** Le mode `cohorts` change G et tiges/ha du massif fictif, déjà trop
  denses (91 → 352 m²/ha). La vue le montrera. La mention « non validée écologiquement » reste
  obligatoire.
- **Identité entre fils avec la FFT.** Elle est garantie si chaque transformée de ligne ou de
  colonne est faite par un seul fil, avec le même plan. C'est à prouver par SHA-256, et pas
  seulement à affirmer.
- **Transposition des axes.** La ligne 0 est au nord et x pointe vers l'est. Une FFT qui
  transpose la grille resterait juste sur un cas symétrique. D'où le cas asymétrique du test de
  coordonnées de D.
- **Hors de ce plan, et à inscrire au kanban :**
  - `prepare` doit écrire `cohorts_init` sur une SER réelle, à partir des polygones nemeton et des
    types de végétation, hors polygone, avec le diamètre tiré de h0 par l'allométrie citée
    (M5b) ;
  - `post` et `assets` ne lisent pas encore le niveau SER (ils le refusent, code 2) ;
  - la comparaison à iLand, LANDIS-II, TreeMig et MARGOT (M5b) ;
  - le recrutement dans l'intervalle de confiance IFN (critère b).
