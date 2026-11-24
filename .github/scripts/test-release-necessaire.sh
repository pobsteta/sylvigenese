#!/bin/sh
# Tests de release-necessaire.sh : cas synthétiques dans un dépôt temporaire. Repris de pobsteta/marculus.
S="$(cd "$(dirname "$0")" && pwd)/release-necessaire.sh"
ECHECS=0
verifie() { # nom attendu obtenu
  case "$3" in "$2"*) echo "ok   $1";; *) echo "ECHEC $1 : attendu '$2', obtenu '$3'"; ECHECS=$((ECHECS+1));; esac
}
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
cd "$T" && git init -q . && git config user.email t@t && git config user.name t
commit() { git add -A && git commit -q -m "$1"; }
ecrit() { mkdir -p "$(dirname "$1")"; echo "$2" >> "$1"; }

ecrit R/prepare.R 1; commit init
verifie "aucun tag" "release:" "$("$S")"
git tag v2026.11.1
verifie "rien changé" "pas de release:" "$("$S")"
ecrit pilotage/kanban.md x; ecrit docs/a.pdf x; ecrit README.md x; commit pilotage
verifie "seulement pilotage/docs/md" "pas de release:" "$("$S")"
ecrit gama/models/sim.gaml 2; commit code
verifie "pilotage + code" "release:" "$("$S")"
git tag -f v2026.11.1 HEAD >/dev/null
ecrit .github/badges/x.svg x; commit badge
verifie "badge seul" "pas de release:" "$("$S")"
ecrit .github/workflows/release.yml x; commit workflow
verifie "workflow modifié" "release:" "$("$S")"
git tag v2026.11.2; ecrit assets/gen.py 1; commit code2; ecrit pilotage/j.md x; commit pilotage2
verifie "code puis pilotage (CI annulée)" "release:" "$("$S")"
verifie "commit inconnu" "release:" "$("$S" deadbeef)"

CODE2=$(git rev-parse HEAD)
verifie "commit = tête de main" "release:" "$("$S" HEAD "" "$CODE2")"
ecrit assets/gen.py 2; commit code3
verifie "commit dépassé par la tête" "pas de release: commit dépassé par $(git rev-parse HEAD | cut -c1-7)" "$("$S" "$CODE2" "" "$(git rev-parse HEAD)")"
verifie "tête inconnue localement (SHA brut)" "pas de release: commit dépassé par 1234567" "$("$S" HEAD "" 1234567890abcdef1234567890abcdef12345678)"
verifie "tête illisible : on publie" "release:" "$("$S" HEAD)"
git tag v2026.11.3
ecrit tests/testthat/test-prepare.R x; ecrit tests/python/test_assets.py x
ecrit .github/scripts/test-release-necessaire.sh x; commit tests
verifie "tests seuls" "pas de release:" "$("$S" HEAD "" "$(git rev-parse HEAD)")"
ecrit R/biomes.R 1; commit "test + code"
verifie "tests + code" "release:" "$("$S" HEAD "" "$(git rev-parse HEAD)")"
git tag v2026.11.4
ecrit tests/x.R x; ecrit .github/scripts/release-necessaire.sh x; commit "test + script de release"
verifie "le script de release lui-même compte" "release:" "$("$S" HEAD "" "$(git rev-parse HEAD)")"

git tag v2026.11.5; ecrit R/dynamics.R 1; commit "code D"; CODED=$(git rev-parse HEAD)
ecrit pilotage/m.md x; ecrit docs/n.md x; commit "pilotage + docs"; PILOT=$(git rev-parse HEAD)
verifie "code puis pilotage : release" "release:" "$("$S" "$CODED" "" "$PILOT")"
ecrit R/dynamics.R 2; commit "code E"; CODEE=$(git rev-parse HEAD)
verifie "code puis code : dépassé" "pas de release: commit dépassé par $(printf '%s' "$CODEE" | cut -c1-7)" "$("$S" "$CODED" "" "$CODEE")"

if [ "$ECHECS" -eq 0 ]; then echo "Tous les tests passent."; else echo "$ECHECS échec(s)."; exit 1; fi
