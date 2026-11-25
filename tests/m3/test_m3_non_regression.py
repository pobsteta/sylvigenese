"""M3a, non-régression (spec §11) : empreinte de VALEURS de la chaîne nominale (graine 42, 100 ans, jeu fictif),
figée dans tests/m3/reference/nominal.json. Elle ne vaut qu'une fois la simulation jugée juste par Pascal : la
figer est une décision, pas un réflexe. Tant que le fichier est absent, le test échoue en le disant.

Pour figer, après relecture des résultats :  SYLVIGENESE_M3_FREEZE=1 python3 -m pytest tests/m3/test_m3_non_regression.py
(le test écrit alors le fichier et vérifie qu'il se relit à l'identique)."""
import json
import os
from pathlib import Path

import numpy as np
import pytest

import helpers_m3 as H

REF = Path(__file__).parent / "reference" / "nominal.json"
T0 = H.SIM_NOMINAL["t0"]
ANNEES = (T0, T0 + 1, T0 + 10, T0 + 50, T0 + 100)


def empreinte(zdir):
    out = {"annees": {}}
    for y in ANNEES:
        t = H.read_year(zdir, "trees", y)
        vivants = t[t["status"] == "alive"]
        c = H.read_year(zdir, "cells", y)
        out["annees"][str(y)] = {
            "lignes": int(len(t)), "vivants": int(len(vivants)), "morts": int((t["status"] == "dead").sum()),
            "recrues": int(t["tree_id"].str.startswith("r").sum()),
            "somme_d130": float(vivants["d130"].sum()), "somme_h": float(vivants["h"].sum()),
            "somme_x": float(vivants["x"].sum()), "somme_y": float(vivants["y"].sum()),
            "g_total_m2_ha": float(c["basal_area_m2_ha"].sum()), "stems_total_ha": float(c["stems_ha"].sum()),
            "lignes_cellules": int(len(c)),
        }
    j = H.read_run_json(zdir)
    out["run"] = {k: j[k] for k in ("seed", "t0", "years", "zeroed_values", "provisional_share", "domain_outputs",
                                    "cells_at_height_ceiling", "edge_disks", "mixed_cells", "recruits", "deaths")}
    return out


def _egal(a, b, chemin=""):
    if isinstance(a, dict):
        assert set(a) == set(b), f"{chemin} : clés différentes {set(a) ^ set(b)}"
        for k in a:
            _egal(a[k], b[k], f"{chemin}/{k}")
    elif isinstance(a, float) or isinstance(b, float):
        assert a == pytest.approx(b, rel=1e-9, abs=1e-9), f"{chemin} : {a!r} contre {b!r}"
    else:
        assert a == b, f"{chemin} : {a!r} contre {b!r}"


def test_la_chaine_nominale_redonne_l_empreinte_figee(chaine):
    emp = empreinte(chaine["dir"])
    if os.environ.get("SYLVIGENESE_M3_FREEZE") == "1":
        REF.parent.mkdir(exist_ok=True)
        REF.write_text(json.dumps(emp, indent=1, sort_keys=True), encoding="utf-8")
    assert REF.is_file(), ("empreinte de non-régression absente (tests/m3/reference/nominal.json) : à figer, après "
                           "accord de Pascal sur les résultats, avec SYLVIGENESE_M3_FREEZE=1")
    _egal(json.loads(REF.read_text(encoding="utf-8")), json.loads(json.dumps(emp)))
