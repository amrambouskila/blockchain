# Status

## Current State
**Phase:** Phase 3 educational node is implemented, and Phase 2 wallet code is in place. The written SAST line on every phase is still open.
**Released version:** 0.2.0 in `pyproject.toml`
**Changelog head:** unreleased 0.2.1 in `docs/versions.md`

## What Exists
- Phase 1 stays at the repo root: `bitcoin_wallet.py` and `constants.py`. `create_and_send_transaction` still asks Bitcoin Core at `127.0.0.1:8332` to sign and broadcast. Tests mock that RPC client and never touch mainnet.
- Phase 2 lives in the flat package `blockchain_dev/bitcoin_wallet_dev/src/btc_wallet/`. It covers BIP-32, BIP-39 (12 or 24 English words), BIP-44, Bech32 and Bech32m, a P2SH multisig script, AES-256-GCM wallet files, coin selection, fee-estimate parsing, and a local educational signer. That signer is not used on the Phase 1 send path.
- Phase 3 lives in `blockchain_dev/edu_node/src/edu_node/`. It is a small chain, not a Bitcoin clone: 80-byte headers, double-SHA256 proof of work, a short script allowlist, a mempool, loopback peers, and a FastAPI app. The chain file is `chain.json`. Docker stores it on the named volume `edu_chain`. There is no Postgres.
- `uv run pytest` passed on this machine: 453 tests, coverage 100% on `bitcoin_wallet`, `constants`, `btc_wallet`, and `edu_node`.
- GitHub Actions runs lint, then sast, then test (JUnit), then `docker-build` with Trivy. The image was built on this machine as `blockchain-edu-node:ci`. A short run returned health 200 and a genesis tip, and the container was removed.

## Decisions that differ from the first plan
- **Signing.** Phase 1 send stays on Bitcoin Core. The educational signer uses `ecdsa` `sign_digest_deterministic`. That is the timing-sensitive call named by the open advisory, and it is not on the hot send path.
- **Storage.** The encrypted wallet is a file, not Postgres. The chain is `chain.json` on a Docker volume, not Postgres.
- **Layout.** Phase 2 is a flat package, one class per file. It is not the nested `keys/` `address/` `wallet/` tree sketched in the master plan.
- **Multisig.** Tests check the script bytes and the P2SH address. They do not call Bitcoin Core `verifymessage`.
- **Chain choice.** The tip is the chain with the most work. Equal work keeps the first tip. Coinbase outputs can be spent in the next block. A new tip is announced by sending the whole chain, not only the new block.

## What's Next
The code for all three phases is in place. The security-scan box stays open. `pip-audit` and Trivy both still report CVE-2024-23342 (PYSEC-2026-1325) in `ecdsa` 0.19.2, and there is no fixed release. Trivy also reports Debian 13 packages that have no fix yet: util-linux, ncurses, sqlite, systemd, acl, and perl. The ids are in `docs/versions.md`. Do not ignore those findings, and do not swap `ecdsa` unless you decide to. CodeQL runs in GitHub Actions and was not run here. `PROJECT_DOCUMENTATION.html` is stale: it still describes the older layout and version. There is no web UI.

## Security
- ruff, including its security rules, is clean. Semgrep at error severity is clean on the tracked tree. The untracked wallet and node source was copied outside the git tree and scanned the same way: 39 Python files, no findings. Semgrep's default ignore skips `tests/`. gitleaks is clean.
- `pip-audit` is not clean, for the `ecdsa` advisory above. That is why the SAST boxes stay unchecked.
- Host port `8224` is registered in `PORT_ASSIGNMENTS.md` for the educational node. Peers are not published.
