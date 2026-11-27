from contextlib import closing

import pytest
import uvicorn
from fastapi.testclient import TestClient

from synapse.api.app import app
from synapse.main import run_full


@pytest.mark.asyncio
async def test_local_launch_opens_with_no_key_and_rejects_nonlocal_requests(monkeypatch):
    import synapse.api.routes.integrations as integrations

    monkeypatch.setenv("SYNAPSE_API_KEY", "legacy-launcher-key")
    monkeypatch.setattr(integrations, "_opencode_payload", lambda: {"status": "available"})
    app.state.rate_limiter.reset()

    async def serve(server):
        assert server.config.proxy_headers is False
        root = "http://127.0.0.1:8000"
        with closing(TestClient(server.config.app, base_url=root, client=("127.0.0.1", 51000))) as client:
            assert client.get("/api/v1/runtime-info").json()["api_auth_required"] is False
            assert client.get("/api/v1/integrations/opencode").status_code == 200
            assert client.get("/api/v1/integrations/opencode", headers={
                "host": "outside.example",
            }).status_code == 403
            assert client.get("/api/v1/integrations/opencode", headers={
                "origin": "http://localhost:8080",
            }).status_code == 403
            assert client.get("/api/v1/integrations/opencode", headers={
                "x-forwarded-for": "192.0.2.1",
            }).status_code == 403
            assert client.get("/api/v1/integrations/opencode", headers={
                "sec-fetch-site": "cross-site",
            }).status_code == 403
            with client.websocket_connect("ws://127.0.0.1:8000/ws", headers={"origin": root}) as ws:
                ws.send_json({"local": True})
                assert ws.receive_json()["data"] == {"local": True}
        with closing(TestClient(server.config.app, base_url=root, client=("192.0.2.1", 51000))) as client:
            assert client.get("/api/v1/integrations/opencode").status_code == 403

    monkeypatch.setattr(uvicorn.Server, "serve", serve)
    await run_full()


@pytest.mark.asyncio
async def test_network_listener_refuses_start_without_key(monkeypatch):
    monkeypatch.delenv("SYNAPSE_API_KEY", raising=False)

    async def serve(_server):
        pytest.fail("network server started without a key")

    monkeypatch.setattr(uvicorn.Server, "serve", serve)
    with pytest.raises(ValueError, match="SYNAPSE_API_KEY"):
        await run_full(host="0.0.0.0")



@pytest.mark.asyncio
async def test_explicitly_protected_loopback_still_requires_key(monkeypatch):
    monkeypatch.setenv("SYNAPSE_API_KEY", "protected-launch-test")
    app.state.rate_limiter.reset()

    async def serve(server):
        root = "http://127.0.0.1:8000"
        with closing(TestClient(server.config.app, base_url=root, client=("127.0.0.1", 51000))) as client:
            result = client.get("/api/v1/runtime-info")
            assert result.status_code == 401
            result = client.get("/api/v1/runtime-info", headers={"x-api-key": "protected-launch-test"})
            assert result.status_code == 200
            assert result.json()["api_auth_required"] is True

    monkeypatch.setattr(uvicorn.Server, "serve", serve)
    await run_full(require_api_key=True)
