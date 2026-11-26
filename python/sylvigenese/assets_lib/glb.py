"""Écriture et relecture des modèles d'arbres `.glb` (glTF 2.0 binaire), identiques à l'octet près.

Étape du BRIEF codée : §4 (`<species>_<stage>.glb`, avec ses niveaux de détail) et spec §9 ; ADR 0007 choix 3 :
trois niveaux de détail par l'extension `MSFT_lod` (le nœud principal est LOD0, `ids` donne LOD1 puis LOD2,
`extras.MSFT_screencoverage` donne les seuils d'écran, en provenance de `config.yml`). Mission 070.

Déterminisme : le JSON est écrit trié, sans espace superflu, sans horodatage ; les tampons sont alignés sur 4
octets (JSON rempli d'espaces, binaire de zéros). Mêmes exemplaire et configuration, mêmes octets, sur la même
machine ; l'identité entre machines (numpy, flottants) n'est pas promise (plan T12).

Les nœuds de LOD1 et LOD2 ne sont pas dans la scène (seul le nœud principal l'est, comme dans l'exemple de
l'extension) : Godot n'applique pas `MSFT_lod`, le chargeur de la vue (T13) lit l'extension et les maillages.
"""

from __future__ import annotations

import json
import struct

from sylvigenese.common import ModuleError
from sylvigenese.assets_lib import lod, models

MAGIC, CHUNK_JSON, CHUNK_BIN = 0x46546C67, 0x4E4F534A, 0x004E4942
GENERATOR = "sylvigenese assets (mission 070)"


def container(doc: dict, binary: bytes) -> bytes:
    """Octets d'un `.glb` : en-tête, bloc JSON (trié, compact), bloc BIN."""
    body = json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    body += b" " * (-len(body) % 4)
    binary = binary + b"\0" * (-len(binary) % 4)
    total = 12 + 8 + len(body) + 8 + len(binary)
    return (struct.pack("<III", MAGIC, 2, total) + struct.pack("<II", len(body), CHUNK_JSON) + body
            + struct.pack("<II", len(binary), CHUNK_BIN) + binary)


def read_container(data: bytes) -> tuple[dict, bytes]:
    """(JSON, bloc binaire) d'un `.glb` ; un fichier mal formé est refusé (jamais une valeur par défaut)."""
    if len(data) < 28:
        raise ModuleError("fichier .glb trop court")
    magic, version, length = struct.unpack_from("<III", data, 0)
    if magic != MAGIC or version != 2 or length != len(data):
        raise ModuleError("en-tête .glb invalide (nombre magique, version 2 ou longueur déclarée)")
    size, kind = struct.unpack_from("<II", data, 12)
    if kind != CHUNK_JSON or 20 + size > len(data):
        raise ModuleError("premier bloc du .glb : bloc JSON attendu")
    doc = json.loads(data[20:20 + size].decode("utf-8"))
    offset = 20 + size
    size2, kind2 = struct.unpack_from("<II", data, offset)
    if kind2 != CHUNK_BIN or offset + 8 + size2 > len(data):
        raise ModuleError("second bloc du .glb : bloc BIN attendu")
    return doc, data[offset + 8: offset + 8 + size2]


def model_document(model: lod.BuiltModel, screencoverage: list[float]) -> tuple[dict, bytes]:
    """Document glTF et tampon d'un modèle : trois maillages, trois nœuds reliés par `MSFT_lod`."""
    doc = {"asset": {"version": "2.0", "generator": GENERATOR}, "scene": 0, "scenes": [{"nodes": [0]}],
           "extensionsUsed": ["MSFT_lod"], "nodes": [], "meshes": [], "materials": [],
           "buffers": [{"byteLength": 0}], "bufferViews": [], "accessors": [], "extras": model.extras}
    buffer = models.Buffer()
    material_ids = models.add_materials(doc, model)
    for k, level in enumerate(model.levels):
        models.add_level_mesh(buffer, doc, level, material_ids, f"{model.stem}_lod{k}")
    top_extras = {**model.node_extras, "MSFT_screencoverage": [float(c) for c in screencoverage]}
    doc["nodes"] = [{"name": f"{model.stem}_lod0", "mesh": 0, "extensions": {"MSFT_lod": {"ids": [1, 2]}},
                     "extras": top_extras},
                    {"name": f"{model.stem}_lod1", "mesh": 1}, {"name": f"{model.stem}_lod2", "mesh": 2}]
    return doc, models.finalize(doc, buffer)


