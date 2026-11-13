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

**The parts of this project:**
1. **Bitcoin Core reference** (`blockchain_dev/bitcoin_blockchain_dev/`) -- a full clone of the Bitcoin Core C++ codebase. This is for reading, studying, and cross-referencing. **DO NOT modify any file under this directory.** It has its own `.git` and is treated as an external dependency.
2. **Python wallet** (`bitcoin_wallet.py` and `constants.py` at the repo root, plus `blockchain_dev/bitcoin_wallet_dev/src/btc_wallet/`) -- key generation, addresses, HD keys, and an educational signer.
3. **Educational node** (`blockchain_dev/edu_node/src/edu_node/`) -- a small chain with proof of work, peers, and an HTTP API. It is not a Bitcoin clone.

**Current phase:** Phase 1, Phase 2, and Phase 3 code are in place. The security-scan line is met with one accepted exception: PYSEC-2026-1325 in `ecdsa`, which has no fix.

### Fleet Defaults: Dark Mode, Plain-English Communication, and Zero Lingering Ephemeral Files (Non-Negotiable)

- **Default theme (Dark mode):** Set dark mode as the default theme for every application that I build or plan to build. Apply dark mode on initial load across all web, mobile, desktop, browser-extension, CLI/TUI, and Streamlit interfaces. If an application includes a theme toggle, persist the user selection and default to dark mode when unset. Configure all charts, canvases, maps, and 3D scenes to use dark-mode surfaces and high-contrast foreground tokens by default.
- **Default communication style (Plain, approachable English — one step at a time):** Explain status updates, bugs, tools, verification steps, and decisions in clear, friendly everyday English — as if explaining to a newer programmer — even though I have years of engineering experience. Avoid dense jargon, unexplained internal shorthand or defect codes, and robotic/compressed ASD-STE100 prose. Walk through blockers, decisions, and multi-item checklists **one step at a time** rather than dumping everything at once, while keeping full technical accuracy and clickable file/line references. Follow another style only when I explicitly request it.
- **Zero lingering ephemeral files (`[v]` full-teardown cleanup protocol):** Never scatter ephemeral or runtime-generated objects and files (logs, PID/lock/ownership receipts, temp/scratch files, local caches, runtime state directories, test/probe outputs, containers, images, or volumes) loose inside the core file structure where I would have to manually determine which files are leftover from previous runs versus part of the core codebase. Isolate runtime-generated files under dedicated gitignored runtime/temp paths, clean up single-run transient files (PIDs, locks, sockets, scratch dirs) on normal stop, and ensure the launcher's **`[v]` (full cleanup / teardown)** option deletes **all** ephemeral and runtime-generated files, directories, caches, logs, containers, images, and volumes created from running the app so `[v]` restores a clean core file structure (`[k]`, `[q]`, and `[r]` preserve intended persistent data/volumes, and coding agents never invoke `[v]` without my explicit authorization).

</critical_context>

---

<project_identity>

## 1. Project Identity

- **Name:** Blockchain
- **Location:** `blockchain/`
- **Master plan:** `docs/BLOCKCHAIN_MASTER_PLAN.md`
- **Nature:** Educational/research -- learning blockchain internals by building
- **Active code:** `bitcoin_wallet.py`, `constants.py`, `blockchain_dev/bitcoin_wallet_dev/src/btc_wallet/`, and `blockchain_dev/edu_node/src/edu_node/`
- **Reference code:** `blockchain_dev/bitcoin_blockchain_dev/` (READ-ONLY)

</project_identity>

---

<phase_constraints>

## 2. Phase Constraints

### Phase 1: Python Wallet Basics (implemented)
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

