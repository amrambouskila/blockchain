"""Legacy P2PKH signing checked against Programming Bitcoin, chapter 7."""

from __future__ import annotations

import pytest

from bitcoin_wallet import BitcoinWallet
from btc_wallet.transaction_signer import TransactionSigner, _script_sig, _varint
from btc_wallet.wallet_constants import (
    MAX_MONEY_SATS,
    MAX_PUSH_ONE_BYTE,
    P2PKH_SCRIPT_PREFIX,
    P2PKH_SCRIPT_SUFFIX,
    SEQUENCE_FINAL,
    VARINT_ONE_BYTE_MAX,
)

_SIGNER = TransactionSigner()
_PRIVATE = f"{8675309:064x}"
_WIRE_HEAD = "99a24308080ab26e6fb65c4eccfadf76"
_WIRE_TAIL = "749bb5bfa8cb08f291320b3c21e56f0d"
_WIRE = _WIRE_HEAD + _WIRE_TAIL
_SIGNED = (
    "010000000199a24308080ab26e6fb65c4eccfadf76"
    "749bb5bfa8cb08f291320b3c21e56f0d0d0000006b"
    "4830450221008ed46aa2cf12d6d81065bfabe90367"
    "0165b538f65ee9a3385e6327d80c66d3b502203124"
    "f804410527497329ec4715e18558082d489b218677"
    "bd029e7fa306a72236012103935581e52c354cd2f4"
    "84fe8ed83af7a3097005b2f9c60bff71d35bd795f5"
    "4b67ffffffff02408af701000000001976a914d52a"
    "d7ca9b3d096a38e752c2018e6fbc40cdf26f88ac80"
    "969800000000001976a914507b27411ccf7f16f102"
    "97de6cef3f291623eddf88ac00000000"
)
_OUTPUT_ONE = "76a914d52ad7ca9b3d096a38e752c2018e6fbc40cdf26f88ac"
_OUTPUT_TWO = "76a914507b27411ccf7f16f10297de6cef3f291623eddf88ac"


def _book_inputs() -> list[tuple[str, int]]:
    """Return the chapter 7 outpoint in display order."""
    return [(bytes.fromhex(_WIRE)[::-1].hex(), 13)]


def _book_outputs() -> list[tuple[int, bytes]]:
    """Return the two chapter 7 outputs in satoshis."""
    return [(33_000_000, bytes.fromhex(_OUTPUT_ONE)), (10_000_000, bytes.fromhex(_OUTPUT_TWO))]


def test_programming_bitcoin_signature_matches_byte_for_byte() -> None:
    """Private key 8675309 signs the chapter 7 transaction to the published hex."""
    signed = _SIGNER.sign_p2pkh(_PRIVATE, _book_inputs(), _book_outputs())
    assert signed == _SIGNED
    assert len(_SIGNER.sighash(_PRIVATE, _book_inputs(), _book_outputs(), 0)) == 32


def test_two_inputs_sign_deterministically() -> None:
    """A second input is signed on its own digest, and repeating the call is stable."""
    inputs = [("ab" * 32, 0), ("cd" * 32, 1)]
    outputs = [(50_000, bytes.fromhex(_OUTPUT_ONE))]
    first = _SIGNER.sign_p2pkh(_PRIVATE, inputs, outputs, locktime=1)
    second = _SIGNER.sign_p2pkh(_PRIVATE.upper(), inputs, outputs, locktime=1)
    assert first == second
    assert _SIGNER.sighash(_PRIVATE, inputs, outputs, 1, locktime=1) != _SIGNER.sighash(
        _PRIVATE, inputs, outputs, 0, locktime=1
    )


def test_push_and_varint_limits() -> None:
    """A one-byte push and a one-byte varint reject the next size up."""
    with pytest.raises(ValueError, match="Signature push"):
        _script_sig(b"\x30" * (MAX_PUSH_ONE_BYTE + 1), b"\x02" + b"\x11" * 32)
    with pytest.raises(ValueError, match="Legacy transaction"):
        _varint(253)


@pytest.mark.parametrize("private_hex", ["", "zz" * 32, "00" * 32, 5])
def test_private_key_is_required(private_hex: object) -> None:
    """Signing refuses a key that is not a 32-byte scalar inside the curve order."""
    with pytest.raises(ValueError):
        _SIGNER.sign_p2pkh(private_hex, _book_inputs(), _book_outputs())  # type: ignore[arg-type]  # boundary input


