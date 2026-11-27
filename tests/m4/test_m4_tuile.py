"""Tuile 3D Tiles 1.1 et contenus glTF (spec §9 ; docs/referentiels/itowns-instancing.md ; contrats tileset)."""
import json

import numpy as np
import pytest

import helpers_m4 as H


@pytest.fixture(scope="module")
def tileset(chaine):
    ts = H.find_tilesets(H.ZONE)
    assert ts, "aucun tiles/<année>/tileset.json"
    return ts[0], json.loads(ts[0].read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def contenus(tileset):
    c = H.walk_tileset(tileset[0])
    assert c, "le tileset ne référence aucun contenu"
    return c


def test_tileset_version_1_1_et_champs_obligatoires(tileset):
    _, ts = tileset
    assert ts["asset"]["version"] == "1.1"
    assert isinstance(ts["geometricError"], (int, float)) and ts["geometricError"] >= 0
    assert "boundingVolume" in ts["root"] and "geometricError" in ts["root"]
    assert ts["root"].get("refine", "ADD") in ("ADD", "REPLACE")


def test_le_tileset_n_utilise_pas_le_pavage_implicite(tileset):
    # Limite déclarée des tests : ils parcourent un arbre explicite (racine, enfants, tilesets externes).
    _, ts = tileset

    def sans_implicite(t):
        assert "implicitTiling" not in t, "pavage implicite : le test de positions ne le parcourt pas"
        for c in t.get("children", []):
            sans_implicite(c)

    sans_implicite(ts["root"])


def test_les_contenus_sont_des_gltf_qui_existent(contenus):
    for c in contenus:
        assert c["uri"].lower().endswith(".gltf"), f"contenu {c['uri']} : .gltf attendu, pas .glb (point A du référentiel iTowns)"
        assert c["path"].is_file(), f"contenu absent : {c['uri']}"
        assert not c["uri"].startswith(("http://", "https://", "/")), f"uri non relative : {c['uri']}"


def test_chaque_tuile_a_un_volume_englobant(contenus):
    for c in contenus:
        assert c["volume"] and any(k in c["volume"] for k in ("box", "sphere", "region")), c["uri"]


def test_gltf_2_0_avec_l_extension_d_instanciation_declaree(contenus):
    for c in contenus:
        g = H.read_gltf(c["path"])
        assert g["asset"]["version"] == "2.0", c["uri"]
        assert H.EXT in g.get("extensionsUsed", []), f"{c['uri']} : {H.EXT} absent de extensionsUsed"
        assert set(g.get("extensionsRequired", [])) <= {H.EXT, "KHR_materials_unlit"}, \
            f"{c['uri']} : extension requise inconnue de three/iTowns : {g.get('extensionsRequired')}"
        assert H.instance_nodes(g), f"{c['uri']} : aucun noeud portant {H.EXT}"


def test_gltf_buffers_vues_et_accesseurs_coherents(contenus):
    for c in contenus:
        g = H.read_gltf(c["path"])
        base = c["path"].parent
        for i, b in enumerate(g["buffers"]):
            assert "uri" in b, f"{c['uri']} : buffer {i} sans uri (un .gltf n'a pas de bloc binaire)"
            data = H._buffer_bytes(g, i, base, {})
            assert len(data) >= b["byteLength"] > 0, f"{c['uri']} : buffer {i} plus court que byteLength"
        for i, v in enumerate(g["bufferViews"]):
            assert v.get("byteOffset", 0) + v["byteLength"] <= g["buffers"][v["buffer"]]["byteLength"], \
                f"{c['uri']} : bufferView {i} hors de son buffer"
        cache = {}
        for i in range(len(g["accessors"])):
            a = H.read_accessor(g, i, base, cache)         # lève si l'accesseur sort du tampon
            assert len(a) == g["accessors"][i]["count"]
        for m in g["meshes"]:
            for p in m["primitives"]:
                pos = g["accessors"][p["attributes"]["POSITION"]]
                assert "min" in pos and "max" in pos, "glTF 2.0 : POSITION doit porter min et max"


def test_les_attributs_d_instance_ont_le_meme_nombre_de_lignes(contenus):
    for c in contenus:
        g = H.read_gltf(c["path"])
        for i, _ in H.instance_nodes(g):
            attrs = g["nodes"][i]["extensions"][H.EXT]["attributes"]
            assert "TRANSLATION" in attrs, f"{c['uri']} : TRANSLATION obligatoire pour placer les arbres"
            counts = {k: g["accessors"][v]["count"] for k, v in attrs.items()}
            assert len(set(counts.values())) == 1, f"{c['uri']} : comptes d'attributs différents : {counts}"
            for k in ("TRANSLATION", "SCALE"):
                if k in attrs:
                    acc = g["accessors"][attrs[k]]
                    assert acc["type"] == "VEC3" and acc["componentType"] == 5126, f"{k} : VEC3 float32 attendu"
            assert "mesh" in g["nodes"][i], f"{c['uri']} : noeud instancié sans maillage"


def test_chaque_tuile_contient_ses_instances_dans_son_volume(chaine, instances):
    inst = instances["inst"]
    m = instances["match"]
    assert len(inst["world"]), "aucune instance"
    frame = m["frame"]
    start = 0
    for c in inst["contents"]:
        g = H.read_gltf(c["path"])
        n = sum(g["accessors"][g["nodes"][i]["extensions"][H.EXT]["attributes"]["TRANSLATION"]]["count"]
                for i, _ in H.instance_nodes(g))
        w = inst["world"][start:start + n]
        start += n
        ok = H.volume_contains(c["volume"], c["matrix"], w, frame)
        assert ok.all(), f"{c['uri']} : {int((~ok).sum())} instances hors du volume englobant de leur tuile"


def test_un_modele_par_classe_essence_stade_pas_par_arbre(chaine, instances, oracle):
    # M6a (mission 069) : un modèle par (essence, stade) quand un exemplaire existe, sinon le générique du groupe
    # (feuillu, résineux). Remplace l'ancienne épingle « feuillu et résineux » : 2 classes sans exemplaires configurés.
    inst, m = instances["inst"], instances["match"]
    ok = m["tree_of"] >= 0
    idx = m["tree_of"][ok]
    cl, franc = H.model_classes(H.ZONE, oracle.trees["species"][idx], oracle.trees["x"][idx], oracle.trees["y"][idx], oracle.trees["h"][idx])
    models = inst["model"][ok]
    classes = set(c for c, f in zip(cl, franc) if f)
    employes = set(models[franc].tolist())
    assert len(classes) >= 2
    assert len(employes) == len(classes), f"{len(employes)} modèles pour {len(classes)} classes (essence, stade) : {sorted(classes)}"
