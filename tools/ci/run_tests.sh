#!/usr/bin/env bash
# Tous les tests du projet, dans l'ordre : R, Rust, Python et Node (make test), pytest des
# contrats et des fixtures, tests d'acceptation de M1a (tests/m1), puis le validateur sur le
# jeu fictif (spec §11).
# Appelé par .claude/test-command (hook du plugin, lancé par « sh -c ») et par la CI.
# Le bash et pipefail sont ici et non dans test-command : sous dash, « a | tee » masquerait l'échec de a.
# Tout saut de test pytest est un échec (un test sauté sans le dire n'est pas un test passé).
# SYLVIGENESE_PYTEST_EXTRA : chemins pytest supplémentaires (sert à prouver que l'échec remonte).
#
# Sans argument : toutes les sections, dans l'ordre historique (c'est ce que lance
# .claude/test-command, donc le poste local).
# Avec des arguments : seulement ces sections, dans l'ordre donné (la CI en fait un job par
# groupe, mission 043). Sections :
#   r        testthat (make test-r)
#   rust     cargo test (make test-rust)
#   python   pytest python (make test-python)
#   web      node --test (make test-web)
#   contrats pytest tests/contracts, contracts/tests, tools/fixtures/tests, tools/referentiels/tests
#            et python
#   m1 m2 m4 m3   tests d'acceptation des jalons, une session pytest chacun
#            (m3 et m4 compilent d'abord simulate en release : leurs tests tournent sans réseau)
#   post     tests d'acceptation de post, volume et carbone (mission 052) : chaîne R, simulate sur 5 ans,
#            post et assets, sans réseau (simulate compilé d'abord, comme pour m3 et m4) ; la fiche v3 y est aussi
#            vérifiée dans le navigateur (mission 057 : Node, Playwright et Chromium requis, comme pour m4)
#   validate le validateur sur le jeu fictif
# Chaque section écrit sa durée (sortie standard et, en CI, résumé du job).
set -euo pipefail
cd "$(dirname "$0")/../.."

ALL_SECTIONS=(r rust python web contrats m1 m2 m4 m3 post validate)

out="$(mktemp)"
current=""
started=0
trap 'rm -f "$out"; report_duration "interrompue ou en échec"' EXIT

# Écrit la durée de la section en cours (si une l'est), puis l'oublie.
report_duration() {
  [ -n "$current" ] || return 0
  local s=$(( SECONDS - started )) line
  line="Durée de la section « $current » : $((s / 60)) min $((s % 60)) s (${s} s) — ${1:-terminée}"
  echo "== $line"
  if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
    echo "- $line" >> "$GITHUB_STEP_SUMMARY"
  fi
  current=""
}

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

# Compile simulate en release (la cible de `make simulate`), avec le réseau.
# Les tests de M3 et M4 lancent `make simulate` sans réseau : offline_env() de tests/m3/helpers_m3.py
# et tests/m4/helpers_m4.py met http_proxy, https_proxy, HTTP_PROXY, HTTPS_PROXY, ALL_PROXY et all_proxy
# à http://127.0.0.1:9 (proxy mort, cas terrain « absence de réseau »). cargo n'y peut pas télécharger
# les crates. Dans le parcours complet, make test-rust remplissait le registre avant ; un job qui ne
# lance que m3 ou m4 (CI découpée, mission 043) partait d'un registre vide : tous ses tests échouaient.
build_simulate() {
  cargo fetch --locked --manifest-path simulate/Cargo.toml
  cargo build --release --locked --manifest-path simulate/Cargo.toml
}

run_section() {
  case "$1" in
    r)        make test-r ;;
    rust)     make test-rust ;;
    python)   make test-python ;;
    web)      make test-web ;;
    contrats)
      # shellcheck disable=SC2086
      run_pytest tests/contracts contracts/tests tools/fixtures/tests tools/referentiels/tests python ${SYLVIGENESE_PYTEST_EXTRA:-} ;;
    # Tests d'acceptation du jalon M1a (mission 021) : session séparée, car leurs modules
    # d'aide portent le même nom que ceux des contrats (helpers.py).
    m1)       run_pytest tests/m1 ;;
    m2)       run_pytest tests/m2 ;;
    m4)       build_simulate; run_pytest tests/m4 ;;
    m3)       build_simulate; run_pytest tests/m3 ;;
    post)     build_simulate; run_pytest tests/post ;;
    validate) make validate ZONE=zone_fictive ;;
    *)
      echo "run_tests.sh : section inconnue « $1 » (attendu : ${ALL_SECTIONS[*]})." >&2
      exit 2 ;;
  esac
}

if [ "$#" -eq 0 ]; then
  set -- "${ALL_SECTIONS[@]}"
fi

# Contrôle de tous les noms avant de lancer quoi que ce soit.
for s in "$@"; do
  case " ${ALL_SECTIONS[*]} " in
    *" $s "*) ;;
    *) echo "run_tests.sh : section inconnue « $s » (attendu : ${ALL_SECTIONS[*]})." >&2; exit 2 ;;
  esac
done

for s in "$@"; do
  current="$s"
  started=$SECONDS
  echo "== section « $s » : début"
  run_section "$s"
  report_duration
done
