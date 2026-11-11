import base64

import pytest

from deviceshare.agent import websocket_url
from deviceshare.backends import execute

def test_simulator_writes_bytes(tmp_path):
    payload = b"print sample"
    job = {
        "id": "a" * 32, "operation": "simulate",
        "device_id": "sim:printer", "data_base64": base64.b64encode(payload).decode()
    }
    result = execute(job, {"simulator_dir": str(tmp_path)})
    assert result["simulated"] is True
    assert (tmp_path / ("a" * 32 + ".bin")).read_bytes() == payload

def test_serial_denied_without_approval():
    job = {"id": "b" * 32, "operation": "serial_exchange",
           "device_id": "serial:loop://", "data_base64": "YQ==",
           "options": {"baudrate": 9600, "read_size": 1}}
    with pytest.raises(PermissionError):
        execute(job, {"allowed_serial_ports": []})

def test_serial_loopback():
    job = {"id": "c" * 32, "operation": "serial_exchange",
           "device_id": "serial:loop://", "data_base64": "aGVsbG8=",
           "options": {"baudrate": 9600, "read_size": 5}}
    result = execute(job, {"allowed_serial_ports": ["loop://"]})
    assert base64.b64decode(result["received_base64"]) == b"hello"

def test_websocket_https_requirement():
    assert websocket_url("http://127.0.0.1:8765", "station-01").startswith("ws://")
    assert websocket_url("https://example.org", "station-01").startswith("wss://")
    with pytest.raises(ValueError):
        websocket_url("http://example.org", "station-01")
