"""Compact targets, retargeting, and chain work."""

from __future__ import annotations

import pytest

from edu_node.compact_target import GENESIS_TARGET, CompactTarget
from edu_node.node_constants import EXPECTED_TIMESPAN, GENESIS_BITS, TARGET_ERROR


def test_genesis_bits_are_the_easiest_allowed_target() -> None:
    """Genesis is accepted, and anything easier is not."""
    target = CompactTarget()
    assert target.to_target(GENESIS_BITS) == GENESIS_TARGET
    assert target.to_bits(GENESIS_TARGET) == GENESIS_BITS
    with pytest.raises(ValueError, match=TARGET_ERROR):
        target.to_target(GENESIS_BITS + 1)
    with pytest.raises(ValueError, match=TARGET_ERROR):
        target.to_target(0x207FFFFF)


@pytest.mark.parametrize(
    "bits",
    [True, -1, 0x1_0000_0000, 0x01000000, 0x01000001, 0x01800000, 0x00000001, 0x21000001],
)
def test_broken_compact_bits_are_rejected(bits: int) -> None:
    """Zero mantissa, the sign bit, and a bad exponent or type are rejected."""
    with pytest.raises(ValueError, match=TARGET_ERROR):
        CompactTarget().to_target(bits)  # type: ignore[arg-type]  # bool is not compact bits


def test_integer_targets_outside_the_chain_range_are_rejected() -> None:
    """Only targets from 1 through the genesis target have a compact form."""
    target = CompactTarget()
    with pytest.raises(ValueError, match=TARGET_ERROR):
        target.to_bits(True)  # type: ignore[arg-type]  # bool is not a target
    with pytest.raises(ValueError, match=TARGET_ERROR):
        target.to_bits(0)
    with pytest.raises(ValueError, match=TARGET_ERROR):
        target.to_bits(GENESIS_TARGET + 1)


def test_sign_bit_in_the_compact_mantissa_shifts_one_byte() -> None:
    """A mantissa with the high bit set is shifted so the encoding stays positive."""
    assert CompactTarget().to_bits(0x800000) == (4 << 24) | 0x8000


def test_small_targets_pack_into_three_bytes_or_fewer() -> None:
    """A target below 2^24 is shifted left instead of right."""
    assert CompactTarget().to_target(CompactTarget().to_bits(0x7F)) == 0x7F


def test_retarget_clamps_the_elapsed_time() -> None:
    """Very fast blocks get harder, and a zero clamp becomes one second."""
    target = CompactTarget()
    harder = target.retarget(GENESIS_BITS, 1, EXPECTED_TIMESPAN)
    assert target.to_target(harder) < GENESIS_TARGET
    back = target.retarget(harder, EXPECTED_TIMESPAN * 4, EXPECTED_TIMESPAN)
    assert target.to_target(harder) < target.to_target(back) <= GENESIS_TARGET
    tiny = target.retarget(GENESIS_BITS, 0, 1)
    assert tiny == GENESIS_BITS


@pytest.mark.parametrize(("actual", "expected"), [(True, 1), (1, True), (0, 0), (-1, 10)])
def test_retarget_rejects_bad_intervals(actual: int, expected: int) -> None:
    """Only non-negative integer intervals with a positive expected span are usable."""
    with pytest.raises(ValueError, match=TARGET_ERROR):
        CompactTarget().retarget(GENESIS_BITS, actual, expected)  # type: ignore[arg-type]  # bool is not seconds


def test_work_grows_as_the_target_shrinks() -> None:
    """A harder target adds more work than genesis."""
    harder = CompactTarget().retarget(GENESIS_BITS, 1, EXPECTED_TIMESPAN)
    assert CompactTarget().work(harder) > CompactTarget().work(GENESIS_BITS)
