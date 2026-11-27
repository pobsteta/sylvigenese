"""Mission 066 : la mortalité de stress des semis (0,184, TreeMig éq. 40 p. 16) n'est plus une constante du code mais le
terme `stress_mortality` de params/regeneration (contrat version 0.3).

- Référence : les résultats du mode `cohorts` sont **les mêmes octets** que ceux relevés (SHA-256 des fichiers Parquet de
  sim/, tests/m5/reference/cohorts_ombre_treemig.json), aux deux niveaux : SER (32 × 32, 5 ans) et massif (8 ans).
  Mission 084b (27/11/2026) : l'ombre des semis passe à la forme de TreeMig (lumière exp(−k × couvert) en 10 classes,
  seuil de klighs) ; la référence est relevée de nouveau : celle de la SER ne change pas (aucune cellule de la SER
  fictive n'est sous le seuil de lumière, ni avant ni après), celle du massif change (15 fichiers sur 18). L'ancienne
  référence (cohorts_avant_stress_mortality.json, état d'avant 084b) est gardée pour le dire (`AVANT_084B`).
  Histoire de la référence d'avant : relevée le 26/11/2026 sur le moteur de la mission 065 (identité avant et après 066),
  puis le 27/11/2026 pour 080 (identité avant et après le contrôle « K couvre d99 »).
  flags.parquet n'y est pas : il porte les mentions Q2 et Q3 et, depuis 084b, celle des classes de lumière provisoires.
- Le terme est lu : sous ombre forte, un autre nombre change les résultats (le test discrimine).
- Absent : code 2, le message nomme le terme et l'essence ; aucune valeur d'emprunt.
- Mentions Q2 (stock initial en régime) et Q3 (lumière et ombre seules) écrites en mode cohorts, et non en ifn_direct.
"""
import hashlib
import json

import pytest

import helpers_m5 as H
import ser_fictive as G

REFERENCE = json.loads((H.ROOT / "tests" / "m5" / "reference" / "cohorts_ombre_treemig.json")
                       .read_text(encoding="utf-8"))
AVANT_084B = json.loads((H.ROOT / "tests" / "m5" / "reference" / "cohorts_avant_stress_mortality.json")
                        .read_text(encoding="utf-8"))


