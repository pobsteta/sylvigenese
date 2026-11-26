"""Lecture par lots des grandes tables (mission 065).

Le validateur ne charge plus un Parquet entier : il le lit par lots (`iter_batches`), fichier
par fichier pour une partition Hive, et contrôle la clé unique par hachage 64 bits, paquet par
paquet, avec une vérification exacte des candidats. Ces tests forcent de petits lots
(`tables.BATCH_ROWS`) et de petits paquets (`tables.ROWS_PER_PASS`) pour exercer, sur des
tables de quelques dizaines de lignes, ce qui se passe sur 128 millions de lignes : un doublon
dont les deux lignes sont dans deux lots différents, une erreur au dernier lot, un type faux
dans le dernier fichier d'une partition, une collision de hachage, une lecture qui échoue au
dernier lot. Les valeurs sont celles d'un essai : aucune n'a de sens écologique.
"""
import random
import re

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from validator import cli, parquet_files, tables
from validator.report import Findings

ROWS = 40          # lignes de la table d'essai
GROUP = 8          # lignes par groupe de lignes du Parquet : 5 groupes
BATCH = 8          # lignes par lot de lecture : 5 lots


def run(capsys, argv):
    code = cli.main(argv)
    out = capsys.readouterr()
    return code, out.out + out.err


@pytest.fixture
def petits_lots(monkeypatch):
    """Lots de 8 lignes ; paquets de hachages de 4 lignes : 40 lignes font 5 lots et 16 paquets
    sur disque ; candidats vérifiés 2 par 2."""
    monkeypatch.setattr(tables, "BATCH_ROWS", BATCH)
    monkeypatch.setattr(tables, "ROWS_PER_PASS", 4)
    monkeypatch.setattr(tables, "EXACT_ROWS", 2)


@pytest.fixture
def lots_comptes(monkeypatch):
    """Compte les lots lus et interdit la lecture d'un Parquet d'un seul tenant."""
    seen = []
    original = parquet_files.FileSource.batches

    def batches(self, columns):
        for batch in original(self, columns):
            seen.append(batch.num_rows)
            yield batch

    def refuse_read(*args, **kwargs):
        raise AssertionError("ParquetFile.read appelé : la table serait chargée entière")

    monkeypatch.setattr(parquet_files.FileSource, "batches", batches)
    monkeypatch.setattr(pq.ParquetFile, "read", refuse_read)
    return seen


def cohorts(n=ROWS):
    """cohorts_init conforme : cellules 0, 1, ..., une essence, une classe par ligne."""
    return {"cell_id": list(range(n)), "species": ["09"] * n, "d_class": [0] * n,
            "stems_ha": [10.0] * n, "source": ["synthétique"] * n}


def write(path, columns, *, group=GROUP):
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.table(columns), path, row_group_size=group)
    return path


def test_table_de_plusieurs_groupes_lue_par_lots(tmp_path, capsys, petits_lots, lots_comptes):
    path = write(tmp_path / "cohorts_init.parquet", cohorts())
    assert pq.ParquetFile(path).metadata.num_row_groups == ROWS // GROUP
    code, out = run(capsys, ["cohorts_init", str(path)])
    assert code == 0, out
    assert lots_comptes and max(lots_comptes) <= BATCH
    # une seule lecture : sans hachage vu deux fois, la clé n'est pas relue
    assert len(lots_comptes) == ROWS // BATCH


