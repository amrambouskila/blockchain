"""A node mines, saves, and follows the chain with the most work."""

from __future__ import annotations

import socket
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from edu_node import node_constants
from edu_node.node_constants import (
    BLOCK_ERROR,
    CHAIN_ERROR,
    COMMAND_BLOCK,
    COMMAND_HELLO,
    COMMAND_TIP,
    GENESIS_TIME,
    LOOPBACK_HOST,
    NODE_ID_BYTES,
    PEER_ERROR,
    SYNC_ERROR,
    TX_ERROR,
)
from edu_node.node_host import NodeHost
from edu_node.peer_frame import PeerFrame
from edu_node.peer_link import PeerLink
from tests.chain_blocks import ChainBlocks

_KEY = f"{1:064x}"
_OTHER = f"{3:064x}"


def _clock_at(moment: int) -> object:
    """Return a clock fixed at moment."""

    def clock() -> int:
        return moment

    return clock


def test_open_creates_genesis_and_reloads_it(tmp_path: Path) -> None:
    """A new directory is mined once, and opening it again keeps that block."""
    directory = tmp_path / "chain"
    first = NodeHost.open(directory, clock=_clock_at(GENESIS_TIME))  # type: ignore[arg-type]  # clock callable
    try:
        assert first.tip()[0] == 0
        assert first.listen() == first.port()
        assert first.page(0, 1)[0][0] == 0
        assert first.page(4, 1) == []
        tip = first.tip()
        first.wait_for_tip(tip[0], tip[1], 0.01)
    finally:
        first.close()
    second = NodeHost.open(directory, _KEY, create_genesis=False, clock=_clock_at(GENESIS_TIME))  # type: ignore[arg-type]
    try:
        assert second.tip() == tip
    finally:
        second.close()
        second.close()


def test_a_bad_key_does_not_create_a_directory_and_a_bad_file_does_not_open(tmp_path: Path) -> None:
    """The key is checked first, and a broken chain file is not loaded."""
    missing = tmp_path / "missing"
    with pytest.raises(ValueError, match="Private key"):
        NodeHost.open(missing, "zz")
    assert missing.exists() is False
    directory = tmp_path / "saved"
    host = NodeHost.open(directory, _KEY, clock=_clock_at(GENESIS_TIME))  # type: ignore[arg-type]
    host.close()
    (directory / "chain.json").write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match=CHAIN_ERROR):
        NodeHost.open(directory, _KEY, create_genesis=False, clock=_clock_at(GENESIS_TIME))  # type: ignore[arg-type]


