"""M3a, non-régression (spec §11) : empreinte de VALEURS de `simulate` (graine 42, 100 ans, 1 fil), figée dans
tests/m3/reference/nominal.json : référence technique, non validée écologiquement (décision de Pascal du
25/11/2026 ; vraisemblance traitée en M3b). La figer est une décision, pas un réflexe. Tant que le fichier est
absent, le test échoue en le disant.

Ce test ne juge QUE le moteur : `simulate` est rejoué sur des ENTRÉES FIGÉES, versionnées sous
tests/m3/reference/entrees/ (sorties de prepare, biomes, trees et dynamics sur le jeu fictif, voir le MANIFEST.json
qui en donne les empreintes et l'environnement qui les a produites). Raison (25/11/2026) : l'état initial produit
par la chaîne R dépend de la plateforme. GDAL 3.11 a changé le rééchantillonnage « mode » (pondéré par la surface
couverte) ; station_type.tif passe de 20 m à 25 m par ce mode dans prepare (R/prepare_grid.R) ; 50 cellules sur
1600 changent de type de station entre GDAL 3.8.4 et 3.12.2, donc de biome, donc l'essence d'arbres hors polygone,
donc leur d130. La chaîne entière jugée ici mêlait ce défaut amont au moteur. La stabilité amont est testée à part
(test_m3_amont.py).

Les ressources versionnées ailleurs ne sont pas recopiées (un lien plutôt qu'une copie) : params/allometry.parquet
et zone.yml viennent de tests/fixtures/zone_fictive, contracts/species.csv du dépôt.

Pour figer l'empreinte (référence technique, décision de Pascal du 25/11/2026) :
    SYLVIGENESE_M3_FREEZE=1 python3 -m pytest tests/m3/test_m3_non_regression.py
Pour figer de nouveau les entrées depuis la chaîne nominale (décision, comme l'empreinte ; dire l'environnement) :
    SYLVIGENESE_M3_FREEZE_ENTREES=1 python3 -m pytest tests/m3/test_m3_non_regression.py"""
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

import helpers_m3 as H

REF = Path(__file__).parent / "reference" / "nominal.json"
ENTREES = Path(__file__).parent / "reference" / "entrees"
MANIFEST = ENTREES / "MANIFEST.json"
ZONE_NR = "m3_non_regression"
T0 = H.SIM_NOMINAL["t0"]
ANNEES = (T0, T0 + 1, T0 + 10, T0 + 50, T0 + 100)
STATUT = ("référence technique, non validée écologiquement (décision de Pascal du 25/11/2026 ; "
          "vraisemblance traitée en M3b)")

# Ce que `simulate` lit dans la zone et que la chaîne R PRODUIT (donc ce qui dépend de la plateforme) : figé.
FICHIERS_FIGES = ("grid.tif", "h0.tif", "chm_date.tif", "site_potential.tif", "station_gradients.tif", "ser.tif",
                  "ser.csv", "trees_init/trees.parquet", "params/growth.parquet", "params/mortality.parquet",
                  "params/recruitment.parquet", "params/height_curve.parquet")
# Ce que `simulate` lit et qui est déjà versionné dans le jeu fictif : pris à la source.
FICHIERS_VERSIONNES = ("params/allometry.parquet", "zone.yml")


def empreinte(zdir):
    out = {"annees": {}}
    for y in ANNEES:
        t = H.read_year(zdir, "trees", y)
        vivants = t.where(t["status"] == "alive")
        c = H.read_year(zdir, "cells", y)
        out["annees"][str(y)] = {
            "lignes": int(len(t)), "vivants": int(len(vivants)), "morts": int((t["status"] == "dead").sum()),
            "recrues": int(H.commence_par(t["tree_id"], "r").sum()),
            "somme_d130": float(vivants["d130"].sum()), "somme_h": float(vivants["h"].sum()),
            "somme_x": float(vivants["x"].sum()), "somme_y": float(vivants["y"].sum()),
            "g_total_m2_ha": float(c["basal_area_m2_ha"].sum()), "stems_total_ha": float(c["stems_ha"].sum()),
            "lignes_cellules": int(len(c)),
        }
    j = H.read_run_json(zdir)
    out["run"] = {k: j[k] for k in ("seed", "t0", "years", "zeroed_values", "provisional_share", "domain_outputs",
                                    "cells_at_height_ceiling", "edge_disks", "mixed_cells", "recruits", "deaths")}
    return out


