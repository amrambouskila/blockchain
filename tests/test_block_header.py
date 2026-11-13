"""80-byte headers round-trip, and a bad length or version does not."""

from __future__ import annotations

import pytest

from edu_node.block_header import BlockHeader
from edu_node.node_constants import BLOCK_ERROR, BLOCK_VERSION, HASH_BYTES


def test_header_round_trip() -> None:
    """Serialize and parse return the same six fields."""
    header = BlockHeader(BLOCK_VERSION, b"\x02" * HASH_BYTES, b"\x03" * HASH_BYTES, 10, 20, 30)
    parsed = BlockHeader.parse(header.serialize())
    assert parsed.version == BLOCK_VERSION
    assert parsed.previous == header.previous
    assert parsed.merkle_root == header.merkle_root
    assert parsed.timestamp == 10
    assert parsed.bits == 20
    assert parsed.nonce == 30


@pytest.mark.parametrize("raw", [b"", b"\x00" * 79, b"\x00" * 81, "00" * 80])
def test_header_length_is_rejected(raw: bytes) -> None:
    """Only an 80-byte header parses."""
    with pytest.raises(ValueError, match=BLOCK_ERROR):
        BlockHeader.parse(raw)  # type: ignore[arg-type]  # a header is bytes


def test_header_version_is_rejected() -> None:
    """A different version byte is not this chain's header."""
    raw = BlockHeader(BLOCK_VERSION, b"\x02" * HASH_BYTES, b"\x03" * HASH_BYTES, 10, 20, 30).serialize()
    broken = b"\x02\x00\x00\x00" + raw[4:]
    with pytest.raises(ValueError, match=BLOCK_ERROR):
        BlockHeader.parse(broken)
