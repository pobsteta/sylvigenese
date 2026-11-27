"""Module `assets` (spec §2, §9) : modèles glTF, tuiles 3D, fiches de cellule, rasters web.

Étape du BRIEF codée : spec §2 (module `assets`), §9 (formats : glTF 2.0, 3D Tiles 1.1 avec
instanciation, COG, fiche de cellule ; « une tuile par année retenue ») et §10 (statut
provisoire). Deux modes :
- **état initial** (mission 028) : `sim/` absent ; `assets` lit `trees_init/trees.parquet`, l'annonce
  et écrit une seule année ;
- **années simulées** (mission 047, plan `docs/plans/m4a-suite-temps.md`, T1 à T10) : `sim/` présent ;
  `assets` lit `sim/` (voir `assets_lib/sim_state.py`) et écrit, pour chaque année retenue
  (t0, puis une sur `assets.year_step`, puis la dernière), une tuile des seuls arbres vivants, puis
  des fiches qui portent toutes les années retenues et une carte de surface terrière par année.

Sorties, sous le dossier de la zone :
- `assets/trees/<espar>_<stade>.glb` : un modèle du générateur de tarif-nemeton par exemplaire lu (mission 070,
  décision de Pascal Q1 : par fichiers, `assets.models.exemplars_dir`), trois niveaux de détail (`MSFT_lod`) ;
  `assets/trees/generique_<groupe>.glb` pour les arbres sans exemplaire (Q3, signalés et comptés, jamais un
  emprunt) ; sans `exemplars_dir`, tous les arbres sont dessinés par un modèle générique (dit à l'écran) ;
- `tiles/<année>/tileset.json` (3D Tiles 1.1) et `tiles/<année>/t_<x>_<y>.gltf` (+ .bin),
  une instance par arbre (vivant) (`EXT_mesh_gpu_instancing`), un nœud par modèle, les mêmes sommets que le LOD2 du
  `.glb` ; repère : voir `assets_lib/frame.py` ;
- `massif/index.json` et `massif/<année>/<bloc>.json` (version 2) : ce que lit la vue massif (Godot) : arbres,
  terrain, couverts, semis, mentions (voir `assets_lib/massif.py`) ;
- `tiles/index.json` : les années, leurs instances et leurs tuiles (contrat `assets.tiles_index`) ;
- `web/cells/t_<x>_<y>.json` : fiches de cellule (version 1 à l'état initial, 2 avec `sim/`) ;
- `web/rasters/vegetation_map.tif` : COG avec aperçus ; avec `sim/`, `web/rasters/g_<année>.tif`.

Écriture atomique : tout est écrit dans `<zone>/.en_cours/`, contrôlé par le validateur (contrats
`assets.*`), puis seulement mis à la place de `tiles/`, `web/cells/`, `web/rasters/` et
`assets/trees/`. Un refus n'écrit rien et laisse les sorties précédentes intactes ; les années
périmées disparaissent avec l'ancien `tiles/`. Les sorties sont identiques à l'octet près à
chaque exécution. `assets` n'importe ni `simulate` ni `post` : il ne lit que leurs fichiers.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

import numpy as np
import rasterio

from sylvigenese import common
from sylvigenese.common import ModuleError, EXIT_IMPOSSIBLE, EXIT_OK
from sylvigenese.assets_lib import (altitude, cog, exemplars, glb, initial_state, cell_sheets, massif, models,
                                    sim_state, stages, tiles)

MARKER = "zone.yml"
STAGING = ".en_cours"
MANAGED = ("tiles", "web/cells", "web/rasters", "assets/trees", "massif")   # dossiers remplacés d'un bloc
MENTION_SIM = "trajectoire technique, non validée écologiquement (décision du 25/11/2026)"
INDEX_NOTES_SIM = [
    MENTION_SIM + " : toutes les années, t0 compris, viennent de sim/ (simulate)",
    "une année retenue sur year_step, puis toujours la dernière ; aucune interpolation entre deux années retenues",
    "instances : arbres vivants seulement ; les morts de l'année sont comptés dans dead et ne sont pas dessinés "
    "(bois mort non simulé)",
    "carte des types de végétation : état initial",
    "semis non simulés ; volume et carbone non calculés (post, après M4a)",
]
SEMIS_IFN_DIRECT = "semis non simulés"   # début de la dernière note, vrai en ifn_direct seulement (mission 066)
# Dernière note de l'index quand post a tourné (sim/summary.parquet présent, fiches v3, mission 054) : elle remplace
# « volume et carbone non calculés », qui serait faux. Le nom du tarif est celui des fiches (cell_sheets.TARIF_NAME,
# ou celui du jeu fictif).
INDEX_NOTE_POST = ("semis non simulés ; volume aérien total et carbone aérien calculés par post (sim/summary.parquet), "
                   "tarif provisoire : {tarif} ; sol et bois mort non comptés")


def models_note(registry: models.ModelRegistry, generic: int, unit: str) -> str:
    """Note de tiles/index.json sur l'origine des modèles d'arbres, exacte selon le cas (Q3) : modèles du générateur
    pour N essence(s) et S stade(s), génériques pour les autres, ou tout générique sans exemplaire ; `generic` est le
    nombre d'arbres dessinés par un modèle générique, `unit` dit ce qu'on compte (« arbre(s) » ou « arbre-année(s) »)."""
    if not registry.exemplars:
        return (f"aucun exemplaire du générateur de tarif-nemeton lu : tous les arbres sont dessinés par les modèles "
                f"génériques feuillu et résineux, provisoires (Q3) : {generic} {unit} dessiné(s) en générique")
    essences = sorted({e for e, _ in registry.exemplars})
    grades = sorted({s for _, s in registry.exemplars})
    return (f"modèles du générateur de tarif-nemeton (provisoires) pour {len(essences)} essence(s) du générateur et "
            f"{len(grades)} stade(s) ({len(registry.exemplars)} exemplaire(s)) ; modèles génériques feuillu et résineux "
            f"pour les autres : {generic} {unit} dessiné(s) en générique, sans emprunt à une autre essence (Q3)")


def index_notes_sim(docs: dict[str, dict], run: dict | None = None, models_text: str | None = None) -> list[str]:
    """Notes de tiles/index.json en mode sim : celles de INDEX_NOTES_SIM, la dernière dite selon les fiches écrites
    (v2 : volume et carbone non calculés ; v3 : calculés par post, avec le tarif) et selon le mode de recrutement de
    sim/run.json. « semis non simulés » n'est dit qu'en ifn_direct (ou sans run.json) ; en mode cohorts, la note dit
    les semis simulés (techniques, non validés) et ce que run.json déclare non simulé (cell_sheets.seedling_note)."""
    tarifs = sorted({d["tarif"]["name"] for d in docs.values() if d["schema_version"] == 3})
    notes = list(INDEX_NOTES_SIM)
    if models_text:
        notes.insert(3, models_text)    # avant « carte des types de végétation »
    if tarifs:
        notes = notes[:-1] + [INDEX_NOTE_POST.format(tarif=" ; ".join(tarifs))]
    if run and run.get("recruitment") == "cohorts":
        notes[-1] = notes[-1].replace(SEMIS_IFN_DIRECT, cell_sheets.seedling_note(run), 1)
    return notes


def sheet_version(docs: dict[str, dict]) -> str:
    """Version(s) des fiches réellement écrites, pour le message final (par exemple « v3 »)."""
    return "/".join(f"v{v}" for v in sorted({d["schema_version"] for d in docs.values()}))
INDEX_NOTES_INITIAL = [
    "état initial (trees_init) : sim/ absent, aucune année simulée",
    "résultat provisoire : surface de houppier et d130 provisoires (spec §4.3)",
]


def is_fictitious_zone(zone: Path) -> bool:
    """Vrai si `<zone>/zone.yml` dit `fictive: true` (contrat zone_marker) ; les copies en héritent."""
    path = zone / MARKER
    if not path.is_file():
        return False
    content = common.read_config(path)  # YAML simple ; le contrôle des clés est celui du validateur
    return content.get("fictive") is True


def say(message: str) -> None:
    print(f"[assets] {message}", file=sys.stderr)


def say_models(registry: models.ModelRegistry) -> None:
    """Annonce d'où viennent les modèles : exemplaires lus, ou modèles génériques seulement (Q3)."""
    if registry.exemplars:
        say(f"modèles du générateur : {len(registry.exemplars)} exemplaire(s) lus dans {registry.settings.exemplars_dir} ; "
            "tout arbre sans exemplaire (essence ou stade) est dessiné par le modèle générique de son groupe, signalé "
            "et compté (Q3)")
    else:
        say("ATTENTION : assets.models.exemplars_dir absent de config.yml : aucun exemplaire du générateur ; tous les "
            "arbres sont dessinés par les modèles génériques feuillu et résineux (Q3), dit dans massif/index.json")


