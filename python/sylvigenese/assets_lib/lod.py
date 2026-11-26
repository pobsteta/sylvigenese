"""Du segment au maillage : conversion z-up -> y-up, tubes, cartes de feuillage, trois niveaux de détail.

Étape du BRIEF codée : §4 et §9 (un `.glb` par essence et stade, avec ses niveaux de détail) ; plan
`docs/plans/m6a.md` T3 (réduction des segments), T6 (repères), Q2 (feuillage en cartes à couleur unie, par
essence, provisoire : illustration, aucune densité ni indice foliaire) et Q3 (modèle générique sans emprunt).
Mission 070. Aucun code du générateur : les entrées sont les segments d'un exemplaire (`exemplars.py`).

Repères (T6). Le générateur est z-up (x est, y nord, z haut) ; glTF est y-up. La conversion
(x, y, z) -> (x, z, -y) est faite ICI, une seule fois, sur les segments ; tout ce qui suit est en y-up
(x est, y haut, z = -nord), base du tronc en y = 0.

Règle de réduction (T3), qui ne dit rien d'écologique et se teste :
- la tige (niveau 0) est gardée entière dans les trois niveaux : tous les niveaux ont la même hauteur ;
- LOD0 : tubes de 6 faces ; les branches sont gardées par rayon décroissant (r0 de départ) tant que le
  budget de triangles de `config.yml` le permet ;
- LOD1 : tubes de 4 faces, tige et branches de niveaux 1 et 2 seulement, même règle de budget ;
- LOD2 : un tube de 4 faces pour la tige, et le houppier en croix de trois plans verticaux dont le contour
  suit les étendues MESURÉES du LOD0 ;
- feuillage (Q2) : à l'extrémité de chaque branche gardée, une carte en croix (deux quadrilatères verticaux), de
  couleur unie, suspendue sous l'extrémité (son bord haut est à l'extrémité : le feuillage ne dépasse jamais la
  hauteur du bois). Le nombre de cartes est plafonné à une part du budget (`FOLIAGE_SHARE`) ; aux niveaux
  grossiers, moins de cartes, plus grandes (même surface totale à peu près).
Les constantes de ce module (faces, part du feuillage, rayon plancher) sont des choix de dessin, signalés
et provisoires ; les budgets de triangles et la taille des cartes viennent de `config.yml`.

Tout est déterministe : mêmes segments, même configuration, mêmes sommets à l'octet près (numpy, sans
tirage aléatoire ; l'orientation d'une carte vient de son rang par la suite de la section d'or).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from sylvigenese.common import ModuleError

SIDES = (6, 4, 4)               # faces des tubes de LOD0, LOD1, LOD2 (choix de dessin, provisoire)
LOD1_MAX_NIVEAU = 2             # LOD1 : tige et branches de niveaux 1 et 2
FOLIAGE_SHARE = 0.25            # part du budget de triangles réservée aux cartes (choix de dessin, provisoire)
MIN_RADIUS_M = 0.001            # rayon plancher du maillage (1 mm) : pas de triangle dégénéré à la pointe
CROWN_PLANES = 3                # plans du houppier de LOD2
CROWN_BINS = 4                  # tranches de hauteur du contour de LOD2
GOLDEN = 0.6180339887498949
BARK, FOLIAGE = "ecorce", "feuillage"


@dataclass
class Primitive:
    """Un morceau de maillage d'un seul matériau (positions et normales float32, indices non signés)."""
    name: str
    positions: np.ndarray
    normals: np.ndarray
    indices: np.ndarray
    color: list[float]

    @property
    def triangles(self) -> int:
        return len(self.indices) // 3


@dataclass
class Level:
    primitives: list[Primitive]

    @property
    def triangles(self) -> int:
        return sum(p.triangles for p in self.primitives)

    def all_positions(self) -> np.ndarray:
        return np.vstack([p.positions for p in self.primitives])


@dataclass
class BuiltModel:
    """Un modèle prêt à écrire : trois niveaux, hauteur et rayon de référence, extras du .glb."""
    stem: str                                  # nom du fichier sans .glb
    kind: str                                  # own | generic
    levels: list[Level]
    h_ref_m: float
    r_ref_m: float
    extras: dict
    node_extras: dict = field(default_factory=dict)
    measures: dict = field(default_factory=dict)


def to_y_up(x, y, z) -> np.ndarray:
    """Repère du générateur (z-up : x est, y nord, z haut) -> glTF (y-up) : (x, y, z) -> (x, z, -y)."""
    return np.column_stack([np.asarray(x, dtype="float64"), np.asarray(z, dtype="float64"),
                            -np.asarray(y, dtype="float64")])


