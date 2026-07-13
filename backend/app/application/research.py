from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID, uuid4

from backend.app.domain.research import (
    ComparableEvidence,
    ComparableRanker,
    ListingStatus,
    MarketplaceListing,
    PriceStatistics,
    ResearchTarget,
    SearchQuery,
    ShippingStatistics,
    StagedQueryGenerator,
    calculate_price_statistics,
    calculate_shipping_statistics,
    default_evidence_period,
)


@dataclass(frozen=True, slots=True)
class MarketplaceSearchResult:
    listings: tuple[MarketplaceListing, ...]
    parser_version: str
    raw_result_ref: str | None = None


class MercariResearchProvider(Protocol):
    provider_name: str

    async def search(
        self,
        query: SearchQuery,
        sold_limit: int,
        active_limit: int,
    ) -> MarketplaceSearchResult: ...


@dataclass(frozen=True, slots=True)
class ResearchRequest:
    canonical_product_id: UUID
    run_id: UUID
    target: ResearchTarget
    researched_at: datetime
    sold_limit: int = 50
    active_limit: int = 50
    evidence_days: int = 90
    minimum_sold_comparables: int = 3
    config_version: str = "mercari-research-v1"

    def __post_init__(self) -> None:
        if not 1 <= self.sold_limit <= 50 or not 1 <= self.active_limit <= 50:
            raise ValueError("Mercari result limits must be between 1 and 50")
        if not 1 <= self.evidence_days <= 365:
            raise ValueError("evidence_days must be between 1 and 365")
        if not 1 <= self.minimum_sold_comparables <= 50:
            raise ValueError("minimum_sold_comparables must be between 1 and 50")
        if self.researched_at.tzinfo is None:
            raise ValueError("researched_at must include a timezone")


@dataclass(frozen=True, slots=True)
class QueryExecution:
    id: UUID
    query: SearchQuery
    status: str
    listings: tuple[MarketplaceListing, ...]
    parser_version: str
    raw_result_ref: str | None
    error_category: str | None
    error_message: str | None
    started_at: datetime
    completed_at: datetime


@dataclass(frozen=True, slots=True)
class ResearchOutcome:
    session_id: UUID
    request: ResearchRequest
    provider: str
    status: str
    evidence_period_start: datetime
    evidence_period_end: datetime
    executions: tuple[QueryExecution, ...]
    comparables: tuple[ComparableEvidence, ...]
    price_statistics: PriceStatistics
    shipping_statistics: ShippingStatistics
    completed_at: datetime


class ResearchRepository(Protocol):
    async def save(self, outcome: ResearchOutcome) -> None: ...


def _prefer_listing(
    previous: MarketplaceListing | None,
    current: MarketplaceListing,
) -> MarketplaceListing:
    if previous is None:
        return current
    if current.status is ListingStatus.SOLD and previous.status is ListingStatus.ACTIVE:
        return current
    return previous


class ConductMercariResearch:
    def __init__(
        self,
        provider: MercariResearchProvider,
        repository: ResearchRepository,
        query_generator: StagedQueryGenerator | None = None,
        ranker: ComparableRanker | None = None,
    ) -> None:
        self._provider = provider
        self._repository = repository
        self._query_generator = query_generator or StagedQueryGenerator()
        self._ranker = ranker or ComparableRanker()

    async def execute(self, request: ResearchRequest) -> ResearchOutcome:
        period_start, period_end = default_evidence_period(
            request.researched_at,
            request.evidence_days,
        )
        executions: list[QueryExecution] = []
        unique_listings: dict[str, MarketplaceListing] = {}
        for query in self._query_generator.generate(request.target):
            try:
                result = await self._provider.search(
                    query,
                    request.sold_limit,
                    request.active_limit,
                )
                for listing in result.listings:
                    unique_listings[listing.external_listing_id] = _prefer_listing(
                        unique_listings.get(listing.external_listing_id),
                        listing,
                    )
                execution = QueryExecution(
                    id=uuid4(),
                    query=query,
                    status="completed",
                    listings=result.listings,
                    parser_version=result.parser_version,
                    raw_result_ref=result.raw_result_ref,
                    error_category=None,
                    error_message=None,
                    started_at=request.researched_at,
                    completed_at=request.researched_at,
                )
            except Exception as exc:
                execution = QueryExecution(
                    id=uuid4(),
                    query=query,
                    status="failed",
                    listings=(),
                    parser_version="unavailable",
                    raw_result_ref=None,
                    error_category=type(exc).__name__,
                    error_message=str(exc),
                    started_at=request.researched_at,
                    completed_at=request.researched_at,
                )
            executions.append(execution)

        comparables = self._ranker.rank(
            request.target,
            tuple(unique_listings.values()),
            period_start,
            period_end,
        )
        failures = sum(execution.status == "failed" for execution in executions)
        if failures == len(executions):
            status = "research_unavailable"
        elif failures:
            status = "partial_failure"
        elif not unique_listings:
            status = "research_unavailable"
        else:
            status = "completed"
        outcome = ResearchOutcome(
            session_id=uuid4(),
            request=request,
            provider=self._provider.provider_name,
            status=status,
            evidence_period_start=period_start,
            evidence_period_end=period_end,
            executions=tuple(executions),
            comparables=comparables,
            price_statistics=calculate_price_statistics(
                comparables,
                request.minimum_sold_comparables,
            ),
            shipping_statistics=calculate_shipping_statistics(comparables),
            completed_at=request.researched_at,
        )
        await self._repository.save(outcome)
        return outcome
