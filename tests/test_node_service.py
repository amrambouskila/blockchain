"""HTTP and websocket routes for one educational node."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from edu_node.node_constants import BLOCK_ERROR, DEFAULT_ORIGIN, GENESIS_TIME, TX_ERROR
from edu_node.node_host import NodeHost
from edu_node.node_service import create_app
from tests.chain_blocks import ChainBlocks

_KEY = f"{1:064x}"


def _clock() -> int:
    """Return the timestamp used while this API test mines."""
    return GENESIS_TIME


def test_routes_read_the_chain_and_do_not_echo_a_bad_transaction(tmp_path: Path) -> None:
    """Health, pages, a payment, mining, the websocket, and the origin list all answer."""
    node = NodeHost.open(tmp_path / "api", _KEY, clock=_clock)
    try:
        app = create_app(node, ["*", DEFAULT_ORIGIN, "z" * 201])
        with TestClient(app) as client:
            assert client.get("/health").json() == {"status": "ok"}
            assert client.get("/tip").json()["height"] == 0
            page = client.get("/blocks").json()
            assert page["offset"] == 0
            assert len(page["blocks"]) == 1
            height_zero = client.get("/blocks/0")
            assert height_zero.status_code == 200
            assert height_zero.json()["height"] == 0
            missing = client.get("/blocks/9")
            assert missing.status_code == 404
            assert missing.json()["detail"] == BLOCK_ERROR
            rejected = client.post("/transactions", json={"raw_hex": "00"})
            assert rejected.status_code == 400
            assert rejected.json()["detail"] == TX_ERROR
            assert client.post("/transactions", json={"raw_hex": "aa", "extra": 1}).status_code == 422
            coin = node.block_at(0).transactions[0]
            payment = ChainBlocks().spend(_KEY, coin, 0, coin.outputs[0][0] - 500, coin.outputs[0][1])
            accepted = client.post("/transactions", json={"raw_hex": payment.raw.hex()})
            assert accepted.json()["txid"] == payment.display_id
            with client.websocket_connect("/events") as socket:
                assert socket.receive_json()["height"] == 0
                socket.send_text("hello")
                assert socket.receive_json()["block_id"]
            allowed = client.get("/health", headers={"origin": DEFAULT_ORIGIN})
            assert allowed.headers["access-control-allow-origin"] == DEFAULT_ORIGIN
            assert "access-control-allow-origin" not in client.get("/health", headers={"origin": "*"}).headers
            mined = client.post("/mine")
            assert mined.status_code == 200
            assert mined.json()["height"] == 1
            assert client.get("/blocks", params={"offset": 5, "limit": 1}).json()["blocks"] == []
            assert len(node.block_at(1).transactions) == 2
        fallback = create_app(node, [])
        with TestClient(fallback) as client:
            response = client.get("/health", headers={"origin": DEFAULT_ORIGIN})
            assert response.headers["access-control-allow-origin"] == DEFAULT_ORIGIN
    finally:
        node.close()
