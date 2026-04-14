# Blockchain Project - CLAUDE.md

> **MANDATORY WORKFLOW: READ THIS ENTIRE FILE BEFORE EVERY CHANGE.** Every time. No skimming, no assuming prior-session context carries over -- it does not.
>
> **Why:** This project spans multiple sessions and months of development. Skipping the re-read produces decisions that contradict the architecture, duplicate existing patterns, break data contracts, or introduce tech debt that compounds.
>
> **The workflow, every time:**
> 1. Read this entire file in full.
> 2. Read `docs/BLOCKCHAIN_MASTER_PLAN.md` -- the authoritative master plan.
> 3. Read `docs/status.md` -- current state / what was just built.
> 4. Read `docs/versions.md` -- recent version history.
> 5. Read the source files you plan to modify -- understand existing patterns first.
> 6. Then implement, following the rules and contracts defined here.

---

## 0. Critical Context

This is a **blockchain learning and research project**, not a production cryptocurrency system. Its purpose is to deeply understand blockchain internals -- cryptography, consensus, transaction mechanics, wallet operations -- by studying Bitcoin Core source code and building Python implementations from scratch.

**What this project is NOT:**
- Not a production wallet. Never store real funds with this code.
- Not a fork of Bitcoin Core. The Bitcoin Core clone is READ-ONLY reference material.
- Not a DeFi/smart-contract platform (that may come in later phases, but not now).

**The two halves of this project:**
1. **Bitcoin Core reference** (`blockchain_dev/bitcoin_blockchain_dev/`) -- a full clone of the Bitcoin Core C++ codebase. This is for reading, studying, and cross-referencing. **DO NOT modify any file under this directory.** It has its own `.git` and is treated as an external dependency.
2. **Python wallet** (`blockchain_dev/bitcoin_wallet_dev/`) -- the active development target. A Python implementation of Bitcoin wallet operations: key generation, address derivation, transaction creation, signing, and broadcasting.

**Current phase:** Phase 1 -- Python wallet basics.

---

## 1. Project Identity

- **Name:** Blockchain
- **Location:** `blockchain/`
- **Master plan:** `docs/BLOCKCHAIN_MASTER_PLAN.md`
- **Nature:** Educational/research -- learning blockchain internals by building
- **Active code:** `blockchain_dev/bitcoin_wallet_dev/`
- **Reference code:** `blockchain_dev/bitcoin_blockchain_dev/` (READ-ONLY)

---

## 2. Phase Constraints

### Phase 1: Python Wallet Basics (current)
**In scope:**
- Private key generation (cryptographically secure)
- Public key derivation (ECDSA secp256k1, compressed)
- Bitcoin address generation (Base58Check encoding)
- Transaction creation, signing, and broadcasting via Bitcoin Core RPC
- Balance retrieval via RPC
- Basic RPC credential management
- Type annotations on all functions
- pytest test suite with mocked RPC calls
- Documentation (this file, master plan, status, versions)

