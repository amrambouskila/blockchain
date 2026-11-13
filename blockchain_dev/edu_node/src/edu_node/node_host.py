"""One educational node: its chain, its memory pool, its peers, and its miner key."""

from __future__ import annotations

import secrets
import socket
import struct
import threading
import time
from collections.abc import Callable
from pathlib import Path

from bitcoin_wallet import BitcoinWallet
from edu_node import node_constants
from edu_node.block_header import BlockHeader
from edu_node.blockchain import Blockchain
from edu_node.chain_store import ChainStore
from edu_node.edu_block import EduBlock
from edu_node.edu_transaction import EduTransaction, p2pkh_script
from edu_node.mempool import Mempool
from edu_node.merkle_tree import MerkleTree
from edu_node.node_constants import (
    BLOCK_VERSION,
    COMMAND_BLOCK,
    COMMAND_HELLO,
    COMMAND_TIP,
    COMMAND_TX,
    HASH_BYTES,
    LOOPBACK_HOST,
    MAX_PEER_PORT,
    NODE_ID_BYTES,
    PEER_ERROR,
    SYNC_ERROR,
    TIP_PAYLOAD_BYTES,
    TX_ERROR,
)
from edu_node.peer_link import PeerLink
from edu_node.peer_server import PeerServer
from edu_node.proof_of_work import ProofOfWork