def ellipsoidal_height(config: dict, zone: Path, trees: dict, announce: bool = True) -> tuple[np.ndarray, dict]:
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
        if announce:
            say("ATTENTION : external.raf20_grid absent ; zone marquée fictive (zone.yml) : ondulation RAF20 prise égale à 0 "
                 "(hauteur ellipsoïdale = altitude NGF), écrite dans les extras. Ne pas faire ainsi sur une zone réelle.")
        return ngf.copy(), {"altitude": "NGF-IGN69 (dtm.tif) sans conversion : ondulation RAF20 = 0 (zone marquée fictive)", "raf20": None}
    raise ModuleError("external.raf20_grid absent de config.yml : conversion NGF-IGN69 -> hauteur ellipsoïdale "
                       "impossible (spec §9, erreur voulue) ; seule une zone marquée fictive (zone.yml) en est dispensée")


# ------------------------------------------------------------------ écriture atomique
class Staging:
    """Dossier d'écriture `<zone>/.en_cours/` : `nouveau/` reçoit les sorties ; `publish` les met à la place des
    dossiers de MANAGED (l'ancien contenu passe par `ancien/` puis disparaît). Le dossier est toujours effacé à la
    sortie, qu'il y ait refus ou non : un refus ne laisse rien derrière lui."""

    def __init__(self, zone: Path):
        self.zone = zone
        self.base = zone / STAGING
        self.root = self.base / "nouveau"

    def __enter__(self) -> "Staging":
        if self.base.exists():
            say(f"{self.base} reste d'une exécution interrompue : effacé")
            shutil.rmtree(self.base)
        self.root.mkdir(parents=True)
        return self

    def __exit__(self, *exc) -> None:
        shutil.rmtree(self.base, ignore_errors=True)

    def publish(self) -> None:
        old = self.base / "ancien"
        moved: list[str] = []
        placed: list[str] = []
        try:
            for rel in MANAGED:
                if (self.zone / rel).exists():
                    (old / rel).parent.mkdir(parents=True, exist_ok=True)
                    os.replace(self.zone / rel, old / rel)
                    moved.append(rel)
            for rel in MANAGED:
                if (self.root / rel).exists():
                    (self.zone / rel).parent.mkdir(parents=True, exist_ok=True)
                    os.replace(self.root / rel, self.zone / rel)
                    placed.append(rel)
        except OSError as error:  # remise en place des anciennes sorties, puis refus
            for rel in placed:
                shutil.rmtree(self.zone / rel, ignore_errors=True)
            for rel in moved:
                os.replace(old / rel, self.zone / rel)
            raise ModuleError(f"publication des sorties impossible ({error}) ; sorties précédentes remises en place")


