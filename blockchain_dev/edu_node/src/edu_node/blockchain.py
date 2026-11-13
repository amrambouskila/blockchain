"""The canonical chain is the one with the most proof-of-work. Equal work keeps the first tip."""

from __future__ import annotations

from collections.abc import Callable

from edu_node import node_constants
from edu_node.compact_target import CompactTarget
from edu_node.edu_block import EduBlock
from edu_node.edu_transaction import EduTransaction
from edu_node.merkle_tree import MerkleTree
from edu_node.node_constants import (
    BLOCK_ERROR,
    BLOCK_SUBSIDY_COINS,
    BLOCK_VERSION,
    DIFFICULTY_INTERVAL,
    EXPECTED_TIMESPAN,
    GENESIS_BITS,
    GENESIS_PARENT,
    GENESIS_TIME,
    HASH_BYTES,
    MAX_TIMESTAMP_STEP,
    SATS_PER_COIN,
)
from edu_node.proof_of_work import ProofOfWork
from edu_node.utxo_set import UtxoSet


class Blockchain:
    """Store blocks and select the chain with the most work."""

    def __init__(self, clock: Callable[[], int]) -> None:
        self._clock = clock
        self._blocks: dict[bytes, EduBlock] = {}
        self._height: dict[bytes, int] = {}
        self._work: dict[bytes, int] = {GENESIS_PARENT: 0}
        self._parent: dict[bytes, bytes] = {}
        self._tip: bytes | None = None
        self._tip_work = 0

    def add(self, block: EduBlock) -> bool:
        """Store block. Return whether it becomes the tip because it has strictly more work."""
        block_id = block.block_id
        if block_id in self._blocks:
            return False
        parent = block.header.previous
        if parent != GENESIS_PARENT and parent not in self._blocks:
            raise ValueError(BLOCK_ERROR)
        self._check_header(block, parent)
        self._apply(self._utxo_at(parent), block)
        height = self.height_after(parent)
        if height >= node_constants.MAX_BLOCK_COUNT:
            raise ValueError(BLOCK_ERROR)
        work = self._work[parent] + CompactTarget().work(block.header.bits)
        self._blocks[block_id] = block
        self._height[block_id] = height
        self._work[block_id] = work
        self._parent[block_id] = parent
        if work > self._tip_work:
            self._tip = block_id
            self._tip_work = work
            return True
        return False

    def height(self) -> int:
        """Return the tip height, or -1 when the chain is empty."""
        if self._tip is None:
            return -1
        return self._height[self._tip]

    def tip(self) -> tuple[int, str, int]:
        """Return height, display id, and total work. An empty chain returns -1, '', and 0."""
        if self._tip is None:
            return -1, "", 0
        return self._height[self._tip], self._blocks[self._tip].display_id, self._tip_work

    def canonical(self) -> list[EduBlock]:
        """Return the tip's blocks from genesis forward."""
        if self._tip is None:
            return []
        chain: list[EduBlock] = []
        cursor = self._tip
        while cursor != GENESIS_PARENT:
            chain.append(self._blocks[cursor])
            cursor = self._parent[cursor]
        chain.reverse()
        return chain

    def canonical_raw(self) -> list[bytes]:
        """Return the canonical blocks as raw bytes."""
        return [block.raw for block in self.canonical()]

    def block_at(self, height: int) -> EduBlock:
        """Return the canonical block at height."""
        blocks = self.canonical()
        if type(height) is not int or not 0 <= height < len(blocks):
            raise KeyError(height)
        return blocks[height]

    def utxo(self) -> UtxoSet:
        """Return the unspent coins of the current tip."""
        if self._tip is None:
            return UtxoSet()
        return self._utxo_at(self._tip)

    def next_parent(self) -> bytes:
        """Return the header hash a new tip block must extend."""
        if self._tip is None:
            return GENESIS_PARENT
        return self._tip

    def height_after(self, parent: bytes) -> int:
        """Return the height of a child of parent."""
        if parent == GENESIS_PARENT:
            return 0
        if parent not in self._blocks:
            raise ValueError(BLOCK_ERROR)
        return self._height[parent] + 1

    def bits_for(self, parent: bytes) -> int:
        """Return the compact target required for a child of parent."""
        if parent == GENESIS_PARENT:
            return GENESIS_BITS
        if parent not in self._blocks:
            raise ValueError(BLOCK_ERROR)
        parent_block = self._blocks[parent]
        if (self._height[parent] + 1) % DIFFICULTY_INTERVAL != 0:
            return parent_block.header.bits
        start = parent
        for _step in range(DIFFICULTY_INTERVAL - 1):
            start = self._parent[start]
        actual = parent_block.header.timestamp - self._blocks[start].header.timestamp
        return CompactTarget().retarget(parent_block.header.bits, actual, EXPECTED_TIMESPAN)

    def timestamp_for(self, parent: bytes) -> int:
        """Return a child timestamp that is after parent and not behind the clock."""
        now = self._clock()
        if type(now) is not int:
            raise ValueError(BLOCK_ERROR)
        if parent == GENESIS_PARENT:
            return max(GENESIS_TIME, now)
        if parent not in self._blocks:
            raise ValueError(BLOCK_ERROR)
        return max(self._blocks[parent].header.timestamp + 1, now)

    def _check_header(self, block: EduBlock, parent: bytes) -> None:
        """Reject a header whose link, target, time, proof, or merkle root is wrong."""
        header = block.header
        if header.version != BLOCK_VERSION:
            raise ValueError(BLOCK_ERROR)
        if len(header.previous) != HASH_BYTES or len(header.merkle_root) != HASH_BYTES:
            raise ValueError(BLOCK_ERROR)
        if header.bits != self.bits_for(parent):
            raise ValueError(BLOCK_ERROR)
        self._check_time(header.timestamp, parent)
        if not ProofOfWork().meets(header.serialize(), header.bits):
            raise ValueError(BLOCK_ERROR)
        root = MerkleTree().root([tx.internal_id for tx in block.transactions])
        if root != header.merkle_root:
            raise ValueError(BLOCK_ERROR)

    def _check_time(self, timestamp: int, parent: bytes) -> None:
        """Reject a timestamp that is not after its parent or that jumps too far."""
        if parent == GENESIS_PARENT:
            now = self._clock()
            if type(now) is not int or timestamp > max(GENESIS_TIME, now) + MAX_TIMESTAMP_STEP:
                raise ValueError(BLOCK_ERROR)
            return
        parent_time = self._blocks[parent].header.timestamp
        if not parent_time < timestamp <= parent_time + MAX_TIMESTAMP_STEP:
            raise ValueError(BLOCK_ERROR)

    def _apply(self, utxo: UtxoSet, block: EduBlock) -> None:
        """Spend every payment, then add the coinbase so it can be spent in the next block."""
        transactions = block.transactions
        if not transactions[0].is_coinbase:
            raise ValueError(BLOCK_ERROR)
        payments: list[EduTransaction] = []
        for tx in transactions[1:]:
            if tx.is_coinbase:
                raise ValueError(BLOCK_ERROR)
            payments.append(tx)
        fees = 0
        for tx in payments:
            try:
                fees += utxo.spend(tx)
            except ValueError:
                raise ValueError(BLOCK_ERROR) from None
        limit = BLOCK_SUBSIDY_COINS * SATS_PER_COIN + fees
        try:
            utxo.add_coinbase(transactions[0], limit)
        except ValueError:
            raise ValueError(BLOCK_ERROR) from None

    def _utxo_at(self, tip: bytes) -> UtxoSet:
        """Replay the chain ending at tip onto a fresh coin set."""
        if tip == GENESIS_PARENT:
            return UtxoSet()
        chain: list[EduBlock] = []
        cursor = tip
        while cursor != GENESIS_PARENT:
            chain.append(self._blocks[cursor])
            cursor = self._parent[cursor]
        utxo = UtxoSet()
        for block in reversed(chain):
            self._apply(utxo, block)
        return utxo
