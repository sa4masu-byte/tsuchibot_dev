import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from backend.app.domain.catalog import (
    ChangeKind,
    NormalizedSourceProduct,
    ProductChange,
    SourceProductState,
    detect_change,
)


@dataclass(frozen=True, slots=True)
class SourceConfig:
    source_type: str
    location_id: str
    display_name: str
    articles_url: str
    max_pages: int = 1
    request_interval_seconds: float = 1.0


@dataclass(frozen=True, slots=True)
class RunContext:
    run_id: UUID
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class SourceCollectionResult:
    products: tuple[NormalizedSourceProduct, ...]
    pages_fetched: int
    duplicate_items_skipped: int


class SourceCatalogProvider(Protocol):
    async def collect(
        self,
        config: SourceConfig,
        context: RunContext,
    ) -> SourceCollectionResult: ...


class CatalogRepository(Protocol):
    async def get_state(
        self,
        source_type: str,
        source_item_id: str,
    ) -> SourceProductState | None: ...

    async def append_observation(
        self,
        product: NormalizedSourceProduct,
        run_id: UUID,
        observed_at: datetime,
        change: ProductChange,
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class IngestionResult:
    product: NormalizedSourceProduct
    change: ProductChange
    observation_created: bool


def observation_idempotency_key(
    product: NormalizedSourceProduct,
    run_id: UUID,
    observed_at: datetime,
) -> str:
    material = "|".join(
        (
            str(run_id),
            product.source_type,
            product.source_item_id,
            observed_at.isoformat(),
            str(product.displayed_price_jpy),
            product.availability.value,
        )
    )
    return hashlib.sha256(material.encode()).hexdigest()


class IngestSourceProduct:
    def __init__(self, repository: CatalogRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        product: NormalizedSourceProduct,
        context: RunContext,
    ) -> IngestionResult:
        previous = await self._repository.get_state(*product.identity)
        change = detect_change(previous, product)
        created = await self._repository.append_observation(
            product,
            context.run_id,
            context.observed_at,
            change,
        )
        return IngestionResult(product=product, change=change, observation_created=created)


@dataclass(frozen=True, slots=True)
class SourceCollectionOutcome:
    location_id: str
    status: str
    collected_count: int
    new_count: int
    changed_count: int
    unchanged_count: int
    error_category: str | None = None
    error_message: str | None = None


class CollectCatalogSources:
    """Collects each location independently so one failure cannot abort the others."""

    def __init__(
        self,
        provider: SourceCatalogProvider,
        ingestion: IngestSourceProduct,
    ) -> None:
        self._provider = provider
        self._ingestion = ingestion

    async def execute(
        self,
        configs: tuple[SourceConfig, ...],
        context: RunContext,
    ) -> tuple[SourceCollectionOutcome, ...]:
        outcomes: list[SourceCollectionOutcome] = []
        for config in configs:
            try:
                collected = await self._provider.collect(config, context)
                results = [
                    await self._ingestion.execute(product, context)
                    for product in collected.products
                ]
                new_count = sum(result.change.kind is ChangeKind.NEW for result in results)
                unchanged_count = sum(
                    result.change.kind is ChangeKind.UNCHANGED for result in results
                )
                outcomes.append(
                    SourceCollectionOutcome(
                        location_id=config.location_id,
                        status="completed",
                        collected_count=len(results),
                        new_count=new_count,
                        changed_count=len(results) - new_count - unchanged_count,
                        unchanged_count=unchanged_count,
                    )
                )
            except Exception as exc:
                outcomes.append(
                    SourceCollectionOutcome(
                        location_id=config.location_id,
                        status="failed",
                        collected_count=0,
                        new_count=0,
                        changed_count=0,
                        unchanged_count=0,
                        error_category=type(exc).__name__,
                        error_message=str(exc),
                    )
                )
        return tuple(outcomes)
