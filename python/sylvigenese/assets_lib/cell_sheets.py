"""Fiches de cellule `web/cells/<tuile>.json` (contrat `assets.cell_sheet`, spec §1 et §10).

Étape du BRIEF codée : spec §1 (la fiche affiche station, type de végétation, composition,
volume, carbone, mention « provisoire ») ; mission 028, état initial (version 1) ; mission 047,
évolution simulée (version 2, voir `build_cell_sheets_v2` plus bas) ; mission 053, évolution simulée
avec le volume aérien total et le carbone aérien de `sim/summary.parquet` (version 3, écrite dès que
`post` a tourné ; BRIEF §6, décisions de Pascal Q1 à Q5 du 26/11/2026 ; voir `year_entry_v3`).

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
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import rasterio

from sylvigenese import common
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


# Mention des semis (mission 062) : « semis non simulés » n'est juste que si sim/run.json ne dit pas le contraire. En
# mode cohorts (M5a), les semis sont simulés ; ce qui ne l'est pas est dit par run.json (`not_simulated`, décision de
# Pascal Q3 du 26/11/2026).
NOTE_SEMIS_COHORTS = ("semis simulés par cohortes (M5a, mode cohorts de simulate ; trajectoire technique, non validée "
                      "écologiquement) ; {non_simules} non simulés")
NON_SIMULES_FR = {"semis": "semis", "sous_bois": "sous-bois", "gibier": "gibier", "fructification": "fructification"}


def seedling_note(run: dict | None) -> str:
    """La note des semis d'après sim/run.json : NOTES_V2[2] sans mode cohorts, sinon NOTE_SEMIS_COHORTS avec la
    liste `not_simulated` de run.json (rien n'est ajouté ni deviné)."""
    if not run or run.get("recruitment") != "cohorts":
        return NOTES_V2[2]
    items = [NON_SIMULES_FR.get(k, k) for k in run.get("not_simulated", [])]
    if not items:
        raise ModuleError("sim/run.json dit recruitment = cohorts sans not_simulated : la mention des semis ne se "
                          "devine pas")
    text = ", ".join(items[:-1]) + " et " + items[-1] if len(items) > 1 else items[0]
    return NOTE_SEMIS_COHORTS.format(non_simules=text)


def _run_of(zone: Path) -> dict | None:
    path = zone / "sim" / "run.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def notes_v2_for(run: dict | None) -> list[str]:
    """NOTES_V2, la note des semis dite selon sim/run.json."""
    notes = list(NOTES_V2)
    notes[2] = seedling_note(run)
    return notes


# Fiche version 3 (mission 053, contrat cell_sheet v3 de la mission 051, décisions de Pascal Q1 à Q5 du 26/11/2026) :
# écrite quand sim/summary.parquet existe ; mêmes notes que la v2, sauf « volume et carbone non calculés », remplacée
# par les définitions du volume et du carbone.
NOTES_V3_HEAD = [
    NOTES_V2[0],
    "volume_m3_ha : volume aérien total (tige et branches, sur écorce) des arbres vivants calculés, lu dans "
    "sim/summary.parquet (post) ; même définition pour toutes les essences (décision de Pascal Q3) ; ni bois fort ni "
    "volume au-dessus de 7 cm",
    "carbon_t_ha : carbone aérien = biomasse aérienne sèche (volume aérien total × infradensité) × fraction de carbone, "
    "en tC/ha ; pas de CO2",
    "sol et bois mort : non modélisés (hors v1), ni dans le volume ni dans le carbone",
    "tarif provisoire (« coefficients non stabilisés ») : voir tarif et sim/post.json pour le commit et les sources",
]
NOTE_PARTIAL = ("volume partiel : une partie des tiges n'est pas calculée (hors du domaine du tarif, ou essence sans "
                "tarif ; ni extrapolation ni emprunt, décision de Pascal Q5) ; basal_area_not_computed_share en donne la "
                "part de surface terrière ; quand elle vaut 1, rien n'est calculé : volume et carbone null, raison dans "
                "not_computed_reason")
NOTE_NO_ROOTS = ("carbone souterrain non calculé : le rapport du GIEC 2006 (tableau 4.4) n'est pas encore lu ni cité "
                 "(décision de Pascal Q4) ; aucune valeur n'est prise à sa place")
REASON_NOTHING = ("aucune tige vivante de la cellule n'est calculée : toutes sont hors du domaine du tarif ou d'une "
                  "essence sans tarif (ni extrapolation ni emprunt, décision de Pascal Q5)")
# Nom et sources du tarif : tirés de params/tarif.parquet (colonnes source_biblio et source_commit, et termes de la
# forme de volume), jamais écrits d'avance (mission 056 : les résineux synthétiques du jeu fictif ne sont pas le
# tarif NEMETON v5, et leurs racines ne viennent pas du GIEC). TARIF_NAME n'est dit que si toutes les formes de
# volume sont celles de NEMETON v5 (contrat import_tarif.tarif).
TARIF_NAME = "tarif NEMETON v5"
VOLUME_MODELS = ("volume_feuillus", "profil_tige_resineux", "expansion_resineux")
SYNTH_TERMS = ("synth_p1", "synth_p2", "synth_E")


def quoted_sources(rows: list[dict]) -> str:
    """Valeurs distinctes de source_biblio, citées telles quelles."""
    return " ; ".join(f"« {b} »" for b in sorted({r["source_biblio"] for r in rows}))


def tarif_name(rows: list[dict]) -> str:
    """Nom du tarif de la fiche v3 : ses formes de volume et la source de ses valeurs (source_biblio)."""
    volume = [r for r in rows if r["modele"] in VOLUME_MODELS]
    has_hw = any(r["modele"] == "volume_feuillus" for r in volume)
    sw = [r for r in volume if r["modele"] != "volume_feuillus"]
    synthetic_sw = any(r["terme"] in SYNTH_TERMS for r in sw)
    if not synthetic_sw:
        forms = TARIF_NAME
    else:
        forms = (("forme NEMETON v5 pour les feuillus, " if has_hw else "")
                 + "forme synthétique du jeu fictif pour les résineux (sans sens écologique)")
    biblios = {r["source_biblio"] for r in volume}
    values = (f"valeurs de source {quoted_sources(volume)}" if len(biblios) == 1 else
              f"valeurs de {len(biblios)} sources (une par modèle, sim/post.json)")
    return f"{forms} ; {values} ; provisoire"


def note_roots(rows: list[dict], commit: str) -> str:
    """Note « racines » de la fiche v3, avec la source du rapport racines/aérien lue dans params/tarif.parquet."""
    roots = [r for r in rows if r["modele"] == "racines"]
    return ("racines : root_carbon_t_ha, carbone des racines, à part du carbone aérien et jamais additionné, "
            f"PROVISOIRE (rapport racines/aérien de params/tarif.parquet, source {quoted_sources(roots)}, "
            f"source_commit {commit} ; décision de Pascal Q4)")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_post_summary(zone: Path, retained: list[int]) -> dict | None:
    """Lignes de sim/summary.parquet des années retenues, par (cell_id, année), si post a tourné ; None sinon.

    Refus (code 2, cause nommée) : summary sans sim/post.json, ou post.json d'un autre run de simulate (empreinte de
    sim/run.json différente) : la fiche ne mêle pas deux runs."""
    path = zone / "sim" / "summary.parquet"
    if not path.is_file():
        return None
    post_path = zone / "sim" / "post.json"
    if not post_path.is_file():
        raise ModuleError(f"{path} existe sans sim/post.json : post a été interrompu ; relancer post")
    try:
        post = json.loads(post_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ModuleError(f"{post_path} illisible : {error}") from error
    run_hash = _sha256(zone / "sim" / "run.json")
    if (post.get("inputs_sha256") or {}).get("sim_run") != run_hash:
        raise ModuleError("sim/summary.parquet vient d'un autre run de simulate (empreinte de sim/run.json différente "
                          "de celle de sim/post.json) : relancer post avant assets")
    code = common.call_validator(["post.summary", str(path)])
    if code != 0:
        raise ModuleError(f"{path} non conforme au contrat post.summary (validateur, code {code}) : il n'est pas lu")
    table = pq.read_table(path)
    has_roots = "carbon_roots_t_ha" in table.schema.names
    keep = set(retained)
    rows: dict[tuple[int, int], dict[str, dict]] = defaultdict(dict)
    names = ["cell_id", "year", "species", "volume_m3_ha", "carbon_t_ha", "stems_not_computed_ha",
             "basal_area_not_computed_share"] + (["carbon_roots_t_ha"] if has_roots else [])
    columns = {n: table.column(n).to_pylist() for n in names}
    for i, year in enumerate(columns["year"]):
        if year in keep:
            rows[(int(columns["cell_id"][i]), int(year))][str(columns["species"][i])] = {n: columns[n][i] for n in names}
    tarif_path = zone / "params" / "tarif.parquet"
    if not tarif_path.is_file():
        raise ModuleError(f"{tarif_path} absent : le nom et les sources du tarif de la fiche se lisent dans le tarif "
                          "qu'a lu post ; rien n'est écrit à sa place")
    if (post.get("inputs_sha256") or {}).get("params_tarif") != _sha256(tarif_path):
        raise ModuleError(f"{tarif_path} a changé depuis post (empreinte différente de celle de sim/post.json) : "
                          "relancer post avant assets")
    tarif_rows = pq.read_table(tarif_path).to_pylist()
    if has_roots and not any(r["modele"] == "racines" for r in tarif_rows):
        raise ModuleError("sim/summary.parquet porte carbon_roots_t_ha mais params/tarif.parquet n'a pas de modèle "
                          "racines : la source des racines ne peut pas être citée")
    return {"rows": rows, "has_roots": has_roots, "commit": post["tarif_commit"], "name": tarif_name(tarif_rows),
            "roots_note": note_roots(tarif_rows, post["tarif_commit"]) if has_roots else NOTE_NO_ROOTS}


def year_entry_v3(rows: list[dict], summary: dict[str, dict], has_roots: bool, year: int, cid: int) -> dict:
    """Une année de la fiche v3 (contrat cell_sheet, year_v3) : l'année v2, plus le volume et le carbone de
    sim/summary.parquet (sommes sur les essences) et la part non calculée. Les essences du summary doivent être
    celles de sim/cells (mêmes arbres vivants) : sinon refus, on ne complète pas."""
    item = year_entry_v2(rows, year, cid)
    species = [c["species"] for c in item["composition"]]
    if sorted(summary) != sorted(species):
        raise ModuleError(f"année {year}, cellule {cid} : essences de sim/summary.parquet {sorted(summary)} différentes "
                          f"de celles de sim/cells {sorted(species)} : summary et cells ne viennent pas du même run")
    if not summary:   # aucun arbre vivant : 0 est un fait arithmétique, pas une valeur devinée
        item.update(volume_m3_ha=0.0, carbon_t_ha=0.0, stems_not_computed_ha=0.0, basal_area_not_computed_share=0.0,
                    volume_partiel=False)
        if has_roots:
            item["root_carbon_t_ha"] = 0.0
        return item
    g_total = g_not_computed = volume = carbon = roots = stems_nc = 0.0
    for entry in item["composition"]:
        r = summary[entry["species"]]
        share = float(r["basal_area_not_computed_share"])
        entry["basal_area_not_computed_share"] = share
        entry["volume_m3_ha"] = None if share == 1.0 else float(r["volume_m3_ha"])
        entry["carbon_t_ha"] = None if share == 1.0 else float(r["carbon_t_ha"])
        g_total += entry["basal_area_m2_ha"]
        g_not_computed += share * entry["basal_area_m2_ha"]
        volume += float(r["volume_m3_ha"])
        carbon += float(r["carbon_t_ha"])
        roots += float(r["carbon_roots_t_ha"]) if has_roots else 0.0
        stems_nc += float(r["stems_not_computed_ha"])
    if all(e["basal_area_not_computed_share"] == 1.0 for e in item["composition"]):
        share = 1.0
    else:   # au moins une tige calculée : la part reste sous 1 (1 veut dire « rien n'est calculé »)
        share = min(g_not_computed / g_total, math.nextafter(1.0, 0.0)) if g_total > 0 else 0.0
    nothing = share == 1.0
    item.update(volume_m3_ha=None if nothing else volume, carbon_t_ha=None if nothing else carbon,
                stems_not_computed_ha=stems_nc, basal_area_not_computed_share=share, volume_partiel=share > 0)
    if has_roots:
        item["root_carbon_t_ha"] = None if nothing else roots
    if nothing:
        item["not_computed_reason"] = REASON_NOTHING
    return item


def _optional_value(array: np.ndarray, nodata, r: int, c: int) -> float | None:
    v = float(array[r, c])
    if not np.isfinite(v) or (nodata is not None and v == nodata):
        return None
    return v


def build_cell_sheets_v2(zone: Path, rows: dict[tuple[int, int], list[dict]], retained: list[int], t0: int,
                         flags: dict[tuple[int, int], list[dict]], species_table: dict[str, str]
                         ) -> tuple[dict[str, dict], dict, dict[int, np.ndarray]]:
    """Fiches v2 (ou v3 si sim/summary.parquet existe) par tuile, comptes, et carte de surface terrière (m2/ha,
    NaN hors forêt) par année retenue.

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
    post = read_post_summary(zone, retained)
    if post is not None:
        stray = sorted({key for key in post["rows"] if key[0] not in wanted})
        if stray:
            raise ModuleError(f"sim/summary.parquet a des lignes pour des cellules sans fiche (par exemple {stray[0]}) : "
                              "summary et cells ne viennent pas du même run")

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
            if post is None:
                item = year_entry_v2(rows.get((cid, year), []), year, cid)
            else:
                item = year_entry_v3(rows.get((cid, year), []), post["rows"].get((cid, year), {}), post["has_roots"],
                                     year, cid)
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
    notes_sim = notes_v2_for(_run_of(zone))
    if post is None:
        docs = {name: {"schema_version": 2, "tile": name, "source": "sim", "notes": list(notes_sim), "cells": cells}
                for name, cells in sorted(tiles.items())}
        return docs, counts, g_maps
    docs = {}
    for name, cells in sorted(tiles.items()):
        notes = list(NOTES_V3_HEAD)
        if any(e["volume_partiel"] for c in cells for e in c["years"]):
            notes.append(NOTE_PARTIAL)
        notes.append(post["roots_note"])
        notes += notes_sim[2:]
        docs[name] = {"schema_version": 3, "tile": name, "source": "sim", "notes": notes,
                      "tarif": {"name": post["name"], "commit": post["commit"], "provisoire": True}, "cells": cells}
    return docs, counts, g_maps


def h_missing(heights: set) -> bool:
    """Vrai si la hauteur dominante lue est absente (null, ou NaN lu par pyarrow comme valeur)."""
    return len(heights) == 1 and all(h is None or (isinstance(h, float) and math.isnan(h)) for h in heights)


def year_entry_v2(rows: list[dict], year: int, cid: int) -> dict:
    """Une année de la fiche v2 depuis les lignes de sim/cells d'une cellule (contrat cell_sheet, year_v2).

    Sans ligne : aucun arbre vivant (tiges et G à 0, d130 moyen et h_dom_m null, composition vide ; contrat
    simulate.cells). Des tiges vivantes avec une h_dom_m null sont refusées, cause nommée : la fiche ne les montre
    jamais comme « aucun arbre vivant » (relecture de la PR n° 9, I2). Une h_dom_m qui diffère d'une essence à l'autre de la même cellule est refusée : on ne choisit pas.
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
    if h_missing(heights) and stems > 0:
        raise ModuleError(f"sim/cells, année {year}, cellule {cid} : {stems:g} tiges/ha vivantes mais h_dom_m est null "
                          "(hauteur dominante non finie dans simulate) ; refusé : la fiche ne dirait pas « aucun arbre "
                          "vivant » pour une cellule qui a des arbres")
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
