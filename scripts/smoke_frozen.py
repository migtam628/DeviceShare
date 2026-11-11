"""Smoke-test PyInstaller executables without hardware or a public listener."""
import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


def check_cli(binary: str, expected: str):
    proc = subprocess.run([binary, "--version"], capture_output=True,
                          text=True, timeout=30, check=True)
    if expected not in proc.stdout:
        raise RuntimeError(f"Version command failed for {binary}: {proc.stdout!r}")
    print(proc.stdout.strip(), flush=True)


def check_hub(binary: str):
    with tempfile.TemporaryDirectory() as temp:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        env = dict(os.environ)
        env.update(
            DEVICESHARE_API_KEY="smoke-test-admin-key-never-use-in-production",
            DEVICESHARE_DB=str(Path(temp) / "test.db"),
            DEVICESHARE_HOST="127.0.0.1",
            DEVICESHARE_PORT=str(port),
        )
        # Avoid inheriting a local shared agent token in CI.
        env.pop("DEVICESHARE_AGENT_TOKEN", None)
        env.pop("DEVICESHARE_LEGACY_AGENT_TOKEN", None)
        with open(Path(temp) / "hub.log", "wb") as log:
            server = subprocess.Popen([binary], env=env, stdout=log, stderr=log)
            try:
                deadline = time.monotonic() + 40
                while time.monotonic() < deadline:
                    if server.poll() is not None:
                        break
                    try:
                        with urllib.request.urlopen(
                                f"http://127.0.0.1:{port}/healthz", timeout=2) as response:
                            if b"deviceshare" in response.read():
                                break
                    except (OSError, urllib.error.URLError):
                        time.sleep(0.3)
                else:
                    raise RuntimeError("Hub failed to start within 40 seconds")
                if server.poll() is not None:
                    raise RuntimeError(f"Hub exited unexpectedly: {server.returncode}")
                with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/dashboard", timeout=5) as response:
                    html = response.read()
                    if b"DeviceShare Console" not in html:
                        raise RuntimeError("Frozen hub did not include dashboard asset")
                print("Frozen hub /healthz and /dashboard OK", flush=True)
            except Exception:
                log.flush()
                print(Path(temp, "hub.log").read_text(errors="replace"), file=sys.stderr)
                raise
            finally:
                if os.name == "nt":
                    # PyInstaller onefile runs a parent bootloader and child process.
                    # Terminating only the parent leaves the child holding log/DB files,
                    # which blocks TemporaryDirectory cleanup on Windows.
                    subprocess.run(
                        ["taskkill", "/PID", str(server.pid), "/T", "/F"],
                        capture_output=True, text=True, timeout=15, check=False,
                    )
                    try:
                        server.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        server.kill()
                        server.wait(timeout=5)
                else:
                    server.terminate()
                    try:
                        server.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        server.kill()
                        server.wait(timeout=10)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", required=True)
    parser.add_argument("--hub", required=True)
    args = parser.parse_args()
    agent_path = str(Path(args.agent).resolve())
    check_cli(agent_path, "DeviceShare Agent")
    check_cli(str(Path(args.hub).resolve()), "DeviceShare Hub")
    scan = subprocess.run([agent_path, "--list-devices"], capture_output=True, text=True,
                          timeout=30, check=True)
    devices = json.loads(scan.stdout)
    if not isinstance(devices, list) or not any(
        d.get("id") == "sim:printer" for d in devices if isinstance(d, dict)
    ):
        raise RuntimeError("Frozen agent did not return JSON device inventory")
    print("Frozen agent read-only device inventory OK", flush=True)
    check_hub(str(Path(args.hub).resolve()))


if __name__ == "__main__":
    main()
