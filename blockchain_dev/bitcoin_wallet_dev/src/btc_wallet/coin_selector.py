"""Deterministic coin selection: an exact coin first, otherwise the smallest covering set."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from itertools import combinations

from btc_wallet.wallet_constants import MAX_COIN_SELECT_UTXOS
from constants import SATOSHI, TXID_HEX_LENGTH

_COIN_ERROR = "Coin selection received an unusable coin."
_FUNDS_ERROR = "Insufficient funds for the transaction."
_TOO_MANY_ERROR = "Too many coins to select from."
_TARGET_ERROR = "Selection target must be a positive satoshi-aligned Decimal."


class CoinSelector:
    """Pick coins with the fewest inputs, then the smallest total, in txid order."""

    def select(
        self,
        utxos: list[tuple[str, int, Decimal]],
        target: Decimal,
    ) -> list[tuple[str, int, Decimal]]:
        """Return the coins that pay target."""
        if not isinstance(utxos, list) or len(utxos) > MAX_COIN_SELECT_UTXOS:
            raise ValueError(_TOO_MANY_ERROR)
        spendable = [_validated_coin(utxo) for utxo in utxos]
        needed = _validated_target(target)
        exact = sorted((coin for coin in spendable if coin[2] == needed), key=lambda coin: (coin[0], coin[1]))
        if exact:
            return [exact[0]]
        best: tuple[tuple[tuple[str, int, Decimal], ...], Decimal] | None = None
        for size in range(1, len(spendable) + 1):
            for combo in combinations(spendable, size):
                total = sum((coin[2] for coin in combo), start=Decimal(0))
                if total < needed:
                    continue
                ordered = tuple(sorted(combo, key=lambda coin: (coin[0], coin[1])))
                if best is None or total < best[1] or (total == best[1] and ordered < best[0]):
                    best = (ordered, total)
            if best is not None:
                return list(best[0])
        raise ValueError(_FUNDS_ERROR)


def _validated_target(target: Decimal) -> Decimal:
    """Return target when it is a positive satoshi-aligned Decimal."""
    if type(target) is not Decimal or not target.is_finite() or target <= 0 or target != target.quantize(SATOSHI):
        raise ValueError(_TARGET_ERROR)
    return target


def _validated_coin(utxo: object) -> tuple[str, int, Decimal]:
    """Return a txid, vout, and amount when utxo has that shape."""
    if not isinstance(utxo, tuple) or len(utxo) != 3:
        raise ValueError(_COIN_ERROR)
    txid, vout, amount = utxo
    if not isinstance(txid, str) or len(txid) != TXID_HEX_LENGTH:
        raise ValueError(_COIN_ERROR)
    if any(character not in "0123456789abcdefABCDEF" for character in txid):
        raise ValueError(_COIN_ERROR)
    if type(vout) is not int or vout < 0:
        raise ValueError(_COIN_ERROR)
    return txid.lower(), vout, _validated_amount(amount)


def _validated_amount(amount: object) -> Decimal:
    """Return amount in BTC when it is a positive satoshi-aligned number."""
    if isinstance(amount, bool) or isinstance(amount, float):
        raise ValueError(_COIN_ERROR)
    if isinstance(amount, Decimal):
        parsed = amount
    elif isinstance(amount, int):
        parsed = Decimal(amount)
    elif isinstance(amount, str):
        try:
            parsed = Decimal(amount)
        except InvalidOperation:
            raise ValueError(_COIN_ERROR) from None
    else:
        raise ValueError(_COIN_ERROR)
    if not parsed.is_finite() or parsed <= 0 or parsed != parsed.quantize(SATOSHI):
        raise ValueError(_COIN_ERROR)
    return parsed
