#!/usr/bin/env bash
# Banc d'essai (mission 005) : lancement rejouable et portable. Un essai à la fois.
#
# Usage : bench/results/run_bench.sh [CHECK|A|B|ROB|CMP|ALL]
#   CHECK : vérifie les outils, écrit machine.json, puis s'arrête
#   A     : toutes les variantes à N=500 et 1000 (Y=100)
#   B     : montée en taille N=2000, 4000, 8000 (Y=10, extrapolé à 100 ans)
#   ROB   : robustesse à N=200 (--inject-nan 5, --hmax-zero, graines invalides)
#   CMP   : écarts relatifs entre variantes sur summary.csv (ecarts.csv)
#   ALL   : CHECK, A, B, ROB, CMP (défaut)
#
# Variables d'environnement (facultatives) :
#   BENCH_TMP     dossier des sorties lourdes (défaut : ${TMPDIR:-/tmp}/sylvigenese-banc)
#   BENCH_LIMIT_S plafond par essai en secondes (défaut 2700 = 45 min)
#   BENCH_RSS_PCT part de la mémoire totale au-delà de laquelle l'essai est tué (défaut 85)
#   BENCH_OUT     dossier des résultats (défaut : bench/results à côté du script)
#
# Mémoire : aucune limite `ulimit -v`. Un garde surveille la mémoire résidente (RSS) de
# l'essai dans /proc (via ps) et le tue au-delà de BENCH_RSS_PCT % de la mémoire totale ;
# le statut est alors « hors mémoire (garde RSS) ». Sont aussi « hors mémoire » : code de
# sortie 4 (SPEC AM3, mémoire insuffisante interceptée) et 137 (tué par l'OOM du noyau).
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RES="${BENCH_OUT:-$ROOT/bench/results}"
TMP="${BENCH_TMP:-${TMPDIR:-/tmp}/sylvigenese-banc}"
LIMIT="${BENCH_LIMIT_S:-2700}"
RSS_PCT="${BENCH_RSS_PCT:-85}"
CSV="$RES/mesures.csv"; IDENT="$RES/identite.csv"; ROBCSV="$RES/robustesse.csv"
SUMDIR="$TMP/sum"
VARIANTS="rust py-numpy py-numba r-base r-rcpp"
NP=$(nproc 2>/dev/null || echo 1)
PC=$(lscpu -p=socket,core 2>/dev/null | grep -v '^#' | sort -u | wc -l); [ "${PC:-0}" -ge 1 ] || PC=$NP
TLIST=$(printf '%s\n' 1 "$PC" "$NP" | sort -nu | tr '\n' ' ')   # T = 1, cœurs physiques, nproc (dédoublonnés)
MEM_KB=$(awk '/^MemTotal:/{print $2}' /proc/meminfo)
TIME_BIN=/usr/bin/time
mkdir -p "$TMP" "$SUMDIR" "$RES"

