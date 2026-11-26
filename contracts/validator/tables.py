"""Contrôle d'une table Arrow contre un Table Schema v2 (Frictionless), en vectoriel.

Sert au Parquet et aux attributs des GeoPackage (spec §2, ADR 0002). Le CSV passe par
frictionless-py (`csv_files.py`). On ne lit pas le Parquet avec frictionless : il passe par
pandas et ligne par ligne, ce qui ne tient pas les 30 minutes sur `sim/`.

Sous-ensemble pris en charge, et rien d'autre (un contrat qui demande plus est refusé,
code 2, plutôt que d'être contrôlé à moitié) :
- types : string, integer, number, boolean, date ;
- contraintes : required, unique, minLength, pattern, enum, minimum, maximum,
  exclusiveMinimum, exclusiveMaximum ;
- niveau table : fieldsMatch (equal, subset), primaryKey, missingValues ;
- extensions de sylvigenese : x-optional (colonne qui peut manquer), x-extent, x-allow-empty, x-require-one-of,
  x-schema-version, x-geopackage, x-csv.

Règles propres au projet (contracts/README.md) : un nombre NaN ou infini est toujours
refusé ; une table vide est refusée sauf `x-allow-empty: true`.

Lecture par lots (mission 065) : la table n'est jamais chargée entière. Une « source » rend,
à la demande, les lots (`pyarrow.RecordBatch`) des colonnes voulues, dans l'ordre des lignes ;
on peut la relire. Chaque contrôle de valeur cumule, lot après lot, le nombre de lignes en
écart, la première (numérotée sur toute la table) et sa valeur : les messages sont ceux d'une
lecture d'un seul tenant. La clé unique (contrainte `unique`, clé primaire) est contrôlée par
hachage 64 bits des clés, en mémoire bornée (voir `_UniqueCheck`) : les hachages sont répartis
en P paquets selon leurs bits de poids faible, un paquet par passe, et un hachage vu deux fois
est vérifié exactement, sur les vraies valeurs de la clé, par une passe de plus. Une collision
de hachage ne crée donc jamais de faux doublon, et un vrai doublon a toujours deux hachages
égaux : il est détecté à coup sûr.
"""
import shutil
import tempfile
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc

from . import extent
from .report import Refused, show_value

FIELD_KEYS = {"name", "type", "format", "title", "description", "constraints", "example",
              "unit", "x-unit", "x-optional"}
CONSTRAINT_KEYS = {"required", "unique", "minLength", "pattern", "enum", "minimum",
                   "maximum", "exclusiveMinimum", "exclusiveMaximum"}
SCHEMA_KEYS = {"$schema", "fields", "fieldsMatch", "primaryKey", "missingValues", "title",
               "description", "x-schema-version", "x-extent", "x-allow-empty",
               "x-require-one-of", "x-geopackage", "x-csv", "x-names-fixed-by"}
TYPES = {"string", "integer", "number", "boolean", "date"}
TYPE_LABELS = {"string": "chaîne", "integer": "entier", "number": "nombre",
               "boolean": "booléen", "date": "date"}


def check_schema_supported(schema):
    """Refuse (code 2) un contrat qui sort du sous-ensemble pris en charge."""
    unknown = set(schema) - SCHEMA_KEYS
    if unknown:
        raise Refused(f"contrat invalide : propriétés non prises en charge {sorted(unknown)}")
    if schema.get("fieldsMatch", "equal") not in ("equal", "subset"):
        raise Refused("contrat invalide : fieldsMatch doit valoir equal ou subset")
    names = set()
    for field in schema.get("fields", []):
        if set(field) - FIELD_KEYS:
            raise Refused(f"contrat invalide : colonne {field.get('name')} : propriétés "
                          f"non prises en charge {sorted(set(field) - FIELD_KEYS)}")
        if field.get("type") not in TYPES:
            raise Refused(f"contrat invalide : colonne {field.get('name')} : type "
                          f"{field.get('type')} non pris en charge")
        if set(field.get("constraints", {})) - CONSTRAINT_KEYS:
            raise Refused(f"contrat invalide : colonne {field['name']} : contraintes non "
                          f"prises en charge {sorted(set(field['constraints']) - CONSTRAINT_KEYS)}")
        names.add(field["name"])
    for key in schema.get("primaryKey", []):
        if key not in names:
            raise Refused(f"contrat invalide : clé primaire {key} absente des colonnes")


