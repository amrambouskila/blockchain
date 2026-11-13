"""BIP-32 extended keys checked against the published test vectors."""

from __future__ import annotations

import base58
import ecdsa
import pytest

from btc_wallet.extended_key import (
    ExtendedKey,
    _child_public_point,
    _child_secret,
    _parse_path,
    _tweak_from_left,
)

SEED_1 = "000102030405060708090a0b0c0d0e0f"
SEED_2 = (
    "fffcf9f6f3f0edeae7e4e1dedbd8d5d2cfccc9c6"
    "c3c0bdbab7b4b1aeaba8a5a29f9c999693908d8a8784817e7b"
    "7875726f6c696663605d5a5754514e4b484542"
)
SEED_3 = (
    "4b381541583be4423346c643850da4b320e46a87"
    "ae3d2a4e6da11eba819cd4acba45d239319ac14f"
    "863b8d5ab5a0d0c64d2e8a1e7d1457df2e5a3c51"
    "c73235be"
)
SEED_4 = "3ddd5602285899a946114506157c7997e5444528f3003f6134712147db19b678"  # gitleaks:allow bip-0032 vector 4

VECTOR_1 = """
m
xpub661MyMwAqRbcFtXgS5sYJABqqG9YLmC4Q1Rdap9gSE8NqtwybGhePY2gZ29ESFjqJoCu1Rupje8YtGqsefD265TMg7usUDFdp6W1EGMcet8
xprv9s21ZrQH143K3QTDL4LXw2F7HEK3wJUD2nW2nRk4stbPy6cq3jPPqjiChkVvvNKmPGJxWUtg6LnF5kejMRNNU3TGtRBeJgk33yuGBxrMPHi
m/0H
xpub68Gmy5EdvgibQVfPdqkBBCHxA5htiqg55crXYuXoQRKfDBFA1WEjWgP6LHhwBZeNK1VTsfTFUHCdrfp1bgwQ9xv5ski8PX9rL2dZXvgGDnw
xprv9uHRZZhk6KAJC1avXpDAp4MDc3sQKNxDiPvvkX8Br5ngLNv1TxvUxt4cV1rGL5hj6KCesnDYUhd7oWgT11eZG7XnxHrnYeSvkzY7d2bhkJ7
m/0H/1
xpub6ASuArnXKPbfEwhqN6e3mwBcDTgzisQN1wXN9BJcM47sSikHjJf3UFHKkNAWbWMiGj7Wf5uMash7SyYq527Hqck2AxYysAA7xmALppuCkwQ
xprv9wTYmMFdV23N2TdNG573QoEsfRrWKQgWeibmLntzniatZvR9BmLnvSxqu53Kw1UmYPxLgboyZQaXwTCg8MSY3H2EU4pWcQDnRnrVA1xe8fs
m/0H/1/2H
xpub6D4BDPcP2GT577Vvch3R8wDkScZWzQzMMUm3PWbmWvVJrZwQY4VUNgqFJPMM3No2dFDFGTsxxpG5uJh7n7epu4trkrX7x7DogT5Uv6fcLW5
xprv9z4pot5VBttmtdRTWfWQmoH1taj2axGVzFqSb8C9xaxKymcFzXBDptWmT7FwuEzG3ryjH4ktypQSAewRiNMjANTtpgP4mLTj34bhnZX7UiM
m/0H/1/2H/2
xpub6FHa3pjLCk84BayeJxFW2SP4XRrFd1JYnxeLeU8EqN3vDfZmbqBqaGJAyiLjTAwm6ZLRQUMv1ZACTj37sR62cfN7fe5JnJ7dh8zL4fiyLHV
xprvA2JDeKCSNNZky6uBCviVfJSKyQ1mDYahRjijr5idH2WwLsEd4Hsb2Tyh8RfQMuPh7f7RtyzTtdrbdqqsunu5Mm3wDvUAKRHSC34sJ7in334
m/0H/1/2H/2/1000000000
xpub6H1LXWLaKsWFhvm6RVpEL9P4KfRZSW7abD2ttkWP3SSQvnyA8FSVqNTEcYFgJS2UaFcxupHiYkro49S8yGasTvXEYBVPamhGW6cFJodrTHy
xprvA41z7zogVVwxVSgdKUHDy1SKmdb533PjDz7J6N6mV6uS3ze1ai8FHa8kmHScGpWmj4WggLyQjgPie1rFSruoUihUZREPSL39UNdE3BBDu76
""".strip()

