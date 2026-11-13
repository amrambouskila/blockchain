"""AES-256-GCM wallet files whose paths stay inside a chosen directory."""

from __future__ import annotations

import os
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from bitcoin_wallet import BitcoinWallet
from btc_wallet.wallet_constants import (
    MAX_PASSPHRASE_CHARACTERS,
    MAX_WALLET_FILE_BYTES,
    MAX_WALLET_PLAINTEXT_BYTES,
    SCRYPT_LENGTH,
    SCRYPT_N,
    SCRYPT_P,
    SCRYPT_R,
    WALLET_FILE_MAGIC,
    WALLET_NONCE_BYTES,
    WALLET_SALT_BYTES,
    WALLET_TAG_BYTES,
)
from constants import CREDENTIALS_FILE_MODE

_PATH_ERROR = "Wallet path must stay inside the wallet directory."
_FILE_ERROR = "Wallet file is invalid."
_ENCRYPTION_TEXT_ERROR = "Wallet encryption secret must be text of at most 1024 characters."
_PLAINTEXT_ERROR = "Wallet plaintext must be non-empty bytes within the size limit."


class WalletCipher:
    """Encrypt and decrypt a wallet file with Scrypt and AES-256-GCM."""

    def __init__(self, directory: Path) -> None:
        if not isinstance(directory, Path):
            raise TypeError("Wallet directory must be a path.")
        self._directory = directory.resolve()

    def encrypt(self, file_name: str, plaintext: bytes, encryption_secret: str) -> None:
        """Write plaintext to file_name so only the current user can read it."""
        path = self._path(file_name)
        body = _require_plaintext(plaintext)
        key = _derive_key(encryption_secret, salt := os.urandom(WALLET_SALT_BYTES))
        nonce = os.urandom(WALLET_NONCE_BYTES)
        ciphertext = AESGCM(key).encrypt(nonce, body, WALLET_FILE_MAGIC)
        _write_owner_only(path, WALLET_FILE_MAGIC + salt + nonce + ciphertext)

    def decrypt(self, file_name: str, encryption_secret: str) -> bytes:
        """Return the plaintext stored in file_name."""
        path = self._path(file_name)
        if not path.is_file():
            raise ValueError(_FILE_ERROR)
        if path.stat().st_size > MAX_WALLET_FILE_BYTES:
            raise ValueError(_FILE_ERROR)
        payload = path.read_bytes()
        header = len(WALLET_FILE_MAGIC) + WALLET_SALT_BYTES + WALLET_NONCE_BYTES + WALLET_TAG_BYTES
        if len(payload) < header or not payload.startswith(WALLET_FILE_MAGIC):
            raise ValueError(_FILE_ERROR)
        offset = len(WALLET_FILE_MAGIC)
        salt = payload[offset : offset + WALLET_SALT_BYTES]
        offset += WALLET_SALT_BYTES
        nonce = payload[offset : offset + WALLET_NONCE_BYTES]
        ciphertext = payload[offset + WALLET_NONCE_BYTES :]
        try:
            return AESGCM(_derive_key(encryption_secret, salt)).decrypt(nonce, ciphertext, WALLET_FILE_MAGIC)
        except InvalidTag:
            raise ValueError("Wallet file could not be decrypted.") from None

    def _path(self, file_name: str) -> Path:
        """Return file_name when it resolves inside this cipher's directory."""
        if not isinstance(file_name, str) or file_name == "":
            raise ValueError(_PATH_ERROR)
        resolved = (self._directory / file_name).resolve()
        if not resolved.is_relative_to(self._directory):
            raise ValueError(_PATH_ERROR)
        return resolved


def _require_plaintext(plaintext: bytes) -> bytes:
    """Return plaintext when it is non-empty and within the size limit."""
    if not isinstance(plaintext, bytes) or plaintext == b"" or len(plaintext) > MAX_WALLET_PLAINTEXT_BYTES:
        raise ValueError(_PLAINTEXT_ERROR)
    return plaintext


def _derive_key(encryption_secret: str, salt: bytes) -> bytes:
    """Return the AES key for encryption_secret without retaining the secret."""
    if (
        not isinstance(encryption_secret, str)
        or encryption_secret == ""
        or len(encryption_secret) > MAX_PASSPHRASE_CHARACTERS
    ):
        raise ValueError(_ENCRYPTION_TEXT_ERROR)
    kdf = Scrypt(salt=salt, length=SCRYPT_LENGTH, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    return kdf.derive(encryption_secret.encode("utf-8"))


def _write_owner_only(path: Path, payload: bytes) -> None:
    """Create path containing payload and limit it to the current user."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if os.name == "posix":
        descriptor = os.open(path, flags, CREDENTIALS_FILE_MODE)
    else:
        descriptor = os.open(path, flags)
    try:
        os.write(descriptor, payload)
    finally:
        os.close(descriptor)
    BitcoinWallet._restrict_to_owner(path)
