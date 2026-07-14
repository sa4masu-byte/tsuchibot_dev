from typing import Any
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

SESSION_ID = uuid4()


class FakeECReviewRepository:
    async def list_sessions(self, limit: int) -> list[dict[str, Any]]:
        return [{"id": str(SESSION_ID), "status": "completed", "limit": limit}]

    async def session_detail(self, session_id: UUID) -> dict[str, Any] | None:
        if session_id != SESSION_ID:
            return None
        return {
            "session": {"id": str(SESSION_ID), "status": "completed"},
            "attempts": [{"source": "amazon", "keyword": "収納 ケース"}],
            "offers": [{"source": "amazon", "eligibility": "eligible"}],
        }


def test_ec_review_requires_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/ec/sessions").status_code == 401


def test_ec_review_list_and_detail(client: TestClient) -> None:
    client.app.state.ec_review_repository = FakeECReviewRepository()
    client.post("/api/v1/auth/login", json={"password": "correct-horse"})
    sessions = client.get("/api/v1/ec/sessions?limit=10")
    assert sessions.status_code == 200
    assert sessions.json()[0]["limit"] == 10
    detail = client.get(f"/api/v1/ec/sessions/{SESSION_ID}")
    assert detail.status_code == 200
    assert detail.json()["offers"][0]["eligibility"] == "eligible"
    assert client.get(f"/api/v1/ec/sessions/{uuid4()}").status_code == 404