VECTOR_2 = """
m
xpub661MyMwAqRbcFW31YEwpkMuc5THy2PSt5bDMsktWQcFF8syAmRUapSCGu8ED9W6oDMSgv6Zz8idoc4a6mr8BDzTJY47LJhkJ8UB7WEGuduB
xprv9s21ZrQH143K31xYSDQpPDxsXRTUcvj2iNHm5NUtrGiGG5e2DtALGdso3pGz6ssrdK4PFmM8NSpSBHNqPqm55Qn3LqFtT2emdEXVYsCzC2U
m/0
xpub69H7F5d8KSRgmmdJg2KhpAK8SR3DjMwAdkxj3ZuxV27CprR9LgpeyGmXUbC6wb7ERfvrnKZjXoUmmDznezpbZb7ap6r1D3tgFxHmwMkQTPH
xprv9vHkqa6EV4sPZHYqZznhT2NPtPCjKuDKGY38FBWLvgaDx45zo9WQRUT3dKYnjwih2yJD9mkrocEZXo1ex8G81dwSM1fwqWpWkeS3v86pgKt
m/0/2147483647H
xpub6ASAVgeehLbnwdqV6UKMHVzgqAG8Gr6riv3Fxxpj8ksbH9ebxaEyBLZ85ySDhKiLDBrQSARLq1uNRts8RuJiHjaDMBU4Zn9h8LZNnBC5y4a
xprv9wSp6B7kry3Vj9m1zSnLvN3xH8RdsPP1Mh7fAaR7aRLcQMKTR2vidYEeEg2mUCTAwCd6vnxVrcjfy2kRgVsFawNzmjuHc2YmYRmagcEPdU9
m/0/2147483647H/1
xpub6DF8uhdarytz3FWdA8TvFSvvAh8dP3283MY7p2V4SeE2wyWmG5mg5EwVvmdMVCQcoNJxGoWaU9DCWh89LojfZ537wTfunKau47EL2dhHKon
xprv9zFnWC6h2cLgpmSA46vutJzBcfJ8yaJGg8cX1e5StJh45BBciYTRXSd25UEPVuesF9yog62tGAQtHjXajPPdbRCHuWS6T8XA2ECKADdw4Ef
m/0/2147483647H/1/2147483646H
xpub6ERApfZwUNrhLCkDtcHTcxd75RbzS1ed54G1LkBUHQVHQKqhMkhgbmJbZRkrgZw4koxb5JaHWkY4ALHY2grBGRjaDMzQLcgJvLJuZZvRcEL
xprvA1RpRA33e1JQ7ifknakTFpgNXPmW2YvmhqLQYMmrj4xJXXWYpDPS3xz7iAxn8L39njGVyuoseXzU6rcxFLJ8HFsTjSyQbLYnMpCqE2VbFWc
m/0/2147483647H/1/2147483646H/2
xpub6FnCn6nSzZAw5Tw7cgR9bi15UV96gLZhjDstkXXxvCLsUXBGXPdSnLFbdpq8p9HmGsApME5hQTZ3emM2rnY5agb9rXpVGyy3bdW6EEgAtqt
xprvA2nrNbFZABcdryreWet9Ea4LvTJcGsqrMzxHx98MMrotbir7yrKCEXw7nadnHM8Dq38EGfSh6dqA9QWTyefMLEcBYJUuekgW4BYPJcr9E7j
""".strip()

VECTOR_3 = """
m
xpub661MyMwAqRbcEZVB4dScxMAdx6d4nFc9nvyvH3v4gJL378CSRZiYmhRoP7mBy6gSPSCYk6SzXPTf3ND1cZAceL7SfJ1Z3GC8vBgp2epUt13
xprv9s21ZrQH143K25QhxbucbDDuQ4naNntJRi4KUfWT7xo4EKsHt2QJDu7KXp1A3u7Bi1j8ph3EGsZ9Xvz9dGuVrtHHs7pXeTzjuxBrCmmhgC6
m/0H
xpub68NZiKmJWnxxS6aaHmn81bvJeTESw724CRDs6HbuccFQN9Ku14VQrADWgqbhhTHBaohPX4CjNLf9fq9MYo6oDaPPLPxSb7gwQN3ih19Zm4Y
xprv9uPDJpEQgRQfDcW7BkF7eTya6RPxXeJCqCJGHuCJ4GiRVLzkTXBAJMu2qaMWPrS7AANYqdq6vcBcBUdJCVVFceUvJFjaPdGZ2y9WACViL4L
""".strip()

