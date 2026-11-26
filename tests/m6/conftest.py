"""Fixtures de session de tests/m6 (mission 069). Zones sous data/m6_* (hors dépôt), supprimées ensuite.
Aucune fixture ne saute un test : si `assets` échoue, les tests qui lisent ses sorties échouent en disant pourquoi."""
import shutil
from pathlib import Path

import pyarrow.parquet as pq
import pytest

import helpers_m6 as M
import helpers_m4 as H


@pytest.fixture(scope="session")
def zone_a():
    """Jeu fictif + exemplaires synthétiques de la fixture : `assets` une fois."""
    z = M.build_zone("m6_a")
    try:
        yield z
    finally:
        H.remove_zone_copy("m6_a")


@pytest.fixture(scope="session")
def zone_b():
    """Même entrée, autre dossier, autre exécution : sert à l'identité à l'octet près."""
    z = M.build_zone("m6_b")
    try:
        yield z
    finally:
        H.remove_zone_copy("m6_b")


@pytest.fixture(scope="session")
def oracle(zone_a):
    return H.Oracle(H.ZONE)


@pytest.fixture(scope="session")
def zone_a_rerun(zone_a):
    """Rejeu de assets sur la zone A déjà construite (idempotence) : octets des .glb avant et après."""
    zdir = M.exige(zone_a)
    avant = {k: M.sha(p) for k, p in M.glb_files(zdir).items()}
    proc = H.run_assets(zone_a["config"])
    return {"proc": proc, "avant": avant, "apres": {k: M.sha(p) for k, p in M.glb_files(zdir).items()}}


@pytest.fixture(scope="session")
def zone_exemplaire_modifie():
    """Copie des exemplaires où UN segment de Fagus_sylvatica_mature change de 5 cm : seul son .glb doit changer."""
    nom = "m6_modifie"
    d = H.ROOT / "data" / "m6_exemplaires_modifies"
    try:
        if d.exists():
            shutil.rmtree(d)
        shutil.copytree(M.EXEMPLARS, d)
        p = d / "Fagus_sylvatica_mature.parquet"
        t = pq.read_table(p)
        i = t.schema.get_field_index("x1")
        col = t.column("x1").to_pylist()
        col[-1] += 0.05      # extrémité de la branche repère (dernier segment), au-delà de toute tolérance d'arrondi
        pq.write_table(t.set_column(i, t.schema.field(i), [col]), p, compression="none")
        yield M.build_zone(nom, exemplars_dir=d)
    finally:
        H.remove_zone_copy(nom)
        shutil.rmtree(d, ignore_errors=True)


@pytest.fixture(scope="session")
def zone_generique():
    """Variante du terrain : (1) Fagus_sylvatica sans exemplaire (hêtres -> générique feuillu, pas de chêne emprunté) ;
    (2) 40 chênes (03) deviennent du châtaignier (10, sans modèle du générateur) ; (3) 5 hêtres sont ramenés à
    h = 0,15 h_pot (stade young) pour que `young` serve."""
    nom = "m6_generique"
    ex = H.ROOT / "data" / "m6_exemplaires_sans_hetre"
    info: dict = {}
    try:
        if ex.exists():
            shutil.rmtree(ex)
        shutil.copytree(M.EXEMPLARS, ex, ignore=shutil.ignore_patterns("Fagus_sylvatica_*"))

        def mut(d):
            t = H.read_trees_init(d)
            sp = t["species"].astype(object).copy()
            chenes = [i for i in range(len(sp)) if sp[i] == "03"][:40]
            for i in chenes:
                sp[i] = "10"
            hp = M.hpot_of_trees(d, t)
            h = t["h"].astype(float).copy()
            hetres = [i for i in range(len(sp)) if sp[i] == "09"][:5]
            for i in hetres:
                h[i] = 0.15 * hp[i]
            H.write_trees_init(d, {"species": sp, "h": h})
            info.update(castaneas=[str(t["tree_id"][i]) for i in chenes], jeunes=[str(t["tree_id"][i]) for i in hetres])

        z = M.build_zone(nom, mut, exemplars_dir=ex)
        z.update(info)
        z["exemplars_dir"] = ex
        yield z
    finally:
        H.remove_zone_copy(nom)
        shutil.rmtree(ex, ignore_errors=True)


# ------------------------------------------------------------------ refus (cas du terrain)
def _corrompu(d: Path):
    p = d / "Abies_alba_old.parquet"
    p.write_bytes(p.read_bytes()[:200])                        # Parquet tronqué


