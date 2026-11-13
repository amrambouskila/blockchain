"""chain.json keeps the canonical block bytes and rejects anything else."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from edu_node import node_constants
from edu_node.chain_store import ChainStore
from edu_node.node_constants import CHAIN_ERROR, CHAIN_FILE_NAME


def test_a_missing_file_is_an_empty_chain_and_save_round_trips(tmp_path: Path) -> None:
    """The directory is created, a missing file loads as nothing, and save replaces it."""
    store = ChainStore(tmp_path / "nested" / "chain")
    assert store.load() == []
    store.save([b"\x01\x02", b""])
    assert store.load() == [b"\x01\x02", b""]
    assert json.loads((tmp_path / "nested" / "chain" / CHAIN_FILE_NAME).read_text(encoding="utf-8")) == {
        "blocks": ["0102", ""],
    }


def test_the_directory_argument_has_to_be_a_path(tmp_path: Path) -> None:
    """A string path is not opened."""
    with pytest.raises(ValueError, match=CHAIN_ERROR):
        ChainStore(tmp_path.as_posix())  # type: ignore[arg-type]  # a directory is a Path


@pytest.mark.parametrize(
    "payload",
    [
        "{",
        "[]",
        "{}",
        '{"blocks":{}}',
        '{"blocks":["abc"]}',
        '{"blocks":["zz"]}',
        '{"blocks":[1]}',
        '{"blocks":[],"x":1}',
    ],
)
def test_bad_json_is_rejected(tmp_path: Path, payload: str) -> None:
    """Only a one-key object of even hex strings is a chain file."""
    ChainStore(tmp_path)
    (tmp_path / CHAIN_FILE_NAME).write_text(payload, encoding="utf-8")
    with pytest.raises(ValueError, match=CHAIN_ERROR):
        ChainStore(tmp_path).load()


def test_bytes_that_are_not_utf8_are_rejected(tmp_path: Path) -> None:
    """A chain file has to decode as text."""
    ChainStore(tmp_path)
    (tmp_path / CHAIN_FILE_NAME).write_bytes(b"\xff")
    with pytest.raises(ValueError, match=CHAIN_ERROR):
        ChainStore(tmp_path).load()


def test_a_read_error_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An unreadable file is the same invalid-chain error, without the original message."""
    store = ChainStore(tmp_path)
    (tmp_path / CHAIN_FILE_NAME).write_text("{}", encoding="utf-8")

    def explode(self: Path, *args: object, **kwargs: object) -> str:
        del self, args, kwargs
        raise OSError("disk")

    monkeypatch.setattr(Path, "read_text", explode)
    with pytest.raises(ValueError, match=CHAIN_ERROR):
        store.load()


def test_the_size_cap_rejects_a_large_file_and_a_large_save(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Load and save both stop at the configured byte cap."""
    monkeypatch.setattr(node_constants, "MAX_CHAIN_FILE_BYTES", 2)
    store = ChainStore(tmp_path)
    (tmp_path / CHAIN_FILE_NAME).write_text("abcd", encoding="utf-8")
    with pytest.raises(ValueError, match=CHAIN_ERROR):
        store.load()
    (tmp_path / CHAIN_FILE_NAME).unlink()
    with pytest.raises(ValueError, match=CHAIN_ERROR):
        store.save([b"\x00"])


@pytest.mark.parametrize("blocks", [b"\x00", ["aa"]])
def test_save_needs_a_list_of_bytes(tmp_path: Path, blocks: list[bytes]) -> None:
    """Anything other than a list of bytes is refused before a file is replaced."""
    store = ChainStore(tmp_path)
    with pytest.raises(ValueError, match=CHAIN_ERROR):
        store.save(blocks)  # type: ignore[arg-type]  # boundary input


def test_the_chain_file_cannot_leave_its_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A resolved path outside the store directory is refused."""
    store = ChainStore(tmp_path)
    original = Path.resolve
    outside = Path("C:/outside") / CHAIN_FILE_NAME

    def resolve(self: Path, *args: object, **kwargs: object) -> Path:
        if self.name == CHAIN_FILE_NAME:
            return outside
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve)
    with pytest.raises(ValueError, match=CHAIN_ERROR):
        store.load()
    with pytest.raises(ValueError, match=CHAIN_ERROR):
        store.save([])
