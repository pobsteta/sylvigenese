"""Module `post` (spec §2) : squelette de la mission 012.

Étape visée plus tard : volume, biomasse et carbone en post-traitement de `sim/`.
Sortie prévue : `sim/summary.parquet`, clé (cellule, année, essence).
Pour l'instant : lit config.yml et fait valider ce fichier.
"""

import sys

from sylvigenese.common import module_main


def main(argv: list[str] | None = None) -> int:
    return module_main("post", argv)


if __name__ == "__main__":
    sys.exit(main())
