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
