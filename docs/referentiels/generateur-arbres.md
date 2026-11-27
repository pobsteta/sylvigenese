# Générateur d'arbres de tarif-nemeton : référentiel pour M6a (mission 067)

## En-tête

- **Source :** dépôt local `/home/user/tarif-nemeton` (main, lecture seule) : `code/synth_arbres.py`, `synth_essences.py`, `synth_population.py`, `synth_calage.py`, `architecture_modeles.py`, `resultats/synth_arbres/` (`bornes_dimensions.csv`, `population.csv`, `LISEZMOI.md`), `donnees/modeles_architecturaux_sources.csv`. Le numéro de commit n'est pas vérifié (aucune commande git ; le plan cite 4ee122c).
- **Date de consultation :** 26/11/2026.
- **Propriétaire :** Pascal.
- **Mission redite :** relever ce que le générateur donne et exige (sortie, dépendances, essences et codes espar, repère, auteurs), les licences des jeux qui ont calé ses dimensions, l'état des attributions architecturales, et ce que `synth_calage.py` fournit pour `hbh`, `Rh`, `b_cible`.
- **Décision éclairée :** M6a, mission E (export des exemplaires) et missions B et D : quelles dimensions et quels paramètres l'export doit lire, quelles essences ont un modèle propre, ce qui peut être publié.
- **Dépôt privé sans licence :** aucun code ni aucune table n'est recopié ici. Les valeurs de `bornes_dimensions.csv` ne sont pas reprises ; seuls les effectifs et quelques ordres de grandeur utiles à la décision le sont. Détail ligne à ligne : `generateur-arbres.csv` (colonnes `source_fichier_ligne` et `statut`).
- **Écarts entre sources relevés :**
  1. Les jeux de calage : le plan cite « QSM BioDiv, Wytham, Demol » pour `bornes_dimensions.csv`. `synth_calage.py:92,96-97` ne lit que des fichiers tirés de BioDiv. Wytham et Demol n'ont servi qu'à l'**attribution architecturale** (`architecture_modeles.py:6-7`). Sa licence à lire pour `bornes_dimensions.csv` est donc celle de BioDiv.
  2. Effectifs : 4 920 arbres (somme des 11 essences), 4 951 (texte du `LISEZMOI.md:32-33`), 4 952 (`nemeton_hcb_biodiv.py:4` et `references.bib:113`). Écart d'un arbre non expliqué.
  3. Rayon de brindille : `synth_essences.py:59` pose le hêtre à 1,14 mm (base rTwig du dépôt GitHub) ; BioDiv a corrigé ses QSM avec rTwig 1.4.0 (hêtre 1,21 mm) (`NEMETON_protocole_campagne_B_v3.md:18`). Les arbres du générateur et les QSM du calage n'ont donc pas la même base de brindilles.
  4. Licence de BioDiv : « CC-BY 4.0 » écrit dans `references.bib:115` (le dépôt de tarif-nemeton), jamais lu à la source.

## 1. Le générateur

### 1.1 Sortie, entrée, repère

- **Sortie :** des segments (troncs de cône) `P0, P1, R0, R1, niveau, axe, racine` (`synth_arbres.py:444`). Le seul export est un CSV de 11 colonnes (`x0..z1, r0_m, r1_m, niveau, axe, racine_niveau1`, `synth_arbres.py:493-501`). **Aucun feuillage, aucun maillage, aucun `.glb`** (absent). Rayons en mètres.
- **Repère : z-up** (`UP = (0, 0, 1)`, `synth_arbres.py:38`).
- **Entrée d'un arbre :** `essence, D_cm, H, hbh, Rh, graine` plus, selon le cas, `b_cible` (`synth_population.py:43-52`). Ligne de commande en `synth_arbres.py:506-514`, défauts `hbh = 0,45 H` et `Rh = 0,12 D + 0,8` (`:517-518`). `population.csv` porte ces colonnes (ligne 1).
- **Reproductibilité :** promise par l'auteur (`synth_arbres.py:28-29`), non éprouvée ici.
- **Piège confirmé (E doit échouer, pas passer) :** `forme_tige()` lit `resultats/synth_arbres/bornes_dimensions.csv` par un chemin **relatif au dossier courant** et, s'il est absent, rend `(1,0 ; 0,0)` sans message (`synth_essences.py:267-273`). L'effet touche les résineux.
- **Garde-fou silencieux :** au-delà de 350 000 axes, un niveau est éclairci (`synth_arbres.py:40`) ; le résumé porte `eclairci`. E doit le relever.

### 1.2 Dépendances

