"""Modèles d'arbres : modèles du générateur par (essence, stade), modèles génériques, tampons glTF.

Étape du BRIEF codée : §4 (un `.glb` par essence et stade, `<species>_<stage>.glb`), §9 (arbres synthétiques
provisoires), spec §2 et §9 ; ADR 0007 (choix 2 à 5) ; plan `docs/plans/m6a.md` T1, T2, T12 et les décisions
de Pascal Q2 (feuillage en cartes, couleur unie, provisoire), Q3 (essence sans exemplaire : modèle générique
feuillu ou résineux, signalé, jamais un emprunt). Missions 028 (modèles génériques) et 070.

- Un seul constructeur de maillage (`lod.py`), deux sorties (T1) : le `.glb` de `assets/trees/` (les trois
  niveaux, `MSFT_lod`) et le contenu `.gltf` des tuiles, qui reprend les MÊMES sommets du niveau LOD2
  (`add_level_mesh` écrit les deux).
- `ModelRegistry` dit, pour un arbre (code espar, stade), le modèle qui le dessine : `own` (fichier du code
  espar propre de l'essence, `<espar>_<stade>`), `alias` (même essence qu'un autre code : le même fichier, pas
  de doublon, pas un emprunt) ou `generic` (`generique_<groupe>`, essence ou stade sans exemplaire, Q3).
- Échelle d'une instance : (rayon / `r_ref_m`, hauteur / `h_ref_m`, rayon / `r_ref_m`). Un modèle générique mesure
  1 m de haut et 1 m de rayon : (r, h, r), comme depuis la mission 028. L'échelle n'est pas uniforme : la tige
  s'épaissit avec le houppier (dit).
- Les modèles génériques (tige et houppier simples, une essence n'est pas dessinée) ont trois niveaux de détail
  comme les autres.
"""

from __future__ import annotations

import json
import math
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from sylvigenese.common import ModuleError
from sylvigenese.assets_lib import exemplars as exemplar_lib
from sylvigenese.assets_lib import lod

GROUPS = ("feuillu", "resineux")
COLORS = {"feuillu": [0.30, 0.52, 0.22, 1.0], "resineux": [0.10, 0.34, 0.22, 1.0]}
TRUNK_COLOR = [0.38, 0.27, 0.17, 1.0]
# Clés demandées à la racine des `.gltf` et du tileset par le contrat `assets.gltf` : elles disent « illustration
# provisoire » (les modèles réellement employés sont dits dans `modeles`, clé ajoutée par tiles.py à chaque tuile).
GENERIC_EXTRAS = {
    "generique": True,
    "provisoire": True,
    "note": "illustration provisoire ; les modèles employés sont dits dans massif/index.json (models, notes)",
}
NON_CALE_CONIFERS = ("résineux : densité des rameaux tirée et non calée, aucun exposant b observé ; stades jeune et "
                     "perche extrapolés (calage sans petit résineux) ; décision de Pascal du 26/11/2026")


def _ring(radius: float, y: float, n: int) -> list[list[float]]:
    return [[radius * math.cos(2 * math.pi * i / n), y, radius * math.sin(2 * math.pi * i / n)] for i in range(n)]


def _vertex_normals(positions: np.ndarray, indices: np.ndarray) -> np.ndarray:
    """Normales lissées : somme des normales de faces par sommet."""
    normals = np.zeros_like(positions)
    for a, b, c in indices.reshape(-1, 3):
        n = np.cross(positions[b] - positions[a], positions[c] - positions[a])
        normals[[a, b, c]] += n
    length = np.linalg.norm(normals, axis=1, keepdims=True)
    length[length == 0] = 1.0
    return normals / length


def _trunk(n: int = 6, radius: float = 0.05, trunk_height: float = 0.4) -> tuple[np.ndarray, np.ndarray]:
    bottom_ring, top_ring = _ring(radius, 0.0, n), _ring(radius, trunk_height, n)
    positions = np.array(bottom_ring + top_ring, dtype="float32")
    indices = []
    for i in range(n):
        j = (i + 1) % n
        indices += [i, n + i, j, j, n + i, n + j]  # côté, vers l'extérieur
    return positions, np.array(indices, dtype="uint16")


