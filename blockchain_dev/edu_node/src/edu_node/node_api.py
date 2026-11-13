"""The process entrypoint. The chain directory defaults to .runtime/edu-chain."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI

from edu_node.node_constants import DEFAULT_ORIGIN
from edu_node.node_host import NodeHost
from edu_node.node_service import create_app


def build_app() -> FastAPI:
    """Open the chain directory from EDU_CHAIN_DIR and return the API."""
    raw_dir = os.environ.get("EDU_CHAIN_DIR", os.path.join(".runtime", "edu-chain"))
    node = NodeHost.open(Path(raw_dir))
    return create_app(node, [DEFAULT_ORIGIN])


app = build_app()
