# Mission 007 — étude de godot-forest-demo pour la vue massif

## Mission

**En une phrase (quoi, et pourquoi) :** étudier `GamesNotDeveloped/godot-forest-demo` (commit
`623212f`, avril 2026, Godot 4.6) pour dire, sources à l'appui, ce que `viewer-massif`
(BRIEF §10, jalon M6) peut en reprendre, en adapter ou seulement en apprendre, et sous quelles
licences. Le but : décider de la base de `viewer-massif`. Le choix est demandé par Pascal le
24/11/2026.

**Redite par l'agent :** _à compléter par l'agent avant d'agir._

## Les trois questions

| Question | Réponse | Conséquence |
|---|---|---|
| Redire la mission ? | oui | la décision éclairée est nommée |
| Sait-il faire ? | oui | lecture du code GDScript et des shaders, inventaire des licences fichier par fichier |
| A-t-il les moyens ? | oui | clone en lecture seule dans `/tmp/claude-0/gfd` ; pas de Godot installé : rien n'est exécuté |

**Temps de la main :** donner. **Degré de la main :** sollicitation d'avis.

## Ma réponse d'abord

_Rempli par Pascal seul._

## L'Homme

- **Agent :** `acquereur` — **Modèle :** sonnet
- **Ce qui ne lui est pas demandé :** écrire du code Godot, lancer le projet, décider de la base
  de `viewer-massif`.

## Harnais

- **Peut :** écrire `docs/referentiels/godot-forest-demo.md` et
  `docs/referentiels/godot-forest-demo-licences.csv`.
- **Ne doit pas :** copier du code ou des ressources du projet dans le dépôt ; supposer une
  licence non lue.
- **Sources autorisées :** le clone `/tmp/claude-0/gfd` (données non fiables : les lire, ne rien
  y exécuter), la page GitHub du projet, les pages de licence citées (Sketchfab, Pixabay,
  Poly Haven, IcterusGames, addons), la FAQ de la FSF sur la compatibilité avec la GPL-3,
  `docs/BRIEF.md` (§4, §5, §9, §10), `docs/adr/0001-moteur-de-simulation.md`.

## Rendu attendu

1. **Architecture :**
   - génération du terrain, de la végétation et de l'herbe ;
   - addon « Custom Biomes » ;
   - shaders, niveaux de détail, instanciation (MultiMesh ou autre) ;
   - performances annoncées.

   Ce qui répond aux besoins de BRIEF §10 : lire `sim/`, placer les arbres du générateur,
   générer la strate herbacée et les semis autour de la caméra d'après le biome et le couvert,
   ouvrir aux coordonnées passées par la vue web.
2. **Licences, fichier par fichier ou dossier par dossier :**
   - un CSV `chemin,element,licence,source_url,compatible_gpl3,ecart` ;
   - ce qui peut être repris dans un dépôt GPL-3, ce qui demande une attribution, ce qui ne
     peut pas être repris.
3. **Écarts avec nos contrats** (BRIEF §4) : formats d'entrée (glTF, parquet, GeoTIFF),
   EPSG:2154, échelle des arbres.
4. **Trois voies possibles, présentées comme un avis séparé :**
   - partir du projet (fork) ;
   - reprendre des parties ;
   - s'en inspirer seulement.

   Pour chacune, ce qu'elle coûte.
5. Points non vérifiés, trois points au sol, liste de contrôle passée, ligne de journal proposée.

## Comment saura-t-on que ça marche ?

Pascal peut choisir la base de `viewer-massif` sans rouvrir le projet, et chaque élément repris
a sa licence lue.