def _broadleaf_crown(n: int = 8, levels: int = 4) -> tuple[np.ndarray, np.ndarray]:
    """Ellipsoïde bas : de y = 0,3 à y = 1, rayon 1 à l'équateur."""
    center, half = 0.65, 0.35
    pts = [[0.0, center - half, 0.0]]
    for k in range(1, levels):
        phi = -math.pi / 2 + math.pi * k / levels
        pts += [[math.cos(phi) * math.cos(2 * math.pi * i / n), center + half * math.sin(phi),
                 math.cos(phi) * math.sin(2 * math.pi * i / n)] for i in range(n)]
    pts.append([0.0, center + half, 0.0])
    positions = np.array(pts, dtype="float32")
    idx = []
    for i in range(n):  # calotte basse
        idx += [0, 1 + (i + 1) % n, 1 + i]
    for k in range(levels - 2):
        a, b = 1 + k * n, 1 + (k + 1) * n
        for i in range(n):
            j = (i + 1) % n
            idx += [a + i, a + j, b + i, a + j, b + j, b + i]
    last = 1 + (levels - 2) * n
    top = len(pts) - 1
    for i in range(n):
        idx += [top, last + i, last + (i + 1) % n]
    return positions, np.array(idx, dtype="uint16")


def _conifer_crown(n: int = 8) -> tuple[np.ndarray, np.ndarray]:
    """Cône : de y = 0,15 (rayon 1) à y = 1 (pointe)."""
    pts = _ring(1.0, 0.15, n) + [[0.0, 0.15, 0.0], [0.0, 1.0, 0.0]]
    positions = np.array(pts, dtype="float32")
    idx = []
    for i in range(n):
        j = (i + 1) % n
        idx += [i, n + 1, j]  # côté
        idx += [i, j, n]  # dessous
    return positions, np.array(idx, dtype="uint16")


def _generic_level(group: str, trunk_sides: int, crown_sides: int, crown_levels: int) -> lod.Level:
    crown = _broadleaf_crown(crown_sides, crown_levels) if group == "feuillu" else _conifer_crown(crown_sides)
    primitives = []
    for (positions, indices), color, name in ((_trunk(trunk_sides), TRUNK_COLOR, "tronc"),
                                              (crown, COLORS[group], "houppier")):
        normals = _vertex_normals(positions.astype("float64"), indices).astype("float32")
        primitives.append(lod.Primitive(name, positions.astype("float32"), normals, indices.astype("uint16"), color))
    return lod.Level(primitives)


def generic_model(group: str) -> lod.BuiltModel:
    """Modèle générique d'un groupe : trois niveaux de détail de la tige et du houppier simples (1 m, 1 m)."""
    if group not in GROUPS:
        raise ModuleError(f"groupe d'essences sans modèle générique : {group!r} (attendu : {', '.join(GROUPS)})")
    levels = [_generic_level(group, 8, 16, 6), _generic_level(group, 6, 8, 4), _generic_level(group, 4, 6, 3)]
    extras = {"generique": True, "groupe": group, "provisoire": True, "synthetique": True}
    return lod.BuiltModel(f"generique_{group}", "generic", levels, 1.0, 1.0, extras)


class Buffer:
    """Construit un .bin : ajoute des blocs alignés sur 4 octets, rend les bufferViews."""

    def __init__(self):
        self.data = bytearray()
        self.views: list[dict] = []
        self.accessors: list[dict] = []

    def add(self, array: np.ndarray, target: int | None, type_: str, component_type: int, with_min_max: bool = False) -> int:
        while len(self.data) % 4:
            self.data.append(0)
        raw = np.ascontiguousarray(array).tobytes()
        view = {"buffer": 0, "byteOffset": len(self.data), "byteLength": len(raw)}
        if target:
            view["target"] = target
        self.data += raw
        self.views.append(view)
        acc = {"bufferView": len(self.views) - 1, "componentType": component_type, "count": int(array.shape[0]), "type": type_}
        if with_min_max:
            acc["min"] = [float(v) for v in array.min(axis=0)]
            acc["max"] = [float(v) for v in array.max(axis=0)]
        self.accessors.append(acc)
        return len(self.accessors) - 1


