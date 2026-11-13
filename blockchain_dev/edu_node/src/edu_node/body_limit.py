"""Reject oversized HTTP bodies before they are read."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping

from edu_node.node_constants import MAX_BODY_BYTES

Scope = MutableMapping[str, object]
Message = MutableMapping[str, object]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
AsgiApp = Callable[[Scope, Receive, Send], Awaitable[None]]

_LIMITED_METHODS = frozenset({"POST", "PUT", "PATCH"})


class BodyLimit:
    """Stop POST, PUT, and PATCH requests that omit a length or exceed the cap."""

    def __init__(self, app: AsgiApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Pass websocket and other non-HTTP scopes through. Limited HTTP methods need a length."""
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return
        method = scope.get("method")
        if method not in _LIMITED_METHODS:
            await self._app(scope, receive, send)
            return
        length = _content_length(scope.get("headers"))
        if isinstance(length, int):
            if length > MAX_BODY_BYTES:
                await _reject(send, 413)
                return
            await self._app(scope, receive, send)
            return
        await _reject(send, 411 if length == "missing" else 400)


def _content_length(headers: object) -> int | str:
    """Return the length, 'missing' when the header is absent, or 'bad' when it is not a size."""
    if not isinstance(headers, list):
        return "missing"
    for name, value in headers:
        if not isinstance(name, bytes) or not isinstance(value, bytes) or name.lower() != b"content-length":
            continue
        try:
            parsed = int(value.decode("ascii"))
        except (UnicodeError, ValueError):
            return "bad"
        if parsed < 0:
            return "bad"
        return parsed
    return "missing"


async def _reject(send: Send, status: int) -> None:
    """Send an empty response with status."""
    await send({"type": "http.response.start", "status": status, "headers": []})
    await send({"type": "http.response.body", "body": b""})
