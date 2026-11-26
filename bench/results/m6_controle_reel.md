# M6a : jeu de contrôle réel hors dépôt (mission 074, 26/11/2026)

> **Ce rapport ne contient que des comptes** (exemplaires, segments, triangles, octets, secondes, codes de sortie).
> Aucune dimension ni aucune coordonnée des exemplaires réels n'est recopiée ici : `tarif-nemeton` est un dépôt privé,
> sans licence (décision de Pascal Q1). Les exemplaires et les `.glb` du contrôle sont sous `data/m6_reel/`, hors dépôt
> (ignoré par git). Les **dimensions D et H demandées viennent du `sim/trees` du jeu fictif**, pas du massif réel.

**Les « vrais arbres »** sont les exemplaires que produit le générateur de `tarif-nemeton` (arbres synthétiques, calibrés
sur des relevés) : par opposition à la fixture de `sylvigenese` (235 segments par arbre, inventée pour la CI).

**État de l'export au moment du contrôle.** Le script d'export, `code/synth_export_exemplaires.py`, est sur la branche
`claude/export-exemplaires` de `tarif-nemeton` (commit `4b0032a`, **PR tarif-nemeton n° 7, brouillon, pas encore
fusionnée par Pascal**). Il a été lancé depuis le clone local (branche courante, dépôt propre, aucune commande git qui
écrit). Si la PR change, ce contrôle est à rejouer. Chaque chiffre renvoie à `m6_reel_controle.csv` (« contrôle Lx »),
`m6_reel_modeles.csv` (« réel Lx ») ou `m6_massif_modeles.csv` (« massif Lx »).

## 1. Ce qui a été lancé (l'ordre du plan, §6)

1. **Demande de dimensions** : `python3 -m sylvigenese.assets --demande-dimensions` sur le `sim/trees` du jeu fictif
   (quantile 0,5, au moins 30 arbres vivants par couple essence-stade ; Q6). Contrat `params/model_dimensions`, **D et H
   seulement**. 0,83 s (contrôle L2).
2. **Export** : `synth_export_exemplaires.py --dimensions <demande> --sortie data/m6_reel/exemplaires`, avec le dépôt
   `tarif-nemeton` comme dossier de travail. Deux fois, pour comparer les octets.
3. **Rejeu** : `tools/rejouer_exemplaires_reels data/m6_reel/exemplaires --sortie data/m6_reel/glb` : lecture et contrat
   `assets.exemplars` des 19 fichiers, construction de tous les `.glb` **deux fois** (comparaison des octets), contrat
   `assets.tree_model` de chaque `.glb`.
4. **Massif** : `assets` sur une zone du jeu fictif (`m6_reel_zone`) configurée avec ces exemplaires, puis `--selftest` de
   la vue Godot sur cette zone.

## 2. Essences et stades exportés

| Essence du générateur | Code espar du `.glb` | Stades exportés | Segments (young, pole, mature, old) | Lignes |
|---|---|---|---|---|
| Quercus_spec | 02 (alias : 03) | 4 | 740, 604, 56 553, 119 900 | réel L2 à L5 |
| Fagus_sylvatica | 09 | 4 | 3 672, 4 478, 55 317, 70 857 | réel L6 à L9 |
| Abies_alba | 61 | 4 | 1 652, 2 090, 74 417, 147 990 | réel L10 à L13 |
| Picea_abies | 62 | **3** (mature absent) | 1 186, 1 803, —, 141 888 | réel L14 à L16 |
| Pseudotsuga_menziesii | 64 | 4 | 1 197, 1 549, 81 480, 127 869 | réel L17 à L20 |

- **19 couples demandés, 19 exportés** (contrôle L3, L13), sur 5 essences (contrôle L4) : **895 242 segments** au total
  (contrôle L14), 51,8 Mo de Parquet (contrôle L19). Sur les 20 couples possibles de ces 5 essences, un n'est pas demandé.
- **Code de sortie de l'export : 0** aux deux exécutions (contrôle L6, L8). 5,7 et 5,4 s (contrôle L7, L9).
- Les 6 autres essences du générateur (11 au total) n'ont **aucun arbre dans le jeu fictif** : elles n'ont pas été
  exercées (reste à M6b, avec le `sim/trees` du massif réel).

## 3. Refus, et pourquoi

- **Refus de l'export : 0** (contrôle L12) ; **refus du rejeu : 0** (code de sortie 0, contrôle L22).
- **Un couple sans dimension demandée** (contrôle L5) : Picea abies, mature. Cause : **1 seul arbre** dans `sim/trees`,
  moins que le minimum de 30 ; la demande ne propose pas de dimension, l'export n'écrit rien (aucune valeur inventée),
  et les arbres de ce couple sont dessinés par le **modèle générique résineux**, signalé et compté (Q3) : 1 arbre en
  2022 (massif L8), aucun en 2032 et 2037 (massif L9, L10). Aucun emprunt à une essence voisine.
- L'export **ne refuse pas** les dimensions hors plage : il les écrit et les marque « non calé » (§4). Les refus de
  l'export (bornes absentes, `hbh`, `Rh` ou `b_cible` fournis dans les dimensions) sont couverts par les 15 tests de la PR n° 7,
  pas rejoués ici.

