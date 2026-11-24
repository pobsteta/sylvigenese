# Mission 006 — surfaces des sylvoécorégions

## Mission

**En une phrase (quoi, et pourquoi) :** établir, sources à l'appui, la surface totale et la
surface boisée de chacune des 86 SER (et des 5 SER d'alluvions récentes), et désigner la plus
grande. Cette donnée dimensionne la grille du moteur (ADR 0001, B2, et « Exigences
mesurables » : résolution de 10 ou 25 m, mémoire dans 31 Go, 5 jours pour 100 ans).

**Redite par l'agent :** _à compléter par l'agent avant d'agir._

## Les trois questions

| Question | Réponse | Conséquence |
|---|---|---|
| Redire la mission ? | oui | la décision éclairée est nommée |
| Sait-il faire ? | oui | CQQCOQP, deux sources par observation |
| A-t-il les moyens ? | en partie | pas d'outil SIG : si aucun tableau n'est publié, il rend la source de la couche (URL, format, version) pour une mission de calcul séparée, au lieu de calculer à la main |

**Temps de la main :** donner. **Degré de la main :** sollicitation d'avis.

## Ma réponse d'abord

_Rempli par Pascal seul._

## L'Homme

- **Agent :** `acquereur` — **Modèle :** sonnet
- **Ce qui ne lui est pas demandé :** choisir la résolution, calculer des surfaces à partir de
  géométries.

## Harnais

- **Peut :** écrire `docs/referentiels/surfaces-ser.md` et `docs/referentiels/surfaces-ser.csv`.
- **Ne doit pas :** inventer une surface, recopier une nomenclature d'un autre système au lieu
  de la citer.
- **Sources autorisées :** IGN (inventaire forestier, Géoplateforme, data.gouv.fr), documents
  de l'IFN (mémentos, fiches SER), publications citant ces surfaces.

## Rendu attendu

- Un CSV : `code_ser,nom,surface_totale_km2,surface_boisee_km2,taux_boisement,source_url,date_consultation,ecart`.
- La plus grande SER par surface totale et par surface boisée, avec le nombre de cellules
  à 10 m et à 25 m, en calcul simple et dit comme tel.
- Les écarts entre sources, les points non vérifiés, trois points au sol, une ligne de journal
  proposée.

## Comment saura-t-on que ça marche ?

Le CSV compte une ligne par SER, sans valeur sans source, et Pascal peut lire en dix secondes
la plus grande SER et sa taille en cellules.
