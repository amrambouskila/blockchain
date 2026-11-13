"""Bech32 and Bech32m addresses checked against BIP-173 and BIP-350 vectors."""

from __future__ import annotations

import bech32
import pytest

from btc_wallet import segwit_address
from btc_wallet.segwit_address import SegwitAddress

GENERATOR_POINT = "0279BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798"
P2WPKH = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
P2WSH = "bc1qrp33g0q5c5txsp9arysrx4k6zdkfs4nce4xj0gdcccefvpysxf3qccfmv3"

VALID = (
    ("BC1QW508D6QEJXTDG4Y5R3ZARVARY0C5XW7KV8F3T4", "0014751e76e8199196d454941c45d1b3a323f1433bd6"),
    (
        "tb1qrp33g0q5c5txsp9arysrx4k6zdkfs4nce4xj0gdcccefvpysxf3q0sl5k7",
        "00201863143c14c5166804bd19203356da136c985678cd4d27a1b8c6329604903262",
    ),
    (
        "bc1pw508d6qejxtdg4y5r3zarvary0c5xw7kw508d6qejxtdg4y5r3zarvary0c5xw7kt5nd6y",
        "5128751e76e8199196d454941c45d1b3a323f1433bd6751e76e8199196d454941c45d1b3a323f1433bd6",
    ),
    ("BC1SW50QGDZ25J", "6002751e"),
    ("bc1zw508d6qejxtdg4y5r3zarvaryvaxxpcs", "5210751e76e8199196d454941c45d1b3a323"),
    (
        "tb1qqqqqp399et2xygdj5xreqhjjvcmzhxw4aywxecjdzew6hylgvsesrxh6hy",
        "0020000000c4a5cad46221b2a187905e5266362b99d5e91c6ce24d165dab93e86433",
    ),
    (
        "tb1pqqqqp399et2xygdj5xreqhjjvcmzhxw4aywxecjdzew6hylgvsesf3hn0c",
        "5120000000c4a5cad46221b2a187905e5266362b99d5e91c6ce24d165dab93e86433",
    ),
    (
        "bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0",
        "512079be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798",
    ),
)

INVALID = (
    "tc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vq5zuyut",
    "bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqh2y7hd",
    "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kemeawh",
    "BC1QR508D6QEJXTDG4Y5R3ZARVARYV98GJ9P",
    "tb1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vq47Zagq",
    "bc1gmk9yu",
)


def _bech32m(hrp: str, version: int, program: bytes) -> str:
    """Build a Bech32m string with the library polymod, independent of SegwitAddress.encode."""
    converted = bech32.convertbits(program, 8, 5)
    assert converted is not None
    payload = [version, *converted]
    values = [*bech32.bech32_hrp_expand(hrp), *payload]
    polymod = bech32.bech32_polymod([*values, 0, 0, 0, 0, 0, 0]) ^ 0x2BC830A3
    checksum = [(polymod >> (5 * (5 - index))) & 31 for index in range(6)]
    return hrp + "1" + "".join(bech32.CHARSET[value] for value in [*payload, *checksum])


@pytest.mark.parametrize(("address", "script_hex"), VALID)
def test_bip350_vectors(address: str, script_hex: str) -> None:
    """Each published address decodes to its scriptPubKey on the right network."""
    hrp = "tb" if address.lower().startswith("tb") else "bc"
    assert SegwitAddress.script_pubkey(address, hrp=hrp).hex() == script_hex
    version, program = SegwitAddress.decode(address, hrp=hrp)
    assert SegwitAddress.encode(version, program, hrp=hrp).lower() == address.lower()


def test_p2wpkh_and_p2wsh_match_bip173() -> None:
    """The compressed generator point pays to the published v0 witness addresses."""
    script = bytes([0x21]) + bytes.fromhex(GENERATOR_POINT) + bytes([0xAC])
    assert SegwitAddress.p2wpkh(GENERATOR_POINT) == P2WPKH
    assert SegwitAddress.p2wpkh(GENERATOR_POINT.lower(), hrp="tb").startswith("tb1q")
    assert SegwitAddress.p2wsh(script) == P2WSH


def test_bad_checksum_is_rejected() -> None:
    """Changing the last character breaks the checksum."""
    last = "p" if P2WPKH[-1] != "p" else "q"
    with pytest.raises(ValueError, match="SegWit address is invalid"):
        SegwitAddress.decode(P2WPKH[:-1] + last)


