"""HID discovery and explicitly approved, read-only input reports.

Raw keyboard HID devices may be managed exclusively by the OS. No HID output,
feature reports, control transfers, or unrestricted USB writes are exposed.
"""
import base64
import hashlib
import re

HID_ID = re.compile(r"^hid:[0-9a-f]{4}:[0-9a-f]{4}:[0-9a-f]{16}$")


def _path_bytes(path):
    if isinstance(path, bytes):
        return path
    if isinstance(path, str):
        return path.encode("utf-8", errors="surrogatepass")
    raise ValueError("HID device path missing")


def device_id(info: dict) -> str:
    vid = int(info["vendor_id"])
    pid = int(info["product_id"])
    if not 0 <= vid <= 65535 or not 0 <= pid <= 65535:
        raise ValueError("invalid USB vendor/product identifier")
    digest = hashlib.sha256(_path_bytes(info["path"])).hexdigest()[:16]
    return f"hid:{vid:04x}:{pid:04x}:{digest}"


def list_hid_devices() -> list[dict[str, str]]:
    try:
        import hid
    except ImportError:
        return []
    result = []
    for info in hid.enumerate():
        try:
            identifier = device_id(info)
            result.append({
                "id": identifier,
                "kind": "hid-input",
                "label": (
                    f"{str(info.get('product_string') or 'HID device')[:80]} "
                    f"({int(info['vendor_id']):04x}:{int(info['product_id']):04x})"
                ),
            })
        except (KeyError, TypeError, ValueError):
            continue
    return result


def read_report(identifier: str, allowed: list[str], read_size: int,
                timeout_ms: int) -> dict:
    if not HID_ID.fullmatch(identifier):
        raise ValueError("invalid HID identifier")
    if identifier not in allowed:
        raise PermissionError("HID device is not explicitly approved for local reads")
    if type(read_size) is not int or not 1 <= read_size <= 64:
        raise ValueError("read_size must be 1..64 bytes")
    if type(timeout_ms) is not int or not 0 <= timeout_ms <= 1000:
        raise ValueError("timeout_ms must be 0..1000")
    try:
        import hid
    except ImportError as exc:
        raise RuntimeError("HID support requires pip install deviceshare[hid]") from exc
    matching = []
    for item in hid.enumerate():
        try:
            if device_id(item) == identifier:
                matching.append(item)
        except (KeyError, ValueError, TypeError):
            continue
    if not matching:
        raise FileNotFoundError("approved HID device is not attached")
    if len(matching) != 1:
        raise RuntimeError("ambiguous HID device identifier")
    device = hid.device()
    try:
        device.open_path(matching[0]["path"])
        data = bytes(device.read(read_size, timeout_ms))
    finally:
        device.close()
    return {
        "received_base64": base64.b64encode(data).decode("ascii"),
        "bytes_read": len(data),
        "timeout_ms": timeout_ms,
    }
