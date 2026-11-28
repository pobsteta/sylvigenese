#!/bin/sh
# Garde de release (mission 087) : les manifestes portent-ils le numéro de l'étiquette à poser ?
# Usage : verifier-version.sh vAAAA.MM.N   (lancé depuis le dépôt, sur le commit à étiqueter)
# Code 0 si les manifestes de manifestes-version.sh (dont les package.json, mission 089) portent AAAA.MM.N.
# Code 1 sinon, chaque manifeste en retard nommé avec sa valeur (release.yml ne pose alors aucune étiquette).
# Le numéro attendu est celui de numero-manifeste.sh (mois sans zéro en tête : v2027.01.1 -> 2027.1.1).
# Code 2 si l'étiquette n'a pas la forme vAAAA.MM.N (MM de 01 à 12).
set -eu
D="$(cd "$(dirname "$0")" && pwd)"
. "$D/manifestes-version.sh"
TAG="${1:-}"
if ! VERSION=$("$D/numero-manifeste.sh" "$TAG" 2>/dev/null); then
  echo "garde de release : étiquette invalide '$TAG' (attendu vAAAA.MM.N, MM de 01 à 12)" >&2; exit 2
fi
cd "$(git rev-parse --show-toplevel)"

EN_RETARD=""
for f in $MANIFESTES; do
  if [ -f "$f" ]; then V=$(version_de "$f"); else V="(fichier absent)"; fi
  [ -n "$V" ] || V="(version illisible)"
  if [ "$V" != "$VERSION" ]; then
    EN_RETARD="$EN_RETARD
  - $f porte « $V »"
  fi
done
if [ -n "$EN_RETARD" ]; then
  echo "garde de release : refus, aucune étiquette posée : les manifestes ne portent pas $VERSION (release $TAG) :$EN_RETARD
  Lancer .github/scripts/aligner-version.sh dans une PR, puis la fusionner." >&2
  exit 1
fi
echo "garde de release : les manifestes portent $VERSION"
