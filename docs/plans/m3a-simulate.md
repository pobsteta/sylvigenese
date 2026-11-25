# Plan de M3a : le moteur `simulate` au niveau massif (25/11/2026)

> Plan rendu par un `dev` (temps « prendre »), validé par l'orchestrateur par délégation ;
> décisions de Pascal Q1 à Q4 et décisions techniques T1 à T10 au journal du 25/11/2026.
> Les fiches de mission 033 à 039 renvoient ici.

## Le pas annuel (état figé au 1er janvier, mises à jour dans des cases séparées)

1. **Concurrence** : pour chaque arbre, `ba_plot` = Σ π (d130/200)² × 10 000 / 706,858 sur les
   arbres simulés du disque de 15 m (lui compris), `bal` sur les seuls arbres plus gros ;
   voisinage 3 × 3 cellules en ordre fixe ; pas de correction de bord, bords comptés.
2. **Accroissement** : η = intercept + Σ f_v(x_v) + b_ser, splines relues aux nœuds
   (contrat `dynamics_params`, ADR 0004), x borné et compté ; station lue dans
   `station_gradients.tif` (bandes trophic, hydric, bioclim) et `ser.tif` ; recherche
   essence → groupe → `toutes_essences`, sinon code 2 ; `d130 += 2 × exp(η)` ; **en moyenne,
   sans bruit** (Pascal, Q4).
3. **Hauteur** : H_dom de la cellule part de `h0.tif` et s'avance d'un an exactement sur la
   courbe de l'essence de plus forte surface terrière (T5) : Chapman-Richards, ou **Korf pour
   le hêtre 09** (Pascal, Q1), A = `site_potential` (une bande vaut pour toutes les essences,
   sinon table explicite, T4) ; dH ≥ 0. **Chaque arbre garde sa hauteur mesurée comme ancre et
   grandit de sa part de ΔH_dom selon son rang en diamètre** (courbe `relative_height_gam`)
   (Pascal, Q2) ; `simulate` avance aussi la hauteur de la date de vol jusqu'à `t0`.
4. **Mortalité** : p = 1 − exp(−exp(η)) par an ; meurt si u(…, MORT) < p ; écrit une fois
   `dead` l'année de sa mort.
5. **Recrutement** (IFN direct) : λ = exp(η) × 0,0625 ha par cellule et essence candidate
   (les quatre jeux de paramètres, T6), `ba_plot` = la cellule (T7) ; nombre de recrues en
   **arrondi aléatoire** (Pascal, Q4) ; d130 = 7,48 cm, position tirée dans la cellule,
   hauteur = H_dom × f(rel_d), `tree_id = r<cell_id>_<année>_<rang>` ; ajoutées en fin d'année.

## Aléa et identité entre fils (T1)

u = mix(mix(mix(mix(mix(seed) ⊕ année) ⊕ entité) ⊕ essence) ⊕ sorte) >> 11 × 2⁻⁵³ (SplitMix64) ;
essence = code espar packé en u64 ; sortes : 1 MORT, 2 NB_RECRUES, 3 RECRUE_X, 4 RECRUE_Y ;
numéro stable d'arbre (initiaux triés par tree_id ; recrues par somme de préfixes séquentielle).
rayon : fonctions pures en parallèle, aucune somme flottante parallèle, sommes en ordre fixe.
Preuve : SHA-256 des sorties identiques pour T = 1, 2, 3, 4, 7 (même machine).

## Sorties, contrôles, codes

- `sim/trees/year=AAAA/part-00000.parquet` (t0 à t0 + years), `sim/cells/year=AAAA/…`
  (semis : **colonne facultative jusqu'à M5, « semis non simulés »**, Pascal Q3 ; d130_mean
  arithmétique, T8), `sim/run.json` (contrat amendé : sorties de domaine, plafonds, bords,
  cellules mêlées), table de signalements mise en page par `post` (T9), Parquet Snappy (T2).
- Contrôles : NaN, non fini, d130 ≤ 0, h ≤ 0 → code 3 avec message en français ;
  règle |Q| < 1e-9 × max(Q) codée et testée (T10), sans objet en M3a.
- Codes 0 / 1 / 2 / 3 / 4 ; estimation mémoire contre MemAvailable × 0,9 (T3), code 4 avant
  toute écriture ; options de test `--memoire-disponible`, `--inject-nan`.
- Crates figées (`=`) : parquet, arrow-array, arrow-schema 60.2.0, rayon 1.12.0, serde_json,
  sha2 ; licences vérifiées par un test.

## Manques à combler (mission G)

Allométries `hcb` et `cw` (synthétiques et provisoires dans le jeu fictif, `import_tarif` pour
le réel depuis tarif-nemeton) ; courbe de Korf du hêtre (nemeton) ; table essence → bande de
`site_potential` ; bloc `simulate` de `config.yml` (t0, seed, years, level ; sans eux : code 2).
