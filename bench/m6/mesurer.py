#!/usr/bin/env python3
"""Mesures de M6a sans GPU (mission 074, plan docs/plans/m6a.md §3 ligne H) : UN SEUL SCRIPT, qui rejoue tout.

Ce qu'il fait, dans l'ordre (chaque étape écrit un CSV sous --sortie, par défaut bench/results/) :
  1. bâtit trois zones d'essai sous data/ (hors dépôt) à partir du jeu fictif versionné : m6_essai (recrutement
     ifn_direct), m6_cohorts (recrutement cohorts, params/regeneration SYNTHÉTIQUES de tests/m5/ser_fictive.py) et
     m6_reel_zone (comme m6_essai, mais dessinée avec les exemplaires du contrôle réel) ;           -> m6_temps.csv
  2. mesure les .glb de la fixture d'exemplaires (octets, sommets et triangles par niveau de détail, lus par un
     analyseur écrit ici, indépendant du code du dépôt) et le temps de génération par modèle ;     -> m6_glb_fixture.csv,
                                                                                                       m6_generation.csv
  3. jeu de contrôle réel (hors dépôt) : demande de dimensions D et H d'après sim/trees, export des exemplaires par
     tarif-nemeton (code/synth_export_exemplaires.py, branche claude/export-exemplaires, PR n° 7 non fusionnée), puis
     tools/rejouer_exemplaires_reels ; SEULS DES COMPTES entrent dans les CSV (segments, triangles, octets, temps,
     décomptes) : aucune valeur des exemplaires réels n'est écrite sous bench/ ;            -> m6_reel_controle.csv,
                                                                                m6_reel_modeles.csv, m6_massif_modeles.csv
  4. avec Godot 4.6.3 en mode sans rendu (--headless) : import, --selftest de la vue (mode éditeur, --path
     viewer-massif), temps par phase et par bloc, instances d'herbe et de semis par cellule (mêmes fonctions que la vue).
                                         -> m6_selftest.csv, m6_phases.csv, m6_blocs.csv, m6_charge.csv, m6_instances_cellule.csv,
                                            m6_instances_resume.csv
Il écrit aussi m6_machine.csv (machine et versions). Rien n'est écrit dans python/, viewer-massif/ ni contracts/ ;
les zones et le cache d'import de Godot sont effacés à la fin, sauf avec --garder (data/m6_reel est toujours gardé).

Un compte de triangles n'est PAS une mesure d'images par seconde : le mode sans rendu n'en donne aucune (M6b, PC de Pascal).

Usage (depuis la racine du dépôt) :
    python3 bench/m6/mesurer.py --godot /chemin/Godot_v4.6.3-stable_linux.x86_64 --tarif-nemeton /chemin/tarif-nemeton
Options : --telecharger-godot DOSSIER (télécharge Godot 4.6.3 et vérifie son SHA-512), --repetitions N (5), --sortie DOSSIER,
--garder. Prérequis : ceux du dépôt (R, cargo, python3 avec numpy, pyarrow, pyyaml, rasterio ; make), le dépôt tarif-nemeton
sur la branche claude/export-exemplaires (ou fusionnée), /usr/bin/time (GNU) facultatif (mémoire résidente).
Codes de sortie : 0 tout mesuré ; 2 impossible (cause nommée) ; 3 un contrôle a échoué (voir m6_reel_controle.csv).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import re
import shutil
import statistics
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

GODOT_URL = "https://github.com/godotengine/godot-builds/releases/download/4.6.3-stable/Godot_v4.6.3-stable_linux.x86_64.zip"
GODOT_SHA512 = "a035258da32b77f966a5376f9fa29c30a6adde826a85ba918e1605bd1fc9823eba7d85f1dd5e748956bd2ba72827c0025ffa11bb82aec91128c407a2e723c99c"
SPECIES_FICTIF = ("03", "09", "61", "62", "64")
POINT = (700250.0, 6500250.0)          # dans le bloc t_700000_6500000 du jeu fictif (zone de 1 km sur 1 km)
VERSIONNES = ("zone.yml", "README.md", "inputs", "params/allometry.parquet", "params/indicator_values.csv", "params/tarif.parquet")
OUT: Path = ROOT / "bench" / "results"
FAILURES: list[str] = []


def say(msg: str) -> None:
    print(f"[m6] {msg}", file=sys.stderr, flush=True)


def die(msg: str, code: int = 2):
    print(f"[m6] erreur : {msg}", file=sys.stderr)
    sys.exit(code)


def write_csv(name: str, fields: list[str], rows: list[dict]) -> Path:
    path = OUT / name
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    say(f"écrit {path.relative_to(ROOT) if ROOT in path.parents else path} ({len(rows)} ligne(s))")
    return path


def offline_env() -> dict:
    env = dict(os.environ)
    for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "all_proxy"):
        env[k] = "http://127.0.0.1:9"       # comme tests/m4 : aucune de ces étapes n'a besoin du réseau
    env.pop("NO_PROXY", None)
    env.pop("no_proxy", None)
    return env


def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None, timeout: int = 3600) -> dict:
    """Lance une commande ; rend code, secondes (horloge murale), mémoire résidente maximale (octets, GNU time si présent)."""
    rss_file = None
    argv = [str(c) for c in cmd]
    if Path("/usr/bin/time").exists():
        rss_file = tempfile.NamedTemporaryFile(delete=False, suffix=".rss")
        rss_file.close()
        argv = ["/usr/bin/time", "-f", "%M", "-o", rss_file.name] + argv
    t0 = time.perf_counter()
    p = subprocess.run(argv, cwd=cwd or ROOT, env=env, capture_output=True, text=True, timeout=timeout)
    seconds = time.perf_counter() - t0
    rss = ""
    if rss_file:
        try:
            lines = Path(rss_file.name).read_text().strip().splitlines()
            rss = int(lines[-1]) * 1024
        except (ValueError, IndexError, OSError):
            rss = ""
        os.unlink(rss_file.name)
    return {"rc": p.returncode, "s": seconds, "rss": rss, "out": p.stdout, "err": p.stderr}


def tail(res: dict, n: int = 1500) -> str:
    return (res["out"] + res["err"])[-n:]


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ------------------------------------------------------------------ 0. machine
def machine(args) -> None:
    import numpy
    import pyarrow
    cpu = ""
    for line in Path("/proc/cpuinfo").read_text().splitlines():
        if line.startswith("model name"):
            cpu = line.split(":", 1)[1].strip()
            break
    mem = ""
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemTotal"):
            mem = str(int(line.split()[1]) * 1024)
            break

    def out(cmd, cwd=None):
        try:
            return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=60).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ""
    rows = [("date", time.strftime("%Y-%m-%d")), ("processeur", cpu), ("coeurs_logiques", os.cpu_count()), ("memoire_octets", mem),
            ("systeme", platform.platform()), ("python", platform.python_version()), ("numpy", numpy.__version__),
            ("pyarrow", pyarrow.__version__), ("godot", out([args.godot, "--version"])),
            ("sylvigenese_commit", out(["git", "rev-parse", "--short", "HEAD"], ROOT) or "inconnu"),
            ("tarif_nemeton_branche", out(["git", "branch", "--show-current"], args.tarif_nemeton)),
            ("tarif_nemeton_commit", out(["git", "rev-parse", "--short", "HEAD"], args.tarif_nemeton)),
            ("repetitions", args.repetitions), ("point_de_vue_x_y", f"{POINT[0]:.0f} {POINT[1]:.0f}")]
    write_csv("m6_machine.csv", ["cle", "valeur"], [{"cle": k, "valeur": v} for k, v in rows])


# ------------------------------------------------------------------ 1. zones d'essai
def make(target: str, zone: str, cfg: Path) -> dict:
    return run(["make", target, f"ZONE={zone}", f"CONFIG={cfg}"], env=offline_env(), timeout=3600)


def build_zones(keep_real: Path, real_exemplars: Path | None) -> dict:
    import yaml
    timings: list[dict] = []
    cfgdir = ROOT / "data" / "m6_cfg"
    shutil.rmtree(cfgdir, ignore_errors=True)
    cfgdir.mkdir(parents=True)

    def timed(step: str, res: dict) -> None:
        timings.append({"etape": step, "secondes": f"{res['s']:.2f}", "code": res["rc"],
                        "memoire_residente_octets": res["rss"]})
        if res["rc"] != 0:
            die(f"étape « {step} » en échec (code {res['rc']}) :\n{tail(res)}")

    # zone de base : entrées versionnées du jeu fictif, 15 ans (années 2022, 2032, 2037 au pas de 10)
    base = ROOT / "data" / "m6_base"
    shutil.rmtree(base, ignore_errors=True)
    src = ROOT / "tests" / "fixtures" / "zone_fictive"
    for rel in VERSIONNES:
        dst = base / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        (shutil.copytree if (src / rel).is_dir() else shutil.copy2)(src / rel, dst)
    text = (ROOT / "config.yml").read_text(encoding="utf-8")
    text = re.sub(r"(?m)^zone:\s*\S+", "zone: m6_base", text)
    text = re.sub(r"(?m)^  years:\s*\d+", "  years: 15", text)
    cfg_base = cfgdir / "base.yml"
    cfg_base.write_text(text, encoding="utf-8")
    for target in ("prepare", "biomes", "trees", "dynamics", "simulate"):
        timed(f"make {target} (jeu fictif, 15 ans, ifn_direct)", make(target, "m6_base", cfg_base))

    def derive(zone: str, exemplars: Path, mutate=None) -> Path:
        cfg = yaml.safe_load(cfg_base.read_text(encoding="utf-8"))
        cfg["zone"] = zone
        cfg["assets"]["models"]["exemplars_dir"] = str(exemplars)
        if mutate:
            mutate(cfg)
        path = cfgdir / f"{zone}.yml"
        path.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return path

    def clone(zone: str, drop_sim: bool = False) -> Path:
        dst = ROOT / "data" / zone
        shutil.rmtree(dst, ignore_errors=True)
        ignore = ["massif", "tiles", "web", "assets", ".en_cours", "config*.yml"] + (["sim", ".sim_en_cours"] if drop_sim else [])
        shutil.copytree(base, dst, ignore=shutil.ignore_patterns(*ignore))
        return dst

    fixture = ROOT / "tests" / "fixtures" / "exemplars_m6"
    zones = {"cfgdir": cfgdir, "base_cfg": cfg_base, "timings": timings}
    # m6_essai : ifn_direct, exemplaires de la fixture
    clone("m6_essai")
    zones["essai"] = derive("m6_essai", fixture)
    # m6_cohorts : cohorts, params/regeneration synthétiques (jamais écologiques : tests/m5/ser_fictive.py)
    z = clone("m6_cohorts", drop_sim=True)
    sys.path.insert(0, str(ROOT / "tests" / "m5"))
    import ser_fictive as G
    G.write_regeneration(z, G.regeneration_rows(SPECIES_FICTIF, par_essence=False))

    def to_cohorts(cfg):
        cfg["simulate"]["recruitment"] = "cohorts"
        cfg["simulate"]["regeneration"] = {"kernel_truncation_cells": 3, "zero_threshold": 1e-9}
    zones["cohorts"] = derive("m6_cohorts", fixture, to_cohorts)
    timed("simulate (cohorts, 15 ans)", make("simulate", "m6_cohorts", zones["cohorts"]))
    # m6_reel_zone : comme m6_essai, dessinée avec les exemplaires du contrôle réel
    if real_exemplars is not None:
        clone("m6_reel_zone")
        zones["reel"] = derive("m6_reel_zone", real_exemplars)
    return zones


def assets(cfg: Path, label: str, timings: list[dict]) -> dict:
    env = offline_env()
    env["PYTHONPATH"] = "python"
    res = run(["python3", "-m", "sylvigenese.assets", "--config", cfg], env=env, timeout=1800)
    timings.append({"etape": f"assets ({label})", "secondes": f"{res['s']:.2f}", "code": res["rc"],
                    "memoire_residente_octets": res["rss"]})
    if res["rc"] != 0:
        die(f"assets ({label}) en échec (code {res['rc']}) :\n{tail(res)}")
    return res


# ------------------------------------------------------------------ 2. .glb (analyseur indépendant)
def read_glb(path: Path) -> tuple[dict, bytes]:
    data = Path(path).read_bytes()
    magic, version, length = struct.unpack_from("<III", data, 0)
    if magic != 0x46546C67 or version != 2 or length != len(data):
        raise ValueError(f"{path} : en-tête .glb invalide")
    size, kind = struct.unpack_from("<II", data, 12)
    if kind != 0x4E4F534A:
        raise ValueError(f"{path} : bloc JSON attendu")
    return json.loads(data[20:20 + size]), data


def glb_counts(path: Path) -> dict:
    """Octets, sommets et triangles de chacun des maillages (niveaux 0, 1, 2) d'un .glb."""
    doc, data = read_glb(path)
    out = {"bytes": len(data)}
    for k, mesh in enumerate(doc["meshes"]):
        v = t = 0
        for prim in mesh["primitives"]:
            v += doc["accessors"][prim["attributes"]["POSITION"]]["count"]
            t += doc["accessors"][prim["indices"]]["count"] // 3
        out[f"vertices_lod{k}"], out[f"triangles_lod{k}"] = v, t
    out["niveaux"] = len(doc["meshes"])
    return out


