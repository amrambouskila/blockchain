"""BIP-32 extended keys from a seed, a path, or a Base58Check xprv/xpub string."""

from __future__ import annotations

import hashlib
import hmac
import re
from typing import Self

import base58
import ecdsa
from ecdsa.ellipticcurve import INFINITY, Point
from ecdsa.errors import MalformedPointError

from bitcoin_wallet import BitcoinWallet
from btc_wallet.wallet_constants import (
    BIP32_MAINNET_PRIVATE_VERSION,
    BIP32_MAINNET_PUBLIC_VERSION,
    BIP32_TESTNET_PRIVATE_VERSION,
    BIP32_TESTNET_PUBLIC_VERSION,
    CHAIN_CODE_BYTES,
    EXTENDED_KEY_BYTES,
    FINGERPRINT_BYTES,
    HARDENED_INDEX,
    HMAC_KEY_BITCOIN_SEED,
    MAX_CHILD_INDEX,
    MAX_DEPTH,
    PRIVATE_KEY_PREFIX,
    SEED_MAX_BYTES,
    SEED_MIN_BYTES,
)
from constants import (
    COMPRESSED_PUBLIC_KEY_BYTES,
    COMPRESSED_PUBLIC_KEY_EVEN_PREFIX,
    COMPRESSED_PUBLIC_KEY_ODD_PREFIX,
    PRIVATE_KEY_BYTES,
)

_PATH_HEAD = re.compile(r"^[mM]$")
_INDEX_STEP = re.compile(r"^(\d+)([hH'])?$")
_EXTENDED_KEY_ERROR = "Extended key is invalid."
_PATH_ERROR = "Derivation path is invalid."


