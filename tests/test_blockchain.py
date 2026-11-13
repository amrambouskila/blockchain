"""The canonical chain is the one with the most work. Equal work keeps the first tip."""

from __future__ import annotations

import pytest

from bitcoin_wallet import BitcoinWallet
from edu_node import node_constants
from edu_node.block_header import BlockHeader
from edu_node.blockchain import Blockchain
from edu_node.compact_target import CompactTarget
from edu_node.edu_block import EduBlock
from edu_node.edu_transaction import EduTransaction, p2pkh_script
from edu_node.merkle_tree import MerkleTree
from edu_node.node_constants import (
    BLOCK_ERROR,
    BLOCK_SUBSIDY_COINS,
    BLOCK_VERSION,
    EXPECTED_TIMESPAN,
    GENESIS_BITS,
    GENESIS_PARENT,
    GENESIS_TIME,
    HASH_BYTES,
    MAX_TIMESTAMP_STEP,
    SATS_PER_COIN,
)
from edu_node.proof_of_work import ProofOfWork
from tests.chain_blocks import ChainBlocks, _raw

_KEY = f"{1:064x}"
_SUBSIDY = BLOCK_SUBSIDY_COINS * SATS_PER_COIN


def _clock() -> int:
    """Return the fixed clock used by most chain tests."""
    return GENESIS_TIME


def _chain() -> Blockchain:
    """Return an empty chain whose clock is the genesis time."""
    return Blockchain(_clock)


def _script() -> bytes:
    """Return the P2PKH script paid by mined coinbases."""
    return p2pkh_script(bytes.fromhex(BitcoinWallet.derive_public_key(_KEY)))


def _foreign(seed: int) -> EduTransaction:
    """Return a payment that does not spend a coin on this chain."""
    display = seed.to_bytes(32, "big").hex()
    return EduTransaction.parse(_raw([(display, 1, b"\x01")], [(1, b"\x51")]))


def _mined(
    chain: Blockchain,
    transactions: list[EduTransaction],
    *,
    parent: bytes | None = None,
    timestamp: int | None = None,
    bits: int | None = None,
) -> EduBlock:
    """Mine transactions onto parent."""
    chosen = chain.next_parent() if parent is None else parent
    when = chain.timestamp_for(chosen) if timestamp is None else timestamp
    chosen_bits = chain.bits_for(chosen) if bits is None else bits
    root = MerkleTree().root([item.internal_id for item in transactions])
    header = ProofOfWork().mine(BLOCK_VERSION, chosen, root, when, chosen_bits)
    return EduBlock(BlockHeader.parse(header), transactions)


def test_an_empty_chain_has_no_tip() -> None:
    """Before genesis the tip is empty and helpers reject an unknown parent."""
    chain = _chain()
    assert chain.height() == -1
    assert chain.tip() == (-1, "", 0)
    assert chain.canonical() == []
    assert chain.canonical_raw() == []
    assert chain.next_parent() == GENESIS_PARENT
    assert chain.bits_for(GENESIS_PARENT) == GENESIS_BITS
    assert chain.timestamp_for(GENESIS_PARENT) == GENESIS_TIME
    assert chain.height_after(GENESIS_PARENT) == 0
    missing = b"\x11" * HASH_BYTES
    with pytest.raises(ValueError, match=BLOCK_ERROR):
        chain.bits_for(missing)
    with pytest.raises(ValueError, match=BLOCK_ERROR):
        chain.timestamp_for(missing)
    with pytest.raises(ValueError, match=BLOCK_ERROR):
        chain.height_after(missing)
    with pytest.raises(KeyError):
        chain.block_at(0)
    with pytest.raises(KeyError):
        chain.block_at(True)  # type: ignore[arg-type]  # bool is not a height
    assert chain.utxo().contains("ab" * 32, 0) is False


def test_a_non_integer_clock_is_rejected() -> None:
    """The clock has to return an integer before a timestamp is chosen."""
    chain = Blockchain(lambda: "now")  # type: ignore[arg-type,return-value]  # boundary clock
    with pytest.raises(ValueError, match=BLOCK_ERROR):
        chain.timestamp_for(GENESIS_PARENT)


