"""Merkle root of transaction ids, duplicating the last leaf when a row is odd."""

from __future__ import annotations

from edu_node.double_sha256 import double_sha256
from edu_node.node_constants import BLOCK_ERROR, HASH_BYTES


class MerkleTree:
    """Build a Merkle root from 32-byte transaction ids."""

    def root(self, leaves: list[bytes]) -> bytes:
        """Return the Merkle root. One leaf is its own root."""
        if not isinstance(leaves, list) or len(leaves) == 0:
            raise ValueError(BLOCK_ERROR)
        level: list[bytes] = []
        for leaf in leaves:
            if not isinstance(leaf, bytes) or len(leaf) != HASH_BYTES:
                raise ValueError(BLOCK_ERROR)
            level.append(leaf)
        while len(level) > 1:
            if len(level) % 2 == 1:
                level.append(level[-1])
            level = [double_sha256(level[index] + level[index + 1]) for index in range(0, len(level), 2)]
        return level[0]