def is_text(arrow_type):
    return (pa.types.is_string(arrow_type) or pa.types.is_large_string(arrow_type)
            or pa.types.is_string_view(arrow_type))


def arrow_type_matches(ts_type, arrow_type):
    if ts_type == "string":
        if pa.types.is_dictionary(arrow_type):
            return is_text(arrow_type.value_type)
        return is_text(arrow_type)
    if ts_type == "integer":
        return pa.types.is_integer(arrow_type)
    if ts_type == "number":
        return pa.types.is_floating(arrow_type)
    if ts_type == "boolean":
        return pa.types.is_boolean(arrow_type)
    if ts_type == "date":
        return pa.types.is_date(arrow_type)
    return False


def check_columns(schema, column_names, findings):
    """Présence des colonnes selon fieldsMatch. Rend les noms des colonnes à contrôler."""
    wanted = [f["name"] for f in schema["fields"]]
    for field in schema["fields"]:
        if field["name"] not in column_names and not field.get("x-optional"):
            findings.error(f"colonne obligatoire absente : {field['name']}")
    if schema.get("fieldsMatch", "equal") == "equal":
        for name in column_names:
            if name not in wanted:
                findings.error(f"colonne inattendue : {name} (absente du contrat)")
    return [n for n in wanted if n in column_names]


# Lignes par lot à la lecture d'un Parquet (environ 50 Mo par lot pour cohorts_init).
BATCH_ROWS = 1 << 20
# Hachages de clé comptés en mémoire à la fois : au-delà, ils sont répartis en P paquets sur
# disque (P puissance de 2), chacun sous ce nombre de lignes (8 octets par hachage, trié).
ROWS_PER_PASS = 1 << 23
# Lignes candidates (hachage vu deux fois) regroupées à la fois sur les vraies valeurs de la clé.
EXACT_ROWS = 1 << 21


class TableSource:
    """Lots d'une table Arrow déjà en mémoire (attributs d'un GeoPackage, tests)."""

    def __init__(self, table):
        self.table = table
        self.num_rows = table.num_rows
        self.column_names = table.column_names
        self.types = {name: table.schema.field(name).type for name in table.column_names}

    def batches(self, columns):
        sub = self.table.select(list(columns))
        return sub.to_batches(max_chunksize=BATCH_ROWS)


class _Hits:
    """Lignes en écart d'un contrôle, cumulées sur les lots : nombre, première, sa valeur."""

    def __init__(self):
        self.count = 0
        self.first_row = None
        self.first_value = None

    def add(self, mask, column, offset):
        mask = pc.fill_null(mask, False)
        n = pc.sum(mask).as_py() or 0
        if not n:
            return
        if self.first_row is None:
            i = pc.index(mask, True).as_py()
            self.first_row = offset + i
            self.first_value = column[i].as_py() if column is not None else None
        self.count += n


def _report(findings, name, hits, what):
    if hits.count:
        findings.error(f"colonne {name} : {hits.count} valeur(s) {what} ; première à la "
                       f"ligne {hits.first_row + 1} : {show_value(hits.first_value)}")


_BOUNDS = (("minimum", pc.less, "inférieures au minimum"),
           ("maximum", pc.greater, "supérieures au maximum"),
           ("exclusiveMinimum", pc.less_equal, "inférieures ou égales au minimum exclusif"),
           ("exclusiveMaximum", pc.greater_equal, "supérieures ou égales au maximum exclusif"))


