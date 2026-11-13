"""Search for a header nonce whose double SHA-256 is at or below the compact target."""

from __future__ import annotations

import struct

from edu_node import node_constants
from edu_node.compact_target import CompactTarget
from edu_node.double_sha256 import double_sha256
from edu_node.node_constants import HEADER_BYTES, MINE_ERROR


class ProofOfWork:
    """Mine and check 80-byte headers."""

    def mine(self, version: int, previous: bytes, merkle_root: bytes, timestamp: int, bits: int) -> bytes:
        """Return an 80-byte header that meets bits."""
        prefix = struct.pack("<I32s32sII", version, previous, merkle_root, timestamp, bits)
        target = CompactTarget().to_target(bits)
        for nonce in range(node_constants.MAX_MINE_ATTEMPTS):
            header = prefix + struct.pack("<I", nonce)
            if int.from_bytes(double_sha256(header), "little") <= target:
                return header
        raise ValueError(MINE_ERROR)

    def meets(self, header: bytes, bits: int) -> bool:
        """Return whether header is 80 bytes and its hash is at or below bits."""
        if not isinstance(header, bytes) or len(header) != HEADER_BYTES:
            return False
        target = CompactTarget().to_target(bits)
        return int.from_bytes(double_sha256(header), "little") <= target
