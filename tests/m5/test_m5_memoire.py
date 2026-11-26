"""Mémoire du niveau SER (spec §11 ; plan m5a, T7 ; décision de Pascal Q5 du 26/11/2026 ; contrat run) :
à N = 1 000 (un million de cellules, 3 ans), l'estimation de mémoire du moteur (`memory_estimate_max_bytes`, la plus
grande faite avant les pas) est à moins de 10 % de la mémoire résidente maximale MESURÉE HORS DU MOTEUR (wait4,
ru_maxrss : le chiffre de /usr/bin/time -v), à 1 et à 4 fils. `memory_peak_rss_bytes` (VmHWM lu par le moteur) est
écrit, entier sous Linux, et concorde avec la mesure externe. Les comptes nouveaux de run.json sont des entiers."""
import helpers_m5 as H

COMPTES = ("zeroed_values", "seedling_stock_limited", "gaps_recolonised", "buffer_cells", "recruits", "deaths")


def _ok(r):
    assert r["proc"].returncode == 0, H.queue(r["proc"])


def test_estimation_de_memoire_a_moins_de_10_pour_cent_de_la_memoire_residente(ser_1000):
    _ok(ser_1000)
    j = H.read_run_json(ser_1000["dir"])
    est, rss = j.get("memory_estimate_max_bytes"), ser_1000["rss_bytes"]
    assert isinstance(est, int) and est > 0, f"memory_estimate_max_bytes : {est!r}"
    ecart = abs(est - rss) / rss
    assert ecart < 0.10, (f"[{ser_1000['threads']} fil(s)] estimation {est / 2**20:.1f} Mio, mémoire résidente "
                          f"mesurée {rss / 2**20:.1f} Mio : écart {100 * ecart:.1f} % (critère : < 10 %)")


def test_memory_peak_rss_bytes_concorde_avec_la_mesure_externe(ser_1000):
    _ok(ser_1000)
    j = H.read_run_json(ser_1000["dir"])
    v = j.get("memory_peak_rss_bytes")
    assert isinstance(v, int) and v > 0, f"memory_peak_rss_bytes sous Linux : {v!r} (null seulement hors de Linux)"
    assert abs(v - ser_1000["rss_bytes"]) / ser_1000["rss_bytes"] < 0.05, (v, ser_1000["rss_bytes"])


def test_l_estimation_maximale_couvre_celle_de_t0(ser_1000):
    _ok(ser_1000)
    j = H.read_run_json(ser_1000["dir"])
    assert j["memory_estimate_max_bytes"] >= j["memory_estimate_bytes"] > 0


def test_les_comptes_de_m5a_sont_des_entiers(ser_1000):
    _ok(ser_1000)
    j = H.read_run_json(ser_1000["dir"])
    for k in COMPTES:
        assert isinstance(j.get(k), int) and not isinstance(j.get(k), bool) and j[k] >= 0, f"{k} : {j.get(k)!r}"
    assert j["level"] == "ser" and j["recruitment"] == "cohorts"
    p = H.run_validate("run", str(ser_1000["dir"] / "sim" / "run.json"))
    assert p.returncode == 0, p.stdout[-800:]

