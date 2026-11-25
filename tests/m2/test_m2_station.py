"""Station aux placettes IFN et garde IFN (spec §6 : variables à l'ajustement ; CLAUDE.md : « Jamais de
croisement d'une placette IFN avec un raster fin » ; fiche 024).

Aucune colonne de station à la placette ne vient d'un raster fin : `trophic` vient de la flore,
`coarse_hydric_700m` et `coarse_bioclim_700m` de la moyenne des gradients dans un disque de 700 m. Les
valeurs attendues sont recalculées ici, sur le raster d'entrée, par une moyenne de disque écrite
indépendamment du module.
"""
import statistics

import pytest

import helpers_m2 as H

TOLERANCE = 0.15            # écart admis entre moyenne par centres de mailles et moyenne du module
MAILLES_POUR_COMPARER = 200  # en deçà, un bord de disque pèse trop : on borne seulement


@pytest.fixture(scope="module")
def plots(chaine):
    return H.read_parquet(H.ZONE / "ifn" / "plots.parquet")


COLONNES_FINES = ("hydric", "bioclim", "slope", "pente", "dtm", "mnt", "h0", "chm", "mnh", "lidar",
                  "station", "fertil", "altitude", "elev", "topo")


def test_aucune_colonne_de_station_fine_dans_les_placettes(plots):
    # Toute variable non préfixée `coarse_` est fine (garde de sylvostation reprise telle quelle).
    colonnes = set(plots[0])
    fines = [c for c in colonnes if any(m in c.lower() for m in COLONNES_FINES) and not c.startswith("coarse_")]
    assert not fines, f"colonnes de station non préfixées coarse_ : {fines}"
    for c in ("trophic", "coarse_hydric_700m", "coarse_bioclim_700m", "ser_code"):
        assert c in colonnes, f"colonne {c} absente de ifn/plots.parquet"


def test_placettes_floutees_donc_jamais_precises(plots):
    for p in plots:
        assert p["source"] == "ifn", p
        assert p["loc_precision_m"] > 25, f"placette {p['plot_id']} dite précise ({p['loc_precision_m']} m)"


def test_la_garde_refuse_station_gradients_aux_placettes_et_accepte_les_colonnes_larges(plots, tmp_path):
    # Spec §6 : « Un test vérifie que la garde IFN refuse station_gradients.tif aux placettes. »
    # Les points sont ceux de ifn/plots.parquet ; les variables permises, les colonnes coarse_ produites.
    import csv
    f = tmp_path / "points.csv"
    with open(f, "w", encoding="utf-8", newline="") as h:
        w = csv.writer(h)
        w.writerow(["x", "y", "source", "loc_precision_m"])
        for p in plots:
            w.writerow([p["x"], p["y"], p["source"], p["loc_precision_m"]])
    larges = sorted(c for c in plots[0] if c.startswith("coarse_"))
    assert larges, "aucune colonne coarse_ à tester"
    expr = (f'pts <- read.csv("{f}", stringsAsFactors = FALSE); '
            'essai <- function(v) tryCatch({assert_no_fine_extract_on_ifn(pts, v); "OK"}, '
            'error = function(e) paste0("ERR|", conditionMessage(e))); '
            f'cat("larges:", essai(c({",".join(chr(34) + c + chr(34) for c in larges)})), "\\n", sep=""); '
            'cat("fine:", essai("station_gradients"), "\\n", sep=""); '
            f'cat("melange:", essai(c({",".join(chr(34) + c + chr(34) for c in larges)}, "station_gradients")), "\\n", sep="")')
    p = H.rscript(expr)
    assert p.returncode == 0, p.stderr[-1500:]
    out = dict(ln.split(":", 1) for ln in p.stdout.splitlines() if ":" in ln)
    assert out["larges"].startswith("OK"), out
    assert out["fine"].startswith("ERR") and "Extraction interdite" in out["fine"], out
    assert out["melange"].startswith("ERR"), out


