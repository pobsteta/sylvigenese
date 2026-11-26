#!/usr/bin/env bash
# Mesure du niveau SER de simulate (M5a, mission 063 ; plan docs/plans/m5a.md, choix T6 et T7 ;
# décision de Pascal Q5 du 26/11/2026). Rejouable depuis la racine du dépôt, sans réseau une fois
# simulate compilé.
#
# Pour chaque taille N (SER fictive de N × N cellules de 25 m, EPSG:2154, écrite par le générateur
# de tests/m5/ser_fictive.py sous data/ser_fictive_<N>/, hors dépôt) et chaque nombre de fils T,
# lance le binaire compilé de simulate (niveau SER, mode cohorts) sur Y années et relève :
#   - la mémoire résidente maximale vue de l'extérieur, par /usr/bin/time -v (« Maximum resident
#     set size »), et celle que le moteur lit lui-même (memory_peak_rss_bytes de run.json, VmHWM) ;
#   - l'estimation de mémoire du moteur (memory_estimate_max_bytes) et son écart relatif à la
#     mémoire résidente mesurée par /usr/bin/time (critère de M5a : moins de 10 %) ;
#   - les temps de calcul et d'écriture, séparés (lignes « calcul … s ; écriture … s » de stderr),
#     la durée de run.json et le temps écoulé.
# Une ligne CSV par exécution, ajoutée au fichier --sortie (créé avec son en-tête s'il n'existe pas).
# Les extrapolations (100 ans, C20) ne sont pas faites ici : c'est le travail de la mission 064,
# qui part de ces lignes et les dit extrapolées.
#
# Réglages numériques des exécutions (non écologiques) : graine 42, t0 2022, write_step = Y (t0 et
# la dernière année écrites), noyau tronqué à 3 cellules, seuil |Q| 1e-9, 6 classes de 5 cm ; les
# paramètres sont les valeurs synthétiques du générateur (provisoires, aucune valeur écologique).
#
# Usage :
#   bash bench/m5/mesurer.sh [--n "1000 2000 4000"] [--fils "1 4"] [--annees 10]
#                            [--sortie data/bench_m5/m5_mesures.csv]
#   bash bench/m5/mesurer.sh --a-vide     # part fixe du programme (PART_FIXE_SER de memoire.rs) :
#                                         # N = 4, 1 an, trois fois à 1 et à 4 fils ; la part fixe
#                                         # est le plus grand VmHWM (le validateur, enfant de
#                                         # simulate, domine la mesure externe à cette taille)
# Dans la CI (variable CI non vide), toute taille au-delà de N = 1 000 est refusée (T10 du plan
# m5a : N = 2 000 et 4 000 restent hors CI, mission 064). N = 4 000 demande environ 4 Gio.
set -euo pipefail
cd "$(dirname "$0")/../.."

TAILLES="1000"
FILS="1 4"
ANNEES=10
SORTIE="data/bench_m5/m5_mesures.csv"
A_VIDE=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --n) TAILLES="$2"; shift 2 ;;
    --fils) FILS="$2"; shift 2 ;;
    --annees) ANNEES="$2"; shift 2 ;;
    --sortie) SORTIE="$2"; shift 2 ;;
    --a-vide) A_VIDE=1; shift ;;
    *) echo "mesurer.sh : option inconnue « $1 »" >&2; exit 2 ;;
  esac
done
if [ "$A_VIDE" -eq 1 ]; then
  TAILLES="4"; FILS="1 4 1 4 1 4"; ANNEES=1
fi
for n in $TAILLES; do
  if [ -n "${CI:-}" ] && [ "$n" -gt 1000 ]; then
    echo "mesurer.sh : N = $n refusé dans la CI (au-delà de N = 1 000 : mission 064, hors CI)." >&2
    exit 2
  fi
done
if [ ! -x /usr/bin/time ]; then
  echo "mesurer.sh : /usr/bin/time absent (paquet « time ») : la mémoire résidente ne serait pas mesurée." >&2
  exit 2
fi

cargo build --release --locked --quiet --manifest-path simulate/Cargo.toml
BINAIRE=simulate/target/release/simulate
COMMIT="$(git rev-parse --short HEAD 2>/dev/null || echo inconnu)"
mkdir -p "$(dirname "$SORTIE")"
if [ ! -f "$SORTIE" ]; then
  echo "date,commit,n,cellules,threads,years,calcul_s,ecriture_s,duration_s,ecoule_s,rss_time_bytes,memory_peak_rss_bytes,memory_estimate_max_bytes,ecart_estimation_rss" > "$SORTIE"
