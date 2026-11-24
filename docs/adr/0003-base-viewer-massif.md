# ADR 0003 — base de la vue massif (`viewer-massif`)

- **Date :** 2026-11-24
- **Statut :** acceptée par délégation de Pascal
- **Proposée par :** Claude (orchestrateur), d'après la mission 007
- **Tranchée par :** Claude (orchestrateur, par délégation de Pascal)

## La décision en une phrase

`viewer-massif` est un projet Godot 4 neuf, sous GPL-3. Il reprend de `godot-forest-demo`
(commit `623212f`) deux mécanismes, en citant leur auteur :
- l'herbe générée autour de la caméra ;
- le découpage des arbres en blocs MultiMesh avec imposteurs.

Il ne reprend ni les modèles Sketchfab, ni la musique, ni UniPlayer, ni les effets de ciel.

## Contexte

La mission 007 (`docs/referentiels/godot-forest-demo.md`) a étudié trois voies :
- forker le projet ;
- en reprendre des parties ;
- s'en inspirer seulement.

Les trois demandent d'écrire la lecture de `massif/` (spec §9), le passage du Lambert-93 au
repère de Godot et l'échelle de chaque arbre. Le projet n'a aucun test. Plusieurs de ses
éléments ont une licence non établie, et la musique est sous licence Pixabay.

## Le crible FRANCE

| Lettre | Réponse | Ce que ça coûte | Prêts à payer ? |
|---|---|---|---|
| **F**rugale | On ne reprend que deux mécanismes éprouvés | On réécrit le reste | oui |
| **R**esponsable | `afficheur` et `dev` ; tests GUT sans interface | Godot à installer dans la CI | oui |
| **A**nticiper | Aucune licence douteuse n'entre dans le dépôt | — | oui |
| **N**ovateur | Les trois voies ont été étudiées | — | — |
| **C**oût | Pas de dette de code sans tests | Plus de code à écrire qu'avec un fork | oui |
| **É**cologique | Code sous MIT et CC BY 4.0 réutilisé avec attribution ; le nôtre sous GPL-3 | Fichier `CREDITS.md` | oui |

## Valeurs sacrifiées

**Le rythme.** Un fork aurait donné une scène visible plus tôt.

## Sources

- `docs/referentiels/godot-forest-demo.md` ;
- `docs/referentiels/godot-forest-demo-licences.csv`.

## Question de contrôle

Cette décision tient-elle nos six valeurs, et que sommes-nous prêts à payer pour cela ?