VECTOR_4 = """
m
xpub661MyMwAqRbcGczjuMoRm6dXaLDEhW1u34gKenbeYqAix21mdUKJyuyu5F1rzYGVxyL6tmgBUAEPrEz92mBXjByMRiJdba9wpnN37RLLAXa
xprv9s21ZrQH143K48vGoLGRPxgo2JNkJ3J3fqkirQC2zVdk5Dgd5w14S7fRDyHH4dWNHUgkvsvNDCkvAwcSHNAQwhwgNMgZhLtQC63zxwhQmRv
m/0H
xpub69AUMk3qDBi3uW1sXgjCmVjJ2G6WQoYSnNHyzkmdCHEhSZ4tBok37xfFEqHd2AddP56Tqp4o56AePAgCjYdvpW2PU2jbUPFKsav5ut6Ch1m
xprv9vB7xEWwNp9kh1wQRfCCQMnZUEG21LpbR9NPCNN1dwhiZkjjeGRnaALmPXCX7SgjFTiCTT6bXes17boXtjq3xLpcDjzEuGLQBM5ohqkao9G
m/0H/1H
xpub6BJA1jSqiukeaesWfxe6sNK9CCGaujFFSJLomWHprUL9DePQ4JDkM5d88n49sMGJxrhpjazuXYWdMf17C9T5XnxkopaeS7jGk1GyyVziaMt
xprv9xJocDuwtYCMNAo3Zw76WENQeAS6WGXQ55RCy7tDJ8oALr4FWkuVoHJeHVAcAqiZLE7Je3vZJHxspZdFHfnBEjHqU5hG1Jaj32dVoS6XLT1
""".strip()

INVALID_EXTENDED = """
xpub661MyMwAqRbcEYS8w7XLSVeEsBXy79zSzH1J8vCdxAZningWLdN3zgtU6LBpB85b3D2yc8sfvZU521AAwdZafEz7mnzBBsz4wKY5fTtTQBm
xprv9s21ZrQH143K24Mfq5zL5MhWK9hUhhGbd45hLXo2Pq2oqzMMo63oStZzFGTQQD3dC4H2D5GBj7vWvSQaaBv5cxi9gafk7NF3pnBju6dwKvH
xpub661MyMwAqRbcEYS8w7XLSVeEsBXy79zSzH1J8vCdxAZningWLdN3zgtU6Txnt3siSujt9RCVYsx4qHZGc62TG4McvMGcAUjeuwZdduYEvFn
xprv9s21ZrQH143K24Mfq5zL5MhWK9hUhhGbd45hLXo2Pq2oqzMMo63oStZzFGpWnsj83BHtEy5Zt8CcDr1UiRXuWCmTQLxEK9vbz5gPstX92JQ
xpub661MyMwAqRbcEYS8w7XLSVeEsBXy79zSzH1J8vCdxAZningWLdN3zgtU6N8ZMMXctdiCjxTNq964yKkwrkBJJwpzZS4HS2fxvyYUA4q2Xe4
xprv9s21ZrQH143K24Mfq5zL5MhWK9hUhhGbd45hLXo2Pq2oqzMMo63oStZzFAzHGBP2UuGCqWLTAPLcMtD9y5gkZ6Eq3Rjuahrv17fEQ3Qen6J
xprv9s2SPatNQ9Vc6GTbVMFPFo7jsaZySyzk7L8n2uqKXJen3KUmvQNTuLh3fhZMBoG3G4ZW1N2kZuHEPY53qmbZzCHshoQnNf4GvELZfqTUrcv
xpub661no6RGEX3uJkY4bNnPcw4URcQTrSibUZ4NqJEw5eBkv7ovTwgiT91XX27VbEXGENhYRCf7hyEbWrR3FewATdCEebj6znwMfQkhRYHRLpJ
xprv9s21ZrQH4r4TsiLvyLXqM9P7k1K3EYhA1kkD6xuquB5i39AU8KF42acDyL3qsDbU9NmZn6MsGSUYZEsuoePmjzsB3eFKSUEh3Gu1N3cqVUN
xpub661MyMwAuDcm6CRQ5N4qiHKrJ39Xe1R1NyfouMKTTWcguwVcfrZJaNvhpebzGerh7gucBvzEQWRugZDuDXjNDRmXzSZe4c7mnTK97pTvGS8
DMwo58pR1QLEFihHiXPVykYB6fJmsTeHvyTp7hRThAtCX8CvYzgPcn8XnmdfHGMQzT7ayAmfo4z3gY5KfbrZWZ6St24UVf2Qgo6oujFktLHdHY4
DMwo58pR1QLEFihHiXPVykYB6fJmsTeHvyTp7hRThAtCX8CvYzgPcn8XnmdfHPmHJiEDXkTiJTVV9rHEBUem2mwVbbNfvT2MTcAqj3nesx8uBf9
xprv9s21ZrQH143K24Mfq5zL5MhWK9hUhhGbd45hLXo2Pq2oqzMMo63oStZzF93Y5wvzdUayhgkkFoicQZcP3y52uPPxFnfoLZB21Teqt1VvEHx
xprv9s21ZrQH143K24Mfq5zL5MhWK9hUhhGbd45hLXo2Pq2oqzMMo63oStZzFAzHGBP2UuGCqWLTAPLcMtD5SDKr24z3aiUvKr9bJpdrcLg1y3G
xpub661MyMwAqRbcEYS8w7XLSVeEsBXy79zSzH1J8vCdxAZningWLdN3zgtU6Q5JXayek4PRsn35jii4veMimro1xefsM58PgBMrvdYre8QyULY
xprv9s21ZrQH143K3QTDL4LXw2F7HEK3wJUD2nW2nRk4stbPy6cq3jPPqjiChkVvvNKmPGJxWUtg6LnF5kejMRNNU3TGtRBeJgk33yuGBxrMPHL
""".strip().splitlines()


