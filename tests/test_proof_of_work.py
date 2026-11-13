"""Proof of work finds a nonce at genesis difficulty and reports a miss."""

from __future__ import annotations

import struct

import pytest

from edu_node import node_constants
from edu_node.compact_target import CompactTarget
from edu_node.double_sha256 import double_sha256
from edu_node.node_constants import BLOCK_VERSION, GENESIS_BITS, HASH_BYTES, MINE_ERROR
from edu_node.proof_of_work import ProofOfWork


def test_mined_header_meets_its_target() -> None:
    """A mined header is 80 bytes and its hash is at or below the target."""
    header = ProofOfWork().mine(BLOCK_VERSION, b"\x01" * HASH_BYTES, b"\x02" * HASH_BYTES, 1_700_000_000, GENESIS_BITS)
    assert ProofOfWork().meets(header, GENESIS_BITS) is True
    hashed = int.from_bytes(double_sha256(header), "little")
    assert CompactTarget().to_target(GENESIS_BITS) >= hashed


def test_mine_stops_when_the_attempt_cap_is_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """No attempts means the search fails immediately."""
    monkeypatch.setattr(node_constants, "MAX_MINE_ATTEMPTS", 0)
    with pytest.raises(ValueError, match=MINE_ERROR):
        ProofOfWork().mine(BLOCK_VERSION, b"\x01" * HASH_BYTES, b"\x02" * HASH_BYTES, 1, GENESIS_BITS)


def test_short_header_does_not_meet() -> None:
    """A header that is not 80 bytes is not proof of work."""
    assert ProofOfWork().meets(b"\x00", GENESIS_BITS) is False
    assert ProofOfWork().meets("00", GENESIS_BITS) is False  # type: ignore[arg-type]  # a header is bytes
    unmet = struct.pack("<I32s32sIII", BLOCK_VERSION, bytes(HASH_BYTES), bytes(HASH_BYTES), 1, GENESIS_BITS, 0)
    if ProofOfWork().meets(unmet, GENESIS_BITS):
        unmet = unmet[:-4] + struct.pack("<I", 1)
    assert ProofOfWork().meets(unmet, GENESIS_BITS) is False