def write_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def resolve_models(registry: models.ModelRegistry, species: np.ndarray, grades: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Nom du modèle et genre (`own`, `alias`, `generic`) de chaque arbre d'après son essence et son stade (Q3)."""
    pairs = {pair: registry.resolve(*pair) for pair in set(zip(species.tolist(), grades.tolist()))}
    both = [pairs[pair] for pair in zip(species.tolist(), grades.tolist())]
    return (np.array([b[0] for b in both], dtype=object), np.array([b[1] for b in both], dtype=object))


def note_generic_models(docs: dict[str, dict], registry: models.ModelRegistry, generic: int) -> None:
    """Dit aux fiches les arbres dessinés par un modèle générique (Q3), quand des exemplaires sont lus : la note
    est écrite une fois pour les fiches v2 et v3, et par année de cellule pour la v1. Sans exemplaire, tout est
    générique et l'index le dit déjà : les fiches ne changent pas."""
    if not registry.exemplars or not generic:
        return
    note = (f"{generic} arbre(s) (arbre-années retenues) dessiné(s) par un modèle générique feuillu ou résineux : essence ou "
            "stade sans exemplaire du générateur (Q3), jamais un emprunt à une autre essence ; voir massif/index.json")
    for doc in docs.values():
        if doc["schema_version"] == 1:
            for cell in doc["cells"]:
                for entry in cell["years"]:
                    entry["notes"].append(note)
        else:
            doc["notes"].append(note)


def split_into_tiles(trees: dict, z: np.ndarray, groups: np.ndarray, radius: np.ndarray | None = None) -> list[dict]:
    """Tuiles de 500 m (coin sud-ouest, EPSG:2154) des arbres donnés, dans l'ordre des noms ;
    `groups` : nom du modèle de chaque arbre."""
    x_west, y_south = tiles.tile_corner(trees["x"], trees["y"])
    built = []
    for tile_x, tile_y in sorted(set(zip(x_west.tolist(), y_south.tolist()))):
        selected = (x_west == tile_x) & (y_south == tile_y)
        subset = {k: v[selected] for k, v in trees.items()}
        built.append(tiles.build_tile(tile_x, tile_y, subset, z[selected], groups[selected],
                                      radius=None if radius is None else radius[selected]))
    return built


# ------------------------------------------------------------------ état initial (sim/ absent)
def write_initial_state(config: dict, zone: Path, out: Path, base_dir: Path | None = None) -> dict:
    """Écrit sous `out` toutes les sorties de l'état initial ; rend un résumé (chiffres).

    `base_dir` : dossier d'où se lit un `assets.models.exemplars_dir` relatif (le dossier de config.yml)."""
    if (zone / "sim").exists():
        raise ModuleError(f"{zone / 'sim'} existe : l'état initial ne s'écrit que sans sim/ "
                          "(avec sim/, assets écrit les années simulées)")
    say(f"mode état initial : sim/ absent, lecture de {zone / 'trees_init' / 'trees.parquet'}")
    registry = models.ModelRegistry.from_config(config, base_dir)
    say_models(registry)
    trees = initial_state.read_trees(zone)
    groups = initial_state.group_of_each_tree(trees["species"], initial_state.species_groups())
    year, year_origin = initial_state.displayed_year(config, zone)
    say(f"année affichée : {year} ({year_origin})")
    z, altitude_info = ellipsoidal_height(config, zone, trees)
    grades = stages.tree_stages(zone, trees["x"], trees["y"], trees["h"])
    stems, kinds = resolve_models(registry, trees["species"], grades)

    built_tiles = split_into_tiles(trees, z, stems)
    docs, counts = cell_sheets.build_cell_sheets(zone, trees, year)
    note_generic_models(docs, registry, int((kinds == "generic").sum()))
    if not (zone / "vegetation_map.tif").is_file():
        raise ModuleError(f"raster introuvable : {zone / 'vegetation_map.tif'} (sortie de biomes)")
    expected_instances = sum(t["n"] for t in built_tiles)
    if expected_instances != len(trees["h"]):
        raise ModuleError(f"{expected_instances} instances prévues pour {len(trees['h'])} arbres de trees_init")

    written_models = glb.write_models(registry, out / "assets" / "trees", {s for s in stems.tolist() if s.startswith("generique_")})
    tiles_dir = out / "tiles" / str(year)
    tiles_dir.mkdir(parents=True, exist_ok=True)
    for t in built_tiles:
        tiles.write_content(tiles_dir, t, year, registry)
    extras = {**models.GENERIC_EXTRAS, "generique": bool((kinds == "generic").any()), "annee": year, "etat": "initial", "origine_annee": year_origin,
              "source": "trees_init/trees.parquet", "instances": int(len(trees["h"])),
              "repere": "ECEF (EPSG:4978) par le transform de chaque tuile ; repère local est-nord-haut ; contenu glTF Y haut",
              **altitude_info}
    tiles.write_tileset(tiles_dir, built_tiles, year, extras)
    write_json(out / "tiles" / "index.json", {
        "schema_version": 1, "source": "trees_init", "t0": year, "provisoire": True, "notes": [*INDEX_NOTES_INITIAL, models_note(registry, int((kinds == "generic").sum()), "arbre(s)")],
        "years": [{"year": year, "instances": int(len(trees["h"])), "tileset": f"{year}/tileset.json",
                   "tiles": [{"tile": t["name"], "instances": t["n"]} for t in built_tiles]}]})
    written_sheets = cell_sheets.write_cell_sheets(out / "web" / "cells", docs)
    cog.write_cog(zone / "vegetation_map.tif", out / "web" / "rasters" / "vegetation_map.tif")

    written_instances = sum(t["n"] for t in built_tiles)
    if written_instances != len(trees["h"]):
        raise ModuleError(f"{written_instances} instances écrites pour {len(trees['h'])} arbres de trees_init")
    writer = massif.MassifWriter(out, zone, zone_name=config["zone"], source="trees_init", run=None, registry=registry,
                                 fictive=is_fictitious_zone(zone))
    writer.add_year(year, {**trees, "hcb": None, "cw": 2.0 * tiles.crown_radius(trees["crown_area"])}, grades, stems, kinds)
    block_summary = writer.finish([t["name"] for t in built_tiles])
    return {"mode": "initial", "year": year, "years": [year], "trees": int(len(trees["h"])), "tiles": len(built_tiles),
            "models": len(written_models), "sheets": len(written_sheets), "cells": counts, "tiles_dir": zone / "tiles" / str(year),
            "massif": block_summary}


def produce_initial_state(config: dict, zone: Path, base_dir: Path | None = None) -> dict:
    """État initial écrit puis publié sous la zone (sans appel du validateur : voir `run`)."""
    with Staging(zone) as staging:
        summary = write_initial_state(config, zone, staging.root, base_dir)
        staging.publish()
    return summary


# ------------------------------------------------------------------ années simulées (sim/ présent)
def check_sim_inputs(zone: Path, retained: list[int]) -> None:
    """Validateur sur les seules parties de sim/ lues (plan T6) : run.json, flags, cells, trees des années retenues."""
    batches = [("simulate.run", [zone / "sim" / "run.json"]), ("simulate.flags", [zone / "sim" / "flags.parquet"]),
               ("simulate.cells", [zone / "sim" / "cells"]),
               ("simulate.trees", [zone / "sim" / "trees" / f"year={y}" for y in retained])]
    for contract, paths in batches:
        code = common.call_validator([contract, *map(str, paths)])
        if code != 0:
            raise ModuleError(f"sim/ non conforme au contrat {contract} (validateur, code {code}) : sim/ n'est pas lu")


def write_sim_state(config: dict, zone: Path, out: Path, base_dir: Path | None = None) -> dict:
    """Écrit sous `out` les années retenues de sim/ ; rend un résumé (chiffres).

    `base_dir` : dossier d'où se lit un `assets.models.exemplars_dir` relatif (le dossier de config.yml)."""
    step = sim_state.year_step(config)
    run = sim_state.read_run(zone, config)
    t0, horizon = int(run["t0"]), int(run["years"])
    retained = sim_state.retained_years(t0, horizon, step)
    say(f"mode années simulées : lecture de {zone / 'sim'} (t0 {t0}, {horizon} ans) ; années retenues, "
        f"une sur {step} et la dernière : {', '.join(map(str, retained))}")
    sim_state.check_partitions(zone, t0, horizon, retained)
    check_sim_inputs(zone, retained)
    species_table = initial_state.species_groups()
    if not (zone / "vegetation_map.tif").is_file():
        raise ModuleError(f"raster introuvable : {zone / 'vegetation_map.tif'} (sortie de biomes)")
    registry = models.ModelRegistry.from_config(config, base_dir)
    say_models(registry)

    # 1. cellules : toutes les années (échelle fixe de la carte, Q3), années retenues pour les fiches
    cells = sim_state.read_cells(zone, t0, horizon)
    with rasterio.open(zone / "vegetation_map.tif") as src:
        veg, nodata_veg, width = src.read(1), src.nodata, src.width
    forest = {int(r * width + c) for r, c in zip(*np.nonzero(veg != nodata_veg))}
    scale_min, scale_max = sim_state.basal_area_scale(cells, forest)
    keep = set(retained)
    rows: dict[tuple[int, int], list[dict]] = {}
    for r in cells.to_pylist():
        if r["year"] in keep:
            rows.setdefault((r["cell_id"], r["year"]), []).append(r)
    flags = sim_state.cell_flags(zone, retained)
    docs, counts, g_maps = cell_sheets.build_cell_sheets_v2(zone, rows, retained, t0, flags, species_table)

    # 2. une tuile par année retenue, des seuls arbres vivants (T4, T5) ; une année à la fois en mémoire
    writer = massif.MassifWriter(out, zone, zone_name=config["zone"], source="sim", run=run, registry=registry,
                                 fictive=is_fictitious_zone(zone))
    index_years, per_year = [], []
    altitude_info: dict = {}
    generic_stems: set[str] = set()
    generic_trees = 0
    for n_year, year in enumerate(retained):
        trees = sim_state.read_trees(zone, year)
        groups_all = initial_state.group_of_each_tree(trees["species"], species_table)
        alive = trees["status"] == "alive"
        dead = int((~alive).sum())
        if not alive.any():
            raise ModuleError(f"sim/trees/year={year} : aucun arbre vivant ; une tuile vide n'est pas prévue")
        living = {k: v[alive] for k, v in trees.items()}
        grades = stages.tree_stages(zone, living["x"], living["y"], living["h"])
        stems, kinds = resolve_models(registry, living["species"], grades)
        generic_stems |= {s for s in stems.tolist() if s.startswith("generique_")}
        generic_trees += int((kinds == "generic").sum())
        z, altitude_info = ellipsoidal_height(config, zone, living, announce=n_year == 0)
        built = split_into_tiles(living, z, stems, radius=living["cw"] / 2.0)
        tiles_dir = out / "tiles" / str(year)
        tiles_dir.mkdir(parents=True)
        for t in built:
            tiles.write_content(tiles_dir, t, year, registry, state="simulé")
        n_alive = int(alive.sum())
        if sum(t["n"] for t in built) != n_alive:
            raise ModuleError(f"{year} : {sum(t['n'] for t in built)} instances pour {n_alive} arbres vivants")
        extras = {**models.GENERIC_EXTRAS, "generique": bool((kinds == "generic").any()), "annee": year, "etat": "simulé", "source": f"sim/trees/year={year}",
                  "instances": n_alive, "morts_non_dessines": dead, "run_config_sha256": run["config_sha256"],
                  "mention": MENTION_SIM, "rayon": "cw / 2 de sim/trees ; hauteur : h de sim/trees",
                  "repere": "ECEF (EPSG:4978) par le transform de chaque tuile ; repère local est-nord-haut ; contenu glTF Y haut",
                  **altitude_info}
        tiles.write_tileset(tiles_dir, built, year, extras)
        writer.add_year(year, {**living, "hcb": living["hcb"]}, grades, stems, kinds)
        per_year.append({t["name"]: t["n"] for t in built})
        index_years.append({"year": year, "instances": n_alive, "dead": dead, "tileset": f"{year}/tileset.json"})
        say(f"{year} : {n_alive} arbres vivants en {len(built)} tuile(s), {dead} mort(s) non dessiné(s)")
        del trees, living, z, built
    written_models = glb.write_models(registry, out / "assets" / "trees", generic_stems)
    note_generic_models(docs, registry, generic_trees)

    # 3. index (toutes les tuiles de la zone pour chaque année, 0 instance comprise), fiches, cartes
    all_tiles = sorted(set(docs) | {name for counts_year in per_year for name in counts_year})
    for entry, counts_year in zip(index_years, per_year):
        entry["tiles"] = [{"tile": name, "instances": int(counts_year.get(name, 0))} for name in all_tiles]
    write_json(out / "tiles" / "index.json", {
        "schema_version": 1, "source": "sim", "t0": t0, "year_step": step, "run_config_sha256": run["config_sha256"],
        "provisoire": True, "notes": index_notes_sim(docs, run, models_note(registry, generic_trees, "arbre-année(s)")),
        "basal_area_map": {"unit": "m2/ha", "scale_min_m2_ha": scale_min, "scale_max_m2_ha": scale_max,
                           "mention": "surface terrière par cellule (m2/ha), web/rasters/g_<année>.tif, échelle fixe sur "
                                      f"toutes les années simulées ({t0} à {t0 + horizon}) ; " + MENTION_SIM},
        "years": index_years})
    block_summary = writer.finish(all_tiles)
    written_sheets = cell_sheets.write_cell_sheets(out / "web" / "cells", docs)
    cog.write_cog(zone / "vegetation_map.tif", out / "web" / "rasters" / "vegetation_map.tif")
    for year in retained:
        cog.write_basal_area_cog(zone / "grid.tif", g_maps[year], out / "web" / "rasters" / f"g_{year}.tif")
    return {"mode": "sim", "year": retained[0], "years": retained, "trees": sum(e["instances"] for e in index_years),
            "dead": sum(e["dead"] for e in index_years), "tiles": len(all_tiles), "models": len(written_models),
            "sheets": len(written_sheets), "sheet_version": sheet_version(docs), "cells": counts,
            "scale": (scale_min, scale_max), "massif": block_summary}


# ------------------------------------------------------------------ contrôle et point d'entrée
def validate_outputs(root: Path, years: int | list[int], grid: Path | None = None) -> int:
    """Appelle le validateur sur chaque contrat `assets.*` des sorties sous `root` ; rend le pire code (0 si tout
    conforme). `grid` : grid.tif de la zone, exigé pour contrôler les cartes g_<année>.tif."""
    years = [years] if isinstance(years, int) else list(years)
    rasters = root / "web" / "rasters"
    batches = [
        ("assets.gltf", sorted((root / "assets" / "trees").glob("*.gltf"))
         + [p for y in years for p in sorted((root / "tiles" / str(y)).glob("*.gltf"))]),
        ("assets.tree_model", sorted((root / "assets" / "trees").glob("*.glb"))),
        ("assets.tileset", [root / "tiles" / str(y) / "tileset.json" for y in years]),
        ("assets.tiles_index", [root / "tiles" / "index.json"]),
        ("assets.massif_index", [root / "massif" / "index.json"]),
        ("assets.massif_block", sorted((root / "massif").glob("*/*.json"))),
        ("assets.cell_sheet", sorted((root / "web" / "cells").glob("*.json"))),
        ("assets.web_raster", sorted(rasters.glob("*.tif"))),
    ]
    g_maps = sorted(rasters.glob("g_*.tif"))
    if g_maps:
        if grid is None:
            raise ModuleError("contrôle des cartes g_<année>.tif impossible sans grid.tif")
        batches.append(("assets.basal_area_raster", ["--grid", grid, *g_maps]))
    worst = 0
    for contract, paths in batches:
        if not paths:
            continue
        code = common.call_validator([contract, *map(str, paths)])
        if code != 0:
            say(f"contrat {contract} : validateur code {code}")
            worst = max(worst, code)
    return worst


def run(config_path: str) -> int:
    try:
        config = common.read_config(config_path)
        zone = initial_state.zone_dir(config)
        base_dir = Path(config_path).resolve().parent
        with_sim = (zone / "sim").exists()
        if with_sim:
            sim_state.year_step(config)  # cause nommée avant le verdict général du validateur
        code = common.call_validator(["config", str(config_path)])
        if code != 0:
            raise ModuleError(f"config.yml non conforme (validateur, code {code})")
        with Staging(zone) as staging:
            summary = (write_sim_state if with_sim else write_initial_state)(config, zone, staging.root, base_dir)
            code = validate_outputs(staging.root, summary["years"], zone / "grid.tif")
            if code != 0:
                raise ModuleError(f"sorties non conformes aux contrats assets.* (validateur, code {code}) ; rien n'est publié")
            staging.publish()
    except ModuleError as error:
        print(f"[assets] erreur : {error}", file=sys.stderr)
        return EXIT_IMPOSSIBLE
    c, m = summary["cells"], summary["massif"]
    blocks = (f"massif/ : {m['blocks']} bloc(s) par année, {m['trees']} arbre(s) au total, dont {m['generic']} dessiné(s) "
              "par un modèle générique (essence ou stade sans exemplaire, Q3)")
    if summary["mode"] == "sim":
        say(f"années simulées {', '.join(map(str, summary['years']))} : {summary['trees']} instances (vivants) au total, "
            f"{summary['dead']} morts non dessinés, {summary['tiles']} tuile(s), {summary['models']} modèle(s) .glb, "
            f"{summary['sheets']} fiche(s) {summary['sheet_version']} de "
            f"{c['cells']} cellule(s), {len(summary['years'])} carte(s) de surface terrière (échelle "
            f"{summary['scale'][0]:.3f} à {summary['scale'][1]:.3f} m2/ha) ; {blocks} ; {MENTION_SIM} ; tous les contrats assets.* conformes")
        return EXIT_OK
    say(f"état initial {summary['year']} : {summary['trees']} instances en {summary['tiles']} tuile(s), "
         f"{summary['models']} modèle(s) .glb, {summary['sheets']} fiche(s) de {c['cells']} cellule(s) "
         f"(sans station : {c['without_station']}, sans type de végétation : {c['without_vegetation']}, sans H0 : {c['without_h0']}), "
         f"1 COG ; {blocks} ; tous les contrats assets.* conformes")
    return EXIT_OK


def request_dimensions(config_path: str, out: Path, quantile: float, min_trees: int) -> int:
    """Écrit le fichier de DEMANDE des dimensions D et H des exemplaires (Q6), au format `params.model_dimensions`,
    d'après les quantiles de sim/trees ; ne touche à aucune sortie de assets."""
    try:
        config = common.read_config(config_path)
        zone = initial_state.zone_dir(config)
        rows, notes = exemplars.dimensions_request(zone, config, quantile, min_trees)
        exemplars.write_request(out, rows)
    except ModuleError as error:
        print(f"[assets] erreur : {error}", file=sys.stderr)
        return EXIT_IMPOSSIBLE
    say(f"demande de dimensions écrite : {out} ({len(rows)} ligne(s), D et H de {len(rows) // 2} couple(s) essence-stade, "
        f"quantile {quantile:g}, au moins {min_trees} arbres) ; à donner à l'export de tarif-nemeton (--dimensions)")
    for note in notes:
        say(f"signalement : {note['essence']} {note['stage']} : {note['reason']}")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="assets", exit_on_error=False)
    parser.add_argument("--config", default="config.yml", help="chemin de config.yml")
    parser.add_argument("--demande-dimensions", metavar="FICHIER.csv", default=None,
                        help="écrit seulement la demande de dimensions des exemplaires (D et H, quantiles de sim/trees, "
                             "contrat params.model_dimensions) pour l'export de tarif-nemeton, puis s'arrête")
    parser.add_argument("--quantile", type=float, default=0.5,
                        help="quantile de D et H de la demande (0,5 : la médiane) ; seulement avec --demande-dimensions")
    parser.add_argument("--min-arbres", type=int, default=30,
                        help="nombre minimal d'arbres vivants d'un couple essence-stade pour demander ses dimensions")
    try:
        options = parser.parse_args(argv)
    except (argparse.ArgumentError, SystemExit):
        return EXIT_IMPOSSIBLE
    if options.demande_dimensions:
        return request_dimensions(options.config, Path(options.demande_dimensions), options.quantile, options.min_arbres)
    return run(options.config)


if __name__ == "__main__":
    sys.exit(main())