def _rows(text: str) -> list[tuple[str, str, str]]:
    """Return path, public, and private rows from a BIP-32 vector block."""
    lines = text.splitlines()
    return [(lines[index], lines[index + 1], lines[index + 2]) for index in range(0, len(lines), 3)]


def _fields(node: ExtendedKey) -> dict[str, object]:
    """Return the constructor fields stored in a serialized extended key."""
    payload = base58.b58decode_check(node.serialize())
    return {
        "private_key": bytes.fromhex(node.private_hex()),
        "public_key": bytes.fromhex(node.public_hex()),
        "chain_code": payload[13:45],
        "depth": payload[4],
        "parent_fingerprint": payload[5:9],
        "child_index": int.from_bytes(payload[9:13], "big"),
        "testnet": node.is_testnet(),
    }


@pytest.mark.parametrize(
    ("seed_hex", "text"),
    [(SEED_1, VECTOR_1), (SEED_2, VECTOR_2), (SEED_3, VECTOR_3), (SEED_4, VECTOR_4)],
)
def test_bip32_vectors(seed_hex: str, text: str) -> None:
    """Each published path matches its xprv and xpub, and both forms parse back."""
    master = ExtendedKey.from_seed(bytes.fromhex(seed_hex))
    for path, public, private in _rows(text):
        node = master.derive_path(path)
        assert node.serialize() == private
        assert node.neuter().serialize() == public
        assert ExtendedKey.parse(private).serialize() == private
        assert ExtendedKey.parse(public).serialize() == public
        assert ExtendedKey.parse(public).public_hex() == node.public_hex()
        with pytest.raises(ValueError, match="no private key"):
            ExtendedKey.parse(public).private_hex()


def test_apostrophe_matches_hardened_mark() -> None:
    """A trailing apostrophe is the same hardened step as H."""
    master = ExtendedKey.from_seed(bytes.fromhex(SEED_1))
    assert master.derive_path("m/0'").serialize() == master.derive_path("m/0H").serialize()
    assert master.derive_path("m/2147483648").serialize() == master.derive_path("m/0H").serialize()


def test_public_derivation_matches_the_private_child() -> None:
    """A non-hardened child of a public parent matches the neutered private child."""
    parent = ExtendedKey.from_seed(bytes.fromhex(SEED_1)).derive_path("m/0H")
    public_child = parent.neuter().derive_path("M/1")
    private_child = parent.derive_path("m/1").neuter()
    assert public_child.serialize() == private_child.serialize()


def test_testnet_version_bytes_round_trip() -> None:
    """Swapping in the testnet version bytes is what from_seed(testnet=True) stores."""
    main = ExtendedKey.from_seed(bytes.fromhex(SEED_1))
    payload = bytearray(base58.b58decode_check(main.serialize()))
    payload[:4] = bytes.fromhex("04358394")
    encoded = base58.b58encode_check(bytes(payload)).decode()
    testnet = ExtendedKey.from_seed(bytes.fromhex(SEED_1), testnet=True)
    assert testnet.serialize() == encoded
    assert testnet.is_testnet() is True
    assert ExtendedKey.parse(encoded).neuter().serialize().startswith("tpub")
    assert main.is_testnet() is False


def test_public_parent_cannot_derive_hardened_or_private_path() -> None:
    """A neutered key can walk normal children and refuses hardened or private paths."""
    public = ExtendedKey.from_seed(bytes.fromhex(SEED_1)).neuter()
    with pytest.raises(ValueError, match="Hardened child keys"):
        public.derive(2**31)
    with pytest.raises(ValueError, match="private path"):
        public.derive_path("m/0")
    assert public.derive_path("M").serialize() == public.serialize()