def test_doublon_dans_deux_lots_differents_est_detecte(tmp_path, capsys, petits_lots, lots_comptes):
    data = cohorts()
    data["cell_id"][ROWS - 1] = 3            # (3, 09, 0) à la ligne 4 (lot 1) et 40 (lot 5)
    path = write(tmp_path / "cohorts_init.parquet", data)
    code, out = run(capsys, ["cohorts_init", str(path)])
    assert code == 3, out
    assert "colonne (cell_id, species, d_class) : 1 doublon(s) ; par exemple « 3, 09, 0 »" in out
    # lecture principale, puis une relecture des colonnes de la clé pour la vérification exacte
    assert len(lots_comptes) == 2 * (ROWS // BATCH)


def test_plusieurs_doublons_comptes_exactement_entre_lots(tmp_path, capsys, petits_lots):
    data = cohorts()
    for i, j in ((0, 39), (9, 17), (25, 33)):  # trois clés en double, toujours sur deux lots
        data["cell_id"][j] = data["cell_id"][i]
    data["cell_id"][38] = 9                    # la clé 9 vue trois fois : un seul doublon
    path = write(tmp_path / "cohorts_init.parquet", data)
    code, out = run(capsys, ["cohorts_init", str(path)])
    assert code == 3 and "3 doublon(s) ; par exemple « 0, 09, 0 »" in out, out


def test_erreur_de_valeur_au_dernier_lot(tmp_path, capsys, petits_lots, lots_comptes):
    data = cohorts()
    data["stems_ha"][ROWS - 1] = float("nan")
    data["d_class"][ROWS - 2] = -1
    path = write(tmp_path / "cohorts_init.parquet", data)
    code, out = run(capsys, ["cohorts_init", str(path)])
    assert code == 3, out
    assert "colonne stems_ha : 1 valeur(s) NaN ou infinies, refusées (valeur invalide) ; " \
           "première à la ligne 40 : « nan »" in out
    assert "colonne d_class : 1 valeur(s) inférieures au minimum 0 ; première à la ligne 39 : « -1 »" in out


def test_erreur_de_type_dans_le_dernier_fichier_de_la_partition(tmp_path, capsys, petits_lots):
    """Dans un Parquet, le type est celui de tout le fichier : le dernier « lot » qui peut porter un
    type faux est le dernier fichier d'une partition. Il est signalé, lui seul."""
    root = tmp_path / "sim" / "cohorts"
    good = {"cell_id": list(range(ROWS)), "species": ["09"] * ROWS, "d_class": [0] * ROWS,
            "stems_ha": [10.0] * ROWS}
    for year in (2030, 2040):
        write(root / f"year={year}" / "part-0.parquet", good)
    bad = dict(good, stems_ha=[str(v) for v in good["stems_ha"]])
    write(root / "year=2050" / "part-0.parquet", bad)
    code, out = run(capsys, ["simulate.cohorts", str(root)])
    assert code == 3, out
    assert out.count("conforme : ") == 2 + 1 and "non conforme" in out
    assert re.search(r"year=2050/part-0\.parquet : contrat simulate\.cohorts : colonne stems_ha : "
                     r"type attendu nombre \(number\), trouvé string", out), out
    assert "year=2030/part-0.parquet (contrat simulate.cohorts)" in out


def test_partition_lue_fichier_par_fichier(tmp_path, capsys, petits_lots, lots_comptes):
    root = tmp_path / "sim" / "cohorts"
    rows = {"cell_id": list(range(ROWS)), "species": ["09"] * ROWS, "d_class": [0] * ROWS,
            "stems_ha": [10.0] * ROWS}
    for year in (2030, 2040):
        write(root / f"year={year}" / "part-0.parquet", rows)
    code, out = run(capsys, ["simulate.cohorts", str(root)])
    assert code == 0, out                      # même clé, deux années : pas un doublon
    assert max(lots_comptes) <= BATCH


def test_collision_de_hachage_ne_cree_pas_de_faux_doublon(tmp_path, capsys, petits_lots, monkeypatch):
    """Toutes les clés ont le même hachage : la vérification exacte les départage."""
    monkeypatch.setattr(tables, "_hash_key", lambda batch, keys: pa.array([7] * batch.num_rows, pa.uint64()))
    path = write(tmp_path / "cohorts_init.parquet", cohorts())
    assert run(capsys, ["cohorts_init", str(path)])[0] == 0
    data = cohorts()
    data["cell_id"][30] = 12
    path = write(tmp_path / "doublon" / "cohorts_init.parquet", data)
    code, out = run(capsys, ["cohorts_init", str(path)])
    assert code == 3 and "1 doublon(s) ; par exemple « 12, 09, 0 »" in out, out


def test_lecture_qui_echoue_au_dernier_lot(tmp_path, capsys, petits_lots, monkeypatch):
    """Une erreur de lecture, même au dernier lot, rend le fichier illisible : un seul message."""
    data = cohorts()
    data["d_class"][0] = -1                    # écart déjà vu avant l'échec : il n'est pas dit
    path = write(tmp_path / "cohorts_init.parquet", data)
    original = pq.ParquetFile.iter_batches

    def iter_batches(self, *args, **kwargs):
        batches = list(original(self, *args, **kwargs))
        yield from batches[:-1]
        raise OSError("lot illisible")

    monkeypatch.setattr(pq.ParquetFile, "iter_batches", iter_batches)
    code, out = run(capsys, ["cohorts_init", str(path)])
    assert code == 3, out
    assert "fichier Parquet illisible (OSError)" in out and "d_class" not in out


SCHEMA = {"fields": [
    {"name": "id", "type": "integer", "constraints": {"unique": True, "minimum": 0}},
    {"name": "a", "type": "string",
     "constraints": {"pattern": "[A-C]{1,2}", "minLength": 1, "enum": ["A", "B", "AB", "CC", ""]}},
    {"name": "b", "type": "integer", "constraints": {"required": True, "maximum": 5}},
    {"name": "v", "type": "number", "constraints": {"exclusiveMinimum": 0}},
    {"name": "x", "type": "number"}, {"name": "y", "type": "number"}],
    "primaryKey": ["a", "b"], "x-require-one-of": ["id", "v"], "x-extent": {"x": "x", "y": "y"}}


def random_table(seed):
    r = random.Random(seed)
    n = r.randint(0, 60)

    def pick(values):
        return [r.choice(values) for _ in range(n)]

    return pa.table({
        "id": pa.array(pick([None, -1, 0, 1, 2, 3, 4, 5] + list(range(100, 160))), pa.int64()),
        "a": pa.array(pick([None, "A", "B", "AB", "CC", "", "Z", "abc"]), pa.string()),
        "b": pa.array(pick([None, 0, 1, 2, 6, 7]), pa.int64()),
        "v": pa.array(pick([None, 0.0, 1.0, -0.0, float("nan"), float("inf"), 2.5]), pa.float64()),
        "x": pa.array(pick([652000.0, 652000.0, 1.0]), pa.float64()),
        "y": pa.array(pick([6862000.0, 6862000.0, 2.0]), pa.float64())})


def brute_force_duplicates(table, keys):
    """Clés en double, comptées à la main (référence) : nombre et première en ordre de lecture."""
    first, count = {}, {}
    for i, row in enumerate(zip(*(table[k].to_pylist() for k in keys))):
        if all(v is None for v in row):
            continue
        first.setdefault(row, i)
        count[row] = count.get(row, 0) + 1
    dup = sorted((first[k], k) for k, c in count.items() if c > 1)
    return len(dup), (dup[0][1] if dup else None)


@pytest.mark.parametrize("seed", range(60))
def test_memes_messages_quelle_que_soit_la_taille_des_lots(seed, tmp_path, monkeypatch):
    """Lots de 7 lignes et paquets de 5 contre une lecture d'un seul tenant : mêmes messages,
    et le nombre de doublons de la clé primaire est celui d'un comptage à la main."""
    table = random_table(seed)
    whole = Findings()
    tables.check_table(SCHEMA, table, whole)
    path = write(tmp_path / "t.parquet", {c: table[c] for c in table.column_names}, group=5)
    monkeypatch.setattr(tables, "BATCH_ROWS", 7)
    monkeypatch.setattr(tables, "ROWS_PER_PASS", 5)
    monkeypatch.setattr(tables, "EXACT_ROWS", 3)
    [(_, batched)] = parquet_files.check(path, SCHEMA, {})
    assert batched.errors == whole.errors
    n, example = brute_force_duplicates(table, ["a", "b"])
    found = [e for e in whole.errors if e.startswith("colonne (a, b) : ")]
    if n:
        shown = ", ".join("(vide)" if v is None else str(v) for v in example)
        assert found == [f"colonne (a, b) : {n} doublon(s) ; par exemple « {shown} »"]
    else:
        assert found == []


def test_nombre_de_passes_borne_la_memoire_des_cles(monkeypatch):
    monkeypatch.setattr(tables, "ROWS_PER_PASS", 1 << 23)
    assert tables._passes_for(0) == 1
    assert tables._passes_for(1 << 23) == 1
    assert tables._passes_for((1 << 23) + 1) == 2
    assert tables._passes_for(128_000_000) == 16     # cohorts_init à N = 4 000 : 8 M par paquet


def test_paquets_temporaires_effaces(tmp_path, capsys, petits_lots, monkeypatch):
    """Les paquets de hachages écrits sur disque sont effacés, conforme ou non."""
    import tempfile
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "tmp"))
    (tmp_path / "tmp").mkdir()
    data = cohorts()
    data["cell_id"][ROWS - 1] = 0
    path = write(tmp_path / "cohorts_init.parquet", data)
    assert run(capsys, ["cohorts_init", str(path)])[0] == 3
    assert list((tmp_path / "tmp").iterdir()) == []


def test_cle_repetee_des_milliers_de_fois(tmp_path, capsys, petits_lots):
    """Une seule clé sur toutes les lignes : un doublon, la mémoire des hachages reste compactée."""
    n = 3000
    data = {"cell_id": [5] * n, "species": ["09"] * n, "d_class": [0] * n,
            "stems_ha": [1.0] * n, "source": ["synthétique"] * n}
    path = write(tmp_path / "cohorts_init.parquet", data, group=500)
    code, out = run(capsys, ["cohorts_init", str(path)])
    assert code == 3 and "1 doublon(s) ; par exemple « 5, 09, 0 »" in out, out
