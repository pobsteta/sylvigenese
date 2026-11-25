# Mission 040 — point de départ de la courbe de Korf

## Mission

**En une phrase (quoi, et pourquoi) :** Ajouter au modèle `korf` de `dynamics_params` trois termes provisoires et sourcés (`t_ref0` âge de départ, `h_ref0` hauteur de départ, `age_ref` âge de référence), écrits par `dynamics` depuis nemeton, pour que `simulate` choisisse la classe de fertilité du hêtre sans constante cachée (décision du 25/11/2026, journal).

## L'Homme

- **Agent :** `dev` — **Modèle :** sonnet — **Temps de la main :** donner.

## Harnais

- **Peut (périmètre) :** `contracts/tables/params/dynamics_params.schema.json` (description du modèle korf) et ses cas dans `contracts/tests/`, `R/dynamics.R` et son test, le jeu fictif régénéré par `make dynamics` (sorties ignorées par git).
- **Ne doit pas :** toucher à `simulate/` (le moteur lit déjà `ReferenceKorf` en option) ; inventer une valeur (nemeton bd6fbe5, `DYN_KORF_REGIONS`, `DYN_KORF_REF_AGE`).
- **Câblé :** aucune commande git qui écrit ; tests vérifiés sur une copie `git archive HEAD`.

## Tests

- testthat : les trois termes écrits pour le hêtre, valeurs citées ; contrat : un cas conforme, un cas fautif ; `make dynamics` et `make validate` verts.
