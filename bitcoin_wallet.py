"""Bitcoin wallet keys, mainnet P2PKH addresses, and Bitcoin Core RPC."""

from __future__ import annotations

import hashlib
import http.client
import json
import logging
import os
import re
import secrets
import subprocess
from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TypeVar
from urllib.parse import quote, urlunsplit

import base58
import ecdsa
from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException

from btc_wallet.coin_selector import CoinSelector
from btc_wallet.fee_estimate import FeeEstimate
from constants import (
    CHECKSUM_BYTES,
    COMPRESSED_PUBLIC_KEY_BYTES,
    COMPRESSED_PUBLIC_KEY_EVEN_PREFIX,
    COMPRESSED_PUBLIC_KEY_ODD_PREFIX,
    CREDENTIAL_PASSWORD_RANDOM_BYTES,
    CREDENTIAL_USERNAME_PREFIX,
    CREDENTIAL_USERNAME_RANDOM_BYTES,
    CREDENTIALS_FILE_MODE,
    DEFAULT_FEE_CONFIRMATION_TARGET,
    DEFAULT_TX_FEE_BTC,
    HASH160_BYTES,
    MAINNET_P2PKH_VERSION,
    MAX_CONFIRMATIONS,
    MAX_CREDENTIALS_BYTES,
    MAX_FEE_CONFIRMATION_TARGET,
    MAX_UTXO_COUNT,
    MIN_CONFIRMATIONS,
    MIN_FEE_CONFIRMATION_TARGET,
    PRIVATE_KEY_BYTES,
    RPC_HOST,
    RPC_METHOD_CREATE_RAW_TRANSACTION,
    RPC_METHOD_ESTIMATE_SMART_FEE,
    RPC_METHOD_LIST_UNSPENT,
    RPC_METHOD_SEND_RAW_TRANSACTION,
    RPC_METHOD_SIGN_RAW_TRANSACTION,
    RPC_PASSWORD_KEY,
    RPC_PORT,
    RPC_SCHEME,
    RPC_TIMEOUT_SECONDS,
    RPC_USERNAME_KEY,
    SATOSHI,
    TXID_HEX_LENGTH,
    VERSION_BYTES,
)

# The BitcoinRPC logger records RPC arguments, including the private key passed to signrawtransactionwithkey.
logging.getLogger("BitcoinRPC").disabled = True

logger = logging.getLogger(__name__)

T = TypeVar("T")

WALLET_DIRECTORY = Path(__file__).resolve().parent

_PRIVATE_KEY_RE = re.compile(rf"[0-9a-fA-F]{{{PRIVATE_KEY_BYTES * 2}}}")
_COMPRESSED_PUBLIC_KEY_RE = re.compile(rf"0[23][0-9a-fA-F]{{{(COMPRESSED_PUBLIC_KEY_BYTES - 1) * 2}}}")
_TXID_RE = re.compile(rf"[0-9a-fA-F]{{{TXID_HEX_LENGTH}}}")
_WINDOWS_ROOT_RE = re.compile(r"^[A-Za-z]:\\Windows$", re.IGNORECASE)
_WINDOWS_ACCOUNT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._-]{0,63}$")

_PRIVATE_KEY_ERROR = "Private key must be 32 bytes of hex inside the secp256k1 order."
_PUBLIC_KEY_ERROR = "Public key must be a compressed secp256k1 point."
_ADDRESS_ERROR = "Recipient address must be a mainnet P2PKH address."
_AMOUNT_ERROR = "Amount must be a positive satoshi-aligned Decimal."
_CREDENTIALS_ERROR = "Credentials file must be a JSON object with rpc_user and rpc_password."
_CREDENTIALS_PATH_ERROR = "Credentials path must stay inside the wallet directory."
_UTXO_ERROR = "Bitcoin Core returned a UTXO this wallet will not use."
_UTXO_LIST_ERROR = "Bitcoin Core returned a UTXO list this wallet will not use."
_REDACTED = "[redacted]"


class BitcoinCoreResponseError(Exception):
    """Raised when Bitcoin Core returns a response this wallet will not use."""


