"""Explicitly authorized peripherals. No arbitrary shell or USB write operations."""
import base64
import binascii
import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .models import MAX_PAYLOAD_BYTES
from .hid_devices import read_report

def _payload(job: dict) -> bytes:
    try:
        data = base64.b64decode(job["data_base64"], validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("invalid job data") from exc
    if len(data) > MAX_PAYLOAD_BYTES:
        raise ValueError("payload too large")
    return data

def _raw_print(printer: str, data: bytes) -> dict[str, str]:
    if platform.system() == "Windows":
        try:
            import win32print
        except ImportError as exc:
            raise RuntimeError("Windows raw printing needs pip install deviceshare[windows]") from exc
        handle = win32print.OpenPrinter(printer)
        try:
            task_id = win32print.StartDocPrinter(handle, 1, ("DeviceShare", None, "RAW"))
            try:
                win32print.StartPagePrinter(handle)
                win32print.WritePrinter(handle, data)
                win32print.EndPagePrinter(handle)
            finally:
                win32print.EndDocPrinter(handle)
            return {"queue": "windows-spooler", "job_id": str(task_id)}
        finally:
            win32print.ClosePrinter(handle)
    if not shutil.which("lp"):
        raise RuntimeError("CUPS lp command not installed")
    result = subprocess.run(["lp", "-d", printer, "-o", "raw"],
                            input=data, capture_output=True, timeout=30, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace")[:400])
    return {"queue": "cups", "message": result.stdout.decode(errors="replace").strip()}

def _document_print(printer: str, data: bytes, mime_type: str) -> dict[str, str]:
    if platform.system() == "Windows":
        raise RuntimeError("Document printing on Windows is not yet supported; use print_raw")
    if mime_type not in ("application/pdf", "image/png"):
        raise ValueError("supported document formats: PDF, PNG")
    if not shutil.which("lp"):
        raise RuntimeError("CUPS lp command not installed")
    suffix = ".pdf" if mime_type == "application/pdf" else ".png"
    tmp_name = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(data)
            tmp_name = tmp.name
        result = subprocess.run(["lp", "-d", printer, tmp_name],
                                capture_output=True, timeout=30, check=False)
        if result.returncode:
            raise RuntimeError(result.stderr.decode(errors="replace")[:400])
        return {"queue": "cups", "message": result.stdout.decode(errors="replace").strip()}
    finally:
        if tmp_name:
            Path(tmp_name).unlink(missing_ok=True)

def execute(job: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Return a queue-acceptance result, not proof of physical output."""
    operation = job["operation"]
    device_id = job["device_id"]
    data = _payload(job)
    options = job.get("options", {})
    if operation == "simulate":
        if device_id != "sim:printer" or not config.get("allow_simulator", True):
            raise PermissionError("simulator disabled")
        spool = Path(config.get("simulator_dir", "./data/simulator")).expanduser()
        spool.mkdir(parents=True, exist_ok=True)
        output = spool / (job["id"] + ".bin")
        # The output name comes from a server-generated hex UUID; defend local calls too.
        if not all(c in "0123456789abcdef" for c in job["id"]):
            raise ValueError("invalid job ID")
        output.write_bytes(data)
        return {"simulated": True, "file": str(output), "bytes": len(data)}

    if operation in ("print_raw", "print_document"):
        if not device_id.startswith("printer:"):
            raise ValueError("expected a printer device")
        printer = device_id.removeprefix("printer:")
        if printer not in config.get("allowed_printers", []):
            raise PermissionError("printer is not in local allowlist")
        if operation == "print_raw":
            return _raw_print(printer, data)
        return _document_print(printer, data, options.get("mime_type", ""))

    if operation == "hid_read":
        if data:
            raise ValueError("HID input reads cannot write payload bytes")
        return read_report(
            device_id,
            config.get("allowed_hid_devices", []),
            options.get("read_size", 64),
            options.get("timeout_ms", 500),
        )

    if operation == "serial_exchange":
        if not device_id.startswith("serial:"):
            raise ValueError("expected a serial device")
        port = device_id.removeprefix("serial:")
        if port not in config.get("allowed_serial_ports", []):
            raise PermissionError("serial port is not in local allowlist")
        import serial
        baudrate = options.get("baudrate", 9600)
        read_size = options.get("read_size", 0)
        if type(baudrate) is not int or baudrate not in (300,1200,2400,4800,9600,19200,38400,57600,115200,230400):
            raise ValueError("invalid baudrate")
        if type(read_size) is not int or not 0 <= read_size <= 4096:
            raise ValueError("invalid read size")
        # serial_for_url supports loop:// for testing, only if explicitly allowlisted.
        with serial.serial_for_url(port, baudrate=baudrate, timeout=2,
                                   write_timeout=2) as device:
            count = device.write(data) if data else 0
            answer = device.read(read_size) if read_size else b""
        return {"written": count, "received_base64": base64.b64encode(answer).decode()}

    raise ValueError("unsupported operation")
