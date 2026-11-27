"""Du segment au .glb (mission 070) : repère z-up -> y-up, tubes, cartes de feuillage, trois niveaux de détail,
extras, identité à l'octet près. Exemplaires SYNTHÉTIQUES (exemplars_synthetiques.py), aucune valeur écologique."""

import hashlib
import json
import subprocess
import sys

import numpy as np
import pytest
import yaml

import exemplars_synthetiques as F
from sylvigenese.assets_lib import exemplars, glb, lod, models
from sylvigenese.common import ModuleError

from test_assets import ROOT

REPO = yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8"))
BUDGETS = REPO["assets"]["models"]["triangle_budgets"]
COVER = REPO["assets"]["models"]["screencoverage"]


def registry(tmp_path, **overrides):
    config = yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8"))
    config["assets"]["models"]["exemplars_dir"] = str(tmp_path)
    for key, value in overrides.items():
        config["assets"]["models"][key] = value
    return models.ModelRegistry.from_config(config)


@pytest.fixture
def reg(tmp_path):
    F.write_set(tmp_path)
    return registry(tmp_path)


def read(stem, reg):
    data = glb.model_bytes(reg.model(stem), reg.settings.screencoverage)
    doc, binary = glb.read_container(data)
    return data, doc, binary


def level_positions(doc, binary, level):
    mesh = doc["meshes"][doc["nodes"][level]["mesh"]] if level == 0 else doc["meshes"][level]
    out = []
    for prim in mesh["primitives"]:
        acc = doc["accessors"][prim["attributes"]["POSITION"]]
        view = doc["bufferViews"][acc["bufferView"]]
        out.append(np.frombuffer(binary, dtype="<f4", count=3 * acc["count"], offset=view["byteOffset"]).reshape(-1, 3))
    return np.vstack(out)


# ------------------------------------------------------------------ repère
def test_conversion_z_up_vers_y_up_sur_un_point_asymetrique():
    got = lod.to_y_up([2.0], [5.0], [14.4])
    assert got.tolist() == [[2.0, 14.4, -5.0]]            # (x, y, z) -> (x, z, -y) ; x != y


def test_la_branche_repere_se_retrouve_au_point_converti_et_pas_aux_fausses_conversions(tmp_path):
    F.write(tmp_path, "Fagus_sylvatica", "mature", seg=F.minimal("mature"))        # tige et branche repère seulement
    reg = registry(tmp_path)
    _, doc, binary = read("09_mature", reg)
    pos = level_positions(doc, binary, 0)
    h = 24.0
    good = np.array([2.0, 0.6 * h, -5.0])
    near = lambda q: float(np.min(np.linalg.norm(pos - np.array(q), axis=1)))          # noqa: E731
    assert near(good) < 0.1                                                           # sommet du tube repère (r1 = 4 cm)
    for wrong in ([2.0, 0.6 * h, 5.0], [5.0, 0.6 * h, -2.0], [2.0, 5.0, -0.6 * h], [-2.0, 0.6 * h, -5.0]):
        assert near(wrong) > 1.0, wrong
    assert pos[:, 2].max() < 1.0                         # tout est au nord (z <= 0) : x et y pas échangés, nord = -z
    assert pos[:, 0].min() > -1.0                        # tout est à l'est


def test_etendue_de_lod0_en_y_est_h_ref_et_la_base_est_en_zero(reg):
    for stage in F.STAGES:
        model = reg.model(f"09_{stage}")
        pos = model.levels[0].all_positions()
        assert pos[:, 1].max() == pytest.approx(model.h_ref_m, rel=1e-6)
        assert model.h_ref_m == pytest.approx(F.HEIGHT[stage], rel=0.01)                 # l'étendue z de l'exemplaire
        assert abs(pos[:, 1].min()) < 0.01 * model.h_ref_m
        for level in model.levels[1:]:                                                  # même hauteur, même base
            p = level.all_positions()
            assert abs(p[:, 1].max() - model.h_ref_m) < 0.01 * model.h_ref_m and abs(p[:, 1].min()) < 0.02 * model.h_ref_m


