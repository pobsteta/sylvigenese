# Mission 042 — passage du type de station à 25 m par une règle indépendante de GDAL

## Mission

**En une phrase (quoi, et pourquoi) :** Remplacer le « mode » de GDAL dans `resample_categorical` (`R/prepare_grid.R`) par la règle décidée par Pascal le 25/11/2026 (majorité pondérée par la surface couverte ; à égalité, le pixel qui couvre le centre de la cellule ; chaque cellule à égalité listée au rapport), parce que GDAL 3.11 a changé son mode et fait basculer 50 cellules sur 1 600 selon la version installée (journal, rendu du dev de 039).

## L'Homme

- **Agent :** `dev` — **Modèle :** opus — **Temps de la main :** donner. Mission ouverte après la fusion de M3a (premier pas de M3b).

## Harnais

- **Peut :** `R/prepare_grid.R` et son test ; la ligne de rapport des égalités ; `tests/m3/test_m3_amont.py` étendu à species et d130 ; le regel de `tests/m3/reference/entrees/` et de `nominal.json` par `SYLVIGENESE_M3_FREEZE*` (référence technique, décision du 25/11/2026).
- **Ne doit pas :** relâcher une tolérance ; dépendre de la version de GDAL ou de terra.
- **Câblé :** aucune commande git qui écrit ; tests vérifiés sur une copie `git archive HEAD`.

## Tests

- testthat : un cas à majorité nette, un cas à égalité départagé par le centre et signalé, un cas aux bords ; même sortie quelle que soit la version de GDAL (la règle n'appelle pas `resample(method = "mode")`).
- `test_m3_amont` à l'égalité exacte sur species et d130.
