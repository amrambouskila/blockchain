"""Pytest setup for wallet tests. Runtime reports stay under .runtime/."""

from __future__ import annotations

from pathlib import Path

import pytest

RUNTIME_DIRECTORY = Path(__file__).resolve().parent.parent / ".runtime"
RUNTIME_DIRECTORY.mkdir(exist_ok=True)


def pytest_configure(config: pytest.Config) -> None:
    """Create the gitignored directory that holds coverage and JUnit output."""
    del config
    RUNTIME_DIRECTORY.mkdir(exist_ok=True)


@pytest.fixture(autouse=True)
def wallet_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point credential files at a temporary directory."""
    monkeypatch.setattr("bitcoin_wallet.WALLET_DIRECTORY", tmp_path)
    return tmp_path
