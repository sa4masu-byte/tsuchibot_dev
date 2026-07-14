from backend.app.domain.ec import (
    ECEligibility,
    ECOffer,
    ECPolicy,
    ECProductType,
    ECSource,
    build_ec_keywords,
    evaluate_ec_offer,
    practical_rakuten_offers,
    should_explore_ec,
)


def offer(source: ECSource = ECSource.AMAZON, **changes: object) -> ECOffer:
    values: dict[str, object] = {
        "source": source,
        "source_item_id": "item-1",
        "canonical_url": "https://example.com/item-1",
        "title": "Unbranded item",
        "displayed_price_jpy": 1000,
    }
    values.update(changes)
    return ECOffer(**values)  # type: ignore[arg-type]


def test_keyword_priority_deduplicates_and_honours_budget() -> None:
    keywords = build_ec_keywords(
        ("Craft Kit", "収納 ケース"),
        ("craft   kit", "高需要商品"),
        ("Sale",),
        3,
    )
    assert [item.value for item in keywords] == ["Craft Kit", "収納 ケース", "高需要商品"]
    assert [item.strategy.value for item in keywords] == [
        "profit_pattern",
        "profit_pattern",
        "mercari_demand",
    ]


def test_ec_trigger_does_not_force_candidates() -> None:
    policy = ECPolicy(minimum_useful_candidates=3)
    assert should_explore_ec(2, policy)
    assert not should_explore_ec(3, policy)
    assert should_explore_ec(3, policy, complete_scan=True)


def test_points_are_reference_only_in_sourcing_cost() -> None:
    item = offer(
        displayed_price_jpy=1000,
        sourcing_shipping_jpy=200,
        definite_coupon_jpy=100,
        points_reference_jpy=500,
    )
    evaluation = evaluate_ec_offer(item, ECPolicy())
    assert evaluation.sourcing_cost_jpy == 1100
    assert evaluation.eligibility is ECEligibility.ELIGIBLE


def test_overseas_policy_requires_variant_delivery_and_seller_quality() -> None:
    eligible = offer(
        ECSource.ALIEXPRESS,
        selected_variant="blue / medium",
        delivery_days=7,
        product_rating=4.8,
        review_count=100,
        seller_rating=4.7,
    )
    assert evaluate_ec_offer(eligible, ECPolicy()).eligibility is ECEligibility.ELIGIBLE

    unknown = offer(ECSource.SHEIN, variant_price_confirmed=False)
    result = evaluate_ec_offer(unknown, ECPolicy())
    assert result.eligibility is ECEligibility.CONFIRMATION_REQUIRED
    assert "delivery_days_unknown" in result.reason_codes


def test_exclusions_and_authenticity_are_hard_rejections() -> None:
    item = offer(
        ECSource.ALIEXPRESS,
        product_type=ECProductType.BATTERY,
        brand="Unknown branded claim",
        selected_variant="one size",
        delivery_days=5,
        product_rating=4.9,
        review_count=500,
        seller_rating=4.9,
    )
    result = evaluate_ec_offer(item, ECPolicy())
    assert result.eligibility is ECEligibility.REJECTED
    assert "excluded_product_type:battery" in result.reason_codes
    assert "authenticity_unconfirmed" in result.reason_codes


def test_rakuten_retains_three_practical_lowest_offers() -> None:
    offers = tuple(
        offer(
            ECSource.RAKUTEN,
            source_item_id=f"item-{price}",
            displayed_price_jpy=price,
            delivery_days=2,
            shop_rating=4.5,
        )
        for price in (1400, 900, 1200, 1000)
    )
    assert [item.displayed_price_jpy for item in practical_rakuten_offers(offers)] == [
        900,
        1000,
        1200,
    ]
