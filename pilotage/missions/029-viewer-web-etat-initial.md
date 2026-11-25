# Mission 029 — viewer-web-etat-initial

## Mission

**En une phrase (quoi, et pourquoi) :** Écrire la vue web locale (TypeScript, iTowns 2.46) qui affiche sur le jeu fictif la tuile 3D des arbres de l'état initial, la carte des types de végétation en COG, et la fiche d'une cellule au clic (station, type de végétation, composition, mention « provisoire », commande à copier pour la vue massif), avec un script qui compte les instances dessinées et mesure les images par seconde, pour donner à Pascal une première vue lisible (décision du 25/11/2026).

**Redite par l'agent :** _à compléter par l'agent avant d'agir._

## Les trois questions

| Question | Réponse | Conséquence |
|---|---|---|
| Redire la mission ? | oui | |
| Sait-il faire ? | oui : spec §1 (parcours), §9, docs/referentiels/itowns-instancing.md | |
| A-t-il les moyens ? | oui : Node 22, npm (registres ouverts), Chromium et Playwright préinstallés ; sorties de 028 | |

**Temps de la main :** donner. **Degré de la main :** le chef tranche (orchestrateur, par délégation de Pascal).

## Ma réponse d'abord

_Rempli par Pascal seul._

## L'Homme

- **Agent :** `afficheur` — **Modèle :** sonnet
- **Ce qui ne lui est pas demandé :** la simulation dans le temps (curseur des années : prévu, désactivé tant qu'il n'y a qu'une année) ; Godot.

## Harnais

- **Peut (périmètre) :** `viewer-web/` (src, test, package.json, package-lock.json, configuration du bundler), la cible `viewer` du Makefile.
- **Câblé :** pas de `main`, pas de « terminé » sans tests verts, journal en ajout seul ; aucune commande git qui écrit (l'orchestrateur commite).
- **Ne doit pas :** dépendre d'un service réseau pour s'afficher (fond IGN facultatif : si data.geopf.fr est joignable, sinon la vue s'affiche sur le MNT local et le dit) ; afficher un chiffre sans la mention « provisoire » quand il l'est.
- **Sources autorisées :** docs/spec.md §1, §2, §9, §10 ; docs/referentiels/itowns-instancing.md ; les contrats de 028 ; https://www.itowns-project.org (documentation) si joignable.

## Journal

- **Ce que l'agent inscrit :** une ligne par rendu et par aller-retour, proposée à l'orchestrateur.

## Valeur provisoire (chiffre, réglage)

- aucune.

## Dépend de / rouge attendu jusqu'à

- dépend de 028 (tuiles, fiches, COG) ; les tests de 030 sur la vue sont rouges jusqu'à son rendu.

## Tests

- tests du code TypeScript (node --test) ; script Playwright qui ouvre la page, attend le chargement, compte les instances par l'API (14 080 attendues), relève les images par seconde (référence locale, sans seuil), ouvre une fiche de cellule et vérifie ses champs ; capture d'écran à deviceScaleFactor 2.

## Terrain

- **Échantillon que Pascal vérifiera :** la capture d'écran de la vue et la fiche d'une cellule, puis la même page ouverte par Pascal sur sa machine.

## Qui veille, qui tranche

- **Relecteur :** `relecteur`, puis Claude par délégation (validation du jalon et fusion déléguées le 25/11/2026). **Arrêt :** 3 allers-retours. **Qui tranche :** Claude par délégation, Pascal peut défaire.

## Comment saura-t-on que ça marche ?

`make viewer ZONE=zone_fictive` sert la page en local ; le script compte 14 080 instances et enregistre la capture.
