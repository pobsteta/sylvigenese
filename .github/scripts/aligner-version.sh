#!/bin/sh
# Met les manifestes au numéro de la prochaine release (mission 087, décision de Pascal du 27/11/2026).
# Usage : aligner-version.sh [AAAA.MM]   (défaut : mois courant, UTC ; lancé depuis le dépôt)
# Le numéro est celui de version-calendaire.sh, sans le « v » (ex. v2026.11.18 -> 2026.11.18) ; il est écrit dans
# simulate/Cargo.toml, simulate/Cargo.lock (ligne du paquet simulate), python/pyproject.toml et DESCRIPTION.
# Geste à faire dans chaque PR qui change le produit : release.yml refuse de poser l'étiquette si les manifestes
# ne portent pas le numéro qu'il calcule (verifier-version.sh).
# Refus (code 1, rien n'est écrit) : un manifeste sans ligne de version lisible, ou des étiquettes locales en
# retard sur celles de origin (faire « git fetch --tags » d'abord). origin illisible : signalé, on continue avec
# les étiquettes locales.
set -eu
D="$(cd "$(dirname "$0")" && pwd)"
. "$D/manifestes-version.sh"
cd "$(git rev-parse --show-toplevel)"

TAG=$("$D/version-calendaire.sh" "$@")
VERSION=${TAG#v}
MOIS=${VERSION%.*}

# Étiquettes de origin : le numéro calculé ne doit pas déjà y être pris.
if DISTANTES=$(git ls-remote --tags origin "refs/tags/v$MOIS.*" 2>/dev/null); then
  DERNIER=$(printf '%s\n' "$DISTANTES" | sed -n "s|^[0-9a-f]*[[:space:]]*refs/tags/v$MOIS\.\([0-9][0-9]*\)$|\1|p" | sort -n | tail -n 1)
  if [ -n "$DERNIER" ] && [ "$DERNIER" -ge "${VERSION##*.}" ]; then
    echo "aligner-version : origin porte déjà v$MOIS.$DERNIER, les étiquettes locales sont en retard : faire « git fetch --tags » puis relancer. Rien n'est écrit." >&2
    exit 1
  fi
else
  echo "aligner-version : signalement : origin illisible, numéro calculé sur les seules étiquettes locales ($TAG)." >&2
fi

for f in $MANIFESTES; do
  if [ ! -f "$f" ]; then
    echo "aligner-version : $f absent. Rien n'est écrit." >&2; exit 1
  fi
  if [ -z "$(version_de "$f")" ]; then
    echo "aligner-version : pas de ligne de version lisible dans $f. Rien n'est écrit." >&2; exit 1
  fi
done

ecrire() { # fichier commande-sed
  sed "$2" "$1" > "$1.aligner" && mv "$1.aligner" "$1"
}
ecrire simulate/Cargo.toml "1,/^version = /s/^version = \".*\"$/version = \"$VERSION\"/"
ecrire python/pyproject.toml "1,/^version = /s/^version = \".*\"$/version = \"$VERSION\"/"
ecrire simulate/Cargo.lock "/^name = \"simulate\"$/{n;s/^version = \".*\"$/version = \"$VERSION\"/;}"
ecrire DESCRIPTION "s/^Version: .*$/Version: $VERSION/"

for f in $MANIFESTES; do
  if [ "$(version_de "$f")" != "$VERSION" ]; then
    echo "aligner-version : $f porte « $(version_de "$f") » après écriture, attendu $VERSION." >&2; exit 1
  fi
done
echo "manifestes alignés sur $VERSION (prochaine release $TAG)"
