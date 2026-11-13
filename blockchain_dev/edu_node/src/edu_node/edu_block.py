"""A block is an 80-byte header plus the raw transactions it commits to."""

from __future__ import annotations

import struct

from edu_node.block_header import BlockHeader
from edu_node.double_sha256 import double_sha256
from edu_node.edu_transaction import EduTransaction
from edu_node.node_constants import BLOCK_ERROR, HEADER_BYTES, MAX_BLOCK_BYTES, MAX_TX_BYTES, MAX_TX_PER_BLOCK


class EduBlock:
    """One educational block."""

    def __init__(self, header: BlockHeader, transactions: list[EduTransaction]) -> None:
        self.header = header
        self.transactions = transactions

    @property
    def block_id(self) -> bytes:
        """Return the double SHA-256 of the header."""
        return double_sha256(self.header.serialize())

    @property
    def display_id(self) -> str:
        """Return the reversed header hash."""
        return self.block_id[::-1].hex()

    @property
    def raw(self) -> bytes:
        """Return the header, a transaction count, and each transaction with its length."""
        parts = [self.header.serialize(), struct.pack("<H", len(self.transactions))]
        for tx in self.transactions:
            parts.append(struct.pack("<I", len(tx.raw)))
            parts.append(tx.raw)
        raw = b"".join(parts)
        if len(raw) > MAX_BLOCK_BYTES:
            raise ValueError(BLOCK_ERROR)
        return raw

    @classmethod
    def parse(cls, raw: bytes) -> EduBlock:
        """Return a block when the framing and each transaction parse."""
        if not isinstance(raw, bytes) or not HEADER_BYTES < len(raw) <= MAX_BLOCK_BYTES:
            raise ValueError(BLOCK_ERROR)
        header = BlockHeader.parse(raw[:HEADER_BYTES])
        count = int.from_bytes(raw[HEADER_BYTES : HEADER_BYTES + 2], "little")
        if not 1 <= count <= MAX_TX_PER_BLOCK:
            raise ValueError(BLOCK_ERROR)
        cursor = HEADER_BYTES + 2
        transactions: list[EduTransaction] = []
        for _index in range(count):
            if cursor + 4 > len(raw):
                raise ValueError(BLOCK_ERROR)
            length = int.from_bytes(raw[cursor : cursor + 4], "little")
            cursor += 4
            if not 1 <= length <= MAX_TX_BYTES or cursor + length > len(raw):
                raise ValueError(BLOCK_ERROR)
            transactions.append(EduTransaction.parse(raw[cursor : cursor + length]))
            cursor += length
        if cursor != len(raw):
            raise ValueError(BLOCK_ERROR)
        return cls(header, transactions)
