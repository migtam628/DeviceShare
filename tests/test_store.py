import pytest

from deviceshare.store import Store

def job(key=None):
    return {"agent_id": "station-01", "device_id": "sim:printer",
            "operation": "simulate", "data_base64": "aGVsbG8=",
            "options": {}, "idempotency_key": key}

def test_state_and_no_replay(tmp_path):
    store = Store(str(tmp_path / "jobs.db"))
    created = store.create(job())
    assert created["status"] == "queued"
    assert len(store.pending("station-01")) == 1
    assert store.mark_sent(created["id"])
    assert not store.mark_sent(created["id"])
    store.uncertain("station-01")
    assert not store.pending("station-01")
    assert store.list()[0]["status"] == "unknown"

def test_idempotency(tmp_path):
    store = Store(str(tmp_path / "jobs.db"))
    first = store.create(job("same"))
    assert store.create(job("same"))["id"] == first["id"]
    mismatch = job("same")
    mismatch["data_base64"] = "Y2hhbmdlZA=="
    with pytest.raises(ValueError):
        store.create(mismatch)

def test_result_transition(tmp_path):
    store = Store(str(tmp_path / "jobs.db"))
    created = store.create(job())
    assert not store.complete(created["id"], "station-01", True, {"ok": True})
    assert store.mark_sent(created["id"])
    assert not store.complete(created["id"], "other-agent", True, {"ok": True})
    assert store.complete(created["id"], "station-01", True, {"accepted": True})
    assert store.list()[0]["status"] == "accepted"
