"""Pairing, revocation and dashboard security checks."""
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from deviceshare.hub import create_app

API_KEY = "long-admin-key-for-tests-only"

def test_paired_agent_cannot_be_hijacked(tmp_path):
    app = create_app(store_path=str(tmp_path / "db.sqlite"), api_key=API_KEY)
    headers = {"X-API-Key": API_KEY}
    with TestClient(app) as client:
        assert client.get("/v1/agents").status_code == 401
        initial = client.get("/v1/agents", headers=headers)
        assert initial.status_code == 200
        assert initial.json() == []
        issued = client.post("/v1/agents/station-01/credential", headers=headers)
        assert issued.status_code == 200
        token = issued.json()["token"]
        assert len(token) >= 32
        assert token not in str(app.state.store.list_agent_credentials())
        assert client.get("/v1/agents", headers=headers).json()[0]["credential_status"] == "paired"

        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/v1/agents/station-01/ws",
                                          headers={"X-Agent-Token": "invalid"}):
                pass
        with client.websocket_connect("/v1/agents/station-01/ws",
                                      headers={"X-Agent-Token": token}) as websocket:
            websocket.send_json({"type": "inventory", "devices": []})
            assert client.get("/v1/agents", headers=headers).json()[0]["online"] is True

        rotated = client.post("/v1/agents/station-01/credential", headers=headers)
        assert rotated.status_code == 200
        next_token = rotated.json()["token"]
        assert next_token != token
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/v1/agents/station-01/ws",
                                          headers={"X-Agent-Token": token}):
                pass
        with client.websocket_connect("/v1/agents/station-01/ws",
                                      headers={"X-Agent-Token": next_token}) as websocket:
            websocket.send_json({"type": "inventory", "devices": []})
        revoked = client.delete("/v1/agents/station-01/credential", headers=headers)
        assert revoked.json() == {"agent_id": "station-01", "revoked": True}
        assert client.get("/v1/agents", headers=headers).json()[0]["credential_status"] == "revoked"
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/v1/agents/station-01/ws",
                                          headers={"X-Agent-Token": next_token}):
                pass
        assert client.delete("/v1/agents/station-01/credential", headers=headers).status_code == 404

def test_dashboard_does_not_embed_api_secret(tmp_path):
    app = create_app(store_path=str(tmp_path / "db.sqlite"), api_key=API_KEY)
    with TestClient(app) as client:
        response = client.get("/dashboard")
        assert response.status_code == 200
        assert "DeviceShare Console" in response.text
        assert API_KEY not in response.text
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-frame-options"] == "DENY"
        assert "form-action 'none'" in response.headers["content-security-policy"]

def test_agent_id_rejected(tmp_path):
    app = create_app(store_path=str(tmp_path / "db.sqlite"), api_key=API_KEY)
    with TestClient(app) as client:
        response = client.post("/v1/agents/not%20valid/credential",
                               headers={"X-API-Key": API_KEY})
        assert response.status_code == 422

def test_legacy_token_never_overrides_paired_agent(tmp_path):
    app = create_app(store_path=str(tmp_path / "db.sqlite"),
                     api_key=API_KEY, agent_token="a-long-shared-legacy-token")
    headers = {"X-API-Key": API_KEY}
    with TestClient(app) as client:
        with client.websocket_connect("/v1/agents/unpaired/ws",
                                      headers={"X-Agent-Token": "a-long-shared-legacy-token"}) as ws:
            ws.send_json({"type": "inventory", "devices": []})
        client.post("/v1/agents/unpaired/credential", headers=headers)
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/v1/agents/unpaired/ws",
                                          headers={"X-Agent-Token": "a-long-shared-legacy-token"}):
                pass
