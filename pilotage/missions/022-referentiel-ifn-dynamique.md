# Mission 022 — référentiel IFN de la dynamique

## Mission

**En une phrase (quoi, et pourquoi) :** Établir, sources IFN lues et citées, les tables et colonnes des données brutes qui servent à ajuster l'accroissement (accroissement radial sur 5 ans), la mortalité à 5 ans (placettes revisitées) et le recrutement (arbres franchissant 7,5 cm), leurs unités, codes, années de validité et règles de revisite, ainsi que la source des valeurs indicatrices de la flore (Ellenberg ou indicateurs de sylvostation) pour le gradient trophique, afin que les contrats, le jeu fictif et le module dynamics ne nomment aucune variable de mémoire (BRIEF §6 : « les noms exacts des variables IFN sont à vérifier dans la documentation des données brutes avant tout ajustement »).

**Redite par l'agent :** _à compléter par l'agent avant d'agir._

## Les trois questions

| Question | Réponse | Conséquence |
|---|---|---|
| Redire la mission ? | oui | |
| Sait-il faire ? | oui : documentation IFN déposée en local, sylvostation en lecture seule | |
| A-t-il les moyens ? | oui : les PDF se lisent avec l'outil Read (par pages), metadonnees.csv en texte | |

**Temps de la main :** donner. **Degré de la main :** le chef tranche (orchestrateur, par délégation de Pascal).

## Ma réponse d'abord

_Rempli par Pascal seul._

## L'Homme

- **Agent :** `acquereur` — **Modèle :** sonnet
- **Ce qui ne lui est pas demandé :** aucun code, aucun ajustement, aucune décision de modèle.

## Harnais

- **Peut (périmètre) :** `docs/referentiels/ifn-dynamique.md` (et un `.csv` des colonnes s'il aide).
- **Câblé :** pas de `main`, pas de « terminé » sans tests verts, journal en ajout seul ; aucune commande git qui écrit (l'orchestrateur commite).
- **Ne doit pas :** citer une colonne sans le fichier et la page ou la ligne de metadonnees.csv ; trancher un choix de modèle (le signaler comme question).
- **Sources autorisées :** /home/user/ref-externes/ifn_doc_2025/ (documentation des données brutes IFN, export du 2026-10-07 : IGN_DB_doc_arbre.pdf, IGN_DB_doc_placette.pdf, IGN_DB_doc_flore.pdf, IGN_DB_doc_ecologie.pdf, IGN_DB_documentation_generale.pdf, metadonnees.csv), téléchargée par l'orchestrateur depuis https://inventaire-forestier.ign.fr/dataifn/data/export_dataifn_doc_2025.zip ; /tmp/claude-0/repos/sylvostation (R/placettes.R, inst/extdata/, en lecture seule, https://github.com/pobsteta/sylvostation commit 2864d70) ; docs/referentiels/ifn-placettes.md ; docs/spec.md §6 ; docs/BRIEF.md §6.

## Journal

- **Ce que l'agent inscrit :** une ligne par rendu et par aller-retour, proposée à l'orchestrateur.

## Valeur provisoire (chiffre, réglage)

- aucune.

## Dépend de / rouge attendu jusqu'à

- aucune ; précède 023, 024, 025 et 026.

## Tests

- chaque colonne a sa source (fichier, page) ; au moins deux sources concordantes pour les règles de revisite (documentation générale et fiche de table) ; ce qui n'a pas été trouvé est dit.

## Terrain

- **Échantillon que Pascal vérifiera :** le tableau des colonnes de `docs/referentiels/ifn-dynamique.md`, comparé à un export IFN réel de Pascal.

## Qui veille, qui tranche

- **Relecteur :** `relecteur`, puis Claude par délégation (validation du jalon et fusion déléguées le 25/11/2026). **Arrêt :** 3 allers-retours. **Qui tranche :** Claude par délégation, Pascal peut défaire.

## Comment saura-t-on que ça marche ?

Les missions 023 à 026 n'inventent aucun nom de colonne : chacune renvoie à une ligne de ce référentiel.