def tube_mesh(p0: np.ndarray, p1: np.ndarray, r0: np.ndarray, r1: np.ndarray, sides: int):
    """Tubes (troncs de cône) de `sides` faces, sans bouchons : positions (m * 2 * sides, 3), normales, indices.

    Un tube a 2 * sides triangles. Orientation : face extérieure en sens direct (anti-horaire vu du dehors)."""
    m = len(p0)
    axis = p1 - p0
    length = np.linalg.norm(axis, axis=1)
    if (length <= 1e-9).any():
        raise ModuleError("segment de longueur nulle : un exemplaire ne peut pas être maillé")
    unit = axis / length[:, None]
    helper = np.where((np.abs(unit[:, 1]) < 0.9)[:, None], np.array([0.0, 1.0, 0.0]), np.array([1.0, 0.0, 0.0]))
    u = np.cross(unit, helper)
    u /= np.linalg.norm(u, axis=1, keepdims=True)
    v = np.cross(unit, u)
    theta = 2.0 * math.pi * np.arange(sides) / sides
    radial = np.cos(theta)[None, :, None] * u[:, None, :] + np.sin(theta)[None, :, None] * v[:, None, :]
    ring0 = p0[:, None, :] + np.maximum(r0, MIN_RADIUS_M)[:, None, None] * radial
    ring1 = p1[:, None, :] + np.maximum(r1, MIN_RADIUS_M)[:, None, None] * radial
    positions = np.concatenate([ring0, ring1], axis=1).reshape(-1, 3)
    normals = np.concatenate([radial, radial], axis=1).reshape(-1, 3)
    i = np.arange(sides)
    j = (i + 1) % sides
    local = np.stack([np.stack([i, j, sides + i], axis=1), np.stack([j, sides + j, sides + i], axis=1)], axis=1)
    local = local.reshape(-1, 3)                                              # (2 * sides, 3)
    indices = (local[None, :, :] + (np.arange(m) * 2 * sides)[:, None, None]).reshape(-1)
    return positions, normals, indices


def card_mesh(tips: np.ndarray, size: float):
    """Une carte en croix (deux quadrilatères verticaux) par extrémité de branche.

    Le bord haut de la carte est à l'extrémité (elle est suspendue dessous) ; la carte ne descend pas sous
    y = 0. Orientation : angle 2π·frac(rang × section d'or). 4 triangles et 8 sommets par carte."""
    n = len(tips)
    half = size / 2.0
    angle = 2.0 * math.pi * np.modf(np.arange(n) * GOLDEN)[0]
    d1 = np.stack([np.cos(angle), np.zeros(n), np.sin(angle)], axis=1)
    d2 = np.stack([-np.sin(angle), np.zeros(n), np.cos(angle)], axis=1)
    center = tips.copy()
    center[:, 1] = np.maximum(tips[:, 1] - half, half)
    up = np.array([0.0, half, 0.0])
    quads = []
    for d in (d1, d2):
        quads.append(np.stack([center - half * d - up, center + half * d - up,
                               center + half * d + up, center - half * d + up], axis=1))
    positions = np.concatenate(quads, axis=1).reshape(-1, 3)                       # (n * 8, 3)
    normals = np.tile(np.array([0.0, 1.0, 0.0]), (len(positions), 1))
    pattern = np.array([0, 1, 2, 0, 2, 3, 4, 5, 6, 4, 6, 7])
    indices = (pattern[None, :] + (np.arange(n) * 8)[:, None]).reshape(-1)
    return positions, normals, indices


def _index_dtype(vertex_count: int):
    return np.uint16 if vertex_count < 65536 else np.uint32


def _primitive(name: str, parts: list, color: list[float]) -> Primitive:
    """Assemble des (positions, normales, indices) en une primitive float32 ; indices décalés."""
    positions, normals, indices, base = [], [], [], 0
    for p, n, i in parts:
        positions.append(p)
        normals.append(n)
        indices.append(i + base)
        base += len(p)
    pos = np.concatenate(positions).astype("float32")
    nor = np.concatenate(normals).astype("float32")
    idx = np.concatenate(indices).astype(_index_dtype(len(pos)))
    return Primitive(name, pos, nor, idx, color)


