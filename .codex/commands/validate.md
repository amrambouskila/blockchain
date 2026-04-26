---
name: validate
description: Validate cryptographic operations and wallet logic against Bitcoin specifications
---

# Cryptographic Validation

Multi-layer validation of wallet cryptographic operations against Bitcoin protocol specifications and known test vectors.

## Instructions

Before anything else:
1. Re-read `AGENTS.md` sections 3 and 5 (Architecture rules and Bitcoin Core reference).
2. Re-read `docs/BLOCKCHAIN_MASTER_PLAN.md` section 7 (Cross-Phase Concerns -- Cryptographic Primitives).

### Layer 1: Key Generation Validation
- Private key is exactly 256 bits (32 bytes)
- Private key is within valid secp256k1 range (1 to n-1, where n is the curve order)
- Entropy sources are cryptographically secure (`secrets.token_bytes`, `os.urandom`)
- No deterministic fallback that could produce predictable keys

### Layer 2: Public Key Derivation Validation
- ECDSA point multiplication uses secp256k1 curve (not P-256, not ed25519)
- Compressed public key format: `02` prefix if y is even, `03` if y is odd
- Public key is exactly 33 bytes (1 prefix + 32 x-coordinate)
- **Test vector**: Validate against at least one known private-key-to-public-key pair from Bitcoin wiki or BIP-340

### Layer 3: Address Generation Validation
- Hash160 = RIPEMD-160(SHA-256(compressed_public_key))
- Network byte prepended: `0x00` for mainnet P2PKH, `0x6f` for testnet
- Checksum = first 4 bytes of SHA-256(SHA-256(network_byte + hash160))
- Base58Check encoding produces valid Bitcoin address format
- **Test vector**: Validate against known addresses:
  - Genesis block coinbase address: `1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa`
  - Or use Bitcoin wiki's Base58Check test vectors

### Layer 4: Transaction Validation
- Raw transaction format matches Bitcoin serialization spec
- Signature uses DER encoding
- `signrawtransactionwithkey` receives the correct private key format
- Change calculation: `total_input - amount - fee >= 0`
- Fee is not negative and not unreasonably large

### Layer 5: RPC Integration Validation
- RPC connection handles authentication correctly
- `listunspent` returns valid UTXO format
- `createrawtransaction` / `signrawtransactionwithkey` / `sendrawtransaction` chain works end-to-end
- Error handling for: connection refused, auth failure, insufficient funds, invalid address

### Report Format
```
=== CRYPTO VALIDATION REPORT ===

Key Generation:     PASS/FAIL (details)
Public Key:         PASS/FAIL (test vectors: N validated)
Address:            PASS/FAIL (test vectors: N validated)
Transactions:       PASS/FAIL (details)
RPC Integration:    PASS/FAIL / NOT TESTED (requires running node)

OVERALL: VALID / ISSUES FOUND (list each issue)
```