class _FieldCheck:
    """Contraintes d'une colonne déjà au bon type, cumulées lot par lot."""

    def __init__(self, field):
        self.field = field
        self.cons = field.get("constraints", {})
        self.nan = _Hits()
        self.missing = _Hits()
        self.short = _Hits()
        self.pattern = _Hits()
        self.enum = _Hits()
        self.bounds = {key: _Hits() for key, _, _ in _BOUNDS if key in self.cons}
        self.unique = _UniqueCheck([field["name"]], primary_key=False) if self.cons.get("unique") else None

    def feed(self, column, offset):
        cons = self.cons
        if self.field["type"] == "number":
            self.nan.add(pc.invert(pc.is_finite(column)), column, offset)
        if cons.get("required") and column.null_count:
            self.missing.add(pc.is_null(column), None, offset)
        if "minLength" in cons:
            self.short.add(pc.less(pc.utf8_length(column), cons["minLength"]), column, offset)
        if "pattern" in cons:
            matched = pc.match_substring_regex(column, "^(?:" + cons["pattern"] + ")$")
            self.pattern.add(pc.invert(matched), column, offset)
        if "enum" in cons:
            allowed = pa.array(cons["enum"], type=column.type)
            inside = pc.is_in(column, value_set=allowed)
            outside = pc.and_(pc.invert(inside), pc.is_valid(column))  # NULL : vu par required
            self.enum.add(outside, column, offset)
        for key, op, _ in _BOUNDS:
            if key in cons:
                self.bounds[key].add(op(column, cons[key]), column, offset)

    def report(self, findings):
        name, cons = self.field["name"], self.cons
        _report(findings, name, self.nan, "NaN ou infinies, refusées (valeur invalide)")
        if self.missing.count:
            findings.error(f"colonne {name} : {self.missing.count} valeur(s) manquante(s) alors "
                           f"qu'elle est obligatoire ; première à la ligne {self.missing.first_row + 1}")
        if "minLength" in cons:
            what = "vides" if cons["minLength"] == 1 else f"de moins de {cons['minLength']} caractères"
            _report(findings, name, self.short, what)
        if "pattern" in cons:
            hint = f" ({self.field['description']})" if "description" in self.field else ""
            _report(findings, name, self.pattern,
                    f"qui ne respectent pas le motif attendu {cons['pattern']}{hint}")
        if "enum" in cons:
            _report(findings, name, self.enum,
                    "hors de la liste fermée (" + ", ".join(map(str, cons["enum"])) + ")")
        for key, _, word in _BOUNDS:
            if key in cons:
                _report(findings, name, self.bounds[key], f"{word} {cons[key]}")
        if self.unique is not None:
            self.unique.report(findings)


# ------------------------------------------------------------------ clé unique, par hachage

_U64 = pa.uint64()
_SHIFTS = {k: pa.scalar(k, _U64) for k in (27, 30, 31)}
_MIX1 = pa.scalar(0xBF58476D1CE4E5B9, _U64)
_MIX2 = pa.scalar(0x94D049BB133111EB, _U64)
_PRIME = pa.scalar(0x100000001B3, _U64)
_SEED = pa.scalar(0xCBF29CE484222325, _U64)
_NULL_WORD = pa.scalar(0x5A17C0DE5A17C0DE, _U64)


def _mix(x):
    """Brassage 64 bits (finaliseur de splitmix64), arithmétique modulo 2^64."""
    x = pc.bit_wise_xor(x, pc.shift_right(x, _SHIFTS[30]))
    x = pc.multiply(x, _MIX1)
    x = pc.bit_wise_xor(x, pc.shift_right(x, _SHIFTS[27]))
    x = pc.multiply(x, _MIX2)
    return pc.bit_wise_xor(x, pc.shift_right(x, _SHIFTS[31]))


def _column_words(column):
    """Un mot de 64 bits par valeur ; une valeur nulle a son mot fixe.

    Deux valeurs égales ont toujours le même mot (c'est tout ce qu'exige l'exactitude) ; deux
    valeurs différentes peuvent en partager un : la vérification exacte les départage.
    """
    column = _text_as_string(column)
    t = column.type
    if pa.types.is_string(t):
        encoded = pc.dictionary_encode(column)
        # hash() de Python sur les valeurs distinctes du lot : stable dans un même processus,
        # ce qui suffit, tout le contrôle d'un fichier ayant lieu dans le même processus.
        words = pa.array([hash(v) & 0xFFFFFFFFFFFFFFFF for v in encoded.dictionary.to_pylist()],
                         type=_U64)
        values = pc.take(words, encoded.indices)
    elif pa.types.is_floating(t):
        values = pc.add(pc.cast(column, pa.float64()), 0.0).view(_U64)  # -0 et +0 confondus
    elif pa.types.is_date32(t):
        values = pc.cast(pc.cast(column, pa.int32()), _U64, safe=False)
    elif pa.types.is_date64(t):
        values = pc.cast(pc.cast(column, pa.int64()), _U64, safe=False)
    elif pa.types.is_boolean(t):
        values = pc.cast(pc.cast(column, pa.uint8()), _U64)
    else:
        values = pc.cast(column, _U64, safe=False)
    return pc.fill_null(values, _NULL_WORD)