def empreinte_parquet(zdir):
    """SHA-256 de chaque fichier Parquet de sim/, sauf flags.parquet (il nomme la zone et porte les mentions)."""
    base = zdir / "sim"
    return {str(p.relative_to(base)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(base.rglob("*.parquet")) if p.name != "flags.parquet"}


def test_le_generateur_ecrit_le_terme_a_la_valeur_de_treemig():
    valeur, unite = G.REGENERATION_DEFAUT["stress_mortality"]
    assert (valeur, unite) == (0.184, "1/an")
    lignes = [r for r in G.regeneration_rows() if r["term"] == "stress_mortality"]
    assert lignes and all(r["value"] == 0.184 and r["unit"] == "1/an" and r["provisoire"] for r in lignes)


def test_ser_cohorts_resultats_identiques_a_la_reference(ser_nominale):
    assert ser_nominale["proc"].returncode == 0, H.queue(ser_nominale["proc"])
    maintenant = empreinte_parquet(ser_nominale["dir"])
    assert set(maintenant) == set(REFERENCE["ser_nominale"])
    assert maintenant == REFERENCE["ser_nominale"]


def test_massif_cohorts_resultats_identiques_a_la_reference(massif_cohorts):
    assert massif_cohorts["proc"].returncode == 0, H.queue(massif_cohorts["proc"])
    maintenant = empreinte_parquet(massif_cohorts["dir"])
    assert set(maintenant) == set(REFERENCE["massif_cohorts"])
    assert maintenant == REFERENCE["massif_cohorts"]


def test_ce_que_084b_change_dans_la_reference():
    """Le changement est dit et prouvé : la SER fictive n'a aucune cellule sous le seuil de lumière (octets inchangés),
    le massif change (15 fichiers sur 18 : des cellules à fort couvert projeté passent sous le seuil)."""
    assert REFERENCE["ser_nominale"] == AVANT_084B["ser_nominale"]
    changes = [f for f in AVANT_084B["massif_cohorts"] if REFERENCE["massif_cohorts"][f] != AVANT_084B["massif_cohorts"][f]]
    assert len(changes) == 15 and len(AVANT_084B["massif_cohorts"]) == 18, changes


def _passage_ombrage(valeur):
    """SER de 20 × 20, 3 ans, coefficient d'extinction très fort (réglage d'essai) : l'ombre de toute cellule qui a des
    adultes dépasse la tolérance, et la mortalité de stress s'applique. Un passage avec le terme à `valeur`."""
    nom = f"m5_ser_ombragee_{str(valeur).replace('.', '')}"
    H.remove_zone(nom)
    try:
        zdir, cfg = H.zone_ser(nom, 20, H.sim_ser(3),
                               regeneration={"light_extinction_coef": 50.0, "stress_mortality": valeur})
        proc = H.run_simulate(nom, cfg)
        assert proc.returncode == 0, H.queue(proc)
        return empreinte_parquet(zdir)
    finally:
        H.remove_zone(nom)


def test_le_terme_est_lu_et_pas_une_constante():
    """Le test discrimine : sous ombre forte, 0 et 0,184 donnent des fichiers de sim/ différents (si le moteur gardait
    une constante, les deux seraient identiques). Il produit lui-même les deux passages (robuste à `-k`)."""
    assert _passage_ombrage(0.184) != _passage_ombrage(0.0)


@pytest.fixture(scope="module", params=["ser", "massif"])
def sans_stress(request):
    nom = f"m5_sans_stress_{request.param}"
    H.remove_zone(nom)
    if request.param == "ser":
        zdir, cfg = H.zone_ser(nom, 12, H.sim_ser(1),
                               mutate=lambda z: G.write_regeneration(
                                   z, G.regeneration_rows(G.ESSENCES_DEFAUT, omis=((None, "stress_mortality"),
                                                                                   ("03", "stress_mortality"),
                                                                                   ("61", "stress_mortality")))))
    else:
        zdir, cfg = H.zone_massif(nom, H.sim_massif(1), lambda z: G.write_regeneration(
            z, G.regeneration_rows(H.ESSENCES_MASSIF, par_essence=False, omis=((None, "stress_mortality"),))))
    res = {"dir": zdir, "proc": H.run_simulate(nom, cfg), "niveau": request.param}
    yield res
    H.remove_zone(nom)


def test_terme_absent_code_2_qui_nomme_le_terme(sans_stress):
    proc = sans_stress["proc"]
    assert proc.returncode == 2, H.queue(proc)
    texte = H.queue(proc)
    assert "stress_mortality" in texte, texte
    assert not (sans_stress["dir"] / "sim").exists() or not any((sans_stress["dir"] / "sim").glob("run.json"))


def test_mentions_q2_et_q3_en_mode_cohorts(ser_nominale, massif_cohorts):
    for res in (ser_nominale, massif_cohorts):
        kinds = H.flags_kinds(res["dir"])
        assert "stock_initial_en_regime" in kinds and "lumiere_et_ombre_seules" in kinds
        assert "classes_lumiere_et_extinction_provisoires" in kinds, "réglages provisoires de l'ombre non dits"
        assert "semis_non_simules" not in kinds


def test_pas_de_mention_q2_q3_en_ifn_direct(massif_ifn_direct):
    kinds = H.flags_kinds(massif_ifn_direct["dir"])
    assert "semis_non_simules" in kinds
    assert "stock_initial_en_regime" not in kinds and "lumiere_et_ombre_seules" not in kinds
    assert "classes_lumiere_et_extinction_provisoires" not in kinds
