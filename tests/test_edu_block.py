"""Block framing: a header, a count, and each transaction with its length."""

from __future__ import annotations

import struct

import pytest

from edu_node import edu_block as edu_block_module
from edu_node.edu_block import EduBlock
from edu_node.edu_transaction import EduTransaction
from edu_node.node_constants import BLOCK_ERROR, BLOCK_VERSION, HEADER_BYTES, MAX_TX_PER_BLOCK


def _header() -> bytes:
    """Return an 80-byte version-1 header. These tests do not check proof of work."""
    return struct.pack("<I32s32sIII", BLOCK_VERSION, bytes(32), bytes(32), 1, 1, 1)


def _sample() -> EduTransaction:
    """Return a tiny coinbase used as block payload."""
    return EduTransaction.coinbase(0, 1, b"\x51")


def _frame(transactions: list[EduTransaction], *, count: int | None = None) -> bytes:
    """Return header plus transaction lengths."""
    chosen = len(transactions) if count is None else count
    parts = [_header(), struct.pack("<H", chosen)]
    for transaction in transactions:
        parts.append(struct.pack("<I", len(transaction.raw)))
        parts.append(transaction.raw)
    return b"".join(parts)


def test_a_block_round_trips_through_its_raw_bytes() -> None:
    """Parse returns the same transaction, and the display id is the reversed header hash."""
    transaction = _sample()
    raw = _frame([transaction])
    block = EduBlock.parse(raw)
    assert block.raw == raw
    assert block.transactions[0].display_id == transaction.display_id
    assert block.display_id == block.block_id[::-1].hex()


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        _header(),
        _header() + b"\x01",
        _frame([], count=0),
        _frame([], count=MAX_TX_PER_BLOCK + 1),
        _header() + struct.pack("<H", 1) + b"\x01\x00",
        _header() + struct.pack("<HI", 1, 0),
        _header() + struct.pack("<HI", 1, 10),
        _frame([_sample()]) + b"\x00",
        "00",
    ],
)
def test_broken_block_bytes_are_rejected(raw: bytes) -> None:
    """Length, count, transaction size, and trailing bytes are rejected."""
    with pytest.raises(ValueError, match=BLOCK_ERROR):
        EduBlock.parse(raw)  # type: ignore[arg-type]  # a block is bytes


def test_caps_reject_an_oversized_block_or_transaction(monkeypatch: pytest.MonkeyPatch) -> None:
    """The raw property and the parser both honor their size caps."""
    block = EduBlock.parse(_frame([_sample()]))
    monkeypatch.setattr(edu_block_module, "MAX_BLOCK_BYTES", 10)
    with pytest.raises(ValueError, match=BLOCK_ERROR):
        _ = block.raw
    monkeypatch.setattr(edu_block_module, "MAX_BLOCK_BYTES", HEADER_BYTES)
    with pytest.raises(ValueError, match=BLOCK_ERROR):
        EduBlock.parse(_frame([_sample()]))
    monkeypatch.setattr(edu_block_module, "MAX_BLOCK_BYTES", 256_000)
    monkeypatch.setattr(edu_block_module, "MAX_TX_BYTES", 1)
    with pytest.raises(ValueError, match=BLOCK_ERROR):
        EduBlock.parse(_frame([_sample()]))
