from typing import Any
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

PRODUCT_ID = uuid4()
COMPARABLE_ID = uuid4()


class FakeReviewRepository:
    def __init__(self) -> None:
        self.commands: list[tuple[str, Any]] = []

    async def dashboard(self) -> dict[str, Any]:
        return {"tier_counts": {"recommended": 1}, "open_error_count": 0}

    async def list_products(self, **filters: Any) -> list[dict[str, Any]]:
        return [{"canonical_product_id": str(PRODUCT_ID), "filters": filters}]

    async def product_detail(self, product_id: UUID) -> dict[str, Any] | None:
        if product_id != PRODUCT_ID:
            return None
        return {
            "product": {"id": str(PRODUCT_ID), "display_name": "テスト商品"},
            "comparables": [],
            "recommendation": {"recommendation_tier": "candidate"},
        }

    async def create_correction(
        self,
        product_id: UUID,
        field_name: str,
        corrected_value: object,
        reason: str | None,
        actor: str,
        idempotency_key: str,
    ) -> dict[str, UUID]:
        if product_id != PRODUCT_ID:
            raise KeyError(product_id)
        self.commands.append(
            ("correction", (field_name, corrected_value, reason, actor, idempotency_key))
        )
        return _context()

    async def set_comparable_decision(
        self,
        product_id: UUID,
        comparable_id: UUID,
        **command: Any,
    ) -> dict[str, UUID]:
        if product_id != PRODUCT_ID or comparable_id != COMPARABLE_ID:
            raise KeyError(comparable_id)
        self.commands.append(("comparable", command))
        return _context()


class FakeRecalculate:
    def __init__(self) -> None:
        self.calls: list[dict[str, UUID]] = []

    async def execute(self, context: dict[str, UUID]) -> object:
        self.calls.append(context)
        return object()


def _context() -> dict[str, UUID]:
    return {
        "source_product_id": uuid4(),
        "research_session_id": uuid4(),
        "run_id": uuid4(),
    }


def _configure(client: TestClient) -> tuple[FakeReviewRepository, FakeRecalculate]:
    repository = FakeReviewRepository()
    recalculate = FakeRecalculate()
    client.app.state.review_repository = repository
    client.app.state.recalculate_reviewed_product = recalculate
    client.post("/api/v1/auth/login", json={"password": "correct-horse"})
    return repository, recalculate


def test_review_reads_require_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/dashboard").status_code == 401
    assert client.get("/api/v1/products").status_code == 401


def test_dashboard_list_and_detail(client: TestClient) -> None:
    _configure(client)
    assert client.get("/api/v1/dashboard").json()["open_error_count"] == 0
    products = client.get("/api/v1/products?tier=candidate&sort=created_at").json()
    assert products[0]["filters"]["tier"] == "candidate"
    detail = client.get(f"/api/v1/products/{PRODUCT_ID}")
    assert detail.status_code == 200
    assert detail.json()["product"]["display_name"] == "テスト商品"
    assert client.get(f"/api/v1/products/{uuid4()}").status_code == 404


def test_correction_validates_recalculates_and_rejects_cross_origin(
    client: TestClient,
) -> None:
    repository, recalculate = _configure(client)
    path = f"/api/v1/products/{PRODUCT_ID}/corrections"
    missing_key = client.post(
        path,
        json={"field_name": "estimated_sale_price_jpy", "corrected_value": 1200},
    )
    assert missing_key.status_code == 422
    invalid = client.post(
        path,
        headers={"Idempotency-Key": "correction-invalid"},
        json={"field_name": "estimated_sale_price_jpy", "corrected_value": -1},
    )
    assert invalid.status_code == 422
    forbidden = client.post(
        path,
        headers={"Idempotency-Key": "correction-origin", "Origin": "https://evil.test"},
        json={"field_name": "estimated_sale_price_jpy", "corrected_value": 1200},
    )
    assert forbidden.status_code == 403
    response = client.post(
        path,
        headers={"Idempotency-Key": "correction-valid"},
        json={
            "field_name": "estimated_sale_price_jpy",
            "corrected_value": 1200,
            "reason": "手動確認",
        },
    )
    assert response.status_code == 200
    assert repository.commands[0][0] == "correction"
    assert len(recalculate.calls) == 1


def test_comparable_exclude_and_restore_recalculate(client: TestClient) -> None:
    repository, recalculate = _configure(client)
    base = f"/api/v1/products/{PRODUCT_ID}/comparables/{COMPARABLE_ID}"
    exclude = client.post(
        f"{base}/exclude",
        headers={"Idempotency-Key": "exclude-comparable"},
        json={"reason": "別商品"},
    )
    restore = client.post(
        f"{base}/restore",
        headers={"Idempotency-Key": "restore-comparable"},
        json={"reason": "再確認済み"},
    )
    assert exclude.status_code == 200
    assert restore.status_code == 200
    assert repository.commands[0][1]["exclude"] is True
    assert repository.commands[1][1]["exclude"] is False
    assert len(recalculate.calls) == 2
