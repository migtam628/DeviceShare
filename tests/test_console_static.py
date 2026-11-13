"""Static checks for the routed desktop console and its browser script."""
import re
import shutil
import subprocess
from importlib.resources import files

import pytest


def test_console_contains_all_screens_and_printer_actions():
    html = files("deviceshare").joinpath("console.html").read_text(encoding="utf-8")
    assert "<title>DeviceShare Console</title>" in html
    for screen in ("dashboard", "printers", "studio", "jobs", "devices", "diagnostics", "settings"):
        assert 'data-screen="' + screen + '"' in html
        assert 'data-nav="' + screen + '"' in html
    for name in ("studioPrinter", "testPrint", "customText", "printText",
                 "printDocument", "printCopies", "printMedia", "printSides",
                 "signIn", "signOut", "signOutAll", "runDiagnostics", "copyDiagnostics", "refreshSelectedPrinter"):
        assert 'id="' + name + '"' in html
    assert "localStorage.setItem(\"deviceshare_printer\"" in html
    assert "localStorage.setItem(\"deviceshare_refresh_seconds\"" in html
    # No raw admin token is intentionally written to browser storage.
    assert "localStorage.setItem(\"apiKey\"" not in html
    assert "sessionStorage.setItem(\"apiKey\"" not in html


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js not installed")
def test_embedded_console_javascript_syntax():
    html = files("deviceshare").joinpath("console.html").read_text(encoding="utf-8")
    script = re.search(r"<script>(.*?)</script>", html, re.DOTALL)
    assert script is not None
    process = subprocess.run(["node", "--check"], input=script.group(1),
                             capture_output=True, text=True, encoding="utf-8", timeout=20)
    assert process.returncode == 0, process.stderr
