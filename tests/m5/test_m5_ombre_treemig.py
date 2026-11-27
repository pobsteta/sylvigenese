"""Missions 084b et 084c : l'ombre des semis à la forme de TreeMig (décisions de Pascal du 27/11/2026).

La lumière relative d'une cellule est exp(−k × couvert projeté) ; le seuil de lumière de l'essence vient de sa tolérance
de Niinemets par klighs puis par la loi de TreeMig (p. 14) ; la mortalité de stress est `stress_mortality` × part, avec,
depuis 084c, une **comparaison directe** : part = 1 si l < seuil, 0 sinon (l = seuil : 0, TreeMig : l_up < seuil, strict).
Il n'y a plus de classes de lumière : `light_class_count` est retiré du contrat (version 0.5) et refusé s'il est fourni.

Les formes fermées (loi lumière-seuil, seuil franchi, non franchi, égalité) sont prouvées par les tests Rust
(simulate/tests/semis.rs). Ici, de bout en bout, sans lire simulate/src, **aux deux niveaux (SER et massif)** :
- chacun des neuf termes nouveaux est écrit par le générateur avec sa source et provisoire = vrai ;
- chacun, absent, arrête simulate (code 2) et est nommé ;
- `light_class_count`, fourni, est refusé (code 2) par son nom et « terme retiré » ;
- oracles exacts (aux octets) : égalité l = seuil = 1 (k = 0) donne les mêmes fichiers que sans stress ; seuil non franchi
  (k = 0, seuil 0,5) aussi ; seuil franchi (k énorme : l = 0 sous toute canopée) ne dépend pas de la hauteur du seuil
  (0,5 ou 1) ; et il diffère d'un passage sans stress (le stress s'applique) ;
- le seuil et le coefficient d'extinction sont lus (changer l'un change les résultats).
"""
import hashlib

import pyarrow.parquet as pq
import pytest

import helpers_m5 as H
import ser_fictive as G

NOUVEAUX = ["klighs_intercept", "klighs_per_shade_tolerance", "klighs_min", "klighs_max",
            "light_threshold_klighs_break", "light_threshold_high_slope", "light_threshold_high_intercept",
            "light_threshold_low_slope", "light_threshold_low_klighs_origin"]
# Mission 086 (contrat 0.6) : les deux bornes de la plage de N testée, lues comme les autres termes (absentes : code 2).
PLAGE_N = ["klighs_tested_n_min", "klighs_tested_n_max"]
TERMES_LUS = NOUVEAUX + PLAGE_N
# Réglages d'essai (aucune valeur écologique) qui rendent le calcul exact en binaire : N = 3 donne klighs = 6 − 3 = 3
# (branche basse), seuil = 0,25 × (3 − 1) = 0,5 ; mortalité de stress 0,25 ; survie à pleine lumière 0,75.
SEUIL_EXACT = {"klighs_intercept": 6.0, "klighs_per_shade_tolerance": -1.0, "light_threshold_low_slope": 0.25,
               "stress_mortality": 0.25, "seedling_survival_full_light_yr": 0.75}
# Seuil de 1,0 exactement : klighs = 4 (ordonnée 4, pente 0), branche haute dès klighs ≥ 0, 0,25 × 4 + 0 = 1.
SEUIL_UN = {"klighs_intercept": 4.0, "klighs_per_shade_tolerance": 0.0, "light_threshold_klighs_break": 0.0,
            "light_threshold_high_slope": 0.25, "light_threshold_high_intercept": 0.0,
            "stress_mortality": 0.25, "seedling_survival_full_light_yr": 0.75}
SANS_STRESS = {"stress_mortality": 0.0, "seedling_survival_full_light_yr": 0.75}
NIVEAUX = ["ser", "massif"]