def add_level_mesh(buffer: Buffer, doc: dict, level: lod.Level, material_ids: list[int], name: str) -> int:
    """Ajoute à `doc` le maillage d'un niveau de détail (une primitive par matériau) ; rend son indice.

    Sert au `.glb` (les trois niveaux) et au contenu de tuile (LOD2) : les mêmes octets de sommets."""
    primitives = []
    for primitive, material in zip(level.primitives, material_ids):
        a_pos = buffer.add(primitive.positions, 34962, "VEC3", 5126, with_min_max=True)
        a_nor = buffer.add(primitive.normals, 34962, "VEC3", 5126)
        component = 5123 if primitive.indices.dtype == np.uint16 else 5125
        a_idx = buffer.add(primitive.indices, 34963, "SCALAR", component)
        primitives.append({"attributes": {"POSITION": a_pos, "NORMAL": a_nor}, "indices": a_idx,
                           "material": material, "mode": 4})
    doc["meshes"].append({"name": name, "primitives": primitives})
    return len(doc["meshes"]) - 1


def add_materials(doc: dict, model: lod.BuiltModel) -> list[int]:
    """Ajoute les matériaux du modèle (un par primitive du niveau LOD0) ; rend leurs indices."""
    ids = []
    for primitive in model.levels[0].primitives:
        doc["materials"].append({"name": f"{model.stem}_{primitive.name}", "doubleSided": True,
                                 "pbrMetallicRoughness": {"baseColorFactor": [round(float(c), 6) for c in primitive.color],
                                                          "metallicFactor": 0.0, "roughnessFactor": 1.0}})
        ids.append(len(doc["materials"]) - 1)
    return ids


def empty_document(bin_name: str) -> dict:
    return {"asset": {"version": "2.0", "generator": "sylvigenese assets (mission 028)"},
            "scene": 0, "scenes": [{"nodes": []}], "nodes": [], "meshes": [], "materials": [],
            "buffers": [{"uri": bin_name, "byteLength": 0}], "bufferViews": [], "accessors": []}


def finalize(doc: dict, buffer: Buffer) -> bytes:
    """Complète le document avec le tampon ; rend le contenu du .bin (multiple de 4 octets)."""
    while len(buffer.data) % 4:
        buffer.data.append(0)
    doc["bufferViews"], doc["accessors"] = buffer.views, buffer.accessors
    doc["buffers"][0]["byteLength"] = len(buffer.data)
    return bytes(buffer.data)


