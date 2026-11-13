"""BIP-39 phrases checked against the English wordlist and a published seed."""

from __future__ import annotations

import pytest
from mnemonic import Mnemonic

from btc_wallet.bip44_account import Bip44Account
from btc_wallet.mnemonic_seed import MnemonicSeed

ABANDON = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
TREZOR_SEED = (
    "c55257c360c07c72029aebc1b53c05ed0362ada38ead3e3e"
    "9efa3708e53495531f09a6987599d18264c1e1c92f2cf141"
    "630c7a3c4ab7c81b2f001698e7463b04"
)


def test_trezor_passphrase_matches_the_published_seed() -> None:
    """The all-abandon phrase with passphrase TREZOR produces the published 64-byte seed."""
    first = MnemonicSeed(ABANDON, "TREZOR")
    second = MnemonicSeed(ABANDON, "TREZOR")
    assert first.seed_bytes() == bytes.fromhex(TREZOR_SEED)
    assert first.master_key().serialize() == second.master_key().serialize()
    assert first.master_key(testnet=True).is_testnet() is True
    receive = Bip44Account(first.master_key()).receive_address(0)
    assert receive == Bip44Account(second.master_key()).receive_address(0)


def test_empty_passphrase_changes_the_seed() -> None:
    """An empty passphrase is allowed and does not match the TREZOR seed."""
    seed = MnemonicSeed(ABANDON)
    assert len(seed.seed_bytes()) == 64
    assert seed.seed_bytes() != bytes.fromhex(TREZOR_SEED)
    assert seed.master_key().is_testnet() is False


@pytest.mark.parametrize("word_count", [12, 24])
def test_generate_returns_a_checksummed_phrase(word_count: int) -> None:
    """Generated phrases are 12 or 24 listed words and rebuild the same seed."""
    phrase, seed = MnemonicSeed.generate(word_count)
    assert len(phrase.split(" ")) == word_count
    assert Mnemonic("english").check(phrase) is True
    assert MnemonicSeed(phrase).seed_bytes() == seed.seed_bytes()


def test_generate_rejects_other_lengths() -> None:
    """Fifteen, eighteen, and twenty-one words are outside this wallet even if the library allows them."""
    with pytest.raises(ValueError, match="12 or 24"):
        MnemonicSeed.generate(15)


@pytest.mark.parametrize("strength", [160, 192, 224])
def test_library_lengths_are_rejected(strength: int) -> None:
    """A valid phrase of another length still cannot build a seed."""
    phrase = Mnemonic("english").generate(strength)
    with pytest.raises(ValueError, match="12 or 24") as caught:
        MnemonicSeed(phrase)
    assert phrase not in str(caught.value)


def test_bad_phrase_is_rejected_without_echoing_it() -> None:
    """A checksum failure and an unknown word share one error that omits the phrase."""
    words = ABANDON.split(" ")
    words[-1] = "abandon"
    bad_checksum = " ".join(words)
    unknown = ABANDON.replace("about", "notaword")
    for phrase in (bad_checksum, unknown, "abandon"):
        with pytest.raises(ValueError, match="12 or 24") as caught:
            MnemonicSeed(phrase)
        assert phrase not in str(caught.value)
    with pytest.raises(ValueError, match="12 or 24"):
        MnemonicSeed("")
    with pytest.raises(ValueError, match="12 or 24"):
        MnemonicSeed(12)  # type: ignore[arg-type]  # non-str boundary input


@pytest.mark.parametrize("extra", [5, "x" * 1025])
def test_passphrase_must_be_short_text(extra: object) -> None:
    """The extra passphrase is text of at most 1024 characters."""
    with pytest.raises(ValueError, match="1024"):
        MnemonicSeed(ABANDON, extra)  # type: ignore[arg-type]  # non-str boundary input
    assert len(MnemonicSeed(ABANDON, "x" * 1024).seed_bytes()) == 64
