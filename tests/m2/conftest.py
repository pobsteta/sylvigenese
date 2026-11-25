"""Pytest M2a (mission 026) : lance `make prepare biomes dynamics` sur le jeu fictif, une fois par
session, sans réseau, puis les tests lisent les sorties. Des zones variantes (copies sous data/m2_*,
supprimées ensuite) servent de tests discriminants : chacune casse ou change UNE règle de la spec §6.

Aucune fixture ne saute un test (le script de CI refuse tout test sauté) : si make échoue, les tests
d'exécution échouent, et ceux qui lisent les sorties échouent sur « sortie absente ».
"""
import shutil
import sys
from pathlib import Path

import pyarrow.parquet as pq
import pytest

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import helpers_m2 as H  # noqa: E402

SPIKE_ID_CENTRE, SPIKE_ID_COIN = "9000001", "9000002"


# ------------------------------------------------------------------ chaîne nominale
@pytest.fixture(scope="session")
def chaine():
    """make prepare biomes dynamics, puis make dynamics une seconde fois (rejeu des params)."""
    H.clean_outputs(H.ZONE)
    res = {"make": H.run_make("prepare", "biomes", "dynamics")}
    res["params_1"] = _lire_params(H.ZONE)
    res["rapport_1"] = _lire_rapport(H.ZONE)
    res["make_2"] = H.run_make("dynamics")
    res["params_2"] = _lire_params(H.ZONE)
    return res


def _lire_params(zone_dir):
    try:
        return H.read_params(zone_dir)
    except Exception:  # noqa: BLE001 - l'absence est déjà signalée par les tests de sortie
        return None


def _lire_rapport(zone_dir):
    p = zone_dir / H.RAPPORT
    return p.read_bytes() if p.is_file() else None


@pytest.fixture(scope="session")
def ifn():
    return H.ifn_de(H.ZONE)


@pytest.fixture(scope="session")
def rapport(chaine):
    return H.html_blocks(H.ZONE / H.RAPPORT)


@pytest.fixture(scope="session")
def params(chaine):
    return H.read_params(H.ZONE)


# ------------------------------------------------------------------ zones variantes
def _variante(name, mutate, etapes=("prepare", "dynamics")):
    """Copie du jeu fictif, mutation des entrées, puis make des étapes en un seul appel."""
    zone_dir, cfg = H.make_zone_copy(name, mutate)
    res = {"dir": zone_dir, "config": cfg, "name": name}
    res["make"] = H.run_make(*etapes, zone=name, config=cfg)
    res["rapport"] = zone_dir / H.RAPPORT
    return res


def _indexer(plots, trees):
    """(IDP, A, visite) -> ligne d'ARBRE, et (IDP, visite) -> ligne de PLACETTE."""
    visite = {(p["CAMPAGNE"], p["IDP"]): int(p["VISITE"]) for p in plots}
    arbres = {(t["IDP"], t["A"], visite[(t["CAMPAGNE"], t["IDP"])]): t for t in trees}
    placettes = {(p["IDP"], int(p["VISITE"])): p for p in plots}
    return visite, arbres, placettes


def _plots_libres(zone_dir):
    """Placettes revues que ni les incidents ni les travaux n'écartent, par IDP ; celles qui ont une
    valeur de station d'abord (jeu fictif sans placette hors du raster : toutes). Les variantes y
    prennent leurs arbres, pour que leurs comptes bougent quelle que soit la lecture de la règle."""
    ifn = H.ifn_de(zone_dir)
    ecartees = ifn.travaux_ou_incident()
    libres = [i for i in ifn.revisited_plots() if i not in ecartees]
    return sorted(libres, key=lambda i: (i in ifn.sans_station, int(i))), ifn


def _arbres_vivants_choisis(zone_dir, essence, part):
    """Arbres de l'essence, à risque, vivants à la 2e visite, sur placettes libres : les `part` premiers
    (placettes à station d'abord, puis par IDP et A). Renvoie [(IDP, A)]."""
    libres, ifn = _plots_libres(zone_dir)
    rang = {i: n for n, i in enumerate(libres)}
    cand = sorted(((t1["IDP"], t1["A"]) for t1, t2 in ifn.at_risk(set(ifn.plot_rows) - set(libres))
                   if t1["ESPAR"] == essence and t2["VEGET5"] == "0"),
                  key=lambda k: (rang[k[0]], int(k[1])))
    return cand[: int(len(cand) * part)]


