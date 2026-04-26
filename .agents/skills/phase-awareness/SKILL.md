---
name: phase-awareness
description: Proactively applied at session start and before implementation work; orients Codex to the current phase and its explicit scope constraints
---

# Phase Awareness

## Trigger
Applied at session start and before any implementation work begins.

## Protocol

### At session start
1. Read `AGENTS.md` section 2 (Phase Constraints) to determine the current phase.
2. Read `docs/status.md` for the current state and in-progress work.
3. Read `docs/versions.md` for the latest version entry.
4. Report the current phase and its scope in the orientation paragraph.

### Before any implementation work
1. Confirm the requested change falls within the current phase's scope.
2. If the request involves Phase 2+ features (HD wallets, SegWit, multi-sig, custom blockchain, P2P), STOP and flag it:
   - "This is a Phase N feature. Current phase is Phase M. Proceed anyway?"
3. If the request would modify the `bitcoin_blockchain_dev/` reference directory, BLOCK it immediately -- that directory is read-only regardless of phase.

### Phase 1 scope checklist
In scope:
- Private key generation and management
- Public key derivation (compressed, secp256k1)
- P2PKH address generation (Base58Check)
- Transaction creation, signing, broadcasting via RPC
- Balance retrieval via RPC
- Type annotations, docstrings, tests
- Constants extraction, error handling improvements

Out of scope (Phase 2+):
- BIP-32 HD key derivation
- BIP-39 mnemonic seed phrases
- BIP-44 multi-account structure
- SegWit / Bech32 addresses
- Multi-signature transactions
- Wallet encryption
- Coin selection algorithms
- Custom blockchain implementation
- P2P networking
- Docker containerization
- Frontend / UI

### Phase transitions
When all items in the Phase Completion Gate (AGENTS.md section 10) are checked off, flag it:
- "Phase 1 completion gate appears to be met. Review the checklist and confirm before moving to Phase 2."