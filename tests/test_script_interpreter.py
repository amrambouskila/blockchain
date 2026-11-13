"""The script interpreter accepts a real signature and rejects everything outside its allowlist."""

from __future__ import annotations

import ecdsa
import pytest

from bitcoin_wallet import BitcoinWallet
from btc_wallet.transaction_signer import TransactionSigner
from btc_wallet.wallet_constants import SIGHASH_ALL
from edu_node.edu_transaction import EduTransaction, p2pkh_script
from edu_node.node_constants import (
    MAX_OPCODE_COUNT,
    MAX_SCRIPT_BYTES,
    MAX_STACK_ITEM_BYTES,
    MAX_STACK_ITEMS,
    OP_1,
    OP_16,
    OP_CHECKMULTISIG,
    OP_CHECKSIG,
    OP_DUP,
    OP_EQUALVERIFY,
    OP_HASH160,
    OP_PUSH_MAX,
)
from edu_node.script_interpreter import ScriptInterpreter, _compressed_key
from tests.chain_blocks import _raw

_KEY = f"{1:064x}"
_SOURCE = "ab" * 32


def _public_key() -> bytes:
    """Return the compressed public key for the test private key."""
    return bytes.fromhex(BitcoinWallet.derive_public_key(_KEY))


def _payment(script_sig: bytes, script_code: bytes) -> EduTransaction:
    """Return a one-input transaction carrying script_sig."""
    return EduTransaction.parse(_raw([(_SOURCE, 0, script_sig)], [(10, b"\x51")]))


def _signed_script(script_code: bytes) -> tuple[bytes, EduTransaction]:
    """Return a signature push and the transaction that signature commits to."""
    signature = TransactionSigner().sign_input(_KEY, [(_SOURCE, 0)], [(10, b"\x51")], 0, script_code)
    assert len(signature) <= OP_PUSH_MAX
    script_sig = bytes([len(signature)]) + signature
    return script_sig, _payment(script_sig, script_code)


def test_p2pkh_accepts_a_low_s_signature() -> None:
    """A payment to the key that signed it leaves one true stack item."""
    public_key = _public_key()
    script_pub = p2pkh_script(public_key)
    signature = TransactionSigner().sign_input(_KEY, [(_SOURCE, 0)], [(10, script_pub)], 0, script_pub)
    script_sig = bytes([len(signature), *signature, len(public_key), *public_key])
    transaction = EduTransaction.parse(_raw([(_SOURCE, 0, script_sig)], [(10, script_pub)]))
    assert ScriptInterpreter().accepts(script_sig, script_pub, transaction, 0) is True


def test_a_changed_signature_is_false() -> None:
    """Checksig pushes an empty item when the signature does not verify."""
    public_key = _public_key()
    script_pub = p2pkh_script(public_key)
    signature = bytearray(
        TransactionSigner().sign_input(_KEY, [(_SOURCE, 0)], [(10, script_pub)], 0, script_pub),
    )
    signature[0] ^= 0x01
    script_sig = bytes([len(signature), *signature, len(public_key), *public_key])
    transaction = _payment(script_sig, script_pub)
    assert ScriptInterpreter().accepts(script_sig, script_pub, transaction, 0) is False


def test_bare_multisig_accepts_one_key() -> None:
    """One signature satisfies a 1-of-1 multisig after Bitcoin's extra dummy pop."""
    public_key = _public_key()
    script_pub = bytes([OP_1, len(public_key)]) + public_key + bytes([OP_1, OP_CHECKMULTISIG])
    signature = TransactionSigner().sign_input(_KEY, [(_SOURCE, 0)], [(10, b"\x51")], 0, script_pub)
    script_sig = bytes([0, len(signature)]) + signature
    transaction = _payment(script_sig, script_pub)
    assert ScriptInterpreter().accepts(script_sig, script_pub, transaction, 0) is True


def test_bare_multisig_rejects_a_bad_signature() -> None:
    """A multisig that never finds a match fails the script."""
    public_key = _public_key()
    script_pub = bytes([OP_1, len(public_key)]) + public_key + bytes([OP_1, OP_CHECKMULTISIG])
    script_sig = bytes([0, 2, 0x30, SIGHASH_ALL])
    transaction = _payment(script_sig, script_pub)
    assert ScriptInterpreter().accepts(script_sig, script_pub, transaction, 0) is False


def test_multisig_counts_must_fit_the_stack() -> None:
    """Missing keys, a zero count, too many keys, or a long count all fail."""
    public_key = _public_key()
    pushed_key = bytes([len(public_key)]) + public_key
    scripts = [
        bytes([OP_1, OP_CHECKMULTISIG]),
        bytes([0, OP_CHECKMULTISIG]),
        bytes([1, 17, OP_CHECKMULTISIG]),
        bytes([OP_16, OP_CHECKMULTISIG]),
        bytes([0]) + pushed_key + bytes([OP_1, OP_CHECKMULTISIG]),
        bytes([5, 1, 1, 1, 1, 1]) + pushed_key + bytes([OP_1, OP_CHECKMULTISIG]),
        bytes([2, 0x30, SIGHASH_ALL, OP_1]) + pushed_key + bytes([OP_1, OP_CHECKMULTISIG]),
        bytes([0, 2, 0x30, 1, 2, 0x30, 1, OP_1 + 1]) + pushed_key + bytes([OP_1, OP_CHECKMULTISIG]),
    ]
    transaction = _payment(b"", b"")
    for script in scripts:
        assert ScriptInterpreter().accepts(b"", script, transaction, 0) is False


