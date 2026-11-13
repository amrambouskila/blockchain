"""Published-vector and RPC-boundary tests for the Phase 1 wallet."""

from __future__ import annotations

import http.client
import json
import logging
import os
import stat
import subprocess
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock
from urllib.parse import quote, unquote, urlsplit

import base58
import ecdsa
import pytest
from bitcoinrpc.authproxy import JSONRPCException

import bitcoin_wallet
from bitcoin_wallet import BitcoinCoreResponseError, BitcoinWallet
from constants import (
    CREDENTIALS_FILE_MODE,
    DEFAULT_TX_FEE_BTC,
    HASH160_BYTES,
    MAX_CONFIRMATIONS,
    MAX_CREDENTIALS_BYTES,
    MAX_UTXO_COUNT,
    MIN_CONFIRMATIONS,
    P2SH_VERSION,
    PRIVATE_KEY_BYTES,
    RPC_HOST,
    RPC_PASSWORD_KEY,
    RPC_PORT,
    RPC_SCHEME,
    RPC_TIMEOUT_SECONDS,
    RPC_USERNAME_KEY,
    SATOSHI,
    WIF_COMPRESSED_FLAG,
    WIF_VERSION,
)

# Bitcoin wiki, "Technical background of version 1 Bitcoin addresses" (compressed).
WIKI_PRIVATE_KEY = (
    "18e14a7b6a307f426a94f8114701e7c8e774e7f9a47e2c2035db29a206321725"  # gitleaks:allow wiki compressed key
)
WIKI_PUBLIC_KEY = (
    "0250863ad64a87ae8a2fe83c1af1a8403cb53f53e486d8511dad8a04887e5b2352"  # gitleaks:allow wiki compressed pubkey
)
WIKI_ADDRESS = "1PMycacnJaSqwwJqjawXBErnLsZ7RkXUAs"

# SEC 2 generator, private key 1. Compressed address only.
KEY_ONE = "0000000000000000000000000000000000000000000000000000000000000001"  # gitleaks:allow secp256k1 generator key 1
KEY_ONE_PUBLIC_KEY = (
    "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"  # gitleaks:allow secp256k1 generator pubkey
)
KEY_ONE_ADDRESS = "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"  # gitleaks:allow public address

# Private key 6 exercises the odd compressed prefix. Point taken from ecdsa, address from HASH160.
KEY_SIX = "0000000000000000000000000000000000000000000000000000000000000006"  # gitleaks:allow odd prefix key 6
KEY_SIX_PUBLIC_KEY = (
    "03fff97bd5755eeea420453a14355235d382f6472f8568a18b2f057a1460297556"  # gitleaks:allow odd prefix pubkey
)
KEY_SIX_ADDRESS = "1Cf2hs39Woi61YNkYGUAcohL2K2q4pawBq"  # gitleaks:allow public address

# Bitcoin Core v25 src/test/key_tests.cpp (MIT). Hex is decoded from the WIF inside the test.
CORE_WIF_ONE = (
    "Kwr371tjA9u2rFSMZjTNun2PXXP3WPZu2afRHTcta6KxEUdm1vEw"  # gitleaks:allow bitcoin/bitcoin key_tests.cpp strSecret1C
)
CORE_ADDRESS_ONE = "1NoJrossxPBKfCHuJXT4HadJrXRE9Fxiqs"
CORE_WIF_TWO = (
    "L3Hq7a8FEQwJkW1M2GNKDW28546Vp5miewcCzSqUD9kCAXrJdS3g"  # gitleaks:allow bitcoin/bitcoin key_tests.cpp strSecret2C
)
CORE_ADDRESS_TWO = "1CRj2HyM1CXWzHAXLQtiGLyggNT9WQqsDs"

_REDACTED = "[redacted]"


def _hex_from_compressed_wif(wif: str) -> str:
    """Return the 32-byte hex key encoded by a compressed WIF."""
    payload = base58.b58decode_check(wif)
    assert payload[:1] == WIF_VERSION
    assert payload[-1:] == WIF_COMPRESSED_FLAG
    assert len(payload) == 34
    return payload[1:33].hex()


def _utxo(amount: object, vout: object = 0, txid: str | None = None) -> dict[str, object]:
    """Return one listunspent-shaped entry."""
    return {"txid": "ab" * 32 if txid is None else txid, "vout": vout, "amount": amount}


