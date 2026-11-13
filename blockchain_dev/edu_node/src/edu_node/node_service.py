"""HTTP and websocket routes for one educational node."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from edu_node.body_limit import BodyLimit
from edu_node.models.block_list import BlockList
from edu_node.models.block_record import BlockRecord
from edu_node.models.mine_result import MineResult
from edu_node.models.tip_view import TipView
from edu_node.models.transaction_body import TransactionBody
from edu_node.node_constants import (
    BLOCK_ERROR,
    DEFAULT_ORIGIN,
    DEFAULT_PAGE_SIZE,
    MAX_ORIGIN_LENGTH,
    MAX_PAGE_SIZE,
    TX_ERROR,
)
from edu_node.node_host import NodeHost


def create_app(node: NodeHost, origins: list[str]) -> FastAPI:
    """Return the API for node. The browser origin list never includes '*'."""
    app = FastAPI(title="Educational chain")
    app.state.node = node
    app.add_middleware(BodyLimit)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins(origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["content-type"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        """Report that the process is answering."""
        return {"status": "ok"}

    @app.get("/tip", response_model=TipView)
    def tip() -> TipView:
        """Return the current tip."""
        height, block_id, work = node.tip()
        return TipView(height=height, block_id=block_id, work=work)

    @app.get("/blocks", response_model=BlockList)
    def blocks(
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    ) -> BlockList:
        """Return one page of the canonical chain."""
        records = [
            BlockRecord(height=height, block_id=block.display_id, raw_hex=block.raw.hex())
            for height, block in node.page(offset, limit)
        ]
        return BlockList(offset=offset, blocks=records)

    @app.get("/blocks/{height}", response_model=BlockRecord)
    def block(height: int) -> BlockRecord:
        """Return one block, or 404 when that height is not on the canonical chain."""
        try:
            found = node.block_at(height)
        except KeyError:
            raise HTTPException(status_code=404, detail=BLOCK_ERROR) from None
        return BlockRecord(height=height, block_id=found.display_id, raw_hex=found.raw.hex())

    @app.post("/transactions")
    def transactions(body: TransactionBody) -> dict[str, str]:
        """Accept a raw transaction. Failures use one generic message."""
        try:
            txid = node.submit(body.raw_hex)
        except ValueError:
            raise HTTPException(status_code=400, detail=TX_ERROR) from None
        return {"txid": txid}

    @app.post("/mine", response_model=MineResult)
    def mine() -> MineResult:
        """Mine with the node's in-memory key. The request cannot supply a private key."""
        block = node.mine()
        return MineResult(block_id=block.display_id, height=node.tip()[0])

    @app.websocket("/events")
    async def events(socket: WebSocket) -> None:
        """Send the tip on connect and again after any client text. The text is not a command."""
        await socket.accept()
        await socket.send_json(_tip_payload(node))
        try:
            while True:
                await socket.receive_text()
                await socket.send_json(_tip_payload(node))
        except WebSocketDisconnect:
            return

    return app


def _allowed_origins(origins: list[str]) -> list[str]:
    """Drop '*' and over-long origins. An empty result uses the local default."""
    allowed = [origin for origin in origins if origin != "*" and len(origin) <= MAX_ORIGIN_LENGTH]
    if not allowed:
        return [DEFAULT_ORIGIN]
    return allowed


def _tip_payload(node: NodeHost) -> dict[str, int | str]:
    """Return the tip fields sent on the websocket."""
    height, block_id, work = node.tip()
    return {"height": height, "block_id": block_id, "work": work}
