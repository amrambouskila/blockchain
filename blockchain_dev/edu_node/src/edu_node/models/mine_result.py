"""The block a local mine call produced."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class MineResult(BaseModel):
    """Display id and height of a newly mined block."""

    model_config = ConfigDict(extra="forbid")

    block_id: str
    height: int