class ExtendedKey:
    """One BIP-32 node: a secp256k1 key, a chain code, and its place in the tree."""

    def __init__(
        self,
        *,
        private_key: bytes | None,
        public_key: bytes,
        chain_code: bytes,
        depth: int,
        parent_fingerprint: bytes,
        child_index: int,
        testnet: bool,
    ) -> None:
        if type(testnet) is not bool or not _valid_chain_code(chain_code):
            raise ValueError(_EXTENDED_KEY_ERROR)
        if type(depth) is not int or not 0 <= depth <= MAX_DEPTH:
            raise ValueError(_EXTENDED_KEY_ERROR)
        if not isinstance(parent_fingerprint, bytes) or len(parent_fingerprint) != FINGERPRINT_BYTES:
            raise ValueError(_EXTENDED_KEY_ERROR)
        if type(child_index) is not int or not 0 <= child_index <= MAX_CHILD_INDEX:
            raise ValueError(_EXTENDED_KEY_ERROR)
        if depth == 0 and (parent_fingerprint != bytes(FINGERPRINT_BYTES) or child_index != 0):
            raise ValueError(_EXTENDED_KEY_ERROR)
        checked_public = _require_public_key(public_key)
        if private_key is not None:
            private_hex = _require_private_key(private_key)
            if checked_public != bytes.fromhex(BitcoinWallet.derive_public_key(private_hex)):
                raise ValueError(_EXTENDED_KEY_ERROR)
        self._private_key = private_key
        self._public_key = checked_public
        self._chain_code = chain_code
        self._depth = depth
        self._parent_fingerprint = parent_fingerprint
        self._child_index = child_index
        self._testnet = testnet

    @classmethod
    def from_seed(cls, seed: bytes, *, testnet: bool = False) -> Self:
        """Return the master key for a 16- to 64-byte seed."""
        if not isinstance(seed, bytes) or not SEED_MIN_BYTES <= len(seed) <= SEED_MAX_BYTES:
            raise ValueError(_EXTENDED_KEY_ERROR)
        digest = hmac.new(HMAC_KEY_BITCOIN_SEED, seed, hashlib.sha512).digest()
        secret = _tweak_from_left(digest[:PRIVATE_KEY_BYTES])
        if secret is None or secret == 0:  # pragma: no cover - out-of-range HMAC output is tested on the helper
            raise ValueError(_EXTENDED_KEY_ERROR)
        private_key = secret.to_bytes(PRIVATE_KEY_BYTES, "big")
        public_key = bytes.fromhex(BitcoinWallet.derive_public_key(private_key.hex()))
        return cls(
            private_key=private_key,
            public_key=public_key,
            chain_code=digest[PRIVATE_KEY_BYTES:],
            depth=0,
            parent_fingerprint=bytes(FINGERPRINT_BYTES),
            child_index=0,
            testnet=testnet,
        )

    @classmethod
    def parse(cls, encoded: str) -> Self:
        """Return the extended key stored in a Base58Check xprv, xpub, tprv, or tpub string."""
        if not isinstance(encoded, str) or encoded == "":
            raise ValueError(_EXTENDED_KEY_ERROR)
        try:
            payload = base58.b58decode_check(encoded)
        except ValueError:
            raise ValueError(_EXTENDED_KEY_ERROR) from None
        if len(payload) != EXTENDED_KEY_BYTES:
            raise ValueError(_EXTENDED_KEY_ERROR)
        version = payload[:4]
        network = _network_for_version(version)
        if network is None:
            raise ValueError(_EXTENDED_KEY_ERROR)
        depth = payload[4]
        parent_fingerprint = payload[5:9]
        child_index = int.from_bytes(payload[9:13], "big")
        chain_code = payload[13:45]
        key_data = payload[45:]
        testnet = network == "testnet"
        if version in {BIP32_MAINNET_PRIVATE_VERSION, BIP32_TESTNET_PRIVATE_VERSION}:
            if len(key_data) != COMPRESSED_PUBLIC_KEY_BYTES or key_data[:1] != PRIVATE_KEY_PREFIX:
                raise ValueError(_EXTENDED_KEY_ERROR)
            private_key = key_data[1:]
            private_hex = _require_private_key(private_key)
            public_key = bytes.fromhex(BitcoinWallet.derive_public_key(private_hex))
            return cls(
                private_key=private_key,
                public_key=public_key,
                chain_code=chain_code,
                depth=depth,
                parent_fingerprint=parent_fingerprint,
                child_index=child_index,
                testnet=testnet,
            )
        return cls(
            private_key=None,
            public_key=key_data,
            chain_code=chain_code,
            depth=depth,
            parent_fingerprint=parent_fingerprint,
            child_index=child_index,
            testnet=testnet,
        )

    def serialize(self) -> str:
        """Return the Base58Check form of this extended key."""
        if self._testnet:
            version = BIP32_TESTNET_PRIVATE_VERSION if self._private_key is not None else BIP32_TESTNET_PUBLIC_VERSION
        else:
            version = BIP32_MAINNET_PRIVATE_VERSION if self._private_key is not None else BIP32_MAINNET_PUBLIC_VERSION
        key_data = PRIVATE_KEY_PREFIX + self._private_key if self._private_key is not None else self._public_key
        payload = (
            version
            + bytes([self._depth])
            + self._parent_fingerprint
            + self._child_index.to_bytes(FINGERPRINT_BYTES, "big")
            + self._chain_code
            + key_data
        )
        return base58.b58encode_check(payload).decode()

    def neuter(self) -> Self:
        """Return the public extended key for this node."""
        return type(self)(
            private_key=None,
            public_key=self._public_key,
            chain_code=self._chain_code,
            depth=self._depth,
            parent_fingerprint=self._parent_fingerprint,
            child_index=self._child_index,
            testnet=self._testnet,
        )

    def derive(self, index: int) -> Self:
        """Return the child extended key at index, including hardened indexes at or above 2^31."""
        if type(index) is not int or not 0 <= index <= MAX_CHILD_INDEX:
            raise ValueError(_PATH_ERROR)
        if self._depth == MAX_DEPTH:
            raise ValueError(_PATH_ERROR)
        hardened = index >= HARDENED_INDEX
        if self._private_key is None and hardened:
            raise ValueError("Hardened child keys need the private key.")
        parent_fingerprint = BitcoinWallet._hash160(self._public_key)[:FINGERPRINT_BYTES]
        if self._private_key is not None:
            data_key = PRIVATE_KEY_PREFIX + self._private_key if hardened else self._public_key
            left, chain_code = _hmac_halves(self._chain_code, data_key + index.to_bytes(FINGERPRINT_BYTES, "big"))
            child_secret = _child_secret(int.from_bytes(self._private_key, "big"), _tweak_from_left(left))
            if child_secret is None:  # pragma: no cover - invalid tweak is tested on _child_secret
                raise ValueError(_EXTENDED_KEY_ERROR)
            private_key = child_secret.to_bytes(PRIVATE_KEY_BYTES, "big")
            public_key = bytes.fromhex(BitcoinWallet.derive_public_key(private_key.hex()))
        else:
            data = self._public_key + index.to_bytes(FINGERPRINT_BYTES, "big")
            left, chain_code = _hmac_halves(self._chain_code, data)
            tweak = _tweak_from_left(left)
            parent_point = ecdsa.VerifyingKey.from_string(self._public_key, curve=ecdsa.SECP256k1).pubkey.point
            child_point = _child_public_point(tweak, parent_point)
            if child_point is None:  # pragma: no cover - infinity result is tested on _child_public_point
                raise ValueError(_EXTENDED_KEY_ERROR)
            private_key = None
            public_key = _compress_point(child_point)
        return type(self)(
            private_key=private_key,
            public_key=public_key,
            chain_code=chain_code,
            depth=self._depth + 1,
            parent_fingerprint=parent_fingerprint,
            child_index=index,
            testnet=self._testnet,
        )

    def derive_path(self, path: str) -> Self:
        """Return the node at path, where m keeps the private key and M drops it first."""
        head, indexes = _parse_path(path)
        if head == "m" and self._private_key is None:
            raise ValueError("A private path needs the private key.")
        current: Self = self.neuter() if head == "M" and self._private_key is not None else self
        for index in indexes:
            current = current.derive(index)
        return current

    def private_hex(self) -> str:
        """Return the 32-byte private key as hex."""
        if self._private_key is None:
            raise ValueError("This extended key has no private key.")
        return self._private_key.hex()

    def public_hex(self) -> str:
        """Return the compressed public key as hex."""
        return self._public_key.hex()

    def is_testnet(self) -> bool:
        """Return whether this key uses the testnet version bytes."""
        return self._testnet


