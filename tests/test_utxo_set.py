"""Coins can be spent once, and a coinbase is not spendable as a payment."""

from __future__ import annotations

import struct

import pytest

from bitcoin_wallet import BitcoinWallet
from btc_wallet.transaction_signer import TransactionSigner
from btc_wallet.wallet_constants import MAX_MONEY_SATS, SEQUENCE_FINAL
from edu_node.edu_transaction import EduTransaction, p2pkh_script
from edu_node.node_constants import BLOCK_ERROR, TX_ERROR
from edu_node.utxo_set import UtxoSet
from tests.chain_blocks import _raw

_KEY = f"{1:064x}"


def _script() -> bytes:
    """Return the P2PKH script for the test key."""
    return p2pkh_script(bytes.fromhex(BitcoinWallet.derive_public_key(_KEY)))


def _fund(utxo: UtxoSet, height: int, value: int, script: bytes) -> EduTransaction:
    """Add one coinbase output and return that transaction."""
    transaction = EduTransaction.coinbase(height, value, script)
    utxo.add_coinbase(transaction, value)
    return transaction


def _spend(inputs: list[tuple[str, int]], outputs: list[tuple[int, bytes]]) -> EduTransaction:
    """Return a signed payment."""
    raw = TransactionSigner().sign_p2pkh(_KEY, inputs, outputs)
    return EduTransaction.parse(bytes.fromhex(raw))


def test_a_payment_spends_one_coin_and_a_copy_keeps_it() -> None:
    """Spending removes the coin from the original set only and returns the fee."""
    script = _script()
    utxo = UtxoSet()
    coin = _fund(utxo, 0, 1_000, script)
    twin = utxo.copy()
    payment = _spend([(coin.display_id, 0)], [(600, script)])
    assert utxo.spend(payment) == 400
    assert utxo.contains(coin.display_id, 0) is False
    assert utxo.contains(payment.display_id, 0) is True
    assert utxo.value(payment.display_id, 0) == 600
    assert twin.contains(coin.display_id, 0) is True
    with pytest.raises(ValueError, match=TX_ERROR):
        utxo.value(coin.display_id, 0)
    assert utxo.contains("cd" * 32, 0) is False


def test_the_same_outpoint_cannot_be_spent_twice_in_one_transaction() -> None:
    """A repeated input is rejected before the coin is removed."""
    script = _script()
    utxo = UtxoSet()
    coin = _fund(utxo, 0, 1_000, script)
    payment = _spend([(coin.display_id, 0), (coin.display_id, 0)], [(100, script)])
    with pytest.raises(ValueError, match=TX_ERROR):
        utxo.spend(payment)
    assert utxo.value(coin.display_id, 0) == 1_000


def test_overspending_or_a_bad_script_leaves_the_coin() -> None:
    """Missing coins, coinbases, bad scripts, and too many satoshis are refused."""
    script = _script()
    utxo = UtxoSet()
    coin = _fund(utxo, 0, 1_000, script)
    with pytest.raises(ValueError, match=TX_ERROR):
        utxo.spend(coin)
    with pytest.raises(ValueError, match=TX_ERROR):
        utxo.spend(_spend([("cd" * 32, 0)], [(1, script)]))
    with pytest.raises(ValueError, match=TX_ERROR):
        utxo.spend(_spend([(coin.display_id, 0)], [(1_001, script)]))
    bad = EduTransaction.parse(_raw([(coin.display_id, 0, b"\x51")], [(1, b"\x51")]))
    with pytest.raises(ValueError, match=TX_ERROR):
        utxo.spend(bad)
    assert utxo.contains(coin.display_id, 0) is True


def test_outputs_cannot_add_up_past_the_money_limit() -> None:
    """Two maximum coins cannot be paid onward when the sum passes the money limit."""
    script = _script()
    utxo = UtxoSet()
    first = _fund(utxo, 0, MAX_MONEY_SATS, script)
    second = _fund(utxo, 1, MAX_MONEY_SATS, script)
    payment = _spend(
        [(first.display_id, 0), (second.display_id, 0)],
        [(MAX_MONEY_SATS, script), (MAX_MONEY_SATS, script)],
    )
    with pytest.raises(ValueError, match=TX_ERROR):
        utxo.spend(payment)
    assert utxo.contains(first.display_id, 0) is True
    assert utxo.contains(second.display_id, 0) is True


def test_coinbase_outputs_have_one_value_inside_the_subsidy() -> None:
    """A payment, a second output, or a value over the subsidy is not added."""
    utxo = UtxoSet()
    script = b"\x51"
    payment = _spend([("cd" * 32, 0)], [(1, script)])
    with pytest.raises(ValueError, match=BLOCK_ERROR):
        utxo.add_coinbase(payment, 1)
    script_sig = bytes([4]) + struct.pack("<I", 3)
    two_outputs = EduTransaction.parse(
        _raw([("00" * 32, SEQUENCE_FINAL, script_sig)], [(1, script), (1, script)]),
    )
    with pytest.raises(ValueError, match=BLOCK_ERROR):
        utxo.add_coinbase(two_outputs, 5)
    rich = EduTransaction.coinbase(4, 10, script)
    with pytest.raises(ValueError, match=BLOCK_ERROR):
        utxo.add_coinbase(rich, 9)
