"""Legacy transaction bytes compatible with TransactionSigner, plus a coinbase builder."""

from __future__ import annotations

import struct

from bitcoin_wallet import BitcoinWallet
from btc_wallet.wallet_constants import (
    MAX_MONEY_SATS,
    P2PKH_SCRIPT_PREFIX,
    P2PKH_SCRIPT_SUFFIX,
    SEQUENCE_FINAL,
    TX_VERSION,
    VARINT_ONE_BYTE_MAX,
)
from edu_node.double_sha256 import double_sha256
from edu_node.node_constants import HASH_BYTES, MAX_TX_BYTES, TX_ERROR

_ZERO_TXID = "00" * HASH_BYTES


def p2pkh_script(public_key: bytes) -> bytes:
    """Return the P2PKH script for a compressed public key."""
    if not isinstance(public_key, bytes):
        raise ValueError(TX_ERROR)
    return P2PKH_SCRIPT_PREFIX + BitcoinWallet._hash160(public_key) + P2PKH_SCRIPT_SUFFIX


class EduTransaction:
    """One parsed legacy transaction."""

    def __init__(
        self,
        raw: bytes,
        inputs: list[tuple[str, int, bytes, int]],
        outputs: list[tuple[int, bytes]],
        locktime: int,
    ) -> None:
        self.raw = raw
        self.inputs = inputs
        self.outputs = outputs
        self.locktime = locktime

    @property
    def internal_id(self) -> bytes:
        """Return the double SHA-256 of the raw transaction."""
        return double_sha256(self.raw)

    @property
    def display_id(self) -> str:
        """Return the reversed transaction id hex that TransactionSigner expects."""
        return self.internal_id[::-1].hex()

    @property
    def is_coinbase(self) -> bool:
        """Return whether the only input is the coinbase outpoint."""
        if len(self.inputs) != 1:
            return False
        txid, vout, _script, _sequence = self.inputs[0]
        return txid == _ZERO_TXID and vout == SEQUENCE_FINAL

    @classmethod
    def coinbase(cls, height: int, value: int, pay_script: bytes) -> EduTransaction:
        """Return a coinbase that pays pay_script and records height in the input script."""
        if type(height) is not int or not 0 <= height <= SEQUENCE_FINAL:
            raise ValueError(TX_ERROR)
        if type(value) is not int or not 0 <= value <= MAX_MONEY_SATS:
            raise ValueError(TX_ERROR)
        if not isinstance(pay_script, bytes) or not 1 <= len(pay_script) <= VARINT_ONE_BYTE_MAX:
            raise ValueError(TX_ERROR)
        script_sig = bytes([4]) + struct.pack("<I", height)
        raw = _serialize([(bytes(HASH_BYTES), SEQUENCE_FINAL, script_sig)], [(value, pay_script)], 0)
        return cls.parse(raw)

    @classmethod
    def parse(cls, raw: bytes) -> EduTransaction:
        """Return a transaction when raw uses one-byte counts and final sequences."""
        if not isinstance(raw, bytes) or not 1 <= len(raw) <= MAX_TX_BYTES:
            raise ValueError(TX_ERROR)
        cursor = 0
        version, cursor = _read_int(raw, cursor, 4)
        if version != TX_VERSION:
            raise ValueError(TX_ERROR)
        input_count, cursor = _read_count(raw, cursor)
        if input_count < 1:
            raise ValueError(TX_ERROR)
        inputs: list[tuple[str, int, bytes, int]] = []
        for _index in range(input_count):
            prev, cursor = _read(raw, cursor, HASH_BYTES)
            vout, cursor = _read_uint(raw, cursor)
            script, cursor = _read_script(raw, cursor, allow_empty=True)
            sequence, cursor = _read_uint(raw, cursor)
            if sequence != SEQUENCE_FINAL:
                raise ValueError(TX_ERROR)
            inputs.append((prev[::-1].hex(), vout, script, sequence))
        output_count, cursor = _read_count(raw, cursor)
        if output_count < 1:
            raise ValueError(TX_ERROR)
        outputs: list[tuple[int, bytes]] = []
        for _index in range(output_count):
            value, cursor = _read_signed(raw, cursor)
            script, cursor = _read_script(raw, cursor, allow_empty=False)
            outputs.append((value, script))
        locktime, cursor = _read_uint(raw, cursor)
        if cursor != len(raw):
            raise ValueError(TX_ERROR)
        return cls(raw, inputs, outputs, locktime)


def _serialize(
    inputs: list[tuple[bytes, int, bytes]],
    outputs: list[tuple[int, bytes]],
    locktime: int,
) -> bytes:
    """Return legacy transaction bytes with one-byte counts."""
    parts = [struct.pack("<I", TX_VERSION), bytes([len(inputs)])]
    for previous, vout, script in inputs:
        parts.append(previous)
        parts.append(struct.pack("<I", vout))
        parts.append(bytes([len(script)]))
        parts.append(script)
        parts.append(struct.pack("<I", SEQUENCE_FINAL))
    parts.append(bytes([len(outputs)]))
    for value, script in outputs:
        parts.append(struct.pack("<q", value))
        parts.append(bytes([len(script)]))
        parts.append(script)
    parts.append(struct.pack("<I", locktime))
    return b"".join(parts)


def _read(raw: bytes, cursor: int, size: int) -> tuple[bytes, int]:
    """Return the next size bytes."""
    end = cursor + size
    if end > len(raw):
        raise ValueError(TX_ERROR)
    return raw[cursor:end], end


def _read_int(raw: bytes, cursor: int, size: int) -> tuple[int, int]:
    """Return an unsigned little-endian integer."""
    chunk, end = _read(raw, cursor, size)
    return int.from_bytes(chunk, "little"), end


def _read_uint(raw: bytes, cursor: int) -> tuple[int, int]:
    """Return a 32-bit unsigned integer."""
    return _read_int(raw, cursor, 4)


def _read_signed(raw: bytes, cursor: int) -> tuple[int, int]:
    """Return a non-negative satoshi value."""
    chunk, end = _read(raw, cursor, 8)
    value = int.from_bytes(chunk, "little", signed=True)
    if not 0 <= value <= MAX_MONEY_SATS:
        raise ValueError(TX_ERROR)
    return value, end


def _read_count(raw: bytes, cursor: int) -> tuple[int, int]:
    """Return a one-byte count."""
    chunk, end = _read(raw, cursor, 1)
    count = chunk[0]
    if count > VARINT_ONE_BYTE_MAX:
        raise ValueError(TX_ERROR)
    return count, end


def _read_script(raw: bytes, cursor: int, *, allow_empty: bool) -> tuple[bytes, int]:
    """Return a script whose length fits in one byte."""
    length, cursor = _read_count(raw, cursor)
    if length == 0 and not allow_empty:
        raise ValueError(TX_ERROR)
    return _read(raw, cursor, length)
