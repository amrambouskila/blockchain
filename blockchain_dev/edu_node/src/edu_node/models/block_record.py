"""One block in an API response."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class BlockRecord(BaseModel):
    """A canonical block's height, display id, and raw hex."""

    model_config = ConfigDict(extra="forbid")

    height: int
    block_id: str
    raw_hex: str
