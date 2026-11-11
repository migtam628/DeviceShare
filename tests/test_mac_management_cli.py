"""macOS management CLI contracts without requiring Apple hardware."""
import json
import os
import subprocess
import sys

import pytest


def test_agent_list_devices_does_not_need_token(monkeypatch):
    monkeypatch.delenv("DEVICESHARE_AGENT_TOKEN", raising=False)
    output = subprocess.check_output(
        [sys.executable, "-m", "deviceshare.agent", "--list-devices"], text=True
    )
    result = json.loads(output)
    assert isinstance(result, list)
    assert any(item["id"] == "sim:printer" for item in result)


def test_hub_reads_private_api_key_file(tmp_path, monkeypatch):
    from deviceshare import hub

    key = tmp_path / "admin-key"
    key.write_text("test-secure-hub-key-32-characters-long")
    key.chmod(0o600)
    monkeypatch.setenv("DEVICESHARE_DB", str(tmp_path / "data.db"))
    monkeypatch.delenv("DEVICESHARE_API_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", ["deviceshare-hub", "--api-key-file", str(key)])
    actual = {}

    def capture(app, **kwargs):
        actual["app"] = app
        actual["kwargs"] = kwargs

    monkeypatch.setattr(hub.uvicorn, "run", capture)
    hub.main()
    assert actual["app"].title == "DeviceShare"
    assert actual["kwargs"]["host"] == "127.0.0.1"


@pytest.mark.skipif(os.name == "nt", reason="Unix file permissions only")
def test_hub_refuses_world_readable_api_key_file(tmp_path, monkeypatch):
    from deviceshare import hub

    key = tmp_path / "admin-key"
    key.write_text("test-secure-hub-key-32-characters-long")
    key.chmod(0o644)
    monkeypatch.setattr(sys, "argv", ["deviceshare-hub", "--api-key-file", str(key)])
    with pytest.raises(SystemExit) as exc:
        hub.main()
    assert exc.value.code == 2
