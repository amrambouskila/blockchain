"""Legacy P2PKH signing for learning. The send path still asks Bitcoin Core to sign."""

from __future__ import annotations

import hashlib
import struct

import ecdsa

from bitcoin_wallet import BitcoinWallet
from btc_wallet.wallet_constants import (
    MAX_MONEY_SATS,
    MAX_PUSH_ONE_BYTE,
    MAX_TX_ELEMENTS,
    P2PKH_SCRIPT_PREFIX,
    P2PKH_SCRIPT_SUFFIX,
    SEQUENCE_FINAL,
    SIGHASH_ALL,
    TX_VERSION,
    VARINT_ONE_BYTE_MAX,
)
from constants import COMPRESSED_PUBLIC_KEY_BYTES, TXID_HEX_LENGTH

_TX_ERROR = "Legacy transaction is invalid."
_PUSH_ERROR = "Signature push is longer than a single-byte length."


class TransactionSigner:
    """Sign a legacy P2PKH transaction whose inputs all pay to one private key."""

    def sign_p2pkh(
        self,
        private_key_hex: str,
        inputs: list[tuple[str, int]],
        outputs: list[tuple[int, bytes]],
        *,
        locktime: int = 0,
    ) -> str:
        """Return the signed transaction hex. Inputs are display txid and vout."""
        private_hex = BitcoinWallet._require_private_key_hex(private_key_hex)
        public_key = bytes.fromhex(BitcoinWallet.derive_public_key(private_hex))
        script_code = _p2pkh_script(BitcoinWallet._hash160(public_key))
        checked_inputs = _require_inputs(inputs)
        checked_outputs = _require_outputs(outputs)
        checked_locktime = _require_locktime(locktime)
        signatures = [
            _signature(private_hex, checked_inputs, checked_outputs, index, script_code, checked_locktime)
            for index in range(len(checked_inputs))
        ]
        script_sigs = [_script_sig(signature, public_key) for signature in signatures]
        return _serialize(checked_inputs, checked_outputs, script_sigs, checked_locktime).hex()

    def sighash(
        self,
        private_key_hex: str,
        inputs: list[tuple[str, int]],
        outputs: list[tuple[int, bytes]],
        index: int,
        *,
        locktime: int = 0,
    ) -> bytes:
        """Return the legacy SIGHASH_ALL digest for one input."""
        private_hex = BitcoinWallet._require_private_key_hex(private_key_hex)
        public_key = bytes.fromhex(BitcoinWallet.derive_public_key(private_hex))
        checked_inputs = _require_inputs(inputs)
        if type(index) is not int or not 0 <= index < len(checked_inputs):
            raise ValueError(_TX_ERROR)
        return _sighash(
            checked_inputs,
            _require_outputs(outputs),
            index,
            _p2pkh_script(BitcoinWallet._hash160(public_key)),
            _require_locktime(locktime),
        )

    def digest(
        self,
        inputs: list[tuple[str, int]],
        outputs: list[tuple[int, bytes]],
        index: int,
        script_code: bytes,
        *,
        locktime: int = 0,
    ) -> bytes:
        """Return the legacy SIGHASH_ALL digest using script_code at index."""
        checked_inputs = _require_inputs(inputs)
        if type(index) is not int or not 0 <= index < len(checked_inputs):
            raise ValueError(_TX_ERROR)
        if not isinstance(script_code, bytes) or not 1 <= len(script_code) <= VARINT_ONE_BYTE_MAX:
            raise ValueError(_TX_ERROR)
        return _sighash(
            checked_inputs,
            _require_outputs(outputs),
            index,
            script_code,
            _require_locktime(locktime),
        )

    def sign_input(
        self,
        private_key_hex: str,
        inputs: list[tuple[str, int]],
        outputs: list[tuple[int, bytes]],
        index: int,
        script_code: bytes,
        *,
        locktime: int = 0,
    ) -> bytes:
        """Return the low-s DER signature plus SIGHASH_ALL for script_code."""
        self.digest(inputs, outputs, index, script_code, locktime=locktime)
        private_hex = BitcoinWallet._require_private_key_hex(private_key_hex)
        return _signature(
            private_hex,
            _require_inputs(inputs),
            _require_outputs(outputs),
            index,
            script_code,
            _require_locktime(locktime),
        )


def _signature(
    private_hex: str,
    inputs: list[tuple[bytes, int]],
    outputs: list[tuple[int, bytes]],
    index: int,
    script_code: bytes,
    locktime: int,
) -> bytes:
    """Return the low-s DER signature plus the SIGHASH_ALL byte."""
    digest = _sighash(inputs, outputs, index, script_code, locktime)
    signing_key = ecdsa.SigningKey.from_string(
        bytes.fromhex(private_hex),
        curve=ecdsa.SECP256k1,
        hashfunc=hashlib.sha256,
    )
    der = signing_key.sign_digest_deterministic(
        digest,
        hashfunc=hashlib.sha256,
        sigencode=ecdsa.util.sigencode_der_canonize,
    )
    return der + bytes([SIGHASH_ALL])