def glb_fixture(zone: Path, config: dict) -> None:
    budgets = config["assets"]["models"]["triangle_budgets"]
    rows = []
    for p in sorted((zone / "assets" / "trees").glob("*.glb")):
        c = glb_counts(p)
        doc, _ = read_glb(p)
        extras = doc.get("extras", {})
        rows.append({"modele": p.stem, "sorte": "generique" if p.stem.startswith("generique_") else "generateur",
                     "essence": extras.get("essence_generateur", ""), "stade": extras.get("stage", ""),
                     "calage": extras.get("calage", ""), "octets": c["bytes"], "niveaux": c["niveaux"],
                     "sommets_lod0": c["vertices_lod0"], "sommets_lod1": c["vertices_lod1"], "sommets_lod2": c["vertices_lod2"],
                     "triangles_lod0": c["triangles_lod0"], "triangles_lod1": c["triangles_lod1"], "triangles_lod2": c["triangles_lod2"],
                     "sous_budget": all(c[f"triangles_lod{k}"] <= budgets[f"lod{k}"] for k in range(3)),
                     "budget_lod0": budgets["lod0"], "budget_lod1": budgets["lod1"], "budget_lod2": budgets["lod2"]})
    write_csv("m6_glb_fixture.csv", list(rows[0]), rows)