def write_gltf(path: Path, doc: dict, binary: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.with_suffix(".bin").write_bytes(binary)
    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def write_gltf(path: Path, doc: dict, binary: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.with_suffix(".bin").write_bytes(binary)
    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


# ------------------------------------------------------------------ réglages (config.yml)
@dataclass(frozen=True)
class Settings:
    """Réglages d'AFFICHAGE de `config.yml` (provisoires, « illustration, non mesurée ») ; jamais lus par le moteur."""
    budgets: dict
    screencoverage: list
    exemplars_dir: Path | None
    card_size_m: float | None
    color_by_group: dict | None
    color_by_essence: dict


def _hex(value, where: str) -> str:
    if not (isinstance(value, str) and len(value) == 7 and value[0] == "#"
            and all(c in "0123456789abcdef" for c in value[1:])):
        raise ModuleError(f"{where} : une couleur #rrggbb (minuscules) est attendue, reçu {value!r}")
    return value


def settings_from_config(config: dict, base_dir: Path | None = None) -> Settings:
    """Lit `assets.models` et `viewer.foliage` ; un bloc absent est une erreur (aucune valeur par défaut).

    `exemplars_dir` relatif est lu depuis `base_dir` (le dossier de config.yml)."""
    models = ((config.get("assets") or {}).get("models"))
    if not isinstance(models, dict):
        raise ModuleError("config.yml : bloc assets.models absent (budgets de triangles et seuils des niveaux de "
                          "détail, M6a) ; aucune valeur par défaut n'est prise")
    budgets, cover = models.get("triangle_budgets"), models.get("screencoverage")
    ok = isinstance(budgets, dict) and all(isinstance(budgets.get(k), int) and not isinstance(budgets.get(k), bool)
                                            and budgets[k] > 0 for k in ("lod0", "lod1", "lod2"))
    if not ok or not budgets["lod0"] > budgets["lod1"] > budgets["lod2"]:
        raise ModuleError("config.yml : assets.models.triangle_budgets = {lod0, lod1, lod2} (entiers strictement "
                          "décroissants) attendu")
    good = (isinstance(cover, list) and len(cover) == 3
            and all(isinstance(c, (int, float)) and not isinstance(c, bool) and 0 < c <= 1 for c in cover)
            and cover[0] > cover[1] > cover[2])
    if not good:
        raise ModuleError("config.yml : assets.models.screencoverage = trois nombres de ]0 ; 1] strictement "
                          "décroissants attendu")
    directory = models.get("exemplars_dir")
    if directory is not None:
        directory = Path(str(directory))
        if not directory.is_absolute():
            directory = (base_dir or Path.cwd()) / directory
    foliage = (config.get("viewer") or {}).get("foliage")
    card = group = essence = None
    if isinstance(foliage, dict):
        card = foliage.get("card_size_m")
        if card is not None and not (isinstance(card, (int, float)) and not isinstance(card, bool) and card > 0):
            raise ModuleError("config.yml : viewer.foliage.card_size_m doit être un nombre > 0")
        group = foliage.get("color_by_group")
        if isinstance(group, dict):
            group = {k: _hex(v, f"viewer.foliage.color_by_group.{k}") for k, v in group.items()}
        essence = {k: _hex(v, f"viewer.foliage.color_by_essence.{k}")
                   for k, v in (foliage.get("color_by_essence") or {}).items()}
    return Settings({k: int(budgets[k]) for k in ("lod0", "lod1", "lod2")}, [float(c) for c in cover], directory,
                    None if card is None else float(card), group, essence or {})


def srgb_to_linear(color: str) -> list[float]:
    """#rrggbb (sRGB) -> [r, g, b, 1] linéaire, arrondi à 6 décimales (baseColorFactor de glTF est linéaire)."""
    out = []
    for k in (1, 3, 5):
        c = int(color[k:k + 2], 16) / 255.0
        out.append(round(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4, 6))
    return out + [1.0]


# ------------------------------------------------------------------ modèles du générateur
def own_model(exemplar: exemplar_lib.Exemplar, model: exemplar_lib.SpeciesModel, settings: Settings) -> lod.BuiltModel:
    """Modèle d'un exemplaire : maillage, trois niveaux, extras du contrat `assets.tree_model`.

    « Non calé » : tout résineux (décision de Pascal du 26/11/2026) et tout exemplaire que son export dit
    `calage = non calé` ; `b_cible` n'est écrit que si l'exemplaire en porte un."""
    if settings.card_size_m is None or not settings.color_by_group:
        raise ModuleError("config.yml : viewer.foliage.card_size_m et color_by_group sont exigés pour dessiner les "
                          "cartes de feuillage (Q2) des modèles du générateur")
    color = settings.color_by_essence.get(exemplar.essence) or settings.color_by_group.get(model.group)
    if color is None:
        raise ModuleError(f"config.yml : aucune couleur de feuillage pour {exemplar.essence} ni pour le groupe "
                          f"{model.group} (viewer.foliage)")
    levels, measures = lod.build_levels(exemplar.segments, settings.budgets, settings.card_size_m, TRUNK_COLOR,
                                        srgb_to_linear(color))
    meta = exemplar.meta
    stem = f"{model.owner}_{exemplar.stage}"
    extras = {"species": model.owner, "stage": exemplar.stage, "source_commit": meta["source_commit"],
              "essence_generateur": exemplar.essence, "D_cm": float(meta["D_cm"]), "H_m": float(meta["H_m"]),
              "hbh_m": float(meta["hbh_m"]), "Rh_m": float(meta["Rh_m"]), "graine": exemplar.seed,
              "H_ref_m": measures["h_ref_m"], "rayon_houppier_ref_m": measures["r_ref_m"],
              "provisoire": True, "synthetique": True,
              "feuillage": {"type": "cartes_couleur_unie", "couleur": color}}
    if "b_cible" in meta:
        extras["b_cible"] = float(meta["b_cible"])
    if model.group == "resineux":
        extras["calage"] = "non calé"
        extras["calage_raisons"] = meta.get("calage_raisons") or NON_CALE_CONIFERS
    else:
        # `calage` est obligatoire au contrat : celui de l'export ; à défaut, « calé » si l'exemplaire porte un b_cible
        # visé, « non calé » sinon (aucun b visé = aucune cible de calage)
        extras["calage"] = meta.get("calage") or ("calé" if "b_cible" in meta else "non calé")
        if "calage_raisons" in meta:
            extras["calage_raisons"] = meta["calage_raisons"]
    return lod.BuiltModel(stem, "own", levels, measures["h_ref_m"], measures["r_ref_m"], extras, measures=measures)


class ModelRegistry:
    """Les modèles d'une exécution : exemplaires lus, table des codes espar, modèles construits à la demande."""

    def __init__(self, settings: Settings, exemplars: dict | None = None,
                 species: dict[str, exemplar_lib.SpeciesModel] | None = None):
        self.settings = settings
        self.species = species or exemplar_lib.species_models()
        self.exemplars = exemplars or {}
        self._built: dict[str, lod.BuiltModel] = {}

    @classmethod
    def from_config(cls, config: dict, base_dir: Path | None = None) -> "ModelRegistry":
        if not isinstance((config.get("assets") or {}).get("models"), dict):
            # Un config.yml sans bloc assets.models (anciens essais) ne peut avoir aucun exemplaire : seuls les modèles
            # génériques sont écrits, avec les réglages d'affichage du config.yml du dépôt, et c'est dit (jamais en silence).
            from sylvigenese import common
            from sylvigenese.assets_lib import initial_state
            repo = common.read_config(initial_state.ROOT / "config.yml")
            print("[assets] ATTENTION : assets.models absent de config.yml : budgets de triangles et seuils des niveaux de "
                  "détail lus dans le config.yml du dépôt (modèles génériques seulement, aucun exemplaire)", file=sys.stderr)
            config = {**config, "assets": {**(config.get("assets") or {}), "models": repo["assets"]["models"]}}
        settings = settings_from_config(config, base_dir)
        species = exemplar_lib.species_models()
        found = exemplar_lib.read_directory(settings.exemplars_dir, species) if settings.exemplars_dir else {}
        return cls(settings, found, species)

    def resolve(self, code: str, stage: str) -> tuple[str, str]:
        """(nom du modèle sans .glb, genre `own` | `alias` | `generic`) d'un arbre : jamais un emprunt (Q3)."""
        model = self.species.get(code)
        if model is None:
            raise ModuleError(f"essence {code} absente de contracts/species.csv")
        if model.essence and (model.essence, stage) in self.exemplars:
            return f"{model.owner}_{stage}", ("own" if model.owner == code else "alias")
        return f"generique_{model.group}", "generic"

    def model(self, stem: str) -> lod.BuiltModel:
        """Le modèle construit de ce nom (mis en cache)."""
        if stem not in self._built:
            if stem.startswith("generique_"):
                self._built[stem] = generic_model(stem.split("_", 1)[1])
            else:
                code, _, stage = stem.rpartition("_")
                model = self.species[code]
                self._built[stem] = own_model(self.exemplars[(model.essence, stage)], model, self.settings)
        return self._built[stem]

    def own_stems(self) -> list[str]:
        """Un nom de fichier par exemplaire lu, dans l'ordre des noms."""
        return sorted(f"{self.species_owner(essence)}_{stage}" for essence, stage in self.exemplars)

    def species_owner(self, essence: str) -> str:
        return next(m.owner for m in self.species.values() if m.essence == essence)

    def scale(self, stems: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """(h_ref, r_ref) de chaque instance, d'après le nom de son modèle."""
        refs = {s: (self.model(s).h_ref_m, self.model(s).r_ref_m) for s in set(stems.tolist())}
        h_ref = np.array([refs[s][0] for s in stems.tolist()], dtype="float64")
        r_ref = np.array([refs[s][1] for s in stems.tolist()], dtype="float64")
        return h_ref, r_ref
