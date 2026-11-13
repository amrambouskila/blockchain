"""The peer listener accepts loopback connections on an ephemeral port."""

from __future__ import annotations

import socket
import threading
import time

import pytest

from edu_node import node_constants
from edu_node.node_constants import LOOPBACK_HOST
from edu_node.peer_server import PeerServer


def test_listen_accepts_one_connection_and_can_be_called_twice(monkeypatch: pytest.MonkeyPatch) -> None:
    """The port stays stable, a timeout retries, and a client reaches the handler."""
    monkeypatch.setattr(node_constants, "PEER_ACCEPT_TIMEOUT", 0.01)
    seen: list[socket.socket] = []

    def handler(sock: socket.socket) -> None:
        seen.append(sock)
        sock.close()

    server = PeerServer(handler)
    assert server.port() == 0
    server._accept_loop()
    port = server.listen()
    assert server.listen() == port
    time.sleep(0.05)
    client = socket.create_connection((LOOPBACK_HOST, port), timeout=2)
    try:
        deadline = time.monotonic() + 2
        while not seen and time.monotonic() < deadline:
            time.sleep(0.01)
        assert seen
    finally:
        client.close()
        server.close()
        server.close()


def test_close_ignores_a_listener_error() -> None:
    """A listener that fails to close still lets the accept thread stop."""

    def handler(sock: socket.socket) -> None:
        sock.close()

    server = PeerServer(handler)
    server.listen()
    listener = server._listener
    thread = server._thread
    assert listener is not None
    assert thread is not None

    class _BadListener:
        def close(self) -> None:
            raise OSError("closed")

    server._listener = _BadListener()  # type: ignore[assignment]  # stand-in with a failing close
    server._thread = threading.current_thread()
    server.close()
    listener.close()
    thread.join(1)
