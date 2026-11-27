"""Mission 077 (préparation de M6b) : plus aucune constante d'affichage en dur dans les scripts de la vue massif.

Les réglages d'apparence (rayon des blocs voisins, hauteur des yeux, champ de vision, couleur du sol, vitesse de la caméra,
taille et couleur des textes, soleil, case de MultiMesh, bruit du vent) vivent dans le bloc `viewer` de `config.yml`,
marqués provisoires et « illustration, non mesurée », exigés par `contracts/json/config.schema.json`, sans valeur par défaut
dans les scripts : une clé absente arrête la vue en code 3.

Ce test lit les sources GDScript (pas de Godot requis) et échoue si un littéral de ce genre revient. Les seules constantes
numériques admises dans les scripts sont des conventions ou des unités, nommées ici avec la raison.
"""
import re
from pathlib import Path

import pytest
import yaml

import helpers as h
from validator import cli

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = sorted((ROOT / "viewer-massif" / "scripts").glob("*.gd"))

# constantes numériques admises : convention de `assets` (générique de 1 m x 1 m), unité, masque binaire
ALLOWED_CONSTS = {
    "GENERIC_SIZE_M": "convention de assets.models.generic_model (un générique mesure 1 m x 1 m)",
    "GENERIC_TOLERANCE_M": "tolérance de contrôle de cette convention",
    "M2_PER_HA": "unité : 10 000 m2 par hectare",
    "MASK": "masque 32 bits du hachage",
    # proportions du dessin de la flèche du nord (compass.gd, mission 084c) : « illustration, non mesurée », nommées dans le
    # script avec leur raison, sans sens physique ; la taille et les couleurs viennent du bloc viewer.hud de config.yml
    "ARROW_RADIUS_SHARE": "dessin de la flèche du nord : rayon en part de la taille du contrôle (illustration, non mesurée)",
    "ARROW_WING_SPAN": "dessin de la flèche du nord : écart des ailes en part du rayon (illustration, non mesurée)",
    "ARROW_WING_DEPTH": "dessin de la flèche du nord : recul des ailes en part du rayon (illustration, non mesurée)",
    "ARROW_NOTCH_DEPTH": "dessin de la flèche du nord : creux entre les ailes en part du rayon (illustration, non mesurée)",
    "LABEL_FONT_SHARE": "dessin de la flèche du nord : taille du « N » en part du contrôle (illustration, non mesurée)",
    "LABEL_DISTANCE": "dessin de la flèche du nord : distance du « N » en rayons (illustration, non mesurée)",
    "LABEL_BASELINE_SHARE": "dessin de la flèche du nord : ligne de base du « N » en part de sa hauteur (illustration, non mesurée)",
}
# anciens noms de constantes d'affichage : ils ne doivent plus apparaître
RETIRED_NAMES = ["VIEW_RADIUS_M", "EYE_M", "FOV_DEG", "SPEED_M_S", "FAST_FACTOR", "MOUSE_SENS", "CHUNK_M"]
# motifs d'un littéral d'affichage : (motif, ce qu'il attrape)
LITERAL_PATTERNS = [
    (r"^\s*const\s+[A-Z][A-Z0-9_]*\s*(?::\s*\w+\s*)?:?=\s*-?\d", "constante numérique de tête de script"),
    (r"\.(fov|far|near)\s*=\s*-?\d", "champ de vision ou plan de coupe en dur"),
    (r"rotation_degrees\s*=\s*Vector3\(\s*-?\d", "angle du soleil en dur"),
    (r"font_size_override\([^)]*,\s*\d", "taille de texte en dur"),
    (r"add_theme_constant_override\([^)]*,\s*\d", "épaisseur de contour en dur"),
    (r"offset_(left|top|right|bottom)\s*=\s*-?\d", "marge d'écran en dur"),
    (r"\bposition\s*=\s*Vector2\(\s*-?\d", "position de texte en dur"),
    (r"noise\.frequency\s*=\s*-?\d", "fréquence du vent en dur"),
    (r"clampf\([^)]*,\s*-?\d+\.\d+\s*,\s*-?\d", "limite d'inclinaison en dur"),
    (r"\bColor\(\s*-?\d", "couleur en dur"),
    # mission 084c : la garde ne voyait pas les proportions du dessin (compass.gd : r * 0.32, 0.5, 0.7, 0.3, 1.35, / 4.0)
    # (× 0,5 est admis : la moitié, comme / 2.0, est une convention de géométrie, par exemple le demi-côté d'un carré de 1 m)
    (r"\*\s*-?(?!0\.5\b)\d*\.\d+", "proportion décimale en dur (une constante nommée, acceptée dans ALLOWED_CONSTS, ou une clé viewer)"),
    (r"[\w\)\]]\s*/\s*[3-9]\.\d+", "diviseur décimal en dur (une constante nommée, acceptée dans ALLOWED_CONSTS, ou une clé viewer)"),
]
# lignes admises malgré un motif : textures techniques (normale plate, déplacement neutre, mouvement nul) qui ne sont pas de l'apparence
TECHNICAL_COLOR = re.compile(r"\.fill\(Color\(")