check_tools() {
  local miss=()
  command -v cargo >/dev/null || miss+=("cargo (Rust) : installez rustup ou le paquet apt « cargo », puis lancez « cd bench/rust && cargo build --release »")
  [ -x "$ROOT/bench/rust/target/release/bench-sim" ] || miss+=("binaire bench/rust/target/release/bench-sim absent : lancez « cd bench/rust && cargo build --release »")
  command -v Rscript >/dev/null || miss+=("R (Rscript) : apt install r-base-core")
  if command -v Rscript >/dev/null; then
    for p in Rcpp RcppParallel testthat jsonlite; do
      Rscript -e "quit(status = !requireNamespace('$p', quietly = TRUE))" >/dev/null 2>&1 || miss+=("paquet R $p : apt install r-cran-$(echo $p | tr 'A-Z' 'a-z')")
    done
  fi
  command -v g++ >/dev/null || miss+=("g++ (compilation de Rcpp) : apt install g++")
  command -v python3 >/dev/null || miss+=("python3 : apt install python3 python3-pip")
  if command -v python3 >/dev/null; then
    python3 -I - "$ROOT/bench/python/requirements.txt" <<'PY' >"$TMP/py_missing.txt" 2>&1
import sys, importlib.metadata as m
for l in open(sys.argv[1]):
    l = l.strip()
    if not l or l.startswith("#"): continue
    name, _, ver = l.partition("==")
    try:
        got = m.version(name)
        if ver and got != ver: print(f"paquet Python {name} : version {got} installée, {ver} attendue (pip install -r bench/python/requirements.txt)")
    except m.PackageNotFoundError:
        print(f"paquet Python {name} absent (pip install -r bench/python/requirements.txt)")
PY
    while IFS= read -r l; do [ -n "$l" ] && miss+=("$l"); done < "$TMP/py_missing.txt"
  fi
  if [ ! -x "$TIME_BIN" ] || ! "$TIME_BIN" -v true >/dev/null 2>&1; then
    miss+=("/usr/bin/time (GNU time, option -v) : apt install time")
  fi
  command -v setsid >/dev/null || miss+=("setsid (util-linux) : apt install util-linux")
  if [ ${#miss[@]} -gt 0 ]; then
    echo "Il manque des éléments pour lancer le banc :" >&2
    for m in "${miss[@]}"; do echo "  - $m" >&2; done
    return 1
  fi
  echo "Outils présents."
}

write_machine() {
  python3 -I - "$RES/machine.json" "$NP" "$MEM_KB" "$PC" "$TLIST" <<'PY'
import json, sys, platform, subprocess, datetime
def sh(c):
    try: return subprocess.run(c, shell=True, capture_output=True, text=True).stdout.strip()
    except Exception: return ""
cpu = sh("grep -m1 'model name' /proc/cpuinfo | cut -d: -f2").strip()
json.dump({
  "date": datetime.datetime.now().isoformat(timespec="seconds"),
  "cores_nproc": int(sys.argv[2]),
  "cores_physiques": int(sys.argv[4]),
  "mem_total_mb": round(int(sys.argv[3]) / 1024),
  "cpu_model": cpu,
  "kernel": platform.release(),
  "os": sh("grep PRETTY_NAME /etc/os-release | cut -d= -f2 | tr -d '\"'"),
  "python": sh("python3 --version"),
  "R": sh("R --version | head -1"),
  "rustc": sh("rustc --version"),
  "gxx": sh("g++ --version | head -1"),
  "threads_tested": [int(x) for x in sys.argv[5].split()],
}, open(sys.argv[1], "w"), indent=2, ensure_ascii=False)
PY
}

[ -f "$CSV" ]   || echo "variant,n,years,threads,exit_code,init_s,step_mean_s,total_s,total_100y_s,extrapole,write_s,max_rss_mb,status,wall_s" > "$CSV"
[ -f "$IDENT" ] || echo "variant,n,years,threads_cmp,state_final,summary" > "$IDENT"

cmd() { # variant n years threads out [extra...]
  local v=$1 n=$2 y=$3 t=$4 o=$5; shift 5
  case $v in
    rust) echo "$ROOT/bench/rust/target/release/bench-sim --n $n --years $y --seed 42 --threads $t --out $o $*";;
    py-*) echo "python3 $ROOT/bench/python/sim.py --variant $v --n $n --years $y --seed 42 --threads $t --out $o $*";;
    r-*)  echo "Rscript $ROOT/bench/r/sim.R --variant $v --n $n --years $y --seed 42 --threads $t --out $o $*";;
  esac
}

# Lance « $@ » dans son propre groupe de processus, avec un garde RSS et un plafond de temps.
# Écrit $o/time.txt (GNU time -v) et $o/killed (« rss » ou « temps ») si le garde a tué.
guarded() { # out_dir cmd...
  local o=$1; shift
  rm -f "$o/killed" "$o/pgid"
  setsid -w bash -c 'echo $$ > "$1"; shift; exec "$@"' _ "$o/pgid" \
     "$TIME_BIN" -v -o "$o/time.txt" timeout "$LIMIT" "$@" >"$o/stdout.txt" 2>"$o/stderr.txt" &
  local pid=$! pg="" t0=$SECONDS
  while kill -0 $pid 2>/dev/null; do
    sleep 1
    [ -z "$pg" ] && [ -s "$o/pgid" ] && pg=$(cat "$o/pgid")
    if [ -n "$pg" ]; then
      local rss; rss=$(ps -eo pgid=,rss= | awk -v g="$pg" '$1==g{s+=$2}END{print s+0}')
      if [ "$rss" -gt $((MEM_KB * RSS_PCT / 100)) ]; then
        echo rss > "$o/killed"; kill -KILL -- "-$pg" 2>/dev/null; break
      fi
    fi
  done
  wait $pid 2>/dev/null
  return $?
}

