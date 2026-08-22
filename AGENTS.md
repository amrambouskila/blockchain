# Blockchain Project - AGENTS.md

<mandatory_workflow>

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

</mandatory_workflow>

---

<critical_context>

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

</critical_context>

---

<project_identity>

## 1. Project Identity

- **Name:** Blockchain
- **Location:** `blockchain/`
- **Master plan:** `docs/BLOCKCHAIN_MASTER_PLAN.md`
- **Nature:** Educational/research -- learning blockchain internals by building
- **Active code:** `blockchain_dev/bitcoin_wallet_dev/`
- **Reference code:** `blockchain_dev/bitcoin_blockchain_dev/` (READ-ONLY)

</project_identity>

---

<phase_constraints>

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

</phase_constraints>

---

<architecture>

## 3. Architecture & Code Rules

### Python conventions
- **Python 3.11+**
- **`from __future__ import annotations`** at the top of every module
- Full type annotations on every function signature
- **ruff** for lint + format (`line-length = 120`, rules: `["E", "F", "I", "N", "UP", "ANN", "S"]` -- `S` is the flake8-bandit family, see section 9a)
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

</architecture>

---

<file_structure>

## 4. Directory Structure

```
blockchain/
├── AGENTS.md                              # This file -- project AI guidelines
├── README.md                              # Human-facing overview
├── docs/
│   ├── BLOCKCHAIN_MASTER_PLAN.md          # Authoritative master plan
│   ├── status.md                          # Current project state
│   └── versions.md                        # Semver changelog
├── .codex/
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

</file_structure>

---

<non_negotiable>

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

</non_negotiable>

---

<tech_stack>

## 6. Dependencies (Phase 1)

| Package | Purpose | Version constraint |
|---|---|---|
| `ecdsa` | ECDSA signing (secp256k1) | `>=0.18` |
| `base58` | Base58Check encoding/decoding | `>=2.1` |
| `python-bitcoinrpc` | Bitcoin Core RPC client | `>=1.0` |
| `pytest` | Testing | `>=7.0` |
| `pytest-cov` | Coverage | `>=4.0` |
| `ruff` | Lint + format | `>=0.3` |

</tech_stack>

---

<commands>

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

# SAST (same set the CI `sast` job runs -- see section 9a)
uvx ruff check . && uvx semgrep scan --config auto --config p/owasp-top-ten --config p/python --severity ERROR --error && uv run --with pip-audit pip-audit && gitleaks detect --no-git --redact
# gitleaks is a standalone binary (not on PyPI) -- install it locally; the other three run through uv.
```

</commands>

---

<change_policy>

## 8. Change Policy & Documentation

After every significant change:
1. Update `docs/status.md` to reflect the current state
2. Update `docs/versions.md` with the computed next version (see global AGENTS.md section 6)
3. If architecture decisions were made, document them in the master plan

</change_policy>

---

<versioning>

## 9. Versioning

- **Source of truth:** `docs/versions.md` (no `pyproject.toml` yet -- will be created when the project gets packaged in Phase 2)
- **Current version:** `0.1.0` (initial scaffold + existing wallet code)
- Follows strict semver per global AGENTS.md section 6

</versioning>

---

<security>

## 9a. Security -- SAST Scanning & Injection Safety (Non-Negotiable)

Per global AGENTS.md section 19. This is a wallet: the attack surface is small, but every boundary touches private keys or signed transactions, so the bar is production-grade regardless of the "educational" label.

### SAST scanning
- **Wired.** `.github/workflows/ci.yml` (GitHub Actions -- public project) has a `sast` job (`needs: [lint]`) that fails on any HIGH/CRITICAL finding. When the `test` job lands it goes after `sast` (`needs: [sast]`) so the order stays `lint -> sast -> test`.
- Tools as wired: **CodeQL** (`github/codeql-action` init -> analyze, language `python`, category `codeql`); **Semgrep** via `uvx semgrep scan --config auto --config p/owasp-top-ten --config p/python --severity ERROR --error --sarif`, SARIF uploaded through `github/codeql-action/upload-sarif` (category `semgrep`, `if: !cancelled()`), with a separate step failing the job on findings; **gitleaks** via `gitleaks/gitleaks-action@v2` on a `fetch-depth: 0` checkout (default ruleset -- the custom 64-hex/WIF private-key rule is pending; add it as `.gitleaks.toml` when the first test vector is committed); **`pip-audit`** via `uv run --with pip-audit pip-audit`. Job-level `permissions: contents: read, security-events: write, actions: read`.
- **ruff `S` rules** are wired: `pyproject.toml` lint select is `["E", "F", "I", "N", "UP", "ANN", "S"]` and the tree is clean with no `noqa`. `S101` gets a per-file ignore under `tests/` when the test suite is created (no `tests/` exists yet).
- Pending: project Semgrep rules in `.semgrep/` (none yet -- registry rulesets only); **Trivy** (`aquasecurity/trivy-action`, `--severity HIGH,CRITICAL --exit-code 1`) in `docker-build` once a Dockerfile exists (Phase 2+) -- no Dockerfile today, so no Trivy.
- Local reproduction (see section 7): `uvx ruff check . && uvx semgrep scan --config auto --config p/owasp-top-ten --config p/python --severity ERROR --error && uv run --with pip-audit pip-audit && gitleaks detect --no-git --redact`.

### Injection safety -- input boundary inventory

