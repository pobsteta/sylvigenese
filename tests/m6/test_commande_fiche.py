"""La fiche web donne la commande COMPLÈTE à copier (décision Q7 de Pascal, 26/11/2026) : zone, x, y, année.

    viewer-massif -- --zone <dossier> --x <X> --y <Y> --year <A>

Mêmes sondes que tests/m4/test_m4_vue.py (Playwright, navigateur coupé du réseau) sur la zone m6_a construite avec les
exemplaires de la fixture. `--zone` dit OÙ sont les données : le dossier existe et porte massif/index.json (sinon la
commande copiée ne lancerait rien). Le test croisé « la commande est celle que la vue Godot accepte » est côté GUT
(viewer-massif/tests/test_arguments.gd, mêmes arguments) ; mission 073 relie les deux en CI.
"""
import re
from pathlib import Path

import pytest

import helpers_m4 as H
import helpers_m6 as M
import test_m4_vue as V


@pytest.fixture(scope="module")
def fiche(zone_a, oracle):
    zdir = M.exige(zone_a)
    dans = next(c for c in sorted(oracle.forest_cells()) if oracle.cell_values(c)["stand"] is not None)
    srv = V.Serveur(zone_a["name"], zone_a["config"])
    try:
        srv.attendre()
        res = V.sonde(srv.url, [dans])
    finally:
        srv.arreter()
    res["cell"] = dans
    res["dir"] = zdir
    return res


COMMANDE = re.compile(r"viewer-massif\s+--\s+--zone\s+(\S+)\s+--x\s+(\d+(?:[.,]\d+)?)\s+--y\s+(\d+(?:[.,]\d+)?)\s+--year\s+(\d{4})")


def test_la_fiche_donne_zone_x_y_annee_dans_cet_ordre(fiche):
    txt = fiche["sheets"][str(fiche["cell"])]["text"]
    m = COMMANDE.search(txt)
    assert m, f"commande « viewer-massif -- --zone <dossier> --x <X> --y <Y> --year <A> » absente de la fiche :\n{txt}"
    x, y = H.cell_centre(fiche["cell"])
    assert abs(float(m.group(2).replace(",", ".")) - x) <= 1.0 and abs(float(m.group(3).replace(",", ".")) - y) <= 1.0
    assert int(m.group(4)) == 2022


def test_la_zone_de_la_commande_existe_et_porte_massif(fiche):
    txt = fiche["sheets"][str(fiche["cell"])]["text"]
    m = COMMANDE.search(txt)
    assert m, "commande absente"
    zone = Path(m.group(1))
    chemin = zone if zone.is_absolute() else H.ROOT / zone
    assert chemin.resolve() == fiche["dir"].resolve(), f"--zone {zone} ne désigne pas {fiche['dir']}"
    assert (chemin / "massif" / "index.json").is_file()