run() { # variant n years threads -> ligne CSV ; code retour 0 si ok
  local v=$1 n=$2 y=$3 t=$4 o="$TMP/out_${1}_${2}_${4}"
  rm -rf "$o"; mkdir -p "$o"
  guarded "$o" $(cmd $v $n $y $t $o)
  local ec=$?
  python3 -I - "$v" "$n" "$y" "$t" "$ec" "$o" "$CSV" <<'PY'
import sys, json, os, re
v, n, y, t, ec, o, csv = sys.argv[1:8]; ec = int(ec); y = int(y)
rss = wall = ""
try:
    tx = open(o + "/time.txt").read()
    m = re.search(r"Maximum resident set size \(kbytes\): (\d+)", tx)
    if m: rss = "%.1f" % (int(m.group(1)) / 1024)
    m = re.search(r"Elapsed \(wall clock\) time \(h:mm:ss or m:ss\): ([\d:.]+)", tx)
    if m:
        p = [float(x) for x in m.group(1).split(":")]
        wall = "%.3f" % sum(x * 60 ** i for i, x in enumerate(reversed(p)))
except FileNotFoundError: pass
init = step = tot = wr = t100 = ""; extra = "non"; status = "ok"
killed = os.path.exists(o + "/killed")
if ec == 0 and os.path.exists(o + "/timing.json"):
    j = json.load(open(o + "/timing.json")); init = j["init_s"]; step = j["step_mean_s"]; tot = j["total_s"]; wr = j["write_s"]
    if y == 100: t100 = tot
    else: t100 = init + 100 * step; extra = "oui"
else:
    if killed: status = "hors mémoire (garde RSS)"
    elif ec == 124: status = "hors temps"
    elif ec == 4: status = "hors mémoire"
    elif ec == 137: status = "hors mémoire (tué par l'OOM : code 137)"
    else: status = "erreur"
open(csv, "a").write(",".join(map(str, [v, n, y, t, ec, init, step, tot, t100, extra, wr, rss, status, wall])) + "\n")
print(v, n, y, t, "->", status, "exit", ec, "rss", rss, "total", tot, "wall", wall, flush=True)
PY
  return $ec
}

blocked() { awk -F, -v v="$1" '$1==v && ($13 ~ /^hors/ || $13=="erreur"){f=1} END{exit !f}' "$CSV"; }
skip_row() { echo "$1,$2,$3,$4,,,,,,,,,sauté (taille inférieure hors mémoire/hors temps/erreur)," >> "$CSV"; }

pair() { # variant n years : T=1 puis chaque autre T de TLIST ; identité ; garde summary T=1
  local v=$1 n=$2 y=$3 t
  if blocked $v; then for t in $TLIST; do skip_row $v $n $y $t; done; return; fi
  if run $v $n $y 1; then
    cp "$TMP/out_${v}_${n}_1/summary.csv" "$SUMDIR/${v}_${n}.csv"
    for t in $TLIST; do
      [ "$t" = 1 ] && continue
      if run $v $n $y $t; then
        local a=$TMP/out_${v}_${n}_1 b=$TMP/out_${v}_${n}_$t s=identique m=identique
        cmp -s $a/state_final.f32 $b/state_final.f32 || s=DIFFERENT
        cmp -s $a/summary.csv $b/summary.csv || m=DIFFERENT
        echo "$v,$n,$y,1_vs_$t,$s,$m" >> "$IDENT"
      fi
      rm -f "$TMP/out_${v}_${n}_$t/state_final.f32"
    done
  else
    for t in $TLIST; do [ "$t" = 1 ] || skip_row $v $n $y $t; done
  fi
  rm -f "$TMP"/out_${v}_${n}_*/state_final.f32
}