def _install_rpc(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Replace AuthServiceProxy with a recorder and return the shared client."""
    proxy = MagicMock()
    proxy.listunspent.return_value = []
    proxy.createrawtransaction.return_value = "aa"
    proxy.signrawtransactionwithkey.return_value = {"hex": "bb", "complete": True}
    proxy.sendrawtransaction.return_value = "ab" * 32

    def factory(service_url: str, timeout: int = RPC_TIMEOUT_SECONDS) -> MagicMock:
        """Record service_url and timeout, then return the shared client."""
        proxy.service_url = service_url
        proxy.timeout = timeout
        return proxy

    monkeypatch.setattr(bitcoin_wallet, "AuthServiceProxy", factory)
    return proxy


def _make_wallet(
    monkeypatch: pytest.MonkeyPatch,
    private_key: str | None = KEY_ONE,
) -> tuple[BitcoinWallet, MagicMock]:
    """Return a wallet bound to the fake RPC client."""
    proxy = _install_rpc(monkeypatch)
    return BitcoinWallet(private_key=private_key), proxy


def _p2sh_address() -> str:
    """Return a mainnet P2SH address this wallet must reject."""
    return base58.b58encode_check(P2SH_VERSION + b"\x11" * HASH160_BYTES).decode()


def _bad_checksum(address: str) -> str:
    """Return address with its final character changed."""
    replacement = "1" if address[-1] != "1" else "2"
    return address[:-1] + replacement


def _assert_owner_only(path: Path) -> None:
    """Require a POSIX 0600 mode or a Windows ACL that drops broad inherited entries."""
    if os.name != "nt":
        assert stat.S_IMODE(path.stat().st_mode) == CREDENTIALS_FILE_MODE
        return
    # Read-only icacls listing of a file this test created. shell is false.
    completed = subprocess.run(  # noqa: S603
        [str(BitcoinWallet._windows_icacls_path()), str(path)],
        check=False,
        capture_output=True,
        text=True,
        shell=False,
    )
    assert completed.returncode == 0
    listing = completed.stdout.casefold()
    assert "everyone" not in listing
    assert "builtin\\users" not in listing
    assert "authenticated users" not in listing


def test_bitcoinrpc_logger_is_disabled() -> None:
    """The RPC library logger stays off so it cannot record a private key."""
    assert logging.getLogger("BitcoinRPC").disabled is True


def test_generate_private_key_uses_curve_range() -> None:
    """Generated keys are 32-byte hex values inside the secp256k1 order."""
    first = BitcoinWallet.generate_private_key()
    second = BitcoinWallet.generate_private_key()
    assert first != second
    for key in (first, second):
        assert len(key) == PRIVATE_KEY_BYTES * 2
        value = int(key, 16)
        assert 0 < value < ecdsa.SECP256k1.order
        assert BitcoinWallet.derive_public_key(key).startswith(("02", "03"))


def test_private_key_range_helper() -> None:
    """Zero and the curve order are rejected; one and order-minus-one are accepted."""
    order = ecdsa.SECP256k1.order
    assert BitcoinWallet._private_key_hex_from_int(0) is None
    assert BitcoinWallet._private_key_hex_from_int(order) is None
    assert BitcoinWallet._private_key_hex_from_int(1) == "0" * 63 + "1"
    below_order = BitcoinWallet._private_key_hex_from_int(order - 1)
    assert below_order is not None
    assert len(below_order) == PRIVATE_KEY_BYTES * 2
    assert BitcoinWallet.derive_public_key(below_order).startswith(("02", "03"))


@pytest.mark.parametrize(
    ("private_key", "public_key", "address"),
    [
        (WIKI_PRIVATE_KEY, WIKI_PUBLIC_KEY, WIKI_ADDRESS),
        (KEY_ONE, KEY_ONE_PUBLIC_KEY, KEY_ONE_ADDRESS),
        (KEY_SIX, KEY_SIX_PUBLIC_KEY, KEY_SIX_ADDRESS),
    ],
)
def test_published_key_to_address_vectors(private_key: str, public_key: str, address: str) -> None:
    """Compressed public keys and P2PKH addresses match the published vectors."""
    assert BitcoinWallet.derive_public_key(private_key) == public_key
    assert BitcoinWallet.generate_address(public_key) == address


@pytest.mark.parametrize(
    ("wif", "address"),
    [
        (CORE_WIF_ONE, CORE_ADDRESS_ONE),
        (CORE_WIF_TWO, CORE_ADDRESS_TWO),
    ],
)
def test_bitcoin_core_wif_vectors(wif: str, address: str) -> None:
    """Bitcoin Core compressed WIF vectors decode to the published addresses."""
    private_key = _hex_from_compressed_wif(wif)
    assert BitcoinWallet.generate_address(BitcoinWallet.derive_public_key(private_key)) == address


def test_uppercase_private_key_is_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    """A provided private key is stored in lowercase and keeps the wiki address."""
    wallet, _proxy = _make_wallet(monkeypatch, WIKI_PRIVATE_KEY.upper())
    assert wallet.private_key == WIKI_PRIVATE_KEY
    assert wallet.address == WIKI_ADDRESS


@pytest.mark.parametrize(
    "private_key",
    ["", "zz", "1", "0" * 64, "g" * 64, None],
)
def test_invalid_private_keys_are_rejected(private_key: object) -> None:
    """Rejected private keys raise ValueError and are not copied into the message."""
    with pytest.raises(ValueError, match="Private key") as caught:
        BitcoinWallet.derive_public_key(private_key)  # type: ignore[arg-type]  # non-string boundary input
    if isinstance(private_key, str) and len(private_key) > 2:
        assert private_key not in str(caught.value)


def test_curve_order_is_rejected_without_echoing_the_key() -> None:
    """The secp256k1 order itself is not a usable private key."""
    order_hex = f"{ecdsa.SECP256k1.order:064x}"
    with pytest.raises(ValueError, match="Private key") as caught:
        BitcoinWallet.derive_public_key(order_hex)
    assert order_hex not in str(caught.value)


@pytest.mark.parametrize("public_key", ["", "zz", "04" + "ab" * 64, "02" + "ab" * 31, None])
def test_invalid_public_keys_are_rejected(public_key: object) -> None:
    """Address generation accepts only a compressed public key hex string."""
    with pytest.raises(ValueError, match="Public key") as caught:
        BitcoinWallet.generate_address(public_key)  # type: ignore[arg-type]  # non-string boundary input
    if isinstance(public_key, str) and public_key != "":
        assert public_key not in str(caught.value)


@pytest.mark.parametrize(
    "address",
    ["", "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4", None],
)
def test_validate_address_rejects_empty_bech32_and_non_strings(address: object) -> None:
    """Empty, Bech32, and non-string recipients are rejected before any RPC call."""
    with pytest.raises(ValueError, match="mainnet P2PKH"):
        BitcoinWallet.validate_mainnet_p2pkh_address(address)  # type: ignore[arg-type]  # non-string boundary input


def test_validate_address_rejects_p2sh_and_bad_checksum() -> None:
    """P2SH and a broken checksum are not mainnet P2PKH addresses."""
    assert BitcoinWallet.validate_mainnet_p2pkh_address(WIKI_ADDRESS) == WIKI_ADDRESS
    with pytest.raises(ValueError, match="mainnet P2PKH"):
        BitcoinWallet.validate_mainnet_p2pkh_address(_p2sh_address())
    with pytest.raises(ValueError, match="mainnet P2PKH"):
        BitcoinWallet.validate_mainnet_p2pkh_address(_bad_checksum(WIKI_ADDRESS))


def test_created_credentials_are_owner_only(wallet_home: Path) -> None:
    """A missing credentials file is created with a random pair and owner-only access."""
    credentials = BitcoinWallet.get_rpc_credentials("rpc_credentials.json")
    username = credentials[RPC_USERNAME_KEY]
    password = credentials[RPC_PASSWORD_KEY]
    assert username.startswith("user_")
    assert len(username) == len("user_") + 8
    assert len(password) == 32
    _assert_owner_only(wallet_home / "rpc_credentials.json")


def test_existing_credentials_reload(wallet_home: Path) -> None:
    """An existing two-field credentials file is returned unchanged."""
    payload = {RPC_USERNAME_KEY: "user_test", RPC_PASSWORD_KEY: "secret-value"}
    (wallet_home / "rpc_credentials.json").write_text(json.dumps(payload), encoding="utf-8")
    assert BitcoinWallet.get_rpc_credentials("rpc_credentials.json") == payload
    _assert_owner_only(wallet_home / "rpc_credentials.json")


@pytest.mark.parametrize(
    "payload",
    [
        [1, 2],
        {RPC_USERNAME_KEY: "user_test", RPC_PASSWORD_KEY: "secret-value", "extra": "no"},
        {RPC_USERNAME_KEY: "", RPC_PASSWORD_KEY: "secret-value"},
        {RPC_USERNAME_KEY: "user_test", RPC_PASSWORD_KEY: 5},
        {RPC_USERNAME_KEY: "user_test"},
    ],
)
def test_credential_schema_is_exact(wallet_home: Path, payload: object) -> None:
    """Credentials must be exactly rpc_user and rpc_password as non-empty strings."""
    (wallet_home / "rpc_credentials.json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="rpc_user and rpc_password"):
        BitcoinWallet.get_rpc_credentials("rpc_credentials.json")


def test_invalid_credential_json_hides_file_contents(wallet_home: Path) -> None:
    """A broken JSON file raises ValueError without echoing the file contents."""
    (wallet_home / "rpc_credentials.json").write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="rpc_user and rpc_password") as caught:
        BitcoinWallet.get_rpc_credentials("rpc_credentials.json")
    assert "{" not in str(caught.value)


def test_non_utf8_credentials_are_rejected(wallet_home: Path) -> None:
    """Bytes that are not UTF-8 JSON are rejected."""
    (wallet_home / "rpc_credentials.json").write_bytes(b"\xff\xfe")
    with pytest.raises(ValueError, match="rpc_user and rpc_password") as caught:
        BitcoinWallet.get_rpc_credentials("rpc_credentials.json")
    assert "\\xff" not in str(caught.value)


def test_oversized_credentials_are_rejected(wallet_home: Path) -> None:
    """A credentials file above the size cap is rejected before it is parsed."""
    (wallet_home / "rpc_credentials.json").write_bytes(b"a" * (MAX_CREDENTIALS_BYTES + 1))
    with pytest.raises(ValueError, match="larger"):
        BitcoinWallet.get_rpc_credentials("rpc_credentials.json")


@pytest.mark.parametrize("file_path", ["", None])
def test_credential_path_must_be_a_non_empty_string(file_path: object) -> None:
    """An empty or non-string credentials path is rejected."""
    with pytest.raises(ValueError, match="wallet directory"):
        BitcoinWallet.get_rpc_credentials(file_path)  # type: ignore[arg-type]  # non-string boundary input


def test_parent_traversal_is_rejected() -> None:
    """A credentials path cannot climb out of the wallet directory."""
    with pytest.raises(ValueError, match="wallet directory"):
        BitcoinWallet.get_rpc_credentials("../outside.json")


def test_absolute_path_outside_wallet_is_rejected(wallet_home: Path) -> None:
    """An absolute path outside the wallet directory is rejected."""
    outside = wallet_home.parent / "outside-credentials.json"
    with pytest.raises(ValueError, match="wallet directory"):
        BitcoinWallet.get_rpc_credentials(str(outside))
    assert not outside.exists()


def test_absolute_path_inside_wallet_is_allowed(wallet_home: Path) -> None:
    """An absolute path inside the wallet directory can be loaded."""
    payload = {RPC_USERNAME_KEY: "user_test", RPC_PASSWORD_KEY: "secret-value"}
    target = wallet_home / "inside.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    assert BitcoinWallet.get_rpc_credentials(str(target)) == payload


def _point_at_directory(link: Path, outside: Path) -> None:
    """Make link refer to outside, using a directory junction when symlinks are denied."""
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        command = str(BitcoinWallet._windows_icacls_path().with_name("cmd.exe"))
        # Test-only junction. shell is false and both paths were created by this test.
        completed = subprocess.run(  # noqa: S603
            [command, "/c", "mklink", "/J", str(link), str(outside)],
            check=False,
            capture_output=True,
            text=True,
            shell=False,
        )
        if completed.returncode != 0:
            pytest.skip("This platform refused to create a symlink or junction")


def test_reparse_point_outside_wallet_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A symlink or junction that resolves outside the wallet directory is rejected."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(bitcoin_wallet, "WALLET_DIRECTORY", home)
    outside = tmp_path / "outside"
    outside.mkdir()
    payload = {RPC_USERNAME_KEY: "user_test", RPC_PASSWORD_KEY: "secret-value"}
    (outside / "creds.json").write_text(json.dumps(payload), encoding="utf-8")
    _point_at_directory(home / "link", outside)
    with pytest.raises(ValueError, match="wallet directory"):
        BitcoinWallet.get_rpc_credentials("link/creds.json")


def test_posix_permissions_use_owner_mode(monkeypatch: pytest.MonkeyPatch, wallet_home: Path) -> None:
    """The POSIX branch creates the file with the owner-only mode."""
    modes: list[int] = []

    def record_chmod(self: Path, mode: int) -> None:
        """Remember the mode requested for the credentials file."""
        modes.append(mode)

    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.setattr(Path, "chmod", record_chmod)
    BitcoinWallet.get_rpc_credentials("posix.json")
    assert modes == [CREDENTIALS_FILE_MODE]
    assert (wallet_home / "posix.json").exists()


def test_windows_acl_uses_icacls(monkeypatch: pytest.MonkeyPatch, wallet_home: Path) -> None:
    """The Windows branch grants read and write to the current user only."""
    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.setenv("USERNAME", "tester")
    monkeypatch.setenv("SystemRoot", r"D:\Windows")
    seen: list[list[str]] = []

    def fake_run(
        args: list[str],
        check: bool = False,
        capture_output: bool = True,
        text: bool = True,
        shell: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        """Record the icacls invocation and report success."""
        del check, capture_output, text
        assert shell is False
        seen.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    BitcoinWallet.get_rpc_credentials("win.json")
    assert seen[0][0] == "D:\\Windows\\System32\\icacls.exe"
    assert seen[0][2:] == ["/inheritance:r", "/grant:r", "tester:(R,W)"]


def test_windows_icacls_defaults_system_root(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without SystemRoot, icacls is resolved under C:\\Windows."""
    monkeypatch.delenv("SystemRoot", raising=False)
    assert str(BitcoinWallet._windows_icacls_path()) == "C:\\Windows\\System32\\icacls.exe"


def test_windows_icacls_rejects_unexpected_system_root(monkeypatch: pytest.MonkeyPatch) -> None:
    """SystemRoot cannot point icacls at an arbitrary directory."""
    monkeypatch.setenv("SystemRoot", r"C:\NotWindows")
    with pytest.raises(OSError, match="Windows directory"):
        BitcoinWallet._windows_icacls_path()


def test_windows_acl_rejects_unsafe_username(monkeypatch: pytest.MonkeyPatch, wallet_home: Path) -> None:
    """An account name that can change the icacls grant is rejected."""
    monkeypatch.setenv("USERNAME", "tester:(F)")
    path = wallet_home / "creds.json"
    path.write_text("{}", encoding="utf-8")

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        """Fail the test if icacls is started for a rejected account name."""
        del args, kwargs
        raise AssertionError("icacls should not run")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(OSError, match="current user"):
        BitcoinWallet._restrict_windows_acl(path)


def test_windows_acl_requires_username(monkeypatch: pytest.MonkeyPatch, wallet_home: Path) -> None:
    """A missing USERNAME stops the Windows ACL change."""
    monkeypatch.delenv("USERNAME", raising=False)
    path = wallet_home / "creds.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(OSError, match="current user"):
        BitcoinWallet._restrict_windows_acl(path)


def test_windows_acl_failure_hides_tool_output(monkeypatch: pytest.MonkeyPatch, wallet_home: Path) -> None:
    """A failing icacls command raises a generic error."""
    monkeypatch.setenv("USERNAME", "tester")

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        """Report a failed icacls command with text the wallet must not surface."""
        del args, kwargs
        return subprocess.CompletedProcess([], 1, "", "secret-tool-output")

    monkeypatch.setattr(subprocess, "run", fake_run)
    path = wallet_home / "creds.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(OSError, match="could not be restricted") as caught:
        BitcoinWallet._restrict_windows_acl(path)
    assert "secret-tool-output" not in str(caught.value)


def test_rpc_url_encodes_credentials(monkeypatch: pytest.MonkeyPatch, wallet_home: Path) -> None:
    """User and password are percent-encoded and the host and port stay fixed."""
    username = "user_name"
    user_credential = "p@ss:word/\r\n"
    payload = {RPC_USERNAME_KEY: username, RPC_PASSWORD_KEY: user_credential}
    (wallet_home / "rpc_credentials.json").write_text(json.dumps(payload), encoding="utf-8")
    _wallet, proxy = _make_wallet(monkeypatch, KEY_ONE)
    parts = urlsplit(proxy.service_url)
    userinfo, separator, host = proxy.service_url.removeprefix(f"{RPC_SCHEME}://").rpartition("@")
    assert separator == "@"
    assert host == f"{RPC_HOST}:{RPC_PORT}"
    assert "@" not in userinfo
    assert "%40" in userinfo
    assert "%3A" in userinfo
    assert "%2F" in userinfo
    assert "%0D" in userinfo
    assert "%0A" in userinfo
    assert parts.hostname == RPC_HOST
    assert parts.port == RPC_PORT
    assert unquote(parts.username or "") == username
    assert unquote(parts.password or "") == user_credential
    assert proxy.timeout == RPC_TIMEOUT_SECONDS


def test_generated_wallet_address_matches_derivation(monkeypatch: pytest.MonkeyPatch) -> None:
    """A wallet with no supplied key derives its address from the key it generated."""
    wallet, _proxy = _make_wallet(monkeypatch, None)
    assert wallet.public_key == BitcoinWallet.derive_public_key(wallet.private_key)
    assert wallet.address == BitcoinWallet.generate_address(wallet.public_key)


def test_balance_sums_validated_amounts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Decimal, integer, and string UTXO amounts add up, and listunspent gets the confirmations window."""
    wallet, proxy = _make_wallet(monkeypatch)
    proxy.listunspent.return_value = [
        _utxo(Decimal("0.1")),
        _utxo("0.2", vout=1, txid="cd" * 32),
        _utxo(2, vout=2, txid="ef" * 32),
    ]
    assert wallet.get_balance() == Decimal("2.3")
    proxy.listunspent.assert_called_once_with(MIN_CONFIRMATIONS, MAX_CONFIRMATIONS, [wallet.address])


def test_empty_balance_is_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """No UTXOs produce a Decimal zero balance."""
    wallet, _proxy = _make_wallet(monkeypatch)
    assert wallet.get_balance() == Decimal(0)


@pytest.mark.parametrize(
    "entry",
    [
        None,
        {"txid": "zz", "vout": 0, "amount": Decimal("1")},
        {"txid": "ab" * 32, "vout": True, "amount": Decimal("1")},
        {"txid": "ab" * 32, "vout": -1, "amount": Decimal("1")},
        {"txid": "ab" * 32, "vout": 1.5, "amount": Decimal("1")},
        {"txid": "ab" * 32, "vout": 0, "amount": 1.5},
        {"txid": "ab" * 32, "vout": 0, "amount": True},
        {"txid": "ab" * 32, "vout": 0, "amount": "nope"},
        {"txid": "ab" * 32, "vout": 0, "amount": "NaN"},
        {"txid": "ab" * 32, "vout": 0, "amount": "Infinity"},
        {"txid": "ab" * 32, "vout": 0, "amount": "0"},
        {"txid": "ab" * 32, "vout": 0, "amount": "-1"},
        {"txid": "ab" * 32, "vout": 0, "amount": "0.000000001"},
        {"txid": "ab" * 32, "vout": 0, "amount": None},
    ],
)
def test_malformed_utxo_is_rejected(monkeypatch: pytest.MonkeyPatch, entry: object) -> None:
    """A UTXO with a bad txid, vout, or amount is rejected."""
    wallet, proxy = _make_wallet(monkeypatch)
    proxy.listunspent.return_value = [entry]
    with pytest.raises(BitcoinCoreResponseError, match="UTXO this wallet"):
        wallet.get_balance()


def test_non_list_utxos_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """listunspent must return a list."""
    wallet, proxy = _make_wallet(monkeypatch)
    proxy.listunspent.return_value = {"txid": "ab" * 32}
    with pytest.raises(BitcoinCoreResponseError, match="UTXO list"):
        wallet.get_balance()


def test_too_many_utxos_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """The UTXO list is capped before any entry is used."""
    wallet, proxy = _make_wallet(monkeypatch)
    proxy.listunspent.return_value = [_utxo(Decimal("1"))] * (MAX_UTXO_COUNT + 1)
    with pytest.raises(BitcoinCoreResponseError, match="UTXO list"):
        wallet.get_balance()


@pytest.mark.parametrize(
    "error",
    [
        JSONRPCException({"code": 1, "message": "rpc down"}),
        OSError("disk"),
        TimeoutError("slow"),
        ValueError("bad"),
        http.client.HTTPException("http"),
    ],
)
def test_rpc_failures_are_wrapped(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    """RPC, OS, timeout, value, and HTTP failures become BitcoinCoreResponseError."""
    wallet, proxy = _make_wallet(monkeypatch)
    proxy.listunspent.side_effect = error
    with pytest.raises(BitcoinCoreResponseError, match="RPC call failed") as caught:
        wallet.get_balance()
    assert caught.value.__cause__ is None


def test_rpc_error_redacts_secrets(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    """An RPC error loses the password, username, private key, encodings, and newlines."""
    wallet, proxy = _make_wallet(monkeypatch)
    password = wallet.rpc_credentials[RPC_PASSWORD_KEY]
    username = wallet.rpc_credentials[RPC_USERNAME_KEY]
    message = f"bad\r\n{password}\r\n{username}\r\n{wallet.private_key}\r\n{quote(password, safe='')}"
    proxy.listunspent.side_effect = JSONRPCException({"code": 1, "message": message})
    with caplog.at_level(logging.ERROR):
        with pytest.raises(BitcoinCoreResponseError, match="RPC call failed") as caught:
            wallet.get_balance()
    text = str(caught.value)
    for secret in (password, username, wallet.private_key, quote(password, safe="")):
        assert secret not in text
        assert secret not in caplog.text
    assert "\n" not in text
    assert "\r" not in text
    assert _REDACTED in text
    assert caplog.records[0].detail  # type: ignore[attr-defined]  # logging extra field
    assert password not in caplog.records[0].detail  # type: ignore[attr-defined]  # logging extra field


def test_redact_skips_empty_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty credential is not treated as a secret to replace."""
    wallet, _proxy = _make_wallet(monkeypatch)
    wallet.rpc_credentials[RPC_PASSWORD_KEY] = ""
    assert "" not in wallet._secret_values()
    assert wallet._redact("hello") == "hello"


def test_send_with_change_uses_fewest_coins(monkeypatch: pytest.MonkeyPatch) -> None:
    """Coin selection prefers one coin over an earlier pair and returns the txid."""
    wallet, proxy = _make_wallet(monkeypatch)
    proxy.listunspent.return_value = [
        _utxo(Decimal("0.1")),
        _utxo(Decimal("0.2"), vout=1, txid="cd" * 32),
        _utxo(Decimal("5"), vout=2, txid="ef" * 32),
    ]
    amount = Decimal("0.25")
    txid = wallet.create_and_send_transaction(WIKI_ADDRESS, amount)
    assert txid == "ab" * 32
    inputs, outputs = proxy.createrawtransaction.call_args.args
    assert inputs == [{"txid": "ef" * 32, "vout": 2}]
    total = Decimal("5")
    assert outputs[WIKI_ADDRESS] == amount.quantize(SATOSHI)
    assert outputs[wallet.address] == (total - amount - DEFAULT_TX_FEE_BTC).quantize(SATOSHI)
    assert proxy.signrawtransactionwithkey.call_args.args[0] == "aa"
    assert proxy.signrawtransactionwithkey.call_args.args[1] == [wallet.private_key]
    assert proxy.sendrawtransaction.call_args.args[0] == "bb"


def test_send_exact_amount_has_no_change_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """An input that matches the amount plus fee has no change output."""
    wallet, proxy = _make_wallet(monkeypatch)
    amount = Decimal("0.25")
    proxy.listunspent.return_value = [_utxo(amount + DEFAULT_TX_FEE_BTC)]
    wallet.create_and_send_transaction(WIKI_ADDRESS, amount)
    _inputs, outputs = proxy.createrawtransaction.call_args.args
    assert set(outputs) == {WIKI_ADDRESS}
    assert outputs[WIKI_ADDRESS] == amount


def test_send_to_self_merges_the_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """Paying this wallet's own address keeps a single combined output."""
    wallet, proxy = _make_wallet(monkeypatch)
    proxy.listunspent.return_value = [_utxo(Decimal("1"))]
    wallet.create_and_send_transaction(wallet.address, Decimal("0.2"))
    _inputs, outputs = proxy.createrawtransaction.call_args.args
    assert set(outputs) == {wallet.address}
    assert outputs[wallet.address] == Decimal("1") - DEFAULT_TX_FEE_BTC


def test_insufficient_funds(monkeypatch: pytest.MonkeyPatch) -> None:
    """The fee is included when deciding that the balance is too small."""
    wallet, proxy = _make_wallet(monkeypatch)
    proxy.listunspent.return_value = [_utxo(Decimal("0.2"))]
    with pytest.raises(ValueError, match="Insufficient funds"):
        wallet.create_and_send_transaction(WIKI_ADDRESS, Decimal("0.2"))
    proxy.signrawtransactionwithkey.assert_not_called()


@pytest.mark.parametrize(
    "amount",
    [
        Decimal("0"),
        Decimal("-0.1"),
        0.1,
        1,
        True,
        Decimal("0.000000001"),
        Decimal("NaN"),
        Decimal("Infinity"),
    ],
)
def test_invalid_send_amounts_never_call_rpc(monkeypatch: pytest.MonkeyPatch, amount: object) -> None:
    """Amounts must be positive satoshi-aligned Decimal values."""
    wallet, proxy = _make_wallet(monkeypatch)
    with pytest.raises(ValueError, match="Amount"):
        wallet.create_and_send_transaction(WIKI_ADDRESS, amount)  # type: ignore[arg-type]  # non-Decimal boundary input
    proxy.listunspent.assert_not_called()


def test_invalid_recipient_never_calls_rpc(monkeypatch: pytest.MonkeyPatch) -> None:
    """An invalid recipient is rejected before listunspent or signing."""
    wallet, proxy = _make_wallet(monkeypatch)
    with pytest.raises(ValueError, match="mainnet P2PKH"):
        wallet.create_and_send_transaction(_p2sh_address(), Decimal("0.1"))
    proxy.listunspent.assert_not_called()
    proxy.signrawtransactionwithkey.assert_not_called()


def test_create_raw_failure_does_not_sign(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed createrawtransaction does not call the signer."""
    wallet, proxy = _make_wallet(monkeypatch)
    proxy.listunspent.return_value = [_utxo(Decimal("1"))]
    proxy.createrawtransaction.side_effect = JSONRPCException({"code": -1, "message": "no raw"})
    with pytest.raises(BitcoinCoreResponseError, match="RPC call failed"):
        wallet.create_and_send_transaction(WIKI_ADDRESS, Decimal("0.2"))
    proxy.signrawtransactionwithkey.assert_not_called()


@pytest.mark.parametrize("raw_tx", [None, ""])
def test_create_raw_requires_hex(monkeypatch: pytest.MonkeyPatch, raw_tx: object) -> None:
    """An empty or non-string raw transaction is rejected."""
    wallet, proxy = _make_wallet(monkeypatch)
    proxy.createrawtransaction.return_value = raw_tx
    with pytest.raises(BitcoinCoreResponseError, match="raw transaction"):
        wallet.create_raw_transaction([], {})


def test_sign_failure_hides_private_key(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    """A signing failure is logged and raised without the private key or the RPC arguments."""
    wallet, proxy = _make_wallet(monkeypatch)
    proxy.signrawtransactionwithkey.side_effect = JSONRPCException({"code": 1, "message": wallet.private_key})
    with caplog.at_level(logging.ERROR):
        with pytest.raises(BitcoinCoreResponseError, match="could not sign") as caught:
            wallet.sign_transaction("abcd")
    assert wallet.private_key not in str(caught.value)
    assert wallet.private_key not in caplog.text
    assert caught.value.__cause__ is None
    assert not hasattr(caplog.records[0], "detail")


@pytest.mark.parametrize(
    "signed",
    [
        {"complete": False, "hex": "ff"},
        ["ff"],
        {"complete": True, "hex": ""},
        {"complete": True},
    ],
)
def test_incomplete_signature_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    signed: object,
) -> None:
    """Signing must return a completed non-empty hex transaction."""
    wallet, proxy = _make_wallet(monkeypatch)
    proxy.signrawtransactionwithkey.return_value = signed
    with caplog.at_level(logging.ERROR):
        with pytest.raises(BitcoinCoreResponseError):
            wallet.sign_transaction("abcd")
    proxy.sendrawtransaction.assert_not_called()
    assert wallet.private_key not in caplog.text


def test_empty_raw_transaction_is_not_signed(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty raw transaction never reaches the signer."""
    wallet, proxy = _make_wallet(monkeypatch)
    with pytest.raises(ValueError, match="Raw transaction"):
        wallet.sign_transaction("")
    proxy.signrawtransactionwithkey.assert_not_called()


def test_broadcast_requires_a_txid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Broadcast returns a 64-character hex id and rejects anything else."""
    wallet, proxy = _make_wallet(monkeypatch)
    proxy.sendrawtransaction.return_value = "AB" * 32
    assert wallet.broadcast_transaction("bb") == "ab" * 32
    proxy.sendrawtransaction.return_value = "zzzz"
    with pytest.raises(BitcoinCoreResponseError, match="transaction id"):
        wallet.broadcast_transaction("bb")
    with pytest.raises(ValueError, match="Signed transaction"):
        wallet.broadcast_transaction("")


def test_estimate_fee_rate_reads_the_node(monkeypatch: pytest.MonkeyPatch) -> None:
    """The default confirmation target is six blocks, and the rate comes back unchanged."""
    wallet, proxy = _make_wallet(monkeypatch)
    proxy.estimatesmartfee.return_value = {"feerate": Decimal("0.00001000")}
    assert wallet.estimate_fee_rate() == Decimal("0.00001000")
    proxy.estimatesmartfee.assert_called_once_with(6)


@pytest.mark.parametrize("target", [True, 0, 1009, "6"])
def test_estimate_fee_rate_rejects_a_bad_target(monkeypatch: pytest.MonkeyPatch, target: object) -> None:
    """A confirmation target outside 1 to 1008 never calls the node."""
    wallet, proxy = _make_wallet(monkeypatch)
    with pytest.raises(ValueError, match="Confirmation target"):
        wallet.estimate_fee_rate(target)  # type: ignore[arg-type]  # non-int boundary input
    proxy.estimatesmartfee.assert_not_called()


def test_estimate_fee_rate_rejects_a_node_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """An estimatesmartfee error payload stays a fee error instead of an RPC failure."""
    wallet, proxy = _make_wallet(monkeypatch)
    proxy.estimatesmartfee.return_value = {"errors": ["Insufficient data or no feerate found"]}
    with pytest.raises(ValueError, match="Fee estimate"):
        wallet.estimate_fee_rate(2)
