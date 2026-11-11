"""Outbound-only DeviceShare agent for local peripherals."""
import argparse
import asyncio
import json
import os
import re
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
    while True:
        try:
            async with connect(
                url,
                additional_headers={"X-Agent-Token": token},
                open_timeout=10,
                max_size=1_600_000,
                ping_interval=20,
                ping_timeout=20,
            ) as socket:
                async def refresh_inventory():
                    while True:
                        devices = await asyncio.to_thread(discover)
                        await socket.send(json.dumps({"type": "inventory", "devices": devices}))
                        await asyncio.sleep(30)

                inventory_task = asyncio.create_task(refresh_inventory())
                print("Connected to DeviceShare hub", flush=True)
                try:
                    async for message in socket:
                        payload = json.loads(message)
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
                finally:
                    inventory_task.cancel()
                    try:
                        await inventory_task
                    except asyncio.CancelledError:
                        pass
        except Exception as exc:
            # Connection errors and server restarts: reconnect, never replay local jobs.
            print(f"Disconnected: {type(exc).__name__}: {exc}", flush=True)
        await asyncio.sleep(5)

def main():
    parser = argparse.ArgumentParser(description="DeviceShare local agent")
    parser.add_argument("--version", action="version", version="DeviceShare Agent 0.2.0a2")
    parser.add_argument("--config", default=os.environ.get(
        "DEVICESHARE_AGENT_CONFIG", "./config/agent.json"))
    args = parser.parse_args()
    asyncio.run(run(load_config(args.config)))

if __name__ == "__main__":
    main()