| Boundary | Where | Injection classes | Required defense |
|---|---|---|---|
| RPC credentials file | `BitcoinWallet.get_rpc_credentials()` -- `rpc_credentials_file` ctor arg, `json.load`/`json.dump` | Path traversal, unsafe deserialization, secrets | Resolve path and require `resolved.is_relative_to(base.resolve())` (base = wallet directory); `json` only, never `pickle`; validate the decoded dict against a typed schema (`rpc_user`/`rpc_password` as `str`, nothing else) before use; file written with owner-only permissions; file stays gitignored |
| RPC URL construction | `BitcoinWallet.connect_to_rpc()` -- `f'http://{rpc_user}:{rpc_password}@127.0.0.1:8332'` | Header/URL injection, SSRF, secrets | Percent-encode user and password (`urllib.parse.quote`) so `@`, `/`, `:`, CR/LF in a credential cannot rewrite the host; host/port are constants, never taken from the credentials file; credentials never echoed in logs or exceptions |
| Bitcoin Core JSON-RPC responses | `listunspent`, `createrawtransaction`, `signrawtransactionwithkey`, `sendrawtransaction` via `AuthServiceProxy` | Unsafe deserialization, resource exhaustion, log injection | Treat the node as untrusted: validate UTXO entries (`txid` 64-hex, `vout` int >= 0, `amount` `Decimal`) before arithmetic or re-submission; cap the number of UTXOs iterated; `JSONRPCException` messages are logged via structured logging with CR/LF stripped, never interpolated into a shell or a further RPC call |
| Send parameters | `create_and_send_transaction(recipient_address, amount)` and `__main__` | Input validation (address/amount), resource exhaustion | `recipient_address` must pass Base58Check decode + version-byte check (Bech32 validation added in Phase 2) before being placed in an output map; `amount` is `Decimal`, bounded `> 0` and `<= balance - fee`; never build the outputs dict from unvalidated strings |
| Error output | `print(f"... {e}")` in every RPC wrapper | Secrets leakage, log injection | Exceptions never contain the private key or RPC password; replace `print` with `logging` using structured fields; `signrawtransactionwithkey` errors are logged without the arguments |
| Entropy | `generate_private_key()` | Weak randomness (ruff `S311`) | `secrets.token_bytes` / `os.urandom` only; the `random.getrandbits` mix is flagged by `S311` and is removed as part of Phase 1 cleanup, not suppressed |

Planned boundaries (documented here when built, per the master plan):
- **Phase 2:** BIP-39 mnemonic input (wordlist allowlist + checksum before any derivation; never logged), encrypted wallet file at rest (AES-256-GCM via `cryptography`, authenticated decrypt before parsing, path-traversal check on the wallet path), `estimatesmartfee` RPC responses (validated numeric bounds).
- **Phase 3:** FastAPI REST + WebSocket node API (Pydantic request models, body-size limits, pagination caps, explicit CORS allowlist), P2P TCP layer (bounded message framing, max block/tx size, per-peer rate limits, no deserialization beyond a typed wire schema), script engine (op-count and stack-size limits, no `eval`/`exec`, interpreter over an explicit opcode allowlist).

### Project-specific additions
- `blockchain_dev/bitcoin_blockchain_dev/` (Bitcoin Core clone) is excluded from Semgrep/gitleaks paths -- it is read-only reference material, not project code, and is gitignored.
- Private keys are the highest-value secret in the repo: gitleaks must carry a custom rule for 64-hex strings and WIF-prefixed strings in any committed file (pending -- the wired `gitleaks-action` currently runs its default ruleset); a test vector key is allowed only in `tests/` with an inline `# gitleaks:allow` and the published source of the vector.
- Never send a mainnet transaction from CI or from a test. Tests mock `AuthServiceProxy`; the `sast` job has no network access to a node.

The task-completion self-audit (section 11) now includes a **Security check** item.

</security>

---

<definition_of_done>

## 10. Phase Completion Gate -- Phase 1

Phase 1 is done when:
- [ ] `bitcoin_wallet.py` has full type annotations
- [ ] `from __future__ import annotations` at top of every module
- [ ] All functions have docstrings documenting parameters and return types
- [ ] pytest test suite exists with tests for: key generation, public key derivation, address generation
- [ ] Tests use known Bitcoin test vectors for validation
- [ ] No magic numbers -- fee, network byte, etc. extracted to named constants
- [ ] ruff passes cleanly (including `S` rules)
- [ ] SAST green with zero HIGH/CRITICAL findings (`sast` job in `.github/workflows/ci.yml`)
- [ ] All input boundaries injection-safe and documented in `<security>` (section 9a)
- [ ] `docs/status.md` and `docs/versions.md` are current
- [ ] README.md accurately describes the project and how to run it

</definition_of_done>

---

<self_audit>

## 11. Output & Completion Expectations

At the end of every non-trivial task, run the universal self-audit checklist from global AGENTS.md section 15, plus these project-specific items:

1. **Crypto safety check** -- No private keys logged, printed, or included in error messages. No custom cryptography introduced.
2. **Reference isolation check** -- No files under `bitcoin_blockchain_dev/` were modified.
3. **RPC credential check** -- No RPC credentials committed or hard-coded.
4. **Test vector check** -- If crypto operations were added/changed, are they validated against known test vectors?
5. **Security check** -- Local SAST clean; every touched input boundary names its injection class(es) and defense; `<security>` section updated if a boundary was added.

---

**Closing reminder:** Re-read this file before the next change. Prior sessions do not carry over.

</self_audit>