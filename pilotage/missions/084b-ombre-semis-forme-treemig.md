# Mission 084b — ombre des semis à la forme de TreeMig

## Mission

**En une phrase :** Reprendre la mortalité de stress des semis de `simulate` à la forme de TreeMig (décisions de Pascal du 27/11/2026) : lumière relative de la cellule = exp(−k × couvert projeté) répartie sur 10 classes de largeur égale, seuil de lumière par essence tiré de la tolérance de Niinemets par la correspondance de la mission 083 puis la loi de TreeMig (p. 14), mortalité = part de chaque classe sous le seuil × `stress_mortality`, moyennée sur les classes.

## L'Homme

- **Agent :** `dev` (Rust) — **Temps de la main :** donner.

## Harnais

- **Peut :** `simulate/src/` (semis, paramètres, contrôles), `simulate/tests/`, `contracts/` (`params/regeneration` : termes nouveaux, version mineure), `tests/m5/` (générateur et fixtures ; une nouvelle référence si les résultats changent), `docs/adr/0006-niveau-ser.md` (choix 13), `docs/referentiels/regeneration.md` (renvoi seulement).
- **Ne doit pas :** écrire une valeur écologique en dur (constantes de la loi, coefficients de la correspondance, bornes et nombre de classes, extinction : termes sourcés ou provisoires de `params/regeneration` ou de `config.yml`) ; recopier une valeur de klighs ou de Niinemets par essence ; changer un résultat en `ifn_direct` ; casser l'identité entre fils.
- **Câblé :** aucune commande git qui écrit ; vérification sur une copie `git archive HEAD`.

## Tests

- Formes fermées de la loi lumière-seuil et de la part sous le seuil (classe entièrement au-dessus, au-dessous, coupée) ; continuité en klighs = 5 ; terme absent = code 2 ; `ifn_direct` identique (nominal.json) ; identité de 1 à 7 fils ; cargo, m5, m3 et contrats verts, aucun sauté ; ce qui change dans les résultats en cohortes chiffré.
