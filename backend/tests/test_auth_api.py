from backend.app.infrastructure.security.session import SessionManager
from fastapi.testclient import TestClient


def test_health_is_public(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "tsuchibot-api"}


def test_backend_root_redirects_to_api_documentation(client: TestClient) -> None:
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/docs"


def test_protected_endpoint_requires_session(client: TestClient) -> None:
    response = client.get("/api/v1/runs")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_login_session_and_logout(client: TestClient) -> None:
    bad = client.post("/api/v1/auth/login", json={"password": "wrong"})
    assert bad.status_code == 401

    login = client.post("/api/v1/auth/login", json={"password": "correct-horse"})
    assert login.status_code == 200
    assert login.json()["authenticated"] is True
    cookie = login.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie

    session = client.get("/api/v1/auth/session")
    assert session.status_code == 200
    assert session.json()["authenticated"] is True

    logout = client.post("/api/v1/auth/logout")
    assert logout.status_code == 204
    assert client.get("/api/v1/runs").status_code == 401


def test_login_is_rate_limited_per_client_after_five_failures(client: TestClient) -> None:
    for _ in range(5):
        assert client.post("/api/v1/auth/login", json={"password": "wrong"}).status_code == 401
    blocked = client.post("/api/v1/auth/login", json={"password": "correct-horse"})
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "RATE_LIMITED"
    assert int(blocked.headers["retry-after"]) > 0


def test_cross_site_login_logout_and_dispatch_are_rejected(client: TestClient) -> None:
    headers = {"Origin": "https://untrusted.example"}
    assert (
        client.post("/api/v1/auth/login", headers=headers, json={"password": "x"}).status_code
        == 403
    )
    assert client.post("/api/v1/auth/login", json={"password": "correct-horse"}).status_code == 200
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 403
    assert (
        client.post(
            "/api/v1/runs/dispatch",
            headers={"Sec-Fetch-Site": "cross-site"},
            json={"mode": "incremental"},
        ).status_code
        == 403
    )


def test_large_request_is_rejected_before_parsing(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        content=b"x" * (1024 * 1024 + 1),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "REQUEST_TOO_LARGE"


def test_large_streamed_request_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        content=iter([b"x" * 700_000, b"x" * 400_000]),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413


def test_malformed_signed_cookie_is_treated_as_unauthenticated() -> None:
    manager = SessionManager("test-secret", 60)
    malformed = "a."
    signature = manager._sign(malformed.split(".", maxsplit=1)[0])
    assert manager.verify(f"a.{signature}") is None
