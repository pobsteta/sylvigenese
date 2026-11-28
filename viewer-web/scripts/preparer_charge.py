"""Prépare la zone de charge synthétique `data/m4_charge/` (100 013 puis 100 000 arbres) pour le relevé des images
par seconde sur carte graphique (mission 088, BRIEF §11, critère b de M4).

Elle rejoue exactement ce que fait la fixture `charge` des tests de m4 (tests/m4/conftest.py) : mêmes aides
(`tests/m4/helpers_m4*.py`, importées sans les modifier), même zone, mêmes années. Seule différence : la zone n'est
PAS effacée à la fin, pour que le navigateur la serve. Zone fictive, aucune valeur écologique.

Prérequis : les sorties de `make prepare biomes trees` sur tests/fixtures/zone_fictive (elles y sont après
`bash tools/ci/run_tests.sh m4`) ; sinon le script s'arrête en le disant.
Usage : python3 viewer-web/scripts/preparer_charge.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "m4"))

import helpers_m4 as H  # noqa: E402
import helpers_m4_temps as T  # noqa: E402


def main() -> int:
    manquants = [f for f in ("vegetation_map.tif", "stand_map.tif", "station_type.tif", "h0.tif", "stands.parquet",
                             "trees_init/trees.parquet") if not (H.ZONE / f).exists()]
    if manquants:
        print(f"Sorties de la chaîne absentes de {H.ZONE} ({', '.join(manquants)}) : lancer d'abord "
              "`make prepare biomes trees` sur le jeu fictif.", file=sys.stderr)
        return 2
    zdir, _ = H.clone_zone(T.CHARGE)
    cfg = T.write_config(zdir, T.CHARGE, {"level": "massif", "seed": 42, "t0": 2022, "years": 1, "threads": 1,
                                         "recruitment": "ifn_direct"}, {"year_step": T.STEP}, "config_m4_charge.yml")
    T.build_charge_sim(zdir, cfg, sorted(H.Oracle(H.ZONE).forest_cells()))
    p = H.run_assets(cfg)
    if p.returncode != 0:
        print("assets en échec sur la zone de charge :\n" + T.queue(p), file=sys.stderr)
        return 2
    print(f"Zone de charge prête : {zdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
