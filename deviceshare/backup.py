"""Offline owner commands for safe, private snapshots of the Hub SQLite ledger.

No HTTP endpoint deliberately: the ledger includes credentials and raw job payloads.
The SQLite backup API creates a consistent snapshot while the live Hub is running.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path


REQUIRED_TABLES = frozenset({
    "jobs", "agent_credentials", "admin_sessions", "admin_account", "activation_codes",
})


def _existing_database(path: str | Path) -> Path:
    source = Path(path).expanduser()
    if source.is_symlink() or not source.is_file():
        raise ValueError("Database must be an existing regular file (not a symlink)")
    return source.resolve(strict=True)


def _read_only(path: Path) -> sqlite3.Connection:
    # Read-only is important: sqlite3.connect(path) would create a missing DB.
    return sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=30)


def _validate_connection(db: sqlite3.Connection) -> None:
    status = db.execute("PRAGMA integrity_check").fetchone()
    if status != ("ok",):
        raise ValueError("SQLite integrity check failed")
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not REQUIRED_TABLES.issubset(tables):
        raise ValueError("Not a complete DeviceShare Hub database")


def verify_database(path: str | Path) -> None:
    """Reject corrupt, absent or unrelated databases without modifying them."""
    with closing(_read_only(_existing_database(path))) as db:
        _validate_connection(db)


def _copy_snapshot(source: Path, destination: Path) -> None:
    if destination.is_symlink() or destination.exists():
        raise FileExistsError(f"Target already exists: {destination}")
    if destination.resolve() == source:
        raise ValueError("Source and target must be different")
    if any(Path(str(destination) + suffix).exists() for suffix in ("-wal", "-shm", "-journal")):
        raise FileExistsError("Target has SQLite sidecar files; choose a fresh destination")

    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # The temp is private before any sensitive bytes are written; publish atomically.
    descriptor, temp_name = tempfile.mkstemp(prefix=".deviceshare-", suffix=".db", dir=destination.parent)
    temp = Path(temp_name)
    try:
        os.chmod(temp, 0o600)
        os.close(descriptor)
        descriptor = -1
        with closing(_read_only(source)) as live, closing(sqlite3.connect(str(temp))) as snapshot:
            _validate_connection(live)
            live.backup(snapshot, pages=128, sleep=0.05)
            _validate_connection(snapshot)
        # Hard-link creation is exclusive (fails if destination appeared mid-backup).
        # Unlike os.replace, it cannot overwrite an existing database.
        os.link(temp, destination)
    finally:
        if descriptor != -1:
            os.close(descriptor)
        temp.unlink(missing_ok=True)


def backup_database(source: str | Path, destination: str | Path) -> None:
    """Back up a live Hub to a new local file. Never overwrite an old backup."""
    _copy_snapshot(_existing_database(source), Path(destination).expanduser())


def restore_database(backup: str | Path, destination: str | Path) -> None:
    """Restore into a fresh path, never over a live/previous Hub database.

    Stop the Hub before pointing DEVICESHARE_DB at the restored path. Store startup
    marks any previously 'sent' jobs 'unknown' to avoid automatically reprinting.
    """
    _copy_snapshot(_existing_database(backup), Path(destination).expanduser())
