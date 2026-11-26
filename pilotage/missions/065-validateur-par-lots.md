# Mission 065 — le validateur des contrats lit les grandes tables par lots

## Mission

**En une phrase :** Faire lire les Parquet au validateur des contrats par lots, avec une mémoire bornée et exactement les mêmes contrôles, pour que `simulate` puisse valider ses sorties sur une SER réelle et que M5a se mesure à N = 4 000 (le validateur était tué faute de mémoire sur 128 M lignes ; journal du 26/11/2026).

## L'Homme

- **Agent :** `dev` — **Modèle :** opus — **Temps de la main :** donner. Fiche écrite après coup par l'orchestrateur, la consigne faisait foi.

## Harnais

- **Peut :** `contracts/validator/`, `contracts/tests/`.
- **Ne doit pas :** relâcher une règle de contrat ; laisser passer un doublon de clé.
- **Câblé :** aucune commande git qui écrit.

## Tests

- Doublon réparti sur deux lots détecté, erreur au dernier lot signalée, messages identiques à une lecture d'un seul tenant ; mémoire bornée mesurée à N = 4 000.
