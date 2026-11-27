"""Mission 084b : l'ombre des semis à la forme de TreeMig (décisions de Pascal du 27/11/2026).

La lumière relative d'une cellule est exp(−k × couvert projeté), rangée dans `light_class_count` classes de largeur égale
sur [0, 1] ; le seuil de lumière de l'essence vient de sa tolérance de Niinemets par klighs puis par la loi de TreeMig
(p. 14) ; la mortalité de stress est la part de la classe sous le seuil × `stress_mortality` (éq. 39 et 40). Avec une
seule lumière par cellule, la part de lumière de la classe qui la contient vaut 1 (la fraction de l'éq. 39 ne joue que
dans cette classe).

Les formes fermées (loi lumière-seuil, part sous le seuil, continuité en klighs = 5) sont prouvées par les tests Rust
(simulate/tests/semis.rs). Ici, de bout en bout, sans lire simulate/src :
- chacun des dix termes nouveaux est écrit par le générateur avec sa source et provisoire = vrai ;
- chacun, absent, arrête simulate (code 2) et est nommé ;
- un oracle exact : une classe unique donne la fraction (seuil) à toute cellule, quelle que soit sa lumière ; elle est
  égale (aux octets) à une survie à pleine lumière abaissée de la même quantité, sans ombre ;
- le nombre de classes et la pente du seuil sont lus (changer l'un ou l'autre change les résultats sous ombre forte).
"""
import hashlib

import pytest

import helpers_m5 as H
import ser_fictive as G

NOUVEAUX = ["klighs_intercept", "klighs_per_shade_tolerance", "klighs_min", "klighs_max",
            "light_threshold_klighs_break", "light_threshold_high_slope", "light_threshold_high_intercept",
            "light_threshold_low_slope", "light_threshold_low_klighs_origin", "light_class_count"]
# Réglages d'essai (aucune valeur écologique) qui rendent le calcul exact en binaire : N = 3 donne klighs = 6 − 3 = 3
# (branche basse), seuil = 0,25 × (3 − 1) = 0,5 ; mortalité de stress 0,25.
SEUIL_EXACT = {"klighs_intercept": 6.0, "klighs_per_shade_tolerance": -1.0, "light_threshold_low_slope": 0.25,
               "stress_mortality": 0.25}


def _empreinte(zdir):
    base = zdir / "sim"
    return {str(p.relative_to(base)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(base.rglob("*.parquet")) if p.name != "flags.parquet"}


def _passage(nom, **regeneration):
    H.remove_zone(nom)
    try:
        zdir, cfg = H.zone_ser(nom, 16, H.sim_ser(3), regeneration=regeneration)
        proc = H.run_simulate(nom, cfg)
        assert proc.returncode == 0, H.queue(proc)
        return _empreinte(zdir)
    finally:
        H.remove_zone(nom)


def test_les_dix_termes_sont_ecrits_provisoires_et_sources():
    lignes = G.regeneration_rows()
    for terme in NOUVEAUX:
        propres = [r for r in lignes if r["term"] == terme]
        assert propres and all(r["provisoire"] and r["unit"] == "1" for r in propres), terme
        assert all(r["source"] == G.SOURCE_TERME[terme] for r in propres), terme
    assert "p. 14" in G.SOURCE_TERME["light_threshold_high_slope"]
    assert "mission 083" in G.SOURCE_TERME["klighs_intercept"]
    assert "sans source" in G.SOURCE_TERME["light_class_count"]
    assert [G.REGENERATION_DEFAUT[t][0] for t in NOUVEAUX] == [9.091, -1.238, 1.0, 9.0, 5.0, 0.1, -0.4, 0.025, 1.0, 10.0]


@pytest.fixture(scope="module", params=NOUVEAUX)
def sans_terme(request):
    nom = f"m5_sans_{request.param}"
    H.remove_zone(nom)
    zdir, cfg = H.zone_ser(nom, 12, H.sim_ser(1), mutate=lambda z: G.write_regeneration(
        z, G.regeneration_rows(G.ESSENCES_DEFAUT, omis=((None, request.param), ("03", request.param),
                                                        ("61", request.param)))))
    res = {"dir": zdir, "proc": H.run_simulate(nom, cfg), "terme": request.param}
    yield res
    H.remove_zone(nom)


def test_terme_absent_code_2_qui_nomme_le_terme(sans_terme):
    proc = sans_terme["proc"]
    assert proc.returncode == 2, H.queue(proc)
    assert sans_terme["terme"] in H.queue(proc)
    assert not (sans_terme["dir"] / "sim").exists() or not any((sans_terme["dir"] / "sim").glob("run.json"))


def test_une_classe_unique_donne_la_fraction_du_seuil_a_toute_cellule_oracle_exact():
    """Une seule classe [0, 1] : toute lumière y tombe, la part vaut seuil = 0,5, la survie 0,75 − 0,25 × 0,5 = 0,625 en
    toute cellule, même sous ombre forte (k = 50). Sans ombre (k = 0, 10 classes : l = 1, classe [0,9 ; 1] au-dessus du
    seuil, part 0) et une survie à pleine lumière de 0,625, tout est identique, aux octets : l'oracle exact."""
    avec_ombre = _passage("m5_ombre_une_classe", **SEUIL_EXACT, light_extinction_coef=50.0, light_class_count=1.0,
                          seedling_survival_full_light_yr=0.75)
    sans_ombre = _passage("m5_ombre_sans", **SEUIL_EXACT, light_extinction_coef=0.0, light_class_count=10.0,
                          seedling_survival_full_light_yr=0.625)
    assert avec_ombre == sans_ombre


def test_les_classes_et_le_seuil_sont_lus_et_pas_des_constantes():
    """Sous ombre forte (k = 50 : l proche de 0), 10 classes donnent un stress entier (part 1) ; une classe, la fraction
    du seuil : les résultats diffèrent. La pente de la loi change le seuil : les résultats diffèrent aussi."""
    forte = {"light_extinction_coef": 50.0}
    dix = _passage("m5_ombre_dix", **forte)
    une = _passage("m5_ombre_une", **forte, light_class_count=1.0)
    assert dix != une
    pente = _passage("m5_ombre_pente", **forte, light_class_count=1.0, light_threshold_high_slope=0.2)
    assert pente != une