def _egal(a, b, chemin=""):
    if isinstance(a, dict):
        assert set(a) == set(b), f"{chemin} : clés différentes {set(a) ^ set(b)}"
        for k in a:
            _egal(a[k], b[k], f"{chemin}/{k}")
    elif isinstance(a, float) or isinstance(b, float):
        assert a == pytest.approx(b, rel=1e-9, abs=1e-9), f"{chemin} : référence {a!r}, obtenu {b!r}"
    else:
        assert a == b, f"{chemin} : référence {a!r}, obtenu {b!r}"


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _environnement_r() -> dict:
    """Versions de R et des bibliothèques qui ont produit les entrées (pour le MANIFEST)."""
    code = ('v <- c(R = R.version.string, terra = as.character(packageVersion("terra")), '
            'sf = as.character(packageVersion("sf")), arrow = as.character(packageVersion("arrow")), '
            'terra::gdal(lib = "all")); cat(paste(names(v), v, sep = "=", collapse = "\\n"))')
    res = subprocess.run(["Rscript", "-e", code], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    return dict(l.split("=", 1) for l in res.stdout.splitlines() if "=" in l)


def _figer_entrees(src: Path) -> None:
    if ENTREES.exists():
        shutil.rmtree(ENTREES)
    for rel in FICHIERS_FIGES:
        (ENTREES / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src / rel, ENTREES / rel)
    manifest = {
        "objet": "entrées de simulate figées pour la non-régression du moteur (tests/m3/test_m3_non_regression.py)",
        "produites_par": "make prepare biomes trees dynamics sur une copie de tests/fixtures/zone_fictive (chaîne de tests/m3)",
        "statut": STATUT,
        "environnement": _environnement_r(),
        "fichiers": {rel: sha256(ENTREES / rel) for rel in FICHIERS_FIGES},
    }
    MANIFEST.write_text(json.dumps(manifest, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


@pytest.fixture(scope="module")
def moteur_sur_entrees_figees(request):
    """Zone data/m3_non_regression bâtie des seules entrées figées (et des fichiers versionnés du jeu fictif),
    puis `simulate` seul, avec la configuration nominale (graine 42, 100 ans, 1 fil)."""
    if os.environ.get("SYLVIGENESE_M3_FREEZE_ENTREES") == "1":
        _figer_entrees(request.getfixturevalue("chaine")["dir"])
    H.remove_zone(ZONE_NR)
    zdir = H.zone_dir(ZONE_NR)
    zdir.mkdir(parents=True)
    for rel in FICHIERS_FIGES:
        assert (ENTREES / rel).is_file(), f"entrée figée absente : {ENTREES / rel}"
        (zdir / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ENTREES / rel, zdir / rel)
    for rel in FICHIERS_VERSIONNES:
        (zdir / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(H.FIXTURE / rel, zdir / rel)
    cfg = H.write_config(zdir, ZONE_NR, dict(H.SIM_NOMINAL))
    proc = H.run_simulate(ZONE_NR, cfg)
    yield {"dir": zdir, "proc": proc}
    H.remove_zone(ZONE_NR)


def test_les_entrees_figees_sont_celles_du_manifest(moteur_sur_entrees_figees):
    """Une entrée figée ne change pas sans qu'on le voie : chaque fichier a l'empreinte du MANIFEST, et le MANIFEST
    ne liste que les fichiers figés (ni plus, ni moins). (La fixture passe d'abord : en mode gel, elle écrit les
    entrées et le MANIFEST.)"""
    assert MANIFEST.is_file(), f"{MANIFEST} absent : figer les entrées avec SYLVIGENESE_M3_FREEZE_ENTREES=1"
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert set(m["fichiers"]) == set(FICHIERS_FIGES)
    for rel, attendu in m["fichiers"].items():
        assert sha256(ENTREES / rel) == attendu, f"{rel} : empreinte différente du MANIFEST"


def test_le_moteur_redonne_l_empreinte_figee(moteur_sur_entrees_figees):
    r = moteur_sur_entrees_figees
    assert r["proc"].returncode == 0, H.queue(r["proc"])
    emp = empreinte(r["dir"])
    if os.environ.get("SYLVIGENESE_M3_FREEZE") == "1":
        REF.parent.mkdir(exist_ok=True)
        REF.write_text(json.dumps(emp, indent=1, sort_keys=True), encoding="utf-8")
    assert REF.is_file(), ("empreinte de non-régression absente (tests/m3/reference/nominal.json) : à figer avec "
                           "SYLVIGENESE_M3_FREEZE=1 ; référence technique, non validée écologiquement (décision de "
                           "Pascal du 25/11/2026 ; vraisemblance traitée en M3b)")
    _egal(json.loads(REF.read_text(encoding="utf-8")), json.loads(json.dumps(emp)))