def code_lines(path: Path):
    """Lignes de code d'un script : sans commentaires de ligne (## et #) ni contenu des chaînes."""
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = re.sub(r'"(?:[^"\\]|\\.)*"', '""', raw)
        line = line.split("#", 1)[0]
        if line.strip():
            yield number, line


def test_the_scripts_are_found():
    assert len(SCRIPTS) >= 12
    assert {p.name for p in SCRIPTS} >= {"massif_view.gd", "camera_fly.gd", "main.gd", "viewer_config.gd"}


@pytest.mark.parametrize("path", SCRIPTS, ids=lambda p: p.name)
def test_no_display_literal_in_the_scripts(path):
    found = []
    for number, line in code_lines(path):
        for pattern, why in LITERAL_PATTERNS:
            if not re.search(pattern, line):
                continue
            if why == "constante numérique de tête de script":
                name = re.search(r"const\s+([A-Z][A-Z0-9_]*)", line).group(1)
                if name in ALLOWED_CONSTS:
                    continue
            if why == "couleur en dur" and TECHNICAL_COLOR.search(line):
                continue
            found.append(f"{path.name}:{number} : {why} : {line.strip()}")
        for name in RETIRED_NAMES:
            if re.search(rf"\b{name}\b", line):
                found.append(f"{path.name}:{number} : ancienne constante {name}")
    assert not found, "constante d'affichage en dur (à mettre dans le bloc viewer de config.yml) :\n" + "\n".join(found)


def test_the_guard_sees_the_proportions_of_the_compass(tmp_path):
    """Mission 084c : l'ancien compass.gd (r * 0.32, 0.7, 0.3, 0.3, 1.35, / 4.0) passait inaperçu ; le garde le
    voit maintenant, et le compass.gd actuel n'en garde aucun (constantes nommées, ALLOWED_CONSTS)."""
    old = tmp_path / "ancien_compass.gd"
    old.write_text("var base := [Vector2(0.0, -r), Vector2(r * 0.5, r * 0.7), Vector2(0.0, r * 0.3)]\n"
                   "var r := _size_px * 0.32\nvar fs := int(_size_px * 0.3)\n"
                   "var at := Vector2(0.0, -r * 1.35) - Vector2(w / 2.0, -label_size.y / 4.0)\n", encoding="utf-8")
    seen = [why for _, line in code_lines(old) for pattern, why in LITERAL_PATTERNS if re.search(pattern, line)]
    assert len(seen) == 5 and all("en dur" in why for why in seen), seen
    new = ROOT / "viewer-massif" / "scripts" / "compass.gd"
    names = set(re.findall(r"^const\s+([A-Z][A-Z0-9_]*)\s*:=", new.read_text(encoding="utf-8"), re.M))
    assert names == {n for n in ALLOWED_CONSTS if n.startswith(("ARROW_", "LABEL_"))}, names


def test_the_guard_catches_a_returning_literal(tmp_path):
    """Preuve que le garde est discriminant : un script d'essai qui rapporte les anciens littéraux est attrapé."""
    bad = tmp_path / "mauvais.gd"
    bad.write_text("const EYE_M := 1.7\ncamera.fov = 75.0\nconst GENERIC_SIZE_M := 1.0\n"
                   "gm.albedo_color = Color(0.36, 0.33, 0.24)\nimg.fill(Color(0.5, 0.5, 1.0))\n"
                   "top.add_theme_font_size_override(\"font_size\", 22)\n", encoding="utf-8")
    hits = []
    for _, line in code_lines(bad):
        for pattern, why in LITERAL_PATTERNS:
            if re.search(pattern, line):
                if why == "constante numérique de tête de script" and "GENERIC_SIZE_M" in line:
                    continue
                if why == "couleur en dur" and TECHNICAL_COLOR.search(line):
                    continue
                hits.append(why)
    assert sorted(set(hits)) == sorted({"constante numérique de tête de script", "champ de vision ou plan de coupe en dur",
                                       "couleur en dur", "taille de texte en dur"})
    assert len(hits) == 4


