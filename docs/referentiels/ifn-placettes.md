# IFN, données brutes : cercles de placette et unité de `c13` (mission 016)

- **Propriétaire :** Pascal
- **Date de consultation :** 2026-11-24
- **Mission redite :** établir, sources lues, les rayons des cercles de placette par classe de dimension et l'unité de `c13` dans la documentation des données brutes de l'IFN.
- **Décision éclairée :** spec §12 (« Documentation IFN : cercles de placette, unité de `c13` »). Elle commande (1) la formule du d130 tiré de `c13`, (2) le rayon à retenir pour le voisinage de concurrence (question 6 de `entrees-externes.md`), (3) la règle de garde IFN (700 m ou 1 km).

## Sources réellement consultées

| # | URL | Ce qui y a été lu |
|---|---|---|
| S1 | https://inventaire-forestier.ign.fr/spip.php?rubrique159 (« Les données brutes ») | liens des archives ; mise à jour des données brutes au 07/10/2026 ; flou des coordonnées ; licence |
| S2 | https://inventaire-forestier.ign.fr/IMG/pdf/ign_imot-2025.pdf (IMOT, « Instructions pour les mesures et observations de terrain », campagne 2025, 190 pages et plus) | **pages 61, 63 et 71 lues en image** ; pages 1-7 et 64-70 aussi |
| S3 | https://inventaire-forestier.ign.fr/spip.php?rubrique166 (« Définitions ») | seuil de recensabilité (lu par WebFetch, résumé du site par un petit modèle) |
| S4 | https://inventaire-forestier.ign.fr/dataifn/data/export_dataifn_doc_2025.zip | téléchargée (5,9 Mo) mais **illisible ici** : archive binaire, aucun outil de décompression dans cette session. Elle contient `IGN_DB_doc_arbre.pdf` et probablement `metadonnees.csv`. **Non lue.** |

Autres pages joignables et lues : `https://inventaire-forestier.ign.fr/` (accueil) et `spip.php?rubrique25` (page des manuels IMOT 2020 à 2026, chemins `IMG/pdf/ign_imot-AAAA.pdf`).

## 1. Cercles de placette (source S2, IMOT 2025, p. 61, « Placettes de mesure » et tableau DIMESS)

Citation (p. 61) : « Les dispositifs de sélection des arbres à inventorier, ou placettes de mesures, sont des placettes circulaires emboîtées, centrées sur le piquet repère. »

| Rayon | Arbres inventoriés (texte de la p. 61) | Classes DIMESS | Circonférence (mm) | Diamètre (cm) |
|---|---|---|---|---|
| R = 6 m | vivants, morts ou chablis, petit bois et très petit bois | 1 TPB, 2 PB | 235 à 705 (705 exclu) | 7,5 à 22,5 (22,5 exclu) |
| R = 9 m | vivants, morts ou chablis, moyen bois | 3 MB | 705 à 1175 (exclu) | 22,5 à 37,5 (exclu) |
| R = 15 m | vivants, morts ou chablis, gros bois et très gros bois | 4 GB, 5 TGB | 1175 et plus | 37,5 cm et plus |

Détails du tableau DIMESS de la p. 61 : TPB 235 à 395 mm (7,5 à 12,5 cm) ; PB 395 à 705 mm (12,5 à 22,5 cm) ; MB 705 à 1175 mm (22,5 à 37,5 cm) ; GB 1175 à 1645 mm (37,5 à 52,5 cm) ; TGB 1645 mm et plus (52,5 cm et plus).

