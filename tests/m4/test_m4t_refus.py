"""Suite de M4a (mission 045) : refus de assets quand sim/ existe (plan T6, contrat config.assets ; CLAUDE.md :
« signaler plutôt que deviner »). Code 2 pour : run.json absent, partition retenue absente, bloc simulate différent
de run.json (graine, t0, years), bloc assets absent ou faux, h_dom_m absent de sim/cells. Aucun refus n'écrit de
tuile, d'index, de fiche ni de carte ; un refus laisse intactes les sorties précédentes (écriture atomique)."""
import helpers_m4_temps as T


def test_assets_refuse_avec_le_code_attendu_et_nomme_la_cause(refus_temps, temps):
    # Un refus ne prouve quelque chose que si le cas nominal passe : sinon un assets qui refuse tout serait vert.
    T.exige_temps(temps)
    r = refus_temps
    p = r["proc"]
    if r["code"] is None:
        assert p.returncode != 0, f"{r['cas']} : assets aurait dû refuser :\n" + T.queue(p)
    else:
        assert p.returncode == r["code"], f"{r['cas']} : code {p.returncode}, {r['code']} attendu :\n" + T.queue(p)
    texte = (p.stderr + p.stdout).lower()
    assert any(m.lower() in texte for m in r["mots"]), f"{r['cas']} : message sans aucun des mots {r['mots']} :\n" + T.queue(p)


def test_un_refus_n_ecrit_ni_tuile_ni_index_ni_fiche_ni_carte(refus_temps, temps):
    T.exige_temps(temps)
    d = refus_temps["dir"]
    ecrit = [str(p.relative_to(d)) for p in
             list((d / "tiles").rglob("tileset.json")) + list((d / "tiles").glob("index.json")) +
             list((d / "web" / "cells").glob("*.json")) + list((d / "web" / "rasters").glob("g_*.tif"))]
    assert not ecrit, f"{refus_temps['cas']} : écrit malgré le refus : {ecrit[:4]}"


def test_un_refus_ne_touche_pas_a_sim(refus_temps, temps):
    T.exige_temps(temps)
    # assets lit sim/, il ne l'écrit jamais (les modules ne se parlent que par fichiers).
    d = refus_temps["dir"]
    assert not (d / "sim" / ".en_cours").exists()
    assert sorted(p.name for p in (d / "sim").iterdir()) == sorted(p.name for p in (temps["dir"] / "sim").iterdir()) or \
        refus_temps["cas"] == "run_json_absent"


def test_un_refus_laisse_les_sorties_precedentes_intactes(refus_atomique):
    r = refus_atomique
    assert r["proc"].returncode == 2, "partition retenue absente : code 2 attendu\n" + T.queue(r["proc"])
    assert r["avant"], "aucune sortie précédente : test sans pouvoir"
    diff = sorted(k for k in set(r["avant"]) | set(r["apres"]) if r["avant"].get(k) != r["apres"].get(k))
    assert not diff, f"le refus a modifié ou retiré des sorties valides : {diff[:5]}"
    assert not list(r["dir"].rglob(".en_cours")), "dossier .en_cours resté après le refus"
