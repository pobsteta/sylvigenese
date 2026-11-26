"""Les .glb d'arbres produits par `assets` à partir des exemplaires de la fixture (mission 069, plan §6).

Par couple (essence, stade) : trois niveaux de détail (MSFT_lod), triangles strictement décroissants et sous les
budgets de config.yml, étendue de LOD0 en +Y = H_ref_m à 1 %, sommets finis, extras, nom conforme au catalogue et à
species.csv, repère (x, y, z) -> (x, z, -y). Lus par l'analyseur indépendant tests/m6/glb.py.
Rouge attendu tant que les missions 070 (D) n'ont pas rendu les .glb.
"""
import json
import subprocess

import numpy as np
import pytest

import helpers_m6 as M
from glb import Glb, z_up_to_y_up

# (code espar qui porte le fichier, essence du générateur) des essences de la fixture
PROPRES = [("09", "Fagus_sylvatica"), ("02", "Quercus_spec"), ("61", "Abies_alba")]
COUPLES = [(e, c, s) for c, e in PROPRES for s in M.STAGES]
IDS = [f"{c}_{s}" for _, c, s in COUPLES]
BUDGETS = M.repo_config()["assets"]["models"]["triangle_budgets"]
SCREEN = M.repo_config()["assets"]["models"]["screencoverage"]


@pytest.fixture(scope="module")
def zdir(zone_a):
    return M.exige(zone_a)


def test_un_glb_par_essence_et_stade_et_aucun_autre_modele_propre(zdir):
    f = M.glb_files(zdir)
    attendus = {f"{c}_{s}" for _, c, s in COUPLES}
    propres = {k for k in f if not k.startswith("generique_")}
    assert propres == attendus, f"manquants : {sorted(attendus - propres)} ; en trop : {sorted(propres - attendus)}"


def test_aucun_fichier_pour_un_alias_ni_pour_une_essence_sans_exemplaire(zdir):
    f = M.glb_files(zdir)
    interdits = [k for k in f if k.split("_")[0] in ("03", "62", "64", "10")]
    assert not interdits, f"doublon d'alias ou emprunt : {interdits}"


def test_le_generique_resineux_existe_pour_62_et_64_sans_exemplaire(zdir):
    assert "generique_resineux" in M.glb_files(zdir)


