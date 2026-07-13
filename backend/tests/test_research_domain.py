from dataclasses import replace
from datetime import UTC, datetime, timedelta

from backend.app.domain.research import (
    ComparableDecision,
    ComparableRanker,
    ListingStatus,
    MarketplaceListing,
    ResearchTarget,
    SearchStage,
    ShippingResponsibility,
    StagedQueryGenerator,
    calculate_price_statistics,
    calculate_shipping_statistics,
)


def target() -> ResearchTarget:
    return ResearchTarget(
        source_title="任天堂 Nintendo Switch HAC-001 本体",
        category="ゲーム機",
        manufacturer="任天堂",
        brand="Nintendo",
        model_numbers=("HAC-001",),
        series="Nintendo Switch",
        product_type="ゲーム機",
        condition="good",
        search_terms=("Nintendo Switch 本体", "HAC-001"),
    )


def listing(
    listing_id: str,
    price: int,
    now: datetime,
    *,
    status: ListingStatus = ListingStatus.SOLD,
    sold_days_ago: int = 10,
    title: str = "Nintendo Switch HAC-001 本体 中古",
    is_bundle: bool = False,
    bundle_unit_count: int | None = None,
    is_junk: bool = False,
) -> MarketplaceListing:
    return MarketplaceListing(
        external_listing_id=listing_id,
        canonical_url=f"https://jp.mercari.com/item/{listing_id}",
        title=title,
        status=status,
        displayed_price_jpy=price,
        sold_at=now - timedelta(days=sold_days_ago) if status is ListingStatus.SOLD else None,
        condition="good",
        shipping_method="らくらくメルカリ便",
        shipping_responsibility=ShippingResponsibility.SELLER,
        estimated_shipping_jpy=750,
        is_bundle=is_bundle,
        bundle_unit_count=bundle_unit_count,
        is_junk=is_junk,
    )


def test_staged_queries_follow_required_order_and_deduplicate() -> None:
    queries = StagedQueryGenerator().generate(target())

    assert [query.stage for query in queries] == [
        SearchStage.EXACT_MODEL,
        SearchStage.MANUFACTURER_MODEL,
        SearchStage.SERIES_PRODUCT_TYPE,
        SearchStage.MANUFACTURER_PRODUCT_TYPE,
        SearchStage.SIMILAR_PRODUCT,
    ]
    assert [query.order for query in queries] == [1, 2, 3, 4, 5]
    assert queries[0].normalized_text == "hac-001"


def test_comparable_ranking_applies_90_day_and_special_listing_rules() -> None:
    now = datetime(2026, 7, 13, tzinfo=UTC)
    listings = (
        listing("m1", 20000, now),
        listing("m2", 22000, now),
        listing("m3", 24000, now),
        listing("active", 25000, now, status=ListingStatus.ACTIVE),
        listing("old", 18000, now, sold_days_ago=91),
        listing("bundle", 40000, now, is_bundle=True),
        listing("junk", 10000, now, is_junk=True),
    )

    evidence = ComparableRanker().rank(
        target(),
        listings,
        now - timedelta(days=90),
        now,
    )
    by_id = {item.listing.external_listing_id: item for item in evidence}

    assert by_id["m1"].included_in_price is True
    assert by_id["active"].included_in_price is False
    assert by_id["old"].included_in_price is False
    assert by_id["bundle"].current_decision is ComparableDecision.EXCLUDE
    assert by_id["bundle"].decision_reason == "bundle_unit_count_unknown"
    assert by_id["junk"].current_decision is ComparableDecision.EXCLUDE

    price = calculate_price_statistics(evidence)
    assert price.included_count == 3
    assert price.median_price_jpy == 22000
    assert price.lower_quartile_price_jpy == 20000
    assert price.minimum_price_jpy == 20000
    assert price.maximum_price_jpy == 24000
    assert price.sufficient_evidence is True

    shipping = calculate_shipping_statistics(evidence)
    assert shipping.evidence_count == 5
    assert shipping.median_shipping_jpy == 750
    assert shipping.confidence == 1.0


def test_bundle_uses_unit_price_only_when_unit_count_is_known() -> None:
    now = datetime(2026, 7, 13, tzinfo=UTC)
    evidence = ComparableRanker().rank(
        target(),
        (
            listing("bundle", 40000, now, is_bundle=True, bundle_unit_count=2),
            listing("m2", 21000, now),
            listing("m3", 22000, now),
        ),
        now - timedelta(days=90),
        now,
    )

    price = calculate_price_statistics(evidence)
    assert price.included_count == 3
    assert price.median_price_jpy == 21000


def test_known_condition_mismatch_requires_review_and_is_not_priced() -> None:
    now = datetime(2026, 7, 13, tzinfo=UTC)
    mismatched = replace(listing("poor", 10000, now), condition="poor")

    evidence = ComparableRanker().rank(
        target(),
        (mismatched,),
        now - timedelta(days=90),
        now,
    )

    assert evidence[0].current_decision is ComparableDecision.REVIEW
    assert evidence[0].decision_reason == "condition_mismatch"
    assert evidence[0].included_in_price is False


def test_recent_listing_time_is_conservative_upper_bound_for_unknown_sold_date() -> None:
    now = datetime(2026, 7, 13, tzinfo=UTC)
    sold = replace(
        listing("unknown-sold-date", 20000, now),
        sold_at=None,
        listed_at=now - timedelta(days=30),
    )

    evidence = ComparableRanker().rank(
        target(),
        (sold,),
        now - timedelta(days=90),
        now,
    )

    assert evidence[0].included_in_price is True
