"""Module `assets` (spec §2, §9) : modèles glTF, tuiles 3D, fiches de cellule, rasters web.

Étape du BRIEF codée : spec §2 (module `assets`), §9 (formats : glTF 2.0, 3D Tiles 1.1 avec
instanciation, COG, fiche de cellule) et §10 (statut provisoire). Mission 028 : **état
initial**. Si `sim/` est absent, `assets` lit `trees_init/trees.parquet` et l'annonce ; la
lecture de `sim/` (années simulées) n'est pas encore faite et `sim/` présent est une erreur.

Sorties, sous le dossier de la zone :
- `assets/trees/{feuillu,resineux}.gltf` (+ .bin) : modèles génériques provisoires (M6) ;
- `tiles/<année>/tileset.json` (3D Tiles 1.1) et `tiles/<année>/t_<x>_<y>.gltf` (+ .bin),
  une instance par arbre (`EXT_mesh_gpu_instancing`) ; repère : voir `assets_lib/repere.py` ;
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

from sylvigenese import commun
from sylvigenese.commun import ErreurModule, SORTIE_IMPOSSIBLE, SORTIE_OK
from sylvigenese.assets_lib import altitude, cog, etat_initial, fiches, modeles, tuiles

JEU_FICTIF = "zone_fictive"


def dire(message: str) -> None:
    print(f"[assets] {message}", file=sys.stderr)


def hauteur_ellipsoidale(config: dict, zone: Path, arbres: dict) -> tuple[np.ndarray, dict]:
    """Hauteur ellipsoïdale du pied de chaque arbre = altitude NGF du MNT + ondulation RAF20.

    Sans grille RAF20 : erreur (spec §9), sauf pour le jeu fictif, dont les coordonnées sont
    synthétiques : l'ondulation y vaut 0, ce qui est annoncé et écrit dans les extras.
    """
    ngf = altitude.lire_altitude_ngf(zone / "dtm.tif", arbres["x"], arbres["y"])
    raf20 = (config.get("external") or {}).get("raf20_grid")
    if raf20:
        n = altitude.ondulation_raf20(Path(raf20), arbres["x"], arbres["y"])
        return ngf + n, {"altitude": "NGF-IGN69 (dtm.tif) + ondulation RAF20", "raf20": str(raf20)}
    if config.get("zone") == JEU_FICTIF:
        dire("ATTENTION : external.raf20_grid absent ; jeu fictif : ondulation RAF20 prise égale à 0 "
             "(hauteur ellipsoïdale = altitude NGF), écrite dans les extras. Ne pas faire ainsi sur une zone réelle.")
        return ngf.copy(), {"altitude": "NGF-IGN69 (dtm.tif) sans conversion : ondulation RAF20 = 0 (jeu fictif)", "raf20": None}
    raise ErreurModule("external.raf20_grid absent de config.yml : conversion NGF-IGN69 -> hauteur ellipsoïdale "
                       "impossible (spec §9, erreur voulue)")


def produire_etat_initial(config: dict, zone: Path) -> dict:
    """Écrit toutes les sorties de l'état initial ; rend un résumé (chiffres)."""
    if (zone / "sim").exists():
        raise ErreurModule(f"{zone / 'sim'} existe : la lecture des années simulées n'est pas encore faite "
                           "(mission suivante) ; mode « état initial » seulement")
    dire(f"mode état initial : sim/ absent, lecture de {zone / 'trees_init' / 'trees.parquet'}")
    arbres = etat_initial.lire_arbres(zone)
    groupes = etat_initial.groupe_de_chaque_arbre(arbres["species"], etat_initial.groupes_essences())
    annee, origine_annee = etat_initial.annee_affichee(config, zone)
    dire(f"année affichée : {annee} ({origine_annee})")
    z, info_altitude = hauteur_ellipsoidale(config, zone, arbres)

    modeles_ecrits = modeles.ecrire_modeles(zone / "assets" / "trees")

    dossier_tuiles = zone / "tiles" / str(annee)
    if dossier_tuiles.exists():
        for ancien in list(dossier_tuiles.glob("*.gltf")) + list(dossier_tuiles.glob("*.bin")) + list(dossier_tuiles.glob("tileset.json")):
            ancien.unlink()
    dossier_tuiles.mkdir(parents=True, exist_ok=True)
    x_ouest, y_sud = tuiles.coin_tuile(arbres["x"], arbres["y"])
    cles = sorted(set(zip(x_ouest.tolist(), y_sud.tolist())))
    liste = []
    for xo, ys in cles:
        choix = (x_ouest == xo) & (y_sud == ys)
        sous = {k: v[choix] for k, v in arbres.items()}
        t = tuiles.construire_tuile(xo, ys, sous, z[choix], groupes[choix])
        tuiles.ecrire_contenu(dossier_tuiles, t, annee)
        liste.append(t)
    extras = dict(modeles.EXTRAS_GENERIQUE, annee=annee, etat="initial", origine_annee=origine_annee,
                  source="trees_init/trees.parquet", instances=int(len(arbres["h"])),
                  repere="ECEF (EPSG:4978) par le transform de chaque tuile ; repère local est-nord-haut ; contenu glTF Y haut",
                  **info_altitude)
    tuiles.ecrire_tileset(dossier_tuiles, liste, annee, extras)

    docs, comptes = fiches.construire_fiches(zone, arbres, annee)
    fiches_ecrites = fiches.ecrire_fiches(zone / "web" / "cells", docs)
    cog.ecrire_cog(zone / "vegetation_map.tif", zone / "web" / "rasters" / "vegetation_map.tif")

    instances_ecrites = sum(t["n"] for t in liste)
    if instances_ecrites != len(arbres["h"]):
        raise ErreurModule(f"{instances_ecrites} instances écrites pour {len(arbres['h'])} arbres de trees_init")
    return {"annee": annee, "arbres": int(len(arbres["h"])), "tuiles": len(liste), "modeles": len(modeles_ecrits),
            "fiches": len(fiches_ecrites), "cellules": comptes, "dossier_tuiles": dossier_tuiles}