def _yup_declare(d: Path):
    p = d / "Fagus_sylvatica_young.parquet"
    t = pq.read_table(p)
    meta = dict(t.schema.metadata)
    meta[b"frame"] = b"y-up"                                    # repère non dit ou autre que z-up
    pq.write_table(t.replace_schema_metadata(meta), p, compression="none")


def _sans_colonne(d: Path):
    p = d / "Quercus_spec_pole.parquet"
    t = pq.read_table(p)
    pq.write_table(t.drop_columns(["r1_m"]), p, compression="none")


def _essence_hors_referentiel(d: Path):
    p = d / "Fagus_sylvatica_pole.parquet"
    t = pq.read_table(p)
    meta = dict(t.schema.metadata)
    meta[b"essence"] = b"Zzzz_inventus"
    pq.write_table(t.replace_schema_metadata(meta), d / "Zzzz_inventus_pole.parquet", compression="none")
    p.unlink()


def _doublon(d: Path):
    import shutil as sh
    sh.copy(d / "Abies_alba_pole.parquet", d / "Abies_alba_pole_bis.parquet")


def _non_synthetique(d: Path):
    p = d / "Abies_alba_mature.parquet"
    t = pq.read_table(p)
    meta = dict(t.schema.metadata)
    meta[b"synthetic"] = b"false"                               # un exemplaire présenté comme réel
    pq.write_table(t.replace_schema_metadata(meta), p, compression="none")


def _sans_commit(d: Path):
    p = d / "Abies_alba_young.parquet"
    t = pq.read_table(p)
    meta = {k: v for k, v in t.schema.metadata.items() if k != b"source_commit"}
    pq.write_table(t.replace_schema_metadata(meta), p, compression="none")


# nom : (mutation du dossier d'exemplaires, mots dont l'un doit être dans le message)
REFUS_EXEMPLAIRES = {
    "parquet_corrompu": (_corrompu, ("Abies_alba_old",)),
    "repere_non_zup": (_yup_declare, ("z-up", "frame", "repère")),
    "colonne_r1_m_absente": (_sans_colonne, ("r1_m",)),
    "essence_hors_referentiel": (_essence_hors_referentiel, ("Zzzz_inventus",)),
    "doublon_essence_stade": (_doublon, ("doublon", "double", "unique", "deux fois", "dupliqu")),
    "exemplaire_non_synthetique": (_non_synthetique, ("synthetic", "synthétique")),
    "source_commit_absent": (_sans_commit, ("source_commit",)),
}


@pytest.fixture(scope="module", params=list(REFUS_EXEMPLAIRES))
def refus(request):
    nom = "m6_refus_" + str(sorted(REFUS_EXEMPLAIRES).index(request.param))
    ex = H.ROOT / "data" / (nom + "_exemplaires")
    mutate, mots = REFUS_EXEMPLAIRES[request.param]
    try:
        if ex.exists():
            shutil.rmtree(ex)
        shutil.copytree(M.EXEMPLARS, ex)
        mutate(ex)
        z = M.build_zone(nom, exemplars_dir=ex)
        yield request.param, z, mots
    finally:
        H.remove_zone_copy(nom)
        shutil.rmtree(ex, ignore_errors=True)


@pytest.fixture(scope="session")
def zone_exemplars_dir_absent():
    nom = "m6_refus_dir_absent"
    try:
        yield M.build_zone(nom, exemplars_dir=H.ROOT / "data" / "n_existe_pas_m6")
    finally:
        H.remove_zone_copy(nom)


# ------------------------------------------------------------------ zone avec sim/ (mode `sim`, recrutement ifn_direct)
@pytest.fixture(scope="session")
def zone_sim(zone_a):
    """Copie du jeu fictif, `make dynamics simulate` sur 15 ans (comme tests/m4 `temps`), puis `assets` (pas de 10) avec
    les exemplaires de la fixture. Années retenues : 2022, 2032, 2037. Recrutement `ifn_direct` : le mode `cohorts` exige
    params/regeneration, absent du jeu fictif (cas non couvert ici, dit au compte rendu)."""
    import helpers_m4_temps as T
    nom = "m6_sim"
    try:
        zdir, _ = H.clone_zone(nom)
        base = T.write_config(zdir, nom, T.sim_block(), {"year_step": T.STEP}, "config_m6_base.yml")
        cfg = M.write_config(zdir, nom, M.EXEMPLARS, "config_m6_sim.yml", base=base)
        res = {"dir": zdir, "name": nom, "config": cfg, "make": H.run_make("dynamics", "simulate", zone=nom, config=cfg)}
        res["proc"] = H.run_assets(cfg) if res["make"].returncode == 0 else res["make"]
        yield res
    finally:
        H.remove_zone_copy(nom)
