from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from backend.app.application.catalog import RunContext, SourceConfig
from backend.app.domain.catalog import Availability
from backend.app.infrastructure.sources import (
    JimotyParser,
    JimotySpotAdapter,
    SourceBlockedError,
    SourceParsingError,
)

FIXTURES = Path(__file__).parent / "fixtures" / "jimoty"
BASE_URL = "https://jmty.jp/profiles/location/articles"


def config(max_pages: int = 1) -> SourceConfig:
    return SourceConfig("jimoty", "location", "Test location", BASE_URL, max_pages, 0)


def context() -> RunContext:
    return RunContext(uuid4(), datetime(2026, 7, 13, 12, tzinfo=UTC))


def test_parser_normalizes_profile_cards() -> None:
    html = (FIXTURES / "profile_page_1.html").read_text()
    products, next_url = JimotyParser().parse(html, config(), context().observed_at)

    assert len(products) == 2
    assert products[0].source_item_id == "abc123"
    assert products[0].displayed_price_jpy == 1500
    assert products[0].category == "toy"
    assert products[0].availability is Availability.AVAILABLE
    assert products[0].listing_timestamp == datetime(2026, 7, 12, tzinfo=UTC)
    assert products[1].displayed_price_jpy == 0
    assert products[1].availability is Availability.UNAVAILABLE
    assert products[1].listing_timestamp == datetime(2025, 12, 31, tzinfo=UTC)
    assert next_url == f"{BASE_URL}?page=2"


def test_parser_fails_loudly_when_structure_changes() -> None:
    html = (FIXTURES / "broken.html").read_text()
    with pytest.raises(SourceParsingError):
        JimotyParser().parse(html, config(), context().observed_at)


@pytest.mark.asyncio
async def test_adapter_paginates_and_deduplicates() -> None:
    page_1 = (FIXTURES / "profile_page_1.html").read_text()
    page_2 = (FIXTURES / "profile_page_2.html").read_text()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=page_2 if "page=2" in str(request.url) else page_1)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await JimotySpotAdapter(client=client).collect(config(max_pages=2), context())

    assert result.pages_fetched == 2
    assert result.duplicate_items_skipped == 1
    assert [product.source_item_id for product in result.products] == [
        "abc123",
        "free456",
        "new789",
    ]


@pytest.mark.asyncio
async def test_adapter_does_not_retry_blocked_response() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(403)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SourceBlockedError):
            await JimotySpotAdapter(client=client, max_retries=2).collect(config(), context())
    assert calls == 1


@pytest.mark.asyncio
async def test_adapter_retries_bounded_transient_response() -> None:
    calls = 0
    delays: list[float] = []
    html = (FIXTURES / "profile_page_2.html").read_text()

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503 if calls == 1 else 200, text=html)

    async def record_delay(delay: float) -> None:
        delays.append(delay)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await JimotySpotAdapter(
            client=client,
            max_retries=1,
            sleep=record_delay,
        ).collect(config(), context())

    assert len(result.products) == 2
    assert calls == 2
    assert delays == [1]
