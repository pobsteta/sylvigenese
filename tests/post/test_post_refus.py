"""Refus de post (plan T8 ; « signaler plutôt que deviner ») : params/tarif absent, modèle manquant, sim/ absent,
run.json absent ou d'une autre config, essence hors référentiel, tree_id en double. Code 2 quand le plan le fixe ;
message qui nomme la cause ; aucune sortie publiée (écriture dans sim/.post_en_cours puis publication)."""
import helpers_post as P


def test_refus(refus):
    p, code = refus["proc"], refus["code"]
    if code is None:
        assert p.returncode != 0, f"{refus['cas']} : post a accepté ({P.queue(p)})"
    else:
        assert p.returncode == code, f"{refus['cas']} : code {p.returncode}, attendu {code}\n{P.queue(p)}"
    msg = P.sans_accent(p.stdout + p.stderr)
    assert any(P.sans_accent(m) in msg for m in refus["mots"]), \
        f"{refus['cas']} : le message ne nomme pas la cause ({refus['mots']}) :\n{P.queue(p)}"
    for rel in P.POST_OUTPUTS:
        assert not (refus["dir"] / rel).exists(), f"{refus['cas']} : {rel} publié malgré le refus"
    assert "Traceback" not in p.stderr, f"{refus['cas']} : trace Python au lieu d'un message\n{p.stderr[-1500:]}"