RETRAITS = ["6", "7", "N", "T"]


def _mut_retraits(zone_dir, vers_mort=False):
    choisis = _arbres_vivants_choisis(zone_dir, H.ESSENCE_CIBLE, 0.4)
    assert len(choisis) >= 20, f"jeu fictif trop pauvre en arbres {H.ESSENCE_CIBLE} vivants ({len(choisis)})"

    def fn(ph, plots, ah, trees, fh, flora):
        _v, arbres, _p = _indexer(plots, trees)
        for i, (idp, a) in enumerate(choisis):
            t = arbres[(idp, a, 2)]
            if vers_mort:
                t["VEGET5"], t["IR5"] = "M", ""
            else:
                t["VEGET5"] = RETRAITS[i % 4]
                for c in H.PLEIN_FILE:
                    t[c] = ""

    H.edit_ifn(zone_dir, fn)


@pytest.fixture(scope="session")
def zone_retraits(chaine):
    """Arbres de l'essence cible coupés (6, 7), non retrouvés (N) et perdus (T) : retirés et comptés."""
    try:
        yield _variante("m2_retraits", _mut_retraits)
    finally:
        H.remove_zone_copy("m2_retraits")


@pytest.fixture(scope="session")
def zone_morts(chaine):
    """Les mêmes arbres, mais morts sur pied (M) : ils DOIVENT compter comme morts."""
    try:
        yield _variante("m2_morts", lambda d: _mut_retraits(d, vers_mort=True))
    finally:
        H.remove_zone_copy("m2_morts")


def _mut_incidents(zone_dir):
    libres, _ifn = _plots_libres(zone_dir)
    choisies = set(libres[:5])

    def fn(ph, plots, ah, trees, fh, flora):
        for p in plots:
            if p["IDP"] in choisies and p["VISITE"] == "1":
                p["NINCID"], p["INCID"] = "4", "3"  # tempête, plus de 50 % du couvert

    H.edit_ifn(zone_dir, fn)


@pytest.fixture(scope="session")
def zone_incidents(chaine):
    try:
        yield _variante("m2_incidents", _mut_incidents)
    finally:
        H.remove_zone_copy("m2_incidents")


C13_EXCEPTIONNEL_1, C13_EXCEPTIONNEL_2 = "2.900", "2.920"   # d130 92,3 puis 92,9 cm (le jeu : 81,7 au plus)


def _mut_recrues(zone_dir):
    libres, ifn = _plots_libres(zone_dir)
    modele = next(t for t in sorted(ifn.recruits(set()), key=lambda t: (int(t["IDP"]), int(t["A"]))))
    exceptionnel = next(k for k in _arbres_vivants_choisis(zone_dir, H.ESSENCE_DOMAINE, 1.0))

    def fn(ph, plots, ah, trees, fh, flora):
        _v, arbres, placettes = _indexer(plots, trees)
        suivant = {}
        for (idp, a, _vis) in arbres:
            suivant[idp] = max(suivant.get(idp, 0), int(a))
        for i in range(H.NOUVELLES_RECRUES + H.SOUS_LE_SEUIL):
            idp = libres[i % 3]
            suivant[idp] += 1
            r = dict(modele)
            r.update(IDP=idp, A=str(suivant[idp]), CAMPAGNE=placettes[(idp, 2)]["CAMPAGNE"])
            r["C13"] = "0.236" if i < H.NOUVELLES_RECRUES else "0.234"
            r["IR5"] = ""
            if i < H.RECRUES_SANS_POIDS:
                r["W"] = ""
            trees.append(r)
        idp, a = exceptionnel
        arbres[(idp, a, 1)]["C13"] = C13_EXCEPTIONNEL_1
        arbres[(idp, a, 2)]["C13"] = C13_EXCEPTIONNEL_2

    H.edit_ifn(zone_dir, fn)


@pytest.fixture(scope="session")
def zone_recrues(chaine):
    try:
        yield _variante("m2_recrues", _mut_recrues)
    finally:
        H.remove_zone_copy("m2_recrues")


def _mut_sans_datepoint(zone_dir):
    def fn(ph, plots, ah, trees, fh, flora):
        for p in plots:
            p["DATEPOINT"] = ""

    H.edit_ifn(zone_dir, fn)


@pytest.fixture(scope="session")
def zone_sans_datepoint(chaine):
    try:
        yield _variante("m2_sans_datepoint", _mut_sans_datepoint)
    finally:
        H.remove_zone_copy("m2_sans_datepoint")