@pytest.mark.parametrize(
    "inputs",
    [
        [],
        [("ab" * 32, 0)] * 253,
        ["ab"],
        [("zz" * 32, 0)],
        [("ab" * 31, 0)],
        [("ab" * 32, True)],
        [("ab" * 32, -1)],
        [("ab" * 32, SEQUENCE_FINAL + 1)],
    ],
)
def test_bad_inputs_are_rejected(inputs: object) -> None:
    """Inputs are one to 252 display outpoints with a 32-bit vout."""
    with pytest.raises(ValueError, match="Legacy transaction"):
        _SIGNER.sign_p2pkh(_PRIVATE, inputs, _book_outputs())  # type: ignore[arg-type]  # boundary input


@pytest.mark.parametrize(
    "outputs",
    [
        [],
        [(0, b"\x51")] * 253,
        ["nope"],
        [(True, b"\x51")],
        [(-1, b"\x51")],
        [(MAX_MONEY_SATS + 1, b"\x51")],
        [(0, b"")],
        [(0, b"\x51" * 253)],
    ],
)
def test_bad_outputs_are_rejected(outputs: object) -> None:
    """Outputs carry a bounded satoshi value and a script of 1 to 252 bytes."""
    with pytest.raises(ValueError, match="Legacy transaction"):
        _SIGNER.sign_p2pkh(_PRIVATE, _book_inputs(), outputs)  # type: ignore[arg-type]  # boundary input
    accepted = _SIGNER.sign_p2pkh(_PRIVATE, _book_inputs(), [(0, b"\x51" * 252)])
    assert accepted.startswith("01000000")


@pytest.mark.parametrize("locktime", [True, -1, SEQUENCE_FINAL + 1])
def test_locktime_is_a_uint32(locktime: object) -> None:
    """Locktime is a whole number from 0 through 2^32-1."""
    with pytest.raises(ValueError, match="Legacy transaction"):
        _SIGNER.sign_p2pkh(_PRIVATE, _book_inputs(), _book_outputs(), locktime=locktime)  # type: ignore[arg-type]  # boundary input


@pytest.mark.parametrize("index", [True, -1, 1])
def test_sighash_index_must_name_an_input(index: object) -> None:
    """The sighash index has to point at one of the inputs."""
    with pytest.raises(ValueError, match="Legacy transaction"):
        _SIGNER.sighash(_PRIVATE, _book_inputs(), _book_outputs(), index)  # type: ignore[arg-type]  # boundary input


def _key_script() -> bytes:
    """Return the P2PKH script for the chapter 7 private key."""
    public_key = bytes.fromhex(BitcoinWallet.derive_public_key(_PRIVATE))
    return P2PKH_SCRIPT_PREFIX + BitcoinWallet._hash160(public_key) + P2PKH_SCRIPT_SUFFIX


def test_digest_matches_sighash_for_the_same_script() -> None:
    """A digest built from the key's script matches sighash."""
    script = _key_script()
    assert _SIGNER.digest(_book_inputs(), _book_outputs(), 0, script) == _SIGNER.sighash(
        _PRIVATE,
        _book_inputs(),
        _book_outputs(),
        0,
    )
    assert _SIGNER.sign_input(_PRIVATE, _book_inputs(), _book_outputs(), 0, script).endswith(b"\x01")


def test_digest_index_must_name_an_input() -> None:
    """The digest index has to point at one of the inputs."""
    with pytest.raises(ValueError, match="Legacy transaction"):
        _SIGNER.digest(_book_inputs(), _book_outputs(), 1, b"\x51")


@pytest.mark.parametrize("script", [b"", b"x" * (VARINT_ONE_BYTE_MAX + 1), "abcd", 5])
def test_digest_rejects_a_bad_script(script: object) -> None:
    """The script code has to be bytes that fit in one length byte."""
    with pytest.raises(ValueError, match="Legacy transaction"):
        _SIGNER.digest(_book_inputs(), _book_outputs(), 0, script)  # type: ignore[arg-type]  # boundary input


def test_sign_input_rejects_a_bad_private_key() -> None:
    """Signing still refuses a key that is not 32 bytes of hex."""
    with pytest.raises(ValueError, match="Private key"):
        _SIGNER.sign_input("zz", _book_inputs(), _book_outputs(), 0, _key_script())
