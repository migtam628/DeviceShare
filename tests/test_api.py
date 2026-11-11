import base64

from fastapi.testclient import TestClient

from deviceshare.hub import create_app

API_KEY = "a-very-long-test-api-key"
AGENT_TOKEN = "a-separate-long-agent-token"

def test_auth_and_queue(tmp_path):
    app = create_app(store_path=str(tmp_path / "test.db"),
                     api_key=API_KEY, agent_token=AGENT_TOKEN)
    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/v1/jobs").status_code == 401
        headers = {"X-API-Key": API_KEY}
        response = client.post("/v1/jobs", headers=headers, json={
            "agent_id": "station-01", "device_id": "sim:printer",
            "operation": "simulate", "data_base64": base64.b64encode(b"test").decode()
        })
        assert response.status_code == 202
        assert response.json()["status"] == "queued"
        assert len(client.get("/v1/jobs", headers=headers).json()) == 1

def test_agent_delivery(tmp_path):
    app = create_app(store_path=str(tmp_path / "test.db"),
                     api_key=API_KEY, agent_token=AGENT_TOKEN)
    with TestClient(app) as client:
        payload = {"agent_id": "station-01", "device_id": "sim:printer",
                   "operation": "simulate", "data_base64": "aGVsbG8="}
        response = client.post("/v1/jobs", headers={"X-API-Key": API_KEY}, json=payload)
        job_id = response.json()["id"]
        with client.websocket_connect(
                "/v1/agents/station-01/ws",
                headers={"X-Agent-Token": AGENT_TOKEN}) as ws:
            ws.send_json({"type": "inventory", "devices": [
                {"id": "sim:printer", "kind": "simulator", "label": "Simulator"}]})
            delivered = ws.receive_json()
            assert delivered["type"] == "job"
            assert delivered["id"] == job_id
            ws.send_json({"type": "result", "id": job_id,
                          "success": True, "detail": {"simulated": True}})
        statuses = client.get("/v1/jobs", headers={"X-API-Key": API_KEY}).json()
        assert statuses[0]["status"] in ("accepted", "unknown")
        # Disconnect must never put an already-sent job back in queued.
        assert app.state.store.pending("station-01") == []
