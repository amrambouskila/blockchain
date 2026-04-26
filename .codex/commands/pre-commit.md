---
name: pre-commit
description: Read-only pre-commit audit -- tests, lint, crypto safety, docs check
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

### Step 2: Test Suite
```
Run: pytest tests/ -v --cov (if tests exist)
```
Report: PASS/FAIL, coverage percentage

### Step 3: Crypto Safety Audit
For every modified Python file (check `git diff --name-only`):
- No private keys in print/log/error statements
- No `random` module used for cryptographic entropy (only `secrets` / `os.urandom`)
- No custom crypto algorithms introduced
- All ECDSA operations use `ecdsa` library with `SECP256k1` curve
- Base58Check encoding uses `base58` library (not hand-rolled)

### Step 4: Reference Isolation
- Verify NO files under `bitcoin_blockchain_dev/` appear in `git diff`
- Verify NO files under `bitcoin_blockchain_dev/` appear in `git status` (staged or unstaged)

### Step 5: Credential Check
- No RPC credentials in any committed file
- `rpc_credentials.json` is gitignored
- No private keys in any committed file
- `.env` files are gitignored

### Step 6: Test Vector Validation
- If crypto operations were added/modified, at least one test uses known Bitcoin test vectors
- Key derivation tests match published secp256k1 test cases
- Address generation tests match known Bitcoin addresses

### Step 7: Documentation
- `docs/status.md` reflects current state
- `docs/versions.md` updated with changes (semver computed per global AGENTS.md section 6)

### Step 8: Unified Report
```
=== PRE-COMMIT REPORT ===

Lint:              PASS/FAIL
Tests:             PASS/FAIL (N% coverage)
Crypto Safety:     PASS/FAIL
Reference Isolation: PASS/FAIL
Credentials:       PASS/FAIL
Test Vectors:      PASS/FAIL (N vectors validated)
Docs:              Updated: YES/NO

VERDICT: READY TO COMMIT / NOT READY (list blockers)
```