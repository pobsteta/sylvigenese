"""Vue web (mission 029) : la page servie en local charge la tuile, expose le nombre d'instances dessinées
(compté par l'API, spec §11 M4) et ouvre la fiche d'une cellule.

Interface exigée (voir l'en-tête de probe_view.cjs) :
  - `make viewer ZONE=<zone> CONFIG=<config> PORT=<port>` : serveur au premier plan sur http://127.0.0.1:<PORT>/,
    la page est à la racine ; il sert aussi tiles/ et web/ de la zone ;
  - window.sylvigenese = {ready, error, instanceCount, year, openCell(cell_id)} ;
  - fiche : élément [data-testid="cell-sheet"] avec data-cell-id.
Playwright est celui de Node (python3 n'a pas le paquet `playwright`) : un petit script CommonJS le pilote.
Le navigateur est coupé du réseau : la vue doit s'afficher sans service extérieur.
"""
import json
import os
import re
import signal
import socket
import subprocess
import time
import urllib.request

import pytest

import helpers_m4 as H

PROBE = H.HERE / "probe_view.cjs"


def _port_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Serveur:
    def __init__(self, zone: str, config=None):
        self.port = _port_libre()
        cmd = ["make", "viewer", f"ZONE={zone}", f"PORT={self.port}"]
        if config is not None:
            cmd.append(f"CONFIG={config}")
        self.proc = subprocess.Popen(cmd, cwd=H.ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                     start_new_session=True)
        self.url = f"http://127.0.0.1:{self.port}/"

    def attendre(self, delai=300):
        fin = time.time() + delai
        while time.time() < fin:
            if self.proc.poll() is not None:
                raise AssertionError(f"make viewer s'est arrêté (code {self.proc.returncode}) :\n{self.proc.stdout.read()[-1500:]}")
            try:
                with urllib.request.urlopen(self.url, timeout=2) as r:
                    if r.status == 200:
                        return
            except Exception:  # noqa: BLE001 - le serveur démarre
                time.sleep(0.5)
        raise AssertionError(f"la page {self.url} ne répond pas après {delai} s")

    def arreter(self):
        try:
            os.killpg(self.proc.pid, signal.SIGTERM)
            self.proc.wait(timeout=20)
        except Exception:  # noqa: BLE001
            try:
                os.killpg(self.proc.pid, signal.SIGKILL)
            except Exception:  # noqa: BLE001
                pass


def sonde(url: str, ids: list[int], capture=None) -> dict:
    cmd = ["node", str(PROBE), url, ",".join(map(str, ids))] + ([str(capture)] if capture else [])
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    assert p.returncode == 0 and p.stdout.strip(), f"sonde Playwright en échec (code {p.returncode}) :\n{p.stderr[-1500:]}"
    return json.loads(p.stdout)


@pytest.fixture(scope="module")
def vue(chaine, oracle):
    """Page de la zone fictive, deux fiches ouvertes : une cellule dans un polygone, une hors polygone."""
    dans = next(c for c in sorted(oracle.forest_cells()) if oracle.cell_values(c)["stand"] is not None)
    hors = next(c for c in sorted(oracle.forest_cells()) if oracle.cell_values(c)["stand"] is None)
    srv = Serveur(H.ZONE_NAME, None if H.ZONE_NAME == "zone_fictive" else H.write_config(H.ZONE, H.ZONE_NAME))
    try:
        srv.attendre()
        res = sonde(srv.url, [dans, hors], H.ROOT / "tests" / "m4" / "capture_vue.png")
    finally:
        srv.arreter()
    res["cells"] = (dans, hors)
    return res


def test_la_page_charge_sans_erreur(vue):
    assert "fatal" not in vue, vue.get("fatal")
    assert vue["state"]["error"] is None, vue["state"]["error"]
    assert vue["state"]["ready"] is True
    assert vue["errors"] == [], f"erreurs de la page : {vue['errors'][:3]}"


def test_la_vue_compte_14080_instances_dessinees(vue):
    assert vue["state"]["instanceCount"] == 14080, f"instanceCount = {vue['state']['instanceCount']}"


