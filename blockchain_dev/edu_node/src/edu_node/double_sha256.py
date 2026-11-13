"""Double SHA-256 for headers, transactions, and Merkle leaves."""

from __future__ import annotations

import hashlib


def double_sha256(payload: bytes) -> bytes:
    """Return SHA-256 of SHA-256 of payload."""
    return hashlib.sha256(hashlib.sha256(payload).digest()).digest()