phaseA() {
  # échauffement : compilation numba et C++ (Rcpp) hors chronomètre
  python3 $ROOT/bench/python/sim.py --variant py-numba --n 100 --years 2 --threads $NP --out $TMP/warm_nb >/dev/null 2>&1
  Rscript $ROOT/bench/r/sim.R --variant r-rcpp --n 100 --years 2 --threads 1 --out $TMP/warm_r >/dev/null 2>&1
  for n in 500 1000; do for v in $VARIANTS; do pair $v $n 100; done; done
}
phaseB() { for v in $VARIANTS; do for n in 2000 4000 8000; do pair $v $n 10; done; done; }

phaseROB() {
  [ -f "$ROBCSV" ] || echo "variant,test,exit_code,attendu,conforme,message" > "$ROBCSV"
  local v t o
  for v in $VARIANTS; do
    for t in "inject-nan|--inject-nan 5|3" "hmax-zero|--hmax-zero|2" "seed -1|--seed -1|2" "seed 1.5|--seed 1.5|2" "seed 2^53|--seed 9007199254740992|2"; do
      IFS='|' read -r name opt want <<<"$t"
      o=$TMP/rob_$v; rm -rf "$o"; mkdir -p "$o"
      # la graine par défaut (42) est fournie par cmd ; pour les tests de graine, on retire la nôtre
      local c; c=$(cmd $v 200 20 1 $o $opt)
      case $name in seed*) c=$(echo "$c" | sed 's/--seed 42 //');; esac
      ( timeout 600 $c >"$o/out.txt" 2>"$o/err.txt" ); local ec=$?
      python3 -I - "$v" "$name" "$ec" "$want" "$o" "$ROBCSV" <<'PY'
import sys, csv
v, name, ec, want, o, out = sys.argv[1:7]
txt = " ".join(l.strip() for f in ("out.txt", "err.txt") for l in open(f"{o}/{f}", errors="replace") if l.strip() and not l.startswith("[py-numba]"))
txt = txt[:300]
csv.writer(open(out, "a", newline="")).writerow([v, name, ec, want, "oui" if int(ec) == int(want) else "NON", txt])
PY
    done
  done
}

phaseCMP() {
  python3 -I - "$SUMDIR" "$RES/ecarts.csv" <<'PY'
import sys, os, csv, itertools, collections
d, out = sys.argv[1:3]
files = collections.defaultdict(dict)
for f in os.listdir(d):
    v, n = f[:-4].rsplit("_", 1); files[int(n)][v] = os.path.join(d, f)
def load(p):
    r = list(csv.DictReader(open(p))); return r
rows = []
for n in sorted(files):
    for a, b in itertools.combinations(sorted(files[n]), 2):
        A, B = load(files[n][a]), load(files[n][b])
        if len(A) != len(B): rows.append([n, a, b, "lignes différentes", ""]); continue
        worst, col = 0.0, ""
        for x, y in zip(A, B):
            for c in ("sum_B", "sum_D", "mean_H"):
                u, w = float(x[c]), float(y[c]); den = max(abs(u), abs(w))
                e = 0.0 if den == 0 else abs(u - w) / den
                if e > worst: worst, col = e, f"{c} (année {x['year']}, essence {x['species']})"
        rows.append([n, a, b, "%.3e" % worst, col])
w = csv.writer(open(out, "w", newline="")); w.writerow(["n", "variante_a", "variante_b", "ecart_relatif_max", "ou"]); w.writerows(rows)
print(open(out).read())
PY
}

case "${1:-ALL}" in
  CHECK) check_tools && write_machine;;
  A) phaseA;; B) phaseB;; ROB) phaseROB;; CMP) phaseCMP;;
  ALL) check_tools || exit 1; write_machine; phaseA; phaseB; phaseROB; phaseCMP;;
  *) echo "Usage : $0 [CHECK|A|B|ROB|CMP|ALL]" >&2; exit 2;;
esac
