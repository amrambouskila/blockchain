"""BIP-44 accounts at m/44'/coin'/account'/change/index."""

from __future__ import annotations

import pytest

from bitcoin_wallet import BitcoinWallet
from btc_wallet.bip44_account import Bip44Account
from btc_wallet.extended_key import ExtendedKey
from btc_wallet.segwit_address import SegwitAddress

SEED = "000102030405060708090a0b0c0d0e0f"


def _account(testnet: bool = False, account: int = 0) -> tuple[ExtendedKey, Bip44Account]:
    """Return a master key and the BIP-44 account derived from the BIP-32 vector-1 seed."""
    master = ExtendedKey.from_seed(bytes.fromhex(SEED), testnet=testnet)
    return master, Bip44Account(master, account)


def test_receive_and_change_match_the_path() -> None:
    """External and internal addresses match the hardened BIP-44 path, including apostrophe form."""
    master, account = _account()
    receive = master.derive_path("m/44'/0'/0'/0/0")
    change = master.derive_path("m/44H/0H/0H/1/1")
    assert account.receive_address(0) == BitcoinWallet.generate_address(receive.public_hex())
    assert account.private_hex() == receive.private_hex()
    assert account.change_address(1) == BitcoinWallet.generate_address(change.public_hex())
    assert account.private_hex(1, change=True) == change.private_hex()
    assert account.receive_segwit_address(0) == SegwitAddress.p2wpkh(receive.public_hex())
    assert account.receive_address(0) != account.change_address(0)


def test_account_extended_keys_match_the_account_node() -> None:
    """The account xprv and xpub are the node at m/44H/0H/0H."""
    master, account = _account()
    node = master.derive_path("m/44H/0H/0H")
    assert account.account_extended_private() == node.serialize()
    assert account.account_extended_public() == node.neuter().serialize()
    second = master.derive_path("m/44H/0H/1H")
    assert Bip44Account(master, 1).account_extended_private() == second.serialize()


def test_testnet_uses_coin_one_and_the_tb_prefix() -> None:
    """Testnet accounts use coin 1 and bech32 prefix tb."""
    master, account = _account(testnet=True)
    receive = master.derive_path("m/44H/1H/0H/0/0")
    assert account.receive_address(0) == BitcoinWallet.generate_address(receive.public_hex())
    assert account.receive_segwit_address(0) == SegwitAddress.p2wpkh(receive.public_hex(), hrp="tb")
    assert account.change_segwit_address(0).startswith("tb1")
    assert account.account_extended_private().startswith("tprv")


@pytest.mark.parametrize("account", [True, -1, 2**31])
def test_account_index_is_bounded(account: object) -> None:
    """The account index is a whole number below 2^31."""
    master = ExtendedKey.from_seed(bytes.fromhex(SEED))
    with pytest.raises(ValueError, match="invalid"):
        Bip44Account(master, account)  # type: ignore[arg-type]  # non-int boundary input


def test_public_master_is_rejected() -> None:
    """An account cannot be built from a public extended key."""
    master = ExtendedKey.from_seed(bytes.fromhex(SEED)).neuter()
    with pytest.raises(ValueError, match="master private key"):
        Bip44Account(master)


@pytest.mark.parametrize("index", [True, -1, 2**31])
def test_address_index_is_bounded(index: object) -> None:
    """Address indexes stay below 2^31, and change must be a boolean."""
    _master, account = _account()
    with pytest.raises(ValueError, match="invalid"):
        account.receive_address(index)  # type: ignore[arg-type]  # non-int boundary input
    with pytest.raises(ValueError, match="invalid"):
        account.private_hex(change="yes")  # type: ignore[arg-type]  # non-bool boundary input
