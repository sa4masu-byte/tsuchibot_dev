from datetime import UTC, datetime
from uuid import uuid4

import pytest
from backend.app.application.catalog import (
    CollectCatalogSources,
    IngestSourceProduct,
    RunContext,
    SourceCollectionResult,
    SourceConfig,
)
from backend.app.domain.catalog import Availability, NormalizedSourceProduct
from backend.app.infrastructure.database import InMemoryCatalogRepository


class PartiallyFailingProvider:
    async def collect(self, config: SourceConfig, context: RunContext) -> SourceCollectionResult:
        if config.location_id == "failed-location":
            raise TimeoutError("source timed out")
        product = NormalizedSourceProduct(
            source_type="jimoty",
            source_location_id=config.location_id,
            source_item_id="item-1",
            canonical_url="https://jmty.jp/example/article-item-1",
            title="Product",
            displayed_price_jpy=500,
            category="toy",
            availability=Availability.AVAILABLE,
            listing_timestamp=None,
            image_urls=(),
            raw_metadata={},
            parser_version="test-v1",
        )
        return SourceCollectionResult((product,), 1, 0)


@pytest.mark.asyncio
async def test_source_failure_does_not_stop_other_location() -> None:
    repository = InMemoryCatalogRepository()
    use_case = CollectCatalogSources(
        PartiallyFailingProvider(),
        IngestSourceProduct(repository),
    )
    configs = (
        SourceConfig("jimoty", "failed-location", "Failed", "https://example.com/failed"),
        SourceConfig("jimoty", "working-location", "Working", "https://example.com/working"),
    )
    outcomes = await use_case.execute(
        configs,
        RunContext(uuid4(), datetime(2026, 7, 13, tzinfo=UTC)),
    )

    assert outcomes[0].status == "failed"
    assert outcomes[0].error_category == "TimeoutError"
    assert outcomes[1].status == "completed"
    assert outcomes[1].new_count == 1
    assert len(repository.observations) == 1
