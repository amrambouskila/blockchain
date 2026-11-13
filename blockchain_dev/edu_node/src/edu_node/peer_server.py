"""Accept loopback peers on an ephemeral port."""

from __future__ import annotations

import socket
import threading
from collections.abc import Callable

from edu_node import node_constants
from edu_node.node_constants import LOOPBACK_HOST


class PeerServer:
    """Listen on 127.0.0.1 and hand each accepted socket to a handler."""

    def __init__(self, handler: Callable[[socket.socket], None]) -> None:
        self._handler = handler
        self._listener: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._port = 0
        self._closed = False

    def listen(self) -> int:
        """Start the accept thread once and return its port."""
        if self._listener is not None:
            return self._port
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((LOOPBACK_HOST, 0))
        listener.listen()
        self._listener = listener
        self._port = int(listener.getsockname()[1])
        self._thread = threading.Thread(target=self._accept_loop, name="edu-peer-accept", daemon=True)
        self._thread.start()
        return self._port

    def port(self) -> int:
        """Return the bound port, or 0 before listen."""
        return self._port

    def close(self) -> None:
        """Stop accepting. Closing the listener wakes the accept thread."""
        self._closed = True
        listener = self._listener
        if listener is not None:
            try:
                listener.close()
            except OSError:
                pass
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(1.0)

    def _accept_loop(self) -> None:
        """Accept until the listener is closed. A timeout just tries again."""
        listener = self._listener
        if listener is None:
            return
        while not self._closed:
            try:
                listener.settimeout(node_constants.PEER_ACCEPT_TIMEOUT)
                client, _address = listener.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            threading.Thread(target=self._handler, args=(client,), daemon=True).start()
