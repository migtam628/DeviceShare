import base64
import pytest
from pydantic import ValidationError

from deviceshare.models import JobCreate

def encoded(raw=b"hello"):
    return base64.b64encode(raw).decode()

def test_simulator_job():
    job = JobCreate(agent_id="station-01", device_id="sim:printer",
                    operation="simulate", data_base64=encoded())
    assert job.operation == "simulate"

@pytest.mark.parametrize("operation,device_id", [
    ("print_raw", "serial:COM1"),
    ("serial_exchange", "printer:test"),
    ("simulate", "sim:unsafe"),
])
def test_operation_device_mismatch(operation, device_id):
    with pytest.raises(ValidationError):
        JobCreate(agent_id="station-01", device_id=device_id,
                  operation=operation, data_base64=encoded())

def test_invalid_b64():
    with pytest.raises(ValidationError):
        JobCreate(agent_id="station-01", device_id="sim:printer",
                  operation="simulate", data_base64="not valid base64!")

def test_size_limit():
    with pytest.raises(ValidationError):
        JobCreate(agent_id="station-01", device_id="sim:printer",
                  operation="simulate", data_base64=encoded(b"X" * (1024 * 1024 + 1)))
