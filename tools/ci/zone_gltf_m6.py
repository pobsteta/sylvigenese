#!/usr/bin/env python3
"""Construit, pour le glTF-Validator du job m6 (mission 075), les deux zones dont les .glb sont à valider :

  data/m6_gltf_base : le jeu fictif (entrées versionnées de tests/fixtures/zone_fictive), chaîne
                      `prepare biomes trees assets` sans réseau : modèles génériques ;
  data/m6_gltf_a    : le jeu fictif + les exemplaires de la fixture tests/fixtures/exemplars_m6 (`assets` rejoué) :
                      modèles par essence et stade.

C'est la préparation de tests/m6/conftest.py (zone_de_base, zone_a), rejouée telle quelle avec les mêmes aides
(tests/m4/helpers_m4.py, tests/m6/helpers_m6.py). Les tests de m6 effacent leurs zones en fin de session : d'où cette
construction à part. Usage : python3 tools/ci/zone_gltf_m6.py [--nettoyer]   (--nettoyer supprime les deux zones).
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "m4"))
sys.path.insert(0, str(ROOT / "tests" / "m6"))

import helpers_m4 as H  # noqa: E402
import helpers_m6 as M  # noqa: E402

BASE, A = "m6_gltf_base", "m6_gltf_a"
VERSIONNES = ("zone.yml", "README.md", "inputs", "params/allometry.parquet", "params/indicator_values.csv",
              "params/tarif.parquet")  # même liste que tests/m6/conftest.py


def nettoyer() -> None:
    for nom in (BASE, A):
        H.remove_zone_copy(nom)


def construire() -> int:
    nettoyer()
    ancien = H.ZONE
    base = ROOT / "data" / BASE
    for rel in VERSIONNES:
        src, dst = ancien / rel, base / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dst) if src.is_dir() else shutil.copy2(src, dst)
    H.ZONE = base
    r = H.run_make(*H.CHAIN, zone=BASE)
    if r.returncode != 0:
        print((r.stdout + r.stderr)[-2500:], file=sys.stderr)
        return 1
    z = M.build_zone(A)
    if z["proc"].returncode != 0:
        print((z["proc"].stdout + z["proc"].stderr)[-2500:], file=sys.stderr)
        return 1
    for nom in (BASE, A):
        n = len(list((ROOT / "data" / nom / "assets" / "trees").glob("*.glb")))
        print(f"data/{nom} : {n} .glb dans assets/trees")
    return 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--nettoyer"]:
        nettoyer()
        sys.exit(0)
    sys.exit(construire())
