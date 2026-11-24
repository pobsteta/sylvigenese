# Mission 015 — lecteur-geotiff-rust

## Mission

**En une phrase (quoi, et pourquoi) :** Écrire dans `simulate/` le lecteur GeoTIFF sans GDAL au profil `contracts/geotiff_profile.json`, qui relit des fichiers d'essai écrits par terra et rasterio et refuse le reste avec le code 2, pour lever le risque principal de l'ADR 0002 côté moteur.

**Redite par l'agent :** _à compléter par l'agent avant d'agir._

## Les trois questions (règle de staffing)

| Question | Réponse | Conséquence |
|---|---|---|
| Peut-il redire la mission en une phrase, avec son but ? | oui | |
| Sait-il comment faire ? | oui | sources nommées ci-dessous |
| A-t-il les moyens ? | oui | outils du conteneur (R 4.3, Rust 1.97, Python 3.13, réseau limité) |

**Temps de la main :** donner. **Degré de la main :** le chef tranche.

## Ma réponse d'abord

_Rempli par Pascal seul._

## L'Homme

- **Agent :** `dev` — **Modèle :** sonnet

## Harnais

- **Peut (périmètre) :** `simulate/src/geotiff.rs`, `simulate/tests/geotiff*.rs`, `simulate/tests/fixtures/`.
- **Câblé (ne peut pas) :** pas de `main` ; pas de « terminé » sans tests verts ; journal en ajout seul.
- **Ne doit pas (écrit) :** dépendre de GDAL ; contourner la règle de lisibilité du Rust ; faire un commit git (l'orchestrateur intègre).
- **Sources autorisées :** contracts/geotiff_profile.json (009), docs/spec.md §9, CLAUDE.md.

## Journal

- **Ce que l'agent inscrit :** une ligne proposée à l'orchestrateur, dans son rendu.

## Valeur provisoire (chiffre, réglage)

- aucune

## Dépend de / rouge attendu jusqu'à

- 009 et 012 ; ordre de fusion : après 012

## Tests

- fichiers terra et rasterio relus ; fichiers hors profil refusés avec le code 2

## Terrain

- **Échantillon que Pascal vérifiera :** au jalon M0, `make validate ZONE=zone_fictive` vert.

## Qui veille, qui tranche

- **Relecteur :** `relecteur`, puis Claude (orchestrateur, par délégation de Pascal).
- **Critère d'arrêt de la relecture :** 3 allers-retours ; au-delà, la décision remonte à Pascal.
- **Qui tranche :** Claude par délégation (pilotage/equipe.md), Pascal peut défaire.

## Comment saura-t-on que ça marche ?

fichiers terra et rasterio relus ; fichiers hors profil refusés avec le code 2.
