#!/usr/bin/env bash
# Banc d'essai, mission 005 : lancement rejouable. Un essai à la fois.
# Usage : bench/results/run_bench.sh [A|B|ROB|ALL]
#   A   : toutes les variantes à N=500 et 1000 (Y=100)
#   B   : montée en taille 2000, 4000, 8000 (Y=10), variante par variante
#   ROB : robustesse à N=200 (--inject-nan 5, --hmax-zero)
# Ajoute au CSV après chaque essai. Plafond 45 min par essai, limite mémoire virtuelle 14 Go.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RES="$ROOT/bench/results"
TMP=/tmp/claude-0/banc
CSV="$RES/mesures.csv"
IDENT="$RES/identite.csv"
ROBCSV="$RES/robustesse.csv"
SUMDIR="$TMP/sum"
LIMIT=2700
VARIANTS="rust py-numpy py-numba r-base r-rcpp"
mkdir -p "$TMP" "$SUMDIR"
[ -f "$CSV" ] || echo "variant,n,years,threads,exit_code,init_s,step_mean_s,total_s,total_100y_s,extrapole,write_s,max_rss_mb,status" > "$CSV"
[ -f "$IDENT" ] || echo "variant,n,years,state_final_1v4,summary_1v4" > "$IDENT"
[ -f "$ROBCSV" ] || echo "variant,test,exit_code,message" > "$ROBCSV"

cmd() { # variant n years threads out [extra...]
  local v=$1 n=$2 y=$3 t=$4 o=$5; shift 5
  case $v in
    rust) echo "$ROOT/bench/rust/target/release/bench-sim --n $n --years $y --seed 42 --threads $t --out $o $*";;
    py-*) echo "python3 $ROOT/bench/python/sim.py --variant $v --n $n --years $y --seed 42 --threads $t --out $o $*";;
    r-*)  echo "Rscript $ROOT/bench/r/sim.R --variant $v --n $n --years $y --seed 42 --threads $t --out $o $*";;
  esac
}

run() { # variant n years threads  -> écrit une ligne CSV ; code retour 0 si ok
  local v=$1 n=$2 y=$3 t=$4 o="$TMP/out_${1}_${2}_${4}"
  rm -rf "$o"; mkdir -p "$o"
  ( ulimit -v 14000000; /usr/bin/time -v -o "$o/time.txt" timeout $LIMIT $(cmd $v $n $y $t $o) >"$o/stdout.txt" 2>"$o/stderr.txt" )
  local ec=$?
  local rss; rss=$(awk -F: '/Maximum resident/{printf "%.1f",$2/1024}' "$o/time.txt" 2>/dev/null)
  python3 -I - "$v" "$n" "$y" "$t" "$ec" "${rss:-}" "$o" "$CSV" <<'PY'
import sys,json,os
v,n,y,t,ec,rss,o,csv=sys.argv[1:9]; ec=int(ec); y=int(y)
init=step=tot=wr=""; t100=""; extra="non"; status="ok"
if ec==0 and os.path.exists(o+"/timing.json"):
    j=json.load(open(o+"/timing.json")); init=j["init_s"]; step=j["step_mean_s"]; tot=j["total_s"]; wr=j["write_s"]
    if y==100: t100=tot
    else: t100=init+100*step; extra="oui"
else:
    err=open(o+"/stderr.txt",errors="replace").read().lower()
    if ec==124: status="hors temps"
    elif ec==137 or "memory" in err or "mémoire" in err or "alloc" in err or "cannot allocate" in err: status="hors mémoire"
    else: status="erreur"
open(csv,"a").write(",".join(map(str,[v,n,y,t,ec,init,step,tot,t100,extra,wr,rss,status]))+"\n")
print(v,n,y,t,"->",status,"exit",ec,"rss",rss,"total",tot)
PY
  return $ec
}

blocked() { # variant n : vrai si une taille inférieure a échoué (hors mémoire/temps/erreur)
  grep -E "^$1,[0-9]+,[0-9]+,[0-9]+,[0-9]+,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,(hors|erreur)" "$CSV" >/dev/null
}

skip_row() { echo "$1,$2,$3,$4,,,,,,,,,sauté (taille inférieure hors mémoire/hors temps)" >> "$CSV"; }

pair() { # variant n years : T=1 puis T=4, identité, garde summary T=1
  local v=$1 n=$2 y=$3
  if blocked $v; then skip_row $v $n $y 1; skip_row $v $n $y 4; return; fi
  if run $v $n $y 1; then
    cp "$TMP/out_${v}_${n}_1/summary.csv" "$SUMDIR/${v}_${n}.csv"
    if run $v $n $y 4; then
      local a=$TMP/out_${v}_${n}_1 b=$TMP/out_${v}_${n}_4 s=identique m=identique
      cmp -s $a/state_final.f32 $b/state_final.f32 || s=DIFFERENT
      cmp -s $a/summary.csv $b/summary.csv || m=DIFFERENT
      echo "$v,$n,$y,$s,$m" >> "$IDENT"
    fi
  else
    skip_row $v $n $y 4
  fi
  rm -f $TMP/out_${v}_${n}_*/state_final.f32
}

phaseA() {
  # échauffement : compilation numba et C++ hors chronomètre
  python3 $ROOT/bench/python/sim.py --variant py-numba --n 100 --years 2 --threads 4 --out $TMP/warm_nb >/dev/null 2>&1
  Rscript $ROOT/bench/r/sim.R --variant r-rcpp --n 100 --years 2 --threads 1 --out $TMP/warm_r >/dev/null 2>&1
  for n in 500 1000; do for v in $VARIANTS; do pair $v $n 100; done; done
}
phaseB() { for v in $VARIANTS; do for n in 2000 4000 8000; do pair $v $n 10; done; done; }
phaseROB() {
  for v in $VARIANTS; do
    for opt in "--inject-nan 5" "--hmax-zero"; do
      o=$TMP/rob_$v; rm -rf $o; mkdir -p $o
      ( ulimit -v 14000000; timeout 600 $(cmd $v 200 20 1 $o $opt) >$o/out.txt 2>$o/err.txt ); ec=$?
      msg=$(cat $o/out.txt $o/err.txt | grep -v '^$' | grep -v '^Warning\|^Exécution\|Loading' | head -3 | tr '\n,' ' ;' )
      echo "$v,\"$opt\",$ec,\"$msg\"" >> "$ROBCSV"
    done
  done
}
case "${1:-ALL}" in A) phaseA;; B) phaseB;; ROB) phaseROB;; ALL) phaseA; phaseB; phaseROB;; esac