class BitcoinWallet:
    """A single-key wallet that asks Bitcoin Core to build, sign, and broadcast transactions."""

    rpc_credentials: dict[str, str]
    rpc_connection: AuthServiceProxy
    private_key: str
    public_key: str
    address: str

    def __init__(self, rpc_credentials_file: str = "rpc_credentials.json", private_key: str | None = None) -> None:
        """Store credentials from rpc_credentials_file and derive an address from private_key."""
        self.rpc_credentials = self.get_rpc_credentials(rpc_credentials_file)
        self.rpc_connection = self.connect_to_rpc()
        if private_key is None:
            self.private_key = self.generate_private_key()
        else:
            self.private_key = self._require_private_key_hex(private_key)
        self.public_key = self.derive_public_key(self.private_key)
        self.address = self.generate_address(self.public_key)

    @staticmethod
    def get_rpc_credentials(file_path: str = "rpc_credentials.json") -> dict[str, str]:
        """Return rpc_user and rpc_password loaded or created at file_path inside the wallet directory."""
        path = BitcoinWallet._credentials_path(file_path)
        if path.exists():
            credentials = BitcoinWallet._load_credentials(path)
        else:
            credentials = {
                RPC_USERNAME_KEY: CREDENTIAL_USERNAME_PREFIX + secrets.token_hex(CREDENTIAL_USERNAME_RANDOM_BYTES),
                RPC_PASSWORD_KEY: secrets.token_hex(CREDENTIAL_PASSWORD_RANDOM_BYTES),
            }
            BitcoinWallet._write_credentials(path, credentials)
        BitcoinWallet._restrict_to_owner(path)
        return credentials

    def connect_to_rpc(self) -> AuthServiceProxy:
        """Return an RPC client for the fixed local Bitcoin Core endpoint."""
        user = quote(self.rpc_credentials[RPC_USERNAME_KEY], safe="")
        password = quote(self.rpc_credentials[RPC_PASSWORD_KEY], safe="")
        netloc = f"{user}:{password}@{RPC_HOST}:{RPC_PORT}"
        url = urlunsplit((RPC_SCHEME, netloc, "", "", ""))
        return AuthServiceProxy(url, timeout=RPC_TIMEOUT_SECONDS)

    @staticmethod
    def generate_private_key() -> str:
        """Return a new hex private key drawn from secrets.token_bytes and os.urandom."""
        while True:
            entropy = secrets.token_bytes(PRIVATE_KEY_BYTES) + os.urandom(PRIVATE_KEY_BYTES)
            candidate = BitcoinWallet._candidate_private_key(entropy)
            if candidate is not None:
                return candidate
            continue  # pragma: no cover - out-of-range decision is tested on _private_key_hex_from_int.

    @staticmethod
    def derive_public_key(private_key_hex: str) -> str:
        """Return the compressed secp256k1 public key hex for private_key_hex."""
        normalized = BitcoinWallet._require_private_key_hex(private_key_hex)
        signing_key = ecdsa.SigningKey.from_string(bytes.fromhex(normalized), curve=ecdsa.SECP256k1)
        point = signing_key.get_verifying_key().pubkey.point
        prefix = COMPRESSED_PUBLIC_KEY_EVEN_PREFIX if point.y() % 2 == 0 else COMPRESSED_PUBLIC_KEY_ODD_PREFIX
        return (prefix + point.x().to_bytes(PRIVATE_KEY_BYTES, "big")).hex()

    @staticmethod
    def generate_address(public_key_hex: str) -> str:
        """Return the mainnet P2PKH address for compressed public_key_hex."""
        if not isinstance(public_key_hex, str) or _COMPRESSED_PUBLIC_KEY_RE.fullmatch(public_key_hex) is None:
            raise ValueError(_PUBLIC_KEY_ERROR)
        payload = MAINNET_P2PKH_VERSION + BitcoinWallet._hash160(bytes.fromhex(public_key_hex))
        checksum = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:CHECKSUM_BYTES]
        return base58.b58encode(payload + checksum).decode()

    @staticmethod
    def validate_mainnet_p2pkh_address(address: str) -> str:
        """Return address when it is a mainnet P2PKH Base58Check address."""
        if not isinstance(address, str) or address == "":
            raise ValueError(_ADDRESS_ERROR)
        try:
            decoded = base58.b58decode_check(address)
        except ValueError:
            raise ValueError(_ADDRESS_ERROR) from None
        if len(decoded) != VERSION_BYTES + HASH160_BYTES or decoded[:VERSION_BYTES] != MAINNET_P2PKH_VERSION:
            raise ValueError(_ADDRESS_ERROR)
        return address

    def get_balance(self) -> Decimal:
        """Return the spendable balance in BTC for this wallet address."""
        return sum((amount for _, _, amount in self._validated_utxos()), start=Decimal(0))

    def create_raw_transaction(self, inputs: list[dict[str, str | int]], outputs: dict[str, Decimal]) -> str:
        """Return the hex raw transaction Bitcoin Core built for inputs and outputs."""
        raw_tx = self._call_rpc(
            RPC_METHOD_CREATE_RAW_TRANSACTION,
            lambda: self.rpc_connection.createrawtransaction(inputs, outputs),
        )
        if not isinstance(raw_tx, str) or raw_tx == "":
            raise BitcoinCoreResponseError("Bitcoin Core did not return a raw transaction.")
        return raw_tx

    def sign_transaction(self, raw_tx: str) -> str:
        """Return the signed transaction hex for raw_tx."""
        if not isinstance(raw_tx, str) or raw_tx == "":
            raise ValueError("Raw transaction must be non-empty hex.")
        signed = self._call_rpc(
            RPC_METHOD_SIGN_RAW_TRANSACTION,
            lambda: self.rpc_connection.signrawtransactionwithkey(raw_tx, [self.private_key]),
        )
        if not isinstance(signed, dict) or signed.get("complete") is not True:
            logger.error(
                "Bitcoin Core did not complete the signature", extra={"rpc_method": RPC_METHOD_SIGN_RAW_TRANSACTION}
            )
            raise BitcoinCoreResponseError("Bitcoin Core did not complete the signature.")
        signed_hex = signed.get("hex")
        if not isinstance(signed_hex, str) or signed_hex == "":
            raise BitcoinCoreResponseError("Bitcoin Core did not return a signed transaction.")
        return signed_hex

    def broadcast_transaction(self, signed_tx: str) -> str:
        """Return the transaction id Bitcoin Core assigned to signed_tx."""
        if not isinstance(signed_tx, str) or signed_tx == "":
            raise ValueError("Signed transaction must be non-empty hex.")
        txid = self._call_rpc(
            RPC_METHOD_SEND_RAW_TRANSACTION,
            lambda: self.rpc_connection.sendrawtransaction(signed_tx),
        )
        if not isinstance(txid, str) or _TXID_RE.fullmatch(txid) is None:
            raise BitcoinCoreResponseError("Bitcoin Core did not return a transaction id.")
        return txid.lower()

    def create_and_send_transaction(self, recipient_address: str, amount: Decimal) -> str:
        """Return the txid of a coin-selected payment of amount BTC to recipient_address."""
        recipient = self.validate_mainnet_p2pkh_address(recipient_address)
        send_amount = BitcoinWallet._require_send_amount(amount)
        needed = send_amount + DEFAULT_TX_FEE_BTC
        selected = CoinSelector().select(self._validated_utxos(), needed)
        total = sum((utxo_amount for _txid, _vout, utxo_amount in selected), start=Decimal(0))
        change = (total - needed).quantize(SATOSHI)
        if recipient == self.address:
            outputs = {recipient: (total - DEFAULT_TX_FEE_BTC).quantize(SATOSHI)}
        else:
            outputs = {recipient: send_amount.quantize(SATOSHI)}
            if change > 0:
                outputs[self.address] = change
        inputs = [{"txid": txid, "vout": vout} for txid, vout, _amount in selected]
        raw_tx = self.create_raw_transaction(inputs, outputs)
        return self.broadcast_transaction(self.sign_transaction(raw_tx))

    def estimate_fee_rate(self, confirmation_target: int = DEFAULT_FEE_CONFIRMATION_TARGET) -> Decimal:
        """Return the estimatesmartfee rate in BTC per kilobyte for confirmation_target blocks."""
        if type(confirmation_target) is not int or not (
            MIN_FEE_CONFIRMATION_TARGET <= confirmation_target <= MAX_FEE_CONFIRMATION_TARGET
        ):
            raise ValueError("Confirmation target must be a whole number of blocks in range.")
        payload = self._call_rpc(
            RPC_METHOD_ESTIMATE_SMART_FEE,
            lambda: self.rpc_connection.estimatesmartfee(confirmation_target),
        )
        return FeeEstimate().parse(payload)

    def _validated_utxos(self) -> list[tuple[str, int, Decimal]]:
        """Return txid, vout, and amount tuples from listunspent."""
        raw_utxos = self._call_rpc(
            RPC_METHOD_LIST_UNSPENT,
            lambda: self.rpc_connection.listunspent(MIN_CONFIRMATIONS, MAX_CONFIRMATIONS, [self.address]),
        )
        if not isinstance(raw_utxos, list) or len(raw_utxos) > MAX_UTXO_COUNT:
            raise BitcoinCoreResponseError(_UTXO_LIST_ERROR)
        return [BitcoinWallet._parse_utxo(entry) for entry in raw_utxos]

    def _call_rpc(self, method_name: str, call: Callable[[], T]) -> T:
        """Return the result of call, or raise BitcoinCoreResponseError with secrets removed."""
        try:
            return call()
        except (JSONRPCException, OSError, TimeoutError, ValueError, http.client.HTTPException) as exc:
            if method_name == RPC_METHOD_SIGN_RAW_TRANSACTION:
                logger.error("Bitcoin Core RPC call failed", extra={"rpc_method": method_name})
                raise BitcoinCoreResponseError("Bitcoin Core could not sign the transaction.") from None
            detail = self._redact(str(exc))
            logger.error("Bitcoin Core RPC call failed", extra={"rpc_method": method_name, "detail": detail})
            raise BitcoinCoreResponseError(f"Bitcoin Core RPC call failed: {detail}") from None

    def _secret_values(self) -> set[str]:
        """Return the private key, RPC username, RPC password, and their percent-encoded forms."""
        values: set[str] = set()
        for secret in (
            self.private_key,
            self.rpc_credentials[RPC_USERNAME_KEY],
            self.rpc_credentials[RPC_PASSWORD_KEY],
        ):
            if secret == "":
                continue
            values.add(secret)
            values.add(quote(secret, safe=""))
        return values

    def _redact(self, text: str) -> str:
        """Return text with secrets removed and CR/LF stripped."""
        redacted = text
        for secret in sorted(self._secret_values(), key=len, reverse=True):
            redacted = redacted.replace(secret, _REDACTED)
        return redacted.replace("\r", "").replace("\n", "")

    @staticmethod
    def _candidate_private_key(entropy: bytes) -> str | None:
        """Return a hex private key hashed from entropy, or None when the hash is outside the curve."""
        digest = hashlib.sha256(entropy).digest()
        return BitcoinWallet._private_key_hex_from_int(int.from_bytes(digest, "big"))

    @staticmethod
    def _private_key_hex_from_int(key_int: int) -> str | None:
        """Return key_int as 64 hex characters when it lies inside the curve order, otherwise None."""
        if key_int <= 0 or key_int >= ecdsa.SECP256k1.order:
            return None
        return f"{key_int:0{PRIVATE_KEY_BYTES * 2}x}"

    @staticmethod
    def _require_private_key_hex(private_key_hex: str) -> str:
        """Return private_key_hex in lowercase when it is a 32-byte key inside the curve order."""
        if not isinstance(private_key_hex, str) or _PRIVATE_KEY_RE.fullmatch(private_key_hex) is None:
            raise ValueError(_PRIVATE_KEY_ERROR)
        normalized = BitcoinWallet._private_key_hex_from_int(int(private_key_hex, 16))
        if normalized is None:
            raise ValueError(_PRIVATE_KEY_ERROR)
        return normalized

    @staticmethod
    def _hash160(payload: bytes) -> bytes:
        """Return the HASH160 digest of payload."""
        sha = hashlib.sha256(payload).digest()
        # RIPEMD-160 is required by the Bitcoin address format; it is not used as a password hash.
        return hashlib.new("ripemd160", sha, usedforsecurity=False).digest()

    @staticmethod
    def _require_send_amount(amount: Decimal) -> Decimal:
        """Return amount when it is a positive finite Decimal aligned to one satoshi."""
        if type(amount) is not Decimal or not amount.is_finite() or amount <= 0 or amount != amount.quantize(SATOSHI):
            raise ValueError(_AMOUNT_ERROR)
        return amount

    @staticmethod
    def _parse_utxo(entry: object) -> tuple[str, int, Decimal]:
        """Return txid, vout, and amount from one listunspent entry."""
        if not isinstance(entry, dict):
            raise BitcoinCoreResponseError(_UTXO_ERROR)
        txid = entry.get("txid")
        vout = entry.get("vout")
        if not isinstance(txid, str) or _TXID_RE.fullmatch(txid) is None or type(vout) is not int or vout < 0:
            raise BitcoinCoreResponseError(_UTXO_ERROR)
        return txid.lower(), vout, BitcoinWallet._parse_amount(entry.get("amount"))

    @staticmethod
    def _parse_amount(amount: object) -> Decimal:
        """Return amount as a positive satoshi-aligned Decimal."""
        if isinstance(amount, bool) or isinstance(amount, float):
            raise BitcoinCoreResponseError(_UTXO_ERROR)
        if isinstance(amount, Decimal):
            parsed = amount
        elif isinstance(amount, int):
            parsed = Decimal(amount)
        elif isinstance(amount, str):
            try:
                parsed = Decimal(amount)
            except InvalidOperation:
                raise BitcoinCoreResponseError(_UTXO_ERROR) from None
        else:
            raise BitcoinCoreResponseError(_UTXO_ERROR)
        if not parsed.is_finite() or parsed <= 0 or parsed != parsed.quantize(SATOSHI):
            raise BitcoinCoreResponseError(_UTXO_ERROR)
        return parsed

    @staticmethod
    def _credentials_path(file_path: str) -> Path:
        """Return file_path when it resolves inside the wallet directory."""
        if not isinstance(file_path, str) or file_path == "":
            raise ValueError(_CREDENTIALS_PATH_ERROR)
        base = WALLET_DIRECTORY.resolve()
        resolved = (base / file_path).resolve()
        if not resolved.is_relative_to(base):
            raise ValueError(_CREDENTIALS_PATH_ERROR)
        return resolved

    @staticmethod
    def _load_credentials(path: Path) -> dict[str, str]:
        """Return the credential pair stored at path."""
        if path.stat().st_size > MAX_CREDENTIALS_BYTES:
            raise ValueError("Credentials file is larger than the allowed size.")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeError):
            raise ValueError(_CREDENTIALS_ERROR) from None
        return BitcoinWallet._validated_credentials(payload)

    @staticmethod
    def _validated_credentials(payload: object) -> dict[str, str]:
        """Return payload when it is exactly rpc_user and rpc_password as non-empty strings."""
        if not isinstance(payload, dict) or set(payload) != {RPC_USERNAME_KEY, RPC_PASSWORD_KEY}:
            raise ValueError(_CREDENTIALS_ERROR)
        username = payload[RPC_USERNAME_KEY]
        password = payload[RPC_PASSWORD_KEY]
        if not isinstance(username, str) or not isinstance(password, str) or username == "" or password == "":
            raise ValueError(_CREDENTIALS_ERROR)
        return {RPC_USERNAME_KEY: username, RPC_PASSWORD_KEY: password}

    @staticmethod
    def _write_credentials(path: Path, credentials: dict[str, str]) -> None:
        """Write credentials as JSON, creating the file for the current user only."""
        payload = json.dumps(credentials).encode()
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        if os.name == "posix":
            descriptor = os.open(path, flags, CREDENTIALS_FILE_MODE)
        else:
            descriptor = os.open(path, flags)
        try:
            os.write(descriptor, payload)
        finally:
            os.close(descriptor)

    @staticmethod
    def _restrict_to_owner(path: Path) -> None:
        """Limit path so only the current user can read and write it."""
        if os.name == "nt":
            BitcoinWallet._restrict_windows_acl(path)
            return
        path.chmod(CREDENTIALS_FILE_MODE)

    @staticmethod
    def _windows_icacls_path() -> Path:
        """Return icacls.exe when SystemRoot is a drive folder named Windows."""
        system_root = os.environ.get("SystemRoot", r"C:\Windows")
        if _WINDOWS_ROOT_RE.fullmatch(system_root) is None:
            raise OSError("The Windows directory could not be used to restrict the credentials file.")
        return Path(system_root) / "System32" / "icacls.exe"

    @staticmethod
    def _restrict_windows_acl(path: Path) -> None:
        """Replace inherited Windows ACLs with read and write for the current user."""
        username = os.environ.get("USERNAME", "")
        if _WINDOWS_ACCOUNT_RE.fullmatch(username) is None:
            raise OSError("The current user name is required to restrict the credentials file.")
        # shell is false. SystemRoot is X:\Windows and USERNAME is a plain account name.
        # shlex.quote would add quotes that icacls treats as part of the account name.
        completed = subprocess.run(  # noqa: S603
            [  # nosemgrep: dangerous-subprocess-use-tainted-env-args
                str(BitcoinWallet._windows_icacls_path()),
                str(path),
                "/inheritance:r",
                "/grant:r",
                f"{username}:(R,W)",
            ],
            check=False,
            capture_output=True,
            text=True,
            shell=False,
        )
        if completed.returncode != 0:
            raise OSError("The credentials file could not be restricted to its owner.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    wallet = BitcoinWallet()
    print(f"Wallet Address: {wallet.address}")
    print(f"Wallet Balance: {wallet.get_balance()} BTC")
