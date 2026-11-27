# Mission 072 — vue massif godot (M6a, mission F du plan)

## Mission

**En une phrase :** La vue massif Godot (`viewer-massif/`) : arguments `--zone --x --y --year`, lecture de `massif/`, repère (T6), terrain, chargement des `.glb` à l'exécution (T13), arbres en blocs MultiMesh (un par bloc, modèle et niveau, `visibility_range`), strate herbacée et semis autour de la caméra (T8), global uniforms déclarés dans `project.godot`, rendu Compatibility en repli (T14), bandeau de mentions « provisoire », sortie de contrôle `--selftest`.

Référence : [`docs/plans/m6a.md`](../../docs/plans/m6a.md) §3 (ligne F), avec les réponses de Pascal Q1 à Q8 du 26/11/2026 (journal) et la critique du contradicteur intégrée au plan.

## L'Homme

- **Agent :** `afficheur` — **Temps de la main :** donner.

## Harnais

- **Peut :** `viewer-massif/` (scènes, scripts, `export_presets.cfg`, `CREDITS.md`, `addons/gut/` versionné, `README.md`), `docs/referentiels/godot-forest-demo.md` (attribution seulement)
- **Ne doit pas :** lire `sim/` ou du Parquet ; ouvrir une valeur écologique dans un script ; **copier de `godot-forest-demo` autre chose que le shader d'herbe MIT (SimpleGrassTextured, IcterusGames, commit 623212f : avis de copyright gardé, `CREDITS.md`)** ; copier une texture d'herbe dont l'origine n'est pas établie (T8) ; mesurer des images par seconde (M6b) ; inventer une valeur écologique ; trancher une question de sens (la poser dans le compte rendu).
- **Câblé :** aucune commande git qui écrit dans sylvigenese ; disque juste (quelques Go), nettoyer ce qui est créé.

## Tests

- GUT de C verts ; `--headless --import` sans erreur ; `--selftest` à 0