def test_headers_are_rejected_before_proof_of_work() -> None:
    """Version, parent, merkle length, bits, and time fail without mining."""
    chain = Blockchain(lambda: 0)
    assert chain.timestamp_for(GENESIS_PARENT) == GENESIS_TIME
    placeholder = [EduTransaction.coinbase(0, 1, b"\x51")]
    too_new = GENESIS_TIME + MAX_TIMESTAMP_STEP + 1
    cases = [
        BlockHeader(2, GENESIS_PARENT, b"\x22" * HASH_BYTES, GENESIS_TIME, GENESIS_BITS, 0),
        BlockHeader(BLOCK_VERSION, b"\x22" * HASH_BYTES, b"\x22" * HASH_BYTES, GENESIS_TIME, GENESIS_BITS, 0),
        BlockHeader(BLOCK_VERSION, GENESIS_PARENT, b"\x22" * 31, GENESIS_TIME, GENESIS_BITS, 0),
        BlockHeader(BLOCK_VERSION, GENESIS_PARENT, b"\x22" * HASH_BYTES, GENESIS_TIME, 1, 0),
        BlockHeader(BLOCK_VERSION, GENESIS_PARENT, b"\x22" * HASH_BYTES, too_new, GENESIS_BITS, 0),
    ]
    for header in cases:
        with pytest.raises(ValueError, match=BLOCK_ERROR):
            chain.add(EduBlock(header, placeholder))


def test_proof_merkle_and_a_swapped_clock_are_rejected() -> None:
    """A bad nonce, an empty transaction list, a wrong root, and a bad clock all fail."""
    chain = _chain()
    blocks = ChainBlocks()
    found = False
    for nonce in range(40):
        header = BlockHeader(BLOCK_VERSION, GENESIS_PARENT, b"\x44" * HASH_BYTES, GENESIS_TIME, GENESIS_BITS, nonce)
        if not ProofOfWork().meets(header.serialize(), GENESIS_BITS):
            with pytest.raises(ValueError, match=BLOCK_ERROR):
                chain.add(EduBlock(header, [EduTransaction.coinbase(0, 1, b"\x51")]))
            found = True
            break
    assert found is True
    real = blocks.block(chain, _KEY)
    with pytest.raises(ValueError, match=BLOCK_ERROR):
        chain.add(EduBlock(real.header, []))
    with pytest.raises(ValueError, match=BLOCK_ERROR):
        chain.add(EduBlock(real.header, [_foreign(9)]))
    chain._clock = lambda: "later"  # type: ignore[method-assign,assignment]  # boundary clock
    with pytest.raises(ValueError, match=BLOCK_ERROR):
        chain.add(real)


def test_genesis_and_a_later_payment_update_the_coins() -> None:
    """A coinbase can be spent in the next block, and that block collects the fee."""
    chain = _chain()
    blocks = ChainBlocks()
    genesis = blocks.block(chain, _KEY)
    assert chain.add(genesis) is True
    assert chain.add(genesis) is False
    coin = genesis.transactions[0]
    fee = 1_000
    payment = blocks.spend(_KEY, coin, 0, _SUBSIDY - fee, _script())
    child = blocks.block(chain, _KEY, payments=[payment], fee=fee)
    assert chain.add(child) is True
    assert chain.height() == 1
    assert chain.canonical_raw()[0] == genesis.raw
    assert child.transactions[0].outputs[0][0] == _SUBSIDY + fee
    assert chain.utxo().contains(coin.display_id, 0) is False
    assert chain.utxo().contains(payment.display_id, 0) is True
    assert chain.block_at(1).display_id == child.display_id
    with pytest.raises(KeyError):
        chain.block_at(2)


