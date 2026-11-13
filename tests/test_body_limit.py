"""POST, PUT, and PATCH need a content length, and that length has to fit the cap."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from edu_node.body_limit import BodyLimit
from edu_node.node_constants import MAX_BODY_BYTES

Message = dict[str, object]
Send = Callable[[Message], Awaitable[None]]


def _exercise(scope: dict[str, object]) -> list[Message]:
    """Run the middleware and return the messages it sent."""
    sent: list[Message] = []

    async def receive() -> Message:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Message) -> None:
        sent.append(message)

    async def app(scope: dict[str, object], receive: Callable[[], Awaitable[Message]], send: Send) -> None:
        del scope, receive
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    asyncio.run(BodyLimit(app)(scope, receive, send))
    return sent


def test_non_limited_scopes_reach_the_app() -> None:
    """Websocket and GET requests are not measured."""
    assert _exercise({"type": "websocket"})[0]["status"] == 200
    assert _exercise({"type": "http", "method": "GET"})[0]["status"] == 200


def test_missing_and_bad_lengths_are_rejected() -> None:
    """No header is 411, and a header that is not a size is 400."""
    missing = _exercise({"type": "http", "method": "POST"})
    assert missing[0]["status"] == 411
    empty = _exercise({"type": "http", "method": "PUT", "headers": []})
    assert empty[0]["status"] == 411
    for value in (b"\xff", b"no", b"-1"):
        rejected = _exercise({"type": "http", "method": "PATCH", "headers": [(b"content-length", value)]})
        assert rejected[0]["status"] == 400
        assert rejected[1]["body"] == b""


def test_a_declared_length_is_capped() -> None:
    """A length inside the cap reaches the app, and a larger one is 413."""
    headers = [(b"host", b"localhost"), (1, 2), (b"content-length", b"0")]
    assert _exercise({"type": "http", "method": "POST", "headers": headers})[0]["status"] == 200
    allowed = str(MAX_BODY_BYTES).encode("ascii")
    assert _exercise({"type": "http", "method": "POST", "headers": [(b"content-length", allowed)]})[0]["status"] == 200
    huge = str(MAX_BODY_BYTES + 1).encode("ascii")
    rejected = _exercise({"type": "http", "method": "POST", "headers": [(b"content-length", huge)]})
    assert rejected[0]["status"] == 413
