"""Recovery protects sensitive data and avoids accidental job replay."""

import os
import sqlite3
import subprocess
import sys

import pytest

from deviceshare.backup import backup_database, restore_database, verify_database
from deviceshare.store import Store


def test_live_snapshot_preserves_job_and_credentials_and_is_private(tmp_path):
    source = tmp_path / "hub.db"
    store = Store(str(source))
    token = store.issue_agent_credential("a")
    code = store.issue_activation_code()
    store.activate_admin(code, "owner@example.test", "long-secure-test-password")
    created = store.create({
        "agent_id": "a", "device_id": "sim:printer", "operation": "simulate",
        "data_base64": "c2Vuc2l0aXZl", "options": {},
    })
    assert store.mark_sent(created["id"])

    # Live writes may continue; backup API must snapshot committed transactions.
    backup = tmp_path / "private" / "snapshot.db"
    backup_database(source, backup)
    verify_database(backup)
    if os.name != "nt":
        assert backup.stat().st_mode & 0o077 == 0
    assert Store(str(tmp_path / "not-the-backup.db")).list() == []
    with sqlite3.connect(backup) as db:
        assert db.execute("SELECT data_base64,status FROM jobs").fetchone() == (
            "c2Vuc2l0aXZl", "sent",
        )

    target = tmp_path / "new" / "restored.db"
    restore_database(backup, target)
    verify_database(target)
    restored = Store(str(target))
    assert restored.verify_agent_credential("a", token)
    assert restored.verify_admin_password("owner@example.test", "long-secure-test-password") == (True, "ok")
    assert restored.list()[0]["status"] == "unknown"
    assert restored.pending("a") == []


def test_backup_and_restore_refuse_overwrite(tmp_path):
    source = tmp_path / "hub.db"
    Store(str(source))
    target = tmp_path / "snapshot.db"
    backup_database(source, target)
    before = target.read_bytes()
    with pytest.raises(FileExistsError):
        backup_database(source, target)
    with pytest.raises(FileExistsError):
        restore_database(target, source)
    assert target.read_bytes() == before
    assert not list(tmp_path.glob(".deviceshare-*"))


def test_missing_corrupt_and_unrelated_files_are_rejected(tmp_path):
    missing = tmp_path / "no-db.db"
    out = tmp_path / "out.db"
    with pytest.raises(ValueError, match="existing regular"):
        backup_database(missing, out)
    assert not missing.exists() and not out.exists()

    corrupt = tmp_path / "corrupt.db"
    corrupt.write_bytes(b"not a SQLite database")
    with pytest.raises((ValueError, sqlite3.DatabaseError)):
        backup_database(corrupt, out)
    assert not out.exists()

    unrelated = tmp_path / "unrelated.db"
    sqlite3.connect(unrelated).close()
    with pytest.raises(ValueError, match="complete DeviceShare"):
        verify_database(unrelated)


def test_no_symlink_or_leftover_sidecars(tmp_path):
    source = tmp_path / "hub.db"
    Store(str(source))
    link = tmp_path / "link.db"
    try:
        link.symlink_to(source)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks unavailable")
    with pytest.raises(ValueError):
        backup_database(link, tmp_path / "snapshot.db")
    with pytest.raises(FileExistsError):
        backup_database(source, link)
    destination = tmp_path / "recovered.db"
    (tmp_path / "recovered.db-wal").touch()
    with pytest.raises(FileExistsError, match="sidecar"):
        backup_database(source, destination)


def test_hub_cli_backup_verify_restore(tmp_path):
    source = tmp_path / "hub.db"
    Store(str(source))
    backup = tmp_path / "backup.db"
    restored = tmp_path / "restored.db"

    def run(*args):
        return subprocess.run(
            [sys.executable, "-m", "deviceshare.hub", "--db", str(source), *args],
            capture_output=True, text=True, timeout=30,
        )

    assert run("--backup-db", str(backup)).returncode == 0
    assert run("--verify-db", str(backup)).returncode == 0
    assert run("--restore-db", str(backup), "--restore-to", str(restored)).returncode == 0
    assert restored.is_file()
    assert run("--backup-db", str(backup)).returncode != 0
    assert run("--restore-db", str(backup)).returncode != 0
