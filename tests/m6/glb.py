"""Analyseur de .glb INDÉPENDANT de contracts/validator/gltf.py et de python/sylvigenese (mission 069).

Il relit un .glb octet par octet (en-tête de 12 octets, blocs JSON puis BIN, accesseurs, vues) avec
numpy et struct, et rend ce que les tests comparent : triangles et sommets par niveau de détail
(extension MSFT_lod : nœud principal = LOD0, `ids` = LOD1 puis LOD2), étendues, extras.
Il lève AssertionError sur un fichier malformé (message en français), jamais une valeur par défaut.
"""
from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

import numpy as np

MAGIC, CHUNK_JSON, CHUNK_BIN = 0x46546C67, 0x4E4F534A, 0x004E4942
COMP = {5120: "i1", 5121: "u1", 5122: "<i2", 5123: "<u2", 5125: "<u4", 5126: "<f4"}
NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


class Glb:
    def __init__(self, path: Path):
        self.path = Path(path)
        data = self.path.read_bytes()
        self.data = data
        assert len(data) >= 20, f"{path} : trop court pour un .glb"
        magic, version, length = struct.unpack_from("<III", data, 0)
        assert magic == MAGIC, f"{path} : nombre magique glTF absent"
        assert version == 2, f"{path} : conteneur version {version}"
        assert length == len(data), f"{path} : longueur déclarée {length}, réelle {len(data)} (tronqué ?)"
        chunks, off = [], 12
        while off < len(data):
            assert off + 8 <= len(data), f"{path} : bloc coupé"
            size, kind = struct.unpack_from("<II", data, off)
            assert off + 8 + size <= len(data), f"{path} : bloc {kind:#x} dépasse le fichier"
            chunks.append((kind, data[off + 8: off + 8 + size]))
            off += 8 + size
            assert size % 4 == 0, f"{path} : bloc non aligné sur 4 octets"
        assert chunks and chunks[0][0] == CHUNK_JSON, f"{path} : le premier bloc doit être JSON"
        self.json = json.loads(chunks[0][1].decode("utf-8").rstrip(" \x00"))
        bins = [b for k, b in chunks[1:] if k == CHUNK_BIN]
        assert len(bins) == 1, f"{path} : un bloc BIN attendu"
        self.bin = bins[0]
        assert self.json["asset"]["version"] == "2.0"

    # ---- accesseurs
    def accessor(self, idx: int) -> np.ndarray:
        acc = self.json["accessors"][idx]
        view = self.json["bufferViews"][acc["bufferView"]]
        assert view.get("buffer", 0) == 0
        dt = np.dtype(COMP[acc["componentType"]])
        nc = NCOMP[acc["type"]]
        start = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
        stride = view.get("byteStride") or dt.itemsize * nc
        n = acc["count"]
        need = start + (n - 1) * stride + dt.itemsize * nc
        assert need <= len(self.bin), f"accessors[{idx}] sort du bloc BIN"
        raw = np.frombuffer(self.bin, dtype="u1")
        rows = np.lib.stride_tricks.as_strided(raw[start:], shape=(n, dt.itemsize * nc), strides=(stride, 1))
        out = np.frombuffer(np.ascontiguousarray(rows).tobytes(), dtype=dt).reshape(n, nc)
        return out if nc > 1 else out.reshape(n)

    def mesh_arrays(self, mesh_idx: int):
        """(positions float32 (N,3), indices uint32 (M,)) concaténés sur les primitives du maillage."""
        pos, idx, base = [], [], 0
        for prim in self.json["meshes"][mesh_idx]["primitives"]:
            assert prim.get("mode", 4) == 4, "triangles attendus"
            p = self.accessor(prim["attributes"]["POSITION"]).astype("<f4")
            i = self.accessor(prim["indices"]).astype("<u4")
            assert i.max() < len(p), "indice hors maillage"
            pos.append(p)
            idx.append(i + base)
            base += len(p)
        return np.vstack(pos), np.concatenate(idx)

    # ---- niveaux de détail (MSFT_lod)
    def lod_nodes(self) -> list[int]:
        nodes = self.json["nodes"]
        lead = [i for i, n in enumerate(nodes) if "MSFT_lod" in (n.get("extensions") or {})]
        assert len(lead) == 1, f"MSFT_lod : {len(lead)} nœuds principaux"
        ids = nodes[lead[0]]["extensions"]["MSFT_lod"]["ids"]
        assert len(ids) == 2, f"MSFT_lod.ids : {ids}"
        assert "MSFT_lod" in self.json.get("extensionsUsed", []), "MSFT_lod absent de extensionsUsed"
        return [lead[0], *ids]

    def lod(self, level: int):
        node = self.json["nodes"][self.lod_nodes()[level]]
        assert "mesh" in node, f"LOD{level} sans maillage"
        return self.mesh_arrays(node["mesh"])

    def triangles(self) -> list[int]:
        return [len(self.lod(k)[1]) // 3 for k in range(3)]

    @property
    def extras(self) -> dict:
        return self.json.get("extras") or {}

    def screencoverage(self):
        return (self.json["nodes"][self.lod_nodes()[0]].get("extras") or {}).get("MSFT_screencoverage")

    def lod2_hash(self) -> str:
        return vertex_hash(self.lod(2)[0])


def vertex_hash(positions: np.ndarray) -> str:
    """Empreinte des sommets (float32 little-endian, ordre du fichier) : sert à comparer deux vues."""
    return hashlib.sha256(np.ascontiguousarray(positions, dtype="<f4").tobytes()).hexdigest()[:16]


def z_up_to_y_up(p):
    """Conversion attendue (plan T6) : (x, y, z) du générateur z-up -> (x, z, -y) de glTF y-up."""
    p = np.asarray(p, dtype=float)
    return np.stack([p[..., 0], p[..., 2], -p[..., 1]], axis=-1)
