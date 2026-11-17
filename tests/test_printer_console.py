"""End-to-end test-page dispatch to an authenticated online DeviceShare agent."""
import base64
import time
from fastapi.testclient import TestClient

from deviceshare.hub import create_app

ADMIN = "long-print-integration-test-admin-api-key"
AGENT = "long-print-integration-test-agent-token"


def test_preview_pages_and_print_studio_dispatch(tmp_path):
    app = create_app(store_path=str(tmp_path / "hub.db"), api_key=ADMIN, agent_token=AGENT)
    with TestClient(app) as client:
        for route in ("/dashboard", "/printers", "/studio", "/jobs", "/devices", "/diagnostics", "/settings"):
            response = client.get(route)
            assert response.status_code == 200
            assert "DeviceShare Console" in response.text
            assert "Printers" in response.text and "Print Studio" in response.text
            assert response.headers["cache-control"] == "no-store"

        with client.websocket_connect(
            "/v1/agents/station/ws", headers={"X-Agent-Token": AGENT}
        ) as socket:
            socket.send_json({
                "type": "inventory",
                "devices": [{"id": "printer:HP_ENVY_6000", "label": "HP ENVY",
                             "kind": "printer", "state": "enabled"}]
            })
            headers = {"X-API-Key": ADMIN}
            body = {"agent_id": "station", "device_id": "printer:HP_ENVY_6000",
                    "copies": 1, "media": "Letter", "sides": "one-sided"}
            # Allow the agent's inventory event to reach the server.
            for _ in range(30):
                response = client.get("/v1/agents", headers=headers)
                if response.json() and response.json()[0]["devices"]:
                    break
                time.sleep(0.02)
            assert response.status_code == 200
            assert response.json()[0]["devices"]
            result = client.post("/v1/print/test", headers=headers, json=body)
            assert result.status_code == 202
            dispatched = socket.receive_json()
            assert dispatched["operation"] == "print_document"
            assert dispatched["device_id"] == "printer:HP_ENVY_6000"
            assert dispatched["options"]["mime_type"] == "application/pdf"
            assert base64.b64decode(dispatched["data_base64"]).startswith(b"%PDF-")
            socket.send_json({"type": "result", "id": result.json()["id"],
                              "success": True, "detail": {"queue": "cups", "job_id": "99"}})
            custom = client.post("/v1/print/text", headers=headers,
                                 json={**body, "text": "Custom text printer test", "title": "Notes"})
            assert custom.status_code == 202
            sent = socket.receive_json()
            assert sent["operation"] == "print_document"
            assert base64.b64decode(sent["data_base64"]).startswith(b"%PDF-")
            socket.send_json({"type": "result", "id": custom.json()["id"],
                              "success": True, "detail": {"queue": "cups", "job_id": "100"}})


def test_test_page_rejects_disabled_printer(tmp_path):
    app = create_app(store_path=str(tmp_path / "hub.db"), api_key=ADMIN, agent_token=AGENT)
    with TestClient(app) as client:
        with client.websocket_connect(
            "/v1/agents/station/ws", headers={"X-Agent-Token": AGENT}
        ) as socket:
            socket.send_json({"type": "inventory", "devices": [
                {"id": "printer:HP_ENVY", "kind": "printer",
                 "label": "HP ENVY", "state": "disabled"}
            ]})
            # Force inventory event processing before the print request.
            for _ in range(20):
                result = client.get("/v1/agents", headers={"X-API-Key": ADMIN}).json()
                if result and result[0]["devices"]:
                    break
            answer = client.post("/v1/print/test", headers={"X-API-Key": ADMIN},
                                 json={"agent_id": "station", "device_id": "printer:HP_ENVY"})
            assert answer.status_code == 409
            assert client.get("/v1/jobs", headers={"X-API-Key": ADMIN}).json() == []


def test_brother_tray_and_zebra_4x6_label_dispatch(tmp_path):
    app = create_app(store_path=str(tmp_path / "hub.db"), api_key=ADMIN, agent_token=AGENT)
    with TestClient(app) as client:
        with client.websocket_connect("/v1/agents/station/ws", headers={"X-Agent-Token": AGENT}) as socket:
            socket.send_json({"type": "inventory", "devices": [
                {"id": "printer:Brother", "kind": "printer", "label": "Brother",
                 "state": "enabled", "accepting": True,
                 "trays": ["Auto", "Tray1", "Tray2", "^INVALID", "Tray2"], "tray_option": "InputSlot"},
                {"id": "printer:Zebra", "kind": "printer", "label": "Zebra",
                 "state": "enabled", "accepting": True}]})
            for _ in range(40):
                inventory = client.get("/v1/agents", headers={"X-API-Key": ADMIN}).json()
                if inventory and len(inventory[0]["devices"]) == 2:
                    break
                time.sleep(0.02)
            brother = next(x for x in inventory[0]["devices"] if x["id"] == "printer:Brother")
            assert brother["trays"] == ["Auto", "Tray1", "Tray2"]
            base = {"agent_id": "station", "device_id": "printer:Brother"}
            invalid = client.post("/v1/print/test", headers={"X-API-Key": ADMIN},
                                  json={**base, "tray": "Tray3"})
            assert invalid.status_code == 409
            assert client.get("/v1/jobs", headers={"X-API-Key": ADMIN}).json() == []
            allowed = client.post("/v1/print/test", headers={"X-API-Key": ADMIN},
                                  json={**base, "tray": "Tray2"})
            assert allowed.status_code == 202
            job = socket.receive_json()
            assert job["operation"] == "print_document" and job["options"]["tray"] == "Tray2"
            socket.send_json({"type": "result", "id": allowed.json()["id"],
                              "success": True, "detail": {"queue": "cups"}})

            label = client.post("/v1/print/station-label", headers={"X-API-Key": ADMIN}, json={
                "agent_id": "station", "device_id": "printer:Zebra", "recipient": "Marta",
                "address_line1": "123 Example St", "city_state_postal": "Miami FL 33101",
                "reference": "ORD-123"})
            assert label.status_code == 202
            dispatched = socket.receive_json()
            assert dispatched["operation"] == "print_raw"
            assert dispatched["device_id"] == "printer:Zebra"
            assert base64.b64decode(dispatched["data_base64"]).startswith(b"^XA\n^PW812\n^LL1218")
