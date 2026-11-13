"""BIP-44 accounts at m/44'/coin'/account'/change/index."""

from __future__ import annotations

from bitcoin_wallet import BitcoinWallet
from btc_wallet.extended_key import ExtendedKey
from btc_wallet.segwit_address import SegwitAddress
from btc_wallet.wallet_constants import (
    BIP44_COIN_MAINNET,
    BIP44_COIN_TESTNET,
    BIP44_EXTERNAL_CHAIN,
    BIP44_INTERNAL_CHAIN,
    BIP44_PURPOSE,
    HARDENED_INDEX,
    HRP_MAINNET,
    HRP_TESTNET,
)

_ACCOUNT_ERROR = "BIP-44 account, chain, or index is invalid."


class Bip44Account:
    """One BIP-44 account derived with hardened purpose, coin, and account indexes."""

    def __init__(self, master: ExtendedKey, account: int = 0) -> None:
        if type(account) is not int or not 0 <= account < HARDENED_INDEX:
            raise ValueError(_ACCOUNT_ERROR)
        try:
            master.private_hex()
        except ValueError:
            raise ValueError("A BIP-44 account needs the master private key.") from None
        coin = BIP44_COIN_TESTNET if master.is_testnet() else BIP44_COIN_MAINNET
        self._account = (
            master.derive(BIP44_PURPOSE + HARDENED_INDEX).derive(coin + HARDENED_INDEX).derive(account + HARDENED_INDEX)
        )
        self._hrp = HRP_TESTNET if master.is_testnet() else HRP_MAINNET

    def receive_address(self, index: int = 0) -> str:
        """Return the external-chain P2PKH address at index."""
        return BitcoinWallet.generate_address(self._node(BIP44_EXTERNAL_CHAIN, index).public_hex())

    def change_address(self, index: int = 0) -> str:
        """Return the internal-chain P2PKH address at index."""
        return BitcoinWallet.generate_address(self._node(BIP44_INTERNAL_CHAIN, index).public_hex())

    def receive_segwit_address(self, index: int = 0) -> str:
        """Return the external-chain P2WPKH address at index."""
        return SegwitAddress.p2wpkh(self._node(BIP44_EXTERNAL_CHAIN, index).public_hex(), hrp=self._hrp)

    def change_segwit_address(self, index: int = 0) -> str:
        """Return the internal-chain P2WPKH address at index."""
        return SegwitAddress.p2wpkh(self._node(BIP44_INTERNAL_CHAIN, index).public_hex(), hrp=self._hrp)

    def private_hex(self, index: int = 0, *, change: bool = False) -> str:
        """Return the private key hex for the external chain, or the change chain when change is set."""
        if type(change) is not bool:
            raise ValueError(_ACCOUNT_ERROR)
        chain = BIP44_INTERNAL_CHAIN if change else BIP44_EXTERNAL_CHAIN
        return self._node(chain, index).private_hex()

    def account_extended_private(self) -> str:
        """Return the account-level xprv or tprv."""
        return self._account.serialize()

    def account_extended_public(self) -> str:
        """Return the account-level xpub or tpub."""
        return self._account.neuter().serialize()

    def _node(self, chain: int, index: int) -> ExtendedKey:
        """Return the node at change/index under this account."""
        if type(index) is not int or not 0 <= index < HARDENED_INDEX:
            raise ValueError(_ACCOUNT_ERROR)
        return self._account.derive(chain).derive(index)