def branch_tips(p0, p1, r0, niveau, axe, kept: np.ndarray) -> np.ndarray:
    """Indices des segments « bout de branche » parmi `kept` : un par axe (un axe = une branche).

    La base d'un axe est le début de son segment le plus gros ; son bout est le segment dont la fin est la plus
    éloignée de cette base (égalités : plus petit indice). Les axes sont rendus triés (niveau, axe)."""
    ids = kept
    axis_of = axe[ids]
    order = np.lexsort((ids, -r0[ids], axis_of))                  # par axe, le plus gros d'abord
    firsts = np.ones(len(order), dtype=bool)
    firsts[1:] = axis_of[order][1:] != axis_of[order][:-1]
    base_of_axis = {int(a): p0[i] for a, i in zip(axis_of[order][firsts], ids[order][firsts])}
    base = np.stack([base_of_axis[int(a)] for a in axis_of])
    distance = np.linalg.norm(p1[ids] - base, axis=1)
    order = np.lexsort((ids, -distance, axis_of))
    firsts = np.ones(len(order), dtype=bool)
    firsts[1:] = axis_of[order][1:] != axis_of[order][:-1]
    tips = ids[order][firsts]
    rank = np.where(niveau[tips] < 0, 10 ** 6, niveau[tips])      # les réitérations après les branches
    return tips[np.lexsort((axe[tips], rank))]


def _evenly(items: np.ndarray, count: int) -> np.ndarray:
    """`count` éléments régulièrement répartis (déterministe) dans `items`."""
    if count >= len(items):
        return items
    if count <= 0:
        return items[:0]
    return items[np.unique(np.round(np.linspace(0, len(items) - 1, count)).astype(int))]


def wood_level(seg: dict, level: int, budget: int, card_size: float, bark_color, foliage_color,
               sizes_hint: float | None = None) -> tuple[Level, int]:
    """LOD0 ou LOD1 d'un exemplaire (segments déjà en y-up dans `seg`). Rend (niveau, nombre de cartes)."""
    sides = SIDES[level]
    cost = 2 * sides
    p0, p1, r0, r1, niveau, axe = (seg[k] for k in ("p0", "p1", "r0", "r1", "niveau", "axe"))
    index = np.arange(len(p0))
    trunk = index[niveau == 0]
    if level == 0:
        branches = index[niveau != 0]
    else:
        branches = index[(niveau >= 1) & (niveau <= LOD1_MAX_NIVEAU)]
    allowed = int(math.floor((1.0 - FOLIAGE_SHARE) * budget / cost))
    if len(trunk) == 0:
        raise ModuleError("exemplaire sans tige (niveau 0) : aucun modèle ne peut être bâti")
    if len(trunk) > allowed:
        raise ModuleError(f"niveau de détail {level} : la tige ({len(trunk)} segments à {cost} triangles) ne tient pas "
                          f"dans le budget de {budget} triangles")
    ranked = branches[np.lexsort((branches, -r0[branches]))]
    kept = np.concatenate([trunk, ranked[: allowed - len(trunk)]])
    kept.sort()
    wood = tube_mesh(p0[kept], p1[kept], r0[kept], r1[kept], sides)
    tips = branch_tips(p0, p1, r0, niveau, axe, kept)
    room = int(math.floor((budget - cost * len(kept)) / 4))
    chosen = _evenly(tips, min(len(tips), room))
    scale = 1.0 if sizes_hint is None or len(chosen) == 0 else math.sqrt(max(sizes_hint / len(chosen), 1.0))
    cards = card_mesh(p1[chosen], card_size * scale)
    primitives = [_primitive(BARK, [wood], bark_color), _primitive(FOLIAGE, [cards], foliage_color)]
    return Level(primitives), int(len(chosen))