class NodeHost:
    """Run a chain on disk and talk to other nodes on the loopback interface."""

    def __init__(self, store: ChainStore, chain: Blockchain, miner_key: str) -> None:
        self._store = store
        self._chain = chain
        self._miner_key = miner_key
        self._mempool = Mempool()
        self._condition = threading.Condition()
        self._links: list[PeerLink] = []
        self._node_id = secrets.token_bytes(NODE_ID_BYTES)
        self._server = PeerServer(self.serve)

    @classmethod
    def open(
        cls,
        directory: Path,
        miner_key: str | None = None,
        *,
        create_genesis: bool = True,
        clock: Callable[[], int] | None = None,
    ) -> NodeHost:
        """Open or create a chain directory. The miner key is checked before the directory is created."""
        if miner_key is None:
            checked = BitcoinWallet.generate_private_key()
        else:
            checked = BitcoinWallet._require_private_key_hex(miner_key)
        ticker = clock if clock is not None else (lambda: int(time.time()))
        store = ChainStore(directory)
        chain = Blockchain(ticker)
        host = cls(store, chain, checked)
        for raw in store.load():
            chain.add(EduBlock.parse(raw))
        host.listen()
        if create_genesis and chain.height() < 0:
            host.mine()
        return host

    def listen(self) -> int:
        """Listen on an ephemeral loopback port. A second call returns the same port."""
        return self._server.listen()

    def port(self) -> int:
        """Return the peer port."""
        return self._server.port()

    def connect(self, port: int) -> None:
        """Connect to another node on 127.0.0.1. Host names are not accepted."""
        if type(port) is not int or not 1 <= port <= MAX_PEER_PORT or port == self.port():
            raise ValueError(PEER_ERROR)
        sock = socket.create_connection((LOOPBACK_HOST, port), timeout=node_constants.PEER_CONNECT_TIMEOUT)
        sock.settimeout(None)
        threading.Thread(target=self.serve, args=(sock,), daemon=True).start()

    def mine(self) -> EduBlock:
        """Mine a block on the current tip, save the canonical chain, and broadcast that chain."""
        with self._condition:
            parent = self._chain.next_parent()
            block = self._mine_locked(parent)
            self._chain.add(block)
            self._mempool.retain(self._chain.utxo())
            self._store.save(self._chain.canonical_raw())
            self._condition.notify_all()
        self._broadcast_chain(None)
        return block

    def submit(self, raw_hex: str) -> str:
        """Add a payment to the pool and broadcast it. Return its display id."""
        if not isinstance(raw_hex, str) or not 1 <= len(raw_hex) <= node_constants.MAX_TX_HEX:
            raise ValueError(TX_ERROR)
        try:
            raw = bytes.fromhex(raw_hex)
        except ValueError:
            raise ValueError(TX_ERROR) from None
        tx = EduTransaction.parse(raw)
        with self._condition:
            self._mempool.retain(self._chain.utxo())
            self._mempool.add(tx, self._chain.utxo())
        self._broadcast_tx(raw, None)
        return tx.display_id

    def tip(self) -> tuple[int, str, int]:
        """Return the current height, display id, and work."""
        with self._condition:
            return self._chain.tip()

    def block_at(self, height: int) -> EduBlock:
        """Return one canonical block."""
        with self._condition:
            return self._chain.block_at(height)

    def page(self, offset: int, limit: int) -> list[tuple[int, EduBlock]]:
        """Return canonical blocks in height order, starting at offset."""
        with self._condition:
            blocks = self._chain.canonical()
        end = min(offset + limit, len(blocks))
        if offset >= len(blocks):
            return []
        return [(index, blocks[index]) for index in range(offset, end)]

    def wait_for_tip(self, height: int, block_id: str, timeout: float) -> None:
        """Block until this node adopts that tip, or raise when timeout seconds have passed."""
        deadline = time.monotonic() + timeout
        with self._condition:
            while True:
                current_height, current_id, _work = self._chain.tip()
                if current_height == height and current_id == block_id:
                    return
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(SYNC_ERROR)
                self._condition.wait(remaining)

    def drop_peers(self) -> None:
        """Close current peer sockets and keep listening."""
        with self._condition:
            links = list(self._links)
            self._links.clear()
        for link in links:
            link.close()

    def close(self) -> None:
        """Stop listening and close every peer."""
        self.drop_peers()
        self._server.close()

    def serve(self, sock: socket.socket) -> None:
        """Read one peer until it closes. A bad frame closes this socket."""
        link = PeerLink(sock)
        with self._condition:
            self._links.append(link)
        reader = threading.Thread(target=self._read_loop, args=(link,), daemon=True)
        reader.start()
        try:
            self._greet(link)
            reader.join()
        finally:
            link.close()
            reader.join(1.0)
            self._forget(link)

    def _mine_locked(self, parent: bytes) -> EduBlock:
        """Assemble and mine. The caller holds the node lock."""
        self._mempool.retain(self._chain.utxo())
        transactions = self._mempool.assemble(
            self._chain.utxo(),
            self._chain.height_after(parent),
            self._pay_script(),
        )
        merkle_root = MerkleTree().root([tx.internal_id for tx in transactions])
        header = ProofOfWork().mine(
            BLOCK_VERSION,
            parent,
            merkle_root,
            self._chain.timestamp_for(parent),
            self._chain.bits_for(parent),
        )
        return EduBlock(BlockHeader.parse(header), transactions)

    def _pay_script(self) -> bytes:
        """Return the P2PKH script paid by this node's coinbase."""
        public_key = bytes.fromhex(BitcoinWallet.derive_public_key(self._miner_key))
        return p2pkh_script(public_key)

    def _greet(self, link: PeerLink) -> None:
        """Send a hello, then the whole canonical chain, then the tip."""
        with self._condition:
            raws = self._chain.canonical_raw()
            tip = self._tip_bytes()
            node_id = self._node_id
        try:
            link.send(COMMAND_HELLO, node_id)
            for raw in raws:
                link.send(COMMAND_BLOCK, raw)
            link.send(COMMAND_TIP, tip)
        except OSError:
            self._forget(link)

    def _read_loop(self, link: PeerLink) -> None:
        """Handle frames until the peer hangs up or sends a broken frame."""
        try:
            while True:
                frame = link.read_one()
                if frame is None:
                    return
                command, payload = frame
                self._on_frame(link, command, payload)
        except (ValueError, OSError, TimeoutError):
            return

    def _on_frame(self, link: PeerLink, command: int, payload: bytes) -> None:
        """Apply one peer message. An unknown command closes the peer."""
        if command == COMMAND_HELLO:
            if len(payload) != NODE_ID_BYTES:
                raise ValueError(PEER_ERROR)
            return
        if command == COMMAND_TIP:
            self._read_tip(payload)
            return
        if command == COMMAND_TX:
            self._take_tx(link, payload)
            return
        if command == COMMAND_BLOCK:
            self._take_block(link, payload)
            return
        raise ValueError(PEER_ERROR)

    def _take_tx(self, link: PeerLink, payload: bytes) -> None:
        """Parse a transaction. A valid one that the pool rejects does not close the peer."""
        tx = EduTransaction.parse(payload)
        try:
            with self._condition:
                self._mempool.retain(self._chain.utxo())
                self._mempool.add(tx, self._chain.utxo())
        except ValueError:
            return
        self._broadcast_tx(payload, link)

    def _take_block(self, link: PeerLink, payload: bytes) -> None:
        """Add a block. Peers that missed a parent receive the whole chain when the tip moves."""
        block = EduBlock.parse(payload)
        with self._condition:
            changed = self._chain.add(block)
            if changed:
                self._mempool.retain(self._chain.utxo())
                self._store.save(self._chain.canonical_raw())
                self._condition.notify_all()
        if changed:
            self._broadcast_chain(link)

    def _read_tip(self, payload: bytes) -> None:
        """Reject a tip announcement whose height or length is impossible."""
        if len(payload) != TIP_PAYLOAD_BYTES:
            raise ValueError(PEER_ERROR)
        height = int.from_bytes(payload[:4], "little")
        if height > node_constants.MAX_BLOCK_COUNT:
            raise ValueError(PEER_ERROR)

    def _broadcast_chain(self, exclude: PeerLink | None) -> None:
        """Send every canonical block, in order, to every peer except exclude."""
        with self._condition:
            raws = self._chain.canonical_raw()
            links = [item for item in self._links if item is not exclude]
        for link in links:
            try:
                for raw in raws:
                    link.send(COMMAND_BLOCK, raw)
            except OSError:
                self._forget(link)

    def _broadcast_tx(self, raw: bytes, exclude: PeerLink | None) -> None:
        """Send one transaction to every peer except exclude."""
        with self._condition:
            links = [item for item in self._links if item is not exclude]
        for link in links:
            try:
                link.send(COMMAND_TX, raw)
            except OSError:
                self._forget(link)

    def _tip_bytes(self) -> bytes:
        """Return the tip height and internal block hash."""
        height, display_id, _work = self._chain.tip()
        if height < 0 or display_id == "":
            return struct.pack("<I", 0) + bytes(HASH_BYTES)
        return struct.pack("<I", height) + bytes.fromhex(display_id)[::-1]

    def _forget(self, link: PeerLink) -> None:
        """Drop a peer from the broadcast list."""
        with self._condition:
            if link in self._links:
                self._links.remove(link)
