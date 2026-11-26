"""La fixture d'exemplaires synthétiques (tests/fixtures/exemplars_m6) tient son contrat (mission 069).

Ces tests passent dès la livraison de la fixture : ils prouvent que le matériau des autres tests est sain
(schéma assets.exemplars, repère z-up, valeurs marquées synthétiques, aucune valeur présentée comme écologique)."""
import importlib.util
import subprocess

import numpy as np
import pyarrow.parquet as pq
import pytest

import helpers_m6 as M

FICHIERS = sorted(M.EXEMPLARS.glob("*.parquet"))


def test_douze_fichiers_trois_essences_quatre_stades():
    assert [p.name for p in FICHIERS] == sorted(f"{e}_{s}.parquet" for e in M.FIXTURE_ESSENCES for s in M.STAGES)


@pytest.mark.parametrize("path", FICHIERS, ids=lambda p: p.stem)
def test_chaque_exemplaire_est_conforme_au_contrat(path):
    p = subprocess.run(["python3", str(M.ROOT / "contracts" / "validate"), "assets.exemplars", str(path)],
                       capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr


@pytest.mark.parametrize("path", FICHIERS, ids=lambda p: p.stem)
def test_repere_z_up_base_en_zero_et_sommet_a_H(path):
    meta = {k.decode(): v.decode() for k, v in pq.read_schema(path).metadata.items()}
    assert meta["frame"] == "z-up" and meta["units"] == "m"
    seg = {k: np.array(v) for k, v in pq.read_table(path).to_pydict().items()}
    z = np.concatenate([seg["z0"], seg["z1"]])
    assert abs(z.min()) < 1e-9, "la base du tronc doit être en z = 0"
    assert abs(z.max() - float(meta["H_m"])) < 1e-9, "le sommet est la hauteur H_m (z est le haut)"
    assert np.isfinite(np.vstack([seg[k] for k in ("x0", "y0", "z0", "x1", "y1", "z1", "r0_m", "r1_m")])).all()


@pytest.mark.parametrize("path", FICHIERS, ids=lambda p: p.stem)
def test_cime_asymetrique_et_branche_repere(path):
    """x et y ne se valent pas (piège de la Somalie) : tout est à y >= 0, la branche repère finit en (2, 5, 0,6 H)."""
    meta = {k.decode(): v.decode() for k, v in pq.read_schema(path).metadata.items()}
    seg = {k: np.array(v) for k, v in pq.read_table(path).to_pydict().items()}
    assert min(seg["y0"].min(), seg["y1"].min()) >= -1e-9
    assert seg["y1"].max() > 4.9
    k = len(seg["x1"]) - 1
    assert (seg["x1"][k], seg["y1"][k]) == (2.0, 5.0)
    assert abs(seg["z1"][k] - 0.6 * float(meta["H_m"])) < 1e-9


@pytest.mark.parametrize("path", FICHIERS, ids=lambda p: p.stem)
def test_tout_est_marque_synthetique_sans_valeur_presentee_comme_ecologique(path):
    meta = {k.decode(): v.decode() for k, v in pq.read_schema(path).metadata.items()}
    assert meta["synthetic"] == "true"
    assert "synthetique" in meta["fixture_note"] and "aucune valeur ecologique" in meta["fixture_note"]
    assert meta["source_commit"] == "0000000", "aucun commit de tarif-nemeton : le fichier n'en vient pas"
    # même suite de dimensions pour toutes les essences : une échelle de test, pas une dendrométrie
    assert meta["D_cm"] == repr({"young": 10.0, "pole": 20.0, "mature": 30.0, "old": 40.0}[meta["stage"]])
    assert meta["H_m"] == repr({"young": 8.0, "pole": 16.0, "mature": 24.0, "old": 32.0}[meta["stage"]])


def test_les_essences_de_la_fixture_sont_au_referentiel_et_62_64_n_ont_pas_d_exemplaire():
    essences = {r["tarif_nemeton_code"] for r in M.species_rows()}
    assert set(M.FIXTURE_ESSENCES) <= essences
    ex = {e for e, _ in M.exemplars_available()}
    assert "Picea_abies" not in ex and "Pseudotsuga_menziesii" not in ex       # 62 et 64 : générique attendu
    assert M.owner_of("03")[:2] == ("Quercus_spec", "02") and M.owner_of("02")[1] == "02"   # 03 est l'alias de 02


def test_la_fixture_se_regenere_a_l_identique(tmp_path):
    spec = importlib.util.spec_from_file_location("make_exemplars_m6", M.ROOT / "tests" / "fixtures" / "make_exemplars_m6.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for f in mod.write_all(tmp_path):
        a, b = pq.read_table(f), pq.read_table(M.EXEMPLARS / f.name)
        assert a.equals(b) and a.schema.metadata == b.schema.metadata, f.name
