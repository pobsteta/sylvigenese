"""Fiches de cellule `web/cells/<tuile>.json` (contrat `assets.cell_sheet`, spec §1 et §10).

Étape du BRIEF codée : spec §1 (la fiche affiche station, type de végétation, composition,
volume, carbone, mention « provisoire ») ; mission 028, état initial (version 1) ; mission 047,
évolution simulée (version 2, voir `build_cell_sheets_v2` plus bas).

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


NOTES_V2 = [
    "trajectoire technique, non validée écologiquement (décision du 25/11/2026) : toutes les années, t0 compris, "
    "viennent de sim/ (simulate), sans interpolation entre deux années retenues",
    "volume et carbone non calculés : ils viendront de post, mission à part après M4a (décision de Pascal du 25/11/2026)",
    "semis non simulés (jusqu'à M5)",
    "type de végétation : état initial ; les types n'évoluent pas dans simulate",
    "chiffres de chaque année : somme des lignes de sim/cells (tiges de 7,5 cm et plus) ; composition : share = part "
    "des tiges de l'essence ; d130_mean_cm : diamètre moyen pondéré par les tiges",
    "une année sans ligne dans sim/cells : la cellule n'a aucun arbre vivant (tiges et surface terrière nulles, "
    "diamètre moyen et hauteur dominante non définis, null)",
    "h_dom_m : hauteur dominante de sim/cells, jamais corrigée au plafond de la station (h_ceiling_m, "
    "site_potential.tif) ; h0_m : hauteur dominante mesurée (h0.tif), donnée à t0 seulement",
]


def _optional_value(array: np.ndarray, nodata, r: int, c: int) -> float | None:
    v = float(array[r, c])
    if not np.isfinite(v) or (nodata is not None and v == nodata):
        return None
    return v


def build_cell_sheets_v2(zone: Path, rows: dict[tuple[int, int], list[dict]], retained: list[int], t0: int,
                         flags: dict[tuple[int, int], list[dict]], species_table: dict[str, str]
                         ) -> tuple[dict[str, dict], dict, dict[int, np.ndarray]]:
    """Fiches v2 par tuile, comptes, et carte de surface terrière (m2/ha, NaN hors forêt) par année retenue.

    `rows` : lignes de sim/cells des années retenues, par (cell_id, année). Une cellule a sa fiche si elle est
    forestière (un type de végétation), porte une ligne de sim/cells ou un signalement une année retenue.
    Tout chiffre est un recalcul arithmétique de sim/cells ; aucun n'est arrondi ni deviné.
    """
    grid, src = _read(zone / "grid.tif")
    width, height, transform = src.width, src.height, src.transform
    veg, src_veg = _read(zone / "vegetation_map.tif")
    sta, src_sta = _read(zone / "station_type.tif")
    h0, src_h0 = _read(zone / "h0.tif")
    ceiling, src_ceiling = _read(zone / "site_potential.tif")
    for name, s in (("vegetation_map", src_veg), ("station_type", src_sta), ("h0", src_h0),
                    ("site_potential", src_ceiling)):
        if (s.width, s.height, s.transform) != (width, height, transform):
            raise ModuleError(f"{name}.tif n'est pas aligné sur grid.tif")
    vegetation_names = read_categories(zone / "vegetation_map.csv")
    station_names = read_categories(zone / "station_type.csv")
    nodata_veg = src_veg.nodata if src_veg.nodata is not None else -1
    nodata_sta = src_sta.nodata if src_sta.nodata is not None else -1

    outside = sorted({cid for cid, _ in list(rows) + list(flags) if not 0 <= cid < width * height})
    if outside:
        raise ModuleError(f"sim/ : cell_id hors de grid.tif ({len(outside)}, par exemple {outside[0]})")
    unknown = sorted({str(r["species"]) for rs in rows.values() for r in rs} - set(species_table))
    if unknown:
        raise ModuleError(f"sim/cells : essence(s) absente(s) de contracts/species.csv : {', '.join(unknown)}")
    forest = {int(r * width + c) for r, c in zip(*np.nonzero(veg != nodata_veg))}
    wanted = forest | {cid for cid, y in rows} | {cid for cid, y in flags}

    g_maps = {y: np.full((height, width), np.nan) for y in retained}
    for y in retained:
        for cid in forest:
            g_maps[y][divmod(cid, width)] = 0.0
    counts = {"cells": 0, "without_station": 0, "without_vegetation": 0, "without_h0": 0, "without_ceiling": 0}
    tiles: dict[str, list[dict]] = defaultdict(list)
    for cid in sorted(wanted):
        r, c = divmod(cid, width)
        x = transform.c + (c + 0.5) * transform.a
        y = transform.f + (r + 0.5) * transform.e
        vegetation_code, station_code = int(veg[r, c]), int(sta[r, c])
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
        h_ceiling = _optional_value(ceiling, src_ceiling.nodata, r, c)
        counts["without_ceiling"] += h_ceiling is None
        years = []
        for year in retained:
            item = year_entry_v2(rows.get((cid, year), []), year, cid)
            item["flags"] = list(flags.get((cid, year), []))
            if year == t0:
                h0_value = _optional_value(h0, src_h0.nodata, r, c)
                if h0_value is None:
                    counts["without_h0"] += 1
                else:
                    item["h0_m"] = h0_value
            if (cid, year) in rows or cid in forest:
                g_maps[year][r, c] = item["basal_area_m2_ha"]
            years.append(item)
        tile_x, tile_y = int(np.floor(x / TILE_M) * TILE_M), int(np.floor(y / TILE_M) * TILE_M)
        tiles[tile_name(tile_x, tile_y)].append({"cell_id": cid, "x": x, "y": y, "station_type": station_name,
                                                 "vegetation_type": vegetation_name, "h_ceiling_m": h_ceiling,
                                                 "years": years})
        counts["cells"] += 1
    docs = {name: {"schema_version": 2, "tile": name, "source": "sim", "notes": list(NOTES_V2), "cells": cells}
            for name, cells in sorted(tiles.items())}
    return docs, counts, g_maps


def year_entry_v2(rows: list[dict], year: int, cid: int) -> dict:
    """Une année de la fiche v2 depuis les lignes de sim/cells d'une cellule (contrat cell_sheet, year_v2).

    Sans ligne : aucun arbre vivant (tiges et G à 0, d130 moyen et h_dom_m null, composition vide ; contrat
    simulate.cells). Une h_dom_m qui diffère d'une essence à l'autre de la même cellule est refusée : on ne choisit pas.
    """
    rows = sorted(rows, key=lambda r: str(r["species"]))
    stems = sum(float(r["stems_ha"]) for r in rows)
    basal = sum(float(r["basal_area_m2_ha"]) for r in rows)
    weighted = sum(float(r["d130_mean"]) * float(r["stems_ha"]) for r in rows
                   if r["d130_mean"] is not None and float(r["stems_ha"]) > 0)
    heights = {r["h_dom_m"] for r in rows}
    if len(heights) > 1:
        raise ModuleError(f"sim/cells, année {year}, cellule {cid} : h_dom_m diffère d'une essence à l'autre "
                          f"({sorted(map(str, heights))}) ; une seule hauteur dominante par cellule est attendue")
    composition = [{"species": str(r["species"]), "stems_ha": float(r["stems_ha"]),
                    "basal_area_m2_ha": float(r["basal_area_m2_ha"]),
                    "share": float(r["stems_ha"]) / stems if stems > 0 else 0.0} for r in rows]
    h_dom = heights.pop() if heights else None
    return {"year": year, "provisoire": True, "stems_ha": stems, "basal_area_m2_ha": basal,
            "d130_mean_cm": weighted / stems if stems > 0 else None,
            "h_dom_m": None if h_dom is None else float(h_dom),
            "composition": composition, "flags": [], "volume_m3_ha": None, "carbon_t_ha": None}


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