def test_ports_transactions_and_peer_messages(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Bad ports and transactions are refused, and a bad frame closes only that peer."""
    host = NodeHost.open(tmp_path / "node", _KEY, clock=_clock_at(GENESIS_TIME))  # type: ignore[arg-type]
    try:
        for port in (True, 0, 65_536, host.port()):
            with pytest.raises(ValueError, match=PEER_ERROR):
                host.connect(port)  # type: ignore[arg-type]  # boundary port
        with pytest.raises(TimeoutError, match=SYNC_ERROR):
            host.wait_for_tip(3, "ab" * 32, 0.01)
        for raw in ("", "abc", "zz", "00"):
            with pytest.raises(ValueError, match=TX_ERROR):
                host.submit(raw)
        with pytest.raises(ValueError, match=TX_ERROR):
            host.submit(1)  # type: ignore[arg-type]  # hex is a string
        monkeypatch.setattr(node_constants, "MAX_TX_HEX", 2)
        with pytest.raises(ValueError, match=TX_ERROR):
            host.submit("abcd")
        monkeypatch.setattr(node_constants, "MAX_TX_HEX", 200_000)
        coin = host.block_at(0).transactions[0]
        payment = ChainBlocks().spend(_KEY, coin, 0, coin.outputs[0][0] - 250, coin.outputs[0][1])
        assert host.submit(payment.raw.hex()) == payment.display_id
        with pytest.raises(ValueError, match=TX_ERROR):
            host.submit(payment.raw.hex())
        host._take_tx(None, coin.raw)  # type: ignore[arg-type]  # no peer to broadcast to
        host._on_frame(None, COMMAND_HELLO, b"\x01" * NODE_ID_BYTES)  # type: ignore[arg-type]
        host._on_frame(None, COMMAND_TIP, b"\x00" * (4 + 32))  # type: ignore[arg-type]
        with pytest.raises(ValueError, match=PEER_ERROR):
            host._on_frame(None, COMMAND_HELLO, b"short")  # type: ignore[arg-type]
        with pytest.raises(ValueError, match=PEER_ERROR):
            host._on_frame(None, COMMAND_TIP, b"\x00")  # type: ignore[arg-type]
        with pytest.raises(ValueError, match=PEER_ERROR):
            host._on_frame(None, 9, b"")  # type: ignore[arg-type]
        with pytest.raises(ValueError, match=BLOCK_ERROR):
            host._on_frame(None, COMMAND_BLOCK, b"\x00")  # type: ignore[arg-type]
        monkeypatch.setattr(node_constants, "MAX_BLOCK_COUNT", -1)
        with pytest.raises(ValueError, match=PEER_ERROR):
            host._read_tip(b"\x00" * (4 + 32))
        _deliver(host.port(), COMMAND_BLOCK, b"\x00")
        assert host.tip()[0] == 0
    finally:
        host.close()


def _send_on_closed_peer(node: NodeHost, send: Callable[[], None]) -> None:
    """Append a closed socket, send through it, and require that peer to be gone."""
    owned, other = socket.socketpair()
    try:
        dead = PeerLink(owned)
        owned.close()
        with node._condition:
            node._links.append(dead)
        send()
        assert dead not in node._links
    finally:
        other.close()


def test_a_payment_is_relayed_and_a_dead_peer_is_dropped(tmp_path: Path) -> None:
    """Another node receives a payment, and a closed socket does not stop a later broadcast."""
    left = NodeHost.open(tmp_path / "left", _KEY, clock=_clock_at(GENESIS_TIME))  # type: ignore[arg-type]
    right = NodeHost.open(tmp_path / "right", _KEY, create_genesis=False, clock=_clock_at(GENESIS_TIME))  # type: ignore[arg-type]
    try:
        right.connect(left.port())
        height, block_id, _work = left.tip()
        right.wait_for_tip(height, block_id, 5)
        coin = left.block_at(0).transactions[0]
        payment = ChainBlocks().spend(_KEY, coin, 0, coin.outputs[0][0] - 100, coin.outputs[0][1])
        left.submit(payment.raw.hex())
        deadline = time.monotonic() + 5
        while payment.display_id not in right._mempool._txs and time.monotonic() < deadline:
            time.sleep(0.02)
        assert payment.display_id in right._mempool._txs
        assert left._links
        left._links[0]._socket.close()
        left.mine()
        _send_on_closed_peer(left, lambda: left._broadcast_chain(None))
        _send_on_closed_peer(left, lambda: left._broadcast_tx(payment.raw, None))
        owned, other = socket.socketpair()
        try:
            dead = PeerLink(owned)
            owned.close()
            left._greet(dead)
        finally:
            other.close()
        right.drop_peers()
    finally:
        left.close()
        right.close()


def test_three_nodes_adopt_the_chain_with_more_work(tmp_path: Path) -> None:
    """After a partition, the heavier fork replaces the earlier tip on the other nodes."""
    alpha = NodeHost.open(tmp_path / "a", _KEY, clock=_clock_at(GENESIS_TIME))  # type: ignore[arg-type]
    beta = NodeHost.open(tmp_path / "b", f"{2:064x}", create_genesis=False, clock=_clock_at(GENESIS_TIME))  # type: ignore[arg-type]
    gamma = NodeHost.open(tmp_path / "c", _OTHER, create_genesis=False, clock=_clock_at(GENESIS_TIME + 50))  # type: ignore[arg-type]
    try:
        beta.connect(alpha.port())
        gamma.connect(alpha.port())
        height, block_id, _work = alpha.tip()
        beta.wait_for_tip(height, block_id, 5)
        gamma.wait_for_tip(height, block_id, 5)
        gamma.drop_peers()
        time.sleep(0.2)
        alpha.mine()
        beta.wait_for_tip(alpha.tip()[0], alpha.tip()[1], 5)
        time.sleep(0.2)
        assert gamma.tip()[1] == block_id
        gamma.mine()
        gamma.mine()
        gamma.connect(alpha.port())
        gamma_height, gamma_id, _gamma_work = gamma.tip()
        alpha.wait_for_tip(gamma_height, gamma_id, 10)
        beta.wait_for_tip(gamma_height, gamma_id, 10)
        assert alpha.tip()[2] > 0
    finally:
        gamma.close()
        beta.close()
        alpha.close()


def test_a_received_block_extends_the_saved_chain(tmp_path: Path) -> None:
    """A new block from a peer is saved, and a duplicate does not replace the tip."""
    host = NodeHost.open(tmp_path / "extend", _KEY, clock=_clock_at(GENESIS_TIME))  # type: ignore[arg-type]
    try:
        original = host.tip()[1]
        extension = ChainBlocks().block(host._chain, _KEY)
        host._take_block(None, extension.raw)  # type: ignore[arg-type]  # broadcast has no peers
        assert host.tip()[1] == extension.display_id
        assert (tmp_path / "extend" / "chain.json").is_file()
        host._take_block(None, extension.raw)  # type: ignore[arg-type]
        assert host.tip()[1] == extension.display_id
        assert original != extension.display_id
    finally:
        host.close()


def _deliver(port: int, command: int, payload: bytes) -> None:
    """Send one frame to a node and wait until the node closes or stays quiet."""
    sock = socket.create_connection((LOOPBACK_HOST, port), timeout=2)
    sock.settimeout(0.5)
    try:
        sock.sendall(PeerFrame().encode(command, payload))
        try:
            sock.recv(16)
        except TimeoutError:
            return
    finally:
        sock.close()
