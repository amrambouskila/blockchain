"""Build educational blocks and the payments used by the node tests."""

from __future__ import annotations

import struct

from bitcoin_wallet import BitcoinWallet
from btc_wallet.transaction_signer import TransactionSigner
from btc_wallet.wallet_constants import SEQUENCE_FINAL, TX_VERSION
from edu_node.block_header import BlockHeader
from edu_node.blockchain import Blockchain
from edu_node.edu_block import EduBlock
from edu_node.edu_transaction import EduTransaction, p2pkh_script
from edu_node.merkle_tree import MerkleTree
from edu_node.node_constants import BLOCK_SUBSIDY_COINS, BLOCK_VERSION, SATS_PER_COIN
from edu_node.proof_of_work import ProofOfWork


class ChainBlocks:
    """Mine blocks on a chain and sign payments that spend one of its outputs."""

    def block(
        self,
        chain: Blockchain,
        private_key: str,
        *,
        parent: bytes | None = None,
        bits: int | None = None,
        timestamp: int | None = None,
        payments: list[EduTransaction] | None = None,
        fee: int = 0,
    ) -> EduBlock:
        """Return a mined block extending parent, paying private_key's P2PKH output."""
        chosen = chain.next_parent() if parent is None else parent
        when = chain.timestamp_for(chosen) if timestamp is None else timestamp
        chosen_bits = chain.bits_for(chosen) if bits is None else bits
        extras = [] if payments is None else payments
        transactions = [self.coinbase(chain, private_key, chosen, fee), *extras]
        return self._mined(chosen, when, chosen_bits, transactions)

    def coinbase(self, chain: Blockchain, private_key: str, parent: bytes, fee: int = 0) -> EduTransaction:
        """Return a coinbase paying private_key at the height that follows parent."""
        script = p2pkh_script(bytes.fromhex(BitcoinWallet.derive_public_key(private_key)))
        value = BLOCK_SUBSIDY_COINS * SATS_PER_COIN + fee
        return EduTransaction.coinbase(chain.height_after(parent), value, script)

    def spend(
        self,
        private_key: str,
        source: EduTransaction,
        vout: int,
        value: int,
        pay_script: bytes,
    ) -> EduTransaction:
        """Return a signed payment that spends one output of source."""
        script_code = source.outputs[vout][1]
        signature = TransactionSigner().sign_input(
            private_key,
            [(source.display_id, vout)],
            [(value, pay_script)],
            0,
            script_code,
        )
        public_key = bytes.fromhex(BitcoinWallet.derive_public_key(private_key))
        script_sig = bytes([len(signature)]) + signature + bytes([len(public_key)]) + public_key
        raw = _raw([(source.display_id, vout, script_sig)], [(value, pay_script)])
        return EduTransaction.parse(raw)

    def _mined(self, parent: bytes, timestamp: int, bits: int, transactions: list[EduTransaction]) -> EduBlock:
        """Return transactions under a header that meets bits."""
        root = MerkleTree().root([tx.internal_id for tx in transactions])
        header = ProofOfWork().mine(BLOCK_VERSION, parent, root, timestamp, bits)
        return EduBlock(BlockHeader.parse(header), transactions)


def _raw(inputs: list[tuple[str, int, bytes]], outputs: list[tuple[int, bytes]]) -> bytes:
    """Return legacy transaction bytes with one-byte counts."""
    parts = [struct.pack("<I", TX_VERSION), bytes([len(inputs)])]
    for display, vout, script in inputs:
        parts.append(bytes.fromhex(display)[::-1])
        parts.append(struct.pack("<I", vout))
        parts.append(bytes([len(script)]))
        parts.append(script)
        parts.append(struct.pack("<I", SEQUENCE_FINAL))
    parts.append(bytes([len(outputs)]))
    for value, script in outputs:
        parts.append(struct.pack("<q", value))
        parts.append(bytes([len(script)]))
        parts.append(script)
    parts.append(struct.pack("<I", 0))
    return b"".join(parts)
