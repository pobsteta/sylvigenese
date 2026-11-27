# Mission 086 — mineurs du cycle 13

## Mission

**En une phrase :** Solder les mineurs de la seconde relecture de la PR n° 17 : renommer le signalement `classes_lumiere_et_extinction_provisoires` (il n'y a plus de classes), nommer dans le signalement les essences dont la tolérance N sort de la plage testée de la correspondance (1,5 à 4,6), compléter la garde des littéraux d'affichage (diviseurs comme / 10.0 ou / 2.5), rendre robustes `check_surfaces` et `_check_roles`, et nuancer la docstring de `test_seuil_franchi_stress_entier_oracle_exact`.

## L'Homme

- **Agent :** `dev` — **Temps de la main :** donner.

## Harnais

- **Peut :** `simulate/src/` (signalement seulement), `simulate/tests/`, `contracts/` (schéma des signalements, terme des bornes de N si nécessaire, validateur), `tests/m5/`, `viewer-massif/scripts/tree_model_loader.gd` et ses tests, `contracts/tests/test_m6b_affichage.py`, `docs/adr/0006-niveau-ser.md` (une ligne).
- **Ne doit pas :** changer un résultat de simulation ; inventer une borne (celles de 1,5 et 4,6 viennent de `regeneration.md` §15 : terme sourcé si elles entrent au contrat).
- **Câblé :** aucune commande git qui écrit ; vérification sur une copie `git archive HEAD`.

## Tests

- Signalement renommé, tests et contrat suivis ; essences hors plage nommées dans un cas d'essai ; garde prouvée discriminante sur / 10.0 et / 2.5 ; aucun sauté ; octets des sorties inchangés hors `flags.parquet`.
