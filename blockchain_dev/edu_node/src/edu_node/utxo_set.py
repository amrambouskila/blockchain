"""The coins a chain can spend, keyed by transaction id and output index."""

from __future__ import annotations

from btc_wallet.wallet_constants import MAX_MONEY_SATS
from edu_node.edu_transaction import EduTransaction
from edu_node.node_constants import BLOCK_ERROR, TX_ERROR
from edu_node.script_interpreter import ScriptInterpreter


class UtxoSet:
    """Spend and add transaction outputs."""

    def __init__(self) -> None:
        self._coins: dict[tuple[str, int], tuple[int, bytes]] = {}

    def copy(self) -> UtxoSet:
        """Return a shallow copy. Coin records are not mutated in place."""
        twin = UtxoSet()
        twin._coins = dict(self._coins)
        return twin

    def contains(self, txid: str, vout: int) -> bool:
        """Return whether that outpoint is still unspent."""
        return (txid, vout) in self._coins

    def value(self, txid: str, vout: int) -> int:
        """Return the satoshi value of an unspent output."""
        coin = self._coins.get((txid, vout))
        if coin is None:
            raise ValueError(TX_ERROR)
        return coin[0]

    def spend(self, tx: EduTransaction) -> int:
        """Apply a non-coinbase transaction and return its fee."""
        if tx.is_coinbase:
            raise ValueError(TX_ERROR)
        incoming = 0
        removing: list[tuple[str, int]] = []
        seen: set[tuple[str, int]] = set()
        for index, (txid, vout, script_sig, _sequence) in enumerate(tx.inputs):
            if (txid, vout) in seen:
                raise ValueError(TX_ERROR)
            seen.add((txid, vout))
            coin = self._coins.get((txid, vout))
            if coin is None:
                raise ValueError(TX_ERROR)
            value, script_pubkey = coin
            if not ScriptInterpreter().accepts(script_sig, script_pubkey, tx, index):
                raise ValueError(TX_ERROR)
            incoming += value
            removing.append((txid, vout))
        outgoing = sum(value for value, _script in tx.outputs)
        if outgoing > incoming or outgoing > MAX_MONEY_SATS:
            raise ValueError(TX_ERROR)
        for key in removing:
            del self._coins[key]
        self._add_outputs(tx)
        return incoming - outgoing

    def add_coinbase(self, tx: EduTransaction, subsidy_limit: int) -> None:
        """Add the single coinbase output when its value is inside subsidy_limit."""
        if not tx.is_coinbase or len(tx.outputs) != 1:
            raise ValueError(BLOCK_ERROR)
        value, _script = tx.outputs[0]
        if value > subsidy_limit:
            raise ValueError(BLOCK_ERROR)
        self._add_outputs(tx)

    def _add_outputs(self, tx: EduTransaction) -> None:
        """Record every output of tx."""
        for vout, (value, script) in enumerate(tx.outputs):
            self._coins[(tx.display_id, vout)] = (value, script)
