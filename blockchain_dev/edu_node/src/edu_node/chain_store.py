"""Save and reload the canonical chain as JSON block hex."""

from __future__ import annotations

import json
import re
from pathlib import Path

from edu_node import node_constants
from edu_node.node_constants import CHAIN_ERROR, CHAIN_FILE_NAME

_HEX = re.compile(r"[0-9a-fA-F]*")


class ChainStore:
    """Read and write chain.json inside one directory."""

    def __init__(self, directory: Path) -> None:
        if not isinstance(directory, Path):
            raise ValueError(CHAIN_ERROR)
        self._directory = directory.resolve()
        self._directory.mkdir(parents=True, exist_ok=True)

    def load(self) -> list[bytes]:
        """Return stored block bytes. A missing file is an empty chain."""
        path = self._chain_path()
        if not path.exists():
            return []
        if path.stat().st_size > node_constants.MAX_CHAIN_FILE_BYTES:
            raise ValueError(CHAIN_ERROR)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            raise ValueError(CHAIN_ERROR) from None
        return _blocks_from_payload(payload)

    def save(self, raw_blocks: list[bytes]) -> None:
        """Replace chain.json with raw_blocks, using a temporary file in this directory."""
        if not isinstance(raw_blocks, list) or any(not isinstance(item, bytes) for item in raw_blocks):
            raise ValueError(CHAIN_ERROR)
        encoded = json.dumps({"blocks": [item.hex() for item in raw_blocks]}, separators=(",", ":")).encode("utf-8")
        if len(encoded) > node_constants.MAX_CHAIN_FILE_BYTES:
            raise ValueError(CHAIN_ERROR)
        path = self._chain_path()
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_bytes(encoded)
        temporary.replace(path)

    def _chain_path(self) -> Path:
        """Return chain.json when it stays inside this directory."""
        path = (self._directory / CHAIN_FILE_NAME).resolve()
        if not path.is_relative_to(self._directory):
            raise ValueError(CHAIN_ERROR)
        return path


def _blocks_from_payload(payload: object) -> list[bytes]:
    """Return block bytes from a one-key JSON object."""
    if not isinstance(payload, dict) or set(payload) != {"blocks"}:
        raise ValueError(CHAIN_ERROR)
    rows = payload["blocks"]
    if not isinstance(rows, list):
        raise ValueError(CHAIN_ERROR)
    raw_blocks: list[bytes] = []
    for row in rows:
        if not isinstance(row, str) or len(row) % 2 != 0 or _HEX.fullmatch(row) is None:
            raise ValueError(CHAIN_ERROR)
        raw_blocks.append(bytes.fromhex(row))
    return raw_blocks
