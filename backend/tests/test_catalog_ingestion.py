from datetime import UTC, datetime
from uuid import uuid4

import pytest
from backend.app.application.catalog import IngestSourceProduct, RunContext
from backend.app.domain.catalog import Availability, ChangeKind, NormalizedSourceProduct
from backend.app.infrastructure.database import InMemoryCatalogRepository


def product(price: int) -> NormalizedSourceProduct:
    return NormalizedSourceProduct(
        source_type="jimoty",
        source_location_id="location-1",
        source_item_id="item-1",
        canonical_url="https://jmty.jp/example/article-item-1",
        title="Product",
        displayed_price_jpy=price,
        category="toy",
        availability=Availability.AVAILABLE,
        listing_timestamp=None,
        image_urls=(),
        raw_metadata={},
        parser_version="test-v1",
    )


@pytest.mark.asyncio
async def test_ingestion_appends_price_history_and_is_idempotent() -> None:
    repository = InMemoryCatalogRepository()
    ingest = IngestSourceProduct(repository)
    context = RunContext(uuid4(), datetime(2026, 7, 13, tzinfo=UTC))

    first = await ingest.execute(product(500), context)
    duplicate = await ingest.execute(product(500), context)
    later = await ingest.execute(
        product(300),
        RunContext(uuid4(), datetime(2026, 7, 14, tzinfo=UTC)),
    )

    assert first.change.kind is ChangeKind.NEW
    assert duplicate.observation_created is False
    assert later.change.kind is ChangeKind.PRICE_CHANGED
    assert [item.product.displayed_price_jpy for item in repository.observations] == [500, 300]
