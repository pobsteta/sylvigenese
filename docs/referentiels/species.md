# Table des essences `contracts/species.csv` (mission 011)

- **Propriétaire :** Pascal
- **Date de consultation :** 2026-11-24
- **Mission redite :** établir `contracts/species.csv` (espar en chaîne avec zéro de tête, nom latin, CD_REF TAXREF, codes nemeton et tarif-nemeton), avec la source de chaque ligne et la règle de `Quercus_spec`, pour que tous les modules parlent la même nomenclature (spec §8).
- **Décision éclairée :** quelle clé de jointure et quelle règle de rattachement les modules reprennent (espar en chaîne ; `Quercus_spec` = 02 + 03 ; groupe feuillu ou résineux pour le plafond `h_pot` par famille).
- **Méthode :** lecture seule des trois dépôts, **aucune exécution** (pas d'outil de calcul dans cette mission). Rien n'est calculé : chaque valeur est recopiée d'un fichier cité, ligne par ligne. Les décomptes ont été faits par recherche de texte.
- **Nomenclature tenue par un autre système :** les codes `espar` et les CD_REF sont ceux de l'IGN (IFN) et du MNHN (TAXREF). Ce fichier les **relie**, il ne les définit pas ; la source unique d'un code reste son propriétaire.

## Les fichiers lus (et uniquement ceux-là)

| Clé dans `source` | Fichier (lecture seule) | Rôle |
|---|---|---|
| `N:L` | nemeton `inst/extdata/ifn_espar_correspondance.csv`, ligne L | espar, nom latin (`espece_sci`), code P1 (`code_p1`) ; 193 lignes |
| `C:L` | sylvostation `inst/extdata/ifn_espar_cdref.csv`, ligne L (copie de `espar-cdref13.csv`, IGN) | CD_REF en **TAXREF v13.0** ; 193 lignes ; espar **sans zéro** pour 02 à 09 |
| `K:L` | sylvostation `inst/extdata/ifn_espar_codes.csv`, ligne L (`metadonnees.csv` de l'IFN, unité ESPAR1) | code tel que noté dans ARBRE (avec zéro) ; 195 lignes, dont 29AF et 68CE |
| `G:L` | nemeton `inst/extdata/infradensite_espar.csv`, ligne L (même numéro de ligne que `N`) | colonne `groupe` (feuillu, resineux) |
| `X:L` | sylvostation `inst/extdata/taxref_v18_extrait.csv`, ligne L (extrait du `TAXREFv18.txt` du MNHN, `SOURCES.md:131-137`) | CD_REF en **TAXREF v18** |
| `T:fichier:L` | tarif-nemeton `code/synth_essences.py` (clé du dictionnaire `ESSENCES`) et `resultats/synth_arbres/bornes_dimensions.csv` (ligne) | code `Genre_espece` |

Commits : ceux de la mission 008 (nemeton bd6fbe5, sylvostation 2864d70, tarif-nemeton 0f51b96), **non revérifiés dans cette mission**.

URL consultées en ligne : `https://taxref.mnhn.fr/api/taxa/97947` et `https://inpn.mnhn.fr/espece/cd_nom/97947` ; **les deux ont échoué** (nom d'hôte non résolu : domaines hors de ceux que la session autorise). Aucune page en ligne n'a donc été lue. Pour ouvrir ces sources, `taxref.mnhn.fr` et `inpn.mnhn.fr` (ou `assets.patrinat.fr`, archive TAXREF v18 de 60 Mo, voir `SOURCES.md:133-135`) doivent être autorisés dans la session.

## Règles de construction

- **Une ligne par code `espar` de l'unité ESPAR1 : 195 lignes** (193 codes taxonomiques + 2 codes génériques 29AF et 68CE). Les trois dépôts ne se contredisent pas sur l'ensemble : nemeton (193), `espar-cdref13` (193), `metadonnees.csv` (195). L'identité des ensembles a été établie en rattachant, code par code, une ligne `C` et une ligne `K` à chacune des 193 lignes `N` ; elle n'a pas été vérifiée par un script.
- **`espar`** : chaîne, avec zéro de tête (`02` à `09`), selon `K` (code d'ARBRE) et `N`. Le fichier `espar-cdref13` écrit `2` à `9` ; la jointure se fait donc sur la chaîne à deux caractères, jamais sur un entier (nemeton `R/ifn_espar.R:98-104` tolère les deux écritures, ce que ce contrat ne fait pas).
- **`latin`** : `espece_sci` de nemeton (`N`), avec sous-espèce ou variété comme dans l'unité ESPAR1 (`K`). Comparaison avec `K` et avec `lib_cdref` (`C`) : faite à l'œil, sans écart de nom relevé ; **non exhaustive**.
- **`taxref_cd_ref`, `taxref_version`** : le CD_REF **v18** quand l'extrait de sylvostation contient la ligne dont le CD_NOM égale le `cd_ref` v13 (37 lignes). Sinon **vide**, et la colonne `ecart` donne le `cd_ref` v13 (`v13=N`) pour une conversion ultérieure : **156 lignes de taxons** ; s'y ajoutent les 2 codes génériques 29AF et 68CE, vides par nature (37 + 156 + 2 = 195). Aucun CD_REF v13 n'est présenté comme du v18.
- **`nemeton_code`** : le **code P1** à quatre lettres (`code_p1` de `N`). 20 lignes. Il est choisi parce que c'est celui de P1 et des courbes de station (`R/ifn_espar.R:3-7`) ; le code « tolérances » de nemeton (binôme en `snake_case`, 194 valeurs) n'est pas repris : c'est le nom latin, déjà dans la colonne `latin`.
- **`tarif_nemeton_code`** : les 11 codes de `ESSENCES` (`synth_essences.py:253-255`) ; ces mêmes 11 codes sont les 11 lignes de `bornes_dimensions.csv`. 13 lignes `espar` les portent.
- **`groupe`** : `feuillu` ou `resineux` (famille, comme `Compo1` de typopeuplement, 1 feuillus, 2 résineux). Repris de `G`. Deux corrections : 25E3 et 25E5 (Salix), classés `resineux` par nemeton (`infradensite_espar.csv:54-55`) alors que ce sont des feuillus ; 29AF et 68CE, absents de `G`, lus dans leur libellé.
- **`source`** : les clés ci-dessus, séparées par `|`. **`ecart`** : tout ce qui diverge entre sources, séparé par ` ; `.

### Règle de `Quercus_spec`

`Quercus_spec` = **`02` (Quercus robur) + `03` (Quercus petraea)**, et rien d'autre.

- Le dépôt le dit : « Chênes sessile et pédonculé » (`synth_essences.py:97`), « moy. pédonculé/sessile » (`code/anciens/tarif_v1_src/nemeton_tarif_v0.py:34`), et le calage ne rattache que `Quercus robur L.`, `Quercus petraea L.` et `Quercus sessiliflora Sal.` à `Quercus_spec` (`code/construire_arbres_peses.py:73-74`).
- **Écart relevé :** le code porte aussi le libellé « Quercus spp. » (`construire_jeu_unifie.py:21`), qui dit tout le genre. Les 9 autres espar de Quercus (04, 05, 06, 07, 08P, 08S, 29CE, 29CM, 34) restent **sans** `tarif_nemeton_code` (« hors Quercus_spec ») : le tarif n'a pas été calé sur eux.
- **Distinct de la règle de l'étage B :** `etage_b_volumes.py:29-31` rend `Quercus_spec` pour « mélange de feuillus » de la BD Forêt. C'est une simplification de **type de peuplement** (fichier `etage_b_volumes.py:8-9` : « chênes (simplification) »), pas une équivalence d'essence. Elle n'est **pas** reprise dans cette table ; si `prepare` s'en sert, elle s'écrit à part, avec `species_source`.
- `Betula_spec` : même logique de genre, rattaché à `12V` et `12P` (seuls bouleaux de l'IFN). Le calage nomme *Betula alba* et *Betula pendula* (`construire_arbres_peses.py:74,166`) ; que `12P` en fasse partie est une conséquence du code de genre, non une phrase du dépôt.

## Écarts relevés entre sources

1. **TAXREF v13 contre v18.** Sur 37 lignes retrouvées dans l'extrait v18, 32 gardent leur CD_REF ; **5 changent** (le nom v13 est devenu synonyme) : `02` 139596 vers 116759 (*Quercus robur*) ; `62` 138781 vers 113432 (*Picea abies*) ; `23AB` 124306 vers 83732 (*Aria edulis*) ; `23AM` 124329 vers 975567 (*Hedlundia mougeotii*) ; `41` 124346 vers 975515 (*Torminalis glaberrima*). Une jointure par le CD_REF v13 donnerait donc des erreurs sur ces cinq essences. Les deux sources (IGN v13 et MNHN v18) ne sont pas indépendantes sur le nom, mais le sont sur la date.
2. **25E3 et 25E5.** `espar-cdref13` et nemeton `ifn_espar_correspondance.csv` écrivent `25000` et `2500000` ; le code d'ARBRE (`ifn_espar_codes.csv:58,60`) et nemeton lui-même ailleurs (`emerge_coefficients.csv:56-57`) écrivent `25E3` et `25E5`. `25E5` lu comme nombre donne 2 500 000 et `25E3` donne 25 000 : l'hypothèse est une conversion par un tableur dans `espar-cdref13` ; je ne l'ai pas vérifiée à la source IGN. La table retient `25E3` et `25E5`, la forme d'ARBRE. **Décision de Pascal si l'on préfère l'autre.**
3. **Salix classés « résineux »** dans `infradensite_espar.csv:54-55` (nemeton) : corrigé dans `groupe`, signalé dans `ecart`. Cela touche la densité de bois de ces deux essences dans nemeton, pas cette table.
4. **29AF et 68CE** : présents dans les codes d'ARBRE et utilisés par nemeton (`ifn_tarif_schaeffer_ser.csv`, `emerge_coefficients.csv`), absents de `espar-cdref13` et de la table de correspondance de nemeton. Sans taxon ni CD_REF, par nature.
5. **49TA et 49TG** : même taxon (*Tamarix gallica*), même CD_REF v13 (125426), deux codes.
6. **POSP.** Le code P1 « Populus cultive » (`ifn_volume_equations.csv:16`) ressemble à l'espar `19` « Peuplier cultivé », mais nemeton ne le relie pas (`ifn_espar_correspondance.csv:28`). **Non repris** (ce serait un rapprochement par le libellé). Idem : la doc dit « 24 essences » P1 (`R/ifn_espar.R:7`), le fichier en compte 21 espèces et 2 codes génériques ; 20 sont reliées à un espar.
7. **Un code d'ARBRE hors dictionnaire** : `332G` (table ARBRE de la GRECO D, `SOURCES.md:245`), absent de `metadonnees.csv`. Pas de ligne : sans définition, je ne peux pas l'écrire sans l'inventer.
8. **Libellés** (sans effet sur les codes) : `17F` « Frêne à fleur » (nemeton, IGN) contre « fleurs » (`K`) ; `23PF` « en cur » (IGN) contre « en cœur » (`K`).

## Limites, dites

- **TAXREF v18 n'est pas joignable** ; 156 lignes sur 195 n'ont donc pas de `taxref_cd_ref`. Les 37 valeurs v18 viennent de l'extrait de sylvostation, qui ne contient que les 269 taxons de la flore IFN : ce n'est **pas** une lecture de TAXREF en ligne, et ce n'est pas une deuxième source indépendante du MNHN.
- **Pas de deuxième source indépendante** pour la correspondance espar vers latin : nemeton, sylvostation et l'IFN partent du même fichier IGN. Le seul contrôle indépendant est celui de la date (v13 contre v18).
- **tarif-nemeton** : dépôt sans licence ; seuls des noms de code y sont lus, aucune donnée n'est copiée. D'autres libellés de genre apparaissent dans des scripts de calage (`Tilia_spec`, `Ulmus_spec`, `Quercus_rubra`, `Prunus_avium`, `Corylus_avellana`…, `construire_jeu_unifie.py:21-30`, `architecture_modeles.py:66-69`) : ce sont des étiquettes de jeux TLS, hors tarif ; **non reprises**.
- **`essence_arbre`** de l'inventaire vidéo (34 codes en français, `essences_bdforet_v2.json`) et classes BD Forêt (`bdforet_essence_espar.csv`) : **non reliées ici** ; ce sont des regroupements, pas des essences. À produire si `prepare` lit `inventaire_video.gpkg`.
- Le code « tolérances » de nemeton n'est pas dans le fichier.
- Rien n'a été exécuté : le schéma de la mission 009 n'a pas pu valider le fichier. Le fichier a 9 colonnes sur chaque ligne et 195 lignes (comptage par recherche de texte).

## Trois points au sol (à vérifier par Pascal)

1. **Les chênes d'une parcelle mixte** (par exemple un peuplement de chênes et de hêtre à Fontainebleau) : l'essence déclarée est-elle bien 02 ou 03 ? Si un chêne pubescent (05) ou rouge (04) y entre, le tarif `Quercus_spec` n'a pas été calé pour lui. C'est le cas le plus sensible : la règle de l'étage B range en outre tous les « mélanges de feuillus » dans `Quercus_spec`.
2. **Les saules** : relever sur une placette IFN d'une zone humide le code d'essence réellement noté (`25E3`, `25E5` ou `25000`, `2500000`) dans ARBRE. C'est le point où la table a choisi une écriture sur une hypothèse.
3. **Un sorbier ou un alisier** (alisier blanc 23AB, alisier torminal 41, alisier de Mougeot 23AM) : la jointure par CD_REF v13 puis v18 change de taxon accepté ; contrôler le nom attendu sur la flore locale avant de joindre à une liste de plantes.

## Question de contrôle

*Quelle décision cette donnée va-t-elle éclairer ?* **La clé de nomenclature que tous les modules emploient pour l'essence** (espar en chaîne), la façon de passer à TAXREF v18 (CD_REF, 5 essences changent depuis la v13) et le périmètre de `Quercus_spec`, avant que `prepare`, `dynamics` et `import_tarif` ne s'écrivent.

## Questions à Pascal

1. `25E3`/`25E5` (code d'ARBRE) ou `25000`/`2500000` (`espar-cdref13`) comme clé ?
2. `Quercus_spec` = 02 + 03 seulement, ou tout le genre (« Quercus spp. ») ? Et la simplification « mélange de feuillus vers chênes » de l'étage B : l'écrire dans `prepare`, ou la refuser ?
3. `nemeton_code` = code P1 (4 lettres) : convient-il, ou faut-il le code « tolérances » (régénération) en plus ? Et POSP vers 19 ?
4. Autoriser `taxref.mnhn.fr` (ou `assets.patrinat.fr`) pour remplir les 156 CD_REF v18 manquants ?

## Liste de contrôle

**Passée, avec les points non cochés suivants.**

1. **Sources et emplacements : coché avec réserves.** Chaque ligne porte ses lignes de fichier (`source`) et sa version TAXREF. Non coché : aucune URL en ligne n'a pu être lue (deux tentatives, deux échecs, citées ci-dessus) ; les commits ne sont pas revérifiés.
2. **Décomptes complets : coché avec réserves.** 195 lignes pour 195 codes ESPAR1 ; 37 CD_REF v18 + 156 vides = 193 + 2 ; 20 codes P1 ; 11 codes tarif sur 13 lignes. Non coché : l'identité des ensembles de codes entre trois fichiers a été faite à la main, non par script ; les comptes viennent de recherches de texte, rien n'a été exécuté.
3. **Termes exacts, limites dites : coché avec réserves.** Les noms latins sont ceux des fichiers ; la comparaison des trois jeux de latin est à l'œil. L'hypothèse du tableur pour 25E3/25E5 n'est pas vérifiée à la source.
4. **Statut dit tel qu'il est : coché.** Table incomplète en TAXREF v18 (19 % remplie) ; non validée par le schéma de 009 ; aucun commit ; sources de tarif-nemeton sans licence, noms de code seuls lus.

## Ligne de journal proposée

`2026-11-24 | acquéreur | mission 011 : contracts/species.csv (195 lignes, espar en chaîne, une par code ESPAR1) et docs/referentiels/species.md. Quercus_spec = 02 + 03 ; CD_REF v18 rempli pour 37 lignes seulement (TAXREF injoignable, extrait de sylvostation), les 156 autres portent leur v13 dans ecart ; 5 essences changent de CD_REF entre v13 et v18 ; 25E3/25E5 retenus contre 25000/2500000 de espar-cdref13. 4 questions à Pascal.`