def _sighash(
    inputs: list[tuple[bytes, int]],
    outputs: list[tuple[int, bytes]],
    index: int,
    script_code: bytes,
    locktime: int,
) -> bytes:
    """Return the double SHA-256 of the legacy SIGHASH_ALL preimage."""
    scripts = [script_code if item == index else b"" for item in range(len(inputs))]
    preimage = _serialize(inputs, outputs, scripts, locktime) + struct.pack("<I", SIGHASH_ALL)
    return hashlib.sha256(hashlib.sha256(preimage).digest()).digest()


def _serialize(
    inputs: list[tuple[bytes, int]],
    outputs: list[tuple[int, bytes]],
    scripts: list[bytes],
    locktime: int,
) -> bytes:
    """Return the legacy transaction bytes with the given per-input scripts."""
    parts = [struct.pack("<I", TX_VERSION), _varint(len(inputs))]
    for (prev_txid, vout), script in zip(inputs, scripts, strict=True):
        parts.append(prev_txid)
        parts.append(struct.pack("<I", vout))
        parts.append(_varint(len(script)))
        parts.append(script)
        parts.append(struct.pack("<I", SEQUENCE_FINAL))
    parts.append(_varint(len(outputs)))
    for value, script in outputs:
        parts.append(struct.pack("<q", value))
        parts.append(_varint(len(script)))
        parts.append(script)
    parts.append(struct.pack("<I", locktime))
    return b"".join(parts)


def _script_sig(signature: bytes, public_key: bytes) -> bytes:
    """Return the P2PKH scriptSig for signature and public_key."""
    if len(signature) > MAX_PUSH_ONE_BYTE or len(public_key) != COMPRESSED_PUBLIC_KEY_BYTES:
        raise ValueError(_PUSH_ERROR)
    return bytes([len(signature)]) + signature + bytes([len(public_key)]) + public_key


def _p2pkh_script(pubkey_hash: bytes) -> bytes:
    """Return the P2PKH scriptPubKey for a 20-byte hash."""
    return P2PKH_SCRIPT_PREFIX + pubkey_hash + P2PKH_SCRIPT_SUFFIX


def _require_inputs(inputs: list[tuple[str, int]]) -> list[tuple[bytes, int]]:
    """Return wire-order previous outpoints."""
    if not isinstance(inputs, list) or not 1 <= len(inputs) <= MAX_TX_ELEMENTS:
        raise ValueError(_TX_ERROR)
    checked: list[tuple[bytes, int]] = []
    for item in inputs:
        if not isinstance(item, tuple) or len(item) != 2:
            raise ValueError(_TX_ERROR)
        txid, vout = item
        if not isinstance(txid, str) or len(txid) != TXID_HEX_LENGTH:
            raise ValueError(_TX_ERROR)
        try:
            raw = bytes.fromhex(txid)
        except ValueError:
            raise ValueError(_TX_ERROR) from None
        if type(vout) is not int or not 0 <= vout <= SEQUENCE_FINAL:
            raise ValueError(_TX_ERROR)
        checked.append((raw[::-1], vout))
    return checked


def _require_outputs(outputs: list[tuple[int, bytes]]) -> list[tuple[int, bytes]]:
    """Return outputs whose values and scripts fit a legacy transaction."""
    if not isinstance(outputs, list) or not 1 <= len(outputs) <= MAX_TX_ELEMENTS:
        raise ValueError(_TX_ERROR)
    checked: list[tuple[int, bytes]] = []
    for item in outputs:
        if not isinstance(item, tuple) or len(item) != 2:
            raise ValueError(_TX_ERROR)
        value, script = item
        if type(value) is not int or not 0 <= value <= MAX_MONEY_SATS:
            raise ValueError(_TX_ERROR)
        if not isinstance(script, bytes) or not 1 <= len(script) <= VARINT_ONE_BYTE_MAX:
            raise ValueError(_TX_ERROR)
        checked.append((value, script))
    return checked


def _require_locktime(locktime: int) -> int:
    """Return locktime when it fits in an unsigned 32-bit integer."""
    if type(locktime) is not int or not 0 <= locktime <= SEQUENCE_FINAL:
        raise ValueError(_TX_ERROR)
    return locktime


def _varint(value: int) -> bytes:
    """Return a one-byte compact size."""
    if not 0 <= value <= VARINT_ONE_BYTE_MAX:
        raise ValueError(_TX_ERROR)
    return bytes([value])
