# ADR 0005 — le tarif NEMETON entre dans `params/` par un contrat propre, au format long

- **Date :** 2026-11-26
- **Statut :** acceptée par délégation de Pascal (26/11/2026, journal) ; Pascal peut la défaire
- **Proposée par :** `dev` de la mission 051 (plan `docs/plans/post-volume-carbone.md` §4)
- **Tranchée par :** Claude (orchestrateur, par délégation de Pascal), après la relecture de la PR n° 10

## La décision en une phrase

`import_tarif` lit `resultats/tarif_v5/parametres_tarif_v5.csv` de tarif-nemeton (mission 050, figé
à un commit cité) et l'écrit dans `params/tarif.parquet` au **format long**, **un terme par ligne**,
sous un **contrat propre** (`contracts/tables/params/tarif.schema.json`) : colonnes `essence` ou
`groupe`, `modele`, `terme`, `valeur`, `unite`, `source_code`, `source_biblio`, plus `source_commit`
et `provisoire`. `post` réécrit les formules en les citant (plan T2) et ne lit que ce fichier ; le
contrat décrit les modèles et leur domaine, **sans aucune valeur**.

## Contexte

- Le tarif NEMETON v5 mélange des formes différentes : une loi ln-linéaire pour les feuillus, un
  profil de tige et une expansion E(D) pour les résineux, des infradensités et une fraction de carbone
  par groupe, un rapport racines/aérien, et un domaine de validité par essence (diamètre, hauteur,
  H/D). Décisions de Pascal du 26/11/2026 : Q1 (v5 seule, figée, provisoire), Q2 (un fichier de
  constantes dans tarif-nemeton, `post` réécrit les formules), Q5 (hors domaine : on ne calcule pas,
  on compte).
- Le contrat générique `parameters.schema.json` (`species`, `species_group`, `model`, `term`,
  `value`, `provisoire`, `source`) ne dit ni l'unité, ni la source en deux parties (code et
  bibliographie), ni le commit. Or `post.json` doit citer le commit du tarif, et chaque terme doit
  porter son unité (cm ou m, `sans_unite`) pour que `import_tarif` puisse la vérifier.
- Les modules ne se parlent que par fichiers, aux formats ouverts (ADR 0002) : le tarif doit être
  relisible sans R ni code de tarif-nemeton (dépôt sans licence : on n'en reprend aucun code).

## Options pesées

| Option | Pour | Contre |
|---|---|---|
| **A. Format long, contrat propre `tarif.schema.json`** (proposée) | une unité, une source de code, une source bibliographique et un commit par terme ; même grammaire que les autres `params/` (un terme par ligne, `provisoire`) ; la liste fermée des modèles rend une faute de frappe visible ; le domaine (`domaine`) a ses termes nommés ; relisible ligne à ligne ; le CSV de la mission 050 se copie presque tel quel | colonnes en français (celles du CSV de tarif-nemeton), contre `species`/`value` des autres `params/` ; un contrat de plus ; la liste des modèles est à tenir d'accord avec la mission 050 |
| B. Garder `parameters.schema.json` | rien à ajouter ; `import_tarif.tarif` et `import_tarif.allometry` restent identiques | ni unité, ni commit, ni source bibliographique séparée (tout dans `source`) ; `post.json` ne peut pas citer le commit sans l'extraire d'un texte libre ; un domaine mélangé aux coefficients sans nom réservé |
| C. Garder la grille `tables_tarif_v5.csv` (D × H) et l'interpoler | aucun fichier à ajouter dans tarif-nemeton | refusée par Pascal (Q2) : elle ne couvre ni 7,5 à 10 cm, ni les chênes sous 15 cm, et l'interpolation est une extrapolation déguisée (Q5) |
| D. Une table large, une colonne par terme | lecture directe | une forme par modèle, donc un contrat par modèle ; ne passe pas à la mise à jour du tarif sans changer le schéma |

## Conséquences

- `catalog.yml` : `import_tarif.tarif` pointe vers `tables/params/tarif.schema.json` ;
  `import_tarif.allometry` garde `parameters.schema.json` (étage B, `hcb`, `cw`).
- Modèles (colonne `modele`, liste fermée) : `volume_feuillus`, `profil_tige_resineux`,
  `expansion_resineux`, `infradensite`, `fraction_carbone`, `racines`, `domaine`. Les termes de
  `volume_feuillus` (a, b, c) et de `domaine` (`dbh_min`, `dbh_max`, `h_min`, `h_max`, `hd_min`,
  `hd_max`) sont nommés par le contrat ; ceux du profil de tige et de E(D) sont ceux que la mission
  050 écrit dans `parametres_tarif_v5.csv`.
- Un terme de domaine absent veut dire que la source ne borne pas la grandeur ; `post` ne met jamais de
  valeur à sa place (signaler plutôt que deviner).
- `provisoire` vaut vrai pour toute valeur de tarif-nemeton v5 tant que son dépôt dit « coefficients
  non stabilisés » (README, l. 8) ; toute valeur du summary en hérite.
- Le jeu fictif porte un `params/tarif.parquet` synthétique de cette forme (`tools/fixtures/`), dont les
  termes du profil des résineux sont des placeholders (`synth_p1`, `synth_p2`, `synth_E`) à remplacer
  quand la mission 050 aura fixé les vrais noms.
- Si la mission 050 nomme autrement un modèle ou une colonne, le contrat suit (une ligne) ou
  `import_tarif` convertit ; il ne faut jamais changer un nom en silence.

## Ce que Pascal peut défaire

Tout : la représentation ne touche que le dépôt. Revenir à l'option B demande de perdre l'unité et le
commit par terme, ou de les ranger dans `source`.
