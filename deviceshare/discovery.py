"""Read-only hardware inventory. Physical USB device operations are not exposed."""
import json
import platform
import shutil
import subprocess

from .hid_devices import list_hid_devices

def discover() -> list[dict[str, str]]:
    devices = [{"id": "sim:printer", "kind": "simulator", "label": "Simulated printer"}]
    if platform.system() == "Windows":
        try:
            import win32print
            for info in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL):
                name = str(info[2])
                devices.append({"id": f"printer:{name}", "kind": "printer", "label": name,
                                "state": "unknown"})
        except ImportError:
            pass
        except Exception:
            pass
    elif shutil.which("lpstat"):
        try:
            accepting = subprocess.run(["lpstat", "-a"], capture_output=True,
                                       text=True, timeout=5, check=False)
            states = subprocess.run(["lpstat", "-p"], capture_output=True,
                                    text=True, timeout=5, check=False)
            queue_states = {}
            if states.returncode == 0:
                for line in states.stdout.splitlines():
                    if line.startswith("printer "):
                        parts = line.split()
                        if len(parts) >= 3:
                            queue_states[parts[1]] = ("disabled" if " disabled " in " " + line + " " else "enabled")
            if accepting.returncode == 0:
                for line in accepting.stdout.splitlines():
                    name, _, status = line.partition(" ")
                    name = name.strip()
                    if name:
                        status_lower = status.lower().strip()
                        accepting_jobs = (
                            False if status_lower.startswith("not accepting")
                            else True if status_lower.startswith("accepting") else None
                        )
                        devices.append({
                            "id": f"printer:{name}", "kind": "printer", "label": name,
                            # CUPS queue state and whether it accepts jobs are
                            # distinct from physical device connectivity.
                            "state": queue_states.get(name, "unknown"),
                            "accepting": accepting_jobs,
                        })
        except (OSError, subprocess.TimeoutExpired):
            pass

    try:
        from serial.tools.list_ports import comports
        for port in comports():
            devices.append({
                "id": f"serial:{port.device}",
                "kind": "serial",
                "label": port.description or port.device,
            })
    except ImportError:
        pass

    try:
        import usb.core
        for device in usb.core.find(find_all=True) or []:
            identifier = f"usb:{device.idVendor:04x}:{device.idProduct:04x}"
            devices.append({"id": identifier, "kind": "usb-readonly",
                            "label": f"USB {device.idVendor:04x}:{device.idProduct:04x}"})
    except (ImportError, OSError, ValueError):
        pass
    try:
        devices.extend(list_hid_devices())
    except (OSError, RuntimeError, ValueError):
        # HID enumeration can be unavailable without OS permissions.
        pass
    return devices

def main():
    print(json.dumps(discover(), indent=2))

if __name__ == "__main__":
    main()
