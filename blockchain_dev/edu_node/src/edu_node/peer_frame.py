"""Length-prefixed peer frames: magic, command, length, payload, and a SHA-256 checksum."""

from __future__ import annotations

import hashlib
import struct

from edu_node.node_constants import (
    CHECKSUM_BYTES,
    FRAME_PREFIX_BYTES,
    MAX_FRAME_PAYLOAD,
    NETWORK_MAGIC,
    PEER_ERROR,
)


class PeerFrame:
    """Encode and split educational peer frames."""

    def encode(self, command: int, payload: bytes) -> bytes:
        """Return one frame. The checksum is the first four bytes of SHA-256(payload)."""
        if type(command) is not int or not 0 <= command <= 255:
            raise ValueError(PEER_ERROR)
        if not isinstance(payload, bytes) or len(payload) > MAX_FRAME_PAYLOAD:
            raise ValueError(PEER_ERROR)
        checksum = hashlib.sha256(payload).digest()[:CHECKSUM_BYTES]
        return NETWORK_MAGIC + bytes([command]) + struct.pack("<I", len(payload)) + payload + checksum

    def feed(self, buffer: bytearray) -> list[tuple[int, bytes]]:
        """Remove every complete frame from buffer and return those frames."""
        frames: list[tuple[int, bytes]] = []
        while True:
            frame = self._pop(buffer)
            if frame is None:
                return frames
            frames.append(frame)

    def _pop(self, buffer: bytearray) -> tuple[int, bytes] | None:
        """Return one frame, or None when more bytes are required."""
        if len(buffer) < len(NETWORK_MAGIC):
            return None
        if bytes(buffer[: len(NETWORK_MAGIC)]) != NETWORK_MAGIC:
            raise ValueError(PEER_ERROR)
        if len(buffer) < FRAME_PREFIX_BYTES:
            return None
        command = buffer[4]
        length = int.from_bytes(buffer[5:FRAME_PREFIX_BYTES], "little")
        if length > MAX_FRAME_PAYLOAD:
            raise ValueError(PEER_ERROR)
        total = FRAME_PREFIX_BYTES + length + CHECKSUM_BYTES
        if len(buffer) < total:
            return None
        payload = bytes(buffer[FRAME_PREFIX_BYTES : FRAME_PREFIX_BYTES + length])
        checksum = bytes(buffer[FRAME_PREFIX_BYTES + length : total])
        if checksum != hashlib.sha256(payload).digest()[:CHECKSUM_BYTES]:
            raise ValueError(PEER_ERROR)
        del buffer[:total]
        return command, payload
