"""AES-256-GCM wallet files kept inside one directory."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from bitcoin_wallet import BitcoinWallet
from btc_wallet import wallet_cipher
from btc_wallet.wallet_cipher import WalletCipher
from constants import CREDENTIALS_FILE_MODE

_PLAINTEXT = b"wallet-record"


def test_round_trip_and_distinct_files(tmp_path: Path) -> None:
    """The same plaintext encrypts differently each time and decrypts with the same text."""
    cipher = WalletCipher(tmp_path)
    cipher.encrypt("one.bin", _PLAINTEXT, "correct horse")
    cipher.encrypt("two.bin", _PLAINTEXT, "correct horse")
    assert cipher.decrypt("one.bin", "correct horse") == _PLAINTEXT
    assert (tmp_path / "one.bin").read_bytes() != (tmp_path / "two.bin").read_bytes()


def test_wrong_text_and_tampering_fail_closed(tmp_path: Path) -> None:
    """A wrong encryption text or a flipped byte does not reveal the plaintext."""
    cipher = WalletCipher(tmp_path)
    cipher.encrypt("note.bin", _PLAINTEXT, "correct horse")
    with pytest.raises(ValueError, match="could not be decrypted") as caught:
        cipher.decrypt("note.bin", "wrong horse")
    assert "wrong horse" not in str(caught.value)
    path = tmp_path / "note.bin"
    payload = bytearray(path.read_bytes())
    payload[-1] ^= 0x01
    path.write_bytes(payload)
    with pytest.raises(ValueError, match="could not be decrypted"):
        cipher.decrypt("note.bin", "correct horse")


def test_missing_truncated_and_bad_magic_files(tmp_path: Path) -> None:
    """A missing, short, or unmarked file is rejected before decryption."""
    cipher = WalletCipher(tmp_path)
    with pytest.raises(ValueError, match="Wallet file is invalid"):
        cipher.decrypt("missing.bin", "correct horse")
    (tmp_path / "short.bin").write_bytes(b"BWE1")
    with pytest.raises(ValueError, match="Wallet file is invalid"):
        cipher.decrypt("short.bin", "correct horse")
    (tmp_path / "magic.bin").write_bytes(b"XXXX" + b"\x00" * 64)
    with pytest.raises(ValueError, match="Wallet file is invalid"):
        cipher.decrypt("magic.bin", "correct horse")
    folder = tmp_path / "folder.bin"
    folder.mkdir()
    with pytest.raises(ValueError, match="Wallet file is invalid"):
        cipher.decrypt("folder.bin", "correct horse")


def test_oversize_file_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A file larger than the cap is not read."""
    cipher = WalletCipher(tmp_path)
    cipher.encrypt("big.bin", _PLAINTEXT, "correct horse")
    monkeypatch.setattr(wallet_cipher, "MAX_WALLET_FILE_BYTES", 8)
    with pytest.raises(ValueError, match="Wallet file is invalid"):
        cipher.decrypt("big.bin", "correct horse")


@pytest.mark.parametrize("file_name", ["../outside.bin", "", 5])
def test_path_must_stay_inside_the_directory(tmp_path: Path, file_name: object) -> None:
    """Relative escape and empty names never create a file."""
    cipher = WalletCipher(tmp_path / "home")
    (tmp_path / "home").mkdir()
    with pytest.raises(ValueError, match="wallet directory"):
        cipher.encrypt(file_name, _PLAINTEXT, "correct horse")  # type: ignore[arg-type]  # boundary input


def test_absolute_paths_are_confined(tmp_path: Path) -> None:
    """An absolute path is allowed only when it still resolves inside the directory."""
    home = tmp_path / "home"
    home.mkdir()
    cipher = WalletCipher(home)
    inside = home / "inside.bin"
    cipher.encrypt(str(inside), _PLAINTEXT, "correct horse")
    assert cipher.decrypt(str(inside), "correct horse") == _PLAINTEXT
    with pytest.raises(ValueError, match="wallet directory"):
        cipher.encrypt(str(tmp_path / "outside.bin"), _PLAINTEXT, "correct horse")


def test_directory_must_be_a_path() -> None:
    """The cipher directory is a Path, not a string."""
    with pytest.raises(TypeError, match="Wallet directory"):
        WalletCipher("home")  # type: ignore[arg-type]  # non-Path boundary input


@pytest.mark.parametrize("plaintext", [b"", "", 5])
def test_plaintext_must_be_non_empty_bytes(tmp_path: Path, plaintext: object) -> None:
    """Empty and non-bytes plaintext is rejected before a key is derived."""
    cipher = WalletCipher(tmp_path)
    with pytest.raises(ValueError, match="plaintext"):
        cipher.encrypt("note.bin", plaintext, "correct horse")  # type: ignore[arg-type]  # boundary input


def test_plaintext_size_cap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Plaintext above the cap is rejected."""
    monkeypatch.setattr(wallet_cipher, "MAX_WALLET_PLAINTEXT_BYTES", 4)
    cipher = WalletCipher(tmp_path)
    with pytest.raises(ValueError, match="plaintext"):
        cipher.encrypt("note.bin", b"12345", "correct horse")


@pytest.mark.parametrize("encryption_text", ["", 5, "x" * 1025])
def test_encryption_text_is_bounded(tmp_path: Path, encryption_text: object) -> None:
    """The encryption text is a non-empty string of at most 1024 characters."""
    cipher = WalletCipher(tmp_path)
    with pytest.raises(ValueError, match="1024"):
        cipher.encrypt("note.bin", _PLAINTEXT, encryption_text)  # type: ignore[arg-type]  # boundary input


def test_posix_open_uses_owner_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The POSIX branch passes the owner-only mode to open."""
    modes: list[int | None] = []
    real_open = os.open

    def record_open(path: str | Path, flags: int, mode: int = -1) -> int:
        """Remember whether open received a mode, then open the file."""
        modes.append(None if mode == -1 else mode)
        if mode == -1:
            return real_open(path, flags)
        return real_open(path, flags, mode)

    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.setattr(os, "open", record_open)
    monkeypatch.setattr(Path, "chmod", lambda _path, _mode: None)
    WalletCipher(tmp_path).encrypt("posix.bin", _PLAINTEXT, "correct horse")
    assert modes == [CREDENTIALS_FILE_MODE]


def test_windows_open_skips_the_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The non-POSIX branch opens without a mode and still restricts the file."""
    modes: list[int | None] = []
    real_open = os.open
    restricted: list[Path] = []

    def record_open(path: str | Path, flags: int, mode: int = -1) -> int:
        """Remember whether open received a mode, then open the file."""
        modes.append(None if mode == -1 else mode)
        if mode == -1:
            return real_open(path, flags)
        return real_open(path, flags, mode)

    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.setattr(os, "open", record_open)
    monkeypatch.setattr(BitcoinWallet, "_restrict_to_owner", lambda path: restricted.append(path))
    WalletCipher(tmp_path).encrypt("windows.bin", _PLAINTEXT, "correct horse")
    assert modes == [None]
    assert restricted == [tmp_path / "windows.bin"]