def valider_sorties(zone: Path, annee: int) -> int:
    """Appelle le validateur sur chaque contrat `assets.*` ; rend le pire code (0 si tout conforme)."""
    pire = 0
    lots = [
        ("assets.gltf", sorted((zone / "assets" / "trees").glob("*.gltf")) + sorted((zone / "tiles" / str(annee)).glob("*.gltf"))),
        ("assets.tileset", [zone / "tiles" / str(annee) / "tileset.json"]),
        ("assets.cell_sheet", sorted((zone / "web" / "cells").glob("*.json"))),
        ("assets.web_raster", [zone / "web" / "rasters" / "vegetation_map.tif"]),
    ]
    for contrat, chemins in lots:
        code = commun.appeler_validateur([contrat, *map(str, chemins)])
        if code != 0:
            dire(f"contrat {contrat} : validateur code {code}")
            pire = max(pire, code)
    return pire


def executer(chemin_config: str) -> int:
    try:
        config = commun.lire_config(chemin_config)
        code = commun.appeler_validateur(["config", str(chemin_config)])
        if code != 0:
            raise ErreurModule(f"config.yml non conforme (validateur, code {code})")
        zone = etat_initial.dossier_zone(config)
        resume = produire_etat_initial(config, zone)
        code = valider_sorties(zone, resume["annee"])
        if code != 0:
            raise ErreurModule(f"sorties non conformes aux contrats assets.* (validateur, code {code})")
    except ErreurModule as erreur:
        print(f"[assets] erreur : {erreur}", file=sys.stderr)
        return SORTIE_IMPOSSIBLE
    c = resume["cellules"]
    dire(f"état initial {resume['annee']} : {resume['arbres']} instances en {resume['tuiles']} tuile(s), "
         f"{resume['modeles']} modèles génériques, {resume['fiches']} fiche(s) de {c['cellules']} cellule(s) "
         f"(sans station : {c['sans_station']}, sans type de végétation : {c['sans_vegetation']}, sans H0 : {c['sans_h0']}), "
         "1 COG ; tous les contrats assets.* conformes")
    return SORTIE_OK


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(prog="assets", exit_on_error=False)
    analyseur.add_argument("--config", default="config.yml", help="chemin de config.yml")
    try:
        options = analyseur.parse_args(argv)
    except (argparse.ArgumentError, SystemExit):
        return SORTIE_IMPOSSIBLE
    return executer(options.config)


if __name__ == "__main__":
    sys.exit(main())