- **Les cercles sont emboîtés et se choisissent par classe de dimension.** Un arbre n'est inventorié que dans le cercle de sa classe. Un gros bois à 10 m du piquet repère est hors du cercle de 9 m mais dans celui de 15 m ; un petit bois à 10 m n'est pas inventorié.
- **Surfaces (calcul de l'acquéreur, π R²) :** 6 m = 113,1 m² ; 9 m = 254,5 m² ; 15 m = 706,9 m². Une tige vaut donc 88, 39 et 14 tiges/ha selon sa classe (poids d'échantillonnage, non fournis dans les données brutes : S1 dit qu'elles ne sont pas pondérées).
- **Seuil de recensabilité (p. 63) :** « seuil de recensabilité (235 mm) ». S3 donne l'ancienne méthode (avant 2005) à 24,5 cm de circonférence et la nouvelle à 23,5 cm.
- **Arbres « limite » (p. 61) :** arbre dont le périmètre à 30 cm au-dessus du niveau de base intercepte le périmètre de la placette ; tolérance de ± 20 cm sur le rayon ; ceux à l'Est (0 à 199 grades) sont à toucher, ceux à l'Ouest (200 à 399 grades) sont à dépasser.
- **Photo-interprétation :** rayon de 25 m (S2 p. 5 ; page des manuels, S1 bis). Ce n'est pas la placette de mesure.

## 2. Unité de `c13` (source S2, IMOT 2025, p. 71)

Titre de la fiche : « C13 : circonférence à 1,30 m (CR4) ».
Définition (citation) : « Circonférence **en millimètres**, à 1,30 mètre à partir du niveau de base en suivant l'axe de la tige. »

- **`c13` est une circonférence, en millimètres.** Le d130 en centimètres se calcule : `d130_cm = c13_mm / (10 π)` (formule de l'acquéreur, non du manuel). Exemple : 1175 mm donne 37,4 cm, cohérent avec le seuil de 37,5 cm du tableau DIMESS.
- **Piège relevé :** la page « Définitions » (S3) parle de circonférence « ≥ 23,5 cm » pour la recensabilité ; ce sont des **seuils** exprimés en cm, non l'unité du champ `c13`.
- Hauteur de mesure : 130 cm au-dessus du niveau de base (tolérance ± 3 cm ; p. 70, MES_C13 = 1). Variante décalée en hauteur : champ `HCD` en cm (p. 70).
- **Non vérifié :** que la colonne `c13` de l'export `dataIFN` soit livrée en mm. L'IMOT décrit la **saisie de terrain** ; le dictionnaire de l'export (`metadonnees.csv`, `IGN_DB_doc_arbre.pdf` dans S4) n'a pas pu être ouvert. À vérifier à la première lecture du fichier `ARBRE` (une valeur d'arbre courant doit être de l'ordre de 300 à 2000, pas de 30 à 200).

## 3. Flou des coordonnées (source S1, pour mémoire)

« Les coordonnées fournies correspondent au centre de la maille kilométrique la plus proche. La placette réelle peut se trouver à 700 m maximum de ce centre » (résumé du site par WebFetch, pas relu à l'écran). Les données ne sont pas pondérées ; licence Ouverte / Etalab 2.0.

## Écarts relevés entre sources

1. **Rayon 15 m seul (typopeuplement, ADR 0005) contre trois cercles (IGN).** Le 15 m ne couvre que les gros et très gros bois ; typopeuplement retient une surface de 706,9 m² pour toute la placette. Les cercles de 6, 9 et 15 m du commentaire de tarif-nemeton sont confirmés par la source IGN (p. 61), avec leur règle d'attribution par classe.
2. **`c13` : « unité à confirmer » (sylvostation, `R/placettes.R:121-123`).** Tranché pour la saisie : millimètres. Reste à confirmer pour l'export.
3. **Flou : « kilomètre » (CLAUDE.md de sylvigenese) contre « 700 m » (IGN, sylvostation, tarif-nemeton).** L'IGN dit : centre de la maille de 1 km, écart réel jusqu'à 700 m. Les deux chiffres décrivent la même chose (maille de 1 km, écart maximal de 700 m). Le CLAUDE.md n'est pas à moi : la règle écrite est à décider par Pascal.

## Limites

- Une seule campagne d'instructions lue (2025). Les manuels 2020 à 2024 existent ; je n'ai pas vérifié que les rayons et l'unité y soient identiques.
- Pages lues en image du PDF ; lecture manuelle, pas d'extraction de texte.
- `metadonnees.csv` : **non lu** (voir S4). Spec §12 le nomme : point non levé.