def test_only_bytes_scripts_and_a_real_index_run() -> None:
    """A non-bytes script, an oversized script, or a bad index never runs."""
    transaction = EduTransaction.coinbase(0, 1, b"\x51")
    interpreter = ScriptInterpreter()
    assert interpreter.accepts(None, b"\x51", transaction, 0) is False  # type: ignore[arg-type]  # boundary input
    assert interpreter.accepts(b"\x51", None, transaction, 0) is False  # type: ignore[arg-type]  # boundary input
    assert interpreter.accepts(b"\x51" * (MAX_SCRIPT_BYTES + 1), b"\x51", transaction, 0) is False
    assert interpreter.accepts(b"\x51", b"\x51" * (MAX_SCRIPT_BYTES + 1), transaction, 0) is False
    assert interpreter.accepts(b"\x51", b"\x51", transaction, True) is False  # type: ignore[arg-type]  # bool index
    assert interpreter.accepts(b"\x51", b"\x51", transaction, -1) is False


def test_simple_opcodes_leave_one_true_item_or_fail() -> None:
    """Push, dup, hash, and equalverify succeed only when the final stack is one true item."""
    transaction = EduTransaction.coinbase(0, 1, b"\x51")
    interpreter = ScriptInterpreter()
    assert interpreter.accepts(b"", bytes([OP_1]), transaction, 0) is True
    assert interpreter.accepts(b"", bytes([OP_16]), transaction, 0) is True
    assert interpreter.accepts(b"", bytes([0]), transaction, 0) is False
    assert interpreter.accepts(b"", bytes([1, 0]), transaction, 0) is False
    assert interpreter.accepts(b"", bytes([OP_1, OP_1]), transaction, 0) is False
    assert interpreter.accepts(b"", b"", transaction, 0) is False
    assert interpreter.accepts(b"", bytes([OP_DUP]), transaction, 0) is False
    assert interpreter.accepts(b"", bytes([OP_HASH160]), transaction, 0) is False
    assert interpreter.accepts(b"", bytes([OP_1, OP_EQUALVERIFY]), transaction, 0) is False
    assert interpreter.accepts(b"", bytes([1, 1, 1, 2, OP_EQUALVERIFY]), transaction, 0) is False
    assert interpreter.accepts(b"", bytes([OP_1, OP_1, OP_EQUALVERIFY, OP_1]), transaction, 0) is True
    assert interpreter.accepts(b"", bytes([2, 1]), transaction, 0) is False
    assert interpreter.accepts(bytes([0xFF]), b"", transaction, 0) is False
    assert interpreter.accepts(b"", bytes([0xFF]), transaction, 0) is False
    full = bytes([0]) * MAX_STACK_ITEMS
    assert interpreter.accepts(full, bytes([1, 0x11]), transaction, 0) is False
    assert interpreter.accepts(full, bytes([OP_1]), transaction, 0) is False
    assert interpreter.accepts(b"", bytes([OP_CHECKMULTISIG]), transaction, 0) is False
    assert interpreter.accepts(b"", bytes([OP_CHECKSIG]), transaction, 0) is False
    assert interpreter.accepts(b"", bytes([OP_1, OP_CHECKSIG]), transaction, 0) is False
    assert interpreter.accepts(b"", bytes([0]) * (MAX_STACK_ITEMS + 1), transaction, 0) is False
    assert interpreter.accepts(b"", bytes([1, 1]) + bytes([OP_DUP]) * (MAX_OPCODE_COUNT + 1), transaction, 0) is False


def test_stack_and_signature_limits_fail_closed() -> None:
    """Oversized pushes and signatures that are not SIGHASH_ALL do not verify."""
    interpreter = ScriptInterpreter()
    transaction = EduTransaction.coinbase(0, 1, b"\x51")
    assert interpreter._push([], b"\x00" * (MAX_STACK_ITEM_BYTES + 1)) is False
    assert interpreter._push([b""] * MAX_STACK_ITEMS, b"\x01") is False
    public_key = _public_key()
    assert interpreter._verify(b"\x01", public_key, transaction, 0, b"\x51") is False
    assert interpreter._verify(b"\x30\x02", public_key, transaction, 0, b"\x51") is False
    assert interpreter._verify(b"\x30\x01", b"\x04" + b"\x11" * 32, transaction, 0, b"\x51") is False
    garbage = b"\x30" + b"\x01" * 8
    assert interpreter._verify(garbage, public_key, transaction, 0, b"\x51") is False
    script_sig, signed = _signed_script(p2pkh_script(public_key))
    assert interpreter.accepts(script_sig, p2pkh_script(public_key), signed, 1) is False


def test_compressed_keys_need_a_real_point(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both parities verify, and a point the curve rejects does not."""
    prefixes: set[int] = set()
    for number in range(1, 40):
        encoded = bytes.fromhex(BitcoinWallet.derive_public_key(f"{number:064x}"))
        prefixes.add(encoded[0])
        assert _compressed_key(encoded) is not None
    assert prefixes == {2, 3}
    prime = ecdsa.SECP256k1.curve.p()
    assert _compressed_key(b"\x02" + bytes(32)) is None
    assert _compressed_key(b"\x04" + b"\x01" * 32) is None
    assert _compressed_key(b"\x02" + b"\xff" * 32) is None
    assert _compressed_key(b"\x02" + prime.to_bytes(32, "big")) is None
    residue = False
    for coordinate in range(1, 30):
        if _compressed_key(b"\x02" + coordinate.to_bytes(32, "big")) is None:
            residue = True
            break
    assert residue is True

    def explode(*_args: object, **_kwargs: object) -> object:
        raise ValueError("rejected")

    monkeypatch.setattr("edu_node.script_interpreter.ecdsa.ellipticcurve.Point", explode)
    assert _compressed_key(_public_key()) is None