DATE_ANTERIEURE = "01/01/2010"


def _mut_date_incoherente(zone_dir):
    libres, _ifn = _plots_libres(zone_dir)

    def fn(ph, plots, ah, trees, fh, flora):
        for p in plots:
            if p["IDP"] == libres[0] and p["VISITE"] == "2":
                p["DATEPOINT"] = DATE_ANTERIEURE  # 2e visite antérieure à la 1re

    H.edit_ifn(zone_dir, fn)
    return libres[0]


@pytest.fixture(scope="session")
def zone_date_incoherente(chaine):
    """prepare puis dynamics, codes lus séparément : la règle admise est « erreur explicite ou ligne de
    rapport », jamais un intervalle négatif utilisé en silence."""
    name = "m2_date_incoherente"
    try:
        zone_dir, cfg = H.make_zone_copy(name, _mut_date_incoherente)
        res = {"dir": zone_dir, "config": cfg, "idp": _plots_libres(zone_dir)[0][0]}
        res["prepare"] = H.run_module_status("prepare", cfg)
        res["dynamics"] = H.run_module_status("dynamics", cfg) if res["prepare"].returncode == 0 else None
        yield res
    finally:
        H.remove_zone_copy(name)


def _mut_sans_revisite(zone_dir):
    def fn(ph, plots, ah, trees, fh, flora):
        v1 = {(p["CAMPAGNE"], p["IDP"]) for p in plots if p["VISITE"] == "1"}
        plots[:] = [p for p in plots if p["VISITE"] == "1"]
        trees[:] = [t for t in trees if (t["CAMPAGNE"], t["IDP"]) in v1]

    H.edit_ifn(zone_dir, fn)


@pytest.fixture(scope="session")
def zone_sans_revisite(chaine):
    """Aucune 2e visite : ni mortalité ni recrutement ni accroissement entre visites à ajuster."""
    name = "m2_sans_revisite"
    try:
        zone_dir, cfg = H.make_zone_copy(name, _mut_sans_revisite)
        res = {"dir": zone_dir, "config": cfg}
        res["prepare"] = H.run_module_status("prepare", cfg)
        res["dynamics"] = H.run_module_status("dynamics", cfg) if res["prepare"].returncode == 0 else None
        yield res
    finally:
        H.remove_zone_copy(name)


# --- raster de station : rampes connues, pointe de 3 x 3 mailles au centre
RAMPE = {1: lambda x, y: (x - 700000.0) / 200.0, 2: lambda x, y: (x - 700000.0) / 100.0,
         3: lambda x, y: (y - 6500000.0) / 100.0}
POINTE = 100.0
CENTRE = (700500.0, 6500500.0)
COIN = (700900.0, 6500900.0)


def _mut_station(zone_dir):
    import numpy as np
    import rasterio

    with rasterio.open(zone_dir / "inputs" / "station_gradients.tif", "r+") as r:
        t = r.transform
        cols, rows = np.meshgrid(np.arange(r.width), np.arange(r.height))
        xs, ys = t.c + (cols + 0.5) * t.a, t.f + (rows + 0.5) * t.e
        for b, f in RAMPE.items():
            arr = f(xs, ys).astype("float32")
            if b == 2:  # pointe sur la maille du centre et ses huit voisines
                c0, r0 = int((CENTRE[0] - t.c) / t.a), int((CENTRE[1] - t.f) / t.e)
                arr[r0 - 1:r0 + 2, c0 - 1:c0 + 2] = POINTE
            r.write(arr, b)

    def fn(ph, plots, ah, trees, fh, flora):
        for p in plots:
            if p["IDP"] == SPIKE_ID_CENTRE:
                p["XL"], p["YL"] = f"{CENTRE[0]:.1f}", f"{CENTRE[1]:.1f}"
            elif p["IDP"] == SPIKE_ID_COIN:
                p["XL"], p["YL"] = f"{COIN[0]:.1f}", f"{COIN[1]:.1f}"

    H.edit_ifn(zone_dir, fn)


@pytest.fixture(scope="session")
def zone_station(chaine):
    """Gradients de station connus (rampes) et une pointe sous une placette déplacée au centre : une
    extraction fine rendrait la pointe, la moyenne du disque de 700 m la dilue."""
    try:
        yield _variante("m2_station", _mut_station, ("prepare",))
    finally:
        H.remove_zone_copy("m2_station")


