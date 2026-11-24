"""Emprise du Lambert-93 : refuse des x et y inversés ou un autre système (spec §7).

L'emprise est lue dans `contracts/lambert93_extent.json` (valeurs provisoires). Ordre des
axes : x = est, y = nord, en mètres, EPSG:2154.
"""
import json
import math
from functools import lru_cache
from pathlib import Path

CONTRACTS_DIR = Path(__file__).resolve().parent.parent


@lru_cache(maxsize=1)
def load_extent():
    with open(CONTRACTS_DIR / "lambert93_extent.json", encoding="utf-8") as f:
        return json.load(f)


def show(v):
    """Coordonnée en mètres, sans notation scientifique."""
    return f"{v:.2f}".rstrip("0").rstrip(".")


def point_problem(x, y):
    """Message si (x, y) tombe hors de l'emprise, None sinon."""
    e = load_extent()
    if x is None or y is None or not math.isfinite(x) or not math.isfinite(y):
        return f"coordonnées absentes ou non finies (x = {x}, y = {y})"
    parts = []
    if not e["x_min"] <= x <= e["x_max"]:
        parts.append(f"x = {show(x)} hors de [{e['x_min']}, {e['x_max']}]")
    if not e["y_min"] <= y <= e["y_max"]:
        parts.append(f"y = {show(y)} hors de [{e['y_min']}, {e['y_max']}]")
    if not parts:
        return None
    hint = ""
    if e["x_min"] <= y <= e["x_max"] and e["y_min"] <= x <= e["y_max"]:
        hint = " ; x et y semblent inversés"
    return "coordonnées hors de l'emprise Lambert-93 : " + ", ".join(parts) + hint


def bounds_problem(x_min, y_min, x_max, y_max):
    """Message si un rectangle sort de l'emprise, None sinon."""
    for x, y in ((x_min, y_min), (x_max, y_max)):
        problem = point_problem(x, y)
        if problem:
            return problem
    return None
