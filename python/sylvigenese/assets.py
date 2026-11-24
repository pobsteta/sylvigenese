"""Module `assets` (spec §2) : squelette de la mission 012.

Étape visée plus tard : génération des modèles glTF, des tuiles 3D, des fiches de cellule
et des rasters web. Sorties prévues : `assets/trees/*.glb`, `tiles/<année>/tileset.json`,
`web/cells/*.json`, `web/rasters/*.tif`, `massif/<bloc>.json`.
Pour l'instant : lit config.yml et fait valider ce fichier.
"""

import sys

from sylvigenese.commun import main_module


def main(argv: list[str] | None = None) -> int:
    return main_module("assets", argv)


if __name__ == "__main__":
    sys.exit(main())
