"""Compact proof-of-work targets, the same encoding Bitcoin uses for nBits."""

from __future__ import annotations

from edu_node.node_constants import GENESIS_BITS, TARGET_ERROR

_SIGN_BIT = 0x00800000
_BYTE_BITS = 8
_COMPACT_SIZE_INDEX = 3
_MIN_EXPONENT = 1
_MAX_EXPONENT = 32
_MAX_BITS = 0xFFFFFFFF


def _uncapped_target(bits: int) -> int:
    """Return the integer target for bits without the genesis ceiling."""
    if type(bits) is not int or not 0 <= bits <= _MAX_BITS:
        raise ValueError(TARGET_ERROR)
    exponent = bits >> 24
    mantissa = bits & 0xFFFFFF
    if mantissa == 0 or mantissa & _SIGN_BIT or not _MIN_EXPONENT <= exponent <= _MAX_EXPONENT:
        raise ValueError(TARGET_ERROR)
    if exponent <= _COMPACT_SIZE_INDEX:
        target = mantissa >> (_BYTE_BITS * (_COMPACT_SIZE_INDEX - exponent))
    else:
        target = mantissa << (_BYTE_BITS * (exponent - _COMPACT_SIZE_INDEX))
    if target <= 0:
        raise ValueError(TARGET_ERROR)
    return target


GENESIS_TARGET = _uncapped_target(GENESIS_BITS)


class CompactTarget:
    """Convert between compact bits, integer targets, and chain work."""

    def to_target(self, bits: int) -> int:
        """Return the integer target for bits, never easier than genesis."""
        target = _uncapped_target(bits)
        if target > GENESIS_TARGET:
            raise ValueError(TARGET_ERROR)
        return target

    def to_bits(self, target: int) -> int:
        """Return the compact form of target."""
        if type(target) is not int or not 1 <= target <= GENESIS_TARGET:
            raise ValueError(TARGET_ERROR)
        size = (target.bit_length() + 7) // _BYTE_BITS
        if size <= _COMPACT_SIZE_INDEX:
            compact = target << (_BYTE_BITS * (_COMPACT_SIZE_INDEX - size))
        else:
            compact = target >> (_BYTE_BITS * (size - _COMPACT_SIZE_INDEX))
        if compact & _SIGN_BIT:
            compact >>= _BYTE_BITS
            size += 1
        return (size << 24) | compact

    def retarget(self, bits: int, actual_seconds: int, expected_seconds: int) -> int:
        """Return bits after clamping the elapsed interval to a factor of four."""
        if type(actual_seconds) is not int or type(expected_seconds) is not int:
            raise ValueError(TARGET_ERROR)
        if expected_seconds <= 0 or actual_seconds < 0:
            raise ValueError(TARGET_ERROR)
        target = self.to_target(bits)
        low = expected_seconds // 4
        high = expected_seconds * 4
        clamped = min(max(actual_seconds, low), high)
        if clamped == 0:
            clamped = 1
        updated = min(GENESIS_TARGET, target * clamped // expected_seconds)
        return self.to_bits(updated)

    def work(self, bits: int) -> int:
        """Return the chain work added by a block with these bits."""
        return (1 << 256) // (self.to_target(bits) + 1)
