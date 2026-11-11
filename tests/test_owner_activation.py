"""First-run email/password activation, login, recovery and session safety."""
from fastapi.testclient import TestClient
from deviceshare.hub import create_app

HOST_KEY = "host-integration-key-long-enough-123456"
BASE = "http://127.0.0.1:8765"
CSRF = {"X-DeviceShare-CSRF": "1"}


def make_client(tmp_path):
    return TestClient(create_app(store_path=str(tmp_path / "owner.sqlite"), api_key=HOST_KEY), base_url=BASE)


def issue_code(client, purpose="activate"):
    response = client.post("/v1/auth/code", json={"purpose": purpose},
                           headers={"X-API-Key": HOST_KEY})
    assert response.status_code == 200, response.text
    assert response.json()["expires_in"] == 600
    return response.json()["code"]


def activate(client, code):
    response = client.post("/v1/auth/activate", headers=CSRF,
                           json={"code": code, "email": "  ADMIN@EXAMPLE.COM  ",
                                 "password": "A longer secure passphrase 123!", "remember": True})
    assert response.status_code == 201, response.text
    assert response.json()["email"] == "admin@example.com"
    assert "httponly" in response.headers["set-cookie"].lower()
    return client.cookies.get("deviceshare_admin_session")


def test_local_activation_login_recovery_and_rotation(tmp_path):
    with make_client(tmp_path) as client:
        assert client.get("/v1/auth/status").json()["activated"] is False
        assert client.post("/v1/auth/code", json={"purpose": "activate"}).status_code == 401
        code = issue_code(client)
        bad = client.post("/v1/auth/activate", headers=CSRF,
                          json={"code": "fake", "email": "admin@example.com",
                                "password": "A longer secure passphrase 123!"})
        assert bad.status_code == 422
        token = activate(client, code)
        assert token and HOST_KEY not in token
        assert client.get("/v1/auth/status").json() == {
            "activated": True, "authenticated": True, "email": "admin@example.com"}
        assert client.get("/v1/agents").status_code == 200
        assert client.post("/v1/auth/code", json={"purpose": "activate"},
                           headers={"X-API-Key": HOST_KEY}).status_code == 409
        assert client.post("/v1/session", json={"api_key": HOST_KEY}).status_code == 410
        # Changing a password forces all remembered browsers to authenticate again.
        changed = client.post("/v1/auth/password", headers=CSRF, json={
            "current_password": "A longer secure passphrase 123!",
            "new_password": "A different secure passphrase 456!"
        })
        assert changed.status_code == 200
        assert client.get("/v1/auth/status").json()["authenticated"] is False
        invalid = client.post("/v1/auth/login", headers=CSRF,
                              json={"email": "admin@example.com",
                                    "password": "A longer secure passphrase 123!"})
        assert invalid.status_code == 401
        success = client.post("/v1/auth/login", headers=CSRF,
                              json={"email": "ADMIN@EXAMPLE.COM",
                                    "password": "A different secure passphrase 456!",
                                    "remember": True})
        assert success.status_code == 200
        assert client.get("/v1/auth/status").json()["authenticated"]
        reset_code = issue_code(client, "reset")
        reset = client.post("/v1/auth/reset", headers=CSRF,
                            json={"email": "admin@example.com", "code": reset_code,
                                  "new_password": "Recovery password example 789!"})
        assert reset.status_code == 200
        assert client.get("/v1/auth/status").json()["authenticated"] is False
        success = client.post("/v1/auth/login", headers=CSRF,
                              json={"email": "admin@example.com",
                                    "password": "Recovery password example 789!"})
        assert success.status_code == 200

    # New hub process with the same database and host secret preserves sessions.
    with make_client(tmp_path) as client:
        assert client.get("/v1/auth/status").json()["activated"] is True
        login = client.post("/v1/auth/login", headers=CSRF,
                            json={"email": "admin@example.com",
                                  "password": "Recovery password example 789!", "remember": True})
        assert login.status_code == 200
        assert client.get("/v1/agents").status_code == 200


def test_login_throttling_and_setup_origin(tmp_path):
    with make_client(tmp_path) as client:
        code = issue_code(client)
        assert client.post("/v1/auth/activate", headers={**CSRF, "Origin": "https://evil.test"},
                           json={"code": code, "email": "admin@example.com",
                                 "password": "A longer secure passphrase 123!"}).status_code == 403
        activate(client, code)
        assert client.delete("/v1/session", headers=CSRF).status_code == 200
        for i in range(5):
            result = client.post("/v1/auth/login", headers=CSRF,
                                 json={"email": "admin@example.com", "password": "wrong"})
            assert result.status_code == 401
        assert client.post("/v1/auth/login", headers=CSRF, json={
            "email": "admin@example.com", "password": "A longer secure passphrase 123!"
        }).status_code == 429


def test_activation_code_five_attempt_limit(tmp_path):
    with make_client(tmp_path) as client:
        code = issue_code(client)
        for _ in range(5):
            result = client.post("/v1/auth/activate", headers=CSRF, json={
                "code": "wrong", "email": "admin@example.com",
                "password": "A longer secure passphrase 123!"
            })
            assert result.status_code == 422
        assert client.post("/v1/auth/activate", headers=CSRF, json={
            "code": code, "email": "admin@example.com",
            "password": "A longer secure passphrase 123!"
        }).status_code == 422
        new_code = issue_code(client)
        assert activate(client, new_code)


def test_no_remote_http_password_submission(tmp_path):
    with TestClient(create_app(store_path=str(tmp_path / "remote.db"), api_key=HOST_KEY),
                    base_url="http://device.example.com") as client:
        assert client.post("/v1/auth/login", headers=CSRF,
                           json={"email": "x@y.com", "password": "hello"}).status_code == 400


def test_cli_setup_and_host_recovery_codes(tmp_path, monkeypatch, capsys):
    import sys
    from deviceshare import hub

    dbpath = str(tmp_path / "standalone.sqlite")
    monkeypatch.setenv("DEVICESHARE_DB", dbpath)
    monkeypatch.setattr(sys, "argv", ["deviceshare-hub", "--issue-activation-code"])
    hub.main()
    output = capsys.readouterr().out
    assert "expires in 10 minutes" in output
    code = output.split(": ", 1)[-1].strip()
    with TestClient(create_app(store_path=dbpath, api_key=HOST_KEY), base_url=BASE) as client:
        activate(client, code)

    monkeypatch.setattr(sys, "argv", ["deviceshare-hub", "--issue-recovery-code"])
    hub.main()
    output = capsys.readouterr().out
    assert "reset code" in output
    reset_code = output.split(": ", 1)[-1].strip()
    with TestClient(create_app(store_path=dbpath, api_key=HOST_KEY), base_url=BASE) as client:
        response = client.post("/v1/auth/reset", headers=CSRF, json={
            "code": reset_code, "email": "admin@example.com",
            "new_password": "Changed by recovery token 123!"
        })
        assert response.status_code == 200, response.text


def test_legacy_session_cannot_complete_owner_activation(tmp_path):
    with make_client(tmp_path) as client:
        assert client.post("/v1/session", json={"api_key": HOST_KEY}).status_code == 200
        assert client.get("/v1/auth/status").json() == {
            "activated": False, "authenticated": False, "email": None
        }
