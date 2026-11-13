"""estimatesmartfee payloads parsed as BTC per kilobyte."""

from __future__ import annotations

from decimal import Decimal

import pytest

from btc_wallet.fee_estimate import FeeEstimate

_PARSER = FeeEstimate()


@pytest.mark.parametrize(
    "feerate",
    [Decimal("0.00001"), Decimal("0.000000001"), 1, "0.00002"],
)
def test_positive_rates_are_accepted(feerate: object) -> None:
    """Decimal, integer, and short text rates come back as Decimal."""
    assert _PARSER.parse({"feerate": feerate}) == Decimal(str(feerate) if not isinstance(feerate, Decimal) else feerate)


def test_errors_reject_even_when_a_rate_is_present() -> None:
    """A non-empty errors field wins over a feerate."""
    with pytest.raises(ValueError, match="Fee estimate"):
        _PARSER.parse({"feerate": Decimal("0.00001"), "errors": ["Insufficient data"]})
    assert _PARSER.parse({"feerate": Decimal("0.00001"), "errors": []}) == Decimal("0.00001")


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {"feerate": None},
        {"feerate": True},
        {"feerate": 1.5},
        {"feerate": "not-a-number"},
        {"feerate": "1" * 33},
        {"feerate": Decimal("0")},
        {"feerate": Decimal("-0.1")},
        {"feerate": Decimal("1.1")},
        {"feerate": Decimal("NaN")},
        {"feerate": Decimal("Infinity")},
        {"errors": ["missing"]},
    ],
)
def test_bad_payloads_are_rejected(payload: object) -> None:
    """Missing, non-numeric, non-finite, and out-of-range rates fail."""
    with pytest.raises(ValueError, match="Fee estimate"):
        _PARSER.parse(payload)
