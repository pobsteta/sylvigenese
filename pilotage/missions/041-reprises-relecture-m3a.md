# Mission 041 — reprises de la relecture de M3a (documentation)

## Mission

**En une phrase (quoi, et pourquoi) :** Mettre la spec, le README des contrats, la description de `config.schema.json` et la doc de `simulate/src/hauteur.rs` d'accord avec les décisions de Pascal du 25/11/2026 (Q1 à Q4 de M3a, t0 = 2022, trouées sans recrue, référence technique), pour qu'un successeur lise la règle là où elle s'applique (relecture de la PR n° 8, points I4 et mineurs de 033, 037, 040).

## L'Homme

- **Agent :** `dev` — **Modèle :** sonnet — **Temps de la main :** donner.

## Harnais

- **Peut :** `docs/spec.md` (§2, §5, §6, §9), `contracts/README.md` (table korf : t_ref0, h_ref0, age_ref), la description de t0 dans `contracts/json/config.schema.json` et `contracts/tables/params/*.schema.json` si elle est périmée, les commentaires et la doc de tête de `simulate/src/hauteur.rs` (aucun changement de code).
- **Ne doit pas :** changer un résultat, un test, une valeur ; décider une règle qui n'est pas au journal (la signaler).
- **Câblé :** aucune commande git qui écrit ; `make validate` et `cargo test --locked` (dans `simulate/`) verts sur une copie `git archive HEAD` + tes fichiers.

## Tests

- `make validate` vert ; `cargo test --locked` vert (doc seulement) ; chaque ajout de la spec renvoie à sa ligne de journal.