@pytest.mark.parametrize("address", INVALID)
def test_invalid_addresses_raise(address: str) -> None:
    """Bad human-readable parts, checksums, lengths, and mixed case are rejected."""
    hrp = "tb" if address.lower().startswith("tb") else "bc"
    with pytest.raises(ValueError, match="SegWit address is invalid"):
        SegwitAddress.decode(address, hrp=hrp)


@pytest.mark.parametrize(
    "address",
    ["", "b" * 91, "bc1q\n", "1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4", "bc1qqqq", 5, P2WPKH.replace("q", "b", 1)],
)
def test_decode_rejects_malformed_text(address: object) -> None:
    """Empty, overlong, non-text, and bad-character strings fail before a program is returned."""
    with pytest.raises(ValueError, match="SegWit address is invalid"):
        SegwitAddress.decode(address)  # type: ignore[arg-type]  # non-str boundary input


def test_hrp_mismatch_and_high_witness_version() -> None:
    """A mainnet address is not a testnet address, and witness version 17 is rejected."""
    with pytest.raises(ValueError, match="SegWit address is invalid"):
        SegwitAddress.decode(P2WPKH, hrp="tb")
    high = _bech32m("bc", 17, b"\x00\x01")
    with pytest.raises(ValueError, match="SegWit address is invalid"):
        SegwitAddress.decode(high)


def _checksum_only() -> str:
    """Return a bc1 string whose checksum is valid and whose data payload is empty."""
    values = list(bech32.bech32_hrp_expand("bc"))
    polymod = bech32.bech32_polymod([*values, 0, 0, 0, 0, 0, 0]) ^ 1
    checksum = [(polymod >> (5 * (5 - index))) & 31 for index in range(6)]
    return "bc1" + "".join(bech32.CHARSET[value] for value in checksum)


def test_empty_checksum_payload_is_rejected() -> None:
    """A valid checksum with no witness version is not an address."""
    with pytest.raises(ValueError, match="SegWit address is invalid"):
        SegwitAddress.decode(_checksum_only())


@pytest.mark.parametrize(
    ("version", "program"),
    [(True, b"\x11" * 20), (-1, b"\x11" * 20), (0, b"\x11" * 21), (1, b"\x11"), (0, "11")],
)
def test_encode_rejects_bad_programs(version: object, program: object) -> None:
    """Witness version and program length are checked before a checksum is built."""
    with pytest.raises(ValueError, match="SegWit address is invalid"):
        SegwitAddress.encode(version, program)  # type: ignore[arg-type]  # boundary input


def test_encode_rejects_a_library_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing or mismatched library encoding does not return an address."""
    monkeypatch.setattr(segwit_address.bech32, "encode", lambda *_args, **_kwargs: None)
    with pytest.raises(ValueError, match="SegWit address is invalid"):
        SegwitAddress.encode(0, b"\x11" * 20)
    monkeypatch.setattr(segwit_address.bech32, "encode", lambda *_args, **_kwargs: P2WPKH)
    with pytest.raises(ValueError, match="SegWit address is invalid"):
        SegwitAddress.encode(0, b"\x22" * 20)


def test_convertbits_failure_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """A program that cannot be regrouped into 5-bit values is rejected."""
    monkeypatch.setattr(segwit_address.bech32, "convertbits", lambda *_args, **_kwargs: None)
    with pytest.raises(ValueError, match="SegWit address is invalid"):
        SegwitAddress.encode(1, b"\x11" * 2)


@pytest.mark.parametrize("hrp", ["BC", "bcrt", ""])
def test_hrp_is_bc_or_tb(hrp: str) -> None:
    """Only the mainnet and testnet human-readable parts are accepted."""
    with pytest.raises(ValueError, match="SegWit address is invalid"):
        SegwitAddress.decode(P2WPKH, hrp=hrp)


@pytest.mark.parametrize("public_key", ["zz" * 33, "04" + "11" * 32, "02" + "00" * 32, 5, GENERATOR_POINT[:-2]])
def test_p2wpkh_rejects_a_bad_public_key(public_key: object) -> None:
    """Pay-to-witness-public-key-hash needs one compressed point on the curve."""
    with pytest.raises(ValueError, match="SegWit address is invalid"):
        SegwitAddress.p2wpkh(public_key)  # type: ignore[arg-type]  # non-str boundary input


def test_p2wsh_rejects_an_empty_script() -> None:
    """An empty witness script is not hashed into an address."""
    with pytest.raises(ValueError, match="SegWit address is invalid"):
        SegwitAddress.p2wsh(b"")
    with pytest.raises(ValueError, match="SegWit address is invalid"):
        SegwitAddress.p2wsh("ac")  # type: ignore[arg-type]  # non-bytes boundary input
