"""Toute sortie de M1a passe contracts/validate (CLAUDE.md : un validateur appelé en fin de module).

`--zone ... --require-outputs` est impossible à M1a : il exigerait aussi les sorties de dynamics,
simulate, post et assets (33 fichiers obligatoires). On valide donc chaque contrat de M1a.
"""
import pytest

import helpers as H

# (contrat complet, chemin sous la zone). Les rasters à variante `grille` reçoivent --grid.
CONTRATS = [
    ("prepare.grid", "grid.tif"),
    ("prepare.dtm", "dtm.tif"),
    ("prepare.forest_mask", "forest_mask.tif"),
    ("prepare.ser", "ser.tif"),
    ("prepare.ser_categories", "ser.csv"),
    ("prepare.h0", "h0.tif"),
    ("prepare.chm_date", "chm_date.tif"),
    ("prepare.station_gradients", "station_gradients.tif"),
    ("prepare.station_type", "station_type.tif"),
    ("prepare.station_type_categories", "station_type.csv"),
    ("prepare.site_potential", "site_potential.tif"),
    ("prepare.site_potential_bands", "site_potential.csv"),
    ("prepare.ifn_plots", "ifn/plots.parquet"),
    ("prepare.ifn_trees", "ifn/trees.parquet"),
    ("prepare.ifn_flora", "ifn/flora.parquet"),
    ("prepare.stands", "stands.parquet"),
    ("biomes.vegetation_map", "vegetation_map.tif"),
    ("biomes.vegetation_categories", "vegetation_map.csv"),
]


@pytest.mark.parametrize("contrat,rel", CONTRATS, ids=[c for c, _ in CONTRATS])
def test_sortie_conforme_au_contrat(runs, contrat, rel):
    p = H.ZONE / rel
    assert p.exists(), f"sortie absente : {rel}"
    r = H.validate("--contract", contrat, "--grid", str(H.ZONE / "grid.tif"), str(p))
    assert r.returncode == 0, f"{contrat} : code {r.returncode}\n{r.stderr[-1500:]}"


def test_trees_init_conforme_au_contrat(runs):
    p = H.trees_init_path()
    r = H.validate("--contract", "prepare.trees_init", str(p))
    assert r.returncode == 0, r.stderr[-1500:]


def test_biomes_du_depot_conformes_au_contrat():
    fichiers = sorted((H.ROOT / "biomes").glob("*.yml"))
    assert fichiers, "biomes/*.yml absent"
    r = H.validate("--contract", "biomes.biome", *map(str, fichiers))
    assert r.returncode == 0, r.stderr[-1500:]


def test_mode_zone_ne_signale_aucune_sortie_de_m1a_absente(runs):
    r = H.validate("--zone", str(H.ZONE), "--grid", str(H.ZONE / "grid.tif"))
    # Le code 2 (sorties de M2 et au-delà absentes) est attendu à M1a ; aucun écart de contrat (3).
    assert r.returncode != 3, r.stderr[-1500:]
    manquants = [ln for ln in r.stderr.splitlines()
                 if "obligatoire absent" in ln
                 and any(f"contrat {c}" in ln for c in
                         ("prepare.", "biomes.vegetation", "inputs."))]
    assert not manquants, "\n".join(manquants)
