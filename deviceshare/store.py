"""SQLite job ledger; no automatic retry after a job is sent to hardware."""
import json
import sqlite3
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
            """)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        return db

    @staticmethod
    def public(row):
        item = dict(row)
        item.pop("data_base64", None)
        item["options"] = json.loads(item.pop("options_json"))
        item["result"] = json.loads(item.pop("result_json")) if item.get("result_json") else None
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
