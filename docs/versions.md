# Version History

## v0.2.1 — 2026-08-24 (unreleased)

### Phase 2 wallet and Phase 3 educational node (2026-11-13)

- The dependency audit ignores only PYSEC-2026-1325. That id is `ecdsa` 0.19.2, reported twice, and the maintainers will not fix it. `.trivyignore` names CVE-2024-23342 and the Debian ids that have no fixed package. `ignore-unfixed` stays off, so a new high finding still fails the image scan.

- Phase 2 is the flat package `btc_wallet`: BIP-32, BIP-39, BIP-44, Bech32 and Bech32m, P2SH multisig checked by script bytes, AES-256-GCM wallet files, coin selection, fee-estimate parsing, and an educational signer. Phase 1 `create_and_send_transaction` still signs through Bitcoin Core.
- Phase 3 is `edu_node`: proof of work, a script allowlist, a mempool, loopback peers, and a FastAPI app. The tip is the chain with the most work, and equal work keeps the first tip. Coinbase outputs spend in the next block. A new tip sends the whole chain.
- The chain is `chain.json` on the Docker volume `edu_chain`, not Postgres. Host port `8224` maps to container port `8000`. Launchers are `run_blockchain.sh` and `run_blockchain.bat`. `[r]` restarts without deleting images. `[v]` also deletes host `.runtime`.
- CI gains a `docker-build` job with Trivy `aquasecurity/trivy-action@v0.36.0` (severity CRITICAL,HIGH, exit code 1, `ignore-unfixed` not set). The image `blockchain-edu-node:ci` was built here. The runtime stage drops the base image's `pip`, which was carrying fixable copies of `certifi`, `msgpack`, `urllib3`, and an old `setuptools` listing. `GET /health` returned 200. That scan, before `.trivyignore` existed, exited 1. `ecdsa` CVE-2024-23342 has no fix. Debian 13 high findings also have no fixed package: util-linux CVE-2026-76642, CVE-2026-78408, CVE-2026-78409, and CVE-2026-78410; ncurses CVE-2025-69720; sqlite CVE-2026-119373, CVE-2026-119374, and CVE-2026-119379; systemd CVE-2026-16742; acl CVE-2026-54369; perl CVE-2026-9538.
- pytest: 453 passed, 100% coverage on the wallet, constants, `btc_wallet`, and `edu_node`. ruff and gitleaks are clean. Semgrep at error severity is clean on tracked files, and a copy of the untracked wallet and node source scanned outside the git tree (39 Python files) also had no findings. Semgrep skips `tests/` by its default ignore. Before the ignore flag, `pip-audit` reported unfixed PYSEC-2026-1325 in `ecdsa` 0.19.2, twice, and the SAST line was still open. The first bullet of this subsection is the current rule. `pyproject.toml` remains `0.2.0`.

### Phase 1 wallet gate (2026-11-13)

- Named constants live in `constants.py`. The wallet stays at the repo root as `bitcoin_wallet.py`.
- Private keys come from `secrets` and `os.urandom` only, and must sit inside the secp256k1 order.
- Send amounts are `Decimal`. RPC failures raise `BitcoinCoreResponseError` instead of returning 0 or None. `create_and_send_transaction` returns the transaction id. The demo script prints the address and balance and does not send.
- Credential paths, RPC URLs, UTXO rows, recipient addresses, and error text are checked at the boundaries in AGENTS.md section 9a.
- pytest covers published key-to-address vectors with a mocked RPC client. CI runs that suite after `sast` and publishes JUnit.
- `.gitleaks.toml` flags 64-hex and WIF secrets. The 64-hex rule uses word boundaries, because this scanner's regex engine rejects lookaround. The path allowlist covers `uv.lock`, the virtualenv, bytecode caches, and `.runtime`.
- Windows credential permissions accept `SystemRoot` only when it is `X:\Windows`, and accept `USERNAME` only when it is a plain account name. At this point `pip-audit` still reported unfixed PYSEC-2026-1325 in `ecdsa` 0.19.2, so the SAST gate item was still open. The accepted exception is the first bullet under the Phase 2 and Phase 3 subsection.

`Decimal` amounts and the new exceptions change behavior. These notes stay under `v0.2.1` because that heading was already the unreleased entry. A minor bump at release time is reasonable. `pyproject.toml` remains `0.2.0` until the release workflow bumps it.

### CI hardening + dependency remediation (2026-08-24)

- **Semgrep invocation corrected.** The job used `semgrep ci` with `--severity` and `--error`, which that subcommand does not accept — it exits 2 with a usage error before scanning. Switched to `semgrep scan`, which supports both.
- **Release workflow hardened against script injection.** `${{ inputs.bump }}` and `${{ steps.bump.outputs.new_version }}` were interpolated directly into `run:` blocks, where the value becomes shell code. Both now pass through `env:` and are read as quoted shell variables. The input is `type: choice`, so this was not exploitable today — it is the pattern that breaks the moment the input type changes.

---

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