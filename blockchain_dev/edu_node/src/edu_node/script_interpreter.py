"""A small script interpreter. Opcodes outside the allowlist fail the script."""

from __future__ import annotations

import hashlib

import ecdsa

from bitcoin_wallet import BitcoinWallet
from btc_wallet.transaction_signer import TransactionSigner
from btc_wallet.wallet_constants import SIGHASH_ALL
from edu_node.edu_transaction import EduTransaction
from edu_node.node_constants import (
    HASH_BYTES,
    MAX_OPCODE_COUNT,
    MAX_SCRIPT_BYTES,
    MAX_STACK_ITEM_BYTES,
    MAX_STACK_ITEMS,
    MULTISIG_MAX,
    MULTISIG_MIN,
    OP_1,
    OP_16,
    OP_CHECKMULTISIG,
    OP_CHECKSIG,
    OP_DUP,
    OP_EQUALVERIFY,
    OP_HASH160,
    OP_PUSH_MAX,
    OP_PUSH_MIN,
    SCRIPT_NUMBER_BYTES,
)

_TRUE = b"\x01"
_FALSE = b""


class ScriptInterpreter:
    """Run a scriptSig and then its scriptPubKey on one stack."""

    def accepts(self, script_sig: bytes, script_pubkey: bytes, tx: EduTransaction, index: int) -> bool:
        """Return whether the scripts leave exactly one true value."""
        if not isinstance(script_sig, bytes) or not isinstance(script_pubkey, bytes):
            return False
        if len(script_sig) > MAX_SCRIPT_BYTES or len(script_pubkey) > MAX_SCRIPT_BYTES:
            return False
        if type(index) is not int or index < 0:
            return False
        stack: list[bytes] = []
        ops = [0]
        if not self._execute(script_sig, stack, ops, tx, index, script_pubkey):
            return False
        if not self._execute(script_pubkey, stack, ops, tx, index, script_pubkey):
            return False
        return len(stack) == 1 and any(byte != 0 for byte in stack[0])

    def _execute(
        self,
        script: bytes,
        stack: list[bytes],
        ops: list[int],
        tx: EduTransaction,
        index: int,
        script_code: bytes,
    ) -> bool:
        """Run one script. Push opcodes do not count toward the opcode limit."""
        cursor = 0
        while cursor < len(script):
            opcode = script[cursor]
            cursor += 1
            if opcode == 0:
                if not self._push(stack, _FALSE):
                    return False
                continue
            if OP_PUSH_MIN <= opcode <= OP_PUSH_MAX:
                payload = script[cursor : cursor + opcode]
                if len(payload) != opcode:
                    return False
                cursor += opcode
                if not self._push(stack, payload):
                    return False
                continue
            ops[0] += 1
            if ops[0] > MAX_OPCODE_COUNT:
                return False
            if OP_1 <= opcode <= OP_16:
                if not self._push(stack, bytes([opcode - OP_1 + 1])):
                    return False
                continue
            if opcode == OP_DUP:
                if len(stack) == 0 or not self._push(stack, stack[-1]):
                    return False
                continue
            if opcode == OP_HASH160:
                if len(stack) == 0:
                    return False
                stack[-1] = BitcoinWallet._hash160(stack[-1])
                continue
            if opcode == OP_EQUALVERIFY:
                if len(stack) < 2 or stack.pop() != stack.pop():
                    return False
                continue
            if opcode == OP_CHECKSIG:
                if not self._checksig(stack, tx, index, script_code):
                    return False
                continue
            if opcode == OP_CHECKMULTISIG:
                if not self._checkmultisig(stack, tx, index, script_code):
                    return False
                continue
            return False
        return True

    def _push(self, stack: list[bytes], item: bytes) -> bool:
        """Push item when the stack and the item are inside the limits."""
        if len(item) > MAX_STACK_ITEM_BYTES or len(stack) >= MAX_STACK_ITEMS:
            return False
        stack.append(item)
        return True

    def _checksig(self, stack: list[bytes], tx: EduTransaction, index: int, script_code: bytes) -> bool:
        """Pop a public key and a signature and push whether they match."""
        if len(stack) < 2:
            return False
        public_key = stack.pop()
        signature = stack.pop()
        return self._push(stack, _TRUE if self._verify(signature, public_key, tx, index, script_code) else _FALSE)

    def _checkmultisig(self, stack: list[bytes], tx: EduTransaction, index: int, script_code: bytes) -> bool:
        """Pop n keys and m signatures. Bitcoin also pops one unused extra item."""
        key_count = self._pop_count(stack)
        if key_count is None or not MULTISIG_MIN <= key_count <= MULTISIG_MAX or len(stack) < key_count + 1:
            return False
        keys = [stack.pop() for _number in range(key_count)]
        sig_count = self._pop_count(stack)
        if sig_count is None or not MULTISIG_MIN <= sig_count <= key_count or len(stack) < sig_count + 1:
            return False
        signatures = [stack.pop() for _number in range(sig_count)]
        stack.pop()
        keys.reverse()
        signatures.reverse()
        key_index = 0
        for signature in signatures:
            matched = False
            while key_index < len(keys):
                public_key = keys[key_index]
                key_index += 1
                if self._verify(signature, public_key, tx, index, script_code):
                    matched = True
                    break
            if not matched:
                return False
        return self._push(stack, _TRUE)

    def _pop_count(self, stack: list[bytes]) -> int | None:
        """Pop a small script number."""
        if len(stack) == 0:
            return None
        item = stack.pop()
        if len(item) > SCRIPT_NUMBER_BYTES:
            return None
        if item == b"":
            return 0
        return int.from_bytes(item, "little")

    def _verify(self, signature: bytes, public_key: bytes, tx: EduTransaction, index: int, script_code: bytes) -> bool:
        """Return whether signature is low-s DER plus SIGHASH_ALL for this input."""
        if len(signature) < 2 or signature[-1] != SIGHASH_ALL or len(public_key) != HASH_BYTES + 1:
            return False
        verifying_key = _compressed_key(public_key)
        if verifying_key is None:
            return False
        try:
            digest = TransactionSigner().digest(
                [(txid, vout) for txid, vout, _script, _sequence in tx.inputs],
                tx.outputs,
                index,
                script_code,
                locktime=tx.locktime,
            )
            verifying_key.verify_digest(signature[:-1], digest, sigdecode=ecdsa.util.sigdecode_der)
        except (ValueError, ecdsa.BadSignatureError, AssertionError):
            return False
        return True


def _compressed_key(public_key: bytes) -> ecdsa.VerifyingKey | None:
    """Return a verifying key for a compressed 02/03 public key."""
    prefix = public_key[0]
    if prefix not in (2, 3):
        return None
    coordinate_x = int.from_bytes(public_key[1:], "big")
    curve = ecdsa.SECP256k1.curve
    prime = curve.p()
    if not 0 < coordinate_x < prime:
        return None
    alpha = (pow(coordinate_x, 3, prime) + curve.a() * coordinate_x + curve.b()) % prime
    beta = pow(alpha, (prime + 1) // 4, prime)
    if pow(beta, 2, prime) != alpha:
        return None
    even = beta % 2 == 0
    coordinate_y = beta if even == (prefix == 2) else prime - beta
    try:
        point = ecdsa.ellipticcurve.Point(curve, coordinate_x, coordinate_y)
        return ecdsa.VerifyingKey.from_public_point(point, curve=ecdsa.SECP256k1, hashfunc=hashlib.sha256)
    except (ValueError, AssertionError):
        return None
