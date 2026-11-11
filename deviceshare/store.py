from __future__ import annotations

"""SQLite job ledger; no automatic retry after a job is sent to hardware."""
import hashlib
import hmac
import json
import secrets
import sqlite3
import time
from contextlib import contextmanager
import uuid
from datetime import datetime, timezone
from pathlib import Path

def now():
    return datetime.now(timezone.utc).isoformat()

class Store:
    def __init__(self, path: str):
        self.path = str(Path(path).expanduser())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                device_id TEXT NOT NULL,
                operation TEXT NOT NULL,
                data_base64 TEXT NOT NULL,
                options_json TEXT NOT NULL,
                idempotency_key TEXT,
                status TEXT NOT NULL,
                result_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(agent_id, idempotency_key)
            );
            CREATE INDEX IF NOT EXISTS idx_jobs_agent_status
                ON jobs(agent_id, status, created_at);
            CREATE TABLE IF NOT EXISTS agent_credentials (
                agent_id TEXT PRIMARY KEY,
                token_sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL,
                revoked_at TEXT
            );
            CREATE TABLE IF NOT EXISTS admin_sessions (
                token_sha256 TEXT PRIMARY KEY,
                api_key_fingerprint TEXT NOT NULL,
                expires_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_admin_sessions_expiry ON admin_sessions(expires_at);
            """)
            # Crash recovery: sent jobs may have reached hardware. Never replay.
            db.execute("UPDATE jobs SET status='unknown', updated_at=? WHERE status='sent'", (now(),))

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def public(row):
        item = dict(row)
        item.pop("data_base64", None)
        item["options"] = json.loads(item.pop("options_json"))
        result_json = item.pop("result_json")
        item["result"] = json.loads(result_json) if result_json else None
        return item

    def create(self, job: dict):
        with self.connect() as db:
            if job.get("idempotency_key"):
                old = db.execute(
                    "SELECT * FROM jobs WHERE agent_id=? AND idempotency_key=?",
                    (job["agent_id"], job["idempotency_key"])
                ).fetchone()
                if old:
                    if (old["device_id"], old["operation"], old["data_base64"], old["options_json"]) != (
                        job["device_id"], job["operation"], job["data_base64"],
                        json.dumps(job.get("options", {}), sort_keys=True)):
                        raise ValueError("idempotency key already used for different job")
                    return self.public(old)
            timestamp = now()
            row = {
                "id": uuid.uuid4().hex,
                "agent_id": job["agent_id"],
                "device_id": job["device_id"],
                "operation": job["operation"],
                "data_base64": job["data_base64"],
                "options_json": json.dumps(job.get("options", {}), sort_keys=True),
                "idempotency_key": job.get("idempotency_key"),
                "status": "queued",
                "result_json": None,
                "created_at": timestamp,
                "updated_at": timestamp,
            }
            db.execute(
                "INSERT INTO jobs VALUES (:id,:agent_id,:device_id,:operation,:data_base64,"
                ":options_json,:idempotency_key,:status,:result_json,:created_at,:updated_at)", row
            )
            return self.public(row)

    def list(self, limit=50):
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self.public(row) for row in rows]

    def pending(self, agent_id: str):
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM jobs WHERE agent_id=? AND status='queued' "
                "ORDER BY created_at LIMIT 50", (agent_id,)
            ).fetchall()
        return [dict(row) for row in rows]

    def mark_sent(self, job_id: str):
        with self.connect() as db:
            return db.execute(
                "UPDATE jobs SET status='sent',updated_at=? WHERE id=? AND status='queued'",
                (now(), job_id)
            ).rowcount == 1

    def complete(self, job_id: str, agent_id: str, success: bool, detail: dict):
        with self.connect() as db:
            return db.execute(
                "UPDATE jobs SET status=?,result_json=?,updated_at=? "
                "WHERE id=? AND agent_id=? AND status='sent'",
                ("accepted" if success else "failed", json.dumps(detail), now(), job_id, agent_id)
            ).rowcount == 1

    def uncertain(self, agent_id: str):
        with self.connect() as db:
            db.execute(
                "UPDATE jobs SET status='unknown',updated_at=? "
                "WHERE agent_id=? AND status='sent'", (now(), agent_id)
            )

    def issue_agent_credential(self, agent_id: str) -> str:
        """Generate a high-entropy token, storing only its SHA-256 digest."""
        token = secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO agent_credentials "
                "(agent_id, token_sha256, created_at, revoked_at) VALUES (?, ?, ?, NULL)",
                (agent_id, digest, now()),
            )
        return token

    def verify_agent_credential(self, agent_id: str, token: str) -> bool:
        if not token or len(token) > 512:
            return False
        with self.connect() as db:
            row = db.execute(
                "SELECT token_sha256, revoked_at FROM agent_credentials WHERE agent_id=?",
                (agent_id,),
            ).fetchone()
        return bool(
            row and row["revoked_at"] is None
            and hmac.compare_digest(
                row["token_sha256"],
                hashlib.sha256(token.encode("utf-8")).hexdigest(),
            )
        )

    def agent_credential_exists(self, agent_id: str) -> bool:
        with self.connect() as db:
            row = db.execute(
                "SELECT 1 FROM agent_credentials WHERE agent_id=?", (agent_id,)
            ).fetchone()
        return row is not None

    def list_agent_credentials(self) -> list[dict]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT agent_id, created_at, revoked_at FROM agent_credentials "
                "ORDER BY agent_id"
            ).fetchall()
        return [dict(row) for row in rows]

    def revoke_agent_credential(self, agent_id: str) -> bool:
        with self.connect() as db:
            return db.execute(
                "UPDATE agent_credentials SET revoked_at=? "
                "WHERE agent_id=? AND revoked_at IS NULL",
                (now(), agent_id),
            ).rowcount == 1

    def issue_admin_session(self, api_key_fingerprint: str, ttl_seconds: int) -> str:
        """Opaque session cookie; raw admin API key is never placed in the cookie or DB."""
        token = secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode("ascii")).hexdigest()
        expires_at = int(time.time()) + ttl_seconds
        with self.connect() as db:
            db.execute("DELETE FROM admin_sessions WHERE expires_at <= ?", (int(time.time()),))
            db.execute(
                "INSERT INTO admin_sessions(token_sha256,api_key_fingerprint,expires_at) "
                "VALUES(?,?,?)", (digest, api_key_fingerprint, expires_at))
        return token

    def verify_admin_session(self, token: str | None, fingerprint: str) -> bool:
        if not token or len(token) > 256:
            return False
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self.connect() as db:
            row = db.execute(
                "SELECT api_key_fingerprint,expires_at FROM admin_sessions "
                "WHERE token_sha256=?", (digest,)).fetchone()
        return bool(row and row["expires_at"] > int(time.time())
                    and hmac.compare_digest(row["api_key_fingerprint"], fingerprint))

    def revoke_admin_session(self, token: str | None) -> None:
        if not token or len(token) > 256:
            return
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self.connect() as db:
            db.execute("DELETE FROM admin_sessions WHERE token_sha256=?", (digest,))

    def revoke_all_admin_sessions(self) -> None:
        with self.connect() as db:
            db.execute("DELETE FROM admin_sessions")
