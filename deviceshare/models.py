"""Shared protocol and job input validation."""
import base64
import binascii
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator

MAX_PAYLOAD_BYTES = 1024 * 1024

class Operation(str, Enum):
    PRINT_RAW = "print_raw"
    PRINT_DOCUMENT = "print_document"
    SERIAL_EXCHANGE = "serial_exchange"
    SIMULATE = "simulate"
    HID_READ = "hid_read"

class JobCreate(BaseModel):
    agent_id: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_.-]+$")
    device_id: str = Field(min_length=1, max_length=300)
    operation: Operation
    data_base64: str = Field(max_length=1_500_000)
    options: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=120)

    @model_validator(mode="after")
    def check_payload(self):
        try:
            raw = base64.b64decode(self.data_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("data_base64 must be valid base64") from exc
        if len(raw) > MAX_PAYLOAD_BYTES:
            raise ValueError("payload exceeds 1 MiB")
        expected = {
            Operation.PRINT_RAW: "printer:",
            Operation.PRINT_DOCUMENT: "printer:",
            Operation.SERIAL_EXCHANGE: "serial:",
            Operation.SIMULATE: "sim:",
            Operation.HID_READ: "hid:",
        }[self.operation]
        if not self.device_id.startswith(expected):
            raise ValueError(f"device_id must start with {expected}")
        if self.operation == Operation.PRINT_DOCUMENT:
            if self.options.get("mime_type") not in ("application/pdf", "image/png"):
                raise ValueError("print_document requires mime_type application/pdf or image/png")
            copies = self.options.get("copies", 1)
            media = self.options.get("media", "Letter")
            sides = self.options.get("sides", "one-sided")
            if type(copies) is not int or not 1 <= copies <= 5:
                raise ValueError("copies must be an integer from 1 to 5")
            if media not in ("Letter", "A4") or sides not in ("one-sided", "two-sided-long-edge"):
                raise ValueError("unsupported print media or sides option")
            if any(k not in ("mime_type", "copies", "media", "sides") for k in self.options):
                raise ValueError("unsupported document print option")
        if self.operation == Operation.SERIAL_EXCHANGE:
            baud = self.options.get("baudrate", 9600)
            read_size = self.options.get("read_size", 0)
            if type(baud) is not int or baud not in (300, 1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200, 230400):
                raise ValueError("unsupported baudrate")
            if type(read_size) is not int or not 0 <= read_size <= 4096:
                raise ValueError("read_size must be 0..4096")
        if self.operation == Operation.HID_READ:
            from .hid_devices import HID_ID
            if not HID_ID.fullmatch(self.device_id):
                raise ValueError("invalid HID device identifier")
            if raw:
                raise ValueError("HID input read cannot include write data")
            size = self.options.get("read_size", 64)
            timeout = self.options.get("timeout_ms", 500)
            if type(size) is not int or not 1 <= size <= 64:
                raise ValueError("HID read_size must be 1..64")
            if type(timeout) is not int or not 0 <= timeout <= 1000:
                raise ValueError("HID timeout_ms must be 0..1000")
        if self.operation == Operation.SIMULATE and self.device_id != "sim:printer":
            raise ValueError("only sim:printer is implemented")
        return self
