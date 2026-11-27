# Mission 081 — mineurs du cycle 11

## Mission

**En une phrase :** Solder les mineurs de la relecture de la PR n° 13 : docstring de la référence cohorts de `tests/m5`, citation exacte des coefficients de Lanczos et test de la branche de réflexion de la gamma dans `simulate/src/dispersion.rs`.

## L'Homme

- **Agent :** `dev` — **Temps de la main :** donner.

## Harnais

- **Peut :** `simulate/src/dispersion.rs` (commentaires et tests seulement), `simulate/tests/`, `tests/m5/test_m5_stress_mortality.py` (docstring seulement).
- **Ne doit pas :** changer un résultat.
- **Câblé :** aucune commande git qui écrit ; vérification sur une copie `git archive HEAD`.

## Tests

- cargo test vert, m5 vert, aucun sauté ; octets inchangés.
