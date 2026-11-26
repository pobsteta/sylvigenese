# Mission 062 — Régénération par cohortes de semis, aux deux niveaux

## Mission

**En une phrase :** Régénération par cohortes de semis, aux deux niveaux, pour recoloniser les trouées et caler le passage à la futaie sur l'IFN (BRIEF §7, selon Q1 à Q4). Contenu : dispersion par FFT avec zone tampon ; règle \|Q\| appliquée (T3) ; installation, croissance et survie ; passage calé ; colonnes de semis dans `sim/cells`. Sont comprises les notes de la vue : la mention « semis non simulés » ne doit plus être écrite quand `run.json` dit l'inverse. (plan `docs/plans/m5a.md`, mission D ; décisions de Pascal Q1 à Q5 du 26/11/2026).

## L'Homme

- **Agent :** `dev` (Rust) — **Modèle :** opus — **Temps de la main :** donner.

## Harnais

- **Peut :** `simulate/src` (nouveaux `semis.rs` et `dispersion.rs` ; `pas.rs`, `sorties.rs`, `controles.rs`, `alea.rs`, `config.rs`, `entrees.rs`), `simulate/tests/`, `simulate/Cargo.{toml,lock}` (`rustfft`, `realfft` figées), `python/sylvigenese/assets_lib/` (notes seules)
- **Ne doit pas :** coder une valeur écologique ; changer `tests/m3/reference/nominal.json` ; casser l'identité entre fils ; importer `bench/`
- **Câblé :** aucune commande git qui écrit ; tests vérifiés sur une copie `git archive HEAD`.

## Tests

- tests unitaires, dont FFT contre convolution directe à 1e-9 et somme du noyau égale à 1 à 1e-12 ; **une source de coordonnées connues** (est 700 012,5 ; nord 6 500 987,5 ; EPSG:2154) **ensemence les cellules attendues**, avec un cas asymétrique qui détecte une transposition ; SHA-256 identiques de 1 à 7 fils ; `cargo test --locked` et `tests/m3` (mode `ifn_direct`) verts

## Précisions de l'orchestrateur (rendu de 060, 26/11/2026)

- Le mode s'appelle `simulate.recruitment` (`ifn_direct` | `cohorts`) ; le bloc de réglages s'appelle `regeneration`.
- `simulate` s'arrête en code 2, avec un message, si `simulate.recruitment` est absent (le schéma ne l'exige pas, pour rester rétrocompatible).
- `config.yml` passe à `cohorts` avec cette mission, sous réserve que `tests/m3` reste jugé en `ifn_direct` (référence de M3a).
