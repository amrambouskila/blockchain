# Version History

## v0.1.2
- Security documentation added:
  - `<security>` section in CLAUDE.md / AGENTS.md -- SAST stage requirement (`sast` job between `lint` and `test` in `.github/workflows/ci.yml`), input-boundary inventory with injection classes and required defenses, ruff `S` rules in the required lint select
  - Security section and per-phase SAST gate lines in `docs/BLOCKCHAIN_MASTER_PLAN.md`
  - `.codex/commands/pre-commit.md` gains a SAST audit step and a SAST row in the verdict table
  - `docs/status.md` gains a Security section (rewritten below into Wired / Pending once the wiring landed in this same version)
- Security wiring (patch: CI/lint configuration only, no runtime behavior change in `bitcoin_wallet.py`):
  - `.github/workflows/ci.yml` gains a `sast` job (`needs: [lint]`, `permissions: contents: read / security-events: write / actions: read`): CodeQL init+analyze (python), `uvx semgrep scan --config auto --config p/owasp-top-ten --config p/python --severity ERROR --error` with SARIF upload via `codeql-action/upload-sarif` and a fail-on-findings step, `gitleaks/gitleaks-action@v2` on a full-depth checkout, and `uv run --with pip-audit pip-audit`. (The audit step was initially written as `uvx pip-audit`, which audits pip-audit's own isolated tool environment rather than the project's dependencies. This repo declares no dependencies today, so both forms report the same result -- the corrected form keeps the audit meaningful once dependencies land.)
  - `pyproject.toml` ruff lint select gains `"S"` (flake8-bandit); tree is clean with no `noqa`
  - No Trivy (no Dockerfile exists yet); no custom gitleaks private-key rule yet; no `.semgrep/` project rules yet
  - Docs reconciled: CLAUDE.md / AGENTS.md `<security>`, master plan Security section and Phase 1 task 8, `.codex/commands/pre-commit.md`, `docs/status.md`

## v0.1.0
- Initial project scaffold
- Existing `BitcoinWallet` class with key generation, public key derivation, address generation, and RPC-based transaction operations
- Project documentation: CLAUDE.md, BLOCKCHAIN_MASTER_PLAN.md, status.md, versions.md
- .claude infrastructure: settings.json, commands (review, pre-commit, validate), skills (phase-awareness)
- .gitignore configured (Bitcoin Core reference directory excluded)