**Still deferred:**
- Frontend / UI -- there is no web UI. The node API is dark-mode-ready only in the sense that it has no screens.
- A production database. Phase 2 stores the encrypted wallet in a file. Phase 3 stores the chain in `chain.json` on a Docker volume. Postgres is not used.

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
- **Python 3.13+**
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
- **Entropy sources:** `secrets.token_bytes()` and `os.urandom()` only.
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
├── Dockerfile                             # Educational node image
├── docker-compose.yml                     # edu-node on host port 8224
├── run_blockchain.sh                      # macOS/Linux launcher
├── run_blockchain.bat                     # Windows launcher
├── bitcoin_wallet.py                      # Phase 1 BitcoinWallet
├── constants.py                           # Phase 1 named values
└── blockchain_dev/
    ├── bitcoin_blockchain_dev/            # READ-ONLY Bitcoin Core clone (gitignored)
    ├── bitcoin_wallet_dev/src/btc_wallet/ # Phase 2 package, one class per file, flat
    └── edu_node/src/edu_node/             # Phase 3 educational node
```

### Key entrypoints
- `bitcoin_wallet.py` -- Phase 1 wallet. Run with `uv run python bitcoin_wallet.py`. Signing and broadcast of that path still use Bitcoin Core RPC.
- `blockchain_dev/bitcoin_wallet_dev/src/btc_wallet/` -- Phase 2 package. Flat modules, not the nested tree the master plan first sketched. The local signer is educational and is not used by `create_and_send_transaction`.
- `blockchain_dev/edu_node/src/edu_node/node_api.py` -- educational node. Importing it mines a chain under `EDU_CHAIN_DIR` or `.runtime/edu-chain`.
- `run_blockchain.bat` / `run_blockchain.sh` -- start the container. Host port `8224`, container port `8000`.
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

Phase 2 and Phase 3 also depend on `bech32`, `cryptography`, `mnemonic`, `fastapi`, and `uvicorn[standard]`. Those pins live in `pyproject.toml` and `uv.lock`.

</tech_stack>

---

<commands>

## 7. Local Commands

```bash
# Install runtime and test dependencies
uv sync --all-groups

# Run the wallet (requires Bitcoin Core running with RPC enabled)
uv run python bitcoin_wallet.py

# Run tests
uv run pytest

# Lint
uvx ruff check .
uvx ruff format --check .

# SAST (same set the CI `sast` job runs -- see section 9a)
uvx ruff check . && uvx semgrep scan --config auto --config p/owasp-top-ten --config p/python --severity ERROR --error && uv run --with pip-audit pip-audit --ignore-vuln PYSEC-2026-1325 && gitleaks detect --no-git --redact --config .gitleaks.toml
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

- **Released version:** `0.2.0` in `pyproject.toml`. Do not edit that field; the release workflow bumps it.
- **Changelog:** `docs/versions.md`. The unreleased heading is `0.2.1`. New notes go under that heading until `0.2.1` is released.
- Follows strict semver per global AGENTS.md section 6

</versioning>

---

<security>

## 9a. Security -- SAST Scanning & Injection Safety (Non-Negotiable)

Per global AGENTS.md section 19. This is a wallet: the attack surface is small, but every boundary touches private keys or signed transactions, so the bar is production-grade regardless of the "educational" label.