def _key_hash(batch, keys):
    """Hachage 64 bits de la clé (composée) de chaque ligne d'un lot : FNV-1a sur des mots de
    64 bits, puis brassage final."""
    h = None
    for k in keys:
        words = _column_words(batch.column(k))
        h = pc.multiply(pc.bit_wise_xor(_SEED if h is None else h, words), _PRIME)
    return _mix(h)


def _hash_key(batch, keys):
    """Point d'entrée du hachage (remplaçable par les tests pour forcer des collisions)."""
    return _key_hash(batch, keys)


def _passes_for(num_rows):
    """Nombre P de paquets de hachages (puissance de 2) : chacun sous ROWS_PER_PASS lignes."""
    passes = 1
    while num_rows > passes * ROWS_PER_PASS:
        passes *= 2
    return passes


class _Scratch:
    """Dossier temporaire des paquets de hachages, créé à la demande, toujours effacé."""

    def __init__(self):
        self.path = None

    def file(self, name):
        if self.path is None:
            self.path = Path(tempfile.mkdtemp(prefix="sylvigenese-validate-"))
        return self.path / name

    def cleanup(self):
        if self.path is not None:
            shutil.rmtree(self.path, ignore_errors=True)
            self.path = None


class _HashCounter:
    """Hachages d'un paquet : ceux déjà vus (triés, sans répétition) et ceux vus deux fois.

    Compacté par tri dès que ROWS_PER_PASS hachages attendent : la mémoire suit le nombre de
    hachages distincts du paquet, même si une clé se répète des millions de fois.
    """

    def __init__(self):
        self.seen = None
        self.twice = []
        self.pending = []
        self.pending_rows = 0

    def add(self, h):
        if len(h):
            self.pending.append(h)
            self.pending_rows += len(h)
            if self.pending_rows >= ROWS_PER_PASS:
                self._compact()

    def _compact(self):
        parts = self.pending + ([self.seen] if self.seen is not None else [])
        self.pending, self.pending_rows = [], 0
        if not parts:
            return
        h = pa.concat_arrays(parts) if len(parts) > 1 else parts[0]
        del parts
        h = h.take(pc.sort_indices(h))
        if len(h) > 1:
            same = pc.equal(h.slice(1), h.slice(0, len(h) - 1))
            repeated = h.slice(1).filter(same)
            if len(repeated):
                self.twice.append(pc.unique(repeated))
            h = h.filter(pa.concat_arrays([pa.array([True]), pc.invert(same)]))
        self.seen = h

    def duplicates(self):
        """Hachages vus au moins deux fois (tableau, éventuellement vide)."""
        self._compact()
        self.seen = None
        if not self.twice:
            return pa.array([], type=_U64)
        return pc.unique(pa.concat_arrays(self.twice))


