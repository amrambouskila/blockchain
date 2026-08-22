---
name: pre-commit
description: Read-only pre-commit audit -- lint, SAST, tests, crypto safety, docs check
---

# Pre-Commit Alignment Gate

Run this before every commit to verify all changes meet project standards. **This command NEVER stages or commits anything** -- it only reports. The user runs git commands themselves.

## Instructions

Before anything else:
1. Re-read `AGENTS.md` in full.
2. Re-read `docs/BLOCKCHAIN_MASTER_PLAN.md` for current phase context.

### Step 1: Lint Check
```
Run: ruff check blockchain_dev/ (if ruff config exists)
```
Report: PASS/FAIL

### Step 2: SAST Audit
```
Run: uvx ruff check . && uvx semgrep scan --config auto --config p/owasp-top-ten --config p/python --severity ERROR --error && uv run --with pip-audit pip-audit && gitleaks detect --no-git --redact
```
(the same set the wired CI `sast` job runs; gitleaks needs a local binary install -- see `AGENTS.md` section 9a; `blockchain_dev/bitcoin_blockchain_dev/` is excluded)
- Zero HIGH/CRITICAL findings; every MEDIUM finding has a written justification
- Every input boundary touched by the diff names its injection class(es) and defense in `AGENTS.md` `<security>`
Report: PASS/FAIL, finding counts by severity

### Step 3: Test Suite
```
Run: pytest tests/ -v --cov (if tests exist)
```
Report: PASS/FAIL, coverage percentage

### Step 4: Crypto Safety Audit
For every modified Python file (check `git diff --name-only`):
- No private keys in print/log/error statements
- No `random` module used for cryptographic entropy (only `secrets` / `os.urandom`)
- No custom crypto algorithms introduced
- All ECDSA operations use `ecdsa` library with `SECP256k1` curve
- Base58Check encoding uses `base58` library (not hand-rolled)

### Step 5: Reference Isolation
- Verify NO files under `bitcoin_blockchain_dev/` appear in `git diff`
- Verify NO files under `bitcoin_blockchain_dev/` appear in `git status` (staged or unstaged)

### Step 6: Credential Check
- No RPC credentials in any committed file
- `rpc_credentials.json` is gitignored
- No private keys in any committed file
- `.env` files are gitignored

### Step 7: Test Vector Validation
- If crypto operations were added/modified, at least one test uses known Bitcoin test vectors
- Key derivation tests match published secp256k1 test cases
- Address generation tests match known Bitcoin addresses

### Step 8: Documentation
- `docs/status.md` reflects current state
- `docs/versions.md` updated with changes (semver computed per global AGENTS.md section 6)

### Step 9: Unified Report
```
=== PRE-COMMIT REPORT ===

Lint:              PASS/FAIL
SAST:              PASS/FAIL (H/C: 0, M triaged: N)
Tests:             PASS/FAIL (N% coverage)
Crypto Safety:     PASS/FAIL
Reference Isolation: PASS/FAIL
Credentials:       PASS/FAIL
Test Vectors:      PASS/FAIL (N vectors validated)
Docs:              Updated: YES/NO

VERDICT: READY TO COMMIT / NOT READY (list blockers)
```