# ------------------------------------------------------------------ maillage
def test_les_tubes_ont_leur_face_vers_l_exterieur_et_2_k_triangles():
    p0, p1 = np.array([[0.0, 0.0, 0.0], [0.0, 2.0, 0.0]]), np.array([[1.0, 2.0, 0.3], [0.0, 3.0, 0.0]])
    positions, normals, indices = lod.tube_mesh(p0, p1, np.array([0.5, 0.3]), np.array([0.2, 0.3]), 6)
    triangles = indices.reshape(-1, 3)
    assert len(triangles) == 2 * 6 * 2 and positions.shape == (2 * 2 * 6, 3)
    for k in range(2):
        axis = (p1[k] - p0[k]) / np.linalg.norm(p1[k] - p0[k])
        tri = triangles[12 * k: 12 * (k + 1)]
        a, b, c = (positions[tri[:, i]] for i in range(3))
        centre = (a + b + c) / 3 - p0[k]
        radial = centre - np.outer(centre @ axis, axis)
        assert (np.einsum("ij,ij->i", np.cross(b - a, c - a), radial) > 0).all()
    assert np.allclose(np.linalg.norm(normals, axis=1), 1.0)


def test_segment_de_longueur_nulle_est_refuse():
    with pytest.raises(ModuleError, match="longueur nulle"):
        lod.tube_mesh(np.zeros((1, 3)), np.zeros((1, 3)), np.array([0.1]), np.array([0.1]), 4)


def test_cartes_de_feuillage_suspendues_sous_l_extremite():
    tips = np.array([[1.0, 10.0, -2.0], [0.0, 0.2, 0.0]])
    positions, normals, indices = lod.card_mesh(tips, 0.6)
    assert positions.shape == (16, 3) and len(indices) == 2 * 4 * 3          # 2 cartes, 4 triangles chacune
    assert positions[:8, 1].max() == pytest.approx(10.0)                      # bord haut = extrémité : jamais au-dessus
    assert positions[:8, 1].min() == pytest.approx(9.4)
    assert positions[8:, 1].min() >= 0.0                                      # une carte ne descend pas sous le sol
    assert (normals == np.array([0.0, 1.0, 0.0])).all()


def test_trois_niveaux_decroissants_sous_les_budgets_et_comptes_exacts(reg):
    model = reg.model("09_mature")
    counts = [level.triangles for level in model.levels]
    assert counts[0] > counts[1] > counts[2] >= 1
    assert counts[0] <= BUDGETS["lod0"] and counts[1] <= BUDGETS["lod1"] and counts[2] <= BUDGETS["lod2"]
    seg = F.segments("mature")
    cards = model.measures["cards"][0]
    assert counts[0] == 12 * len(seg["x0"]) + 4 * cards                       # tubes de 6 faces, tout gardé, 4 triangles/carte
    assert counts[1] == 8 * len(seg["x0"]) + 4 * model.measures["cards"][1]    # tubes de 4 faces, niveaux 0 à 2
    assert counts[2] == 8 + 3 * 6                                              # tige de 4 faces + trois plans de 6 triangles
    assert model.levels[0].primitives[0].name == "ecorce" and model.levels[0].primitives[1].name == "feuillage"


