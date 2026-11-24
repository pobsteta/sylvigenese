# Mission 001 — moteurs existants : TreeMig, LANDIS-II, iLand

## Mission

**En une phrase (quoi, et pourquoi) :** établir, sources à l'appui, ce que TreeMig,
LANDIS-II et iLand permettent de réutiliser pour sylvigenese, pour éclairer la décision de
l'ADR 0001 : réutiliser ou adapter un moteur existant (option G), ou en écrire un, et dans
quel langage.

**Redite par l'agent :** _à compléter par l'agent avant d'agir._

## Les trois questions (règle de staffing)

| Question | Réponse | Conséquence |
|---|---|---|
| Peut-il redire la mission en une phrase, avec son but ? | oui | la décision éclairée est nommée (ADR 0001, option G) |
| Sait-il comment faire ? | oui | CQQCOQP, deux sources par observation, grille ci-dessous |
| A-t-il les moyens ? | oui, en partie | recherche et lecture web ; certains sites peuvent être bloqués par le réseau de la session, ce qui doit être signalé et non contourné |

**Temps de la main :** donner. Pascal a décidé le lancement le 24/11/2026 ; l'agent
collecte, l'orchestrateur rend à Pascal, Pascal tranche.

**Degré de la main :** sollicitation d'avis. L'agent rapporte des faits sourcés et peut
donner un avis séparé ; il ne tranche pas.

## Ma réponse d'abord

_Rempli par Pascal seul, avant de lire le travail de l'agent._

## L'Homme

- **Agent :** `acquereur`
- **Modèle :** sonnet
- **Ce qui ne lui est pas demandé :** choisir le langage, écrire du code, installer ou
  exécuter ces moteurs, modifier le brief ou l'ADR.

## Harnais

- **Peut (périmètre) :** écrire `docs/referentiels/moteurs-existants.md` et
  `docs/referentiels/moteurs-existants.csv`, et rien d'autre.
- **Câblé (ne peut pas) :** pas de `main` ; journal en ajout seul.
- **Ne doit pas (écrit) :** inventer une licence, une version, un chiffre de performance ;
  conclure à la place de Pascal.
- **Sources autorisées :** `docs/BRIEF.md`, `docs/adr/0001-moteur-de-simulation.md`,
  `docs/adr/0001-critique-contradicteur.md`, `CLAUDE.md` ; sites officiels, dépôts de code
  source, articles publiés de chaque moteur.

## La grille, pour chaque moteur

1. **Licence** exacte du code (fichier LICENSE du dépôt, version), et compatibilité avec la GPL-3.
2. **Langage**, version courante, date de la dernière version, activité du dépôt, communauté.
3. **Niveau** : arbre à arbre, cohortes par cellule, ou les deux ; résolution de cellule
   possible ; correspondance avec nos deux niveaux (massif, SER ; BRIEF §3).
4. **Processus spatiaux** : dispersion des graines (noyau, distance), lumière et ombrage,
   concurrence, transitions ; correspondance avec BRIEF §6 et §7.
5. **Échelle et performance publiées** : la plus grande surface simulée, la résolution, la
   durée, la machine, le temps de calcul et la mémoire, avec leur source.
6. **Entrées et sorties** : formats (raster, texte, base), et possibilité de les brancher sur
   nos contrats (BRIEF §4 : GeoTIFF, parquet, EPSG:2154).
7. **Paramétrage** : peut-on y injecter nos modèles ajustés sur l'IFN (accroissement,
   mortalité, recrutement) et une hauteur bornée par la potentialité de station (BRIEF §6) ?
   Ou impose-t-il ses propres équations ? Existe-t-il des paramétrages pour des essences ou
   des régions françaises ou européennes ?
8. **Reproductibilité** : graine fixée, mode sans interface, déterminisme en parallèle.
9. **Usage en France** : publications, organismes utilisateurs.

## Journal

- **Ce que l'agent inscrit :** une ligne de journal proposée à l'orchestrateur.

## Valeur provisoire (chiffre, réglage)

- **Valeur provisoire :** aucune.

## Dépend de / rouge attendu jusqu'à

- **Dépend de :** aucune. Branche `claude/youthful-allen-b094t9` (PR #2).
- **CI rouge attendue :** aucune.

## Tests

- **Comment saura-t-on que c'est juste :** chaque cellule du tableau a une source datée ;
  la licence est lue dans le dépôt lui-même ; chaque chiffre de performance a sa
  publication ; la liste de contrôle est passée.

## Terrain

- **Échantillon que Pascal vérifiera :** les trois points au sol que l'agent désigne.

## Qui veille, qui tranche

- **Relecteur :** l'orchestrateur, puis Pascal.
- **Critère d'arrêt de la relecture :** 3 allers-retours.
- **Point de suivi :** au rendu de l'agent.
- **Qui tranche :** Pascal.

## Comment saura-t-on que ça marche ?

Pascal peut décider de l'option G de l'ADR 0001 (réutiliser, adapter, servir de référence
de validation, ou écarter) sans autre recherche.
