"""Pay-to-script-hash multisig redeem scripts with BIP-67 pubkey ordering."""

from __future__ import annotations

import base58
import ecdsa
from ecdsa.errors import MalformedPointError

from bitcoin_wallet import BitcoinWallet
from btc_wallet.wallet_constants import (
    MULTISIG_MAX,
    MULTISIG_MIN,
    OP_CHECKMULTISIG,
    OP_WITNESS_VERSION_BASE,
    P2SH_SCRIPT_PREFIX,
    P2SH_SCRIPT_SUFFIX,
    PUSH_COMPRESSED_PUBLIC_KEY,
)
from constants import COMPRESSED_PUBLIC_KEY_BYTES, HASH160_BYTES, P2SH_VERSION

_MULTISIG_ERROR = "Multisig redeem script is invalid."


class MultisigScript:
    """A P2SH multisig address whose compressed public keys are sorted lexicographically."""

    def __init__(self, public_keys_hex: list[str], required: int) -> None:
        public_keys = _require_public_keys(public_keys_hex)
        if type(required) is not int or not MULTISIG_MIN <= required <= len(public_keys):
            raise ValueError(_MULTISIG_ERROR)
        ordered = tuple(sorted(public_keys))
        pushes = b"".join(bytes([PUSH_COMPRESSED_PUBLIC_KEY]) + public_key for public_key in ordered)
        self._redeem_script = (
            bytes([OP_WITNESS_VERSION_BASE + required])
            + pushes
            + bytes([OP_WITNESS_VERSION_BASE + len(ordered), OP_CHECKMULTISIG])
        )
        self._address = _p2sh_address(self._redeem_script)

    def redeem_script(self) -> bytes:
        """Return the redeem script."""
        return self._redeem_script

    def address(self) -> str:
        """Return the mainnet P2SH address for the redeem script."""
        return self._address

    def script_pubkey(self) -> bytes:
        """Return the P2SH scriptPubKey."""
        digest = BitcoinWallet._hash160(self._redeem_script)
        return bytes([P2SH_SCRIPT_PREFIX, HASH160_BYTES]) + digest + bytes([P2SH_SCRIPT_SUFFIX])


def _require_public_keys(public_keys_hex: list[str]) -> list[bytes]:
    """Return the unique compressed public keys, or raise when the list is not usable."""
    if not isinstance(public_keys_hex, list) or not MULTISIG_MIN <= len(public_keys_hex) <= MULTISIG_MAX:
        raise ValueError(_MULTISIG_ERROR)
    public_keys: list[bytes] = []
    for public_key_hex in public_keys_hex:
        public_keys.append(_require_compressed_public_key(public_key_hex))
    if len(set(public_keys)) != len(public_keys):
        raise ValueError(_MULTISIG_ERROR)
    return public_keys


def _require_compressed_public_key(public_key_hex: str) -> bytes:
    """Return one compressed secp256k1 public key."""
    if not isinstance(public_key_hex, str) or len(public_key_hex) != COMPRESSED_PUBLIC_KEY_BYTES * 2:
        raise ValueError(_MULTISIG_ERROR)
    try:
        public_key = bytes.fromhex(public_key_hex)
    except ValueError:
        raise ValueError(_MULTISIG_ERROR) from None
    if public_key[:1] not in {b"\x02", b"\x03"}:
        raise ValueError(_MULTISIG_ERROR)
    try:
        ecdsa.VerifyingKey.from_string(public_key, curve=ecdsa.SECP256k1)
    except (MalformedPointError, ValueError):
        raise ValueError(_MULTISIG_ERROR) from None
    return public_key


def _p2sh_address(redeem_script: bytes) -> str:
    """Return the mainnet P2SH address for redeem_script."""
    payload = P2SH_VERSION + BitcoinWallet._hash160(redeem_script)
    return base58.b58encode_check(payload).decode()
