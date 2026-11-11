"""Authenticated FastAPI hub and outbound-agent WebSocket relay."""
import argparse
import base64
import asyncio
import hashlib
import hmac
from importlib.resources import files
import json
import os
import re
import secrets
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, Response, Security, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.security import APIKeyHeader
from urllib.parse import urlsplit

from .models import JobCreate
from .printing import PrintSubmission, TextSubmission, render_pdf
from .store import Store

auth_header = APIKeyHeader(name="X-API-Key", auto_error=False)

@dataclass
class AgentConnection:
    ws: WebSocket
    devices: list[dict[str, Any]] = field(default_factory=list)
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    dispatch_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def send(self, message):
        async with self.send_lock:
            await self.ws.send_json(message)

def create_app(
    store_path: str | None = None,
    api_key: str | None = None,
    agent_token: str | None = None,
) -> FastAPI:
    api_key = api_key or os.environ.get("DEVICESHARE_API_KEY")
    # An optional legacy shared token supports upgrading old agents.
    # Paired credentials always take precedence, including when revoked.
    if agent_token is None:
        agent_token = (os.environ.get("DEVICESHARE_LEGACY_AGENT_TOKEN")
                       or os.environ.get("DEVICESHARE_AGENT_TOKEN"))
    if not api_key or len(api_key) < 16:
        raise RuntimeError("Set DEVICESHARE_API_KEY to a random secret (16+ characters)")
    if agent_token and (len(agent_token) < 16 or secrets.compare_digest(api_key, agent_token)):
        raise RuntimeError("Legacy agent token must be distinct from the API key (16+ characters)")
    store = Store(store_path or os.environ.get("DEVICESHARE_DB", "./data/deviceshare.db"))
    app = FastAPI(title="DeviceShare", version="0.2.0a4",
                  description="DeviceShare API. Printing accepted by an OS queue does not prove paper output.")
    clients: dict[str, AgentConnection] = {}
    app.state.store = store
    app.state.clients = clients
    fingerprint = hmac.new(api_key.encode("utf-8"), b"deviceshare-admin-session-v1", hashlib.sha256).hexdigest()
    session_cookie = "deviceshare_admin_session"

    def same_origin(request: Request) -> bool:
        origin = request.headers.get("origin")
        if not origin:
            return True
        try:
            parsed = urlsplit(origin)
            return (parsed.scheme == request.url.scheme
                    and parsed.netloc == request.url.netloc
                    and not parsed.username and not parsed.password
                    and parsed.path in ("", "/") and not parsed.query and not parsed.fragment)
        except ValueError:
            return False

    def cookie_authorized(request: Request) -> bool:
        return store.verify_admin_session(request.cookies.get(session_cookie), fingerprint)

    async def require_api_key(request: Request, key: str | None = Security(auth_header)):
        # A supplied API key always wins, even if invalid; never let an invalid header
        # silently fall back to a browser cookie.
        if key is not None:
            if secrets.compare_digest(key, api_key):
                return
            raise HTTPException(status_code=401, detail="Invalid API key")
        if not cookie_authorized(request):
            raise HTTPException(status_code=401, detail="Authentication required")
        # Mutations authenticated with browser cookies require a same-origin
        # non-simple header. Cross-site forms cannot send this header, and
        # cross-origin fetches cannot use it without a CORS preflight.
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if request.headers.get("x-deviceshare-csrf") != "1" or not same_origin(request):
                raise HTTPException(status_code=403, detail="Same-origin request required")

    @app.post("/v1/session")
    async def login(request: Request, response: Response, body: dict):
        if not same_origin(request):
            raise HTTPException(status_code=403, detail="Same-origin request required")
        # Never send an admin secret over cleartext to a remote server.
        if request.url.scheme != "https" and request.url.hostname not in ("localhost", "127.0.0.1", "::1"):
            raise HTTPException(status_code=400, detail="Use HTTPS for remote dashboard login")
        supplied = body.get("api_key")
        remember = body.get("remember", False)
        if not isinstance(supplied, str) or len(supplied) > 1024 or not secrets.compare_digest(supplied, api_key):
            raise HTTPException(status_code=401, detail="Invalid API key")
        if not isinstance(remember, bool):
            raise HTTPException(status_code=422, detail="remember must be a boolean")
        ttl = 30 * 86400 if remember else 12 * 3600
        token = store.issue_admin_session(fingerprint, ttl)
        response.set_cookie(
            key=session_cookie, value=token, httponly=True, secure=request.url.scheme == "https",
            samesite="strict", path="/v1", max_age=ttl if remember else None,
        )
        response.headers["Cache-Control"] = "no-store"
        return {"authenticated": True, "remembered": remember}

    @app.get("/v1/session")
    async def session_state(request: Request, response: Response):
        response.headers["Cache-Control"] = "no-store"
        return {"authenticated": cookie_authorized(request)}

    @app.delete("/v1/session")
    async def logout(request: Request, response: Response):
        if request.headers.get("x-deviceshare-csrf") != "1" or not same_origin(request):
            raise HTTPException(status_code=403, detail="Same-origin request required")
        store.revoke_admin_session(request.cookies.get(session_cookie))
        response.delete_cookie(key=session_cookie, path="/v1", samesite="strict")
        response.headers["Cache-Control"] = "no-store"
        return {"authenticated": False}

    @app.delete("/v1/sessions", dependencies=[Depends(require_api_key)])
    async def revoke_all_sessions(request: Request, response: Response):
        store.revoke_all_admin_sessions()
        response.delete_cookie(key=session_cookie, path="/v1", samesite="strict")
        return {"revoked": True}

    async def deliver(agent_id: str):
        client = clients.get(agent_id)
        if client is None:
            return
        async with client.dispatch_lock:
            while True:
                pending = store.pending(agent_id)
                if not pending:
                    return
                for row in pending:
                    if clients.get(agent_id) is not client:
                        return
                    if not store.mark_sent(row["id"]):
                        continue
                    try:
                        await client.send({
                            "type": "job",
                            "id": row["id"],
                            "device_id": row["device_id"],
                            "operation": row["operation"],
                            "data_base64": row["data_base64"],
                            "options": json.loads(row["options_json"]),
                        })
                    except Exception:
                        # Mark uncertain, NEVER automatically replay a possibly printed job.
                        store.uncertain(agent_id)
                        return

    @app.get("/settings", response_class=HTMLResponse, include_in_schema=False)
    async def settings():
        return HTMLResponse(
            content=files("deviceshare").joinpath("settings.html").read_text(encoding="utf-8"),
            headers={
                "Cache-Control": "no-store",
                "Referrer-Policy": "no-referrer",
                "X-Frame-Options": "DENY",
                "Content-Security-Policy": (
                    "default-src 'none'; script-src 'unsafe-inline'; "
                    "style-src 'unsafe-inline'; connect-src 'self'; "
                    "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
                ),
            },
        )

    @app.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
    async def dashboard():
        return HTMLResponse(
            content=files("deviceshare").joinpath("dashboard.html").read_text(encoding="utf-8"),
            headers={
                "Cache-Control": "no-store",
                "Referrer-Policy": "no-referrer",
                "X-Frame-Options": "DENY",
                "Content-Security-Policy": (
                    "default-src 'none'; script-src 'unsafe-inline'; "
                    "style-src 'unsafe-inline'; connect-src 'self'; "
                    "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
                ),
            },
        )

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok", "service": "deviceshare"}

    @app.get("/v1/agents", dependencies=[Depends(require_api_key)])
    async def agents():
        paired = {row["agent_id"]: row for row in store.list_agent_credentials()}
        identifiers = sorted(set(paired) | set(clients))
        return [
            {
                "agent_id": agent_id,
                "online": agent_id in clients,
                "devices": clients[agent_id].devices if agent_id in clients else [],
                "credential_status": (
                    "revoked" if paired[agent_id]["revoked_at"] else "paired"
                ) if agent_id in paired else "legacy / unpaired",
            }
            for agent_id in identifiers
        ]

    @app.post("/v1/agents/{agent_id}/credential", dependencies=[Depends(require_api_key)])
    async def issue_credential(agent_id: str):
        if not re.fullmatch(r"[a-zA-Z0-9_.-]{1,80}", agent_id):
            raise HTTPException(status_code=422, detail="Invalid agent ID")
        token = store.issue_agent_credential(agent_id)
        conn = clients.get(agent_id)
        if conn is not None:
            # Rotation invalidates any existing connection immediately.
            store.uncertain(agent_id)
            await conn.ws.close(code=1012)
        return {"agent_id": agent_id, "token": token,
                "notice": "Store token on agent. This is shown once."}

    @app.delete("/v1/agents/{agent_id}/credential", dependencies=[Depends(require_api_key)])
    async def revoke_credential(agent_id: str):
        if not re.fullmatch(r"[a-zA-Z0-9_.-]{1,80}", agent_id):
            raise HTTPException(status_code=422, detail="Invalid agent ID")
        if not store.revoke_agent_credential(agent_id):
            raise HTTPException(status_code=404, detail="No active credential found")
        conn = clients.get(agent_id)
        if conn is not None:
            store.uncertain(agent_id)
            await conn.ws.close(code=1008)
        return {"agent_id": agent_id, "revoked": True}

    @app.get("/v1/jobs", dependencies=[Depends(require_api_key)])
    async def jobs(limit: int = 50):
        if not 1 <= limit <= 200:
            raise HTTPException(status_code=422, detail="limit must be 1..200")
        return store.list(limit=limit)

    @app.post("/v1/jobs", status_code=202, dependencies=[Depends(require_api_key)])
    async def submit(job: JobCreate):
        try:
            item = store.create(job.model_dump(mode="json"))
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        await deliver(job.agent_id)
        return item

    def submit_pdf_job(payload: PrintSubmission, pdf_data: bytes):
        connection = clients.get(payload.agent_id)
        if connection is None:
            raise HTTPException(status_code=409, detail="Selected agent is offline. No print job was created.")
        available = {d.get("id"): d for d in connection.devices if d.get("kind") == "printer"}
        printer = available.get(payload.device_id)
        if printer is None:
            raise HTTPException(status_code=409, detail="Printer not found in live station inventory. No job created.")
        if printer.get("state") == "disabled":
            raise HTTPException(status_code=409, detail="Selected CUPS queue is disabled. No job created.")
        if len(pdf_data) > 1024 * 1024:
            raise HTTPException(status_code=422, detail="Generated PDF exceeds 1 MiB")
        job = JobCreate(
            agent_id=payload.agent_id,
            device_id=payload.device_id,
            operation="print_document",
            data_base64=base64.b64encode(pdf_data).decode("ascii"),
            options={"mime_type": "application/pdf", "copies": payload.copies,
                     "media": payload.media, "sides": payload.sides},
        )
        return store.create(job.model_dump(mode="json"))

    @app.post("/v1/print/test", status_code=202, dependencies=[Depends(require_api_key)])
    async def print_test(payload: PrintSubmission):
        if payload.agent_id not in clients:
            raise HTTPException(status_code=409, detail="Selected agent is offline. No print job was created.")
        pdf = render_pdf(payload, test_page=True)
        job = submit_pdf_job(payload, pdf)
        await deliver(payload.agent_id)
        return {**job, "notice": "Sent to the selected station. OS spooler acceptance does not confirm physical output."}

    @app.post("/v1/print/text", status_code=202, dependencies=[Depends(require_api_key)])
    async def print_text(payload: TextSubmission):
        if payload.agent_id not in clients:
            raise HTTPException(status_code=409, detail="Selected agent is offline. No print job was created.")
        try:
            pdf = render_pdf(payload, test_page=False)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        job = submit_pdf_job(payload, pdf)
        await deliver(payload.agent_id)
        return {**job, "notice": "Text PDF sent to the selected station. Check the physical printer."}

    @app.websocket("/v1/agents/{agent_id}/ws")
    async def agent_socket(ws: WebSocket, agent_id: str):
        key = ws.headers.get("x-agent-token", "")
        valid_agent_id = re.fullmatch(r"[a-zA-Z0-9_.-]{1,80}", agent_id)
        paired = store.agent_credential_exists(agent_id) if valid_agent_id else False
        valid_credential = bool(valid_agent_id and (
            store.verify_agent_credential(agent_id, key) if paired
            else bool(agent_token and secrets.compare_digest(key, agent_token))
        ))
        if not valid_credential:
            await ws.close(code=1008)
            return
        await ws.accept()
        previous = clients.get(agent_id)
        if previous is not None:
            await previous.ws.close(code=1012)
            store.uncertain(agent_id)
        link = AgentConnection(ws=ws)
        clients[agent_id] = link
        try:
            await deliver(agent_id)
            while True:
                msg = await ws.receive_json()
                if not isinstance(msg, dict):
                    continue
                if msg.get("type") == "inventory":
                    raw = msg.get("devices", [])
                    if isinstance(raw, list):
                        link.devices = [
                            {"id": str(d["id"])[:300], "kind": str(d.get("kind", ""))[:40],
                             "label": str(d.get("label", ""))[:200],
                             "state": str(d.get("state", "unknown"))[:32]}
                            for d in raw[:200]
                            if isinstance(d, dict) and isinstance(d.get("id"), str)
                        ]
                elif msg.get("type") == "result" and isinstance(msg.get("id"), str):
                    successful = msg.get("success") is True
                    detail = msg.get("detail", {})
                    if not isinstance(detail, dict):
                        detail = {"message": str(detail)[:300]}
                    store.complete(msg["id"], agent_id, successful, detail)
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            if clients.get(agent_id) is link:
                del clients[agent_id]
                store.uncertain(agent_id)

    return app

def main():
    parser = argparse.ArgumentParser(description="DeviceShare HTTP hub")
    parser.add_argument("--version", action="version", version="DeviceShare Hub 0.2.0a4")
    parser.add_argument("--api-key-file", default=os.getenv("DEVICESHARE_API_KEY_FILE"),
                        help="Read administrator API key from a private file instead of shell environment")
    args = parser.parse_args()
    key = None
    if args.api_key_file:
        file_path = Path(args.api_key_file).expanduser()
        if os.name != "nt" and file_path.stat().st_mode & 0o077:
            parser.error("Administrator key file must have private permissions (chmod 600)")
        key = file_path.read_text(encoding="utf-8").strip()
    # Loopback by default. For remote access, put TLS and authentication in front.
    uvicorn.run(create_app(api_key=key), host=os.getenv("DEVICESHARE_HOST", "127.0.0.1"),
                port=int(os.getenv("DEVICESHARE_PORT", "8765")))

if __name__ == "__main__":
    main()
