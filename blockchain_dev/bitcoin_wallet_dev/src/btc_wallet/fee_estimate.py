"""Validated estimatesmartfee results, in BTC per kilobyte."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from constants import MAX_FEE_RATE_BTC_PER_KVBYTE

_FEE_ERROR = "Fee estimate is invalid."
_MAX_FEE_TEXT = 32


class FeeEstimate:
    """Read a positive, bounded fee rate from an estimatesmartfee response."""

    def parse(self, payload: object) -> Decimal:
        """Return the fee rate in BTC per kilobyte."""
        if not isinstance(payload, dict):
            raise ValueError(_FEE_ERROR)
        errors = payload.get("errors")
        if errors:
            raise ValueError(_FEE_ERROR)
        return _fee_rate(payload.get("feerate"))


def _fee_rate(feerate: object) -> Decimal:
    """Return feerate when it is a positive finite rate at or below the cap."""
    if isinstance(feerate, bool) or isinstance(feerate, float):
        raise ValueError(_FEE_ERROR)
    if isinstance(feerate, Decimal):
        parsed = feerate
    elif isinstance(feerate, int):
        parsed = Decimal(feerate)
    elif isinstance(feerate, str) and len(feerate) <= _MAX_FEE_TEXT:
        try:
            parsed = Decimal(feerate)
        except InvalidOperation:
            raise ValueError(_FEE_ERROR) from None
    else:
        raise ValueError(_FEE_ERROR)
    if not parsed.is_finite() or parsed <= 0 or parsed > MAX_FEE_RATE_BTC_PER_KVBYTE:
        raise ValueError(_FEE_ERROR)
    return parsed
