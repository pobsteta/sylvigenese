# Mission 071 — export exemplaires tarif nemeton (M6a, mission E du plan)

## Mission

**En une phrase :** Export des exemplaires (Q1 tranchée : par fichiers). Mission à part, validée par Pascal avant lancement ; sa PR se fait sur `tarif-nemeton`, fusionnée par Pascal. Un script court qui, pour chaque essence et chaque stade demandés, écrit les segments en Parquet (essence, D, H, hbh, Rh, b_cible, graine, commit en métadonnées, repère z-up dit), en fixant le dossier courant et en échouant si `bornes_dimensions.csv` est introuvable. Les dimensions viennent de Q6.

Référence : [`docs/plans/m6a.md`](../../docs/plans/m6a.md) §3 (ligne E), avec les réponses de Pascal Q1 à Q8 du 26/11/2026 (journal) et la critique du contradicteur intégrée au plan.

## L'Homme

- **Agent :** `dev` (dépôt tarif-nemeton) — **Temps de la main :** donner.

## Harnais

- **Peut :** `tarif-nemeton/code/synth_export_exemplaires.py` (nouveau), `tarif-nemeton/resultats/synth_arbres/exemplaires/`
- **Ne doit pas :** modifier `synth_arbres.py`, `synth_essences.py`, `synth_calage.py` ou les bornes ; changer un modèle tiré ; copier du code dans `sylvigenese` ; inventer une valeur écologique ; trancher une question de sens (la poser dans le compte rendu).
- **Câblé :** aucune commande git qui écrit, ni dans sylvigenese ni dans tarif-nemeton (l’orchestrateur ouvre la PR sur tarif-nemeton, Pascal la fusionne) ; disque juste (quelques Go), nettoyer ce qui est créé.

## Tests

- mêmes segments, à l'octet près, que `synth_arbres.py --cylindres` pour un cas ; refus si bornes absentes ; la fixture de `sylvigenese` a le même schéma Parquet