def _valid_chain_code(chain_code: bytes) -> bool:
    """Return whether chain_code is 32 bytes."""
    return isinstance(chain_code, bytes) and len(chain_code) == CHAIN_CODE_BYTES


def _require_private_key(private_key: bytes) -> str:
    """Return the normalized hex private key, or raise when it is outside the curve."""
    if not isinstance(private_key, bytes) or len(private_key) != PRIVATE_KEY_BYTES:
        raise ValueError(_EXTENDED_KEY_ERROR)
    normalized = BitcoinWallet._private_key_hex_from_int(int.from_bytes(private_key, "big"))
    if normalized is None:
        raise ValueError(_EXTENDED_KEY_ERROR)
    return normalized


def _require_public_key(public_key: bytes) -> bytes:
    """Return public_key when it is a compressed point on secp256k1."""
    if (
        not isinstance(public_key, bytes)
        or len(public_key) != COMPRESSED_PUBLIC_KEY_BYTES
        or public_key[:1] not in {b"\x02", b"\x03"}
    ):
        raise ValueError(_EXTENDED_KEY_ERROR)
    try:
        ecdsa.VerifyingKey.from_string(public_key, curve=ecdsa.SECP256k1)
    except (MalformedPointError, ValueError):
        raise ValueError(_EXTENDED_KEY_ERROR) from None
    return public_key


def _network_for_version(version: bytes) -> str | None:
    """Return mainnet or testnet for a BIP-32 version, or None when it is unknown."""
    if version in {BIP32_MAINNET_PUBLIC_VERSION, BIP32_MAINNET_PRIVATE_VERSION}:
        return "mainnet"
    if version in {BIP32_TESTNET_PUBLIC_VERSION, BIP32_TESTNET_PRIVATE_VERSION}:
        return "testnet"
    return None


def _hmac_halves(key: bytes, data: bytes) -> tuple[bytes, bytes]:
    """Return the left and right halves of HMAC-SHA512(key, data)."""
    digest = hmac.new(key, data, hashlib.sha512).digest()
    return digest[:PRIVATE_KEY_BYTES], digest[PRIVATE_KEY_BYTES:]


def _tweak_from_left(left: bytes) -> int | None:
    """Return the integer tweak when it is below the curve order, including zero."""
    tweak = int.from_bytes(left, "big")
    if tweak >= ecdsa.SECP256k1.order:
        return None
    return tweak


def _child_secret(parent: int, tweak: int | None) -> int | None:
    """Return the child private key, or None when the tweak or the sum is unusable."""
    if tweak is None or tweak >= ecdsa.SECP256k1.order:
        return None
    child = (parent + tweak) % ecdsa.SECP256k1.order
    if child == 0:
        return None
    return child


def _child_public_point(tweak: int | None, parent: Point) -> Point | None:
    """Return the child public point, or None when the tweak is unusable or the sum is infinity."""
    if tweak is None or tweak >= ecdsa.SECP256k1.order:
        return None
    if tweak == 0:
        return parent
    child = tweak * ecdsa.SECP256k1.generator + parent
    if child == INFINITY:
        return None
    return child


def _compress_point(point: Point) -> bytes:
    """Return the SEC compressed form of point."""
    prefix = COMPRESSED_PUBLIC_KEY_EVEN_PREFIX if point.y() % 2 == 0 else COMPRESSED_PUBLIC_KEY_ODD_PREFIX
    return prefix + point.x().to_bytes(PRIVATE_KEY_BYTES, "big")


def _parse_path(path: str) -> tuple[str, list[int]]:
    """Return the m/M head and the child indexes in path."""
    if not isinstance(path, str) or path == "":
        raise ValueError(_PATH_ERROR)
    parts = path.split("/")
    if _PATH_HEAD.fullmatch(parts[0]) is None:
        raise ValueError(_PATH_ERROR)
    indexes: list[int] = []
    for part in parts[1:]:
        matched = _INDEX_STEP.fullmatch(part)
        if matched is None:
            raise ValueError(_PATH_ERROR)
        number, mark = matched.group(1), matched.group(2)
        if len(number) > 1 and number.startswith("0"):
            raise ValueError(_PATH_ERROR)
        value = int(number)
        if mark is not None:
            if value >= HARDENED_INDEX:
                raise ValueError(_PATH_ERROR)
            value += HARDENED_INDEX
        elif value > MAX_CHILD_INDEX:
            raise ValueError(_PATH_ERROR)
        indexes.append(value)
    return parts[0], indexes
