"""Mission 091 : le banc bench/m6/mesurer.py porte lui-même le scénario 2022 du stade sans exemplaire, sans donnée réelle.

Avant, m6_selftest.csv ne contenait ce cas que par le contrôle réel (m6_reel_zone, hors dépôt). Le scénario
`fictif_stade_sans_exemplaire_2022` rejoue la zone versionnée de viewer-massif/tests/fixtures : le test vérifie que le banc la
déclare, que ses arguments visent un point du bloc, et que les scénarios réels restent déclarés. La vue elle-même est jugée par
GUT (test_repli_generique_et_echelle.gd), qui compte 5 arbres dont 2 génériques sur cette même zone.
"""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def charger_banc():
    spec = importlib.util.spec_from_file_location("mesurer_m6", ROOT / "bench" / "m6" / "mesurer.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_le_banc_declare_le_scenario_2022_du_stade_sans_exemplaire_sur_la_zone_versionnee():
    banc = charger_banc()
    par_nom = {s["name"]: s for s in banc.scenarios()}
    sc = par_nom["fictif_stade_sans_exemplaire_2022"]
    assert sc["year"] == 2022
    zone = Path(sc["zone_dir"])
    assert zone.is_dir() and zone.is_relative_to(ROOT), "zone versionnée, aucune donnée sous data/"
    index = json.loads((zone / "massif" / "index.json").read_text(encoding="utf-8"))
    assert any(m["species"] == "09" and m["stage"] == "young" and m["kind"] == "generic" for m in index["stage_models"])
    assert sc["sans_temps"] and sc["essais"] == 1 and sc["phases"] is False


def test_les_scenarios_reels_restent_declares_et_les_noms_sont_uniques():
    banc = charger_banc()
    noms = [s["name"] for s in banc.scenarios()]
    assert len(noms) == len(set(noms))
    assert {"controle_reel_ifn_direct_2022_reprise_075", "controle_reel_ifn_direct_2032_reprise_075"} <= set(noms)


def test_les_arguments_du_selftest_visent_le_point_du_scenario():
    banc = charger_banc()
    sc = next(s for s in banc.scenarios() if s["name"] == "fictif_stade_sans_exemplaire_2022")
    args = banc.selftest_args(Path(sc["zone_dir"]), sc["year"], sc.get("extra"), sc["point"])
    assert args[args.index("--x") + 1] == "700250" and args[args.index("--y") + 1] == "6500250"
    assert args[args.index("--year") + 1] == "2022" and args[-1] == "--selftest"
    par_defaut = banc.selftest_args(Path("data/m6_essai"), 2037)
    assert par_defaut[par_defaut.index("--x") + 1] == f"{banc.POINT[0]:.0f}", "sans point : le point des zones d'essai"
