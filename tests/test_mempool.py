"""The mempool keeps payments that still spend and builds a coinbase around their fees."""

from __future__ import annotations

import pytest

from bitcoin_wallet import BitcoinWallet
from btc_wallet.transaction_signer import TransactionSigner
from edu_node import node_constants
from edu_node.edu_transaction import EduTransaction, p2pkh_script
from edu_node.mempool import Mempool
from edu_node.node_constants import BLOCK_SUBSIDY_COINS, MEMPOOL_FULL, SATS_PER_COIN, TX_ERROR
from edu_node.utxo_set import UtxoSet
from tests.chain_blocks import _raw

_KEY = f"{1:064x}"


def _script() -> bytes:
    """Return the P2PKH script paid by the test coins."""
    return p2pkh_script(bytes.fromhex(BitcoinWallet.derive_public_key(_KEY)))


def _fund(utxo: UtxoSet, height: int, value: int, script: bytes) -> EduTransaction:
    """Add a coinbase coin."""
    transaction = EduTransaction.coinbase(height, value, script)
    utxo.add_coinbase(transaction, value)
    return transaction


def _spend(inputs: list[tuple[str, int]], outputs: list[tuple[int, bytes]]) -> EduTransaction:
    """Return a signed payment."""
    return EduTransaction.parse(bytes.fromhex(TransactionSigner().sign_p2pkh(_KEY, inputs, outputs)))


def test_payments_are_kept_and_their_fee_is_added_to_the_coinbase() -> None:
    """A valid payment is mined, a stale one is skipped, and retain drops it."""
    script = _script()
    utxo = UtxoSet()
    coin = _fund(utxo, 0, 1_000, script)
    payment = _spend([(coin.display_id, 0)], [(400, script)])
    pool = Mempool()
    assert pool.add(payment, utxo) is True
    assert len(pool.assemble(UtxoSet(), 1, script)) == 1
    built = pool.assemble(utxo, 1, script)
    assert [tx.display_id for tx in built] == [built[0].display_id, payment.display_id]
    assert built[0].outputs[0][0] == BLOCK_SUBSIDY_COINS * SATS_PER_COIN + 600
    pool.retain(UtxoSet())
    assert len(pool.assemble(utxo, 2, script)) == 1


def test_collisions_scripts_and_capacity_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Coinbases, duplicates, double spends, bad scripts, and a full pool are refused."""
    script = _script()
    utxo = UtxoSet()
    first = _fund(utxo, 0, 1_000, script)
    second = _fund(utxo, 1, 1_000, script)
    pool = Mempool()
    with pytest.raises(ValueError, match=TX_ERROR):
        pool.add(first, utxo)
    payment = _spend([(first.display_id, 0)], [(700, script)])
    other = _spend([(first.display_id, 0)], [(500, script)])
    later = _spend([(second.display_id, 0)], [(800, script)])
    pool.add(payment, utxo)
    with pytest.raises(ValueError, match=TX_ERROR):
        pool.add(payment, utxo)
    with pytest.raises(ValueError, match=TX_ERROR):
        pool.add(other, utxo)
    bad = EduTransaction.parse(_raw([(second.display_id, 0, b"\x51")], [(1, b"\x51")]))
    with pytest.raises(ValueError, match=TX_ERROR):
        pool.add(bad, utxo)
    monkeypatch.setattr(node_constants, "MAX_MEMPOOL", 1)
    with pytest.raises(ValueError, match=MEMPOOL_FULL):
        pool.add(later, utxo)
    assert len(pool.assemble(utxo, 3, script)) == 2
