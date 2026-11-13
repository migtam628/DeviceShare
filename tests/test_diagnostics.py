"""Alpha.6 diagnostics never operate hardware or infer physical print completion."""
import time
from types import SimpleNamespace
from unittest.mock import patch

from deviceshare.discovery import discover

from fastapi.testclient import TestClient

from deviceshare.agent import approved_inventory
from deviceshare.diagnostics import build_diagnostics
from deviceshare.hub import create_app

ADMIN = "alpha6-diagnostics-admin-test-key-123456"
AGENT = "alpha6-diagnostics-agent-token-123456"
AUTH = {"X-API-Key": ADMIN}


def test_local_allowlist_reporting_does_not_leak_secrets():
    devices = [
        {"id": "printer:HP_ENVY", "kind": "printer", "label": "HP ENVY", "state": "enabled"},
        {"id": "printer:Unknown", "kind": "printer", "label": "Unknown"},
        {"id": "serial:/dev/cu.usbmodem01", "kind": "serial"},
        {"id": "hid:reader:01", "kind": "hid"},
        {"id": "sim:printer", "kind": "simulator"},
        {"id": "usb:046d:1234", "kind": "usb-readonly"},
    ]
    config = {
        "allowed_printers": ["HP_ENVY"],
        "allowed_serial_ports": [],
        "allowed_hid_devices": ["hid:reader:01"],
        "allow_simulator": False,
        "token_file": "/secret/should-not-travel",
    }
    result = approved_inventory(devices, config)
    assert result[0]["allowed"] is True
    assert result[1]["allowed"] is False
    assert result[2]["allowed"] is False
    assert result[3]["allowed"] is True
    assert result[4]["allowed"] is False
    assert "allowed" not in result[5]
    assert "token_file" not in str(result)
    assert devices[0].get("allowed") is None  # no in-place mutation


def test_finding_messages_cover_offline_approval_disabled_and_unknown():
    agents = [
        {"agent_id": "mac", "online": True, "inventory_age_seconds": 121,
         "devices": [
             {"id": "printer:HP", "kind": "printer", "label": "HP",
              "state": "disabled", "allowed": False},
             {"id": "printer:Brother", "kind": "printer", "label": "Brother",
              "state": "enabled", "allowed": True},
         ]},
        {"agent_id": "office", "online": False, "devices": []},
    ]
    jobs = [
        {"id": "x", "status": "unknown", "operation": "print_document"},
        {"id": "y", "status": "failed", "operation": "print_document"},
    ]
    report = build_diagnostics(agents, jobs)
    codes = [f["code"] for f in report["findings"]]
    for code in ("agent-offline", "inventory-stale", "printer-disabled",
                 "printer-unapproved", "uncertain-jobs", "failed-jobs"):
        assert code in codes
    assert report["counts"] == {
        "stations": 2, "online_stations": 1,
        "discovered_printers": 2, "approved_printers": 1,
        "unknown_jobs": 1, "failed_jobs": 1,
    }
    assert report["overall"] == "attention"
    assert "paper" in report["disclaimer"]
    assert "automatically retry" in " ".join(f["detail"] for f in report["findings"])


def test_cups_queue_acceptance_is_separate_from_enabled_state():
    accepted = SimpleNamespace(
        returncode=0, stdout="HP accepting requests since Tue\nZebra not accepting requests since Tue\n")
    status = SimpleNamespace(
        returncode=0, stdout="printer HP is idle. enabled since Tue\nprinter Zebra is idle. enabled since Tue\n")
    with patch("deviceshare.discovery.platform.system", return_value="Darwin"), \
         patch("deviceshare.discovery.shutil.which", return_value="/usr/bin/lpstat"), \
         patch("deviceshare.discovery.subprocess.run", side_effect=[accepted, status]):
        printers = [d for d in discover() if d.get("kind") == "printer"]
    by_name = {d["label"]: d for d in printers}
    assert by_name["HP"]["state"] == "enabled"
    assert by_name["HP"]["accepting"] is True
    assert by_name["Zebra"]["state"] == "enabled"
    assert by_name["Zebra"]["accepting"] is False


def test_diagnostics_identifies_nonaccepting_queue():
    report = build_diagnostics([
        {"agent_id": "mac", "online": True, "inventory_age_seconds": 5,
         "devices": [{"id": "printer:Zebra", "kind": "printer",
                      "state": "enabled", "accepting": False, "allowed": True}]}
    ], [])
    assert any(item["code"] == "printer-not-accepting" for item in report["findings"])


def test_online_station_not_physical_printer_proof():
    report = build_diagnostics([
        {"agent_id": "mac", "online": True, "inventory_age_seconds": 4,
         "devices": [{"id": "printer:HP", "kind": "printer", "label": "HP",
                      "state": "enabled", "allowed": True}]}
    ], [])
    assert report["overall"] == "observed"
    assert any(f["code"] == "ready-to-test" for f in report["findings"])
    assert not any("physically printed" in f["detail"] for f in report["findings"])


def test_diagnostics_api_auth_and_safe_refresh(tmp_path):
    app = create_app(store_path=str(tmp_path / "db.sqlite"), api_key=ADMIN, agent_token=AGENT)
    with TestClient(app) as client:
        assert client.get("/v1/diagnostics").status_code == 401
        assert client.get("/diagnostics").status_code == 200
        assert "DeviceShare Console" in client.get("/diagnostics").text
        empty = client.get("/v1/diagnostics", headers=AUTH).json()
        assert any(item["code"] == "no-stations" for item in empty["findings"])
        assert client.post("/v1/agents/mac/refresh", headers=AUTH).status_code == 409

        with client.websocket_connect("/v1/agents/mac/ws",
                                      headers={"X-Agent-Token": AGENT}) as socket:
            socket.send_json({"type": "inventory", "devices": [
                {"id": "printer:HP", "kind": "printer", "label": "HP",
                 "state": "enabled", "allowed": False},
            ]})
            for _ in range(50):
                states = client.get("/v1/agents", headers=AUTH).json()
                if states and states[0]["devices"]:
                    break
                time.sleep(0.015)
            assert states[0]["devices"][0]["allowed"] is False
            assert states[0]["inventory_age_seconds"] is not None
            report = client.get("/v1/diagnostics", headers=AUTH).json()
            assert any(f["code"] == "printer-unapproved" for f in report["findings"])
            result = client.post("/v1/agents/mac/refresh", headers=AUTH)
            assert result.status_code == 200
            assert socket.receive_json() == {"type": "refresh_inventory"}
            assert client.post("/v1/agents/mac/refresh", headers=AUTH).status_code == 429


def test_refresh_cookie_csrf_guard(tmp_path):
    app = create_app(store_path=str(tmp_path / "db.sqlite"), api_key=ADMIN)
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        session = client.post("/v1/session", json={"api_key": ADMIN, "remember": False})
        assert session.status_code == 200
        assert client.post("/v1/agents/mac/refresh").status_code == 403
        assert client.get("/v1/diagnostics").status_code == 200
