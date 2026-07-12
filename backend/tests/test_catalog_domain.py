from datetime import UTC, datetime

from backend.app.domain.catalog import (
    Availability,
    ChangeKind,
    NormalizedSourceProduct,
    SourceProductState,
    detect_change,
)


def product(price: int | None = 500, availability: Availability = Availability.AVAILABLE):
    return NormalizedSourceProduct(
        source_type="jimoty",
        source_location_id="location-1",
        source_item_id="item-1",
        canonical_url="https://jmty.jp/example/article-item-1",
        title="Product",
        displayed_price_jpy=price,
        category="toy",
        availability=availability,
        listing_timestamp=datetime(2026, 7, 1, tzinfo=UTC),
        image_urls=(),
        raw_metadata={},
        parser_version="test-v1",
    )


def state(price: int | None = 500, availability: Availability = Availability.AVAILABLE):
    return SourceProductState("jimoty", "item-1", "https://example.com", price, availability)


def test_unseen_product_is_new() -> None:
    change = detect_change(None, product())
    assert change.kind is ChangeKind.NEW
    assert change.requires_reevaluation is True


def test_price_change_retains_delta() -> None:
    change = detect_change(state(price=500), product(price=300))
    assert change.kind is ChangeKind.PRICE_CHANGED
    assert change.previous_price_jpy == 500
    assert change.price_delta_jpy == -200


def test_availability_change_is_detected() -> None:
    change = detect_change(state(), product(availability=Availability.UNAVAILABLE))
    assert change.kind is ChangeKind.AVAILABILITY_CHANGED


def test_unchanged_product_does_not_require_reevaluation() -> None:
    change = detect_change(state(), product())
    assert change.kind is ChangeKind.UNCHANGED
    assert change.requires_reevaluation is False
