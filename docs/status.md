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

## Security

### Verified state (2026-08-24)

- **Semgrep: clean.** Verified locally by running this repo's own CI command against the working tree (0 findings). The invocation itself was broken before today — `semgrep ci` rejects `--severity`/`--error` and exited 2 without scanning.

- Not run locally: gitleaks and Trivy are not part of any project toolchain here; both were exercised through their official images during verification, and CI runs them on every pipeline.
- Security requirements are documented in CLAUDE.md / AGENTS.md `<security>` (section 9a) and the master plan's Security section; every phase gate now requires a green SAST stage and documented injection-safe input boundaries.
- Wired:
  - `sast` job in `.github/workflows/ci.yml` (`needs: [lint]`): CodeQL (python), Semgrep (`uvx semgrep scan`, `auto` + `p/owasp-top-ten` + `p/python`, severity ERROR, SARIF uploaded to code scanning), `gitleaks/gitleaks-action@v2`, `uv run --with pip-audit pip-audit`
  - ruff `S` (flake8-bandit) family in `pyproject.toml` lint select; ruff clean, no `noqa`
- Pending:
  - `test` job chained after `sast` (no test suite yet, so no `S101` per-file ignore under `tests/` yet)
  - Custom gitleaks rule for 64-hex / WIF private keys (`.gitleaks.toml`); `.semgrep/` project rules
  - Trivy in `docker-build` once a Dockerfile exists (Phase 2+)
  - Local Semgrep/gitleaks runs: not executed on this machine yet; gitleaks needs a local binary install
  - Phase 1 boundary fixes from the inventory: path-containment check on `rpc_credentials_file`, percent-encoded RPC URL credentials, typed validation of RPC responses and send parameters, `logging` instead of `print` for errors, removal of the `random.getrandbits` entropy mix (`S311`)

## What's Next
- Add type annotations and `from __future__ import annotations` to `bitcoin_wallet.py`
- Extract magic numbers to named constants
- Create pytest test suite with Bitcoin test vectors for key-to-address derivation
- Add ruff configuration