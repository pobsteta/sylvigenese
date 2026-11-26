"""Pytest de `post` (mission 052) : volume, biomasse et carbone, tests d'acceptation écrits sans lire le code de post.

Zones (sous data/, hors dépôt, effacées en fin de session ; le jeu fictif versionné n'est jamais modifié) :
  - `post_base` : copie du jeu fictif, `make prepare biomes trees dynamics simulate` sur 5 ans (2022 à 2027), sans
    réseau ; puis post, post encore (rejeu), puis assets. C'est la zone « simulée » : l'oracle y recalcule tout.
  - `post_ech` : zone « échantillon » : rasters de post_base, sim/ écrit par l'aide de test (13 arbres choisis,
    2022 et 2023), de quoi refaire chaque valeur à la calculette ; puis post, post (rejeu), assets.
  - variantes de l'échantillon (une seule chose changée) et refus (une seule chose cassée).

Aucun test n'est sauté : si une commande échoue, les tests qui en dépendent échouent en disant la commande et sa sortie.
"""
import shutil
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import helpers_post as P  # noqa: E402

H = P.H
BASE = "post_base"
ECH = "post_ech"


def exige(res: dict, *steps: str) -> Path:
    for s in steps:
        p = res[s]
        assert p.returncode == 0, f"étape « {s} » en échec :\n{P.queue(p)}"
    return res["dir"]


@pytest.fixture(scope="session")
def base():
    """Chaîne complète sur une copie du jeu fictif, 5 ans simulés, puis post (deux fois) et assets."""
    zdir = H.ROOT / "data" / BASE
    try:
        P.copy_zone(H.ZONE, zdir)
        H.clean_chain_outputs(zdir)
        cfg = P.write_config(zdir, BASE)
        res = {"dir": zdir, "config": cfg, "name": BASE}
        res["chaine"] = H.run_make("prepare", "biomes", "trees", "dynamics", "simulate", zone=BASE, config=cfg)
        res["entrees_avant"] = P.hashes(zdir)
        res["post"] = P.run_post(cfg)
        res["sorties_1"] = P.post_outputs(zdir)
        res["post_2"] = P.run_post(cfg)
        res["sorties_2"] = P.post_outputs(zdir)
        res["entrees_apres"] = P.hashes(zdir)
        res["assets"] = H.run_assets(cfg)
        yield res
    finally:
        P.remove_zone(BASE)


@pytest.fixture(scope="session")
def base_dir(base):
    return exige(base, "chaine", "post")


@pytest.fixture(scope="session")
def oracle(base):
    """L'oracle ne dépend que de sim/, de params/ et des rasters : il se construit même si post échoue."""
    exige(base, "chaine")
    return P.Oracle(base["dir"], base["config"])


def build_ech(name: str, tarif=None, rows=None, run_assets=False, rejeu=False) -> dict:
    """Zone échantillon `name` : rasters de post_base (liens physiques), params/ copié, sim/ écrit à la main.
    `tarif(lignes)` modifie params/tarif.parquet ; `rows(année, lignes)` modifie les arbres avant écriture."""
    zdir = H.ROOT / "data" / name
    P.copy_zone(H.ROOT / "data" / BASE, zdir, link=True)
    cfg = P.write_config(zdir, name, years=len(P.MINI_YEARS) - 1, seed=P.MINI_SEED, t0=P.MINI_YEARS[0])
    if tarif is not None:
        P.rewrite_tarif(zdir, tarif)
    P.write_mini_sim(zdir, cfg, rows)
    res = {"dir": zdir, "config": cfg, "name": name, "entrees_avant": P.hashes(zdir)}
    res["post"] = P.run_post(cfg)
    res["sorties_1"] = P.post_outputs(zdir)
    if rejeu:
        res["post_2"] = P.run_post(cfg)
        res["sorties_2"] = P.post_outputs(zdir)
    res["entrees_apres"] = P.hashes(zdir)
    if run_assets:
        res["assets"] = H.run_assets(cfg)
    return res


@pytest.fixture(scope="session")
def ech(base):
    exige(base, "chaine")
    try:
        yield build_ech(ECH, run_assets=True, rejeu=True)
    finally:
        P.remove_zone(ECH)


@pytest.fixture(scope="session")
def ech_dir(ech):
    return exige(ech, "post")


@pytest.fixture(scope="session")
def ech_oracle(ech):
    return P.Oracle(ech["dir"], ech["config"])


# ------------------------------------------------------------------ variantes de l'échantillon (code 0 attendu)
def _sans_racines(rows):
    return [r for r in rows if r["modele"] != "racines"]


