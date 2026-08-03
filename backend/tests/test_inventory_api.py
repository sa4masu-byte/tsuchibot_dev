from typing import Any
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

PRODUCT_ID = uuid4()
POSITION_ID = uuid4()
HYPOTHESIS_ID = uuid4()


class FakeInventoryRepository:
    def __init__(self) -> None:
        self.commands: list[tuple[str, Any]] = []

    async def list_positions(self, limit: int) -> list[dict[str, Any]]:
        return [{"id": POSITION_ID, "limit": limit, "status": "purchased"}]

    async def position_detail(self, position_id: UUID) -> dict[str, Any] | None:
        if position_id != POSITION_ID:
            return None
        return {"id": position_id, "remaining_quantity": 2, "status": "purchased"}

    async def record_purchase(self, product_id: UUID, *command: Any) -> dict[str, Any]:
        self.commands.append(("purchase", (product_id, *command)))
        return {"id": POSITION_ID, "status": "purchased"}

    async def record_listing(self, position_id: UUID, *command: Any) -> dict[str, Any]:
        self.commands.append(("listing", (position_id, *command)))
        return {"id": POSITION_ID, "status": "listed"}

    async def record_sale(self, position_id: UUID, *command: Any) -> dict[str, Any]:
        payload = command[0]
        if payload["quantity"] > 2:
            raise ValueError("quantity cannot exceed remaining inventory")
        self.commands.append(("sale", (position_id, *command)))
        return {"id": POSITION_ID, "status": "sold", "realised_profit_jpy": 700}

    async def record_negative_outcome(self, position_id: UUID, *command: Any) -> dict[str, Any]:
        self.commands.append(("negative", (position_id, *command)))
        return {"id": POSITION_ID, "status": "returned"}

    async def record_preference(self, product_id: UUID, *command: Any) -> dict[str, Any]:
        self.commands.append(("preference", (product_id, *command)))
        return {"signal": command[0]}

    async def record_research_value(self, product_id: UUID, *command: Any) -> dict[str, Any]:
        self.commands.append(("research_value", (product_id, *command)))
        return {"signal": command[0]}

    async def list_hypotheses(self) -> list[dict[str, Any]]:
        return [{"id": HYPOTHESIS_ID, "state": "active"}]

    async def hypothesis_detail(self, hypothesis_id: UUID) -> dict[str, Any] | None:
        return {"id": hypothesis_id, "evidence": []} if hypothesis_id == HYPOTHESIS_ID else None

    async def add_hypothesis_evidence(self, hypothesis_id: UUID, *command: Any) -> dict[str, Any]:
        self.commands.append(("evidence", (hypothesis_id, *command)))
        return {"id": hypothesis_id, "evidence": [command[0]]}


def _configure(client: TestClient) -> FakeInventoryRepository:
    repository = FakeInventoryRepository()
    client.app.state.inventory_repository = repository
    client.post("/api/v1/auth/login", json={"password": "correct-horse"})
    return repository


def _headers(key: str = "inventory-command") -> dict[str, str]:
    return {"Idempotency-Key": key}


def test_inventory_reads_require_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/inventory").status_code == 401
    assert client.get("/api/v1/hypotheses").status_code == 401


def test_inventory_list_and_detail(client: TestClient) -> None:
    _configure(client)
    assert client.get("/api/v1/inventory?limit=25").json()[0]["limit"] == 25
    assert client.get(f"/api/v1/inventory/{POSITION_ID}").status_code == 200
    assert client.get(f"/api/v1/inventory/{uuid4()}").status_code == 404


def test_purchase_validates_quantity_amounts_idempotency_and_origin(client: TestClient) -> None:
    repository = _configure(client)
    path = f"/api/v1/products/{PRODUCT_ID}/purchase"
    body = {
        "purchased": True,
        "purchased_at": "2026-08-03T10:00:00+09:00",
        "quantity": 2,
        "product_amount_jpy": 1000,
        "sourcing_shipping_jpy": 200,
        "coupon_jpy": 100,
        "point_reference_jpy": 50,
        "actual_charged_amount_jpy": 1100,
    }
    assert client.post(path, json=body).status_code == 422
    invalid = {**body, "quantity": 5}
    assert client.post(path, headers=_headers(), json=invalid).status_code == 422
    forbidden = client.post(
        path,
        headers={**_headers(), "Origin": "https://evil.test"},
        json=body,
    )
    assert forbidden.status_code == 403
    assert client.post(path, headers=_headers(), json=body).status_code == 200
    assert repository.commands[0][0] == "purchase"


def test_purchase_can_record_not_purchased_without_financial_values(client: TestClient) -> None:
    repository = _configure(client)
    response = client.post(
        f"/api/v1/products/{PRODUCT_ID}/purchase",
        headers=_headers("purchase-skipped"),
        json={
            "purchased": False,
            "purchased_at": "2026-08-03T10:00:00+09:00",
            "note": "状態が不明",
        },
    )
    assert response.status_code == 200
    assert repository.commands[0][1][1]["purchased"] is False


def test_listing_sale_negative_outcome_and_over_sale(client: TestClient) -> None:
    repository = _configure(client)
    base = f"/api/v1/inventory/{POSITION_ID}"
    listing = client.post(
        f"{base}/listings",
        headers=_headers("listing-command"),
        json={
            "listed_at": "2026-08-03T11:00:00+09:00",
            "marketplace": "mercari",
            "listing_price_jpy": 1800,
            "quantity": 2,
        },
    )
    assert listing.status_code == 200
    sale_body = {
        "sold_at": "2026-08-04T11:00:00+09:00",
        "sold_price_jpy": 1800,
        "actual_fee_jpy": 180,
        "actual_shipping_jpy": 210,
        "quantity": 2,
    }
    assert (
        client.post(f"{base}/sales", headers=_headers("sale-command"), json=sale_body).json()[
            "realised_profit_jpy"
        ]
        == 700
    )
    over_sale = client.post(
        f"{base}/sales",
        headers=_headers("over-sale-command"),
        json={**sale_body, "quantity": 3},
    )
    assert over_sale.status_code == 409
    negative = client.post(
        f"{base}/negative-outcomes",
        headers=_headers("negative-command"),
        json={
            "outcome_type": "returned",
            "quantity": 1,
            "occurred_at": "2026-08-05T11:00:00+09:00",
            "note": "購入者都合",
        },
    )
    assert negative.status_code == 200
    assert [item[0] for item in repository.commands] == ["listing", "sale", "negative"]


def test_feedback_and_hypothesis_evidence_are_append_commands(client: TestClient) -> None:
    repository = _configure(client)
    preference = client.post(
        f"/api/v1/products/{PRODUCT_ID}/feedback/preference",
        headers=_headers("preference-command"),
        json={"signal": "slightly_interested"},
    )
    research = client.post(
        f"/api/v1/products/{PRODUCT_ID}/feedback/research-value",
        headers=_headers("research-command"),
        json={"signal": "worth_researching"},
    )
    evidence = client.post(
        f"/api/v1/hypotheses/{HYPOTHESIS_ID}/evidence",
        headers=_headers("evidence-command"),
        json={
            "evidence_type": "sale_outcome",
            "direction": "supporting",
            "strength": 0.8,
            "source_reference_type": "inventory_position",
            "source_reference_id": str(POSITION_ID),
            "summary": "予測以上の実利益だった",
        },
    )
    assert preference.status_code == research.status_code == evidence.status_code == 200
    assert client.get("/api/v1/hypotheses").json()[0]["state"] == "active"
    assert [item[0] for item in repository.commands] == [
        "preference",
        "research_value",
        "evidence",
    ]
