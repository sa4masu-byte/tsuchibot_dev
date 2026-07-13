from datetime import UTC, datetime, timedelta
from uuid import uuid4

from backend.app.application.research import ConductMercariResearch, ResearchRequest
from backend.app.domain.research import (
    ListingStatus,
    MarketplaceListing,
    ResearchTarget,
    SearchStage,
)
from backend.app.infrastructure.database import InMemoryResearchRepository
from backend.app.infrastructure.sources import ManualMercariAdapter


def make_listing(
    listing_id: str,
    status: ListingStatus,
    now: datetime,
) -> MarketplaceListing:
    return MarketplaceListing(
        external_listing_id=listing_id,
        canonical_url=f"https://jp.mercari.com/item/{listing_id}",
        title="Nintendo Switch HAC-001 本体",
        status=status,
        displayed_price_jpy=22000,
        sold_at=now - timedelta(days=5) if status is ListingStatus.SOLD else None,
        condition="good",
        estimated_shipping_jpy=750,
    )


async def test_conduct_research_deduplicates_listings_and_persists_outcome() -> None:
    now = datetime(2026, 7, 13, tzinfo=UTC)
    active = make_listing("m1", ListingStatus.ACTIVE, now)
    sold = make_listing("m1", ListingStatus.SOLD, now)
    provider = ManualMercariAdapter(
        {
            SearchStage.EXACT_MODEL: (active,),
            SearchStage.MANUFACTURER_MODEL: (sold,),
            SearchStage.SIMILAR_PRODUCT: (
                make_listing("m2", ListingStatus.SOLD, now),
                make_listing("m3", ListingStatus.SOLD, now),
            ),
        }
    )
    repository = InMemoryResearchRepository()
    request = ResearchRequest(
        canonical_product_id=uuid4(),
        run_id=uuid4(),
        researched_at=now,
        target=ResearchTarget(
            source_title="Nintendo Switch HAC-001 本体",
            brand="Nintendo",
            model_numbers=("HAC-001",),
            product_type="ゲーム機",
            condition="good",
        ),
    )

    outcome = await ConductMercariResearch(provider, repository).execute(request)

    assert outcome.status == "completed"
    assert len(outcome.executions) == 4
    assert len(outcome.comparables) == 3
    assert outcome.price_statistics.included_count == 3
    assert outcome.price_statistics.sufficient_evidence is True
    assert repository.outcomes == [outcome]
    listing = next(
        item.listing
        for item in outcome.comparables
        if item.listing.external_listing_id == "m1"
    )
    assert listing.status is ListingStatus.SOLD


async def test_empty_manual_evidence_is_research_unavailable_not_rejection() -> None:
    repository = InMemoryResearchRepository()
    request = ResearchRequest(
        canonical_product_id=uuid4(),
        run_id=uuid4(),
        researched_at=datetime(2026, 7, 13, tzinfo=UTC),
        target=ResearchTarget(source_title="不明な商品"),
    )

    outcome = await ConductMercariResearch(
        ManualMercariAdapter({}),
        repository,
    ).execute(request)

    assert outcome.status == "research_unavailable"
    assert outcome.price_statistics.included_count == 0