class _UniqueCheck:
    """Doublons sur une colonne ou une clé composée, en mémoire bornée.

    Contrainte `unique` d'une colonne : les valeurs nulles sont ignorées.
    Clé primaire (`primary_key=True`) : une valeur nulle est une valeur comme une autre dans le
    couple, donc (H10, nul) en double est refusé ; une ligne dont toutes les colonnes de la clé
    sont nulles est refusée, car elle n'identifie rien (comportement de Frictionless, qui
    sert de référence à Table Schema).

    Méthode (mission 065) : pendant la lecture principale, chaque ligne retenue reçoit un
    hachage 64 bits de sa clé. Au-delà de ROWS_PER_PASS lignes, les hachages sont répartis en
    P paquets (bits de poids faible) écrits dans un dossier temporaire (8 octets par ligne),
    puis chaque paquet est relu seul et compté par tri (`_HashCounter`). Un hachage vu au moins
    deux fois désigne des lignes candidates : une relecture des seules colonnes de la clé les
    regroupe sur les vraies valeurs (regroupement d'Arrow), par tranches d'au plus EXACT_ROWS
    candidats. Seuls les vrais doublons sont comptés, avec la première ligne de chacun ; une
    collision de hachage ne crée pas de faux doublon, et deux lignes de même clé ont toujours le
    même hachage : un doublon est détecté à coup sûr. Une table sans doublon n'est lue qu'une fois.
    """

    def __init__(self, keys, *, primary_key):
        self.keys = list(keys)
        self.primary_key = primary_key
        self.label = keys[0] if len(keys) == 1 else "(" + ", ".join(keys) + ")"
        self.empty = _Hits()
        self.duplicates = 0
        self.example = None          # (première ligne, valeurs de la clé)

    def _kept(self, batch):
        """Masque des lignes dont la clé compte."""
        cols = [batch.column(k) for k in self.keys]
        if self.primary_key:
            empty = None
            for col in cols:
                n = pc.is_null(col)
                empty = n if empty is None else pc.and_(empty, n)
            return pc.invert(empty)
        valid = None
        for col in cols:
            v = pc.is_valid(col)
            valid = v if valid is None else pc.and_(valid, v)
        return valid

    def feed_empty(self, batch, offset):
        if self.primary_key:
            self.empty.add(pc.invert(self._kept(batch)), None, offset)

    # -- lecture principale : hachages, en mémoire ou par paquets sur disque

    def start(self, num_rows, scratch, tag):
        self.passes = _passes_for(num_rows)
        self.counter = _HashCounter() if self.passes == 1 else None
        self.writers = []
        if self.passes > 1:
            schema = pa.schema([("h", _U64)])
            for b in range(self.passes):
                sink = pa.OSFile(str(scratch.file(f"{tag}-{b}.arrows")), "wb")
                self.writers.append((sink, pa.ipc.new_stream(sink, schema)))
        self._paths = [scratch.file(f"{tag}-{b}.arrows") for b in range(self.passes)] \
            if self.passes > 1 else []

    def feed_hashes(self, batch):
        h = _hash_key(batch, self.keys).filter(pc.fill_null(self._kept(batch), False))
        if self.passes == 1:
            self.counter.add(h)
            return
        low = pc.bit_wise_and(h, pa.scalar(self.passes - 1, _U64))
        for b, (_, writer) in enumerate(self.writers):
            part = h.filter(pc.equal(low, pa.scalar(b, _U64)))
            if len(part):
                writer.write_batch(pa.record_batch([part], names=["h"]))

    def candidate_sets(self):
        """Hachages vus au moins deux fois, paquet après paquet."""
        if self.passes == 1:
            yield self.counter.duplicates()
            self.counter = None
            return
        for sink, writer in self.writers:
            writer.close()
            sink.close()
        self.writers = []
        for path in self._paths:
            counter = _HashCounter()
            with pa.OSFile(str(path), "rb") as f:
                for batch in pa.ipc.open_stream(f):
                    counter.add(batch.column(0))
            path.unlink()
            yield counter.duplicates()

    # -- vérification exacte des candidats

    def exact(self, source, candidates):
        """Regroupe sur les vraies valeurs les lignes dont le hachage est candidat."""
        groups, pending, pending_rows = None, [], 0
        offset = 0
        for batch in source.batches(self.keys):
            h = _hash_key(batch, self.keys)
            mask = pc.and_(self._kept(batch), pc.is_in(h, value_set=candidates))
            rows = pc.indices_nonzero(pc.fill_null(mask, False))
            if len(rows):
                cols = [_text_as_string(batch.column(k)).take(rows) for k in self.keys]
                cols.append(pc.add(pc.cast(rows, pa.int64()), offset))
                pending.append(pa.record_batch(cols, names=self.keys + ["__row"]))
                pending_rows += len(rows)
                if pending_rows >= EXACT_ROWS:
                    groups = self._merge(groups, pending)
                    pending, pending_rows = [], 0
            offset += batch.num_rows
        groups = self._merge(groups, pending)
        if groups is None:
            return
        dup = groups.filter(pc.greater(groups["n"], 1))
        if not dup.num_rows:
            return
        self.duplicates += dup.num_rows
        i = pc.index(dup["__row"], pc.min(dup["__row"])).as_py()
        first = dup["__row"][i].as_py()
        if self.example is None or first < self.example[0]:
            self.example = (first, [dup[k][i].as_py() for k in self.keys])

    def _merge(self, groups, pending):
        parts = []
        if pending:
            fresh = pa.Table.from_batches(pending)
            parts.append(fresh.group_by(self.keys, use_threads=False)
                         .aggregate([([], "count_all"), ("__row", "min")])
                         .rename_columns({"count_all": "n", "__row_min": "__row"})
                         .select(self.keys + ["n", "__row"]))
        if groups is not None:
            parts.append(groups)
        if not parts:
            return None
        if len(parts) == 1:
            return parts[0]
        return (pa.concat_tables(parts).group_by(self.keys, use_threads=False)
                .aggregate([("n", "sum"), ("__row", "min")])
                .rename_columns({"n_sum": "n", "__row_min": "__row"})
                .select(self.keys + ["n", "__row"]))

    def report(self, findings):
        if self.primary_key and self.empty.count:
            findings.error(f"clé primaire {self.label} : {self.empty.count} ligne(s) dont la clé "
                           f"est entièrement nulle ; première à la ligne {self.empty.first_row + 1}")
        if self.duplicates:
            example = ", ".join("(vide)" if v is None else str(v) for v in self.example[1])
            findings.error(f"colonne {self.label} : {self.duplicates} doublon(s) ; par exemple "
                           f"{show_value(example)}")


