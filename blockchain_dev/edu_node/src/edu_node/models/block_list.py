"""A page of canonical blocks."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from edu_node.models.block_record import BlockRecord


class BlockList(BaseModel):
    """Blocks from one offset forward."""

    model_config = ConfigDict(extra="forbid")

    offset: int
    blocks: list[BlockRecord]
