"""Peer frames carry a magic prefix, a command, a length, and a SHA-256 checksum."""

from __future__ import annotations

import pytest

from edu_node import peer_frame as peer_frame_module
from edu_node.node_constants import NETWORK_MAGIC, PEER_ERROR
from edu_node.peer_frame import PeerFrame


def test_a_frame_round_trips_including_an_empty_payload() -> None:
    """One buffer can hold two frames, and leftover bytes stay in the buffer."""
    parser = PeerFrame()
    raw = parser.encode(0, b"") + parser.encode(4, b"ping")
    buffer = bytearray(raw + b"\x00")
    assert parser.feed(buffer) == [(0, b""), (4, b"ping")]
    assert buffer == b"\x00"
    assert parser.feed(buffer) == []


def test_short_buffers_wait_for_more_bytes() -> None:
    """A partial magic or a partial payload is not a frame yet."""
    parser = PeerFrame()
    assert parser.feed(bytearray(b"ED")) == []
    prefix = bytearray(NETWORK_MAGIC)
    assert parser.feed(prefix) == []
    encoded = parser.encode(1, b"abcde")
    assert parser.feed(bytearray(encoded[:-3])) == []


@pytest.mark.parametrize(
    ("command", "payload"),
    [(True, b""), (-1, b""), (256, b""), (1, "hi"), (1, b"\x00" * 2)],
)
def test_bad_commands_and_payloads_are_rejected(
    command: int,
    payload: bytes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Commands are one byte, and payloads are bytes inside the size cap."""
    monkeypatch.setattr(peer_frame_module, "MAX_FRAME_PAYLOAD", 1)
    with pytest.raises(ValueError, match=PEER_ERROR):
        PeerFrame().encode(command, payload)  # type: ignore[arg-type]  # boundary input


def test_a_bad_magic_length_or_checksum_is_rejected() -> None:
    """The parser refuses a frame that is not the bytes encode produced."""
    parser = PeerFrame()
    encoded = bytearray(parser.encode(2, b"xyz"))
    with pytest.raises(ValueError, match=PEER_ERROR):
        parser.feed(bytearray(b"XXXX" + encoded[4:]))
    huge = bytearray(NETWORK_MAGIC + b"\x01" + (2_000_000).to_bytes(4, "little"))
    with pytest.raises(ValueError, match=PEER_ERROR):
        parser.feed(huge)
    encoded[-1] ^= 0xFF
    with pytest.raises(ValueError, match=PEER_ERROR):
        parser.feed(encoded)
