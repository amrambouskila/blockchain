"""The process entrypoint opens the chain directory from the environment."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest


def test_build_app_uses_the_environment_or_the_runtime_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing setting uses .runtime/edu-chain, and EDU_CHAIN_DIR replaces it."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("EDU_CHAIN_DIR", raising=False)
    import edu_node.node_api as node_api

    node_api.app.state.node.close()
    importlib.reload(node_api)
    try:
        assert (tmp_path / ".runtime" / "edu-chain" / "chain.json").is_file()
        node_api.app.state.node.close()
        explicit = tmp_path / "explicit-chain"
        monkeypatch.setenv("EDU_CHAIN_DIR", str(explicit))
        importlib.reload(node_api)
        assert (explicit / "chain.json").is_file()
    finally:
        node_api.app.state.node.close()