def _needs_decoding(arrow_type):
    if pa.types.is_dictionary(arrow_type):
        return is_text(arrow_type.value_type)
    return is_text(arrow_type) and not pa.types.is_string(arrow_type)


def _text_as_string(column):
    """Chaînes (dictionnaire, string_view, large_string) décodées en `string`."""
    return pc.cast(column, pa.string()) if _needs_decoding(column.type) else column


def _cast_text(batch):
    """Lot dont les colonnes de chaînes sont décodées en `string`."""
    if not any(_needs_decoding(c.type) for c in batch.columns):
        return batch
    return pa.RecordBatch.from_arrays([_text_as_string(c) for c in batch.columns],
                                      names=batch.schema.names)


def _finish_unique(checks, source):
    """Après la lecture principale : candidats de chaque paquet, puis vérification exacte par
    tranches d'au plus EXACT_ROWS hachages candidats (aucune relecture s'il n'y en a pas)."""
    for c in checks:
        chunk, size = [], 0
        for candidates in c.candidate_sets():
            if len(candidates):
                chunk.append(candidates)
                size += len(candidates)
            if size >= EXACT_ROWS:
                c.exact(source, pa.concat_arrays(chunk))
                chunk, size = [], 0
        if chunk:
            c.exact(source, pa.concat_arrays(chunk))


def _single_pass_unique(check, source, *, with_empty):
    scratch = _Scratch()
    try:
        check.start(source.num_rows, scratch, "u")
        offset = 0
        for batch in source.batches(check.keys):
            batch = _cast_text(batch)
            if with_empty:
                check.feed_empty(batch, offset)
            check.feed_hashes(batch)
            offset += batch.num_rows
        _finish_unique([check], source)
    finally:
        scratch.cleanup()


# ------------------------------------------------------------------------- contrôle complet

def check_field_values(field, column, findings):
    """Contraintes d'une colonne déjà au bon type (colonne entière en mémoire)."""
    if isinstance(column, pa.ChunkedArray):
        column = column.combine_chunks()
    check = _FieldCheck(field)
    source = TableSource(pa.table({field["name"]: column}))
    offset = 0
    for batch in source.batches([field["name"]]):
        check.feed(batch.column(0), offset)
        offset += batch.num_rows
    if check.unique is not None:
        _single_pass_unique(check.unique, source, with_empty=False)
    check.report(findings)


def check_unique(findings, keys, table, *, primary_key=False):
    """Doublons sur une colonne ou une clé composée d'une table en mémoire (voir _UniqueCheck)."""
    check = _UniqueCheck(keys, primary_key=primary_key)
    _single_pass_unique(check, TableSource(table), with_empty=True)
    check.report(findings)


def check_table(schema, table, findings, *, skip=()):
    """Contrôle complet d'une table Arrow en mémoire. `skip` : colonnes déjà signalées au type."""
    return check_source(schema, TableSource(table), findings, skip=skip)