# ------------------------------------------------------------------ colonnes remplies (fiche 024)
def _ligne_station(zone_dir, p):
    px = H.station_disc_pixels(zone_dir / "inputs" / "station_gradients.tif", p["x"], p["y"])
    return px


def _comparer(zone_dir, plots):
    """Écarts de coarse_hydric_700m et coarse_bioclim_700m au calcul indépendant ; liste des placettes
    sans maille dans le disque (le module doit y laisser vide) ; des erreurs lisibles."""
    erreurs, vides = [], set()
    for p in plots:
        px = _ligne_station(zone_dir, p)
        for col, bande in (("coarse_hydric_700m", "hydric"), ("coarse_bioclim_700m", "bioclim")):
            v, valeurs = p[col], px[bande]
            if valeurs.size == 0:
                vides.add(p["plot_id"])
                if v is not None:
                    erreurs.append(f"{p['plot_id']} {col} = {v} alors qu'aucune maille n'est dans le disque")
            elif v is None:
                erreurs.append(f"{p['plot_id']} {col} vide alors que {valeurs.size} mailles sont dans le disque")
            elif valeurs.size >= MAILLES_POUR_COMPARER:
                attendu = float(valeurs.mean())
                if abs(v - attendu) > TOLERANCE:
                    erreurs.append(f"{p['plot_id']} {col} = {v:.3f}, moyenne du disque {attendu:.3f} "
                                   f"({valeurs.size} mailles)")
            elif not (valeurs.min() - 1e-6 <= v <= valeurs.max() + 1e-6):
                erreurs.append(f"{p['plot_id']} {col} = {v:.3f} hors de [{valeurs.min():.3f} ; {valeurs.max():.3f}]")
    return erreurs, vides


def test_coarse_hydric_et_bioclim_sont_la_moyenne_du_disque_de_700_m(plots):
    erreurs, _ = _comparer(H.ZONE, plots)
    assert not erreurs, "\n".join(erreurs[:8])


def test_colonnes_de_station_remplies_ou_leur_vide_est_signale(plots, chaine):
    # « Remplies » : pas de colonne vide, et chaque placette sans valeur est comptée au rapport de prepare
    # (signaler plutôt que deviner).
    for col in ("trophic", "coarse_hydric_700m", "coarse_bioclim_700m"):
        assert any(p[col] is not None for p in plots), f"{col} est vide pour toutes les placettes"
    rapport = H.html_blocks(H.ZONE / "rapport_prepare.html")
    for col, cles in (("coarse_hydric_700m", ("hydri", "coarse", "700 m")),
                      ("coarse_bioclim_700m", ("bioclim", "coarse", "700 m"))):
        vides_lignes = sum(1 for p in plots if p[col] is None)
        vides_placettes = len({p["plot_id"] for p in plots if p[col] is None})
        if not vides_lignes:
            continue
        blocs = [b for b in rapport if any(c in H.sans_accent(b) for c in cles) and "placette" in H.sans_accent(b)]
        assert H.ints_in_blocks(blocs) & {vides_lignes, vides_placettes}, \
            f"{col} : {vides_placettes} placettes ({vides_lignes} lignes) sans valeur, non comptées dans rapport_prepare.html"
    # trophic : flore de 1re visite seulement (spec §6) ; une placette de 1re visite qui a de la flore
    # et pas de valeur est comptée.
    avec_flore = {f["IDP"] for f in H.Ifn(H.ZONE).flora}
    vides = {p["plot_id"] for p in plots if p["visit"] == 1 and p["trophic"] is None and p["plot_id"] in avec_flore}
    if vides:
        blocs = [b for b in rapport if "trophi" in H.sans_accent(b)]
        assert H.ints_in_blocks(blocs) & {len(vides)}, \
            f"trophic : {len(vides)} placettes de 1re visite avec flore sans valeur, non comptées au rapport"


