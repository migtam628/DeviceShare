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

from .auth import check_password, new_password_record, normalize_email, validate_password

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
            CREATE TABLE IF NOT EXISTS admin_account (
                singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                email TEXT NOT NULL UNIQUE,
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                failed_logins INTEGER NOT NULL DEFAULT 0,
                locked_until INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS activation_codes (
                singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                purpose TEXT NOT NULL CHECK(purpose IN ('activate','reset')),
                code_sha256 TEXT NOT NULL,
                expires_at INTEGER NOT NULL,
                failed_attempts INTEGER NOT NULL DEFAULT 0
            );
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

    def admin_account(self) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT email,password_hash FROM admin_account WHERE singleton=1").fetchone()
        return dict(row) if row else None

    def issue_activation_code(self, purpose: str = "activate") -> str:
        if purpose not in ("activate", "reset"):
            raise ValueError("Unsupported activation code purpose")
        account_exists = self.admin_account() is not None
        if (purpose == "activate" and account_exists) or (purpose == "reset" and not account_exists):
            raise ValueError("Activation state does not allow this operation")
        code = secrets.token_urlsafe(12)  # 96 bits of entropy; shown only once.
        digest = hashlib.sha256(code.encode("ascii")).hexdigest()
        with self.connect() as db:
            db.execute(
                "INSERT INTO activation_codes(singleton,purpose,code_sha256,expires_at,failed_attempts) "
                "VALUES(1,?,?,?,0) ON CONFLICT(singleton) DO UPDATE SET purpose=excluded.purpose, "
                "code_sha256=excluded.code_sha256, expires_at=excluded.expires_at, failed_attempts=0",
                (purpose, digest, int(time.time()) + 600),
            )
        return code

    @staticmethod
    def _check_setup_code(db, code: str, purpose: str) -> None:
        row = db.execute("SELECT * FROM activation_codes WHERE singleton=1").fetchone()
        if not row or row["purpose"] != purpose or row["expires_at"] <= int(time.time()) or row["failed_attempts"] >= 5:
            raise ValueError("Setup code expired or invalid. Generate a new code on the host.")
        digest = hashlib.sha256(code.encode("utf-8")).hexdigest() if isinstance(code, str) and len(code) <= 128 else ""
        if not hmac.compare_digest(row["code_sha256"], digest):
            db.execute("UPDATE activation_codes SET failed_attempts=failed_attempts+1 WHERE singleton=1")
            raise ValueError("Incorrect setup code. Generate a new code after five failed attempts.")

    def activate_admin(self, code: str, email: str, password: str) -> str:
        email = normalize_email(email)
        salt, digest = new_password_record(password)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM admin_account WHERE singleton=1").fetchone():
                raise ValueError("An administrator account already exists")
            self._check_setup_code(db, code, "activate")
            db.execute(
                "INSERT INTO admin_account(singleton,email,password_salt,password_hash,created_at) "
                "VALUES(1,?,?,?,?)", (email, salt, digest, now())
            )
            db.execute("DELETE FROM activation_codes")
            db.execute("DELETE FROM admin_sessions")
        return email

    def verify_admin_password(self, email: str, password: str) -> tuple[bool, str]:
        try:
            email = normalize_email(email)
        except ValueError:
            email = ""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM admin_account WHERE singleton=1").fetchone()
            if not row:
                return False, "not_setup"
            if row["locked_until"] > int(time.time()):
                return False, "rate_limited"
            valid = email == row["email"] and check_password(password, row["password_salt"], row["password_hash"])
            if valid:
                db.execute("UPDATE admin_account SET failed_logins=0,locked_until=0 WHERE singleton=1")
                return True, "ok"
            failures = row["failed_logins"] + 1
            lock = int(time.time()) + 60 if failures >= 5 else 0
            db.execute(
                "UPDATE admin_account SET failed_logins=?,locked_until=? WHERE singleton=1",
                (0 if lock else failures, lock),
            )
        return False, "invalid"

    def change_admin_password(self, current: str, new: str) -> None:
        salt, digest = new_password_record(new)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM admin_account WHERE singleton=1").fetchone()
            if not row or not check_password(current, row["password_salt"], row["password_hash"]):
                raise ValueError("Current password is incorrect")
            db.execute(
                "UPDATE admin_account SET password_salt=?,password_hash=?,failed_logins=0,locked_until=0 WHERE singleton=1",
                (salt, digest),
            )
            db.execute("DELETE FROM admin_sessions")

    def reset_admin_password(self, email: str, code: str, new: str) -> None:
        email = normalize_email(email)
        salt, digest = new_password_record(new)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM admin_account WHERE singleton=1").fetchone()
            if row is None or row["email"] != email:
                raise ValueError("Recovery code or email is invalid")
            self._check_setup_code(db, code, "reset")
            db.execute("UPDATE admin_account SET password_salt=?, password_hash=?, failed_logins=0,locked_until=0 WHERE singleton=1", (salt, digest))
            db.execute("DELETE FROM admin_sessions")
            db.execute("DELETE FROM activation_codes")
