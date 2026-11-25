"""Module `assets` (spec §2, §9) : modèles glTF, tuiles 3D, fiches de cellule, rasters web.

Étape du BRIEF codée : spec §2 (module `assets`), §9 (formats : glTF 2.0, 3D Tiles 1.1 avec
instanciation, COG, fiche de cellule) et §10 (statut provisoire). Mission 028 : **état
initial**. Si `sim/` est absent, `assets` lit `trees_init/trees.parquet` et l'annonce ; la
lecture de `sim/` (années simulées) n'est pas encore faite et `sim/` présent est une erreur.

Sorties, sous le dossier de la zone :
- `assets/trees/{feuillu,resineux}.gltf` (+ .bin) : modèles génériques provisoires (M6) ;
- `tiles/<année>/tileset.json` (3D Tiles 1.1) et `tiles/<année>/t_<x>_<y>.gltf` (+ .bin),
  une instance par arbre (`EXT_mesh_gpu_instancing`) ; repère : voir `assets_lib/frame.py` ;
- `web/cells/t_<x>_<y>.json` : fiches de cellule (volume et carbone vides, et dits) ;
- `web/rasters/vegetation_map.tif` : COG avec aperçus.

Les sorties sont écrites octet pour octet à l'identique à chaque exécution. Fin de module :
appel du validateur sur chaque contrat `assets.*`.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import numpy as np

from sylvigenese import common
from sylvigenese.common import ModuleError, EXIT_IMPOSSIBLE, EXIT_OK
from sylvigenese.assets_lib import altitude, cog, initial_state, cell_sheets, models, tiles

MARKER = "zone.yml"


def is_fictitious_zone(zone: Path) -> bool:
    """Vrai si `<zone>/zone.yml` dit `fictive: true` (contrat zone_marker) ; les copies en héritent."""
    path = zone / MARKER
    if not path.is_file():
        return False
    content = common.read_config(path)  # YAML simple ; le contrôle des clés est celui du validateur
    return content.get("fictive") is True


def say(message: str) -> None:
    print(f"[assets] {message}", file=sys.stderr)


def ellipsoidal_height(config: dict, zone: Path, trees: dict) -> tuple[np.ndarray, dict]:
    """Hauteur ellipsoïdale du pied de chaque arbre = altitude NGF du MNT + ondulation RAF20.

    Sans grille RAF20 : erreur (spec §9), sauf pour une zone marquée fictive (`zone.yml`,
    `fictive: true`), dont les coordonnées sont synthétiques : l'ondulation y vaut 0, ce qui est
    annoncé et écrit dans les extras. L'exception suit le marqueur, pas le nom de la zone.
    """
    ngf = altitude.read_ngf_altitude(zone / "dtm.tif", trees["x"], trees["y"])
    raf20 = (config.get("external") or {}).get("raf20_grid")
    if raf20:
        n = altitude.raf20_undulation(Path(raf20), trees["x"], trees["y"])
        return ngf + n, {"altitude": "NGF-IGN69 (dtm.tif) + ondulation RAF20", "raf20": str(raf20)}
    if is_fictitious_zone(zone):
        say("ATTENTION : external.raf20_grid absent ; zone marquée fictive (zone.yml) : ondulation RAF20 prise égale à 0 "
             "(hauteur ellipsoïdale = altitude NGF), écrite dans les extras. Ne pas faire ainsi sur une zone réelle.")
        return ngf.copy(), {"altitude": "NGF-IGN69 (dtm.tif) sans conversion : ondulation RAF20 = 0 (zone marquée fictive)", "raf20": None}
    raise ModuleError("external.raf20_grid absent de config.yml : conversion NGF-IGN69 -> hauteur ellipsoïdale "
                       "impossible (spec §9, erreur voulue) ; seule une zone marquée fictive (zone.yml) en est dispensée")


def produce_initial_state(config: dict, zone: Path) -> dict:
    """Écrit toutes les sorties de l'état initial ; rend un résumé (chiffres)."""
    if (zone / "sim").exists():
        raise ModuleError(f"{zone / 'sim'} existe : la lecture des années simulées n'est pas encore faite "
                           "(mission suivante) ; mode « état initial » seulement")
    say(f"mode état initial : sim/ absent, lecture de {zone / 'trees_init' / 'trees.parquet'}")
    trees = initial_state.read_trees(zone)
    groups = initial_state.group_of_each_tree(trees["species"], initial_state.species_groups())
    year, year_origin = initial_state.displayed_year(config, zone)
    say(f"année affichée : {year} ({year_origin})")
    z, altitude_info = ellipsoidal_height(config, zone, trees)

    # 1. tout est lu et construit en mémoire : un refus n'écrit rien (pas de tuile à moitié écrite)
    x_west, y_south = tiles.tile_corner(trees["x"], trees["y"])
    keys = sorted(set(zip(x_west.tolist(), y_south.tolist())))
    built_tiles = []
    for tile_x, tile_y in keys:
        selected = (x_west == tile_x) & (y_south == tile_y)
        subset = {k: v[selected] for k, v in trees.items()}
        built_tiles.append(tiles.build_tile(tile_x, tile_y, subset, z[selected], groups[selected]))
    docs, counts = cell_sheets.build_cell_sheets(zone, trees, year)
    if not (zone / "vegetation_map.tif").is_file():
        raise ModuleError(f"raster introuvable : {zone / 'vegetation_map.tif'} (sortie de biomes)")
    expected_instances = sum(t["n"] for t in built_tiles)
    if expected_instances != len(trees["h"]):
        raise ModuleError(f"{expected_instances} instances prévues pour {len(trees['h'])} arbres de trees_init")

    # 2. écriture
    written_models = models.write_models(zone / "assets" / "trees")
    tiles_dir = zone / "tiles" / str(year)
    if tiles_dir.exists():
        for old in list(tiles_dir.glob("*.gltf")) + list(tiles_dir.glob("*.bin")) + list(tiles_dir.glob("tileset.json")):
            old.unlink()
    tiles_dir.mkdir(parents=True, exist_ok=True)
    for t in built_tiles:
        tiles.write_content(tiles_dir, t, year)
    extras = {**models.GENERIC_EXTRAS, "annee": year, "etat": "initial", "origine_annee": year_origin,
              "source": "trees_init/trees.parquet", "instances": int(len(trees["h"])),
              "repere": "ECEF (EPSG:4978) par le transform de chaque tuile ; repère local est-nord-haut ; contenu glTF Y haut",
              **altitude_info}
    tiles.write_tileset(tiles_dir, built_tiles, year, extras)
    written_sheets = cell_sheets.write_cell_sheets(zone / "web" / "cells", docs)
    cog.write_cog(zone / "vegetation_map.tif", zone / "web" / "rasters" / "vegetation_map.tif")

    written_instances = sum(t["n"] for t in built_tiles)
    if written_instances != len(trees["h"]):
        raise ModuleError(f"{written_instances} instances écrites pour {len(trees['h'])} arbres de trees_init")
    return {"year": year, "trees": int(len(trees["h"])), "tiles": len(built_tiles), "models": len(written_models),
            "sheets": len(written_sheets), "cells": counts, "tiles_dir": tiles_dir}


