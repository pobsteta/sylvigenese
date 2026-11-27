# Mission 083 — correspondance Niinemets → klighs (seuil de lumière des semis)

## Mission

**En une phrase :** Ajuster, sur les essences communes à Niinemets et Valladares 2006 et à TreePars (TreeMig), une correspondance monotone de la tolérance de Niinemets vers klighs, avec son erreur, et écrire la loi lumière-seuil de TreeMig (éq. 29) qui en découle, pour que M5b passe l'ombre des semis à la forme de TreeMig (décisions de Pascal du 27/11/2026).

## L'Homme

- **Agent :** `analyste` — **Temps de la main :** donner.

## Harnais

- **Peut :** `bench/m5b/` (script), `docs/referentiels/regeneration.*` (section dédiée), lecture hors dépôt de `data/sources/regeneration/` (Niinemets, TreePars2.txt, documentation TreeMig).
- **Ne doit pas :** écrire dans le dépôt une valeur de klighs ou de Niinemets par essence (seuls les coefficients de la correspondance, l'effectif, l'erreur et la méthode) ; inventer une forme.
- **Câblé :** aucune commande git qui écrit.

## Tests

- Rejouable par un seul script depuis les fichiers hors dépôt (sha256 vérifiés) ; erreur dite (résidus, essences les plus mal prédites, par code et non par valeur).