def crown_level(trunk_seg: dict, upper: np.ndarray, h_top: float, budget: int, bark_color, foliage_color) -> Level:
    """LOD2 : tige en un tube de 4 faces, houppier en croix de `CROWN_PLANES` plans, d'après les points `upper`
    (sommets du LOD0, y-up) : contour mesuré par tranches de hauteur, projeté sur chaque plan vertical."""
    low = float(upper[:, 1].min())
    p0, p1, r0, r1, niveau = (trunk_seg[k] for k in ("p0", "p1", "r0", "r1", "niveau"))
    stem = np.nonzero(niveau == 0)[0]
    base = stem[np.argmin(p0[stem, 1])]
    wanted = max(low, 0.1 * h_top)
    top = stem[np.argmin(np.abs(p1[stem, 1] - wanted))]
    if np.allclose(p1[top], p0[base]):
        top = stem[np.argmax(p1[stem, 1])]
    trunk = tube_mesh(p0[[base]], p1[[top]], np.array([r0[stem].max()]), np.array([r1[top]]), SIDES[2])
    edges = np.linspace(low, h_top, CROWN_BINS + 1)
    planes = []
    for k in range(CROWN_PLANES):
        angle = math.pi * k / CROWN_PLANES
        direction = np.array([math.cos(angle), 0.0, math.sin(angle)])
        along = upper @ direction
        lo, hi = [], []
        for b in range(CROWN_BINS):
            inside = (upper[:, 1] >= edges[b]) & ((upper[:, 1] <= edges[b + 1]) if b == CROWN_BINS - 1
                                                  else (upper[:, 1] < edges[b + 1]))
            if inside.any():
                lo.append(float(along[inside].min()))
                hi.append(float(along[inside].max()))
            else:                                                  # tranche vide : celle d'en dessous
                lo.append(lo[-1] if lo else 0.0)
                hi.append(hi[-1] if hi else 0.0)
        vertices = [0.5 * (lo[0] + hi[0]) * direction + np.array([0.0, edges[0], 0.0])]
        for e in range(1, CROWN_BINS):
            for value in (min(lo[e - 1], lo[e]), max(hi[e - 1], hi[e])):
                vertices.append(value * direction + np.array([0.0, edges[e], 0.0]))
        vertices.append(0.5 * (lo[-1] + hi[-1]) * direction + np.array([0.0, edges[-1], 0.0]))
        indices = [0, 1, 2]
        for e in range(CROWN_BINS - 2):
            a = 1 + 2 * e
            indices += [a, a + 1, a + 2, a + 1, a + 3, a + 2]
        last = 1 + 2 * (CROWN_BINS - 2)
        indices += [last, last + 1, len(vertices) - 1]
        planes.append((np.array(vertices), np.tile(np.array([0.0, 1.0, 0.0]), (len(vertices), 1)),
                       np.array(indices)))
    level = Level([_primitive(BARK, [trunk], bark_color), _primitive(FOLIAGE, planes, foliage_color)])
    if level.triangles > budget:
        raise ModuleError(f"niveau de détail 2 : {level.triangles} triangles, budget de {budget}")
    return level


def build_levels(segments: dict[str, np.ndarray], budgets: dict, card_size: float, bark_color, foliage_color
                 ) -> tuple[list[Level], dict]:
    """Les trois niveaux d'un exemplaire (segments z-up) ; rend (niveaux, mesures).

    Mesures : `h_ref_m` (étendue de LOD0 en +Y), `r_ref_m` (plus grande distance horizontale d'un sommet de
    LOD0 à l'axe de la tige), nombre de cartes par niveau. Triangles strictement décroissants et sous les
    budgets, sinon refus : un niveau qui ne baisse pas ne se corrige pas en silence."""
    seg = {"p0": to_y_up(segments["x0"], segments["y0"], segments["z0"]),
           "p1": to_y_up(segments["x1"], segments["y1"], segments["z1"]),
           "r0": segments["r0_m"], "r1": segments["r1_m"], "niveau": segments["niveau"], "axe": segments["axe"]}
    if (np.linalg.norm(seg["p1"] - seg["p0"], axis=1) <= 1e-9).any():
        keep = np.linalg.norm(seg["p1"] - seg["p0"], axis=1) > 1e-9      # segments de longueur nulle : sans objet
        seg = {k: v[keep] for k, v in seg.items()}
    level0, cards0 = wood_level(seg, 0, int(budgets["lod0"]), card_size, bark_color, foliage_color)
    level1, cards1 = wood_level(seg, 1, int(budgets["lod1"]), card_size, bark_color, foliage_color,
                                sizes_hint=float(cards0))
    upper = level0.all_positions().astype("float64")
    h_top = float(level0.all_positions()[:, 1].max())
    level2 = crown_level(seg, upper, h_top, int(budgets["lod2"]), bark_color, foliage_color)
    levels = [level0, level1, level2]
    counts = [lv.triangles for lv in levels]
    if not counts[0] > counts[1] > counts[2] >= 1:
        raise ModuleError(f"triangles par niveau {counts[0]}, {counts[1]}, {counts[2]} : strictement décroissants "
                          "attendus ; budgets ou exemplaire à revoir")
    for k, name in enumerate(("lod0", "lod1", "lod2")):
        if counts[k] > int(budgets[name]):
            raise ModuleError(f"niveau {name.upper()} : {counts[k]} triangles, budget de {budgets[name]}")
    positions = level0.all_positions()
    measures = {"h_ref_m": float(positions[:, 1].max()),
                "r_ref_m": float(np.sqrt(positions[:, 0].astype("float64") ** 2
                                         + positions[:, 2].astype("float64") ** 2).max()),
                "cards": [cards0, cards1], "triangles": counts, "segments": int(len(seg["p0"]))}
    if not measures["h_ref_m"] > 0 or not measures["r_ref_m"] > 0:
        raise ModuleError("exemplaire plat : hauteur ou rayon de référence nul")
    return levels, measures