fi

for n in $TAILLES; do
  zone="ser_fictive_$n"
  if [ ! -f "data/$zone/cohorts_init.parquet" ]; then
    echo "== génération de la SER fictive N = $n (data/$zone)"
    python3 tests/m5/ser_fictive.py --n "$n" --graine 1 --sortie "data/$zone"
  fi
  for t in $FILS; do
    cfg="data/$zone/config_mesure.yml"
    python3 - "$cfg" "$zone" "$ANNEES" "$t" <<'PY'
import re, sys
import yaml
cfg, zone, annees, fils = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
texte = open("config.yml", encoding="utf-8").read()
texte = re.sub(r"(?m)^zone:\s*\S+", f"zone: {zone}", texte)
texte = re.sub(r"(?m)^simulate:\n(?:[ \t#][^\n]*\n?|\n(?=[ \t]))*", "", texte)
bloc = {"level": "ser", "seed": 42, "t0": 2022, "years": annees, "threads": fils, "recruitment": "cohorts",
        "regeneration": {"kernel_truncation_cells": 3, "zero_threshold": 1e-9},
        "ser": {"diameter_class_width_cm": 5.0, "diameter_classes": 6, "write_step": annees}}
texte = texte.rstrip("\n") + "\n\n" + yaml.safe_dump({"simulate": bloc}, sort_keys=False)
open(cfg, "w", encoding="utf-8").write(texte)
PY
    journal="data/$zone/mesure_stderr.txt"
    echo "== N = $n, $t fil(s), $ANNEES an(s)"
    debut=$(date +%s.%N)
    if ! /usr/bin/time -v "$BINAIRE" --config "$cfg" 2> "$journal"; then
      echo "mesurer.sh : simulate a échoué (N = $n, $t fils), voir $journal" >&2
      tail -5 "$journal" >&2
      exit 1
    fi
    fin=$(date +%s.%N)
    python3 - "$journal" "data/$zone/sim/run.json" "$SORTIE" "$COMMIT" "$n" "$t" "$ANNEES" "$debut" "$fin" <<'PY'
import datetime, json, re, sys
journal, run, sortie, commit, n, t, annees, debut, fin = sys.argv[1:]
texte = open(journal, encoding="utf-8", errors="replace").read()
calcul = sum(float(x) for x in re.findall(r"calcul ([0-9.]+) s", texte))
ecriture = sum(float(x) for x in re.findall(r"écriture ([0-9.]+) s", texte))
m = re.search(r"Maximum resident set size \(kbytes\): (\d+)", texte)
rss = int(m.group(1)) * 1024 if m else None
j = json.load(open(run, encoding="utf-8"))
est, pic = j["memory_estimate_max_bytes"], j["memory_peak_rss_bytes"]
ecart = (est - rss) / rss if rss else float("nan")
ligne = [datetime.date.today().isoformat(), commit, n, int(n) ** 2, t, annees, f"{calcul:.3f}", f"{ecriture:.3f}",
         f"{j['duration_s']:.3f}", f"{float(fin) - float(debut):.3f}", rss, pic, est, f"{ecart:.4f}"]
open(sortie, "a", encoding="utf-8").write(",".join(str(v) for v in ligne) + "\n")
print(f"   calcul {calcul:.1f} s, écriture {ecriture:.1f} s ; mémoire résidente {rss / 2**20:.1f} Mio "
      f"(VmHWM {pic / 2**20:.1f}) ; estimation {est / 2**20:.1f} Mio : écart {100 * ecart:+.2f} %")
PY
  done
done
echo "== lignes ajoutées à $SORTIE"
if [ "$A_VIDE" -eq 1 ]; then
  # À cette taille, la mesure externe est celle du validateur (enfant de simulate, environ 120 Mio) :
  # la part fixe du moteur est son propre pic, VmHWM (colonne memory_peak_rss_bytes), le plus grand
  # des six. C'est la valeur à reporter dans PART_FIXE_SER (simulate/src/memoire.rs), avec sa date.
  tail -n 6 "$SORTIE" | awk -F, 'BEGIN { m = 0 } { if ($12 > m) m = $12 } END { printf "== part fixe (VmHWM le plus grand des six) : %d kio\n", m / 1024 }'
fi
