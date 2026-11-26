"""post sur la zone simulée (5 ans) : il aboutit sans réseau, contrôle ses sorties, ne touche pas ses entrées, et son
rejeu rend les mêmes octets (plan T8, T10 ; spec §2 : chaque module appelle le validateur en fin de travail)."""
import json

import helpers_post as P

H = P.H


def test_la_chaine_jusqu_a_simulate_aboutit_sans_reseau(base):
    p = base["chaine"]
    assert p.returncode == 0, "make prepare biomes trees dynamics simulate :\n" + P.queue(p)


def test_post_aboutit_en_code_0_sans_reseau(base):
    p = base["post"]
    assert p.returncode == 0, "post sur la zone simulée :\n" + P.queue(p)


def test_post_ecrit_ses_trois_sorties_aux_chemins_du_catalogue(base_dir):
    for rel in P.POST_OUTPUTS:
        assert (base_dir / rel).is_file(), f"{rel} absent"
    assert not (base_dir / "sim" / ".post_en_cours").exists(), "écriture interrompue laissée dans sim/.post_en_cours"


def test_post_appelle_le_validateur_en_fin_de_module(base):
    sortie = base["post"].stdout + base["post"].stderr
    for contrat in ("post.summary", "post.summary_zone", "post.run"):
        assert f"contrat {contrat})" in sortie, f"post n'a pas contrôlé ses sorties contre {contrat}"


def test_les_sorties_sont_conformes_au_validateur(base_dir):
    for contrat, rel in (("post.summary", "sim/summary.parquet"), ("post.summary_zone", "sim/summary_zone.parquet"),
                         ("post.run", "sim/post.json")):
        p = H.validate(contrat, str(base_dir / rel))
        assert p.returncode == 0, f"{rel} :\n{p.stdout[-2000:]}{p.stderr[-1000:]}"


def test_post_ne_modifie_ni_sim_ni_params(base):
    avant, apres = base["entrees_avant"], base["entrees_apres"]
    assert avant, "aucune entrée relevée"
    assert "params/tarif.parquet" in avant and "sim/run.json" in avant
    assert avant == apres, f"fichiers changés par post : {sorted(k for k in set(avant) | set(apres) if avant.get(k) != apres.get(k))}"


def test_le_rejeu_de_post_rend_les_memes_octets(base):
    assert base["post_2"].returncode == 0, P.queue(base["post_2"])
    a, b = base["sorties_1"], base["sorties_2"]
    for rel in ("sim/summary.parquet", "sim/summary_zone.parquet"):
        assert a[rel] is not None, f"{rel} absent"
        assert a[rel] == b[rel], f"{rel} différent au rejeu"
    ja, jb = json.loads(a["sim/post.json"]), json.loads(b["sim/post.json"])
    ja.pop("duration_s", None)
    jb.pop("duration_s", None)
    assert ja == jb, "post.json différent au rejeu (hors duration_s)"


def test_le_rejeu_rend_le_meme_rapport(base):
    a, b = base["sorties_1"]["rapport_post.html"], base["sorties_2"]["rapport_post.html"]
    assert a is not None, "rapport_post.html absent"
    # la durée peut y être écrite : on compare le texte sans les nombres décimaux de durée
    import re
    norm = lambda s: re.sub(r"\d+[.,]\d+\s*s\b", "<durée>", s.decode("utf-8"))  # noqa: E731
    assert norm(a) == norm(b), "rapport_post.html différent au rejeu"


def test_l_echantillon_aboutit_et_rejoue_a_l_identique(ech):
    assert ech["post"].returncode == 0, "post sur la zone échantillon :\n" + P.queue(ech["post"])
    assert ech["post_2"].returncode == 0, P.queue(ech["post_2"])
    for rel in ("sim/summary.parquet", "sim/summary_zone.parquet"):
        assert ech["sorties_1"][rel] is not None, f"{rel} absent"
        assert ech["sorties_1"][rel] == ech["sorties_2"][rel], f"{rel} différent au rejeu"
    assert ech["entrees_avant"] == ech["entrees_apres"], "post a modifié sim/ ou params/"
