"""One TCP peer, with a send lock so greetings and broadcasts can share the socket."""

from __future__ import annotations

import socket
import threading

from edu_node import node_constants
from edu_node.node_constants import PEER_ERROR
from edu_node.peer_frame import PeerFrame


class PeerLink:
    """Read and write frames on one connected socket."""

    def __init__(self, sock: socket.socket) -> None:
        self._socket = sock
        self._buffer = bytearray()
        self._queue: list[tuple[int, bytes]] = []
        self._parser = PeerFrame()
        self._send_lock = threading.Lock()
        self._messages = 0
        self._bytes_in = 0
        self._closed = False

    def send(self, command: int, payload: bytes) -> None:
        """Send one frame."""
        raw = self._parser.encode(command, payload)
        with self._send_lock:
            self._socket.sendall(raw)

    def read_one(self) -> tuple[int, bytes] | None:
        """Return the next frame. An empty read means the peer closed the socket."""
        while not self._queue:
            chunk = self._socket.recv(node_constants.RECV_BYTES)
            if chunk == b"":
                return None
            self._bytes_in += len(chunk)
            if self._bytes_in > node_constants.MAX_PEER_BYTES:
                raise ValueError(PEER_ERROR)
            self._buffer.extend(chunk)
            self._queue.extend(self._parser.feed(self._buffer))
        self._messages += 1
        if self._messages > node_constants.MAX_PEER_MESSAGES:
            raise ValueError(PEER_ERROR)
        return self._queue.pop(0)

    def close(self) -> None:
        """Shut the socket down so a blocking read wakes up."""
        if self._closed:
            return
        self._closed = True
        try:
            self._socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self._socket.close()