def generation_times(exemplars: Path, config: dict, source: str, reps: int, rows: list[dict]) -> None:
    """Temps de génération d'un modèle (maillage, trois niveaux, octets du .glb) : médiane de `reps` essais."""
    from sylvigenese.assets_lib import glb as glb_lib, models
    cfg = {**config, "assets": {**config["assets"], "models": {**config["assets"]["models"], "exemplars_dir": str(exemplars)}}}
    t0 = time.perf_counter()
    registry = models.ModelRegistry.from_config(cfg, ROOT)
    read_s = time.perf_counter() - t0
    rows.append({"source": source, "modele": "(lecture de tous les exemplaires)", "segments": sum(e.count for e in registry.exemplars.values()),
                 "secondes_mediane": f"{read_s:.3f}", "secondes_min": f"{read_s:.3f}", "secondes_max": f"{read_s:.3f}", "essais": 1})
    stems = registry.own_stems() + [f"generique_{g}" for g in models.GROUPS]
    for stem in stems:
        ts = []
        for _ in range(reps):
            registry._built.pop(stem, None)
            t0 = time.perf_counter()
            glb_lib.model_bytes(registry.model(stem), registry.settings.screencoverage)
            ts.append(time.perf_counter() - t0)
        seg = ""
        if not stem.startswith("generique_"):
            code, _, stage = stem.rpartition("_")
            seg = registry.exemplars[(registry.species[code].essence, stage)].count
        rows.append({"source": source, "modele": stem, "segments": seg, "secondes_mediane": f"{statistics.median(ts):.3f}",
                     "secondes_min": f"{min(ts):.3f}", "secondes_max": f"{max(ts):.3f}", "essais": reps})


