#!/usr/bin/env bash
# Tous les tests du projet, dans l'ordre : R, Rust, Python et Node (make test), pytest des
# contrats et des fixtures, tests d'acceptation de M1a (tests/m1), puis le validateur sur le
# jeu fictif (spec §11).
# Appelé par .claude/test-command (hook du plugin, lancé par « sh -c ») et par la CI.
# Le bash et pipefail sont ici et non dans test-command : sous dash, « a | tee » masquerait l'échec de a.
# Tout saut de test pytest est un échec (un test sauté sans le dire n'est pas un test passé).
# SYLVIGENESE_PYTEST_EXTRA : chemins pytest supplémentaires (sert à prouver que l'échec remonte).
set -euo pipefail
cd "$(dirname "$0")/../.."

make test

out="$(mktemp)"
trap 'rm -f "$out"' EXIT

# Lance pytest sur les chemins donnés ; échec si pytest échoue ou saute un test.
run_pytest() {
  local code
  set +e
  python3 -m pytest -q -rs -p no:cacheprovider "$@" 2>&1 | tee "$out"
  code=${PIPESTATUS[0]}
  set -e
  if [ "$code" -ne 0 ]; then
    echo "run_tests.sh : pytest a échoué (code $code) sur : $*" >&2
    exit "$code"
  fi
  if grep -Eaq '[0-9]+ skipped' "$out"; then
    echo "run_tests.sh : pytest a sauté des tests (terra ou rasterio absent ?) : refusé." >&2
    exit 1
  fi
}

# shellcheck disable=SC2086
run_pytest tests/contracts contracts/tests tools/fixtures/tests python ${SYLVIGENESE_PYTEST_EXTRA:-}
# Tests d'acceptation du jalon M1a (mission 021) : session séparée, car leurs modules
# d'aide portent le même nom que ceux des contrats (helpers.py).
run_pytest tests/m1
run_pytest tests/m2

make validate ZONE=zone_fictive
