"""Fiches de cellule `web/cells/<tuile>.json` (contrat `assets.cell_sheet`, spec §1 et §10).

Étape du BRIEF codée : spec §1 (la fiche affiche station, type de végétation, composition,
volume, carbone, mention « provisoire ») ; mission 028, état initial.

- Une fiche par tuile 3D (mêmes noms que les tuiles), une entrée par cellule de 25 m qui porte
  au moins un arbre ou un type de végétation.
- `cell_id` = ligne × largeur + colonne dans grid.tif, depuis le coin nord-ouest, à partir de 0.
- Composition : part du nombre d'arbres détectés par essence (en v1 le niveau massif ne
  contient que les arbres détectés, spec §4.6 : les dominés ne sont pas comptés).
- Densité : arbres détectés par hectare. H0 : valeur de `h0.tif` (MNH agrégé).
- Volume et carbone : VIDES (`null`) et dits dans `notes` : ils sont calculés par `post`
  (spec §2), après la simulation. Jamais de valeur par défaut.
- `provisoire` est toujours vrai ici : `crown_area` et d130 sont provisoires (spec §4.3) et la
  hauteur n'est pas encore avancée jusqu'à t0.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import rasterio

from sylvigenese.common import ModuleError
from sylvigenese.assets_lib.tiles import TILE_M, tile_name

NOT_PROVIDED = "non_renseigne"
NOTE_VOLUME = "volume et carbone non calculés : ils viennent de post, après la simulation (état initial)"
NOTE_COMPOSITION = "composition : part du nombre d'arbres détectés sur le MNH ; arbres dominés non comptés (spec §4.6)"
NOTE_PROVISIONAL = "résultat provisoire : surface de houppier et d130 provisoires (spec §4.3) ; hauteur du MNH à la date de vol, non avancée jusqu'à t0"


def read_categories(path: Path) -> dict[int, str]:
    """`value,name` -> {valeur: nom} (catégories codées par leur nom, spec §8)."""
    if not path.is_file():
        raise ModuleError(f"table de catégories introuvable : {path}")
    with open(path, encoding="utf-8", newline="") as f:
        return {int(l["value"]): l["name"] for l in csv.DictReader(f)}


def _read(path: Path) -> tuple[np.ndarray, object]:
    if not path.is_file():
        raise ModuleError(f"raster introuvable : {path} (sortie de prepare ou biomes)")
    with rasterio.open(path) as src:
        return src.read(1), src


def build_cell_sheets(zone: Path, trees: dict[str, np.ndarray], year: int) -> tuple[dict[str, dict], dict]:
    """Fiches par tuile {nom: document} et comptes {cells, without_station, without_vegetation, without_h0}."""
    grid, src = _read(zone / "grid.tif")
    width, height = src.width, src.height
    transform = src.transform
    veg, src_veg = _read(zone / "vegetation_map.tif")
    sta, src_sta = _read(zone / "station_type.tif")
    h0, src_h0 = _read(zone / "h0.tif")
    for name, s in (("vegetation_map", src_veg), ("station_type", src_sta), ("h0", src_h0)):
        if (s.width, s.height, s.transform) != (width, height, transform):
            raise ModuleError(f"{name}.tif n'est pas aligné sur grid.tif")
    vegetation_names = read_categories(zone / "vegetation_map.csv")
    station_names = read_categories(zone / "station_type.csv")

    col = np.floor((trees["x"] - transform.c) / transform.a).astype(int)
    row = np.floor((trees["y"] - transform.f) / transform.e).astype(int)
    outside = (col < 0) | (col >= width) | (row < 0) | (row >= height)
    if outside.any():
        raise ModuleError(f"{int(outside.sum())} arbre(s) hors de la grille grid.tif")
    tree_cell = row * width + col
    by_cell: dict[int, list[str]] = defaultdict(list)
    for cid, species_code in zip(tree_cell.tolist(), trees["species"].tolist()):
        by_cell[cid].append(species_code)

    area_ha = abs(transform.a * transform.e) / 10000.0
    nodata_veg = src_veg.nodata if src_veg.nodata is not None else -1
    nodata_sta = src_sta.nodata if src_sta.nodata is not None else -1
    counts = {"cells": 0, "without_station": 0, "without_vegetation": 0, "without_h0": 0}
    tiles: dict[str, list[dict]] = defaultdict(list)
    for r in range(height):
        for c in range(width):
            cid = r * width + c
            vegetation_code = int(veg[r, c])
            if cid not in by_cell and vegetation_code == nodata_veg:
                continue
            x = transform.c + (c + 0.5) * transform.a
            y = transform.f + (r + 0.5) * transform.e
            station_code = int(sta[r, c])
            if vegetation_code == nodata_veg or vegetation_code not in vegetation_names:
                counts["without_vegetation"] += 1
                vegetation_name = NOT_PROVIDED
            else:
                vegetation_name = vegetation_names[vegetation_code]
            if station_code == nodata_sta or station_code not in station_names:
                counts["without_station"] += 1
                station_name = NOT_PROVIDED
            else:
                station_name = station_names[station_code]
            species_codes = sorted(by_cell.get(cid, []))
            n = len(species_codes)
            composition = [{"species": e, "share": round(species_codes.count(e) / n, 6)} for e in sorted(set(species_codes))]
            notes = [NOTE_COMPOSITION, NOTE_VOLUME, NOTE_PROVISIONAL]
            year_item = {"year": year, "provisoire": True, "composition": composition,
                          "volume_m3_ha": None, "carbon_t_ha": None,
                          "density_trees_ha": round(n / area_ha, 3), "notes": notes}
            h0_value = float(h0[r, c])
            if src_h0.nodata is not None and h0_value == src_h0.nodata:
                counts["without_h0"] += 1
                notes.append("H0 absente (nodata dans h0.tif)")
            else:
                year_item["h0_m"] = round(h0_value, 3)
            tile_x, tile_y = int(np.floor(x / TILE_M) * TILE_M), int(np.floor(y / TILE_M) * TILE_M)
            tiles[tile_name(tile_x, tile_y)].append({"cell_id": cid, "x": x, "y": y, "station_type": station_name,
                                              "vegetation_type": vegetation_name, "years": [year_item]})
            counts["cells"] += 1
    docs = {name: {"schema_version": 1, "tile": name, "cells": cells} for name, cells in sorted(tiles.items())}
    return docs, counts


def write_cell_sheets(directory: Path, docs: dict[str, dict]) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    for old in directory.glob("t_*.json"):
        old.unlink()
    paths = []
    for name, doc in docs.items():
        path = directory / f"{name}.json"
        path.write_text(json.dumps(doc, separators=(",", ":"), ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        paths.append(path)
    return paths
