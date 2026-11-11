"""Persistent admin browser sessions are opaque, revocable, and CSRF guarded."""
from fastapi.testclient import TestClient
from deviceshare.hub import create_app

ADMIN = "super-secret-admin-key-for-session-test"
BASE = "http://127.0.0.1:8765"


def test_remember_login_persists_restarts_without_saving_raw_key(tmp_path):
    database = str(tmp_path / "hub.sqlite")
    app = create_app(store_path=database, api_key=ADMIN)
    with TestClient(app, base_url=BASE) as client:
        assert client.get("/v1/session").json() == {"authenticated": False}
        assert client.get("/v1/jobs").status_code == 401
        reply = client.post("/v1/session", json={"api_key": ADMIN, "remember": True})
        assert reply.status_code == 200
        cookie = reply.headers.get("set-cookie", "")
        assert "HttpOnly" in cookie and "SameSite=strict" in cookie
        assert "Max-Age=2592000" in cookie
        assert ADMIN not in cookie
        assert ADMIN not in str(client.cookies)
        assert client.get("/v1/session").json() == {"authenticated": True}
        assert client.get("/v1/agents").status_code == 200
        # Cookie requests cannot mutate anything without a CSRF header.
        assert client.post("/v1/agents/station/credential").status_code == 403
        assert client.post(
            "/v1/agents/station/credential", headers={"X-DeviceShare-CSRF": "1"}
        ).status_code == 200
        cookie_val = client.cookies.get("deviceshare_admin_session")
        assert cookie_val
        with app.state.store.connect() as db:
            row = db.execute("SELECT * FROM admin_sessions").fetchone()
            assert row is not None and cookie_val not in str(dict(row))
            assert ADMIN not in str(dict(row))
        assert client.get("/settings").status_code == 200
        assert ADMIN not in client.get("/settings").text

    # A restarted Hub with the same administrator secret and DB can restore the cookie.
    app2 = create_app(store_path=database, api_key=ADMIN)
    with TestClient(app2, base_url=BASE, cookies={"deviceshare_admin_session": cookie_val}) as client:
        assert client.get("/v1/session").json()["authenticated"]
        assert client.delete("/v1/session").status_code == 403
        reply = client.delete("/v1/session", headers={"X-DeviceShare-CSRF": "1"})
        assert reply.status_code == 200
        assert client.get("/v1/session").json() == {"authenticated": False}


def test_session_cookie_origin_and_api_key_rotation(tmp_path):
    path = str(tmp_path / "hub.sqlite")
    with TestClient(create_app(store_path=path, api_key=ADMIN), base_url=BASE) as client:
        assert client.post("/v1/session", json={"api_key": "invalid", "remember": True}).status_code == 401
        bad = client.post("/v1/session", json={"api_key": ADMIN, "remember": True},
                          headers={"Origin": "https://attacker.invalid"})
        assert bad.status_code == 403
        response = client.post("/v1/session", json={"api_key": ADMIN, "remember": False})
        assert response.status_code == 200
        assert "Max-Age" not in response.headers.get("set-cookie", "")
        token = client.cookies.get("deviceshare_admin_session")
        assert token
        assert client.delete("/v1/sessions", headers={"Origin": "https://attacker.invalid",
                                                      "X-DeviceShare-CSRF": "1"}).status_code == 403
        assert client.delete("/v1/sessions", headers={"X-DeviceShare-CSRF": "1"}).status_code == 200
        assert client.get("/v1/session").json()["authenticated"] is False

    with TestClient(create_app(store_path=path, api_key="changed-admin-key-for-session-test"),
                    base_url=BASE, cookies={"deviceshare_admin_session": token}) as client:
        assert client.get("/v1/session").json()["authenticated"] is False


def test_explicit_api_key_clients_still_work(tmp_path):
    with TestClient(create_app(store_path=str(tmp_path / "hub.sqlite"), api_key=ADMIN),
                    base_url=BASE) as client:
        headers = {"X-API-Key": ADMIN}
        assert client.get("/v1/agents", headers=headers).status_code == 200
        assert client.post("/v1/agents/station/credential", headers=headers).status_code == 200
        assert client.post("/v1/session", json={"api_key": ADMIN, "remember": True}).status_code == 200
        # A bad API header must not be bypassed via valid cookies.
        assert client.get("/v1/agents", headers={"X-API-Key": "wrong"}).status_code == 401


def test_remote_plain_http_login_rejected(tmp_path):
    with TestClient(create_app(store_path=str(tmp_path / "hub.sqlite"), api_key=ADMIN),
                    base_url="http://remote.example.test") as client:
        assert client.post("/v1/session", json={"api_key": ADMIN, "remember": True}).status_code == 400
        assert client.get("/settings").headers["cache-control"] == "no-store"