def leaves(node, prefix=""):
    for key, value in node.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict) and key != "color_by_group":
            yield from leaves(value, path + ".")
        else:
            yield path


def required_paths():
    text = (ROOT / "viewer-massif" / "scripts" / "viewer_config.gd").read_text(encoding="utf-8")
    block = text.split("const REQUIRED := [", 1)[1].split("]", 1)[0]
    return set(re.findall(r'"([a-z_.0-9]+)"', block))


def test_every_key_of_the_viewer_block_is_required_by_the_view():
    """Une clé du bloc viewer que la vue n'exige pas serait lue avec une valeur de repli : toutes sont exigées."""
    config = yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8"))["viewer"]
    optional = {"foliage.color_by_essence"}
    assert set(leaves(config)) - optional == required_paths()


def test_every_viewer_key_is_in_the_schema_required_lists():
    schema = yaml.safe_load((ROOT / "contracts" / "json" / "config.schema.json").read_text(encoding="utf-8"))
    viewer = schema["properties"]["viewer"]

    def required(node, prefix=""):
        for key in node.get("required", []):
            sub = node["properties"][key]
            if sub.get("type") == "object" and key != "color_by_group":
                yield from required(sub, f"{prefix}{key}.")
            else:
                yield f"{prefix}{key}"
    assert set(required(viewer)) == required_paths()


def test_the_display_values_are_marked_provisional_in_config():
    text = (ROOT / "config.yml").read_text(encoding="utf-8")
    block = text.split("\nviewer:\n", 1)[1]
    assert "provisoire: true" in block and "illustration, non mesurée" in block
    for section in ("view", "camera", "ground", "sun", "hud", "grass", "seedlings", "foliage", "lod"):
        assert re.search(rf"^  {section}:", block, re.M), section
    # chaque section nouvelle de M6b dit « illustration, non mesurée » sur la ligne de sa section
    for section in ("view", "camera", "ground", "sun", "hud"):
        line = re.search(rf"^  {section}:.*$", block, re.M).group(0)
        assert "illustration, non mesurée" in line, section


def config_without(tmp_path, *path):
    config = yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8"))
    node = config["viewer"]
    for key in path[:-1]:
        node = node[key]
    del node[path[-1]]
    return h.write_yaml(Path(tmp_path) / "config.yml", config)


@pytest.mark.parametrize("path", [("view", "radius_m"), ("camera", "eye_height_m"), ("camera", "fov_deg"),
                                  ("camera", "speed_m_s"), ("ground", "color"), ("sun", "elevation_deg"),
                                  ("hud", "title_font_size"), ("grass", "wind_noise_frequency"), ("lod", "chunk_m"),
                                  ("view",), ("camera",), ("ground",), ("sun",), ("hud",)],
                         ids=lambda p: ".".join(p))
def test_a_missing_display_key_is_refused_by_the_config_contract(tmp_path, capsys, path):
    code = cli.main(["config", str(config_without(tmp_path, *path))])
    out = capsys.readouterr()
    assert code == 3, out.out + out.err
    assert path[-1] in out.out + out.err


@pytest.mark.parametrize("mutate, word", [
    (lambda v: v["camera"].update(fov_deg=0), "fov_deg"),
    (lambda v: v["camera"].update(fov_deg=180), "fov_deg"),
    (lambda v: v["camera"].update(eye_height_m=-1), "eye_height_m"),
    (lambda v: v["camera"].update(pitch_limit_rad=3), "pitch_limit_rad"),
    (lambda v: v["ground"].update(color="brun"), "color"),
    (lambda v: v["sun"].update(elevation_deg=120), "elevation_deg"),
    (lambda v: v["hud"].update(title_color="jaune"), "title_color"),
    (lambda v: v["hud"].update(title_font_size=0), "title_font_size"),
    (lambda v: v["lod"].update(chunk_m=0), "chunk_m"),
    (lambda v: v["view"].update(rayon=3), "clé inconnue"),
    (lambda v: v["camera"].update(vitesse=3), "clé inconnue"),
])
def test_a_wrong_display_value_is_refused_by_the_config_contract(tmp_path, capsys, mutate, word):
    config = yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8"))
    mutate(config["viewer"])
    code = cli.main(["config", str(h.write_yaml(Path(tmp_path) / "config.yml", config))])
    out = capsys.readouterr()
    assert code == 3, out.out + out.err
    assert word in out.out + out.err


def test_the_real_config_is_accepted(capsys):
    assert cli.main(["config", str(ROOT / "config.yml")]) == 0
    capsys.readouterr()