def check_source(schema, source, findings, *, skip=()):
    """Contrôle complet d'une table lue par lots depuis `source` (TableSource, ou les lots d'un
    Parquet : `parquet_files.FileSource`). Mêmes contrôles et mêmes messages que sur une table
    d'un seul tenant. Rend les noms des colonnes au bon type."""
    check_schema_supported(schema)
    present = check_columns(schema, source.column_names, findings)
    fields = {f["name"]: f for f in schema["fields"]}
    good, steps = [], []
    for name in present:
        if name in skip:
            continue
        field = fields[name]
        arrow_type = source.types[name]
        if not arrow_type_matches(field["type"], arrow_type):
            steps.append(f"colonne {name} : type attendu {TYPE_LABELS[field['type']]} "
                         f"({field['type']}), trouvé {arrow_type}")
            continue
        good.append(name)
        steps.append(_FieldCheck(field))
    field_checks = [s for s in steps if isinstance(s, _FieldCheck)]
    unique_checks = [c.unique for c in field_checks if c.unique is not None]

    keys = schema.get("primaryKey", [])
    kc = fields[keys[0]].get("constraints", {}) if len(keys) == 1 else {}
    already_unique = bool(kc.get("unique") and kc.get("required"))
    pk = None
    if keys and all(k in good for k in keys) and not already_unique:
        pk = _UniqueCheck(keys, primary_key=True)
        unique_checks.append(pk)
    one_of = schema.get("x-require-one-of")
    one_of = one_of if one_of and all(k in good for k in one_of) else None
    none_of = _Hits()
    xy = schema.get("x-extent")
    xy = xy if xy and xy["x"] in good and xy["y"] in good else None
    outside = _Hits()

    # Lecture principale : toutes les colonnes au bon type, lot par lot ; hachages des clés.
    scratch = _Scratch()
    try:
        for i, c in enumerate(unique_checks):
            c.start(source.num_rows, scratch, f"k{i}")
        if good:
            offset = 0
            for batch in source.batches(good):
                batch = _cast_text(batch)
                for check in field_checks:
                    check.feed(batch.column(check.field["name"]), offset)
                for c in unique_checks:
                    c.feed_hashes(batch)
                if pk is not None:
                    pk.feed_empty(batch, offset)
                if one_of:
                    none = None
                    for k in one_of:
                        col = pc.is_null(batch.column(k))
                        none = col if none is None else pc.and_(none, col)
                    none_of.add(none, None, offset)
                if xy:
                    _feed_extent(outside, batch.column(xy["x"]), batch.column(xy["y"]), offset)
                offset += batch.num_rows
        _finish_unique(unique_checks, source)
    finally:
        scratch.cleanup()

    # Messages, dans l'ordre d'une lecture d'un seul tenant.
    for step in steps:
        if isinstance(step, str):
            findings.error(step)
        else:
            step.report(findings)
    if source.num_rows == 0 and not schema.get("x-allow-empty", False):
        findings.error("table vide : au moins une ligne attendue")
    if pk is not None:
        pk.report(findings)
    if none_of.count:
        findings.error(f"colonnes {', '.join(one_of)} : {none_of.count} ligne(s) sans aucune "
                       f"valeur alors qu'au moins une est obligatoire ; première à la "
                       f"ligne {none_of.first_row + 1}")
    if outside.count:
        x, y = outside.first_value
        problem = extent.point_problem(x, y)
        findings.error(f"{outside.count} ligne(s) {problem.replace('coordonnées ', 'aux coordonnées ', 1)} ; "
                       f"première à la ligne {outside.first_row + 1}")
    return good


def _feed_extent(hits, xs, ys, offset):
    """Coordonnées (x, y) hors de l'emprise du Lambert-93, cumulées lot par lot."""
    e = extent.load_extent()
    xs = pc.cast(xs, pa.float64())
    ys = pc.cast(ys, pa.float64())
    outside = pc.or_(
        pc.or_(pc.less(xs, e["x_min"]), pc.greater(xs, e["x_max"])),
        pc.or_(pc.less(ys, e["y_min"]), pc.greater(ys, e["y_max"])))
    before = hits.first_row
    hits.add(outside, None, offset)
    if before is None and hits.first_row is not None:
        i = hits.first_row - offset
        hits.first_value = (xs[i].as_py(), ys[i].as_py())


def check_extent(xs, ys, findings):
    """Toutes les coordonnées (x, y) dans l'emprise du Lambert-93 (colonnes en mémoire)."""
    hits = _Hits()
    if isinstance(xs, pa.ChunkedArray):
        xs, ys = xs.combine_chunks(), ys.combine_chunks()
    _feed_extent(hits, xs, ys, 0)
    if hits.count:
        x, y = hits.first_value
        problem = extent.point_problem(x, y)
        findings.error(f"{hits.count} ligne(s) {problem.replace('coordonnées ', 'aux coordonnées ', 1)} ; "
                       f"première à la ligne {hits.first_row + 1}")