# ------------------------------------------------------------------ 3. jeu de contrôle réel
def control_real(args, zones: dict, base_cfg: dict) -> tuple[Path, list[dict], list[dict]]:
    import pyarrow.parquet as pq
    ctl: list[dict] = []

    def put(cle, valeur, note=""):
        ctl.append({"cle": cle, "valeur": valeur, "note": note})

    export = args.tarif_nemeton / "code" / "synth_export_exemplaires.py"
    if not export.exists():
        die(f"{export} introuvable : le script d'export est sur la branche claude/export-exemplaires de tarif-nemeton "
            "(PR n° 7, non fusionnée au moment de M6a) ; se placer sur cette branche, ou fusionner la PR")
    real = ROOT / "data" / "m6_reel"
    shutil.rmtree(real, ignore_errors=True)
    real.mkdir(parents=True)
    env = dict(os.environ)
    env["PYTHONPATH"] = "python"
    # (a) demande de dimensions : D et H en quantiles de sim/trees (Q6), jeu fictif
    request = real / "dimensions_demande.csv"
    res = run(["python3", "-m", "sylvigenese.assets", "--config", zones["essai"], "--demande-dimensions", request, "--quantile", "0.5"],
              env=env)
    if res["rc"] != 0:
        die(f"demande de dimensions en échec :\n{tail(res)}")
    with open(request, encoding="utf-8", newline="") as f:
        asked = list(csv.DictReader(f))
    couples = sorted({(r["essence"], r["stage"]) for r in asked})
    notes = [l for l in res["err"].splitlines() if "signalement" in l]
    put("demande_dimensions_secondes", f"{res['s']:.2f}")
    put("demande_couples_essence_stade", len(couples), "D et H (quantile 0,5 de sim/trees du jeu fictif, au moins 30 arbres)")
    put("demande_essences", len({e for e, _ in couples}))
    put("demande_signalements_sous_le_minimum", len(notes), "couples sans dimension demandée : modèle générique (Q3)")
    # (b) export (deux fois : l'identité des octets de l'export lui-même)
    outs = []
    for k in (1, 2):
        d = real / ("exemplaires" if k == 1 else "exemplaires_bis")
        res = run(["python3", export, "--dimensions", request, "--sortie", d], cwd=args.tarif_nemeton)
        outs.append((d, res))
        put(f"export_{k}_code_de_sortie", res["rc"], "0 tout écrit ; 2 entrée inutilisable ; 3 au moins un exemplaire refusé")
        put(f"export_{k}_secondes", f"{res['s']:.2f}")
    d1, r1 = outs[0]
    d2, _ = outs[1]
    files1 = sorted(d1.glob("*.parquet"))
    files2 = sorted(d2.glob("*.parquet"))
    same = [a.name for a, b in zip(files1, files2) if a.name == b.name and a.read_bytes() == b.read_bytes()]
    put("export_fichiers_ecrits", len(files1))
    put("export_fichiers_identiques_entre_deux_exports", f"{len(same)} sur {len(files1)}", "octets du Parquet, deux exécutions de l'export")
    if len(same) != len(files1) or len(files1) != len(files2):
        FAILURES.append("export non identique à l'octet près entre deux exécutions")
    shutil.rmtree(d2)
    refused = [l for l in r1["err"].splitlines() if re.search(r"refus|erreur", l, re.I)]
    put("export_refus", len(refused), "lignes de refus ou d'erreur de l'export" + ("" if not refused else " : voir la sortie"))
    if outs[0][1]["rc"] != 0:
        FAILURES.append(f"export en échec (code {outs[0][1]['rc']})")
    segs, calage, over_dmax, below, above = 0, {"calé": 0, "non calé": 0}, 0, 0, 0
    asked_set = set(couples)
    got = set()
    for p in files1:
        schema = pq.read_schema(p)
        meta = {k.decode(): v.decode() for k, v in schema.metadata.items()}
        got.add((meta["essence"], meta["stage"]))
        segs += pq.read_metadata(p).num_rows
        calage[meta["calage"]] += 1
        reasons = meta.get("calage_raisons", "")
        over_dmax += "au-dessus du D_max" in reasons
        below += bool(re.search(r"hors de la plage", reasons))
    put("export_couples_demandes_et_exportes", f"{len(got & asked_set)} sur {len(asked_set)}")
    put("export_segments_au_total", segs)
    put("export_calage_cale", calage["calé"])
    put("export_calage_non_cale", calage["non calé"], "dimensions du jeu fictif hors de la plage de D du calage de tarif-nemeton, ou résineux (b non observé)")
    put("export_non_cale_dont_D_hors_plage_de_calage", below)
    put("export_non_cale_dont_D_au_dessus_du_D_max_du_generateur", over_dmax)
    put("export_octets_parquet", sum(p.stat().st_size for p in files1))
    # sensibilité : même demande à d'autres quantiles (comptes seulement)
    for q in ("0.25", "0.75"):
        rq = real / f"demande_{q}.csv"
        run(["python3", "-m", "sylvigenese.assets", "--config", zones["essai"], "--demande-dimensions", rq, "--quantile", q], env=env)
        dq = real / f"exemplaires_q{q}"
        rr = run(["python3", export, "--dimensions", rq, "--sortie", dq], cwd=args.tarif_nemeton)
        n = c = 0
        for p in sorted(dq.glob("*.parquet")):
            n += 1
            c += dict((k.decode(), v.decode()) for k, v in pq.read_schema(p).metadata.items())["calage"] == "calé"
        put(f"sensibilite_quantile_{q}_exemplaires_ecrits_et_cales", f"{n} écrits, {c} calés", f"code de sortie de l'export : {rr['rc']}")
        shutil.rmtree(dq, ignore_errors=True)
        rq.unlink(missing_ok=True)
    # (c) rejeu : tools/rejouer_exemplaires_reels
    glb_dir = real / "glb"
    res = run([ROOT / "tools" / "rejouer_exemplaires_reels", d1, "--sortie", glb_dir])
    put("rejeu_code_de_sortie", res["rc"], "0 tout conforme et identique ; 2 impossible ; 3 non conforme ou non identique")
    put("rejeu_secondes", f"{res['s']:.2f}", "lecture, deux constructions de tous les .glb, validateur sur chaque fichier")
    put("rejeu_memoire_residente_octets", res["rss"])
    ident = re.search(r"identité des deux écritures : (\w+) ; contrat assets.exemplars : code (\d+) ; contrat assets.tree_model : code (\d+)", res["err"])
    put("rejeu_identite_des_octets_entre_deux_ecritures", ident.group(1) if ident else "inconnu")
    put("rejeu_contrat_assets_exemplars_code", ident.group(2) if ident else "inconnu", "0 = les exemplaires tiennent le contrat")
    put("rejeu_contrat_assets_tree_model_code", ident.group(3) if ident else "inconnu", "0 = les .glb tiennent le contrat")
    put("rejeu_fichiers_conformes_exemplars", len(re.findall(r"^conforme : .*\.parquet \(contrat assets\.exemplars\)", res["out"], re.M)))
    put("rejeu_fichiers_conformes_tree_model", len(re.findall(r"^conforme : .*\.glb \(contrat assets\.tree_model\)", res["out"], re.M)))
    if res["rc"] != 0:
        FAILURES.append(f"rejeu : code {res['rc']}")
        say(tail(res))
    rows = []
    if (glb_dir / "rejouer_exemplaires.csv").exists():
        with open(glb_dir / "rejouer_exemplaires.csv", encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                c = glb_counts(glb_dir / "assets" / "trees" / f"{r['model']}.glb")
                rows.append({"modele": r["model"], "sorte": r["kind"], "essence": r["essence"], "stade": r["stage"],
                             "codes_espar": r["codes_espar"], "segments": r["segments"], "calage": r["calage"], "octets": c["bytes"],
                             "sommets_lod0": c["vertices_lod0"], "sommets_lod1": c["vertices_lod1"], "sommets_lod2": c["vertices_lod2"],
                             "triangles_lod0": c["triangles_lod0"], "triangles_lod1": c["triangles_lod1"], "triangles_lod2": c["triangles_lod2"],
                             "sous_budget": all(c[f"triangles_lod{k}"] <= base_cfg["assets"]["models"]["triangle_budgets"][f"lod{k}"] for k in range(3))})
    own = [r for r in rows if r["sorte"] == "own"]
    put("modeles_du_generateur", len(own))
    put("modeles_generiques", len(rows) - len(own))
    put("modeles_sous_budget_de_triangles", f"{sum(bool(r['sous_budget']) for r in rows)} sur {len(rows)}")
    put("arbres_reels_traites", len(own), "un exemplaire exporté = un arbre réel du générateur construit, validé en .glb")
    put("segments_traites", sum(int(r["segments"]) for r in own))
    put("alias_de_codes_espar", sum(len(r["codes_espar"].split()) - 1 for r in own), "codes espar qui partagent un .glb (02 et 03), sans emprunt")
    return glb_dir, rows, ctl


# ------------------------------------------------------------------ 4. Godot sans rendu
GD_HELPER = r'''extends SceneTree
# Mesure de bloc (bench/m6/mesurer.py, mission 074) : mêmes fonctions que la vue, chronométrées, sans rendu.
const Config := preload("res://scripts/viewer_config.gd")
const Reader := preload("res://scripts/zone_reader.gd")
const View := preload("res://scripts/massif_view.gd")
const GrassLib := preload("res://scripts/grass.gd")
const SeedLib := preload("res://scripts/seedlings.gd")

func _args() -> Dictionary:
	var a := {}
	var u := OS.get_cmdline_user_args()
	var i := 0
	while i < u.size():
		a[u[i].trim_prefix("--")] = u[i + 1]
		i += 2
	return a

func _ms(t0: int) -> float:
	return float(Time.get_ticks_usec() - t0) / 1000.0

func _initialize() -> void:
	var a := _args()
	var zone: String = a["zone"]
	var x := float(a["x"])
	var y := float(a["y"])
	var yr := int(a["year"])
	var cfg := Config.load_for_zone(zone)
	if not cfg["ok"]:
		printerr(cfg["error"])
		quit(3)
		return
	var t := Time.get_ticks_usec()
	var idx := Reader.read_index(zone)
	var t_index := _ms(t)
	var ids := Reader.blocks_around(idx["data"], yr, x, y, 1000.0)
	var blocks_ms := []
	var blocks_bytes := []
	for id in ids:
		var entry := Reader.block_entry(idx["data"], yr, id)
		var path := zone.path_join("massif").path_join(str(entry["file"]))
		t = Time.get_ticks_usec()
		var r := Reader.read_block(path)
		blocks_ms.append(_ms(t))
		blocks_bytes.append(FileAccess.get_file_as_bytes(path).size())
	var view: Node3D = View.new()
	root.add_child(view)
	t = Time.get_ticks_usec()
	var s: Dictionary = view.setup(zone, idx["data"], cfg["data"], x, y, yr)
	var t_setup := _ms(t)
	t = Time.get_ticks_usec()
	view.wait_for_grass()
	var t_grass := _ms(t)
	print("M6BLOC " + JSON.stringify({"ok": s["ok"], "error": s["error"], "index_ms": t_index, "blocks": ids.size(), "read_ms": blocks_ms,
		"read_bytes": blocks_bytes, "setup_ms": t_setup, "wait_grass_ms": t_grass, "stats": view.stats}))
	if a.has("charge"):
		var cache := {}
		var cam: Camera3D = view.camera
		var all_inst := [0, 0, 0]
		var all_tris := [0, 0, 0]
		var vis_inst := [0, 0, 0]
		var vis_tris := [0, 0, 0]
		for bloc in view.get_children():
			if not str(bloc.name).begins_with("bloc_"):
				continue
			for mi in bloc.get_children():
				if not (mi is MultiMeshInstance3D):
					continue
				var k := int(str(mi.name).substr(str(mi.name).length() - 1))
				var mesh: Mesh = mi.multimesh.mesh
				if not cache.has(mesh):
					cache[mesh] = mesh.get_faces().size() / 3
				var n: int = mi.multimesh.instance_count
				all_inst[k] += n
				all_tris[k] += n * int(cache[mesh])
				var d: float = cam.position.distance_to(bloc.position + mi.position)   # repère de la vue : la scène n'est pas encore dans l'arbre (global_position vaudrait 0)
				var b: float = mi.visibility_range_begin
				var e: float = mi.visibility_range_end
				if d >= b and (e <= 0.0 or d < e):
					vis_inst[k] += n
					vis_tris[k] += n * int(cache[mesh])
		var extra := {}
		for nd in view.get_children():
			if nd is MultiMeshInstance3D:
				var mesh2: Mesh = nd.multimesh.mesh
				if not cache.has(mesh2):
					cache[mesh2] = mesh2.get_faces().size() / 3
				var n2: int = nd.multimesh.instance_count
				extra[str(nd.name)] = {"instances": n2, "triangles_par_instance": int(cache[mesh2]), "triangles": n2 * int(cache[mesh2])}
		print("M6CHARGE " + JSON.stringify({"tous_au_niveau": {"instances": all_inst, "triangles": all_tris},
			"dans_la_plage_de_visibilite": {"instances": vis_inst, "triangles": vis_tris}, "autres": extra}))
	if a.has("cells"):
		var g: Dictionary = cfg["data"]["grass"]
		for id in ids:
			var entry := Reader.block_entry(idx["data"], yr, id)
			var b: Dictionary = Reader.read_block(zone.path_join("massif").path_join(str(entry["file"])))["data"]
			var cs := float(b["ground"]["resolution_m"])
			var area_ha := cs * cs / 10000.0
			for c in b["cells"]:
				var cover = c.get("herb_cover", null)
				var grass := -1
				if cover != null:
					grass = GrassLib.positions(str(idx["data"]["zone"]), int(c["cell_id"]), 0.0, 0.0, cs, float(cover), g).size()
				var seeds := {}
				var total := 0
				if bool(b["seedlings_simulated"]):
					for sd in c.get("seedlings", []):
						var n := SeedLib.count(str(idx["data"]["zone"]), int(c["cell_id"]), str(sd["species"]), float(sd["seedlings_ha"]), area_ha)
						seeds[str(sd["species"])] = n
						total += n
				print("M6CELL " + JSON.stringify({"block": id, "cell_id": int(c["cell_id"]), "herb_cover": cover, "grass": grass,
					"seedlings_total": total, "seedlings": seeds}))
	quit(0)
'''


def get_godot(args) -> Path:
    if args.telecharger_godot:
        import urllib.request
        import zipfile
        d = Path(args.telecharger_godot)
        d.mkdir(parents=True, exist_ok=True)
        z = d / "godot.zip"
        say(f"téléchargement de Godot 4.6.3 dans {d}")
        urllib.request.urlretrieve(GODOT_URL, z)
        h = hashlib.sha512(z.read_bytes()).hexdigest()
        if h != GODOT_SHA512:
            die(f"SHA-512 de Godot différent de celui publié : {h}")
        with zipfile.ZipFile(z) as zf:
            zf.extractall(d)
        z.unlink()
        binary = next(d.glob("Godot_v4.6.3-stable_linux.x86_64"))
        binary.chmod(0o755)
        return binary
    g = args.godot or os.environ.get("GODOT") or shutil.which("godot")
    if not g:
        die("Godot 4.6.3 introuvable : --godot /chemin, la variable GODOT, ou --telecharger-godot DOSSIER")
    return Path(g)


def selftest_args(zone: Path, year: int, extra: list[str] | None = None) -> list[str]:
    return ["--headless", "--path", "viewer-massif", *(extra or []), "--", "--zone", str(zone), "--x", f"{POINT[0]:.0f}",
            "--y", f"{POINT[1]:.0f}", "--year", str(year), "--selftest"]


def godot_measures(args, godot: Path, scenarios: list[dict]) -> list[dict]:
    tmp = Path(tempfile.mkdtemp(prefix="m6_godot_"))
    env = dict(os.environ)
    env["XDG_DATA_HOME"] = str(tmp / "xdg")        # sans « .. » : user:// de Godot (leçon de la CI, mission 073)
    (tmp / "xdg").mkdir()
    helper = tmp / "mesure_bloc.gd"
    helper.write_text(GD_HELPER, encoding="utf-8")
    res = run([godot, "--headless", "--path", "viewer-massif", "--import"], env=env)
    imp_err = [l for l in (res["out"] + res["err"]).splitlines() if "ERROR" in l]
    say(f"import : code {res['rc']}, {res['s']:.1f} s, {len(imp_err)} ligne(s) ERROR")
    selftest, phases, blocs, cells, summary, charge = [], [], [], [], [], []
    meta = [{"etape": "godot --headless --import (viewer-massif)", "secondes": f"{res['s']:.2f}", "code": res["rc"],
             "memoire_residente_octets": res["rss"]}]
    if res["rc"] != 0 or imp_err:
        FAILURES.append("import de Godot en échec ou avec des lignes ERROR")
    for sc in scenarios:
        zone = ROOT / "data" / sc["zone"]
        for run_no in range(1, sc.get("essais", args.repetitions) + 1):
            r = run([godot, *selftest_args(zone, sc["year"], sc.get("extra"))], env=env, timeout=900)
            m = re.search(r"SELFTEST (\{.*\})", r["out"])
            st = json.loads(m.group(1)) if m else {}
            errs = [l for l in (r["out"] + r["err"]).splitlines() if "ERROR" in l]
            selftest.append({"scenario": sc["name"], "essai": run_no, "code": r["rc"], "secondes_processus_entier": "" if sc.get("sans_temps") else f"{r['s']:.3f}",
                             "memoire_residente_octets": "" if sc.get("sans_temps") else r["rss"], "lignes_ERROR": len(errs), "blocs": st.get("blocks", ""),
                             "arbres": st.get("trees", ""), "generiques": st.get("generic_trees", ""), "non_cales": st.get("non_cale_trees", ""),
                             "brins_d_herbe": st.get("grass_instances", ""), "semis": st.get("seedlings", ""), "tronque": st.get("truncated", "")})
            if r["rc"] != 0 or not m:
                FAILURES.append(f"selftest {sc['name']} essai {run_no} : code {r['rc']}")
            if sc.get("phases", True):
                a = ["--headless", "--path", "viewer-massif", "-s", str(helper), "--", "--zone", str(zone), "--x", f"{POINT[0]:.0f}",
                     "--y", f"{POINT[1]:.0f}", "--year", str(sc["year"])] + (["--cells", "1"] if run_no == 1 and sc.get("cells") else []) \
                    + (["--charge", "1"] if run_no == 1 else [])
                h = run([godot, *a], env=env, timeout=900)
                mb = re.search(r"M6BLOC (\{.*\})", h["out"])
                if not mb:
                    FAILURES.append(f"phases {sc['name']} essai {run_no} : {tail(h, 400)}")
                    continue
                b = json.loads(mb.group(1))
                if not b["ok"]:
                    FAILURES.append(f"phases {sc['name']} : {b['error']}")
                phases.append({"scenario": sc["name"], "essai": run_no, "blocs": b["blocks"], "lecture_index_ms": f"{b['index_ms']:.3f}",
                               "lecture_des_blocs_ms": f"{sum(b['read_ms']):.1f}", "octets_des_blocs": sum(b["read_bytes"]),
                               "installation_de_la_scene_ms": f"{b['setup_ms']:.1f}", "attente_de_l_herbe_ms": f"{b['wait_grass_ms']:.1f}",
                               "arbres": b["stats"]["trees"], "brins_d_herbe": b["stats"]["grass_instances"], "semis": b["stats"]["seedlings"],
                               "tronque": b["stats"]["truncated"]})
                for i, (ms, nb) in enumerate(zip(b["read_ms"], b["read_bytes"])):
                    blocs.append({"scenario": sc["name"], "essai": run_no, "bloc_rang": i + 1, "octets": nb, "lecture_et_controle_ms": f"{ms:.1f}"})
                if run_no == 1:
                    mc = re.search(r"M6CHARGE (\{.*\})", h["out"])
                    if mc:
                        ch = json.loads(mc.group(1))
                        for k in range(3):
                            charge.append({"scenario": sc["name"], "composante": f"arbres, niveau de détail {k}, tous les arbres du massif chargé au niveau {k}",
                                           "instances": ch["tous_au_niveau"]["instances"][k], "triangles": ch["tous_au_niveau"]["triangles"][k]})
                        for k in range(3):
                            charge.append({"scenario": sc["name"], "composante": f"arbres, niveau de détail {k}, dans sa plage de visibilité au point de vue",
                                           "instances": ch["dans_la_plage_de_visibilite"]["instances"][k], "triangles": ch["dans_la_plage_de_visibilite"]["triangles"][k]})
                        for name, v in sorted(ch["autres"].items()):
                            charge.append({"scenario": sc["name"], "composante": f"{name} (maillage du niveau 0, aucune plage de visibilité)",
                                           "instances": v["instances"], "triangles": v["triangles"]})
                if run_no == 1 and sc.get("cells"):
                    for line in re.findall(r"M6CELL (\{.*\})", h["out"]):
                        c = json.loads(line)
                        cells.append({"scenario": sc["name"], "bloc": c["block"], "cell_id": c["cell_id"],
                                      "couvert_herbace": "" if c["herb_cover"] is None else c["herb_cover"],
                                      "brins_d_herbe": c["grass"], "semis_total": c["seedlings_total"],
                                      "semis_par_essence": " ".join(f"{k}:{v}" for k, v in sorted(c["seedlings"].items()))})
    write_csv("m6_selftest.csv", list(selftest[0]), selftest)
    # un lot de scénarios sans phases (par exemple les seuls scénarios de la reprise 075) n'écrit pas de CSV de phases vide
    if phases:
        write_csv("m6_phases.csv", list(phases[0]), phases)
        write_csv("m6_blocs.csv", list(blocs[0]), blocs)
        write_csv("m6_charge.csv", ["scenario", "composante", "instances", "triangles"], charge)
    if cells:
        write_csv("m6_instances_cellule.csv", list(cells[0]), cells)
    for name in sorted({c["scenario"] for c in cells}):
        sub = [c for c in cells if c["scenario"] == name]
        for col, label in (("brins_d_herbe", "brins d'herbe par cellule (formule de la vue, sans plafond ni rayon)"),
                           ("semis_total", "semis par cellule (formule de la vue ; 0 par construction en ifn_direct, semis non simulés)"
                                             if "ifn_direct" in name else "semis par cellule (formule de la vue)")):
            v = sorted(int(c[col]) for c in sub if c[col] != -1 and c[col] != "")
            n_cover = sum(1 for c in sub if c["couvert_herbace"] != "")
            if not v:
                continue
            summary.append({"scenario": name, "grandeur": label, "cellules": len(sub), "cellules_avec_couvert_connu": n_cover,
                            "cellules_a_zero": sum(1 for x in v if x == 0), "min": v[0], "mediane": int(statistics.median(v)),
                            "p95": v[min(len(v) - 1, int(0.95 * len(v)))], "max": v[-1], "somme": sum(v)})
    if summary:
        write_csv("m6_instances_resume.csv", list(summary[0]), summary)
    shutil.rmtree(tmp, ignore_errors=True)
    return meta


def massif_models(zone: Path, source: str, rows: list[dict]) -> None:
    idx = json.loads((zone / "massif" / "index.json").read_text(encoding="utf-8"))
    for y in idx["years"]:
        k = y["trees_by_kind"]
        rows.append({"source": source, "annee": y["year"], "arbres": y["trees"], "modele_propre": k.get("own", 0),
                     "alias": k.get("alias", 0), "generique": k.get("generic", 0), "blocs": len(y["blocks"])})


# ------------------------------------------------------------------ principal
def main(argv=None) -> int:
    global OUT
    ap = argparse.ArgumentParser(description="Mesures de M6a sans GPU (mission 074)")
    ap.add_argument("--godot", default=None, help="binaire Godot 4.6.3 (sinon variable GODOT, sinon `godot` du PATH)")
    ap.add_argument("--telecharger-godot", default=None, metavar="DOSSIER", help="télécharge Godot 4.6.3 (SHA-512 vérifié) dans ce dossier")
    ap.add_argument("--tarif-nemeton", default=os.environ.get("TARIF_NEMETON_DIR", str(ROOT.parent / "tarif-nemeton")),
                    help="dépôt tarif-nemeton (branche claude/export-exemplaires ou fusionnée)")
    ap.add_argument("--sortie", default=str(OUT), help="dossier des CSV (défaut bench/results)")
    ap.add_argument("--repetitions", type=int, default=5, help="essais par mesure de temps (défaut 5)")
    ap.add_argument("--garder", action="store_true", help="garder les zones data/m6_* et le cache d'import de Godot")
    args = ap.parse_args(argv)
    args.tarif_nemeton = Path(args.tarif_nemeton).resolve()
    OUT = Path(args.sortie).resolve()
    OUT.mkdir(parents=True, exist_ok=True)
    os.chdir(ROOT)
    if not (ROOT / "config.yml").exists():
        die("à lancer depuis un clone de sylvigenese")
    import yaml
    base_cfg = yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8"))
    godot = get_godot(args)
    args.godot = str(godot)

    machine(args)
    say("zones d'essai (prépare, biomes, trees, dynamics, simulate : quelques minutes)")
    zones = build_zones(ROOT / "data" / "m6_reel", None)
    timings = zones["timings"]
    # fixture : assets, .glb
    assets(zones["essai"], "ifn_direct, exemplaires de la fixture", timings)
    assets(zones["cohorts"], "cohorts, exemplaires de la fixture", timings)
    glb_fixture(ROOT / "data" / "m6_essai", base_cfg)
    # contrôle réel (exporte, rejoue)
    glb_dir, real_rows, ctl = control_real(args, zones, base_cfg)
    write_csv("m6_reel_modeles.csv", list(real_rows[0]), real_rows)
    # zone dessinée avec les exemplaires réels
    shutil.rmtree(ROOT / "data" / "m6_reel_zone", ignore_errors=True)
    shutil.copytree(ROOT / "data" / "m6_base", ROOT / "data" / "m6_reel_zone",
                    ignore=shutil.ignore_patterns("massif", "tiles", "web", "assets", ".en_cours", "config*.yml"))
    cfg_reel = yaml.safe_load(zones["essai"].read_text(encoding="utf-8"))
    cfg_reel["zone"] = "m6_reel_zone"
    cfg_reel["assets"]["models"]["exemplars_dir"] = str(ROOT / "data" / "m6_reel" / "exemplaires")
    zones["reel"] = zones["cfgdir"] / "m6_reel_zone.yml"
    zones["reel"].write_text(yaml.safe_dump(cfg_reel, allow_unicode=True, sort_keys=False), encoding="utf-8")
    assets(zones["reel"], "ifn_direct, exemplaires du contrôle réel", timings)
    mm: list[dict] = []
    massif_models(ROOT / "data" / "m6_essai", "fixture, ifn_direct", mm)
    massif_models(ROOT / "data" / "m6_cohorts", "fixture, cohorts", mm)
    massif_models(ROOT / "data" / "m6_reel_zone", "contrôle réel, ifn_direct", mm)
    write_csv("m6_massif_modeles.csv", list(mm[0]), mm)
    for r in mm:
        if r["source"].startswith("contrôle réel") and r["arbres"] != r["modele_propre"] + r["alias"] + r["generique"]:
            FAILURES.append("somme des arbres par sorte de modèle différente du total (contrôle réel)")
    # temps de génération
    gen: list[dict] = []
    generation_times(ROOT / "tests" / "fixtures" / "exemplars_m6", base_cfg, "fixture", args.repetitions, gen)
    generation_times(ROOT / "data" / "m6_reel" / "exemplaires", base_cfg, "controle_reel", args.repetitions, gen)
    write_csv("m6_generation.csv", list(gen[0]), gen)
    # Godot sans rendu
    scenarios = [
        {"name": "fictif_ifn_direct_2022", "zone": "m6_essai", "year": 2022},
        {"name": "fictif_ifn_direct_2037", "zone": "m6_essai", "year": 2037, "cells": True},
        {"name": "fictif_cohorts_2037", "zone": "m6_cohorts", "year": 2037, "cells": True},
        {"name": "controle_reel_ifn_direct_2037", "zone": "m6_reel_zone", "year": 2037},
        {"name": "fictif_cohorts_2037_repli_gl_compatibility", "zone": "m6_cohorts", "year": 2037,
         "extra": ["--rendering-method", "gl_compatibility"], "phases": False},
        # reprise 075 (mission 077) : un stade sans exemplaire d'une essence qui en a d'autres (épicéa mature, 1 arbre en 2022)
        # est dessiné par le générateur générique d'après stage_models ; un seul essai, ni durée ni mémoire (comptes seulement)
        {"name": "controle_reel_ifn_direct_2022_reprise_075", "zone": "m6_reel_zone", "year": 2022, "essais": 1, "sans_temps": True,
         "phases": False},
        {"name": "controle_reel_ifn_direct_2032_reprise_075", "zone": "m6_reel_zone", "year": 2032, "essais": 1, "sans_temps": True,
         "phases": False},
    ]
    timings += godot_measures(args, godot, scenarios)
    write_csv("m6_temps.csv", ["etape", "secondes", "code", "memoire_residente_octets"], timings)
    ctl.append({"cle": "controles_en_echec", "valeur": len(FAILURES), "note": " ; ".join(FAILURES)})
    write_csv("m6_reel_controle.csv", ["cle", "valeur", "note"], ctl)
    if not args.garder:
        for z in ("m6_base", "m6_essai", "m6_cohorts", "m6_reel_zone", "m6_cfg"):
            shutil.rmtree(ROOT / "data" / z, ignore_errors=True)
        shutil.rmtree(ROOT / "viewer-massif" / ".godot", ignore_errors=True)
    if FAILURES:
        say("CONTRÔLES EN ÉCHEC : " + " ; ".join(FAILURES))
        return 3
    say("tout est mesuré")
    return 0


if __name__ == "__main__":
    sys.exit(main())