## 4. « Non calé » : tous les exemplaires

| Compte | Valeur | Ligne |
|---|---|---|
| exemplaires « calé » | **0** | contrôle L15 |
| exemplaires « non calé » | **19 sur 19** | contrôle L16 |
| dont D hors de la plage de D des arbres de calage de tarif-nemeton | 19 | contrôle L17 |
| dont D au-dessus du D maximum du générateur (Fagus, Picea, Abies, Pseudotsuga, stade old) | 4 | contrôle L18 |
| dont résineux (densité des rameaux tirée, aucun `b` observé : la clé `b_cible` est absente) | 11 | réel L10 à L20 (calage) |

**Lecture.** Aucun des 19 exemplaires n'est « calé » parce que les **dimensions du jeu fictif** (D médian par stade)
tombent hors des plages de D de la calibration. Ce n'est pas un défaut de l'export : le contrat l'admet et le dit. Mais
**le chemin « calé » du vrai générateur n'a pas été rejoué** dans ce contrôle. Sensibilité (comptes seulement, export
sans rejeu) : avec les quantiles 0,25 et 0,75 au lieu de 0,5, l'export écrit 19 exemplaires dont **2 calés** dans chaque
cas (contrôle L20, L21). Le contrôle « calé » se fera avec les dimensions du massif réel.

La vue dit les arbres « non calés » à l'écran (selftest : 60 620 arbres non calés sur 60 620 en 2037, selftest L17 à L21).

## 5. Identité des octets et conformité au contrat

| Contrôle | Résultat | Ligne |
|---|---|---|
| deux exports successifs : fichiers Parquet identiques à l'octet près | **19 sur 19** | contrôle L11 |
| rejeu : les deux écritures des `.glb` identiques à l'octet près | **oui** | contrôle L25 |
| contrat `assets.exemplars` sur les 19 Parquet | conformes (code 0) | contrôle L26, L28 |
| contrat `assets.tree_model` sur les `.glb` | **21 fichiers conformes** (19 + 2 génériques), code 0 | contrôle L27, L29 |
| budgets de triangles (20 000, 2 000, 200) | **21 sur 21** tenus | contrôle L32 |
| code de sortie du rejeu | **0** | contrôle L22 |
| contrôles en échec du script de mesure | **0** | contrôle L36 |

L'identité est prouvée **sur cette machine** (numpy 2.5.3, pyarrow 26.0.1, `machine` L8 et L9) ; entre machines, elle
n'est pas promise (plan T12). Le rejeu dure 2,28 s et 353 Mo résidents (contrôle L23, L24).

## 6. Arbres réels traités

- **19 exemplaires réels construits, validés et chargés** (contrôle L33) : 19 `.glb` du générateur de 301 504 à
  628 956 octets, plus 2 génériques (réel L2 à L22) ; 895 242 segments traités (contrôle L34). Triangles : de 7 728 à
  17 196 au niveau 0, de 1 632 à 1 716 au niveau 1, 26 au niveau 2.
- **Arbres du massif d'essai dessinés par ces modèles** (zone du jeu fictif, 4 blocs), par sorte de modèle :

| Année | Arbres | Modèle propre | Alias (code 03 sur le `.glb` 02) | Générique | Ligne |
|---|---|---|---|---|---|
| 2022 | 14 080 | 10 537 | 3 542 | 1 | massif L8 |
| 2032 | 45 954 | 32 493 | 13 461 | 0 | massif L9 |
| 2037 | 60 620 | 42 637 | 17 983 | 0 | massif L10 |

  Pour la fixture, 4 089 arbres en 2022 étaient génériques (massif L2) : avec les 19 exemplaires, il n'en reste qu'un.
  La somme des trois colonnes égale le total à chaque année (le script le contrôle).
- **La vue charge ces `.glb`** : `--selftest` à 0 sur la zone, 60 620 arbres en 2037, 0 générique, 60 620 non calés,
  2,50 s de processus entier, 377 Mo résidents (selftest L17 à L21). Les `.glb` réels sont lus à l'exécution par le
  chargeur de la vue (niveaux `MSFT_lod` lus à la main).

## 7. Ce que ce contrôle ne prouve pas

- **Pas l'aspect** : forme, feuillage et couleur se jugent à l'œil, planche par planche, en M6b.
- **Pas le massif réel** : 5 essences sur 11, dimensions du jeu fictif (D jusqu'au-delà du D maximum du générateur), tous
  « non calés ». Les 44 modèles (11 × 4) restent à exercer.
- **Pas la fusion de la PR n° 7** : le script est celui d'un brouillon.
- **Pas la licence** : les `.glb` réels et les exemplaires restent hors dépôt tant que Pascal n'a pas dit qu'ils peuvent
  être versionnés.

## Rejouer

    python3 bench/m6/mesurer.py --godot <Godot 4.6.3> --tarif-nemeton <dépôt tarif-nemeton, branche claude/export-exemplaires>

Seul `bench/m6/mesurer.py` écrit ces CSV. Sorties conservées hors dépôt : `data/m6_reel/exemplaires/` (19 Parquet,
52 Mo) et `data/m6_reel/glb/` (21 `.glb` et `rejouer_exemplaires.csv`).
