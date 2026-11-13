"""One socket peer can send, hit a rate limit, and close more than once."""

from __future__ import annotations

import socket

import pytest

from edu_node import node_constants
from edu_node.node_constants import PEER_ERROR
from edu_node.peer_frame import PeerFrame
from edu_node.peer_link import PeerLink


def _pair() -> tuple[socket.socket, socket.socket, PeerLink]:
    """Return a connected pair and a link on the left socket."""
    left, right = socket.socketpair()
    left.settimeout(2)
    right.settimeout(2)
    return left, right, PeerLink(left)


def test_frames_are_sent_and_read() -> None:
    """Two frames written together are returned one at a time, then a close returns nothing."""
    _left, right, link = _pair()
    try:
        raw = PeerFrame().encode(1, b"one") + PeerFrame().encode(2, b"two")
        right.sendall(raw)
        assert link.read_one() == (1, b"one")
        assert link.read_one() == (2, b"two")
        link.send(3, b"back")
        assert right.recv(64).startswith(b"EDU1")
        right.close()
        assert link.read_one() is None
    finally:
        link.close()
        right.close()


def test_byte_and_message_caps_close_the_peer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Too many bytes or too many frames raise the peer error."""
    byte_cap = node_constants.MAX_PEER_BYTES
    _left, right, link = _pair()
    try:
        monkeypatch.setattr(node_constants, "MAX_PEER_BYTES", 1)
        right.sendall(PeerFrame().encode(1, b"x"))
        with pytest.raises(ValueError, match=PEER_ERROR):
            link.read_one()
    finally:
        link.close()
        right.close()
    _left, right, link = _pair()
    try:
        monkeypatch.setattr(node_constants, "MAX_PEER_BYTES", byte_cap)
        monkeypatch.setattr(node_constants, "MAX_PEER_MESSAGES", 0)
        right.sendall(PeerFrame().encode(1, b"x"))
        with pytest.raises(ValueError, match=PEER_ERROR):
            link.read_one()
    finally:
        link.close()
        right.close()


def test_close_is_safe_when_the_socket_is_already_closed() -> None:
    """Shutting down a closed socket is ignored, and a second close does nothing."""
    left, right, link = _pair()
    left.close()
    link.close()
    link.close()
    right.close()
