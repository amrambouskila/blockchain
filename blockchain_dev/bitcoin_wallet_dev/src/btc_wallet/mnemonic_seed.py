"""BIP-39 mnemonic phrases checked against the English wordlist before any seed is derived."""

from __future__ import annotations

from typing import Self

from mnemonic import Mnemonic

from btc_wallet.extended_key import ExtendedKey
from btc_wallet.wallet_constants import (
    MAX_PASSPHRASE_CHARACTERS,
    MNEMONIC_LONG_STRENGTH,
    MNEMONIC_LONG_WORDS,
    MNEMONIC_SHORT_STRENGTH,
    MNEMONIC_SHORT_WORDS,
)

_PHRASE_ERROR = "Mnemonic phrase must be 12 or 24 English words with a valid checksum."
_EXTRA_TEXT_ERROR = "Mnemonic passphrase must be text of at most 1024 characters."


class MnemonicSeed:
    """A BIP-39 seed derived only after the phrase and checksum have been checked."""

    def __init__(self, phrase: str, passphrase: str = "") -> None:
        words = Mnemonic("english")
        checked = _require_phrase(words, phrase)
        secret = _require_passphrase(passphrase)
        self._seed = Mnemonic.to_seed(checked, secret)

    @classmethod
    def generate(cls, word_count: int = MNEMONIC_SHORT_WORDS) -> tuple[str, Self]:
        """Return a new 12- or 24-word phrase and the seed derived from it with an empty passphrase."""
        if word_count == MNEMONIC_SHORT_WORDS:
            strength = MNEMONIC_SHORT_STRENGTH
        elif word_count == MNEMONIC_LONG_WORDS:
            strength = MNEMONIC_LONG_STRENGTH
        else:
            raise ValueError(_PHRASE_ERROR)
        phrase = Mnemonic("english").generate(strength)
        return phrase, cls(phrase)

    def master_key(self, *, testnet: bool = False) -> ExtendedKey:
        """Return the BIP-32 master key for this seed."""
        return ExtendedKey.from_seed(self._seed, testnet=testnet)

    def seed_bytes(self) -> bytes:
        """Return the 64-byte BIP-39 seed."""
        return self._seed


def _require_phrase(words: Mnemonic, phrase: str) -> str:
    """Return phrase when it is 12 or 24 listed words with a valid checksum."""
    if not isinstance(phrase, str) or phrase == "":
        raise ValueError(_PHRASE_ERROR)
    pieces = phrase.split(" ")
    if len(pieces) not in {MNEMONIC_SHORT_WORDS, MNEMONIC_LONG_WORDS}:
        raise ValueError(_PHRASE_ERROR)
    if any(piece not in words.wordlist for piece in pieces) or not words.check(phrase):
        raise ValueError(_PHRASE_ERROR)
    return phrase


def _require_passphrase(passphrase: str) -> str:
    """Return passphrase when it is a short string."""
    if not isinstance(passphrase, str) or len(passphrase) > MAX_PASSPHRASE_CHARACTERS:
        raise ValueError(_EXTRA_TEXT_ERROR)
    return passphrase
