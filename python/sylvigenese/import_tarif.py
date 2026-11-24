"""Module `import_tarif` (spec §2, §3) : squelette de la mission 012.

Étape du BRIEF visée plus tard : import des tarifs et de l'allométrie de tarif-nemeton
(`external.tarif_nemeton_dir`, lu par ce module seul ; jamais copié dans le dépôt).
Sorties prévues : `params/tarif.parquet`, `params/allometry.parquet`.
Pour l'instant : lit config.yml et fait valider ce fichier.
"""

import sys

from sylvigenese.commun import main_module


def main(argv: list[str] | None = None) -> int:
    return main_module("import_tarif", argv)


if __name__ == "__main__":
    sys.exit(main())
