"""Native SegWit addresses: Bech32 for witness version 0 and Bech32m for versions 1 through 16."""

from __future__ import annotations

import hashlib

import bech32
import ecdsa
from ecdsa.errors import MalformedPointError

from bitcoin_wallet import BitcoinWallet
from btc_wallet.wallet_constants import (
    BECH32_CHECKSUM_LENGTH,
    BECH32_CONST,
    BECH32_HRP_MAX_LENGTH,
    BECH32_MAX_LENGTH,
    BECH32M_CONST,
    HRP_MAINNET,
    HRP_TESTNET,
    OP_WITNESS_VERSION_BASE,
    WITNESS_PROGRAM_MAX_BYTES,
    WITNESS_PROGRAM_MIN_BYTES,
    WITNESS_V0_PROGRAM_LONG,
    WITNESS_V0_PROGRAM_SHORT,
    WITNESS_VERSION_MAX,
)
from constants import COMPRESSED_PUBLIC_KEY_BYTES

_ADDRESS_ERROR = "SegWit address is invalid."


class SegwitAddress:
    """Encode and decode native SegWit addresses with the bech32 library's checksum."""

    @staticmethod
    def p2wpkh(public_key_hex: str, *, hrp: str = HRP_MAINNET) -> str:
        """Return the version-0 pay-to-witness-public-key-hash address for a compressed public key."""
        program = BitcoinWallet._hash160(_require_compressed_public_key(public_key_hex))
        return SegwitAddress.encode(0, program, hrp=hrp)

    @staticmethod
    def p2wsh(script: bytes, *, hrp: str = HRP_MAINNET) -> str:
        """Return the version-0 pay-to-witness-script-hash address for script."""
        if not isinstance(script, bytes) or script == b"":
            raise ValueError(_ADDRESS_ERROR)
        return SegwitAddress.encode(0, hashlib.sha256(script).digest(), hrp=hrp)

    @staticmethod
    def encode(witness_version: int, program: bytes, *, hrp: str = HRP_MAINNET) -> str:
        """Return the address for witness_version and program."""
        _require_hrp(hrp)
        if type(witness_version) is not int or not 0 <= witness_version <= WITNESS_VERSION_MAX:
            raise ValueError(_ADDRESS_ERROR)
        if not isinstance(program, bytes) or not _program_length_ok(witness_version, len(program)):
            raise ValueError(_ADDRESS_ERROR)
        if witness_version == 0:
            encoded = bech32.encode(hrp, witness_version, program)
        else:
            converted = bech32.convertbits(program, 8, 5)
            if converted is None:  # pragma: no cover - an 8-bit program always converts to 5-bit groups
                raise ValueError(_ADDRESS_ERROR)
            encoded = _encode_bech32m(hrp, [witness_version, *converted])
        if not isinstance(encoded, str) or SegwitAddress.decode(encoded, hrp=hrp) != (witness_version, program):
            raise ValueError(_ADDRESS_ERROR)
        return encoded

    @staticmethod
    def decode(address: str, *, hrp: str = HRP_MAINNET) -> tuple[int, bytes]:
        """Return the witness version and program for address."""
        _require_hrp(hrp)
        decoded = _decode(address, hrp)
        if decoded is None:
            raise ValueError(_ADDRESS_ERROR)
        return decoded

    @staticmethod
    def script_pubkey(address: str, *, hrp: str = HRP_MAINNET) -> bytes:
        """Return the scriptPubKey for address."""
        version, program = SegwitAddress.decode(address, hrp=hrp)
        version_byte = b"\x00" if version == 0 else bytes([OP_WITNESS_VERSION_BASE + version])
        return version_byte + bytes([len(program)]) + program


def _require_hrp(hrp: str) -> None:
    """Raise when hrp is not the mainnet or testnet SegWit prefix."""
    if hrp not in {HRP_MAINNET, HRP_TESTNET}:
        raise ValueError(_ADDRESS_ERROR)


def _require_compressed_public_key(public_key_hex: str) -> bytes:
    """Return the compressed public key bytes when they are on secp256k1."""
    if not isinstance(public_key_hex, str) or len(public_key_hex) != COMPRESSED_PUBLIC_KEY_BYTES * 2:
        raise ValueError(_ADDRESS_ERROR)
    try:
        public_key = bytes.fromhex(public_key_hex)
    except ValueError:
        raise ValueError(_ADDRESS_ERROR) from None
    if public_key[:1] not in {b"\x02", b"\x03"}:
        raise ValueError(_ADDRESS_ERROR)
    try:
        ecdsa.VerifyingKey.from_string(public_key, curve=ecdsa.SECP256k1)
    except (MalformedPointError, ValueError):
        raise ValueError(_ADDRESS_ERROR) from None
    return public_key


def _program_length_ok(witness_version: int, length: int) -> bool:
    """Return whether length is legal for witness_version."""
    if witness_version == 0:
        return length in {WITNESS_V0_PROGRAM_SHORT, WITNESS_V0_PROGRAM_LONG}
    return WITNESS_PROGRAM_MIN_BYTES <= length <= WITNESS_PROGRAM_MAX_BYTES


def _encode_bech32m(hrp: str, data: list[int]) -> str:
    """Return a Bech32m string. Version 0 uses bech32.encode instead."""
    checksum = _checksum(hrp, data, BECH32M_CONST)
    return hrp + "1" + "".join(bech32.CHARSET[value] for value in [*data, *checksum])


def _checksum(hrp: str, data: list[int], constant: int) -> list[int]:
    """Return the 6 checksum values using the bech32 library polymod and the BIP constant."""
    values = [*bech32.bech32_hrp_expand(hrp), *data]
    polymod = bech32.bech32_polymod([*values, 0, 0, 0, 0, 0, 0]) ^ constant
    return [(polymod >> (5 * (5 - index))) & 31 for index in range(BECH32_CHECKSUM_LENGTH)]


def _decode(address: str, hrp: str) -> tuple[int, bytes] | None:
    """Return the witness version and program when address matches hrp and the right checksum."""
    if not isinstance(address, str) or address == "" or len(address) > BECH32_MAX_LENGTH:
        return None
    if any(ord(character) < 33 or ord(character) > 126 for character in address):
        return None
    if address.lower() != address and address.upper() != address:
        return None
    lowered = address.lower()
    separator = lowered.rfind("1")
    if separator < 1 or separator > BECH32_HRP_MAX_LENGTH or separator + 7 > len(lowered):
        return None
    if lowered[:separator] != hrp:
        return None
    data_part = lowered[separator + 1 :]
    if any(character not in bech32.CHARSET for character in data_part):
        return None
    data = [bech32.CHARSET.find(character) for character in data_part]
    constant = bech32.bech32_polymod([*bech32.bech32_hrp_expand(hrp), *data])
    if constant == BECH32_CONST:
        witness_version_encoding = 0
    elif constant == BECH32M_CONST:
        witness_version_encoding = 1
    else:
        return None
    payload = data[:-BECH32_CHECKSUM_LENGTH]
    if payload == []:
        return None
    converted = bech32.convertbits(payload[1:], 5, 8, False)
    if converted is None or not _program_length_ok(payload[0], len(converted)):
        return None
    if payload[0] > WITNESS_VERSION_MAX:
        return None
    if (payload[0] == 0) != (witness_version_encoding == 0):
        return None
    return payload[0], bytes(converted)