- Un arbre : **numpy seul** (`synth_arbres.py:35-36`) ; pandas seulement à l'export CSV (`:495`) et, à la demande, pour lire les bornes (`synth_essences.py:269`).
- Calage : pandas, scipy.optimize (`synth_calage.py:28-32`). Population : pandas, scipy.interpolate, multiprocessing (`synth_population.py:25-32`).
- Python 3.12 annoncé (`README.md:61`). Aucun fichier `requirements`, `pyproject` ni `environment` : **absent**.

### 1.3 Auteurs

- Les en-têtes des cinq fichiers ne nomment **aucun auteur** ni licence : **absent**. Seule mention : « choix de Pascal le 20/11/2026 » (`synth_essences.py:19`).
- Titulaire déclaré : Pascal Obstétar, dépôt privé, « licence à définir avant toute ouverture » (`README.md:90`).
- Auteurs des commits : **non lus** (aucune commande git). Question possible : faut-il les relever avant l'ouverture du dépôt ?

### 1.4 Essences et codes espar

11 essences (`synth_essences.py:253-255`). Treize codes de `contracts/species.csv` les atteignent ; **tous les autres codes espar n'ont pas de modèle** (réponse Q3 : générique).

| Essence du générateur | Codes espar (`species.csv`, ligne) | Modèle architectural | Calage (arbres) |
|---|---|---|---|
| Fagus_sylvatica | 09 (l.10) | Troll, sourcé | 2 987 |
| Quercus_spec | 02 (l.2) et 03 (l.3), **alias** | Rauh, sourcé | 178 |
| Fraxinus_excelsior | 17C (l.22) | Rauh, sourcé | 59 |
| Acer_pseudoplatanus | 15S (l.20) | Rauh, nuance | 65 |
| Betula_spec | 12P (l.13) et 12V (l.14), **alias** | Rauh, **à confirmer** | 23 (forme du hêtre décalée) |
| Carpinus_betulus | 11 (l.12) | Troll, peu sourcé | 66 |
| Picea_abies | 62 (l.157) | Massart, **non établi** | 1 004 |
| Abies_alba | 61 (l.156) | Massart, sourcé | 5 (forme de l'épicéa décalée) |
| Pseudotsuga_menziesii | 64 (l.159) | Massart, **sans source** | 11 (idem) |
| Larix_decidua | 63 (l.158) | Massart, **contredit** | 10 (idem) |
| Pinus_sylvestris | 52 (l.144) | Rauh, QSM ambigus | 512 |

Lignes du générateur : `synth_essences.py` 58, 77, 96, 114, 131, 149, 168, 184, 201, 217, 233 ; `bornes_dimensions.csv` lignes 2 à 12.

### 1.5 Ce que donne `synth_calage.py` (réponse Q6)

- **H :** `H = 1,3 + a (1 - exp(-D/c))` par essence (`synth_calage.py:43-44`).
- **hbh :** `hbh = H (1 - CR)`, avec `CR = α + β ln D` borné à 0,20-0,92 (`synth_calage.py:19,53-54` ; `synth_population.py:92,101`). Le LISEZMOI précise que la base du houppier est lue sur les nuages comme la première branche, d'où des houppiers très longs (`LISEZMOI.md:139`).
- **Rh :** le calage donne une **étendue** maximale `ln E = α + β ln D` (`synth_calage.py:20,55-57`), bornée à 0,5 m - 0,40 H (`synth_population.py:97`). Puis `caler_etendue()` cherche le rayon d'enveloppe `Rh` pour que l'étendue réalisée soit celle tirée à 3 % près (`synth_arbres.py:447-457` ; `synth_population.py:61`). **Rh n'est pas l'étendue.** Un export qui ne rejoue pas ce calage de Rh obtient des houppiers 20 à 30 % trop étroits (`LISEZMOI.md:35-40`).
- **b_cible :** tiré autour de la médiane observée des QSM (`synth_population.py:98-100`). **Six feuillus seulement** ont un b observé (de 15 à 1 659 QSM) ; les cinq résineux n'en ont pas (`n_b = 0`), donc b_cible est vide (`synth_calage.py:127-130`). La cible n'est pas atteinte à 0,03 près pour 13 à 40 % des feuillus (`LISEZMOI.md:67-69`).
- **Densité des rameaux :** **aucune valeur calée.** C'est la variable résolue arbre par arbre pour atteindre b_cible (bissection, plage dens0/3 à 3 dens0, longueur de bois plafonnée à 5 m par cm² de D², `synth_arbres.py:460-490`). Sans b_cible, `dens = dens0 · exp(N(0 ; 0,18))` (`synth_essences.py:312`). La réponse de Pascal (« densité des rameaux depuis la calibration ») se lit donc ainsi : feuillus, densité ajustée à b_cible ; résineux, densité tirée, non calée. À lui dire.
- **Plage de D du calage (écart à signaler) :** le calage ne garde que D >= 7 cm (`synth_calage.py:94`) mais le 5e centile de D observé est, en ordre de grandeur, autour de 30 cm pour le pin, 18 cm pour l'épicéa, 40 à 50 cm pour douglas, mélèze et sapin (`bornes_dimensions.csv` colonne `D_obs_q05`, lignes 8 à 12). Pour ces essences, les stades `young` et `pole` sont des **extrapolations** de la courbe H(D) et de la part de houppier. Si Q6 demande les quantiles de `sim/trees` pour un jeune sapin, `hbh` et `Rh` viennent d'une forme d'épicéa décalée sur 5 arbres.
- **Forme de tige des résineux :** `F0 (D/30)^F1` ajusté au tarif v5 de tarif-nemeton (`synth_calage.py:61-85`) ; l'origine des 85 à 98 points n'est pas remontée.

### 1.6 Attributions architecturales « à confirmer »

- Quatre essences sur onze portent un qualificatif dans le code : bouleaux « à confirmer », épicéa « non établi », douglas « sans source », mélèze « contredit » (`synth_essences.py:150,169,202,218`).
- `modeles_architecturaux_sources.csv` : **31 attributions** (lignes 2-32). Douglas : aucune source (l.31). Mélèze : source et 5 QSM disent Rauh, le générateur applique Massart, conservé par choix de Pascal le 20/11/2026 (l.32 ; `synth_essences.py:19`). Épicéa : Massart (l.22) contre Rauh (l.24-25), mixte (l.26). Pin : Lin 2018 se contredit (l.21), verdict QSM indéterminé.
- Les bornes de port (angles, espacements, fourches, enveloppe) sont des **hypothèses de départ** (`synth_essences.py:3-7`).
- Conséquence : les arbres affichés sont synthétiques ; `extras.provisoire` et `synthetique` du plan §4 sont justifiés. La différence Rauh / Massart se verra à l'œil en M6b.

## 2. Licences des jeux de données du calage

| Jeu | Rôle | Licence trouvée | Statut |
|---|---|---|---|
| BioDiv-3DTrees, DOI 10.25625/8PB1IF (GRO.data) | calage de H, CR, étendue, b (`bornes_dimensions.csv`) et de l'architecture | « CC-BY 4.0 » (`references.bib:115`, seconde main) | **non lue à la source** (doi.org inaccessible) |
| Wytham Woods, Calders et al. 2022, Zenodo 7307956 v1.0 (16/11/2022) | architecture seulement | CC BY 4.0 d'après un résumé de moteur de recherche | **non lue à la source** (zenodo.org inaccessible) |
| Demol et al. 2021, Zenodo 4557401 | architecture seulement (mélèze, pin, frêne, hêtre) | non trouvée | **non lue** |
| rTwig (base de rayons de brindilles) | `r_twig_mm` | paquet : « GPL (>= 3) » (`DESCRIPTION`, branche main, 1.4.0.9000) ; LICENSE introuvable (404) ; licence de la base de données non lue | lu en partie |
| Tarif v5 (tarif-nemeton) | forme de tige des résineux | dépôt privé ; sources du tarif non remontées | non lu |

CC BY 4.0 permet l'usage des **dérivés** (des paramètres calés) avec attribution. Ce n'est pas une conclusion juridique : la lecture des textes reste à Pascal. Les URL à ouvrir sont dans la liste du compte rendu.

## 3. Trois points au sol

1. **Un petit sapin ou un jeune douglas.** Faire générer un `young` de sapin (5 arbres de calage) et de pin (5e centile à 30 cm), comparer sa silhouette à un jeune arbre du même âge dans la forêt : la hauteur du houppier vient d'une extrapolation.
2. **Un mélèze adulte.** Branches redressées et courtes (Rauh, ce que disent la source et 5 QSM) ou étages plats (Massart, ce que le générateur dessine) ? Le point que `LISEZMOI.md:134` lui-même demande d'observer.
3. **Un résineux et sa densité de rameaux.** Aucune densité n'est calée pour les cinq résineux : regarder l'épaisseur de leur houppier sur une planche (`planches_arbres_synthetiques.pdf`) contre un épicéa réel.

## 4. Question de contrôle

*Quelle décision cette donnée va-t-elle éclairer ?* Quelles dimensions de référence et quels paramètres l'export des exemplaires (mission E) lit, pour quelles essences il y a un modèle propre, et ce qui peut sortir du dépôt privé.

## 5. Liste de contrôle

- Sources et emplacements : coché pour le code et les tables locales (fichier et ligne). **Non coché :** licences de BioDiv, Wytham et Demol lues à la source ; licence de la base rTwig ; auteurs des commits ; numéro de commit.
- Décomptes : coché (11 essences, 13 codes espar, 31 attributions, 4 qualificatifs, effectifs de calage). Écart d'un arbre (4 951 contre 4 952) noté, non résolu.
- Termes exacts : coché (« à confirmer », « non établi », « sans source », « contredit »).