def _empreinte(zdir):
    base = zdir / "sim"
    return {str(p.relative_to(base)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(base.rglob("*.parquet")) if p.name != "flags.parquet"}


def _zone(nom, niveau, regeneration, mutate=None):
    if niveau == "ser":
        return H.zone_ser(nom, 16, H.sim_ser(3), mutate=mutate, regeneration=regeneration)
    return H.zone_massif(nom, H.sim_massif(3), mutate=mutate, regeneration=regeneration)


def _passage(nom, niveau, **regeneration):
    nom = f"{nom}_{niveau}"
    H.remove_zone(nom)
    try:
        zdir, cfg = _zone(nom, niveau, regeneration)
        proc = H.run_simulate(nom, cfg)
        assert proc.returncode == 0, H.queue(proc)
        return _empreinte(zdir)
    finally:
        H.remove_zone(nom)


def test_les_neuf_termes_sont_ecrits_provisoires_et_sources():
    lignes = G.regeneration_rows()
    for terme in NOUVEAUX:
        propres = [r for r in lignes if r["term"] == terme]
        assert propres and all(r["provisoire"] and r["unit"] == "1" for r in propres), terme
        assert all(r["source"] == G.SOURCE_TERME[terme] for r in propres), terme
    assert "p. 14" in G.SOURCE_TERME["light_threshold_high_slope"]
    assert "mission 083" in G.SOURCE_TERME["klighs_intercept"]
    assert [G.REGENERATION_DEFAUT[t][0] for t in NOUVEAUX] == [9.091, -1.238, 1.0, 9.0, 5.0, 0.1, -0.4, 0.025, 1.0]
    assert "light_class_count" not in G.REGENERATION_DEFAUT, "terme retiré (contrat 0.5)"
    for terme in PLAGE_N:
        propres = [r for r in lignes if r["term"] == terme]
        assert propres and all(r["provisoire"] and r["unit"] == "1" for r in propres), terme
        assert all(r["source"] == G.SOURCE_TERME[terme] and "§15.2" in r["source"] for r in propres), terme
    assert [G.REGENERATION_DEFAUT[t][0] for t in PLAGE_N] == [1.5, 4.6]


@pytest.fixture(scope="module", params=[(t, n) for n in NIVEAUX for t in TERMES_LUS],
                ids=[f"{n}-{t}" for n in NIVEAUX for t in TERMES_LUS])
def sans_terme(request):
    terme, niveau = request.param
    nom = f"m5_sans_{terme}_{niveau}"
    H.remove_zone(nom)
    if niveau == "ser":
        zdir, cfg = H.zone_ser(nom, 12, H.sim_ser(1), mutate=lambda z: G.write_regeneration(
            z, G.regeneration_rows(G.ESSENCES_DEFAUT, omis=((None, terme), ("03", terme), ("61", terme)))))
    else:
        zdir, cfg = H.zone_massif(nom, H.sim_massif(1), lambda z: G.write_regeneration(
            z, G.regeneration_rows(H.ESSENCES_MASSIF, par_essence=False, omis=((None, terme),))))
    res = {"dir": zdir, "proc": H.run_simulate(nom, cfg), "terme": terme}
    yield res
    H.remove_zone(nom)


def test_terme_absent_code_2_qui_nomme_le_terme(sans_terme):
    proc = sans_terme["proc"]
    assert proc.returncode == 2, H.queue(proc)
    assert sans_terme["terme"] in H.queue(proc)
    assert not (sans_terme["dir"] / "sim").exists() or not any((sans_terme["dir"] / "sim").glob("run.json"))


@pytest.mark.parametrize("niveau", NIVEAUX)
def test_light_class_count_fourni_est_refuse_par_son_nom_terme_retire(niveau):
    """Mission 084c : le terme retiré n'est ni lu ni ignoré en silence : code 2, « terme retiré » et son nom, rien écrit."""
    nom = f"m5_terme_retire_{niveau}"
    H.remove_zone(nom)
    try:
        def ajoute(z):
            essences = G.ESSENCES_DEFAUT if niveau == "ser" else H.ESSENCES_MASSIF
            reglages = {} if niveau == "ser" else {"kernel_scale_m": H.ECHELLE_NOYAU_MASSIF,
                                                   "fecundity_seeds_per_m2_ba_yr": H.FECONDITE_MASSIF}
            lignes = G.regeneration_rows(essences, reglages, par_essence=(niveau == "ser"))
            lignes.append({"species": None, "species_group": "toutes_essences", "term": "light_class_count",
                           "value": 10.0, "unit": "1", "provisoire": True, "source": "ancienne version 0.4"})
            G.write_regeneration(z, lignes)
        zdir, cfg = _zone(nom, niveau, {}, mutate=ajoute)
        proc = H.run_simulate(nom, cfg)
        texte = H.queue(proc)
        assert proc.returncode == 2, texte
        assert "terme retiré" in texte and "light_class_count" in texte, texte
        assert not (zdir / "sim").exists() or not any((zdir / "sim").glob("run.json"))
    finally:
        H.remove_zone(nom)


@pytest.mark.parametrize("niveau", NIVEAUX)
def test_egalite_au_seuil_pas_de_stress_oracle_exact(niveau):
    """k = 0 : l = 1 partout ; seuil = 1 exactement : l = seuil, pas de stress (comparaison stricte). Mêmes fichiers, aux
    octets, qu'un passage sans stress (stress_mortality = 0) ; avec une comparaison « ≤ », la survie serait abaissée de
    0,25 partout et les fichiers différeraient."""
    egal = _passage("m5_ombre_egal", niveau, **SEUIL_UN, light_extinction_coef=0.0)
    sans = _passage("m5_ombre_egal_sans", niveau, **SANS_STRESS, light_extinction_coef=0.0)
    assert egal == sans


@pytest.mark.parametrize("niveau", NIVEAUX)
def test_seuil_non_franchi_pas_de_stress_oracle_exact(niveau):
    """k = 0 : l = 1 > seuil = 0,5 : aucun stress, mêmes octets qu'un passage sans stress."""
    non_franchi = _passage("m5_ombre_non_franchi", niveau, **SEUIL_EXACT, light_extinction_coef=0.0)
    sans = _passage("m5_ombre_non_franchi_sans", niveau, **SANS_STRESS, light_extinction_coef=0.0)
    assert non_franchi == sans


@pytest.mark.parametrize("niveau", NIVEAUX)
def test_seuil_franchi_stress_entier_oracle_exact(niveau):
    """k énorme : l = exp(−k × c) = 0 sous toute canopée (c > 0), l = 1 sans canopée (c = 0, au-dessus de 0,5 et égal à 1 :
    pas de stress). Le stress est donc entier sous canopée, quelle que soit la hauteur du seuil : seuil 0,5 et seuil 1
    donnent les mêmes octets (une fraction de classe ferait dépendre le résultat du seuil) ; et le stress s'applique
    (les octets diffèrent d'un passage sans stress).

    Nuance : ce test seul ne distingue pas l'ancienne forme (fraction de classe coupée) de la comparaison directe. Ce sont
    le test d'égalité (l = seuil, pas de stress, ci-dessous) et le test Rust à l = 0,12 (simulate/tests/semis.rs) qui la
    distinguent ; celui-ci prouve que le stress est entier sous canopée et indépendant de la hauteur du seuil."""
    k = {"light_extinction_coef": 1.0e6}
    moitie = _passage("m5_ombre_franchi_05", niveau, **SEUIL_EXACT, **k)
    un = _passage("m5_ombre_franchi_1", niveau, **SEUIL_UN, **k)
    sans = _passage("m5_ombre_franchi_sans", niveau, **SANS_STRESS, **k)
    assert moitie == un
    assert moitie != sans


@pytest.mark.parametrize("niveau", NIVEAUX)
def test_le_seuil_et_l_extinction_sont_lus_et_pas_des_constantes(niveau):
    """Un coefficient d'extinction fort change les résultats (la lumière est lue) ; la pente de la loi change le seuil,
    donc les résultats d'une lumière intermédiaire (k = 3 : l entre les deux seuils des cellules à fort couvert)."""
    faible = _passage("m5_ombre_faible", niveau, light_extinction_coef=0.0)
    forte = _passage("m5_ombre_forte", niveau, light_extinction_coef=50.0)
    assert faible != forte
    moyen = {"light_extinction_coef": 3.0, "stress_mortality": 0.5}
    seuil_bas = _passage("m5_ombre_seuil_bas", niveau, **moyen)
    seuil_haut = _passage("m5_ombre_seuil_haut", niveau, **moyen, light_threshold_high_slope=0.2)
    assert seuil_bas != seuil_haut


def _message_ombre(zdir):
    t = pq.read_table(zdir / "sim" / "flags.parquet").to_pylist()
    messages = [r["message"] for r in t if r["kind"] == "ombre_semis_provisoire"]
    assert len(messages) == 1, [r["kind"] for r in t]
    return messages[0]


def test_ombre_semis_provisoire_nomme_les_essences_hors_plage_de_n_au_niveau_ser():
    """Mission 086 : 03 à N = 0,5 (hors de 1,5 à 4,6) est nommée, 61 à N = 3 (dans la plage) ne l'est pas ; l'ancien nom
    du signalement n'est plus écrit."""
    nom = "m5_ombre_provisoire_ser"
    H.remove_zone(nom)
    try:
        zdir, cfg = _zone(nom, "ser", {("03", "shade_tolerance"): 0.5})
        proc = H.run_simulate(nom, cfg)
        assert proc.returncode == 0, H.queue(proc)
        assert "classes_lumiere_et_extinction_provisoires" not in H.flags_kinds(zdir)
        message = _message_ombre(zdir)
        assert "03 (N = 0,5, plage 1,5 à 4,6)" in message, message
        assert "61 (N" not in message, message
    finally:
        H.remove_zone(nom)


@pytest.mark.parametrize("tolerance, attendu_nomme", [(5.0, True), (3.0, False)])
def test_ombre_semis_provisoire_nomme_les_essences_hors_plage_de_n_au_niveau_massif(tolerance, attendu_nomme):
    """Au niveau massif, N = 5 (hors de 1,5 à 4,6) : les essences sont nommées ; N = 3 : aucune."""
    nom = f"m5_ombre_provisoire_massif_{int(tolerance)}"
    H.remove_zone(nom)
    try:
        zdir, cfg = _zone(nom, "massif", {"shade_tolerance": tolerance})
        proc = H.run_simulate(nom, cfg)
        assert proc.returncode == 0, H.queue(proc)
        message = _message_ombre(zdir)
        if attendu_nomme:
            assert "(N = 5, plage 1,5 à 4,6)" in message, message
        else:
            assert "aucune essence présente hors de cette plage" in message and "(N =" not in message, message
    finally:
        H.remove_zone(nom)
