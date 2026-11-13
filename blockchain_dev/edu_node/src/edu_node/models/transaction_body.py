"""A raw transaction submitted as hex."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from edu_node.node_constants import MAX_TX_HEX


class TransactionBody(BaseModel):
    """Hex for one transaction. Extra fields are rejected."""

    model_config = ConfigDict(extra="forbid")

    raw_hex: str = Field(min_length=1, max_length=MAX_TX_HEX)
