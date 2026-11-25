"""Module `import_tarif` (spec §2, §3, §4.3) : import de l'allométrie de tarif-nemeton.

Étape visée : état initial, arbres détectés (spec §4.3, BRIEF §12) : le d130 d'un arbre vient de
`ln D = a + b ln H + c ln CPA` (étage B de tarif-nemeton), ou de `ln D = a + b ln H` pour une
essence sans coefficient c. Ce module lit les CSV de résultats de tarif-nemeton (dossier
`external.tarif_nemeton_dir` de config.yml ; rien n'est copié dans le dépôt, aucun code de
tarif-nemeton n'est repris) et écrit `params/allometry.parquet` (modèle `etage_b`, format long
du contrat `import_tarif.allometry`, `provisoire: true`, source citée).

Fichiers lus, sous `<dossier>/resultats/etage_b/` :
- `allometrie_D.csv` : colonnes `essence, a, b_lnH, c_lnCPA, ...` (modèle avec houppier) ;
- `allometrie_D_ifn.csv` : mêmes colonnes, `c_lnCPA` = 0 (modèle sans houppier, calé sur l'IFN).

Règles, dites plutôt que devinées :
- `c_lnCPA` = 0, vide ou absent : pas de terme `c` (le module `trees` prend alors ln D = a + b ln H) ;
- une essence présente dans les deux fichiers garde le jeu de `allometrie_D.csv` (un seul jeu
  a, b, c par essence : mélanger les deux fabriquerait un modèle qu'aucun des deux n'a calé) ;
  le fichier IFN ne sert que pour une essence absente du premier, et le rapport le dit ;
- le code espar vient de `contracts/species.csv`, colonne `tarif_nemeton_code` ; un nom latin
  sans ligne correspondante est signalé et sauté, jamais rattaché à un code par ressemblance ;
- `Quercus_spec` = espar 02 + 03 et rien d'autre (docs/referentiels/species.md, « Règle de
  Quercus_spec ») : les mêmes coefficients sont écrits pour 02 et pour 03, les autres chênes
  n'ont aucun coefficient ; `Betula_spec` = 12P + 12V, de la même façon, comme le fichier le dit.

Source des CSV : https://github.com/pobsteta/tarif-nemeton (dépôt sans licence : seuls des
résultats sont lus ; le commit lu est cité dans la colonne `source`).
Sortie : `data/<zone>/params/allometry.parquet` (jeu fictif : `tests/fixtures/zone_fictive`),
sous la racine `SYLVIGENESE_ROOT` (défaut : dossier courant). Le fichier écrit est validé par
`contracts/validate import_tarif.allometry` avant le code de sortie 0.
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from sylvigenese.commun import (
    SORTIE_IMPOSSIBLE,
    SORTIE_OK,
    ErreurModule,
    appeler_validateur,
    lire_config,
)

NOM = "import_tarif"
MODELE = "etage_b"
URL_DEPOT = "https://github.com/pobsteta/tarif-nemeton"
DOSSIER_RESULTATS = Path("resultats") / "etage_b"
FICHIER_HOUPPIER = "allometrie_D.csv"
FICHIER_IFN = "allometrie_D_ifn.csv"
COLONNES_CSV = ("essence", "a", "b_lnH", "c_lnCPA")

SCHEMA = pa.schema([
    ("species", pa.string()),
    ("species_group", pa.string()),
    ("model", pa.string()),
    ("term", pa.string()),
    ("value", pa.float64()),
    ("provisoire", pa.bool_()),
    ("source", pa.string()),
])


def racine() -> Path:
    return Path(os.environ.get("SYLVIGENESE_ROOT", "."))


def dossier_zone(config: dict) -> Path:
    """Même règle que `prepare_zone_dir` (R) : jeu fictif versionné, sinon data/<zone>."""
    zone = config.get("zone")
    if not zone:
        raise ErreurModule("config.yml : `zone` manquante")
    if zone == "zone_fictive":
        return racine() / "tests" / "fixtures" / "zone_fictive"
    return racine() / "data" / zone


def commit_lu(dossier: Path) -> str | None:
    """Commit (7 caractères) du dépôt tarif-nemeton lu, ou None si `.git` ne le dit pas."""
    git = dossier / ".git"
    try:
        tete = (git / "HEAD").read_text(encoding="utf-8").strip()
        if tete.startswith("ref:"):
            ref = tete.split(":", 1)[1].strip()
            fichier = git / ref
            if fichier.is_file():
                tete = fichier.read_text(encoding="utf-8").strip()
            else:
                tete = next((ligne.split()[0] for ligne in
                             (git / "packed-refs").read_text(encoding="utf-8").splitlines()
                             if ligne.endswith(" " + ref)), "")
    except OSError:
        return None
    return tete[:7] if tete else None


def correspondances_espar(chemin: Path) -> dict[str, list[str]]:
    """`tarif_nemeton_code` -> liste des codes espar (contracts/species.csv), ordre du fichier."""
    if not chemin.is_file():
        raise ErreurModule(f"contracts/species.csv introuvable : {chemin}")
    resultat: dict[str, list[str]] = {}
    with chemin.open(encoding="utf-8", newline="") as flux:
        lecteur = csv.DictReader(flux)
        if not lecteur.fieldnames or not {"espar", "tarif_nemeton_code"} <= set(lecteur.fieldnames):
            raise ErreurModule(f"{chemin} : colonnes espar et tarif_nemeton_code attendues")
        for ligne in lecteur:
            nom = (ligne["tarif_nemeton_code"] or "").strip()
            if nom:
                resultat.setdefault(nom, []).append(ligne["espar"])
    return resultat


def _nombre(texte: str | None, fichier: str, numero: int, colonne: str) -> float | None:
    """Nombre lu, None si la case est vide ; une case illisible est une erreur, pas un zéro."""
    texte = (texte or "").strip()
    if texte == "":
        return None
    try:
        valeur = float(texte)
    except ValueError:
        raise ErreurModule(f"{fichier} ligne {numero} : {colonne} = « {texte} » n'est pas un nombre") from None
    if math.isnan(valeur):
        return None
    if math.isinf(valeur):
        raise ErreurModule(f"{fichier} ligne {numero} : {colonne} = « {texte} » n'est pas fini")
    return valeur


def lire_coefficients(chemin: Path) -> dict[str, dict[str, float | None]]:
    """essence -> {a, b, c} ; c vaut None quand `c_lnCPA` est 0, vide, NA ou la colonne absente."""
    if not chemin.is_file():
        raise ErreurModule(f"fichier de tarif-nemeton introuvable : {chemin}")
    resultat: dict[str, dict[str, float | None]] = {}
    with chemin.open(encoding="utf-8-sig", newline="") as flux:
        lecteur = csv.DictReader(flux)
        manque = [c for c in COLONNES_CSV[:3] if c not in (lecteur.fieldnames or [])]
        if manque:
            raise ErreurModule(f"{chemin.name} : colonne(s) {', '.join(manque)} absente(s)")
        for numero, ligne in enumerate(lecteur, start=2):
            essence = (ligne["essence"] or "").strip()
            if not essence:
                raise ErreurModule(f"{chemin.name} ligne {numero} : essence vide")
            if essence in resultat:
                raise ErreurModule(f"{chemin.name} ligne {numero} : essence {essence} en double")
            a = _nombre(ligne["a"], chemin.name, numero, "a")
            b = _nombre(ligne["b_lnH"], chemin.name, numero, "b_lnH")
            c = _nombre(ligne.get("c_lnCPA"), chemin.name, numero, "c_lnCPA")
            resultat[essence] = {"a": a, "b": b, "c": None if (c is None or c == 0.0) else c}
    return resultat


def construire_lignes(dossier: Path, correspondances: dict[str, list[str]]) -> tuple[list[dict], list[str]]:
    """Lignes du format long, et lignes de rapport (signalements)."""
    resultats = dossier / DOSSIER_RESULTATS
    houppier = lire_coefficients(resultats / FICHIER_HOUPPIER)
    ifn = lire_coefficients(resultats / FICHIER_IFN)
    commit = commit_lu(dossier)
    version = f"commit {commit}" if commit else "commit non lu (dossier sans .git)"
    rapport: list[str] = []
    lignes: list[dict] = []

    jeux: list[tuple[str, str, dict]] = []   # (essence, fichier, coefficients)
    for essence, coef in houppier.items():
        jeux.append((essence, FICHIER_HOUPPIER, coef))
    for essence, coef in ifn.items():
        if essence in houppier:
            rapport.append(f"{essence} : présente dans {FICHIER_HOUPPIER} et {FICHIER_IFN} ; "
                           f"le jeu de {FICHIER_HOUPPIER} est gardé, celui de l'IFN est ignoré")
        else:
            jeux.append((essence, FICHIER_IFN, coef))

    for essence, fichier, coef in jeux:
        if coef["a"] is None or coef["b"] is None:
            rapport.append(f"{essence} ({fichier}) : a ou b manquant, essence sautée (rien n'est deviné)")
            continue
        codes = correspondances.get(essence)
        if not codes:
            rapport.append(f"{essence} ({fichier}) : aucun code espar dans contracts/species.csv "
                           f"(colonne tarif_nemeton_code), essence sautée (rien n'est deviné)")
            continue
        if len(codes) > 1:
            rapport.append(f"{essence} : coefficients écrits pour les espar {', '.join(codes)} "
                           f"(docs/referentiels/species.md : {essence} = ces codes et rien d'autre)")
        if coef["c"] is None:
            rapport.append(f"{essence} ({fichier}) : pas de terme c (c_lnCPA = 0 ou absent) ; "
                           f"ln D = a + b ln H")
        elif coef["c"] < 0:
            rapport.append(f"{essence} ({fichier}) : c = {coef['c']} est négatif (un houppier plus "
                           f"large donnerait un d130 plus petit) ; repris tel quel, à vérifier")
        source = f"tarif-nemeton {DOSSIER_RESULTATS.as_posix()}/{fichier} ({URL_DEPOT}, {version})"
        termes = [("a", coef["a"]), ("b", coef["b"])]
        if coef["c"] is not None:
            termes.append(("c", coef["c"]))
        for espar in codes:
            for terme, valeur in termes:
                lignes.append({"species": espar, "species_group": None, "model": MODELE,
                               "term": terme, "value": float(valeur), "provisoire": True,
                               "source": source})
    if not lignes:
        raise ErreurModule("aucune essence de tarif-nemeton n'a de code espar : rien à écrire")
    lignes.sort(key=lambda r: (r["species"].encode(), r["term"]))
    return lignes, rapport


def ecrire_allometrie(lignes: list[dict], chemin: Path) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    colonnes = {nom: [ligne[nom] for ligne in lignes] for nom in SCHEMA.names}
    pq.write_table(pa.table(colonnes, schema=SCHEMA), chemin)


def importer(config: dict) -> Path:
    """Lit tarif-nemeton, écrit params/allometry.parquet, le fait valider ; rend son chemin."""
    externe = (config.get("external") or {}).get("tarif_nemeton_dir")
    if not externe:
        raise ErreurModule("config.yml : external.tarif_nemeton_dir absent, aucun tarif-nemeton à lire "
                           "(rien n'est inventé)")
    dossier = Path(externe)
    if not dossier.is_dir():
        raise ErreurModule(f"external.tarif_nemeton_dir : dossier introuvable : {dossier}")
    lignes, rapport = construire_lignes(dossier, correspondances_espar(racine() / "contracts" / "species.csv"))
    sortie = dossier_zone(config) / "params" / "allometry.parquet"
    ecrire_allometrie(lignes, sortie)
    for texte in rapport:
        print(f"[{NOM}] {texte}", file=sys.stderr)
    code = appeler_validateur(["import_tarif.allometry", str(sortie)])
    if code != 0:
        raise ErreurModule(f"{sortie} non conforme au contrat import_tarif.allometry (validateur, code {code})")
    especes = sorted({ligne["species"] for ligne in lignes})
    print(f"[{NOM}] {len(lignes)} coefficient(s) etage_b pour {len(especes)} essence(s) "
          f"({', '.join(especes)}), provisoire : {sortie}", file=sys.stderr)
    return sortie


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(prog=NOM, exit_on_error=False)
    analyseur.add_argument("--config", default="config.yml", help="chemin de config.yml")
    try:
        options = analyseur.parse_args(argv)
    except (argparse.ArgumentError, SystemExit):
        return SORTIE_IMPOSSIBLE
    try:
        config = lire_config(options.config)
        code = appeler_validateur(["config", str(options.config)])
        if code != 0:
            raise ErreurModule(f"config.yml non conforme (validateur, code {code})")
        importer(config)
    except ErreurModule as erreur:
        print(f"[{NOM}] erreur : {erreur}", file=sys.stderr)
        return SORTIE_IMPOSSIBLE
    return SORTIE_OK


if __name__ == "__main__":
    sys.exit(main())
