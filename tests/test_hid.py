"""Hardware-independent tests for the restricted HID input plugin."""
import base64
import sys
import types

import pytest
from pydantic import ValidationError

from deviceshare.backends import execute
from deviceshare.hid_devices import device_id, list_hid_devices


class FakeDevice:
    opened = False
    closed = False

    def open_path(self, path):
        assert path == b"fake-path"
        self.opened = True

    def read(self, read_size, timeout_ms):
        assert read_size == 8
        assert timeout_ms == 100
        return [1, 2, 3]

    def close(self):
        self.closed = True


def fake_hid():
    info = {"vendor_id": 0x1A2B, "product_id": 0x3C4D,
            "path": b"fake-path", "product_string": "Test HID"}
    device = FakeDevice()
    module = types.SimpleNamespace(enumerate=lambda: [info], device=lambda: device)
    return info, device, module


def make_job(identifier, data_base64=""):
    return {"id": "a" * 32, "operation": "hid_read", "device_id": identifier,
            "data_base64": data_base64,
            "options": {"read_size": 8, "timeout_ms": 100}}


def test_hid_read_requires_exact_local_device_approval(monkeypatch):
    info, fake, module = fake_hid()
    monkeypatch.setitem(sys.modules, "hid", module)
    identifier = device_id(info)
    assert identifier.startswith("hid:1a2b:3c4d:")
    assert list_hid_devices()[0]["id"] == identifier

    with pytest.raises(PermissionError):
        execute(make_job(identifier), {"allowed_hid_devices": []})
    assert not fake.opened
    result = execute(make_job(identifier), {"allowed_hid_devices": [identifier]})
    assert base64.b64decode(result["received_base64"]) == b"\x01\x02\x03"
    assert fake.opened and fake.closed


def test_hid_read_rejects_writes(monkeypatch):
    info, _, module = fake_hid()
    monkeypatch.setitem(sys.modules, "hid", module)
    identifier = device_id(info)
    with pytest.raises(ValueError):
        execute(make_job(identifier, "aGVsbG8="), {"allowed_hid_devices": [identifier]})


def test_hid_validation():
    from deviceshare.models import JobCreate
    identifier = device_id(fake_hid()[0])
    valid = JobCreate(agent_id="station-01", device_id=identifier,
                      operation="hid_read", data_base64="", options={"read_size": 8})
    assert valid.operation == "hid_read"
    with pytest.raises(ValidationError):
        JobCreate(agent_id="station-01", device_id=identifier,
                  operation="hid_read", data_base64="YQ==")
    with pytest.raises(ValidationError):
        JobCreate(agent_id="station-01", device_id=identifier,
                  operation="hid_read", data_base64="", options={"timeout_ms": 2000})
    with pytest.raises(ValidationError):
        JobCreate(agent_id="station-01", device_id="hid:garbage",
                  operation="hid_read", data_base64="")
