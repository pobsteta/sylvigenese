"""Un fichier conforme et un fichier fautif par contrat du catalogue (spec §11, M0).

Chaque fichier fautif ne diffère du conforme que par un défaut, et le message doit le
nommer. `test_every_contract_has_a_case` garantit qu'aucun contrat n'est oublié.
"""
import re

import pyarrow as pa
import pytest

import helpers as h
from validator import catalog, cli

GOOD, BAD = "good", "bad"


def run(capsys, argv):
    code = cli.main(argv)
    captured = capsys.readouterr()
    return code, captured.out + captured.err


# --------------------------------------------------------------------- fabriques

def stands(tmp, fault):
    rows = h.stands_rows()
    if fault:
        rows[0]["species_espar"] = "9"
    layers = {"stands": ("POLYGON", h.STANDS_COLUMNS, rows, [(h.PARIS_X, h.PARIS_Y)] * 2)}
    return h.gpkg(tmp / "nemeton_stands.gpkg", layers)


def inventaire(tmp, fault):
    plots = ("POINT", [("plot_id", "TEXT"), ("rayon_m", "REAL"), ("seuil_diam_cm", "REAL"),
                       ("autre", "TEXT")],
             [{"plot_id": "PL1", "rayon_m": 15.0, "seuil_diam_cm": 7.5, "autre": "x"}],
             [(h.PARIS_X, h.PARIS_Y)])
    tree = {"plot_id": "PL1", "tree_id": "A1", "essence_arbre": "hetre", "dbh_cm": 30.0,
            "dbh_source": "ruban" if fault else "mesure", "h_m": 22.0, "h_source": "mnh",
            "statut": "vivant"}
    cols = [(k, "REAL" if k in ("dbh_cm", "h_m") else "TEXT") for k in tree]
    trees = ("POINT", cols, [tree], [(h.PARIS_X + 2, h.PARIS_Y + 2)])
    return h.gpkg(tmp / "inventaire_video.gpkg", {"placettes": plots, "arbres": trees})


def lidar_tiles(tmp, fault):
    row = {"flight_date": "hier" if fault else "2024-03-07", "nom": "dalle_1"}
    layer = ("POLYGON", [("flight_date", "DATE"), ("nom", "TEXT")], [row],
             [(h.PARIS_X, h.PARIS_Y)])
    return h.gpkg(tmp / "lidar_tiles.gpkg", {"lidar_tiles": layer})


def forest_mask(tmp, fault):
    layer = ("POLYGON", [], [{}], [(h.PARIS_X, h.PARIS_Y)])
    return h.gpkg(tmp / "forest_mask.gpkg", {"forest_mask": layer},
                  srs_id=4326 if fault else 2154)


def ser(tmp, fault):
    rows = [{"ser_code": "B10", "alluvium_code": None},
            {"ser_code": "B10", "alluvium_code": "L9" if fault else "L3"}]
    layer = ("POLYGON", [("ser_code", "TEXT"), ("alluvium_code", "TEXT")], rows,
             [(h.PARIS_X, h.PARIS_Y)] * 2)
    return h.gpkg(tmp / "ser.gpkg", {"ser": layer})


def fertilite(tmp, fault):
    header = ["species", "type", "n_plots", "fertilite_moy", "fertilite_med",
              "fertilite_sd", "age_ref"]
    rows = [["09", "fraiche_acide", -1 if fault else 12, 24.5, 24.0, 2.1, 50]]
    return h.csv(tmp / "fertilite.csv", header, rows, sep=";")


def ifn_placette(tmp, fault):
    x, y = (h.PARIS_Y, h.PARIS_X) if fault else (h.PARIS_X, h.PARIS_Y)
    return h.csv(tmp / "PLACETTE.csv", ["IDP", "CAMPAGNE", "XL", "YL"],
                 [["1001", 2020, x, y]], sep=";")


