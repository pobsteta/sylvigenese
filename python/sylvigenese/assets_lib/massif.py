"""Bloc massif : `massif/index.json` et `massif/<année>/<bloc>.json` (version 2), lus par la vue Godot.

Étape du BRIEF codée : §10 (la vue massif lit les résultats de `sim/`, par `assets` ; terrain, arbres, couverts
de la strate herbacée et semis autour de la caméra) ; plan `docs/plans/m6a.md` §4 (contrats), T5 (disposition),
T6 (repères), T8 (herbe et semis), T11 (stade d'un arbre) ; ADR 0007 choix 7 ; décisions de Pascal Q3, Q4, Q8.
Mission 070. Contrats `assets.massif_block` (version 2) et `assets.massif_index`.

Ce que contient un bloc (une tuile de 500 m de `tiles/`, même identifiant `t_<x>_<y>`) :
- `origin` : coin sud-ouest du bloc (EPSG:2154) et altitude NGF-IGN69 entière sous le point le plus bas du terrain
  du bloc ; `trees[]` : position RELATIVE à l'origine (x est, y nord, z haut ; ce n'est ni le repère de glTF ni
  celui de Godot : la vue convertit, T6) ; z = altitude NGF du pied (celle de `altitude.py`, bilinéaire sur le MNT
  de la grille) moins `origin.z` ; `stage` = h / h_pot de l'arbre (`stages.py`) ;
- `ground` : l'altitude NGF absolue aux centres des cellules de 25 m, ligne 0 au nord ; un nœud sans valeur (nodata
  ou hors de la grille) prend la valeur du nœud valide le plus proche, et le bloc le DIT (mentions) ;
- `cells[]` : une par cellule de la grille dans le bloc : biome (carte de végétation), couverts `herb_cover` et
  `shrub_cover` lus dans `biomes/*.yml`, `seedlings[]` d'après `sim/cells` en mode `cohorts` seulement.
  Une cellule sans biome porte `null` (jamais un couvert par défaut) ;
- `mentions[]` : provisoire, non validée écologiquement, jeu fictif, semis, modèles génériques employés.

Les arbres sont ceux de `sim/trees` (vivants, années retenues) ou de `trees_init/` (état initial). Un arbre de
`trees_init` n'a pas de hauteur de base du houppier (hcb) : le contrat v2 admet null, null est écrit (jamais 0) et
le bloc compte ces arbres dans ses mentions ; la vue ne s'en sert pas pour dessiner (le modèle porte sa base de
houppier).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import rasterio
import yaml

from sylvigenese.common import ModuleError
from sylvigenese.assets_lib import altitude, cell_sheets, initial_state, sim_state, tiles

CELL_M = 25.0
MENTION_INITIAL = ("état initial (trees_init) : photographie des arbres détectés, non validée écologiquement ; "
                   "hauteur du MNH non avancée jusqu'à t0")
MENTION_SIM = "trajectoire technique, non validée écologiquement (décision du 25/11/2026) ; années de sim/, sans interpolation"
MENTION_HCB = ("hcb absent de trees_init : {n} arbre(s) sans hauteur de base de houppier, hcb écrit null (jamais 0), "
               "non utilisé pour dessiner (le modèle porte sa base de houppier)")
MENTION_STAGE = ("stade de l'arbre = h / h_pot de l'arbre avec les seuils de biomes/stades/stage_breaks.yml, provisoires "
                 "(extension de BRIEF §6, décision de Pascal Q8 du 26/11/2026)")
MENTION_GROUND = ("terrain : MNT de la grille de 25 m, lissé, pas le LiDAR à 1 m ; le pied d'un arbre est posé à moins de "
                  "quelques décimètres de ce sol")
MENTION_MODELS = ("arbres dessinés par les modèles synthétiques du générateur de tarif-nemeton (provisoires, ne valident "
                  "aucun tarif) ; feuillage en cartes à couleur unie, illustration (Q2)")
MENTION_NO_EXEMPLARS = ("aucun exemplaire du générateur de tarif-nemeton lu (assets.models.exemplars_dir absent) : tous les "
                        "arbres sont dessinés par les modèles génériques feuillu et résineux, provisoires (Q3)")
MENTION_SEEDLINGS_COHORTS = ("semis : stock initial déduit des modèles (Q2 de M5a), survie par la lumière et l'ombre "
                             "seules (Q3 de M5a), voir sim/flags.parquet ; herbe et semis dessinés autour de la caméra, "
                             "apparence en constantes d'affichage provisoires (Q4)")


def write_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def read_biomes(directory: Path | None = None) -> dict[str, dict]:
    """Catalogue `biomes/*.yml` : {id: {provisoire, herb_cover, shrub_cover}} ; un couvert absent vaut None."""
    directory = Path(directory) if directory else initial_state.ROOT / "biomes"
    catalog = {}
    for path in sorted(directory.glob("*.yml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(doc, dict) or "id" not in doc:
            raise ModuleError(f"{path} : un biome (clé id) est attendu")
        strata = doc.get("strates") or {}
        cover = {}
        for key, name in (("herbacee", "herb_cover"), ("arbustive", "shrub_cover")):
            value = (strata.get(key) or {}).get("couvert")
            if value is not None and not (isinstance(value, (int, float)) and not isinstance(value, bool)
                                          and 0 <= value <= 1):
                raise ModuleError(f"{path} : couvert {key} = {value!r} : un nombre de 0 à 1 est attendu")
            cover[name] = None if value is None else float(value)
        catalog[str(doc["id"])] = {"provisoire": bool(doc.get("provisoire", True)), **cover}
    if not catalog:
        raise ModuleError(f"aucun biome dans {directory}")
    return catalog


def _nearest_fill(values: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Remplace chaque nœud invalide par le nœud valide le plus proche (distance en nœuds, égalité : ordre des
    lignes puis des colonnes)."""
    if not valid.any():
        raise ModuleError("terrain du bloc : aucun nœud du MNT n'est valide, rien ne peut être écrit")
    rows, cols = np.nonzero(valid)
    out = values.copy()
    for r, c in zip(*np.nonzero(~valid)):
        d = (rows - r) ** 2 + (cols - c) ** 2
        k = int(np.argmin(d))
        out[r, c] = values[rows[k], cols[k]]
    return out


