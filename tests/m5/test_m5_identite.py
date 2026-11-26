"""Identité au bit près entre 1 et N fils, au niveau SER (plan m5a, mission C, T10 ; risque « identité entre fils avec
la FFT », plan §6) : mêmes octets de chaque fichier de sim/ (SHA-256), run.json comparé sans les champs qui disent le
calcul et non le résultat (fils, durée, mémoire estimée et mesurée, empreinte de la config).

N = 40 avec 1, 2 et 7 fils (7 : nombre premier, découpages inégaux) ; N = 1 000 avec 1 et 4 fils (la taille de la CI)."""
import helpers_m5 as H


def _compare(r, digests, ref=1):
    assert r["proc"].returncode == 0, H.queue(r["proc"])
    assert ref in digests, f"l'exécution de référence à {ref} fil n'a pas réussi : identité non jugeable"
    a, b = digests[ref], H.sim_digest(r["dir"])
    assert set(a) == set(b), f"fichiers différents entre 1 et {r['threads']} fils : {sorted(set(a) ^ set(b))[:5]}"
    diff = [k for k in a if a[k] != b[k]]
    assert not diff, f"{len(diff)} fichiers différents entre 1 et {r['threads']} fils : {diff[:5]}"
    assert any(k.startswith("cohorts/") for k in a), "aucun fichier sim/cohorts comparé"


def test_ser_40_identite_entre_fils(ser_fils):
    _compare(ser_fils, ser_fils["digests"])
    assert H.read_run_json(ser_fils["dir"])["threads"] == ser_fils["threads"]


def test_ser_1000_identite_entre_1_et_4_fils(ser_1000):
    _compare(ser_1000, ser_1000["digests"])
