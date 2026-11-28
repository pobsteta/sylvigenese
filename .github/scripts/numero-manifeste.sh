#!/bin/sh
# Étiquette de release -> numéro des manifestes (mission 090, décision de Pascal du 28/11/2026). Seul endroit où
# la conversion est écrite ; utilisé par aligner-version.sh, verifier-version.sh et controler-version-pr.sh.
# Usage : numero-manifeste.sh vAAAA.MM.N   (ex. v2026.11.19 -> 2026.11.19 ; v2027.01.1 -> 2027.1.1)
# Pourquoi : l'étiquette garde le mois sur deux chiffres (tri lisible), mais Cargo, npm (semver strict) et PEP 440
# normalisent ou refusent un zéro en tête (« invalid leading zero » pour Cargo) : les manifestes portent le mois
# sans zéro en tête. Les deux formes se déduisent l'une de l'autre sans ambiguïté (le mois est toujours 1 à 12).
# Sortie standard : le numéro. Code 2, rien sur stdout, message sur stderr si l'étiquette est mal formée :
# pas de « v », année pas sur quatre chiffres, mois hors 01-12, compteur nul, avec zéro en tête ou non numérique.
set -eu
TAG="${1:-}"
refus() { echo "numéro des manifestes : étiquette invalide '$TAG' (attendu vAAAA.MM.N : MM de 01 à 12, N entier sans zéro en tête, à partir de 1)" >&2; exit 2; }
case "$TAG" in
  v[0-9][0-9][0-9][0-9].[0-9][0-9].[1-9]|v[0-9][0-9][0-9][0-9].[0-9][0-9].[1-9]*[0-9]) ;;
  *) refus ;;
esac
R=${TAG#v}
AN=${R%%.*}
R=${R#*.}
MM=${R%%.*}
N=${R#*.}
case "$N" in *[!0-9]*) refus ;; esac
case "$MM" in
  0[1-9]) M=${MM#0} ;;
  1[0-2]) M=$MM ;;
  *) refus ;;
esac
echo "$AN.$M.$N"
