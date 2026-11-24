# Mission 005 — banc d'essai : mesures

## Mission

**En une phrase (quoi, et pourquoi) :** mesurer les cinq variantes du banc (`r-base`,
`r-rcpp`, `py-numpy`, `py-numba`, `rust`) selon `bench/SPEC.md` §9, sur la même machine,
pour éclairer le choix du langage de l'ADR 0001 (vitesse, mémoire, robustesse à l'échelle
d'une SER).

**Redite par l'agent :** _à compléter par l'agent avant d'agir._

## Les trois questions

| Question | Réponse | Conséquence |
|---|---|---|
| Redire la mission ? | oui | |
| Sait-il faire ? | oui | protocole de `bench/SPEC.md` §9 |
| A-t-il les moyens ? | oui, en partie | conteneur à 4 cœurs et 15 Go : ce n'est pas la machine de référence de Pascal (B1, non tranché) |

**Temps de la main :** donner. **Degré de la main :** le chef tranche (protocole imposé).

## Ma réponse d'abord

_Rempli par Pascal seul._

## L'Homme

- **Agent :** `analyste` — **Modèle :** sonnet
- **Ce qui ne lui est pas demandé :** modifier les implémentations, choisir le langage.

## Harnais

- **Peut :** écrire `bench/results/` (script de lancement, CSV des mesures, rapport) ; sorties
  volumineuses dans `/tmp` seulement.
- **Ne doit pas :** modifier `bench/SPEC.md` ni `bench/{python,r,rust}/` ; lancer deux mesures
  en même temps (elles se gêneraient).

## Protocole

- Tailles `N ∈ {500, 1000, 2000, 4000, 8000}`, `T ∈ {1, 4}`, graine 42.
- `Y = 100` pour `N ≤ 1000` ; `Y = 10` au-delà, avec une extrapolation à 100 ans dite comme
  telle.
- Pour chaque essai : `timing.json`, mémoire maximale (`/usr/bin/time -v`), code de sortie.
- Une variante qui dépasse la mémoire ou un plafond de 45 min par essai est notée « hors
  mémoire » ou « hors temps ». Les tailles supérieures de cette variante sont alors sautées.
- Identité au bit près entre `T = 1` et `T = 4` (`cmp`), à chaque taille.
- Écart relatif maximal entre variantes sur `summary.csv`, à chaque taille.
- `--inject-nan 5` et `--hmax-zero` pour chaque variante à `N = 200` : code de sortie et
  message.
- Lignes de code hors tests, par variante.

## Valeur provisoire

- Plafond de 45 min par essai : provisoire, choisi pour tenir la mission dans la journée.

## Comment saura-t-on que ça marche ?

`bench/results/RESULTATS.md` donne un tableau complet (variante × N × T), sans case vide non
expliquée, et Pascal peut le lire en dix secondes.
