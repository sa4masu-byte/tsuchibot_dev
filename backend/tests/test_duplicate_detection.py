from dataclasses import replace

from backend.app.domain.catalog import (
    Availability,
    DuplicateDecisionKind,
    DuplicateDetectionService,
    NormalizedSourceProduct,
)


def product(item_id: str = "item-1", **changes: object) -> NormalizedSourceProduct:
    value = NormalizedSourceProduct(
        source_type="jimoty",
        source_location_id="location-1",
        source_item_id=item_id,
        canonical_url=f"https://jmty.jp/example/article-{item_id}",
        title="Disney Puzzle 108 pieces",
        displayed_price_jpy=500,
        category="toy",
        availability=Availability.AVAILABLE,
        listing_timestamp=None,
        image_urls=(),
        raw_metadata={},
        parser_version="test-v1",
    )
    return replace(value, **changes)


def test_same_source_item_is_exact_duplicate() -> None:
    decision = DuplicateDetectionService().evaluate(product(), (product(),))
    assert decision.kind is DuplicateDecisionKind.EXACT
    assert decision.reason == "same_source_item_id"


def test_same_image_price_and_location_is_only_potential_duplicate() -> None:
    first = product(raw_metadata={"image_hashes": ["hash-1"]})
    second = product("item-2", raw_metadata={"image_hashes": ["hash-1"]})
    decision = DuplicateDetectionService().evaluate(second, (first,))
    assert decision.kind is DuplicateDecisionKind.POTENTIAL
    assert decision.matched_item_id == "item-1"


def test_weak_evidence_does_not_merge_products() -> None:
    first = product()
    second = product("item-2", title="Completely different item", displayed_price_jpy=3000)
    decision = DuplicateDetectionService().evaluate(second, (first,))
    assert decision.kind is DuplicateDecisionKind.DISTINCT