class MassifWriter:
    """Écrit `massif/` année par année (une année en mémoire à la fois), puis l'index."""

    def __init__(self, out: Path, zone: Path, *, zone_name: str, source: str, run: dict | None, registry,
                 fictive: bool):
        self.out, self.zone, self.source, self.zone_name = Path(out), Path(zone), source, zone_name
        self.run, self.registry, self.fictive = run, registry, fictive
        self.cohorts = bool(run) and run.get("recruitment") == "cohorts"
        self.recruitment = None
        if source == "sim":
            self.recruitment = "cohorts" if self.cohorts else "ifn_direct"
        self.biomes = read_biomes()
        self._read_grids()
        self._static: dict[str, dict] = {}
        self.years: list[dict] = []
        self._seedlings: dict[int, dict] = {}
        self.species_stems: dict[str, set[str]] = {}
        self.fallbacks: dict[str, set[str]] = {}
        self.without_hcb = 0

    # ------------------------------------------------------------------ grilles
    def _read_grids(self) -> None:
        zone = self.zone
        with rasterio.open(zone / "dtm.tif") as src:
            if src.crs is None or src.crs.to_epsg() != 2154:
                raise ModuleError(f"{zone / 'dtm.tif'} : EPSG:2154 attendu")
            self.transform, self.width, self.height = src.transform, src.width, src.height
            self.dtm = src.read(1, masked=False).astype("float64")
            self.dtm_nodata = src.nodata
        if abs(self.transform.a - CELL_M) > 1e-9 or abs(self.transform.e + CELL_M) > 1e-9:
            raise ModuleError(f"dtm.tif : maille de {self.transform.a} m, la vue massif attend 25 m (ADR 0001)")
        with rasterio.open(zone / "vegetation_map.tif") as src:
            if (src.width, src.height, src.transform) != (self.width, self.height, self.transform):
                raise ModuleError("vegetation_map.tif n'est pas aligné sur dtm.tif")
            self.vegetation = src.read(1)
            self.vegetation_nodata = src.nodata if src.nodata is not None else -1
        names = cell_sheets.read_categories(zone / "vegetation_map.csv")
        unknown = sorted(set(names.values()) - set(self.biomes))
        if unknown:
            raise ModuleError(f"vegetation_map.csv : biome(s) absent(s) de biomes/*.yml : {', '.join(unknown)}")
        self.vegetation_names = names

    # ------------------------------------------------------------------ partie fixe d'un bloc
    def static(self, name: str) -> dict:
        """Origine, terrain et cellules d'un bloc (identiques toutes les années)."""
        if name in self._static:
            return self._static[name]
        _, x_text, y_text = name.split("_")
        x_sw, y_sw = int(x_text), int(y_text)
        size = tiles.TILE_M
        n = int(size / CELL_M)
        col_left, row_top = (x_sw - self.transform.c) / CELL_M, (self.transform.f - (y_sw + size)) / CELL_M
        if abs(col_left - round(col_left)) > 1e-6 or abs(row_top - round(row_top)) > 1e-6:
            raise ModuleError(f"bloc {name} : la grille de 25 m n'est pas alignée sur le coin du bloc ; la vue massif "
                              "ne sait pas décaler ses nœuds")
        col_left, row_top = int(round(col_left)), int(round(row_top))
        rows, cols = np.mgrid[0:n, 0:n]
        grid_rows, grid_cols = rows + row_top, cols + col_left
        inside = (grid_rows >= 0) & (grid_rows < self.height) & (grid_cols >= 0) & (grid_cols < self.width)
        values = np.zeros((n, n))
        valid = inside.copy()
        values[inside] = self.dtm[grid_rows[inside], grid_cols[inside]]
        if self.dtm_nodata is not None:
            valid &= values != self.dtm_nodata
        valid &= np.isfinite(values)
        outside_count, nodata_count = int((~inside).sum()), int((inside & ~valid).sum())
        ground = _nearest_fill(values, valid)
        z0 = float(math.floor(float(ground.min())))
        cells = []
        for r, c in zip(*np.nonzero(inside)):
            gr, gc = int(grid_rows[r, c]), int(grid_cols[r, c])
            code = int(self.vegetation[gr, gc])
            biome = None if code == self.vegetation_nodata or code not in self.vegetation_names \
                else self.vegetation_names[code]
            info = self.biomes[biome] if biome else {"provisoire": True, "herb_cover": None, "shrub_cover": None}
            cells.append({"cell_id": gr * self.width + gc, "x": (int(c) + 0.5) * CELL_M,
                          "y": size - (int(r) + 0.5) * CELL_M, "biome": biome, "biome_provisoire": info["provisoire"],
                          "herb_cover": info["herb_cover"], "shrub_cover": info["shrub_cover"]})
        mentions = []
        if outside_count or nodata_count:
            mentions.append(f"terrain : {outside_count} nœud(s) hors de la grille et {nodata_count} sans valeur du MNT "
                            "ont pris l'altitude du nœud valide le plus proche (pas une mesure)")
        self._static[name] = {"sw": (x_sw, y_sw), "z0": z0, "ground": [round(float(v), 3) for v in ground.reshape(-1)],
                              "n": n, "cells": cells, "mentions": mentions}
        return self._static[name]

    # ------------------------------------------------------------------ une année
    def _write_block(self, name: str, year: int, items: list[dict], kinds: dict) -> dict:
        static = self.static(name)
        x_sw, y_sw = static["sw"]
        cells = [dict(c) for c in static["cells"]]
        if self.cohorts:
            for c in cells:
                c["seedlings"] = self._seedlings[year].get(c["cell_id"], [])
        mentions = self.common_mentions() + static["mentions"]
        without_hcb = sum(1 for item in items if item["hcb"] is None)
        if without_hcb:
            mentions.append(MENTION_HCB.format(n=without_hcb))
        if kinds["generic"]:
            mentions.append(f"{kinds['generic']} arbre(s) de ce bloc dessiné(s) par un modèle générique "
                            "(essence ou stade sans exemplaire du générateur, Q3), pas par un emprunt à une autre essence")
        else:
            mentions.append("aucun arbre de ce bloc dessiné par un modèle générique (pas d'emprunt à une autre essence, Q3)")
        doc = {"schema_version": 2, "block_id": name, "year": year, "crs": "EPSG:2154", "vertical_datum": "NGF-IGN69",
               "origin": {"x": float(x_sw), "y": float(y_sw), "z": static["z0"]}, "trees": items,
               "ground": {"resolution_m": 25, "nx": static["n"], "ny": static["n"], "z": static["ground"]},
               "cells": cells, "seedlings_simulated": self.cohorts, "mentions": mentions, "provisoire": True}
        write_json(self.out / "massif" / str(year) / f"{name}.json", doc)
        return {"block_id": name, "file": f"{year}/{name}.json", "sw": {"x": float(x_sw), "y": float(y_sw)},
                "size_m": tiles.TILE_M, "trees": len(items)}

    def add_year(self, year: int, trees: dict, stages: np.ndarray, stems: np.ndarray, kinds: np.ndarray) -> dict:
        """Écrit les blocs d'une année qui portent des arbres (les blocs vides sont écrits par `finish`).

        `trees` : tableaux tree_id, species, x, y, d130, h, hcb (ou None), cw ; `stages`, `stems`, `kinds` : stade,
        nom du modèle et genre (`own`, `alias`, `generic`) de chaque arbre."""
        x_west, y_south = tiles.tile_corner(trees["x"], trees["y"])
        names = np.array([tiles.tile_name(int(a), int(b)) for a, b in zip(x_west, y_south)], dtype=object)
        z_ngf = altitude.read_ngf_altitude(self.zone / "dtm.tif", trees["x"], trees["y"])
        self._seedlings[year] = sim_state.read_seedlings(self.zone, year) if self.cohorts else {}
        for code, stem in {(c, s) for c, s in zip(trees["species"].tolist(), stems.tolist())}:
            self.species_stems.setdefault(code, set()).add(stem)
        for code, stage in {(c, g) for c, g, k in zip(trees["species"].tolist(), stages.tolist(), kinds.tolist())
                            if k == "generic"}:
            if self.registry.species[code].essence:
                self.fallbacks.setdefault(code, set()).add(stage)
        blocks, by_kind = [], {"own": 0, "alias": 0, "generic": 0}
        for name in sorted(set(names.tolist())):
            static = self.static(name)
            x_sw, y_sw = static["sw"]
            selected = np.nonzero(names == name)[0]
            selected = selected[np.argsort(trees["tree_id"][selected], kind="stable")]
            items = [{"tree_id": str(trees["tree_id"][i]), "species": str(trees["species"][i]), "stage": str(stages[i]),
                      "x": round(float(trees["x"][i] - x_sw), 3), "y": round(float(trees["y"][i] - y_sw), 3),
                      "z": round(float(z_ngf[i] - static["z0"]), 3), "h": round(float(trees["h"][i]), 3),
                      "d130": round(float(trees["d130"][i]), 3),
                      "hcb": None if trees["hcb"] is None else round(float(trees["hcb"][i]), 3),
                      "cw": round(float(trees["cw"][i]), 3)} for i in selected]
            counts = {k: int((kinds[selected] == k).sum()) for k in by_kind}
            for k, v in counts.items():
                by_kind[k] += v
            blocks.append(self._write_block(name, year, items, counts))
        total = int(len(trees["x"]))
        if trees["hcb"] is None:
            self.without_hcb += total
        if sum(b["trees"] for b in blocks) != total or sum(by_kind.values()) != total:
            raise ModuleError(f"{year} : {sum(b['trees'] for b in blocks)} arbres dans les blocs pour {total} arbres vivants")
        self.years.append({"year": year, "trees": total, "trees_by_kind": by_kind, "blocks": blocks})
        return self.years[-1]

    def common_mentions(self) -> list[str]:
        mentions = [MENTION_SIM if self.source == "sim" else MENTION_INITIAL, MENTION_STAGE, MENTION_GROUND,
                    MENTION_MODELS if self.registry.exemplars else MENTION_NO_EXEMPLARS]
        if self.fictive:
            mentions.insert(1, "jeu fictif : coordonnées et valeurs inventées, aucune source réelle")
        if self.cohorts:
            mentions.append(cell_sheets.seedling_note(self.run))
            mentions.append(MENTION_SEEDLINGS_COHORTS)
        else:
            mentions.append(cell_sheets.NOTES_V2[2])
        return mentions

    # ------------------------------------------------------------------ index
    def finish(self, tile_names: list[str]) -> dict:
        """Écrit les blocs vides manquants (même liste de tuiles chaque année que `tiles/index.json`), puis
        `massif/index.json` ; rend un résumé."""
        tile_names = sorted(tile_names)
        for entry in self.years:
            present = {b["block_id"] for b in entry["blocks"]}
            stray = sorted(present - set(tile_names))
            if stray:
                raise ModuleError(f"{entry['year']} : bloc(s) {', '.join(stray[:3])} hors de la liste des tuiles")
            empty = {"own": 0, "alias": 0, "generic": 0}
            for name in sorted(set(tile_names) - present):
                entry["blocks"].append(self._write_block(name, entry["year"], [], empty))
            entry["blocks"].sort(key=lambda b: b["block_id"])
        species = self.registry.species
        models = []
        notes = self.common_mentions()
        for code in sorted(self.species_stems):
            stems = self.species_stems[code]
            own = sorted(s for s in stems if not s.startswith("generique_"))
            if own:
                owner = own[0].rpartition("_")[0]
                entry = {"species": code, "model": owner, "kind": "own" if owner == code else "alias"}
                if owner != code:
                    entry["alias_of"] = owner
            else:
                entry = {"species": code, "model": f"generique_{species[code].group}", "kind": "generic"}
            models.append(entry)
        if self.without_hcb:
            notes.append(MENTION_HCB.format(n=self.without_hcb) + " (arbre-années)")
        generic = sum(y["trees_by_kind"]["generic"] for y in self.years)
        notes.append(f"modèle générique employé pour {generic} arbre(s) (arbre-années) : essence ou stade sans exemplaire "
                     "du générateur (Q3) ; aucun emprunt à une essence voisine" if generic else
                     "aucun arbre dessiné par un modèle générique")
        for code in sorted(c for c in self.fallbacks if any(not s.startswith("generique_") for s in self.species_stems[c])):
            notes.append(f"essence {code} : stade(s) sans exemplaire, modèle générique : {', '.join(sorted(self.fallbacks[code]))}")
        index = {"schema_version": 1, "zone": self.zone_name, "fictive": self.fictive, "crs": "EPSG:2154",
                 "vertical_datum": "NGF-IGN69", "source": self.source, "block_size_m": tiles.TILE_M, "provisoire": True,
                 "notes": notes, "models": models, "years": self.years}
        if self.recruitment:
            index["recruitment"] = self.recruitment
        write_json(self.out / "massif" / "index.json", index)
        return {"years": [y["year"] for y in self.years], "blocks": len(tile_names),
                "trees": sum(y["trees"] for y in self.years), "generic": generic}
