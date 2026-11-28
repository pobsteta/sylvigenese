#!/bin/sh
# Lecture des versions portées par les manifestes (mission 087), à sourcer par aligner-version.sh et
# verifier-version.sh. Les manifestes : simulate/Cargo.toml (et sa ligne de simulate/Cargo.lock),
# python/pyproject.toml, DESCRIPTION, et (mission 089) les deux paquets Node : tools/ci/ et viewer-web/ (package.json et
# package-lock.json, champ « version » seulement). Ceux des bancs (bench/) ne sont pas concernés.
# Chemins relatifs à la racine du dépôt (le dossier courant des appelants).
MANIFESTES="simulate/Cargo.toml simulate/Cargo.lock python/pyproject.toml DESCRIPTION tools/ci/package.json tools/ci/package-lock.json viewer-web/package.json viewer-web/package-lock.json"

# version_de FICHIER : la version écrite dans FICHIER (vide si elle n'y est pas trouvée).
version_de() {
  case "$1" in
    */Cargo.toml|python/pyproject.toml) sed -n 's/^version = "\(.*\)"$/\1/p' "$1" | head -n 1 ;;
    */Cargo.lock) sed -n '/^name = "simulate"$/{n;s/^version = "\(.*\)"$/\1/p;}' "$1" | head -n 1 ;;
    */package.json) sed -n 's/^  "version": "\(.*\)",\{0,1\}$/\1/p' "$1" | head -n 1 ;;
    */package-lock.json) # version de tête, et celle de packages[""] : si elles diffèrent, « a / b » (jamais égal au numéro)
      A=$(sed -n 's/^  "version": "\(.*\)",\{0,1\}$/\1/p' "$1" | head -n 1)
      B=$(sed -n '/^    "": {$/,/^      "version"/s/^      "version": "\(.*\)",\{0,1\}$/\1/p' "$1" | head -n 1)
      if [ "$A" = "$B" ]; then echo "$A"; else echo "$A / $B"; fi ;;
    DESCRIPTION) sed -n 's/^Version: *\(.*\)$/\1/p' "$1" | head -n 1 ;;
    *) echo "" ;;
  esac
}
