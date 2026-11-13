"""P2SH multisig redeem scripts with lexicographic public keys."""

from __future__ import annotations

import hashlib

import base58
import pytest

from bitcoin_wallet import BitcoinWallet
from btc_wallet.multisig_script import MultisigScript
from constants import P2SH_VERSION

WIKI_PUBLIC = "0250863ad64a87ae8a2fe83c1af1a8403cb53f53e486d8511dad8a04887e5b2352"
GENERATOR_PUBLIC = "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"


def _hash160(payload: bytes) -> bytes:
    """Return HASH160 using the standard library, not the wallet helper."""
    return hashlib.new("ripemd160", hashlib.sha256(payload).digest()).digest()


def test_two_published_keys_sort_and_hash_to_p2sh() -> None:
    """The wiki key sorts before the generator point in a 1-of-2 redeem script."""
    script = MultisigScript([GENERATOR_PUBLIC, WIKI_PUBLIC], 1)
    ordered = sorted(bytes.fromhex(item) for item in (WIKI_PUBLIC, GENERATOR_PUBLIC))
    expected = bytes([0x51]) + b"".join(bytes([0x21]) + point for point in ordered) + bytes([0x52, 0xAE])
    assert script.redeem_script() == expected
    digest = _hash160(expected)
    assert script.address() == base58.b58encode_check(P2SH_VERSION + digest).decode()
    assert script.script_pubkey() == bytes([0xA9, 0x14]) + digest + bytes([0x87])
    assert ordered[0].hex().startswith("0250")


def test_sixteen_of_sixteen_uses_the_top_opcode() -> None:
    """Sixteen required signatures use OP_16 on both the threshold and the key count."""
    public_keys = [BitcoinWallet.derive_public_key(f"{index:064x}") for index in range(1, 17)]
    script = MultisigScript(public_keys, 16)
    redeem = script.redeem_script()
    assert redeem[0] == 0x60
    assert redeem[-2] == 0x60
    assert redeem[-1] == 0xAE


@pytest.mark.parametrize(
    ("public_keys", "required"),
    [
        ([], 1),
        ([WIKI_PUBLIC], 0),
        ([WIKI_PUBLIC], 2),
        ([WIKI_PUBLIC, WIKI_PUBLIC], 1),
        ([WIKI_PUBLIC, "zz" * 33], 1),
        ([WIKI_PUBLIC, "abcd"], 1),
        ([WIKI_PUBLIC, 5], 1),
        ([WIKI_PUBLIC, "04" + "11" * 32], 1),
        ([WIKI_PUBLIC, "02" + "00" * 32], 1),
        (WIKI_PUBLIC, 1),
        ([WIKI_PUBLIC], True),
    ],
)
def test_invalid_multisig_sets_are_rejected(public_keys: object, required: object) -> None:
    """Empty, duplicate, off-curve, and out-of-range sets do not build a script."""
    with pytest.raises(ValueError, match="Multisig"):
        MultisigScript(public_keys, required)  # type: ignore[arg-type]  # boundary input


def test_more_than_sixteen_keys_are_rejected() -> None:
    """The redeem script opcode range stops at 16 public keys."""
    public_keys = [BitcoinWallet.derive_public_key(f"{index:064x}") for index in range(1, 18)]
    with pytest.raises(ValueError, match="Multisig"):
        MultisigScript(public_keys, 1)
