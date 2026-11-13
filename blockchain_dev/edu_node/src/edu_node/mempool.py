"""A small pool of payment transactions waiting for the next block."""

from __future__ import annotations

from edu_node import node_constants
from edu_node.edu_transaction import EduTransaction
from edu_node.node_constants import BLOCK_SUBSIDY_COINS, MEMPOOL_FULL, SATS_PER_COIN, TX_ERROR
from edu_node.utxo_set import UtxoSet


class Mempool:
    """Keep valid payments and build the next block around them."""

    def __init__(self) -> None:
        self._txs: dict[str, EduTransaction] = {}

    def add(self, tx: EduTransaction, utxo: UtxoSet) -> bool:
        """Store tx when it pays for real coins and does not collide with the pool."""
        if tx.is_coinbase or tx.display_id in self._txs:
            raise ValueError(TX_ERROR)
        claimed = {
            (txid, vout) for existing in self._txs.values() for txid, vout, _script, _sequence in existing.inputs
        }
        for txid, vout, _script, _sequence in tx.inputs:
            if (txid, vout) in claimed:
                raise ValueError(TX_ERROR)
        trial = utxo.copy()
        for display_id in sorted(self._txs):
            trial.spend(self._txs[display_id])
        trial.spend(tx)
        if len(self._txs) >= node_constants.MAX_MEMPOOL:
            raise ValueError(MEMPOOL_FULL)
        self._txs[tx.display_id] = tx
        return True

    def retain(self, utxo: UtxoSet) -> None:
        """Drop transactions that no longer pay against utxo."""
        running = utxo.copy()
        kept: dict[str, EduTransaction] = {}
        for display_id in sorted(self._txs):
            tx = self._txs[display_id]
            try:
                running.spend(tx)
            except ValueError:
                continue
            kept[display_id] = tx
        self._txs = kept

    def assemble(self, utxo: UtxoSet, height: int, pay_script: bytes) -> list[EduTransaction]:
        """Return a coinbase plus the payments that still spend cleanly, in txid order."""
        running = utxo.copy()
        chosen: list[EduTransaction] = []
        fees = 0
        for display_id in sorted(self._txs):
            tx = self._txs[display_id]
            try:
                trial = running.copy()
                fee = trial.spend(tx)
            except ValueError:
                continue
            running = trial
            chosen.append(tx)
            fees += fee
        subsidy = BLOCK_SUBSIDY_COINS * SATS_PER_COIN
        coinbase = EduTransaction.coinbase(height, subsidy + fees, pay_script)
        return [coinbase, *chosen]
