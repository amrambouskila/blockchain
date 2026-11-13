"""An 80-byte block header: version, previous block, Merkle root, time, bits, and nonce."""

from __future__ import annotations

import struct

from edu_node.node_constants import BLOCK_ERROR, BLOCK_VERSION, HEADER_BYTES


class BlockHeader:
    """One educational block header."""

    def __init__(
        self,
        version: int,
        previous: bytes,
        merkle_root: bytes,
        timestamp: int,
        bits: int,
        nonce: int,
    ) -> None:
        self.version = version
        self.previous = previous
        self.merkle_root = merkle_root
        self.timestamp = timestamp
        self.bits = bits
        self.nonce = nonce

    def serialize(self) -> bytes:
        """Return the 80-byte header."""
        return struct.pack(
            "<I32s32sIII", self.version, self.previous, self.merkle_root, self.timestamp, self.bits, self.nonce
        )

    @classmethod
    def parse(cls, raw: bytes) -> BlockHeader:
        """Return a header when raw is 80 bytes and the version is the one this chain uses."""
        if not isinstance(raw, bytes) or len(raw) != HEADER_BYTES:
            raise ValueError(BLOCK_ERROR)
        version, previous, merkle_root, timestamp, bits, nonce = struct.unpack("<I32s32sIII", raw)
        if version != BLOCK_VERSION:
            raise ValueError(BLOCK_ERROR)
        return cls(version, previous, merkle_root, timestamp, bits, nonce)
