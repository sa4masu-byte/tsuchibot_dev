from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from backend.app.application.recommendation import (
    CalculateRecommendation,
    InMemoryRecommendationRepository,
    RecommendationRequest,
)
from backend.app.domain.recommendation import (
    RecommendationInput,
    RecommendationPolicy,
    RecommendationTier,
    ShippingEstimateSource,
    calculate_mercari_fee,
    calculate_recommendation,
    calculate_sourcing_cost,
    estimate_shipping,
)


def policy() -> RecommendationPolicy:
    return RecommendationPolicy(
        standard_shipping_by_method=(
            ("ネコポス", 210),
            ("宅急便コンパクト", 520),
        )
    )


def strong_inputs(**overrides: object) -> RecommendationInput:
    values: dict[str, object] = {
        "sourcing_price_jpy": 1000,
        "estimated_sale_price_jpy": 5000,
        "same_product_shipping_median_jpy": 500,
        "same_product_shipping_count": 4,
        "similar_product_shipping_median_jpy": 750,
        "similar_product_shipping_count": 6,
        "shipping_method": "宅急便コンパクト",
        "shipping_evidence_confidence": 0.9,
        "sold_count": 10,
        "active_count": 2,
        "included_sold_comparable_count": 5,
        "sufficient_comparables": True,
        "average_comparable_similarity": 0.9,
        "price_dispersion": 0.1,
        "product_identity_confidence": 0.9,
        "model_number_confidence": 0.9,
        "condition_confidence": 0.9,
        "authenticity_confidence": 0.9,
        "price_competitiveness": 1.0,
        "seasonality_score": 100,
        "hypothesis_score": 100,
        "ec_delivery_score": 100,
        "research_priority_score": 80,
        "research_evidence_snapshot_hash": "fixture-evidence",
    }
    values.update(overrides)
    return RecommendationInput(**values)  # type: ignore[arg-type]


def test_fee_uses_official_ten_percent_rule_with_floor_rounding() -> None:
    assert calculate_mercari_fee(3345, policy()) == 334


def test_sourcing_cost_uses_only_definite_coupon_and_excludes_points() -> None:
    assert calculate_sourcing_cost(2000, 300, 500) == 1800


def test_shipping_fallback_prefers_same_then_similar_then_mapping() -> None:
    same = estimate_shipping(strong_inputs(), policy())
    similar = estimate_shipping(
        strong_inputs(same_product_shipping_median_jpy=None),
        policy(),
    )
    mapped = estimate_shipping(
        strong_inputs(
            same_product_shipping_median_jpy=None,
            similar_product_shipping_median_jpy=None,
        ),
        policy(),
    )

    assert same.source is ShippingEstimateSource.SAME_PRODUCT_MEDIAN
    assert same.amount_jpy == 500
    assert similar.source is ShippingEstimateSource.SIMILAR_PRODUCT_MEDIAN
    assert similar.amount_jpy == 750
    assert mapped.source is ShippingEstimateSource.STANDARD_METHOD_MAPPING
    assert mapped.amount_jpy == 520


def test_complete_high_quality_evidence_is_strongly_recommended() -> None:
    result = calculate_recommendation(strong_inputs(), policy())

    assert result.mercari_fee_jpy == 500
    assert result.expected_profit_jpy == 3000
    assert result.return_on_cost == Decimal("3")
    assert result.sales_margin == Decimal("0.6")
    assert result.sales_prospect_score == 93
    assert result.confidence_score == 93
    assert result.tier is RecommendationTier.STRONGLY_RECOMMENDED
    assert len(result.quantities) == 4
    assert result.quantities[-1].total_expected_profit_jpy == 12000


def test_insufficient_comparables_force_candidate_downgrade() -> None:
    result = calculate_recommendation(
        strong_inputs(
            included_sold_comparable_count=2,
            sufficient_comparables=False,
        ),
        policy(),
    )

    assert result.tier is RecommendationTier.CANDIDATE
    assert any(reason.code == "INSUFFICIENT_COMPARABLES" for reason in result.reasons)


def test_unknown_shipping_prevents_profit_claim_and_requires_confirmation() -> None:
    result = calculate_recommendation(
        strong_inputs(
            same_product_shipping_median_jpy=None,
            similar_product_shipping_median_jpy=None,
            shipping_method=None,
        ),
        policy(),
    )

    assert result.expected_profit_jpy is None
    assert result.tier is RecommendationTier.REJECT
    assert any(
        reason.code == "SHIPPING_ESTIMATE"
        and reason.component_type.value == "confirmation_required"
        for reason in result.reasons
    )


async def test_calculation_is_idempotent_for_same_input_and_scoring_version() -> None:
    repository = InMemoryRecommendationRepository()
    service = CalculateRecommendation(repository)
    request = RecommendationRequest(
        canonical_product_id=uuid4(),
        source_product_id=uuid4(),
        research_session_id=uuid4(),
        run_id=uuid4(),
        inputs=strong_inputs(),
        policy=policy(),
        calculated_at=datetime(2026, 7, 13, tzinfo=UTC),
    )

    first = await service.execute(request)
    second = await service.execute(request)

    assert second.id == first.id
    assert repository.records == [first]

    revised = await service.execute(
        replace(request, policy=replace(policy(), threshold_version="v2"))
    )

    assert revised.id != first.id
    assert len(repository.records) == 2