def test_ser_code_est_la_ser_sous_jacente_jamais_une_alluvion(plots):
    # Spec §3 et §7 : les alluvions L1 à L5 sont rattachées à la SER voisine. Sur le jeu fictif, la seule
    # SER est H10 (le couloir L3 lui est rattaché).
    codes = {p["ser_code"] for p in plots}
    assert codes <= {None, "H10"}, f"ser_code inattendu : {codes}"
    assert "H10" in codes, "ser_code n'est renseigné pour aucune placette"


def test_trophic_vient_de_la_flore_et_reste_dans_l_echelle_des_valeurs_indicatrices(plots):
    # Indices ordinaux de Tichý et al. 2023 : réaction et nutriments de 1 à 9 (docs/referentiels/ifn-dynamique.md §6).
    valeurs = [p["trophic"] for p in plots if p["trophic"] is not None]
    assert valeurs, "trophic est vide partout"
    assert 1 <= min(valeurs) and max(valeurs) <= 9, (min(valeurs), max(valeurs))
    assert statistics.pstdev(valeurs) > 0, "trophic est constant : la flore n'est pas lue"


def test_la_flore_est_celle_de_la_1re_visite(plots, ifn):
    # Q7 : flore relevée en 1re visite seulement ; une placette n'a de flore qu'à sa campagne de 1re visite.
    premiere = {p["IDP"]: p["CAMPAGNE"] for p in ifn.plots if p["VISITE"] == "1"}
    assert all(premiere[f["IDP"]] == f["CAMPAGNE"] for f in ifn.flora), "jeu fictif : flore à une 2e visite"
    # Les placettes de 2e visite ne portent pas de valeur trophique différente de celle de leur 1re visite.
    par = {}
    for p in plots:
        par.setdefault(p["plot_id"], {})[p["visit"]] = p["trophic"]
    for idp, v in par.items():
        if 2 in v and v[2] is not None:
            assert v[2] == v[1], f"{idp} : trophic de 2e visite différent de celui de la 1re"


# ------------------------------------------------------------------ garde : raster connu, pointe sous une placette
def test_variante_station_la_pointe_sous_la_placette_est_diluee_par_le_disque(zone_station, plots):
    # Rampes connues ; une pointe de 100 sur 3 x 3 mailles sous la placette 9000001 déplacée au centre du
    # raster. Une extraction fine (maille de la placette) rendrait 100 ; la moyenne du disque de 700 m, 5.
    assert zone_station["make"].returncode == 0, zone_station["make"].stderr[-1500:]
    var = H.read_parquet(zone_station["dir"] / "ifn" / "plots.parquet")
    erreurs, _ = _comparer(zone_station["dir"], var)
    assert not erreurs, "\n".join(erreurs[:8])
    centre = [p for p in var if p["plot_id"] == "9000001"]
    assert centre and all(p["coarse_hydric_700m"] is not None and p["coarse_hydric_700m"] < 20 for p in centre), \
        [p["coarse_hydric_700m"] for p in centre]  # pas la pointe de 100
    coin = [p for p in var if p["plot_id"] == "9000002"]
    px = H.station_disc_pixels(zone_station["dir"] / "inputs" / "station_gradients.tif", 700900.0, 6500900.0)
    assert coin and all(abs(p["coarse_bioclim_700m"] - float(px["bioclim"].mean())) <= TOLERANCE for p in coin), \
        "disque tronqué par le bord du raster : moyenne attendue sur les seules mailles du disque"


def test_variante_station_trophic_ne_depend_pas_du_raster(zone_station, plots):
    # trophic vient de la flore : changer tous les rasters de station ne le change pas.
    assert zone_station["make"].returncode == 0
    var = H.read_parquet(zone_station["dir"] / "ifn" / "plots.parquet")
    cle = lambda p: (p["plot_id"], p["campaign"])  # noqa: E731
    base = {cle(p): p["trophic"] for p in plots}
    assert {cle(p): p["trophic"] for p in var} == base, "trophic a changé avec le raster de station"