def _metamorphe(rows):
    """E(D) du sapin (61) doublé ; infradensité des feuillus doublée. Rien d'autre."""
    out = []
    for r in rows:
        r = dict(r)
        if r["modele"] == "expansion_resineux" and r["essence"] == "61":
            r["valeur"] = 2.0 * r["valeur"]
        if r["modele"] == "infradensite" and r["groupe"] == "feuillu":
            r["valeur"] = 2.0 * r["valeur"]
        out.append(r)
    return out


@pytest.fixture(scope="session")
def ech_sans_racines(ech):
    exige(ech, "post")
    try:
        yield build_ech("post_var_r", tarif=_sans_racines, run_assets=True)
    finally:
        P.remove_zone("post_var_r")


@pytest.fixture(scope="session")
def ech_metamorphe(ech):
    exige(ech, "post")
    try:
        yield build_ech("post_var_m", tarif=_metamorphe)
    finally:
        P.remove_zone("post_var_m")


# ------------------------------------------------------------------ refus (saisie incomplète, hors référentiel, doublon)
def _tarif_absent(zdir):
    (zdir / "params" / "tarif.parquet").unlink()


def _drop_model(model, groupe=None):
    def f(zdir):
        P.rewrite_tarif(zdir, lambda rows: [r for r in rows
                                            if not (r["modele"] == model and (groupe is None or r["groupe"] == groupe))])
    return f


def _sim_absent(zdir):
    shutil.rmtree(zdir / "sim")


def _run_json_absent(zdir):
    (zdir / "sim" / "run.json").unlink()


def _run_json_autre_config(zdir):
    import json
    p = zdir / "sim" / "run.json"
    run = json.loads(p.read_text(encoding="utf-8"))
    run["config_sha256"] = "0" * 64
    p.write_text(json.dumps(run, indent=1, sort_keys=True), encoding="utf-8")


def _partition_rows(fn):
    """Réécrit les partitions de sim/trees (écrites par l'aide, jamais des liens)."""
    def f(zdir):
        import pyarrow.parquet as pq
        for p in sorted((zdir / "sim" / "trees").rglob("*.parquet")):
            t = pq.read_table(p)
            p.unlink()
            pq.write_table(fn(t), p)
    return f


def _essence_99(t):
    import pyarrow as pa
    i = t.schema.get_field_index("species")
    v = t.column("species").to_pylist()
    v[0] = "99"
    return t.set_column(i, t.schema.field(i), pa.array(v, t.schema.field(i).type))


def _tree_id_double(t):
    import pyarrow as pa
    i = t.schema.get_field_index("tree_id")
    v = t.column("tree_id").to_pylist()
    v[1] = v[0]
    return t.set_column(i, t.schema.field(i), pa.array(v, t.schema.field(i).type))


# nom : (mutation, mots dont l'un doit être dans le message (sans accent, minuscules), code exigé ; None = non nul)
REFUS = {
    "tarif_absent": (_tarif_absent, ("tarif",), 2),
    "modele_infradensite_absent": (_drop_model("infradensite"), ("infradensite",), 2),
    "modele_fraction_carbone_resineux_absent": (_drop_model("fraction_carbone", "resineux"), ("fraction_carbone", "fraction de carbone"), 2),
    "sim_absent": (_sim_absent, ("sim",), 2),
    "run_json_absent": (_run_json_absent, ("run.json",), 2),
    "run_json_d_une_autre_config": (_run_json_autre_config, ("empreinte", "sha256", "run.json", "differe"), 2),
    "essence_hors_referentiel": (_partition_rows(_essence_99), ("99",), None),
    "tree_id_en_double": (_partition_rows(_tree_id_double), ("tree_id", "double", "doublon", "unique"), None),
}


@pytest.fixture(scope="module", params=list(REFUS))
def refus(request, ech):
    exige(ech, "post")
    # nom de zone NEUTRE : le message cite le chemin, qui ne doit contenir aucun des mots attendus
    nom = f"post_r{sorted(REFUS).index(request.param):02d}"
    mutate, mots, code = REFUS[request.param]
    zdir = H.ROOT / "data" / nom
    try:
        P.copy_zone(H.ROOT / "data" / BASE, zdir, link=True)
        cfg = P.write_config(zdir, nom, years=len(P.MINI_YEARS) - 1, seed=P.MINI_SEED, t0=P.MINI_YEARS[0])
        P.write_mini_sim(zdir, cfg)
        mutate(zdir)
        p = P.run_post(cfg)
        yield {"cas": request.param, "dir": zdir, "proc": p, "mots": mots, "code": code}
    finally:
        P.remove_zone(nom)
