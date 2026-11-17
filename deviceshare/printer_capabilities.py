"""Read-only CUPS paper-source discovery and fail-closed job validation.

Only option keywords reported by the selected local printer are accepted.
The default selection never overrides the printer's configured paper source.
"""
from __future__ import annotations

import re
import shutil
import subprocess

TRAY_TOKEN = re.compile(r"[A-Za-z0-9_.-]{1,48}\Z")
MAX_TRAYS = 24


def parse_trays(output: str) -> tuple[str | None, list[str]]:
    """Extract CUPS InputSlot / IPP media-source choices without display labels."""
    for line in output.splitlines():
        key, separator, choices = line.partition(":")
        if not separator:
            continue
        option = key.split("/", 1)[0].strip()
        if option.lower() not in ("inputslot", "media-source"):
            continue
        trays = []
        for value in choices.split():
            token = value.removeprefix("*")
            if TRAY_TOKEN.fullmatch(token) and token not in trays:
                trays.append(token)
            if len(trays) >= MAX_TRAYS:
                break
        return option, trays
    return None, []


def cups_trays(printer: str) -> tuple[str | None, list[str]]:
    """Query only the named local queue, without mutating its defaults."""
    if not shutil.which("lpoptions"):
        return None, []
    try:
        response = subprocess.run(["lpoptions", "-p", printer, "-l"],
                                  capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None, []
    if response.returncode:
        return None, []
    return parse_trays(response.stdout)


def tray_argument(printer: str, tray: str | None) -> str | None:
    """Resolve user choice against the fresh local device capabilities."""
    if tray is None or tray == "":
        return None
    if not isinstance(tray, str) or not TRAY_TOKEN.fullmatch(tray):
        raise ValueError("invalid paper tray identifier")
    option, choices = cups_trays(printer)
    if option is None or tray not in choices:
        raise ValueError("selected paper tray is not advertised by the local printer")
    return f"{option}={tray}"