def ifn_arbre(tmp, fault):
    return h.csv(tmp / "ARBRE.csv", ["IDP", "A", "ESPAR", "C13", "HTOT", "V", "W"],
                 [["1001", 1, "9" if fault else "09", 950, 22.5, 0.8, 14.1]], sep=";")


def ifn_flore(tmp, fault):
    return h.csv(tmp / "FLORE.csv", ["IDP", "CD_REF", "ABOND"],
                 [["1001", "abc" if fault else 97947, 2]], sep=";")


def categories(name):
    def build(tmp, fault):
        rows = [[1, "fraiche_acide"], [2, "seche_calcaire"]]
        if fault:
            rows[1][1] = "fraiche_acide"
        return h.csv(tmp / name, ["value", "name"], rows)
    return build


def raster(name, fault_kwargs, **good):
    def build(tmp, fault):
        kwargs = dict(good)
        if fault:
            kwargs.update(fault_kwargs)
        return h.tif(tmp / name, **kwargs)
    return build


def aligned(name, **good):
    """Raster au profil grille, avec --grid ; fautif : décalé d'une demi-maille."""
    def build(tmp, fault):
        grid = h.tif(tmp / "grid.tif", dtype="uint16")
        origin = (h.ORIGIN[0] + 12.5, h.ORIGIN[1]) if fault else h.ORIGIN
        return h.tif(tmp / name, origin=origin, **good), ["--grid", str(grid)]
    return build


def table(name, columns, mutate, types=None):
    def build(tmp, fault):
        data = columns()
        if fault:
            mutate(data)
        return h.parquet(tmp / name, data, types)
    return build


def trees_init_dir(tmp, fault):
    data = h.trees_init()
    if fault:
        data["species_source"][0] = "estime"
    h.parquet(tmp / "trees_init" / "part-0.parquet", data)
    return tmp / "trees_init"


def ifn_plots():
    return {"plot_id": ["1001"], "campaign": [2020], "x": [h.PARIS_X], "y": [h.PARIS_Y],
            "loc_precision_m": [700.0], "source": ["ifn"], "ser_code": ["B10"],
            "trophic": [0.3], "coarse_hydric_700m": [-0.2], "coarse_bioclim_700m": [0.1]}


def ifn_trees():
    return {"plot_id": ["1001", "1001"], "campaign": [2020, 2020], "tree_id": ["1", "2"],
            "species": ["09", "02"], "d130": [30.2, 18.0], "h": [22.5, None],
            "weight_ha": [14.1, 39.3]}


def ifn_flora():
    return {"plot_id": ["1001"], "campaign": [2020], "cd_ref": [97947],
            "taxref_version": ["13"], "abundance": [2.0]}


def prepared_stands():
    return {"stand_id": ["P1"], "species": ["09"], "d130": [32.5], "h": [24.0],
            "density_ha": [310.0], "age": [80], "source": ["inventaire"],
            "stand_id_source": ["A1"]}


def partitioned(kind, columns, mutate=None):
    """Dossier Hive écrit par pyarrow.dataset ; sans `mutate`, le défaut est une colonne
    year répétée dans le fichier."""
    def build(tmp, fault):
        data = columns()
        root = tmp / kind
        if fault and mutate is None:
            h.parquet(root / "year=2030" / "part-0.parquet", data)
            return root
        if fault:
            mutate(data)
        return h.hive(root, data)
    return build


def document(name, content, mutate, writer):
    def build(tmp, fault):
        data = content()
        if fault:
            mutate(data)
        return writer(tmp / name, data)
    return build


def duplicate_key_config(tmp, fault):
    path = h.write_yaml(tmp / "config.yml", h.config())
    if fault:
        path.write_text(path.read_text(encoding="utf-8") + "management: none\n",
                        encoding="utf-8")
    return path


def tree_model(tmp, fault):
    return h.glb(tmp / "09_mature.glb", version=1 if fault else 2)