def test_depth_limit() -> None:
    """A node at depth 255 cannot derive another child."""
    node = ExtendedKey.from_seed(bytes.fromhex(SEED_1))
    for _index in range(255):
        node = node.derive(0)
    with pytest.raises(ValueError, match="Derivation path"):
        node.derive(0)


@pytest.mark.parametrize("encoded", INVALID_EXTENDED)
def test_invalid_extended_keys_are_rejected(encoded: str) -> None:
    """BIP-32 vector 5 strings fail without the string appearing in the error."""
    with pytest.raises(ValueError, match="Extended key is invalid") as caught:
        ExtendedKey.parse(encoded)
    assert encoded not in str(caught.value)


@pytest.mark.parametrize("seed", [b"", b"\x00" * 15, b"\x00" * 65, "0011"])
def test_seed_length_is_bounded(seed: object) -> None:
    """Master seeds must be 16 to 64 bytes."""
    with pytest.raises(ValueError, match="Extended key is invalid"):
        ExtendedKey.from_seed(seed)  # type: ignore[arg-type]  # non-bytes boundary input


def test_constructor_rejects_inconsistent_material() -> None:
    """Depth, fingerprint, chain code, and the public point are checked together."""
    master = ExtendedKey.from_seed(bytes.fromhex(SEED_1))
    fields = _fields(master)
    other = ExtendedKey.from_seed(bytes.fromhex("11" * 16))
    mismatched = dict(fields)
    mismatched["public_key"] = bytes.fromhex(other.public_hex())
    broken = [
        {**fields, "testnet": 1},
        {**fields, "chain_code": b"\x00" * 31},
        {**fields, "depth": True},
        {**fields, "depth": 256},
        {**fields, "parent_fingerprint": b"\x00" * 3},
        {**fields, "child_index": True},
        {**fields, "child_index": 1},
        {**fields, "private_key": b"\x01"},
        mismatched,
    ]
    for kwargs in broken:
        with pytest.raises(ValueError, match="Extended key is invalid"):
            ExtendedKey(**kwargs)  # type: ignore[arg-type]  # boundary cases are intentionally mistyped


@pytest.mark.parametrize(
    "encoded", ["", 5, "not-base58", base58.b58encode_check(b"\x04\x88\xad\xe4" + b"\x11" * 10).decode()]
)
def test_parse_rejects_malformed_text(encoded: object) -> None:
    """Empty, non-text, bad checksum, and the wrong length all fail the same way."""
    with pytest.raises(ValueError, match="Extended key is invalid"):
        ExtendedKey.parse(encoded)  # type: ignore[arg-type]  # non-str boundary input


@pytest.mark.parametrize(
    "path",
    ["", "n/0", "m/", "m/01", "m/0H/2147483648H", "m/4294967296", "m/-1", 5, "m/0x1"],
)
def test_invalid_paths(path: object) -> None:
    """Path text must be m or M plus plain or hardened indexes."""
    master = ExtendedKey.from_seed(bytes.fromhex(SEED_1))
    with pytest.raises(ValueError, match="Derivation path"):
        master.derive_path(path)  # type: ignore[arg-type]  # non-str boundary input
    with pytest.raises(ValueError, match="Derivation path"):
        master.derive(True)  # type: ignore[arg-type]  # bool is not a child index


def test_private_path_on_a_private_root_keeps_the_master() -> None:
    """derive_path('m') returns the same private serialization."""
    master = ExtendedKey.from_seed(bytes.fromhex(SEED_1))
    assert master.derive_path("m").serialize() == master.serialize()
    assert master.derive_path("M").serialize().startswith("xpub")


def test_tweak_helpers_reject_unusable_values() -> None:
    """Zero is a valid tweak, and an out-of-range sum or the point at infinity is not a child."""
    order = ecdsa.SECP256k1.order
    parent = (order - 1) * ecdsa.SECP256k1.generator
    assert _tweak_from_left(b"\x00" * 32) == 0
    assert _tweak_from_left(order.to_bytes(32, "big")) is None
    assert _child_secret(1, None) is None
    assert _child_secret(1, order) is None
    assert _child_secret(1, order - 1) is None
    assert _child_secret(2, 3) == 5
    assert _child_public_point(None, parent) is None
    assert _child_public_point(order, parent) is None
    assert _child_public_point(0, parent) == parent
    assert _child_public_point(1, parent) is None
    assert _parse_path("m/0h") == ("m", [2**31])