def test_coinbase_rules_are_enforced_after_the_header_is_valid() -> None:
    """The first transaction is the only coinbase, and it cannot pay more than subsidy plus fees."""
    chain = _chain()
    script = _script()
    with pytest.raises(ValueError, match=BLOCK_ERROR):
        chain.add(_mined(chain, [_foreign(4)]))
    with pytest.raises(ValueError, match=BLOCK_ERROR):
        chain.add(_mined(chain, [EduTransaction.coinbase(0, _SUBSIDY, script), EduTransaction.coinbase(1, 1, script)]))
    with pytest.raises(ValueError, match=BLOCK_ERROR):
        chain.add(_mined(chain, [EduTransaction.coinbase(0, _SUBSIDY + 1, script)]))
    coinbase = EduTransaction.coinbase(0, _SUBSIDY, script)
    payment = ChainBlocks().spend(_KEY, coinbase, 0, _SUBSIDY - 1, script)
    with pytest.raises(ValueError, match=BLOCK_ERROR):
        chain.add(_mined(chain, [coinbase, payment]))
    parent_time = GENESIS_TIME
    genesis = ChainBlocks().block(chain, _KEY)
    chain.add(genesis)
    parent = genesis.block_id
    for timestamp in (parent_time, parent_time + MAX_TIMESTAMP_STEP + 1):
        header = BlockHeader(BLOCK_VERSION, parent, b"\x55" * HASH_BYTES, timestamp, GENESIS_BITS, 0)
        with pytest.raises(ValueError, match=BLOCK_ERROR):
            chain.add(EduBlock(header, [EduTransaction.coinbase(1, 1, script)]))


def test_equal_work_keeps_the_first_tip_until_a_heavier_child_arrives() -> None:
    """A sibling is stored, and a child of that sibling becomes the tip when it has more work."""
    chain = _chain()
    blocks = ChainBlocks()
    genesis = blocks.block(chain, _KEY)
    chain.add(genesis)
    left = blocks.block(chain, _KEY, timestamp=GENESIS_TIME + 1)
    right = blocks.block(chain, _KEY, timestamp=GENESIS_TIME + 2)
    assert chain.add(left) is True
    assert chain.add(right) is False
    assert chain.tip()[1] == left.display_id
    child = blocks.block(chain, _KEY, parent=right.block_id, timestamp=GENESIS_TIME + 3)
    assert chain.add(child) is True
    assert chain.block_at(1).display_id == right.display_id
    assert chain.tip()[1] == child.display_id
    assert chain.tip()[2] > CompactTarget().work(GENESIS_BITS)


def test_difficulty_gets_harder_and_then_easier(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every second block retargets, and a block that still uses the old bits is rejected."""
    chain = _chain()
    blocks = ChainBlocks()
    first = blocks.block(chain, _KEY)
    chain.add(first)
    second = blocks.block(chain, _KEY, timestamp=GENESIS_TIME + 1)
    chain.add(second)
    harder = CompactTarget().retarget(GENESIS_BITS, 1, EXPECTED_TIMESPAN)
    assert chain.bits_for(second.block_id) == harder
    stale = BlockHeader(
        BLOCK_VERSION,
        second.block_id,
        b"\x66" * HASH_BYTES,
        GENESIS_TIME + 2,
        GENESIS_BITS,
        0,
    )
    with pytest.raises(ValueError, match=BLOCK_ERROR):
        chain.add(EduBlock(stale, [EduTransaction.coinbase(2, 1, b"\x51")]))
    third = blocks.block(chain, _KEY, timestamp=GENESIS_TIME + 2)
    chain.add(third)
    fourth = blocks.block(chain, _KEY, timestamp=GENESIS_TIME + 2 + EXPECTED_TIMESPAN * 4)
    chain.add(fourth)
    easier = CompactTarget().retarget(harder, EXPECTED_TIMESPAN * 4, EXPECTED_TIMESPAN)
    assert chain.bits_for(fourth.block_id) == easier
    assert CompactTarget().to_target(harder) < CompactTarget().to_target(easier)
    monkeypatch.setattr(node_constants, "MAX_BLOCK_COUNT", chain.height())
    with pytest.raises(ValueError, match=BLOCK_ERROR):
        chain.add(blocks.block(chain, _KEY))