def species(tmp, fault):
    header = ["espar", "latin", "taxref_cd_ref", "taxref_version", "nemeton_code",
              "tarif_nemeton_code", "groupe", "source", "ecart"]
    rows = [["9" if fault else "09", "Fagus sylvatica", 97947, 18, "FASY", "Fagus_sylvatica",
             "feuillu", "N:10", ""]]
    return h.csv(tmp / "species.csv", header, rows)


def setitem(key, value):
    return lambda d: d.__setitem__(key, value)


def set_first(key, value):
    return lambda d: d[key].__setitem__(0, value)


# contrat -> (fabrique, motif du message attendu sur le fichier fautif)
CASES = {
    "inputs.nemeton_stands": (stands, r"species_espar"),
    "inputs.inventaire_video": (inventaire, r"dbh_source"),
    "inputs.chm": (raster("chm.tif", {"pixel": 1.0}, pixel=0.5, tiled=False), r"maille"),
    "inputs.dtm": (raster("dtm.tif", {"crs": "EPSG:2056"}, tiled=False), r"EPSG"),
    "inputs.lidar_tiles": (lidar_tiles, r"flight_date"),
    "inputs.forest_mask": (forest_mask, r"EPSG:2154"),
    "inputs.ser": (ser, r"alluvium_code"),
    "inputs.station_gradients": (raster("sg.tif", {"bands": 1}, bands=3), r"bande"),
    "inputs.station_type": (raster("st.tif", {"nodata": None}, dtype="uint16"), r"nodata"),
    "inputs.fertilite": (fertilite, r"n_plots"),
    "inputs.h_pot": (raster("h_pot.tif", {"bigtiff": True}), r"BigTIFF"),
    "inputs.ifn_placette": (ifn_placette, r"emprise"),
    "inputs.ifn_arbre": (ifn_arbre, r"ESPAR"),
    "inputs.ifn_flore": (ifn_flore, r"CD_REF"),
    "prepare.grid": (raster("grid.tif", {"pixel": 20.0}, dtype="uint16"), r"maille"),
    "prepare.dtm": (aligned("dtm.tif"), r"aligné"),
    "prepare.forest_mask": (raster("fm.tif", {"dtype": "float32"}, dtype="uint16"),
                            r"Float32"),
    "prepare.ser": (raster("ser.tif", {"interleave": "pixel"}, dtype="uint16"),
                    r"PLANARCONFIG"),
    "prepare.ser_categories": (categories("ser.csv"), r"name"),
    "prepare.h0": (raster("h0.tif", {"block": 512}), r"tuiles"),
    "prepare.chm_date": (raster("chm_date.tif", {"dtype": "float32"}, dtype="uint16"),
                         r"type de valeur"),
    "prepare.station_gradients": (raster("sg.tif", {"bands": 2}, bands=3), r"bande"),
    "prepare.station_type": (raster("st.tif", {"compress": "lzw"}, dtype="uint16"), r"LZW"),
    "prepare.station_type_categories": (categories("station_type.csv"), r"name"),
    "prepare.site_potential": (raster("sp.tif", {"crs": "EPSG:3857"}, bands=2), r"EPSG"),
    "prepare.site_potential_bands": (categories("site_potential.csv"), r"name"),
    "prepare.trees_init": (trees_init_dir, r"species_source"),
    "prepare.ifn_plots": (table("plots.parquet", ifn_plots, set_first("loc_precision_m", 0.0)),
                          r"loc_precision_m"),
    "prepare.ifn_trees": (table("trees.parquet", ifn_trees, set_first("tree_id", "2")),
                          r"doublon"),
    "prepare.ifn_flora": (table("flora.parquet", ifn_flora, set_first("cd_ref", 0)),
                          r"cd_ref"),
    "prepare.stands": (table("stands.parquet", prepared_stands, setitem("species", [9])),
                       r"species"),
    "import_tarif.tarif": (table("t.parquet", h.parameters,
                                 lambda d: d.update(species=[None, None],
                                                    species_group=[None, None]),
                                 types={"species": pa.string(), "species_group": pa.string()}),
                           r"species, species_group"),
    "import_tarif.allometry": (table("a.parquet", h.parameters, setitem("provisoire", [1, 1])),
                               r"provisoire"),
    "dynamics.growth": (table("g.parquet", h.parameters, set_first("source", "")), r"source"),
    "dynamics.mortality": (table("m.parquet", h.parameters, lambda d: d.pop("term")),
                           r"term"),
    "dynamics.recruitment": (table("r.parquet", h.parameters, set_first("species", "9")),
                             r"species"),
    "dynamics.height_curve": (table("hc.parquet", h.parameters,
                                    set_first("value", float("inf"))), r"value"),
    "biomes.biome": (document("hetraie.yml", h.biome,
                              lambda d: d["strates"]["arboree"]["composition"].update(sapin=0.5),
                              h.write_yaml), r"sapin"),
    "biomes.vegetation_map": (aligned("vegetation_map.tif", dtype="uint16"), r"aligné"),
    "biomes.vegetation_categories": (categories("vegetation_map.csv"), r"name"),
    "config": (duplicate_key_config, r"double"),
    "simulate.trees": (partitioned("trees", h.sim_trees), r"colonne year présente"),
    "simulate.cells": (partitioned("cells", h.sim_cells, set_first("species", "02")),
                       r"doublon"),
    "simulate.run": (document("run.json", h.run_json, setitem("provisional_share", 1.5),
                              h.write_json), r"provisional_share"),
    "post.summary": (table("summary.parquet", h.summary, set_first("volume_m3_ha", -1.0)),
                     r"volume_m3_ha"),
    "assets.tree_model": (tree_model, r"version 2"),
    "assets.tileset": (document("tileset.json", h.tileset,
                                lambda d: d["asset"].update(version="1.0"), h.write_json),
                       r"asset.version"),
    "assets.cell_sheet": (document("t_0_0.json", h.cell_sheet,
                                   lambda d: d["cells"][0].update(x=h.PARIS_Y, y=h.PARIS_X),
                                   h.write_json), r"inversés"),
    "assets.web_raster": (raster("w.tif", {"driver": "GTiff"}, driver="COG", dtype="uint16",
                                 size=600), r"aperçu"),
    "assets.massif_block": (document("b_0_0.json", h.massif_block,
                                     lambda d: d["trees"][0].update(stage="adulte"),
                                     h.write_json), r"stage"),
    "species": (species, r"espar"),
    "geotiff_profile": (raster("a.tif", {"compress": "zstd"}), r"ZSTD"),
}


def build(name, tmp, fault):
    """Fichier d'essai, et arguments en plus : --grid pour la variante grille."""
    result = CASES[name][0](tmp, fault)
    path, extra = result if isinstance(result, tuple) else (result, [])
    options = catalog.get(name).get("options", {})
    if options.get("variant") == "grille" and not options.get("is_grid") and not extra:
        extra = ["--grid", str(h.tif(tmp / "reference_grid.tif", dtype="uint16"))]
    return path, extra


def test_every_contract_has_a_case():
    assert set(CASES) == set(catalog.load()), "contrat sans fichier conforme ni fautif"


@pytest.mark.parametrize("name", sorted(CASES))
def test_conform_file_passes(name, tmp_path, capsys):
    path, extra = build(name, tmp_path, fault=False)
    code, out = run(capsys, [name, str(path)] + extra)
    assert code == 0, out


@pytest.mark.parametrize("name", sorted(CASES))
def test_faulty_file_is_refused(name, tmp_path, capsys):
    path, extra = build(name, tmp_path, fault=True)
    code, out = run(capsys, [name, str(path)] + extra)
    assert code == 3, out
    assert re.search(CASES[name][1], out), out