def validate_outputs(zone: Path, year: int) -> int:
    """Appelle le validateur sur chaque contrat `assets.*` ; rend le pire code (0 si tout conforme)."""
    worst = 0
    batches = [
        ("assets.gltf", sorted((zone / "assets" / "trees").glob("*.gltf")) + sorted((zone / "tiles" / str(year)).glob("*.gltf"))),
        ("assets.tileset", [zone / "tiles" / str(year) / "tileset.json"]),
        ("assets.cell_sheet", sorted((zone / "web" / "cells").glob("*.json"))),
        ("assets.web_raster", [zone / "web" / "rasters" / "vegetation_map.tif"]),
    ]
    for contract, paths in batches:
        code = common.call_validator([contract, *map(str, paths)])
        if code != 0:
            say(f"contrat {contract} : validateur code {code}")
            worst = max(worst, code)
    return worst


def run(config_path: str) -> int:
    try:
        config = common.read_config(config_path)
        code = common.call_validator(["config", str(config_path)])
        if code != 0:
            raise ModuleError(f"config.yml non conforme (validateur, code {code})")
        zone = initial_state.zone_dir(config)
        summary = produce_initial_state(config, zone)
        code = validate_outputs(zone, summary["year"])
        if code != 0:
            raise ModuleError(f"sorties non conformes aux contrats assets.* (validateur, code {code})")
    except ModuleError as error:
        print(f"[assets] erreur : {error}", file=sys.stderr)
        return EXIT_IMPOSSIBLE
    c = summary["cells"]
    say(f"état initial {summary['year']} : {summary['trees']} instances en {summary['tiles']} tuile(s), "
         f"{summary['models']} modèles génériques, {summary['sheets']} fiche(s) de {c['cells']} cellule(s) "
         f"(sans station : {c['without_station']}, sans type de végétation : {c['without_vegetation']}, sans H0 : {c['without_h0']}), "
         "1 COG ; tous les contrats assets.* conformes")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="assets", exit_on_error=False)
    parser.add_argument("--config", default="config.yml", help="chemin de config.yml")
    try:
        options = parser.parse_args(argv)
    except (argparse.ArgumentError, SystemExit):
        return EXIT_IMPOSSIBLE
    return run(options.config)


if __name__ == "__main__":
    sys.exit(main())