# --- zone de référence, rejouée à neuf (et source des clones pour les refus de dynamics)
@pytest.fixture(scope="session")
def zone_rejeu(chaine):
    try:
        yield _variante("m2_rejeu", None)
    finally:
        H.remove_zone_copy("m2_rejeu")


# ------------------------------------------------------------------ refus de prepare (entrée IFN)
def _modifier_arbre(zone_dir, fn_ligne):
    def fn(ph, plots, ah, trees, fh, flora):
        fn_ligne(trees)

    H.edit_ifn(zone_dir, fn)


def _veget5_hors_referentiel(d):
    def f(trees):
        t = next(t for t in trees if t["VEGET5"] == "0")
        t["VEGET5"] = "Q"

    _modifier_arbre(d, f)


def _arbre_en_double(d):
    _modifier_arbre(d, lambda trees: trees.append(dict(trees[0])))


def _c13_en_millimetres(d):
    def f(trees):
        t = next(t for t in trees if t["C13"].strip())
        t["C13"] = "387"  # l'unité de la saisie de terrain, pas celle de l'export : 12 318 cm de d130

    _modifier_arbre(d, f)


def _espar_vide(d):
    def f(trees):
        trees[0]["ESPAR"] = ""

    _modifier_arbre(d, f)


def _datepoint_impossible(d):
    def fn(ph, plots, ah, trees, fh, flora):
        plots[0]["DATEPOINT"] = "31/02/2015"

    H.edit_ifn(d, fn)


def _visite_hors_enum(d):
    def fn(ph, plots, ah, trees, fh, flora):
        plots[0]["VISITE"] = "3"

    H.edit_ifn(d, fn)


def _a_non_entier(d):
    _modifier_arbre(d, lambda trees: trees[0].__setitem__("A", "premier"))


def _ir5_negatif(d):
    def f(trees):
        t = next(t for t in trees if t["IR5"].strip())
        t["IR5"] = "-0.01"

    _modifier_arbre(d, f)


REFUS_PREPARE = {
    "veget5_hors_referentiel": (_veget5_hors_referentiel, ("VEGET5", "ARBRE")),
    "arbre_en_double": (_arbre_en_double, ("ARBRE", "double", "doublon")),
    "c13_en_millimetres": (_c13_en_millimetres, ("C13",)),
    "espar_vide": (_espar_vide, ("ESPAR",)),
    "datepoint_impossible": (_datepoint_impossible, ("DATEPOINT",)),
    "visite_hors_enum": (_visite_hors_enum, ("VISITE", "PLACETTE")),
    "numero_arbre_non_entier": (_a_non_entier, ("ARBRE",)),
    "ir5_negatif": (_ir5_negatif, ("IR5",)),
}


@pytest.fixture(scope="module", params=list(REFUS_PREPARE))
def refus_prepare(request):
    nom = "m2_refus_" + request.param
    mutate, mot = REFUS_PREPARE[request.param]
    try:
        d, cfg = H.make_zone_copy(nom, mutate)
        p = H.run_module_status("prepare", cfg)
        yield request.param, d, p, mot
    finally:
        H.remove_zone_copy(nom)


# ------------------------------------------------------------------ refus de dynamics (ifn/ préparé)
def _sans_arbres(d):
    (d / "ifn" / "trees.parquet").unlink()


def _sans_placettes(d):
    (d / "ifn" / "plots.parquet").unlink()


def _essence_hors_referentiel(d):
    t = pq.read_table(d / "ifn" / "trees.parquet")
    col = t.column("species").to_pylist()
    col[0] = "ZZZ99"
    i = t.schema.get_field_index("species")
    pq.write_table(t.set_column(i, t.schema.field(i), [col]), d / "ifn" / "trees.parquet")


REFUS_DYNAMICS = {
    "sans_arbres": (_sans_arbres, ("trees",)),
    "sans_placettes": (_sans_placettes, ("plots",)),
    "essence_hors_referentiel": (_essence_hors_referentiel, ("ZZZ99", "species", "essence")),
}


@pytest.fixture(scope="module", params=list(REFUS_DYNAMICS))
def refus_dynamics(request, zone_rejeu):
    nom = "m2_refus_dyn_" + request.param
    mutate, mot = REFUS_DYNAMICS[request.param]
    try:
        d, cfg = H.clone_zone(zone_rejeu["name"], nom, mutate)
        p = H.run_module_status("dynamics", cfg)
        yield request.param, d, p, mot
    finally:
        H.remove_zone_copy(nom)