def model_bytes(model: lod.BuiltModel, screencoverage: list[float]) -> bytes:
    doc, binary = model_document(model, screencoverage)
    return container(doc, binary)


def write_models(registry: models.ModelRegistry, directory, generic_stems=()) -> list:
    """Écrit `<directory>/<espar>_<stade>.glb` pour chaque exemplaire lu (un fichier par essence et stade, jamais
    un doublon d'alias) et `generique_<groupe>.glb` pour chaque modèle générique employé ; rend les chemins."""
    from pathlib import Path
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for stem in sorted(set(registry.own_stems()) | set(generic_stems)):
        path = directory / f"{stem}.glb"
        path.write_bytes(model_bytes(registry.model(stem), registry.settings.screencoverage))
        written.append(path)
    return written


# ------------------------------------------------------------------ rejeu sur un export réel (tools/rejouer_exemplaires_reels)
def replay(exemplars_dir, out_dir, config: dict, base_dir=None) -> dict:
    """Rejoue la construction des `.glb` sur un dossier d'exemplaires (export réel de tarif-nemeton, hors dépôt).

    Les mêmes fonctions qu'en CI : lecture et contrôle des exemplaires, construction, écriture deux fois (les
    octets doivent être identiques), validateur du projet sur chaque `.glb`. Écrit `<out_dir>/assets/trees/*.glb` et
    `<out_dir>/rejouer_exemplaires.csv` (une ligne par modèle : de quoi compter les arbres réels traités). Rend un
    résumé ; aucune donnée n'est copiée dans le dépôt."""
    import csv
    import hashlib
    import shutil
    from pathlib import Path

    from sylvigenese import common
    from sylvigenese.assets_lib import initial_state

    out_dir, exemplars_dir = Path(out_dir).resolve(), Path(exemplars_dir).resolve()
    root = initial_state.ROOT.resolve()
    if out_dir == root or (root in out_dir.parents and root / "data" not in (out_dir, *out_dir.parents)):
        raise ModuleError(f"sortie {out_dir} dans le dépôt : les .glb d'exemplaires réels restent hors dépôt (ADR 0007, "
                          "licence du générateur) ; choisir un dossier hors du dépôt, ou sous data/")
    files = sorted(exemplars_dir.glob("*.parquet"))
    if not files:
        raise ModuleError(f"aucun fichier .parquet dans {exemplars_dir}")
    code_exemplars = common.call_validator(["assets.exemplars", *map(str, files)])
    config = {**config, "assets": {**(config.get("assets") or {}),
                                   "models": {**(config.get("assets") or {}).get("models", {}),
                                              "exemplars_dir": str(exemplars_dir)}}}
    registry = models.ModelRegistry.from_config(config, base_dir)
    stems = registry.own_stems() + [f"generique_{g}" for g in models.GROUPS]
    first, second = out_dir / "assets" / "trees", out_dir / ".rejeu"
    for directory in (first, second):
        if directory.exists():
            shutil.rmtree(directory)
        write_models(registry, directory, {s for s in stems if s.startswith("generique_")})
    identical = all((first / p.name).read_bytes() == p.read_bytes() for p in sorted(second.glob("*.glb")))
    shutil.rmtree(second)
    code_models = common.call_validator(["assets.tree_model", *map(str, sorted(first.glob("*.glb")))])
    owners = {}
    for code, model in registry.species.items():
        if model.owner:
            owners.setdefault(model.owner, []).append(code)
    rows = []
    for stem in stems:
        built = registry.model(stem)
        data = (first / f"{stem}.glb").read_bytes()
        meta = built.measures
        exemplar = None
        if built.kind == "own":
            code, _, stage = stem.rpartition("_")
            exemplar = registry.exemplars[(registry.species[code].essence, stage)]
        rows.append({"model": stem, "kind": built.kind,
                     "essence": built.extras.get("essence_generateur", ""), "stage": built.extras.get("stage", ""),
                     "codes_espar": " ".join(sorted(owners.get(stem.rpartition("_")[0], []))) if exemplar else "",
                     "segments": exemplar.count if exemplar else "",
                     "triangles_lod0": built.levels[0].triangles, "triangles_lod1": built.levels[1].triangles,
                     "triangles_lod2": built.levels[2].triangles,
                     "vertices_lod0": sum(len(p.positions) for p in built.levels[0].primitives),
                     "cards_lod0": meta.get("cards", [""])[0] if meta else "",
                     "H_m": built.extras.get("H_m", ""), "h_ref_m": round(built.h_ref_m, 4),
                     "rayon_houppier_ref_m": round(built.r_ref_m, 4),
                     "calage": built.extras.get("calage", ""), "bytes": len(data),
                     "sha256": hashlib.sha256(data).hexdigest()})
    report = out_dir / "rejouer_exemplaires.csv"
    with open(report, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return {"exemplars": len(files), "models": len(stems), "identical": identical, "report": report,
            "contract_exemplars": code_exemplars, "contract_models": code_models, "rows": rows, "out": out_dir}


def main(argv: list[str] | None = None) -> int:
    """`python -m sylvigenese.assets_lib.glb <exemplaires> [--sortie dossier] [--config config.yml]` (voir
    `tools/rejouer_exemplaires_reels`). Codes : 0 tout conforme et identique, 2 impossible, 3 non conforme."""
    import argparse
    import sys
    import tempfile
    from pathlib import Path

    from sylvigenese import common

    parser = argparse.ArgumentParser(prog="rejouer_exemplaires_reels", exit_on_error=False)
    parser.add_argument("exemplaires", help="dossier des exemplaires Parquet (export de tarif-nemeton, hors dépôt)")
    parser.add_argument("--sortie", default=None, help="dossier des .glb et du rapport (hors dépôt) ; défaut : dossier temporaire")
    parser.add_argument("--config", default="config.yml", help="config.yml (assets.models, viewer) ; défaut : celui du dépôt")
    try:
        options = parser.parse_args(argv)
    except (argparse.ArgumentError, SystemExit):
        return common.EXIT_IMPOSSIBLE
    try:
        config = common.read_config(options.config)
        out = options.sortie or tempfile.mkdtemp(prefix="rejouer_exemplaires_")
        result = replay(options.exemplaires, out, config, base_dir=Path(options.config).resolve().parent)
    except ModuleError as error:
        print(f"[rejouer_exemplaires_reels] erreur : {error}", file=sys.stderr)
        return common.EXIT_IMPOSSIBLE
    own = [r for r in result["rows"] if r["kind"] == "own"]
    print(f"[rejouer_exemplaires_reels] {result['exemplars']} exemplaire(s) lus, {len(own)} modèle(s) du générateur et "
          f"{result['models'] - len(own)} générique(s) écrits dans {result['out'] / 'assets' / 'trees'}", file=sys.stderr)
    for row in own:
        print(f"  {row['model']:<14} {row['essence']:<22} {row['segments']:>7} segments -> triangles "
              f"{row['triangles_lod0']} / {row['triangles_lod1']} / {row['triangles_lod2']}"
              f"{'  [' + row['calage'] + ']' if row['calage'] else ''}", file=sys.stderr)
    print(f"[rejouer_exemplaires_reels] rapport : {result['report']}", file=sys.stderr)
    ok = result["identical"] and result["contract_exemplars"] == 0 and result["contract_models"] == 0
    print(f"[rejouer_exemplaires_reels] identité des deux écritures : {'oui' if result['identical'] else 'NON'} ; "
          f"contrat assets.exemplars : code {result['contract_exemplars']} ; contrat assets.tree_model : code "
          f"{result['contract_models']}", file=sys.stderr)
    return common.EXIT_OK if ok else 3


if __name__ == "__main__":
    import sys
    sys.exit(main())
