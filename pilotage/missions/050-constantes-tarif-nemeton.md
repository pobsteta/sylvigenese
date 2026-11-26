# Mission 050 — fichier de constantes du tarif NEMETON v5 dans tarif-nemeton

## Mission

**En une phrase :** Écrire `resultats/tarif_v5/parametres_tarif_v5.csv` dans tarif-nemeton (dépôt de Pascal), avec toutes les constantes du tarif v5 qui ne sont aujourd'hui que dans le code (coefficients et profils des résineux, expansion E(D), infradensités, fraction de carbone, bornes de domaine), chacune avec son fichier et sa ligne d'origine et sa source, pour que `post` réécrive les formules sans lire de code (décisions de Pascal Q1 et Q2 du 26/11/2026).

## L'Homme

- **Agent :** `dev` — **Modèle :** opus — **Temps de la main :** donner. PR sur pobsteta/tarif-nemeton préparée par l'orchestrateur, relue et fusionnée par Pascal.

## Harnais

- **Peut :** dans `/home/user/tarif-nemeton` : le nouveau CSV, une section du `LISEZMOI.md` de `resultats/tarif_v5/` qui le décrit, un script de contrôle qui recalcule `tables_tarif_v5.csv` à partir du CSV seul.
- **Ne doit pas :** changer une valeur ni une formule de tarif-nemeton ; inventer une constante ; toucher à sylvigenese.
- **Câblé :** aucune commande git qui écrit.

## Tests

- Le recalcul de `tables_tarif_v5.csv` à partir du seul CSV redonne la table à 1e-9 près (ou l'écart est dit et expliqué).
