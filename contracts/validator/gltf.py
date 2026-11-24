"""Modèles d'arbres glTF binaires (`assets/trees/<species>_<stage>.glb`, BRIEF §4, spec §9).

À M0, on contrôle seulement l'en-tête GLB (glTF 2.0, spécification Khronos, §4.4) et le
nom du fichier : essence en code espar, stade dans l'énumération `stage`. La validation
complète du contenu (Khronos glTF-Validator) est reportée à M4.
"""
import json
import re
import struct
from pathlib import Path

from .report import Findings

CONTRACTS_DIR = Path(__file__).resolve().parent.parent
GLB_MAGIC = 0x46546C67  # « glTF »
CHUNK_JSON = 0x4E4F534A  # « JSON »
ESPAR = re.compile(r"^[0-9]{2}[A-Z0-9]{0,3}$")


def stages():
    with open(CONTRACTS_DIR / "json" / "enums" / "stage.json", encoding="utf-8") as f:
        return json.load(f)["enum"]


def check(path, options):
    findings = Findings()
    data = Path(path).read_bytes()
    if len(data) < 20:
        findings.error("fichier GLB illisible : trop court pour un en-tête glTF")
        return [(path, findings)]
    magic, version, length = struct.unpack_from("<III", data, 0)
    if magic != GLB_MAGIC:
        findings.error("fichier GLB illisible : nombre magique « glTF » absent")
        return [(path, findings)]
    if version != 2:
        findings.error(f"conteneur GLB version {version}, version 2 attendue")
    if length != len(data):
        findings.error(f"longueur déclarée {length} octets, fichier de {len(data)} octets")
    chunk_length, chunk_type = struct.unpack_from("<II", data, 12)
    if chunk_type != CHUNK_JSON:
        findings.error("premier bloc du GLB : bloc JSON attendu")
        return [(path, findings)]
    try:
        gltf = json.loads(data[20: 20 + chunk_length].decode("utf-8"))
        asset_version = gltf["asset"]["version"]
    except (ValueError, KeyError, TypeError):
        findings.error("bloc JSON du GLB illisible ou sans asset.version")
        return [(path, findings)]
    if asset_version != "2.0":
        findings.error(f"asset.version = {asset_version!r}, glTF 2.0 attendu")
    if options.get("name_rule") == "species_stage":
        check_name(Path(path).stem, findings)
    return [(path, findings)]


def check_name(stem, findings):
    species, _, stage = stem.rpartition("_")
    allowed = stages()
    if not ESPAR.match(species) or stage not in allowed:
        findings.error(f"nom de fichier {stem}.glb : <species>_<stage>.glb attendu, avec un "
                       f"code espar et un stade parmi {', '.join(allowed)}")
