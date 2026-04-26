---
name: review
description: Deep review of code changes against Blockchain project standards
---

# Code Review

Deep review of changes against Blockchain project standards and crypto safety rules.

## Instructions

Before anything else:
1. Re-read `AGENTS.md` sections 3 (Architecture & Code Rules) and 4 (Directory Structure).
2. Re-read `docs/BLOCKCHAIN_MASTER_PLAN.md` for current phase scope.
3. Confirm the review scope with the user.

### Review Checklist

For every modified file (check `git diff --name-only`):

1. **Reference Isolation**: No files under `bitcoin_blockchain_dev/` were modified.
2. **Type Safety**: Full type annotations on all functions. No `Any`. `from __future__ import annotations` present.
3. **Crypto Safety**:
   - No private keys in logs, print statements, or error messages
   - Entropy from `secrets` / `os.urandom` only (not `random` alone)
   - No custom cryptographic algorithms -- only audited libraries
   - Signature encoding matches Bitcoin specification (DER for ECDSA)
4. **No Magic Numbers**: Network bytes, fees, curve parameters, BIP constants all named.
5. **Error Handling**: Specific exception types. No bare `except:`. No swallowed exceptions.
6. **RPC Credentials**: Not hard-coded, not committed, loaded from gitignored file or env vars.
7. **Test Coverage**: New logic has corresponding tests. Crypto operations validated against known test vectors.
8. **Documentation**: Docstrings present. `docs/status.md` and `docs/versions.md` updated if applicable.
9. **Dead Code**: No commented-out blocks, unused imports, or unused functions.
10. **Phase Scope**: Changes are within the current phase's scope per AGENTS.md section 2.

### Report Format
```
=== REVIEW REPORT ===

CRITICAL (must fix before commit):
- [file:line] Issue description

RECOMMENDED (should fix):
- [file:line] Issue description

POSITIVE PATTERNS:
- What was done well

VERDICT: APPROVED / CHANGES REQUESTED
```