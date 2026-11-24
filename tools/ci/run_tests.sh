#!/usr/bin/env bash
# Tous les tests du projet, dans l'ordre : R, Rust, Python et Node (make test), pytest des
# contrats et des fixtures, puis le validateur sur le jeu fictif (spec §11, M0).
# Appelé par .claude/test-command (hook du plugin, lancé par « sh -c ») et par la CI.
# Le bash et pipefail sont ici et non dans test-command : sous dash, « a | tee » masquerait l'échec de a.
# Tout saut de test pytest est un échec (un test sauté sans le dire n'est pas un test passé).
# SYLVIGENESE_PYTEST_EXTRA : chemins pytest supplémentaires (sert à prouver que l'échec remonte).
set -euo pipefail
cd "$(dirname "$0")/../.."

make test

out="$(mktemp)"
trap 'rm -f "$out"' EXIT
# shellcheck disable=SC2086
python3 -m pytest -q -rs -p no:cacheprovider tests/contracts contracts/tests tools/fixtures/tests python \
  ${SYLVIGENESE_PYTEST_EXTRA:-} 2>&1 | tee "$out"
code=${PIPESTATUS[0]}
if [ "$code" -ne 0 ]; then
  echo "run_tests.sh : pytest a échoué (code $code)." >&2
  exit "$code"
fi
if grep -Eaq '[0-9]+ skipped' "$out"; then
  echo "run_tests.sh : pytest a sauté des tests (terra ou rasterio absent ?) : refusé." >&2
  exit 1
fi

make validate ZONE=zone_fictive