def test_le_budget_reduit_les_branches_les_plus_fines_et_garde_la_tige(tmp_path):
    F.write(tmp_path, "Fagus_sylvatica", "mature")
    small = registry(tmp_path, triangle_budgets={"lod0": 600, "lod1": 300, "lod2": 100})
    model = small.model("09_mature")
    assert [lv.triangles for lv in model.levels][0] <= 600
    assert model.levels[0].triangles > model.levels[1].triangles > model.levels[2].triangles
    assert model.h_ref_m == pytest.approx(24.0, rel=0.01)                      # la tige est gardée entière
    bark = model.levels[0].primitives[0]
    assert bark.triangles == (bark.triangles // 12) * 12 and bark.triangles // 12 < len(F.segments("mature")["x0"])


def test_un_budget_trop_petit_pour_la_tige_est_un_refus(tmp_path):
    F.write(tmp_path, "Fagus_sylvatica", "mature")
    tiny = registry(tmp_path, triangle_budgets={"lod0": 100, "lod1": 50, "lod2": 20})
    with pytest.raises(ModuleError, match="tige"):
        tiny.model("09_mature")


def test_exemplaire_sans_tige_est_un_refus(tmp_path):
    seg = F.segments("mature")
    seg["niveau"] = np.maximum(seg["niveau"], 1)
    F.write(tmp_path, "Fagus_sylvatica", "mature", seg=seg)
    with pytest.raises(ModuleError, match="sans tige"):
        registry(tmp_path).model("09_mature")


def test_bouts_de_branche_un_par_axe():
    seg = F.segments("mature")
    ids = np.arange(len(seg["x0"]))
    p0, p1 = lod.to_y_up(seg["x0"], seg["y0"], seg["z0"]), lod.to_y_up(seg["x1"], seg["y1"], seg["z1"])
    tips = lod.branch_tips(p0, p1, seg["r0_m"], seg["niveau"], seg["axe"], ids)
    assert len(tips) == len(set(seg["axe"].tolist()))
    assert len(set(seg["axe"][tips].tolist())) == len(tips)
    # le bout de la tige (axe 0) est son segment le plus haut
    assert p1[tips[seg["axe"][tips] == 0][0]][1] == pytest.approx(24.0)


# ------------------------------------------------------------------ .glb : forme, extras, identité
def test_glb_trois_niveaux_msft_lod_et_extras(reg):
    data, doc, binary = read("09_mature", reg)
    assert "MSFT_lod" in doc["extensionsUsed"] and doc["scenes"][0]["nodes"] == [0]
    assert doc["nodes"][0]["extensions"]["MSFT_lod"]["ids"] == [1, 2]
    assert doc["nodes"][0]["extras"]["MSFT_screencoverage"] == COVER
    extras = doc["extras"]
    assert extras["species"] == "09" and extras["stage"] == "mature" and extras["essence_generateur"] == "Fagus_sylvatica"
    assert extras["source_commit"] == "0000000" and extras["graine"] == 7 and extras["synthetique"] is True
    assert extras["D_cm"] == 30.0 and extras["H_m"] == 24.0 and extras["b_cible"] == 1.0
    assert extras["H_ref_m"] == pytest.approx(24.0, rel=0.01) and extras["rayon_houppier_ref_m"] > 0
    assert extras["feuillage"]["type"] == "cartes_couleur_unie" and extras["feuillage"]["couleur"].startswith("#")
    assert extras["calage"] == "calé" and "calage_raisons" not in extras     # b_cible visé, aucune raison dite
    assert len(data) % 4 == 0 and data[:4] == b"glTF"


def test_resineux_marque_non_cale_et_b_cible_absent(tmp_path):
    F.write(tmp_path, "Abies_alba", "young", meta={"b_cible": None, "calage": "non calé", "calage_raisons": "essai"})
    F.write(tmp_path, "Abies_alba", "pole", meta={"b_cible": "1.0"})          # `calage` de la fixture : « non calé », recopié
    F.write(tmp_path, "Fagus_sylvatica", "young", meta={"b_cible": None, "calage": "non calé"})
    reg = registry(tmp_path)
    young = reg.model("61_young").extras
    assert young["calage"] == "non calé" and young["calage_raisons"] == "essai" and "b_cible" not in young
    pole = reg.model("61_pole").extras
    assert pole["calage"] == "non calé" and "résineux" in pole["calage_raisons"] and pole["b_cible"] == 1.0
    assert reg.model("09_young").extras["calage"] == "non calé"                # dit par l'export, repris tel quel


def test_couleur_du_feuillage_par_essence_puis_par_groupe(tmp_path):
    F.write(tmp_path, "Fagus_sylvatica", "mature")
    F.write(tmp_path, "Abies_alba", "mature")
    config = yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8"))
    config["assets"]["models"]["exemplars_dir"] = str(tmp_path)
    config["viewer"]["foliage"]["color_by_essence"] = {"Fagus_sylvatica": "#112233"}
    reg = models.ModelRegistry.from_config(config)
    assert reg.model("09_mature").extras["feuillage"]["couleur"] == "#112233"
    assert reg.model("61_mature").extras["feuillage"]["couleur"] == config["viewer"]["foliage"]["color_by_group"]["resineux"]
    colour = reg.model("09_mature").levels[0].primitives[1].color
    assert colour == models.srgb_to_linear("#112233")


def test_deux_executions_donnent_les_memes_octets_et_un_segment_modifie_les_change(tmp_path):
    F.write_set(tmp_path / "a")
    F.write_set(tmp_path / "b")
    one, two = registry(tmp_path / "a"), registry(tmp_path / "b")
    for stem in one.own_stems():
        bytes_a = glb.model_bytes(one.model(stem), one.settings.screencoverage)
        bytes_b = glb.model_bytes(two.model(stem), two.settings.screencoverage)
        assert bytes_a == bytes_b, stem
    seg = F.segments("mature", 11)
    seg["x1"] = seg["x1"].copy()
    seg["x1"][-1] += 0.05                                                        # un segment, 5 cm
    F.write(tmp_path / "a", "Fagus_sylvatica", "mature", seg=seg)
    changed = registry(tmp_path / "a")
    assert glb.model_bytes(changed.model("09_mature"), changed.settings.screencoverage) \
        != glb.model_bytes(one.model("09_mature"), one.settings.screencoverage)
    assert glb.model_bytes(changed.model("09_old"), changed.settings.screencoverage) \
        == glb.model_bytes(one.model("09_old"), one.settings.screencoverage)      # les autres modèles ne bougent pas


def test_ecriture_des_fichiers_un_par_essence_et_stade_sans_doublon_d_alias(tmp_path):
    F.write_set(tmp_path / "ex")
    reg = registry(tmp_path / "ex")
    written = glb.write_models(reg, tmp_path / "out", {"generique_resineux"})
    names = sorted(p.name for p in written)
    assert names == sorted([f"{c}_{s}.glb" for c in ("02", "09", "61") for s in F.STAGES] + ["generique_resineux.glb"])
    assert not any(n.startswith("03_") for n in names)
    again = glb.write_models(reg, tmp_path / "out2", {"generique_resineux"})
    assert [hashlib.sha256(p.read_bytes()).hexdigest() for p in written] \
        == [hashlib.sha256(p.read_bytes()).hexdigest() for p in again]


def validate(path):
    return subprocess.run([sys.executable, str(ROOT / "contracts" / "validate"), "assets.tree_model", str(path)],
                          capture_output=True, text=True, cwd=ROOT)


def test_le_validateur_du_projet_accepte_le_feuillu_et_les_generiques(tmp_path, reg):
    for stem in ("09_mature", "02_young"):
        path = tmp_path / f"{stem}.glb"
        path.write_bytes(glb.model_bytes(reg.model(stem), reg.settings.screencoverage))
        result = validate(path)
        assert result.returncode == 0, result.stdout + result.stderr
    for group in models.GROUPS:
        path = tmp_path / f"generique_{group}.glb"
        path.write_bytes(glb.model_bytes(models.generic_model(group), reg.settings.screencoverage))
        result = validate(path)
        assert result.returncode == 0, result.stdout + result.stderr


def test_le_validateur_accepte_le_resineux_non_cale_sans_b_cible(tmp_path):
    F.write(tmp_path, "Abies_alba", "young", meta={"b_cible": None, "calage": "non calé", "calage_raisons": "essai"})
    F.write(tmp_path, "Abies_alba", "mature")
    reg = registry(tmp_path)
    for stem in ("61_young", "61_mature"):
        path = tmp_path / f"{stem}.glb"
        path.write_bytes(glb.model_bytes(reg.model(stem), reg.settings.screencoverage))
        result = validate(path)
        assert result.returncode == 0, result.stdout + result.stderr


def test_generique_trois_niveaux_signales():
    for group in models.GROUPS:
        model = models.generic_model(group)
        counts = [level.triangles for level in model.levels]
        assert counts[0] > counts[1] > counts[2] >= 1
        assert model.extras == {"generique": True, "groupe": group, "provisoire": True, "synthetique": True}
        assert (model.h_ref_m, model.r_ref_m) == (1.0, 1.0)
        top = model.levels[0].all_positions()
        assert top[:, 1].max() == pytest.approx(1.0) and np.hypot(top[:, 0], top[:, 2]).max() <= 1.0 + 1e-6


def test_resolution_du_modele_alias_generique_et_jamais_un_emprunt(tmp_path):
    F.write(tmp_path, "Quercus_spec", "mature")
    F.write(tmp_path, "Fagus_sylvatica", "old")
    reg = registry(tmp_path)
    assert reg.resolve("02", "mature") == ("02_mature", "own")
    assert reg.resolve("03", "mature") == ("02_mature", "alias")              # même essence : même fichier
    assert reg.resolve("03", "young") == ("generique_feuillu", "generic")     # stade sans exemplaire : générique
    assert reg.resolve("09", "mature") == ("generique_feuillu", "generic")    # pas de chêne emprunté pour le hêtre
    assert reg.resolve("09", "old") == ("09_old", "own")
    assert reg.resolve("62", "mature") == ("generique_resineux", "generic")   # épicéa : aucun exemplaire
    assert reg.resolve("10", "mature") == ("generique_feuillu", "generic")    # châtaignier : aucun modèle du générateur
    with pytest.raises(ModuleError, match="absente de contracts/species.csv"):
        reg.resolve("99Z", "mature")


def test_reglages_absents_ou_incoherents_sont_des_erreurs():
    with pytest.raises(ModuleError, match="assets.models"):
        models.settings_from_config({"zone": "z"})
    base = yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8"))
    for key, value in (("triangle_budgets", {"lod0": 100, "lod1": 200, "lod2": 10}), ("screencoverage", [0.1, 0.2, 0.3])):
        bad = json.loads(json.dumps(base))
        bad["assets"]["models"][key] = value
        with pytest.raises(ModuleError):
            models.settings_from_config(bad)