### SAST scanning
- **Wired.** `.github/workflows/ci.yml` (GitHub Actions -- public project) has a `sast` job (`needs: [lint]`) that fails on any HIGH/CRITICAL finding. When the `test` job lands it goes after `sast` (`needs: [sast]`) so the order stays `lint -> sast -> test -> docker-build`.
- Tools as wired: **CodeQL** (`github/codeql-action` init -> analyze, language `python`, category `codeql`); **Semgrep** via `uvx semgrep scan --config auto --config p/owasp-top-ten --config p/python --severity ERROR --error --sarif`, SARIF uploaded through `github/codeql-action/upload-sarif` (category `semgrep`, `if: !cancelled()`), with a separate step failing the job on findings; **gitleaks** via `gitleaks/gitleaks-action@v2` on a `fetch-depth: 0` checkout with `GITLEAKS_CONFIG: .gitleaks.toml` (default rules plus the 64-hex and WIF rules); **`pip-audit`** via `uv run --with pip-audit pip-audit --ignore-vuln PYSEC-2026-1325`. Job-level `permissions: contents: read, security-events: write, actions: read`. The `test` job is wired after `sast`.
- **ruff `S` rules** are wired: `pyproject.toml` lint select is `["E", "F", "I", "N", "UP", "ANN", "S"]`. `tests/**` ignores `S101` only. The one other suppression is an inline `# noqa: S603` on the Windows `icacls` call, with a written reason: the executable path is computed under `SystemRoot` and `shell` is false.
- **Trivy** is wired in the `docker-build` job (`aquasecurity/trivy-action@v0.36.0`, `exit-code` 1, severity `CRITICAL,HIGH`, `vuln-type` `os,library`, `ignore-unfixed` not set, `trivyignores: .trivyignore`). `.trivyignore` names CVE-2024-23342 and the Debian ids that have no fixed package. Any other high finding still fails the job. Project Semgrep rules in `.semgrep/` are still absent.
- Local reproduction (see section 7): `uvx ruff check . && uvx semgrep scan --config auto --config p/owasp-top-ten --config p/python --severity ERROR --error && uv run --with pip-audit pip-audit --ignore-vuln PYSEC-2026-1325 && gitleaks detect --no-git --redact --config .gitleaks.toml`.

### Injection safety -- input boundary inventory

| Boundary | Where | Injection classes | Required defense |
|---|---|---|---|
| RPC credentials file | `BitcoinWallet.get_rpc_credentials()` -- `rpc_credentials_file` ctor arg, `json.load`/`json.dump` | Path traversal, unsafe deserialization, secrets | Resolve path and require `resolved.is_relative_to(base.resolve())` (base = wallet directory); `json` only, never `pickle`; validate the decoded dict against a typed schema (`rpc_user`/`rpc_password` as `str`, nothing else) before use; file written with owner-only permissions; file stays gitignored. On Windows, `SystemRoot` must match `X:\Windows` and `USERNAME` must be a plain account name before `icacls` runs with `shell` false |
| RPC URL construction | `BitcoinWallet.connect_to_rpc()` -- `urlunsplit` of the fixed scheme, host, and port, with `quote(..., safe="")` on the user and password | Header/URL injection, SSRF, secrets | Percent-encode user and password (`urllib.parse.quote`) so `@`, `/`, `:`, CR/LF in a credential cannot rewrite the host; host/port are constants, never taken from the credentials file; credentials never echoed in logs or exceptions |
| Bitcoin Core JSON-RPC responses | `listunspent`, `createrawtransaction`, `signrawtransactionwithkey`, `sendrawtransaction` via `AuthServiceProxy` | Unsafe deserialization, resource exhaustion, log injection | Treat the node as untrusted: validate UTXO entries (`txid` 64-hex, `vout` int >= 0, `amount` `Decimal`) before arithmetic or re-submission; cap the number of UTXOs iterated; `JSONRPCException` messages are logged via structured logging with CR/LF stripped, never interpolated into a shell or a further RPC call |
| Send parameters | `create_and_send_transaction(recipient_address, amount)` and `__main__` | Input validation (address/amount), resource exhaustion | `recipient_address` must pass Base58Check decode + version-byte check (Bech32 validation added in Phase 2) before being placed in an output map; `amount` is `Decimal`, bounded `> 0` and `<= balance - fee`; never build the outputs dict from unvalidated strings |
| Error output | structured logging in every RPC wrapper | Secrets leakage, log injection | Exceptions never contain the private key or RPC password. Log text strips CR/LF and redacts the private key, RPC user, and RPC password. Sign errors log the method name only. |
| Entropy | `generate_private_key()` | Weak randomness (ruff `S311`) | `secrets.token_bytes` / `os.urandom` only. The `random.getrandbits` mix has been removed. |

