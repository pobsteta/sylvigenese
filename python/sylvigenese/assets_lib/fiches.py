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

from sylvigenese.commun import ErreurModule
from sylvigenese.assets_lib.tuiles import TUILE_M, nom_tuile

NON_RENSEIGNE = "non_renseigne"
NOTE_VOLUME = "volume et carbone non calculés : ils viennent de post, après la simulation (état initial)"
NOTE_COMPOSITION = "composition : part du nombre d'arbres détectés sur le MNH ; arbres dominés non comptés (spec §4.6)"
NOTE_PROVISOIRE = "résultat provisoire : surface de houppier et d130 provisoires (spec §4.3) ; hauteur du MNH à la date de vol, non avancée jusqu'à t0"


def lire_categories(chemin: Path) -> dict[int, str]:
    """`value,name` -> {valeur: nom} (catégories codées par leur nom, spec §8)."""
    if not chemin.is_file():
        raise ErreurModule(f"table de catégories introuvable : {chemin}")
    with open(chemin, encoding="utf-8", newline="") as f:
        return {int(l["value"]): l["name"] for l in csv.DictReader(f)}


def _lire(chemin: Path) -> tuple[np.ndarray, object]:
    if not chemin.is_file():
        raise ErreurModule(f"raster introuvable : {chemin} (sortie de prepare ou biomes)")
    with rasterio.open(chemin) as src:
        return src.read(1), src


def construire_fiches(zone: Path, arbres: dict[str, np.ndarray], annee: int) -> tuple[dict[str, dict], dict]:
    """Fiches par tuile {nom: document} et comptes {cellules, sans_station, sans_vegetation, sans_h0}."""
    grille, src = _lire(zone / "grid.tif")
    largeur, hauteur = src.width, src.height
    transform = src.transform
    veg, src_veg = _lire(zone / "vegetation_map.tif")
    sta, src_sta = _lire(zone / "station_type.tif")
    h0, src_h0 = _lire(zone / "h0.tif")
    for nom, s in (("vegetation_map", src_veg), ("station_type", src_sta), ("h0", src_h0)):
        if (s.width, s.height, s.transform) != (largeur, hauteur, transform):
            raise ErreurModule(f"{nom}.tif n'est pas aligné sur grid.tif")
    noms_veg = lire_categories(zone / "vegetation_map.csv")
    noms_sta = lire_categories(zone / "station_type.csv")

    col = np.floor((arbres["x"] - transform.c) / transform.a).astype(int)
    lig = np.floor((arbres["y"] - transform.f) / transform.e).astype(int)
    hors = (col < 0) | (col >= largeur) | (lig < 0) | (lig >= hauteur)
    if hors.any():
        raise ErreurModule(f"{int(hors.sum())} arbre(s) hors de la grille grid.tif")
    cellule_arbre = lig * largeur + col
    par_cellule: dict[int, list[str]] = defaultdict(list)
    for cid, esp in zip(cellule_arbre.tolist(), arbres["species"].tolist()):
        par_cellule[cid].append(esp)

    surface_ha = abs(transform.a * transform.e) / 10000.0
    nodata_veg = src_veg.nodata if src_veg.nodata is not None else -1
    nodata_sta = src_sta.nodata if src_sta.nodata is not None else -1
    comptes = {"cellules": 0, "sans_station": 0, "sans_vegetation": 0, "sans_h0": 0}
    tuiles: dict[str, list[dict]] = defaultdict(list)
    for r in range(hauteur):
        for c in range(largeur):
            cid = r * largeur + c
            code_veg = int(veg[r, c])
            if cid not in par_cellule and code_veg == nodata_veg:
                continue
            x = transform.c + (c + 0.5) * transform.a
            y = transform.f + (r + 0.5) * transform.e
            code_sta = int(sta[r, c])
            if code_veg == nodata_veg or code_veg not in noms_veg:
                comptes["sans_vegetation"] += 1
                nom_v = NON_RENSEIGNE
            else:
                nom_v = noms_veg[code_veg]
            if code_sta == nodata_sta or code_sta not in noms_sta:
                comptes["sans_station"] += 1
                nom_s = NON_RENSEIGNE
            else:
                nom_s = noms_sta[code_sta]
            especes = sorted(par_cellule.get(cid, []))
            n = len(especes)
            composition = [{"species": e, "share": round(especes.count(e) / n, 6)} for e in sorted(set(especes))]
            notes = [NOTE_COMPOSITION, NOTE_VOLUME, NOTE_PROVISOIRE]
            annee_item = {"year": annee, "provisoire": True, "composition": composition,
                          "volume_m3_ha": None, "carbon_t_ha": None,
                          "density_trees_ha": round(n / surface_ha, 3), "notes": notes}
            valeur_h0 = float(h0[r, c])
            if src_h0.nodata is not None and valeur_h0 == src_h0.nodata:
                comptes["sans_h0"] += 1
                notes.append("H0 absente (nodata dans h0.tif)")
            else:
                annee_item["h0_m"] = round(valeur_h0, 3)
            ex, ny = int(np.floor(x / TUILE_M) * TUILE_M), int(np.floor(y / TUILE_M) * TUILE_M)
            tuiles[nom_tuile(ex, ny)].append({"cell_id": cid, "x": x, "y": y, "station_type": nom_s,
                                              "vegetation_type": nom_v, "years": [annee_item]})
            comptes["cellules"] += 1
    docs = {nom: {"schema_version": 1, "tile": nom, "cells": cellules} for nom, cellules in sorted(tuiles.items())}
    return docs, comptes


def ecrire_fiches(dossier: Path, docs: dict[str, dict]) -> list[Path]:
    dossier.mkdir(parents=True, exist_ok=True)
    for ancien in dossier.glob("t_*.json"):
        ancien.unlink()
    chemins = []
    for nom, doc in docs.items():
        chemin = dossier / f"{nom}.json"
        chemin.write_text(json.dumps(doc, separators=(",", ":"), ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        chemins.append(chemin)
    return chemins
