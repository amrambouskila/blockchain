# Status

## Current State
**Phase:** 1 -- Python Wallet Basics
**Version:** 0.1.0 (initial scaffold)

## What Exists
- `blockchain_dev/bitcoin_wallet_dev/bitcoin_wallet.py` -- a working `BitcoinWallet` class with:
  - Private key generation (mixed entropy: `secrets` + `os.urandom` + `random`)
  - Compressed public key derivation (ECDSA secp256k1)
  - P2PKH address generation (SHA-256 + RIPEMD-160 + Base58Check)
  - Bitcoin Core RPC integration (balance, raw tx, sign, broadcast)
  - RPC credential management (auto-generate + persist to JSON)
- `blockchain_dev/bitcoin_blockchain_dev/` -- full Bitcoin Core clone for reference (read-only)

## What's Missing (Phase 1 remaining)
- Type annotations (`from __future__ import annotations`, full signatures)
- Named constants (network byte, default fee extracted from inline literals)
- Docstrings on all methods
- pytest test suite with known Bitcoin test vectors
- ruff configuration
- Edge case handling (invalid addresses, connection failures)

## Recent Decisions
- Project scaffolded with full documentation infrastructure (CLAUDE.md, master plan, status, versions, .claude hooks/commands/skills)
- Bitcoin Core directory gitignored (it's a reference clone with its own .git)

## What's Next
- Add type annotations and `from __future__ import annotations` to `bitcoin_wallet.py`
- Extract magic numbers to named constants
- Create pytest test suite with Bitcoin test vectors for key-to-address derivation
- Add ruff configuration