Built boundaries:
- **Phase 2 mnemonic:** `MnemonicSeed` accepts only 12 or 24 English words from the `mnemonic` wordlist, checks the checksum before any seed is derived, and never logs the phrase. The extra passphrase is a string capped at 1024 characters.
- **Phase 2 wallet file:** AES-256-GCM via `cryptography`, with the file magic as additional data. The path must stay inside the wallet directory. Decrypt must authenticate before the plaintext is parsed. Owner-only permissions reuse the Phase 1 helper.
- **Phase 2 fee estimate:** `estimatesmartfee` blocks are an integer from 1 to 1008. The payload is parsed as a `Decimal` rate, finite, greater than 0, and at most 1 BTC per kvB. A truthy error list is rejected.
- **Phase 3 HTTP API:** Pydantic models use `extra=forbid`. `POST` and `PUT` and `PATCH` require a content-length of at most 64000 bytes. Page size is at most 50. CORS is an allowlist and falls back to `http://127.0.0.1:8224`. `*` is never allowed. The mine route does not accept a private key. Transaction errors return a generic message and do not echo the body. The websocket treats client text as a ping, not as instructions.
- **Phase 3 peers:** Loopback only, port chosen by the OS, magic `EDU1`, a length cap, a checksum, and per-connection byte and message caps. A bad block closes the peer. A bad transaction is dropped and the peer stays.
- **Phase 3 chain file:** JSON with one `blocks` key, a size cap, and a temp-file replace inside the store directory. The resolved path must stay in that directory.
- **Phase 3 script engine:** An allowlist of push, dup, hash160, equalverify, checksig, and checkmultisig. No `eval` or `exec`. Opcode count, stack size, and item size are capped.

### Project-specific additions
- `blockchain_dev/bitcoin_blockchain_dev/` (Bitcoin Core clone) is excluded from Semgrep/gitleaks paths -- it is read-only reference material, not project code, and is gitignored.
- Private keys are the highest-value secret in the repo. `.gitleaks.toml` adds a 64-hex rule and a WIF rule, and CI passes that file as `GITLEAKS_CONFIG`. The 64-hex rule uses word boundaries because this scanner's regex engine rejects lookaround; a 66-hex public key does not match. The path allowlist covers `uv.lock` package hashes, the virtualenv, bytecode caches, and `.runtime` test output. A test-vector key is allowed only on its own line with `# gitleaks:allow` and the published source of the vector.
- Never send a mainnet transaction from CI or from a test. Tests mock `AuthServiceProxy`; the `sast` job has no network access to a node.

The task-completion self-audit (section 11) now includes a **Security check** item.

</security>

---

<definition_of_done>

## 10. Phase Completion Gate -- Phase 1

Phase 1 is done when:
- [x] `bitcoin_wallet.py` has full type annotations
- [x] `from __future__ import annotations` at top of every module
- [x] All functions have docstrings documenting parameters and return types
- [x] pytest test suite exists with tests for: key generation, public key derivation, address generation
- [x] Tests use known Bitcoin test vectors for validation
- [x] No magic numbers -- fee, network byte, etc. extracted to named constants
- [x] ruff passes cleanly (including `S` rules)
- [x] SAST green, with one accepted exception: PYSEC-2026-1325 in `ecdsa` (`--ignore-vuln` in CI) and the Debian ids in `.trivyignore`. Any other HIGH/CRITICAL finding still fails the job.
- [x] All input boundaries injection-safe and documented in `<security>` (section 9a)
- [x] `docs/status.md` and `docs/versions.md` are current
- [x] README.md accurately describes the project and how to run it

The accepted exception is PYSEC-2026-1325, reported twice for the same `ecdsa` 0.19.2 bug. The maintainers will not fix it. CI passes `--ignore-vuln PYSEC-2026-1325`, and `.trivyignore` names that CVE plus the Debian ids with no fixed package. Any other high finding still fails. Phase 1 send still asks Bitcoin Core to sign. The educational signer is not on that path. CodeQL runs in GitHub Actions and was not run here.

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