**Explicitly deferred:**
- HD wallets (BIP-32/BIP-39/BIP-44) -- Phase 2
- Multi-signature support -- Phase 2
- SegWit / Bech32 addresses -- Phase 2
- Custom blockchain implementation -- Phase 3
- Smart contracts / scripting -- Phase 3
- Frontend / UI -- Phase 3+
- Docker containerization -- Phase 2+ (when there's a service to containerize)

### Phase 2: Enhanced Wallet with Key Management
- BIP-32 hierarchical deterministic key derivation
- BIP-39 mnemonic seed phrases
- BIP-44 multi-account structure
- SegWit (Bech32) address support
- Multi-signature transactions
- Wallet encryption at rest
- Transaction fee estimation
- UTXO management and coin selection algorithms

### Phase 3: Custom Blockchain Implementation
- Simplified blockchain from scratch (not Bitcoin -- educational)
- Proof-of-work consensus
- Peer-to-peer networking (basic)
- Block validation and chain selection
- Merkle tree implementation
- mempool and transaction relay
- Simple scripting language for transaction validation

---

## 3. Architecture & Code Rules

### Python conventions
- **Python 3.11+**
- **`from __future__ import annotations`** at the top of every module
- Full type annotations on every function signature
- **ruff** for lint + format (`line-length = 120`, rules: `["E", "F", "I", "N", "UP", "ANN"]`)
- **pytest** with `pytest-cov` for testing
- **No `Any` type** without explicit justification
- **One class per file** -- `BitcoinWallet` lives in `bitcoin_wallet.py`, future classes get their own files
- **No magic numbers** -- transaction fees, network bytes, curve parameters go in constants or config

### Cryptography rules (security-sensitive)
- **Never roll custom cryptography.** Use `ecdsa`, `hashlib`, `secrets`, `os.urandom` from the standard library or well-audited packages.
- **Private keys are sensitive data.** Never log them, never print them in production code, never include them in error messages.
- **Entropy sources:** `secrets.token_bytes()` and `os.urandom()` are the approved entropy sources. The current `random.getrandbits()` mixing is acceptable for educational purposes but would NOT be acceptable in production.
- **Signature encoding:** DER encoding via `ecdsa.util.sigencode_der` is correct for Bitcoin transactions.
- **Address formats:** Phase 1 uses Base58Check (P2PKH, version byte `0x00` for mainnet). Phase 2 adds Bech32.

### RPC interaction
- Bitcoin Core RPC via `python-bitcoinrpc` (`AuthServiceProxy`)
- Credentials stored in `rpc_credentials.json` (gitignored, never committed)
- Default RPC endpoint: `127.0.0.1:8332` (Bitcoin Core mainnet default)
- All RPC calls wrapped in try/except for `JSONRPCException`

### Error handling
- Validate at system boundaries: user input, RPC responses, file loads
- Specific exception types only -- no bare `except:`
- Never swallow exceptions silently

### Testing
- **pytest** with `pytest-cov`
- Coverage target: 100%
- Mock RPC calls (external dependency) but NEVER mock cryptographic operations
- Test key derivation against known test vectors (BIP-340, Bitcoin wiki test vectors)
- Test address generation against known Bitcoin addresses
- `np.testing`-style tolerance is not needed here -- crypto operations are deterministic, use exact equality

---

## 4. Directory Structure

```
blockchain/
├── CLAUDE.md                              # This file -- project AI guidelines
├── README.md                              # Human-facing overview
├── docs/
│   ├── BLOCKCHAIN_MASTER_PLAN.md          # Authoritative master plan
│   ├── status.md                          # Current project state
│   └── versions.md                        # Semver changelog
├── .claude/
│   ├── settings.json                      # Hooks and permissions
│   ├── commands/                          # Slash commands
│   │   ├── review.md
│   │   ├── pre-commit.md
│   │   └── validate.md
│   └── skills/
│       └── phase-awareness/
│           └── SKILL.md
├── .gitignore
└── blockchain_dev/
    ├── bitcoin_blockchain_dev/            # READ-ONLY Bitcoin Core clone (gitignored)
    │   └── ... (full Bitcoin Core C++ source)
    └── bitcoin_wallet_dev/                # Active Python wallet development
        └── bitcoin_wallet.py              # BitcoinWallet class
```

### Key entrypoints
- `blockchain_dev/bitcoin_wallet_dev/bitcoin_wallet.py` -- the wallet class, run with `python bitcoin_wallet.py`
- `blockchain_dev/bitcoin_blockchain_dev/` -- Bitcoin Core reference (read-only, has its own `.git`)

---

## 5. Bitcoin Core Reference -- READ-ONLY Contract

The `blockchain_dev/bitcoin_blockchain_dev/` directory is a full clone of Bitcoin Core. Rules:

1. **NEVER modify any file** under this directory.
2. **NEVER commit changes** to this directory (it's gitignored).
3. **DO read it** for understanding Bitcoin internals -- the C++ source is the definitive reference for how Bitcoin actually works.
4. **Useful reference paths within Bitcoin Core:**
   - `src/key.cpp` / `src/key.h` -- private key handling
   - `src/pubkey.cpp` / `src/pubkey.h` -- public key operations
   - `src/script/` -- transaction scripting
   - `src/wallet/` -- wallet implementation
   - `src/consensus/` -- consensus rules
   - `src/validation.cpp` -- block/transaction validation
   - `src/net.cpp` -- P2P networking
   - `src/miner.cpp` -- block mining

---

## 6. Dependencies (Phase 1)

| Package | Purpose | Version constraint |
|---|---|---|
| `ecdsa` | ECDSA signing (secp256k1) | `>=0.18` |
| `base58` | Base58Check encoding/decoding | `>=2.1` |
| `python-bitcoinrpc` | Bitcoin Core RPC client | `>=1.0` |
| `pytest` | Testing | `>=7.0` |
| `pytest-cov` | Coverage | `>=4.0` |
| `ruff` | Lint + format | `>=0.3` |

---

## 7. Local Commands

```bash
# Run the wallet (requires Bitcoin Core running with RPC enabled)
cd blockchain_dev/bitcoin_wallet_dev
python bitcoin_wallet.py

# Run tests (when they exist)
pytest tests/ -v --cov=blockchain_dev/bitcoin_wallet_dev

# Lint
ruff check .
ruff format --check .
```

---

## 8. Change Policy & Documentation

After every significant change:
1. Update `docs/status.md` to reflect the current state
2. Update `docs/versions.md` with the computed next version (see global CLAUDE.md section 6)
3. If architecture decisions were made, document them in the master plan

---

## 9. Versioning

- **Source of truth:** `docs/versions.md` (no `pyproject.toml` yet -- will be created when the project gets packaged in Phase 2)
- **Current version:** `0.1.0` (initial scaffold + existing wallet code)
- Follows strict semver per global CLAUDE.md section 6

---

## 10. Phase Completion Gate -- Phase 1

Phase 1 is done when:
- [ ] `bitcoin_wallet.py` has full type annotations
- [ ] `from __future__ import annotations` at top of every module
- [ ] All functions have docstrings documenting parameters and return types
- [ ] pytest test suite exists with tests for: key generation, public key derivation, address generation
- [ ] Tests use known Bitcoin test vectors for validation
- [ ] No magic numbers -- fee, network byte, etc. extracted to named constants
- [ ] ruff passes cleanly
- [ ] `docs/status.md` and `docs/versions.md` are current
- [ ] README.md accurately describes the project and how to run it

---

## 11. Output & Completion Expectations

At the end of every non-trivial task, run the universal self-audit checklist from global CLAUDE.md section 15, plus these project-specific items:

1. **Crypto safety check** -- No private keys logged, printed, or included in error messages. No custom cryptography introduced.
2. **Reference isolation check** -- No files under `bitcoin_blockchain_dev/` were modified.
3. **RPC credential check** -- No RPC credentials committed or hard-coded.
4. **Test vector check** -- If crypto operations were added/changed, are they validated against known test vectors?

---

**Closing reminder:** Re-read this file before the next change. Prior sessions do not carry over.