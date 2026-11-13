"""The chain tip returned by the API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class TipView(BaseModel):
    """Height, display id, and total work of the current tip."""

    model_config = ConfigDict(extra="forbid")

    height: int
    block_id: str
    work: int
