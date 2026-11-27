#!/bin/sh
# Lecture des versions portées par les manifestes (mission 087), à sourcer par aligner-version.sh et
# verifier-version.sh. Les manifestes : simulate/Cargo.toml (et sa ligne de simulate/Cargo.lock),
# python/pyproject.toml, DESCRIPTION. Ceux des bancs (bench/) ne sont pas concernés.
# Chemins relatifs à la racine du dépôt (le dossier courant des appelants).
MANIFESTES="simulate/Cargo.toml simulate/Cargo.lock python/pyproject.toml DESCRIPTION"

# version_de FICHIER : la version écrite dans FICHIER (vide si elle n'y est pas trouvée).
version_de() {
  case "$1" in
    */Cargo.toml|python/pyproject.toml) sed -n 's/^version = "\(.*\)"$/\1/p' "$1" | head -n 1 ;;
    */Cargo.lock) sed -n '/^name = "simulate"$/{n;s/^version = "\(.*\)"$/\1/p;}' "$1" | head -n 1 ;;
    DESCRIPTION) sed -n 's/^Version: *\(.*\)$/\1/p' "$1" | head -n 1 ;;
    *) echo "" ;;
  esac
}
