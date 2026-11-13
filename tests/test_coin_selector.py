"""Deterministic coin selection."""

from __future__ import annotations

from decimal import Decimal

import pytest

from btc_wallet.coin_selector import CoinSelector

_SELECTOR = CoinSelector()


def _coin(mark: str, amount: object, vout: object = 0) -> tuple[str, int, Decimal]:
    """Return a coin whose txid is 32 repeats of a two-character mark."""
    return (mark * 32, vout, amount)  # type: ignore[return-value]  # callers pass boundary amounts too


def test_exact_match_breaks_ties_by_outpoint() -> None:
    """An exact coin wins, and the smaller txid then vout wins a tie."""
    target = Decimal("1")
    chosen = _SELECTOR.select(
        [_coin("bb", target, 1), _coin("aa", target, 2), _coin("aa", target, 0), _coin("cc", Decimal("2"))],
        target,
    )
    assert chosen == [_coin("aa", target, 0)]


def test_fewest_coins_then_smallest_total_then_outpoint() -> None:
    """One larger coin beats two smaller ones, and equal totals use txid order."""
    single = _SELECTOR.select(
        [_coin("ab", "0.1"), _coin("cd", Decimal("0.2"), 1), _coin("EF", 5, 2)],
        Decimal("0.2501"),
    )
    assert single == [("ef" * 32, 2, Decimal(5))]
    tied = _SELECTOR.select(
        [
            _coin("11", Decimal("1")),
            _coin("22", Decimal("4")),
            _coin("33", Decimal("2")),
            _coin("44", Decimal("3")),
        ],
        Decimal("5"),
    )
    assert [item[0][:2] for item in tied] == ["11", "22"]


def test_insufficient_and_too_many() -> None:
    """Empty and short sets fail, and more than 16 coins is refused before searching."""
    with pytest.raises(ValueError, match="Insufficient funds"):
        _SELECTOR.select([], Decimal("1"))
    with pytest.raises(ValueError, match="Too many coins"):
        _SELECTOR.select([_coin("aa", Decimal("1")) for _index in range(17)], Decimal("1"))
    with pytest.raises(ValueError, match="Too many coins"):
        _SELECTOR.select(((_coin("aa", Decimal("1"))),), Decimal("1"))  # type: ignore[arg-type]  # non-list input


@pytest.mark.parametrize(
    "coin",
    [
        "aa" * 32,
        ("zz" * 32, 0, Decimal("1")),
        ("ab" * 31, 0, Decimal("1")),
        ("ab" * 32, True, Decimal("1")),
        ("ab" * 32, -1, Decimal("1")),
        ("ab" * 32, 0, 1.5),
        ("ab" * 32, 0, True),
        ("ab" * 32, 0, "nope"),
        ("ab" * 32, 0, Decimal("0")),
        ("ab" * 32, 0, Decimal("NaN")),
        ("ab" * 32, 0, None),
    ],
)
def test_bad_coins_are_rejected(coin: object) -> None:
    """Each coin needs a 64-hex txid, a whole vout, and a positive satoshi amount."""
    with pytest.raises(ValueError, match="unusable coin"):
        _SELECTOR.select([coin], Decimal("1"))  # type: ignore[list-item]  # boundary input


@pytest.mark.parametrize("target", [Decimal("0"), Decimal("-1"), Decimal("0.000000001"), 1, 1.0, True, Decimal("NaN")])
def test_bad_targets_are_rejected(target: object) -> None:
    """The target is a positive satoshi-aligned Decimal."""
    with pytest.raises(ValueError, match="Selection target"):
        _SELECTOR.select([_coin("aa", Decimal("1"))], target)  # type: ignore[arg-type]  # boundary input
