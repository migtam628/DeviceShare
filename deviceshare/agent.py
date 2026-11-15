"""Outbound-only DeviceShare agent for local peripherals."""
import argparse
import asyncio
import json
import os
import random
import re
import time
from pathlib import Path
from urllib.parse import quote, urlsplit

from websockets.asyncio.client import connect

from .backends import execute
from .discovery import discover

def websocket_url(hub_url: str, agent_id: str, allow_insecure_remote: bool = False) -> str:
    if not re.fullmatch(r"[a-zA-Z0-9_.-]{1,80}", agent_id):
        raise ValueError("agent_id must use letters, numbers, dot, dash or underscore")
    parsed = urlsplit(hub_url)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("hub_url cannot include credentials, query or fragment")
    if parsed.scheme not in ("http", "https", "ws", "wss") or not parsed.hostname:
        raise ValueError("hub_url must be an HTTP(S) or WS(S) URL")
    if parsed.scheme in ("http", "ws") and parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
        if not allow_insecure_remote:
            raise ValueError("Remote agents require HTTPS/WSS (or explicit insecure dev override)")
    scheme = "wss" if parsed.scheme in ("https", "wss") else "ws"
    prefix = parsed.path.rstrip("/")
    return f"{scheme}://{parsed.netloc}{prefix}/v1/agents/{quote(agent_id)}/ws"

def load_config(path: str) -> dict:
    config = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("config must be a JSON object")
    for key in ("allowed_printers", "allowed_serial_ports", "allowed_hid_devices"):
        if not isinstance(config.get(key, []), list):
            raise ValueError(f"{key} must be a list")
    return config

def approved_inventory(devices: list[dict], config: dict) -> list[dict]:
    """Mark only actual local allowlist approval; never send a credential."""
    printers = set(config.get("allowed_printers", []))
    ports = set(config.get("allowed_serial_ports", []))
    hid = set(config.get("allowed_hid_devices", []))
    result = []
    for device in devices:
        entry = dict(device)
        did = str(entry.get("id", ""))
        if did.startswith("printer:"):
            entry["allowed"] = did.removeprefix("printer:") in printers
        elif did.startswith("serial:"):
            entry["allowed"] = did.removeprefix("serial:") in ports
        elif did.startswith("hid:"):
            entry["allowed"] = did in hid
        elif did == "sim:printer":
            entry["allowed"] = config.get("allow_simulator", True) is True
        result.append(entry)
    return result


def reconnect_delay(consecutive_failures: int) -> float:
    """Bounded reconnect backoff with jitter to avoid connection storms."""
    exponent = min(max(consecutive_failures - 1, 0), 4)
    return min(30.0, float(2 ** exponent)) + random.uniform(0, 0.5)


async def refresh_inventory(socket, config: dict, requested: asyncio.Event):
    """Keep reporting device state even when a local OS scan fails once."""
    while True:
        try:
            devices = await asyncio.to_thread(discover)
            message = {"type": "inventory", "devices": approved_inventory(devices, config)}
        except Exception as exc:
            # The detailed error stays in the local station logs; the Hub gets
            # no local file paths, driver internals, or credentials.
            print(f"Inventory scan failed ({type(exc).__name__}): {exc}", flush=True)
            message = {"type": "inventory_error"}
        # Send errors must propagate: a broken socket requires reconnection,
        # not a silent task failure while the station appears online.
        await socket.send(json.dumps(message))
        try:
            await asyncio.wait_for(requested.wait(), timeout=30)
            requested.clear()
        except asyncio.TimeoutError:
            pass


async def receive_jobs(socket, config: dict, requested: asyncio.Event):
    async for message in socket:
        try:
            payload = json.loads(message)
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
            print("Ignored malformed Hub message", flush=True)
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get("type") == "refresh_inventory":
            # Read-only re-enumeration; never replays old print jobs.
            requested.set()
            continue
        if payload.get("type") != "job":
            continue
        job_id = payload.get("id", "")
        try:
            # Avoid blocking the WebSocket event loop on physical I/O.
            result = await asyncio.to_thread(execute, payload, config)
            reply = {"type": "result", "id": job_id,
                     "success": True, "detail": result}
        except Exception as exc:
            reply = {"type": "result", "id": job_id,
                     "success": False,
                     "detail": {"error": str(exc)[:500]}}
        await socket.send(json.dumps(reply))


async def connected_session(socket, config: dict):
    """Reconnect if either inventory reporting or command receiving stops."""
    refresh_requested = asyncio.Event()
    tasks = [
        asyncio.create_task(refresh_inventory(socket, config, refresh_requested)),
        asyncio.create_task(receive_jobs(socket, config, refresh_requested)),
    ]
    try:
        finished, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in finished:
            await task
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def run(config: dict):
    agent_id = config.get("agent_id", "")
    token = os.getenv("DEVICESHARE_AGENT_TOKEN", "")
    token_file = config.get("token_file")
    if not token and token_file:
        token = Path(token_file).expanduser().read_text(encoding="utf-8").strip()
    if len(token) < 16:
        raise ValueError("Agent token is required: set DEVICESHARE_AGENT_TOKEN or token_file")
    url = websocket_url(
        config.get("hub_url", "http://127.0.0.1:8765"), agent_id,
        allow_insecure_remote=config.get("allow_insecure_remote", False),
    )
    print(f"DeviceShare agent {agent_id}: connecting to {url}", flush=True)
    failures = 0
    while True:
        started_at = time.monotonic()
        try:
            async with connect(
                url,
                additional_headers={"X-Agent-Token": token},
                open_timeout=10,
                max_size=1_600_000,
                ping_interval=20,
                ping_timeout=20,
            ) as socket:
                print("Connected to DeviceShare hub", flush=True)
                await connected_session(socket, config)
        except Exception as exc:
            # Connection errors and server restarts: reconnect, never replay local jobs.
            print(f"Disconnected: {type(exc).__name__}: {exc}", flush=True)
        failures = 0 if time.monotonic() - started_at >= 60 else failures + 1
        await asyncio.sleep(reconnect_delay(failures))

def main():
    parser = argparse.ArgumentParser(description="DeviceShare local agent")
    parser.add_argument("--version", action="version", version="DeviceShare Agent 0.2.0a7")
    parser.add_argument("--list-devices", action="store_true",
                        help="Print read-only local device inventory as JSON and exit")
    parser.add_argument("--config", default=os.environ.get(
        "DEVICESHARE_AGENT_CONFIG", "./config/agent.json"))
    args = parser.parse_args()
    if args.list_devices:
        print(json.dumps(discover(), indent=2))
        return
    asyncio.run(run(load_config(args.config)))

if __name__ == "__main__":
    main()