@pytest.mark.parametrize("essence,code,stage", COUPLES, ids=IDS)
def test_le_glb_est_conforme_au_contrat_du_projet(zdir, essence, code, stage):
    p = M.glb_files(zdir).get(f"{code}_{stage}")
    assert p is not None, f"assets/trees/{code}_{stage}.glb absent"
    r = subprocess.run(["python3", str(M.ROOT / "contracts" / "validate"), "assets.tree_model", str(p)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.parametrize("essence,code,stage", COUPLES, ids=IDS)
def test_trois_niveaux_decroissants_sous_les_budgets(zdir, essence, code, stage):
    g = Glb(M.glb_files(zdir)[f"{code}_{stage}"])
    t = g.triangles()
    assert t[0] > t[1] > t[2] >= 1, f"triangles par niveau {t}"
    assert t[0] <= BUDGETS["lod0"] and t[1] <= BUDGETS["lod1"] and t[2] <= BUDGETS["lod2"], \
        f"triangles {t} au-dessus des budgets {BUDGETS}"
    assert g.screencoverage() == SCREEN, f"MSFT_screencoverage {g.screencoverage()} != config {SCREEN}"


@pytest.mark.parametrize("essence,code,stage", COUPLES, ids=IDS)
def test_sommets_finis_et_indices_valides(zdir, essence, code, stage):
    g = Glb(M.glb_files(zdir)[f"{code}_{stage}"])
    for k in range(3):
        pos, idx = g.lod(k)
        assert np.isfinite(pos).all(), f"LOD{k} : sommet non fini"
        assert idx.max() < len(pos) and len(idx) % 3 == 0


@pytest.mark.parametrize("essence,code,stage", COUPLES, ids=IDS)
def test_etendue_de_lod0_en_y_egale_H_ref_a_1_pour_cent_base_en_zero(zdir, essence, code, stage):
    g = Glb(M.glb_files(zdir)[f"{code}_{stage}"])
    pos, _ = g.lod(0)
    h_ref = g.extras["H_ref_m"]
    seg = M.exemplar_segments(essence, stage)
    z_exemplaire = max(seg["z0"].max(), seg["z1"].max())
    assert abs(pos[:, 1].max() - h_ref) <= 0.01 * h_ref, f"y max {pos[:, 1].max()} != H_ref_m {h_ref}"
    assert abs(pos[:, 1].min()) <= 0.01 * h_ref, f"base en y = {pos[:, 1].min()}"
    assert abs(h_ref - z_exemplaire) <= 0.01 * z_exemplaire, f"H_ref_m {h_ref} != étendue z de l'exemplaire {z_exemplaire}"
    # même base pour les trois niveaux : le niveau lointain ne saute pas
    for k in (1, 2):
        p, _ = g.lod(k)
        assert abs(p[:, 1].max() - h_ref) <= 0.05 * h_ref and abs(p[:, 1].min()) <= 0.05 * h_ref, f"LOD{k} hors de [0, H_ref]"


@pytest.mark.parametrize("essence,code,stage", COUPLES, ids=IDS)
def test_repere_un_segment_connu_et_etendues_est_nord(zdir, essence, code, stage):
    """Piège de la Somalie : le générateur est z-up (x est, y nord, z haut) ; glTF est y-up (x est, y haut, z = -nord).
    La branche repère finit en (2, 5, 0,6 H) ; son extrémité doit être en (2, 0,6 H, -5), et rien ne doit exister
    aux conversions fausses ((2, 0,6 H, +5) = nord pris pour sud, (5, 0,6 H, -2) = x et y échangés)."""
    g = Glb(M.glb_files(zdir)[f"{code}_{stage}"])
    pos, _ = g.lod(0)
    seg = M.exemplar_segments(essence, stage)
    k = len(seg["x1"]) - 1
    p1 = np.array([seg["x1"][k], seg["y1"][k], seg["z1"][k]])
    assert tuple(p1[:2]) == (2.0, 5.0)
    r1 = seg["r1_m"][k]
    bon = z_up_to_y_up(p1)
    marge = r1 + 0.5          # tube (r1) et, selon Q2, carte de feuillage (moitié de card_size_m 0,6 en diagonale)

    def proche(q):
        return float(np.min(np.linalg.norm(pos - q, axis=1)))

    assert np.allclose(bon, [2.0, 0.6 * float(M.exemplar_meta(essence, stage)["H_m"]), -5.0])
    assert proche(bon) <= marge, f"aucun sommet près de {bon} (le plus proche : {proche(bon):.3f} m)"
    for faux in ([bon[0], bon[1], +5.0], [5.0, bon[1], -2.0], [2.0, 5.0, -bon[1]], [-2.0, bon[1], -5.0]):
        assert proche(np.array(faux)) > marge + 0.5, f"des sommets existent à la conversion fausse {faux}"
    # étendues : l'est reste +x, le nord (y >= 0 du générateur) est -z de glTF, rien au sud
    x_ex, y_ex = max(seg["x0"].max(), seg["x1"].max()), max(seg["y0"].max(), seg["y1"].max())
    assert pos[:, 0].max() >= x_ex - 0.1, "l'est du générateur n'est pas en +x"
    assert pos[:, 2].min() <= -y_ex + 0.1, "le nord du générateur n'est pas en -z"
    assert pos[:, 2].max() <= 1.0, f"du houppier au sud (z = {pos[:, 2].max():.2f}) : x, y inversés ou nord en +z"


@pytest.mark.parametrize("essence,code,stage", COUPLES, ids=IDS)
def test_extras_redisent_l_exemplaire_et_sont_synthetiques_provisoires(zdir, essence, code, stage):
    g = Glb(M.glb_files(zdir)[f"{code}_{stage}"])
    e, meta = g.extras, M.exemplar_meta(essence, stage)
    assert e["species"] == code and e["stage"] == stage and e["essence_generateur"] == essence
    assert e["source_commit"] == meta["source_commit"]
    for k in ("D_cm", "H_m", "hbh_m", "Rh_m", "b_cible"):
        assert e[k] == pytest.approx(float(meta[k])), f"extras.{k} != métadonnée de l'exemplaire"
    assert e["graine"] == int(meta["seed"])
    assert e["synthetique"] is True and e["provisoire"] is True
    assert e["rayon_houppier_ref_m"] > 0
    assert e["feuillage"]["type"] == "cartes_couleur_unie" and e["feuillage"]["couleur"].startswith("#")


@pytest.mark.parametrize("stage", M.STAGES)
def test_resineux_marque_non_cale_et_pas_le_hetre(zdir, stage):
    """Décision de Pascal (26/11/2026) : les résineux, dont la densité des rameaux est tirée et les stades jeune et
    perche extrapolés, sont marqués « non calé » dans les extras du modèle. Le hêtre ne l'est pas."""
    sapin = json.dumps(Glb(M.glb_files(zdir)[f"61_{stage}"]).extras, ensure_ascii=False)
    hetre = json.dumps(Glb(M.glb_files(zdir)[f"09_{stage}"]).extras, ensure_ascii=False)
    assert "non calé" in sapin, f"61_{stage}.glb : « non calé » absent des extras"
    assert "non calé" not in hetre, f"09_{stage}.glb : « non calé » ne vaut que pour les résineux"


def test_les_generiques_ont_aussi_trois_niveaux_et_sont_signales(zdir):
    g = Glb(M.glb_files(zdir)["generique_resineux"])
    t = g.triangles()
    assert t[0] > t[1] > t[2] >= 1
    assert g.extras["generique"] is True and g.extras["groupe"] == "resineux"
    assert g.extras["synthetique"] is True and g.extras["provisoire"] is True
