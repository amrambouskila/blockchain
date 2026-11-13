"""Legacy transaction parsing, coinbase construction, and P2PKH script bytes."""

from __future__ import annotations

import struct

import pytest

from bitcoin_wallet import BitcoinWallet
from btc_wallet.wallet_constants import MAX_MONEY_SATS, SEQUENCE_FINAL, VARINT_ONE_BYTE_MAX
from edu_node import edu_transaction as edu_transaction_module
from edu_node.edu_transaction import EduTransaction, p2pkh_script
from edu_node.node_constants import TX_ERROR

_KEY = f"{1:064x}"


def _legacy(
    inputs: list[tuple[bytes, int, bytes]],
    outputs: list[tuple[int, bytes]],
    *,
    version: int = 1,
    sequence: int = SEQUENCE_FINAL,
    locktime: int = 0,
) -> bytes:
    """Return one-byte-count transaction bytes for the parser tests."""
    parts = [struct.pack("<I", version), bytes([len(inputs)])]
    for previous, vout, script in inputs:
        parts.extend((previous, struct.pack("<I", vout), bytes([len(script)]), script, struct.pack("<I", sequence)))
    parts.append(bytes([len(outputs)]))
    for value, script in outputs:
        parts.extend((struct.pack("<q", value), bytes([len(script)]), script))
    parts.append(struct.pack("<I", locktime))
    return b"".join(parts)


def test_coinbase_records_height_and_round_trips() -> None:
    """A coinbase pays one script and can be parsed back from its own bytes."""
    pay = p2pkh_script(bytes.fromhex(BitcoinWallet.derive_public_key(_KEY)))
    transaction = EduTransaction.coinbase(7, 9, pay)
    assert transaction.is_coinbase is True
    assert transaction.inputs[0][2] == bytes([4]) + struct.pack("<I", 7)
    assert transaction.outputs == [(9, pay)]
    assert EduTransaction.parse(transaction.raw).display_id == transaction.display_id
    assert len(transaction.internal_id) == 32


def test_p2pkh_script_needs_bytes() -> None:
    """The script helper refuses a public key that is not bytes."""
    with pytest.raises(ValueError, match=TX_ERROR):
        p2pkh_script("02")  # type: ignore[arg-type]  # a public key is bytes


@pytest.mark.parametrize("height", [True, -1, SEQUENCE_FINAL + 1])
def test_coinbase_height_is_a_block_height(height: int) -> None:
    """Height has to be an integer from zero through the sequence maximum."""
    with pytest.raises(ValueError, match=TX_ERROR):
        EduTransaction.coinbase(height, 1, b"\x51")  # type: ignore[arg-type]  # boundary input


@pytest.mark.parametrize("value", [True, -1, MAX_MONEY_SATS + 1])
def test_coinbase_value_is_a_satoshi_amount(value: int) -> None:
    """A coinbase value is a non-negative satoshi count inside the money limit."""
    with pytest.raises(ValueError, match=TX_ERROR):
        EduTransaction.coinbase(0, value, b"\x51")  # type: ignore[arg-type]  # boundary input


@pytest.mark.parametrize("script", ["aa", b"", b"\x51" * (VARINT_ONE_BYTE_MAX + 1)])
def test_coinbase_script_fits_one_length_byte(script: bytes) -> None:
    """The coinbase output script is bytes with a one-byte length."""
    with pytest.raises(ValueError, match=TX_ERROR):
        EduTransaction.coinbase(0, 1, script)  # type: ignore[arg-type]  # boundary input


def test_a_normal_payment_parses_and_is_not_coinbase() -> None:
    """An empty input script is allowed, and two inputs are not a coinbase."""
    single = EduTransaction.parse(_legacy([(bytes(32), 1, b"")], [(0, b"\x51")]))
    assert single.is_coinbase is False
    double = EduTransaction.parse(
        _legacy([(bytes(32), SEQUENCE_FINAL, b"\x01"), (b"\x02" * 32, 0, b"\x01")], [(1, b"\x51")])
    )
    assert double.is_coinbase is False
    assert double.locktime == 0


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"\x02\x00\x00\x00",
        struct.pack("<I", 1),
        struct.pack("<I", 1) + b"\x00",
        struct.pack("<I", 1) + b"\xfd",
        _legacy([(bytes(32), 0, b"\x01")], [(1, b"\x51")], sequence=1),
        _legacy([(bytes(32), 0, b"\x01")], []),
        _legacy([(bytes(32), 0, b"\x01")], [(1, b"")]),
        _legacy([(bytes(32), 0, b"\x01")], [(-1, b"\x51")]),
        _legacy([(bytes(32), 0, b"\x01")], [(MAX_MONEY_SATS + 1, b"\x51")]),
        _legacy([(bytes(32), 0, b"\x01")], [(1, b"\x51")]) + b"\x00",
        "00",
    ],
)
def test_broken_transaction_bytes_are_rejected(raw: bytes) -> None:
    """Version, counts, sequence, money, and trailing bytes are all checked."""
    with pytest.raises(ValueError, match=TX_ERROR):
        EduTransaction.parse(raw)  # type: ignore[arg-type]  # boundary input


def test_a_transaction_over_the_size_cap_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """The parser stops when the byte cap is smaller than the transaction."""
    monkeypatch.setattr(edu_transaction_module, "MAX_TX_BYTES", 8)
    with pytest.raises(ValueError, match=TX_ERROR):
        EduTransaction.parse(_legacy([(bytes(32), 0, b"\x01")], [(1, b"\x51")]))