def test_la_vue_affiche_l_annee_de_la_tuile(vue):
    annee = int(H.find_tilesets(H.ZONE)[0].parent.name)
    assert vue["state"]["year"] == annee


def test_la_vue_ne_depend_pas_du_reseau(vue):
    # Les requêtes extérieures ont été abandonnées : la page est quand même prête (fond IGN facultatif).
    assert vue["state"]["ready"] is True
    assert vue["state"]["hasOpenCell"] is True


def test_la_capture_d_ecran_est_ecrite(vue):
    png = H.HERE / "capture_vue.png"
    assert png.is_file() and png.stat().st_size > 5000
    png.unlink()


def test_la_fiche_s_ouvre_et_donne_station_type_et_composition(vue, oracle, sheets):
    cells = H.sheet_cells(sheets)
    for cid in vue["cells"]:
        f = vue["sheets"][str(cid)]
        assert f["cellId"] == str(cid), f"data-cell-id = {f['cellId']!r}"
        txt = f["text"]
        v = oracle.cell_values(cid)
        assert v["station_type"] in txt, f"fiche {cid} : station {v['station_type']!r} absente"
        assert v["vegetation_type"] in txt, f"fiche {cid} : type {v['vegetation_type']!r} absent"
        for e in cells[cid]["years"][0]["composition"]:
            assert e["species"] in txt, f"fiche {cid} : essence {e['species']} absente"


def test_la_fiche_porte_la_mention_provisoire(vue):
    for cid in vue["cells"]:
        assert re.search(r"provisoire", vue["sheets"][str(cid)]["text"], re.I), f"fiche {cid} sans « provisoire »"


def test_la_fiche_dit_que_volume_et_carbone_ne_sont_pas_calcules(vue):
    for cid in vue["cells"]:
        t = H.sans_accent(vue["sheets"][str(cid)]["text"])
        assert "volume" in t and any(m in t for m in H.SIGNAL_VIDE), f"fiche {cid} : volume non signalé"
        assert ("carbone" in t or "carbon" in t) and any(m in t for m in H.SIGNAL_VIDE), f"fiche {cid} : carbone non signalé"
        assert not re.search(r"(volume|carbone)[^\n]*\b[1-9]\d*[.,]?\d*\s*(m3|m³|t/ha|t\.ha)", t), f"fiche {cid} : un chiffre de volume ou de carbone est affiché"


def test_la_fiche_donne_la_commande_viewer_massif_aux_bonnes_coordonnees(vue):
    for cid in vue["cells"]:
        txt = vue["sheets"][str(cid)]["text"]
        m = re.search(r"viewer-massif\s+--\s+--zone\s+(\S+)\s+--x\s+(\d+(?:[.,]\d+)?)\s+--y\s+(\d+(?:[.,]\d+)?)\s+--year\s+(\d{4})", txt)
        assert m, f"fiche {cid} : commande « viewer-massif -- --zone <dossier> --x <X> --y <Y> --year <A> » absente :\n{txt}"
        x, y = H.cell_centre(cid)
        assert m.group(1).rstrip("/") == f"data/{H.ZONE_NAME}", f"fiche {cid} : --zone {m.group(1)}, attendu data/{H.ZONE_NAME}"
        assert abs(float(m.group(2).replace(",", ".")) - x) <= 1.0 and abs(float(m.group(3).replace(",", ".")) - y) <= 1.0, \
            f"fiche {cid} : commande en ({m.group(2)}, {m.group(3)}), centre attendu ({x}, {y})"
        assert int(m.group(4)) == int(H.find_tilesets(H.ZONE)[0].parent.name)


def test_la_vue_compte_une_instance_de_moins_sur_la_zone_sans_un_arbre(zone_sans_arbre):
    # Test discriminant : le compteur n'est pas un 14 080 écrit en dur.
    assert zone_sans_arbre["run"].returncode == 0, zone_sans_arbre["run"].stderr[-1500:]
    srv = Serveur(zone_sans_arbre["name"], zone_sans_arbre["config"])
    try:
        srv.attendre()
        res = sonde(srv.url, [])
    finally:
        srv.arreter()
    assert "fatal" not in res, res.get("fatal")
    assert res["state"]["instanceCount"] == 14079, f"instanceCount = {res['state']['instanceCount']}"
