import hashlib
import json
from dataclasses import asdict
from decimal import ROUND_HALF_UP, Decimal
from statistics import median

from backend.app.domain.recommendation.models import (
    QuantityEvaluation,
    ReasonComponent,
    ReasonComponentType,
    RecommendationInput,
    RecommendationPolicy,
    RecommendationResult,
    RecommendationTier,
    ShippingEstimate,
    ShippingEstimateSource,
)


def _bounded(value: float, lower: float = 0, upper: float = 1) -> float:
    return min(upper, max(lower, value))


def _score(value: float) -> int:
    return int(Decimal(str(_bounded(value, 0, 100))).quantize(0, ROUND_HALF_UP))


def calculate_mercari_fee(sale_price_jpy: int, policy: RecommendationPolicy) -> int:
    if sale_price_jpy < 0:
        raise ValueError("sale price cannot be negative")
    return sale_price_jpy * policy.fee_rate_basis_points // 10000


def calculate_sourcing_cost(
    displayed_price_jpy: int,
    sourcing_shipping_jpy: int = 0,
    definite_coupon_jpy: int = 0,
) -> int:
    if min(displayed_price_jpy, sourcing_shipping_jpy, definite_coupon_jpy) < 0:
        raise ValueError("sourcing cost inputs cannot be negative")
    subtotal = displayed_price_jpy + sourcing_shipping_jpy
    if definite_coupon_jpy > subtotal:
        raise ValueError("definite coupon cannot exceed sourcing subtotal")
    return subtotal - definite_coupon_jpy


def estimate_shipping(
    inputs: RecommendationInput,
    policy: RecommendationPolicy,
) -> ShippingEstimate:
    if inputs.same_product_shipping_median_jpy is not None:
        return ShippingEstimate(
            inputs.same_product_shipping_median_jpy,
            ShippingEstimateSource.SAME_PRODUCT_MEDIAN,
            max(inputs.shipping_evidence_confidence, 0.8),
            inputs.same_product_shipping_count,
            "same_product_comparable_median",
        )
    if inputs.similar_product_shipping_median_jpy is not None:
        return ShippingEstimate(
            inputs.similar_product_shipping_median_jpy,
            ShippingEstimateSource.SIMILAR_PRODUCT_MEDIAN,
            inputs.shipping_evidence_confidence,
            inputs.similar_product_shipping_count,
            "similar_product_comparable_median",
        )
    if inputs.shipping_method:
        amount = policy.standard_shipping_mapping.get(inputs.shipping_method)
        if amount is not None:
            return ShippingEstimate(
                amount,
                ShippingEstimateSource.STANDARD_METHOD_MAPPING,
                0.45,
                0,
                "versioned_standard_method_mapping",
            )
    return ShippingEstimate(
        None,
        ShippingEstimateSource.UNKNOWN,
        0,
        0,
        "responsible_shipping_estimate_unavailable",
    )


def calculate_financials(
    inputs: RecommendationInput,
    policy: RecommendationPolicy,
    shipping: ShippingEstimate,
) -> tuple[int | None, int | None, int | None, Decimal | None, Decimal | None]:
    sourcing_cost = (
        calculate_sourcing_cost(
            inputs.sourcing_price_jpy,
            inputs.sourcing_shipping_jpy,
            inputs.definite_coupon_jpy,
        )
        if inputs.sourcing_price_jpy is not None
        else None
    )
    if inputs.estimated_sale_price_jpy is None:
        return sourcing_cost, None, None, None, None
    fee = calculate_mercari_fee(inputs.estimated_sale_price_jpy, policy)
    if sourcing_cost is None or shipping.amount_jpy is None:
        return sourcing_cost, fee, None, None, None
    profit = inputs.estimated_sale_price_jpy - fee - shipping.amount_jpy - sourcing_cost
    return_on_cost = (
        Decimal(profit) / Decimal(sourcing_cost) if sourcing_cost > 0 else None
    )
    sales_margin = (
        Decimal(profit) / Decimal(inputs.estimated_sale_price_jpy)
        if inputs.estimated_sale_price_jpy > 0
        else None
    )
    return sourcing_cost, fee, profit, return_on_cost, sales_margin


def calculate_sales_prospect(
    inputs: RecommendationInput,
    policy: RecommendationPolicy,
) -> tuple[int, tuple[ReasonComponent, ...]]:
    sold_volume_points = 30 * min(inputs.sold_count, policy.maximum_sold_volume) / (
        policy.maximum_sold_volume
    )
    total_listings = inputs.sold_count + inputs.active_count
    sold_rate = inputs.sold_count / total_listings if total_listings else 0
    sold_rate_points = 30 * sold_rate
    similarity_points = 20 * (inputs.average_comparable_similarity or 0)
    competitiveness_points = 10 * (inputs.price_competitiveness or 0)
    seasonality_points = 5 * ((inputs.seasonality_score or 0) / 100)
    hypothesis_points = 3 * ((inputs.hypothesis_score or 0) / 100)
    delivery_points = 2 * ((inputs.ec_delivery_score or 0) / 100)
    components = (
        ReasonComponent(
            "SOLD_VOLUME",
            "90日以内の売却済み件数",
            ReasonComponentType.POSITIVE if inputs.sold_count else ReasonComponentType.RISK,
            inputs.sold_count,
            Decimal(str(round(sold_volume_points, 4))),
            "mercari_research",
        ),
        ReasonComponent(
            "SOLD_RATE_HEURISTIC",
            "取得証拠に基づく売却率指標",
            ReasonComponentType.POSITIVE if sold_rate >= 0.5 else ReasonComponentType.RISK,
            round(sold_rate, 6),
            Decimal(str(round(sold_rate_points, 4))),
            "mercari_research",
        ),
        ReasonComponent(
            "COMPARABLE_SIMILARITY",
            "比較商品の平均類似度",
            ReasonComponentType.POSITIVE
            if (inputs.average_comparable_similarity or 0) >= 0.65
            else ReasonComponentType.RISK,
            inputs.average_comparable_similarity,
            Decimal(str(round(similarity_points, 4))),
            "comparable_ranking",
        ),
        ReasonComponent(
            "PRICE_COMPETITIVENESS",
            "販売中価格に対する価格競争力",
            ReasonComponentType.POSITIVE
            if (inputs.price_competitiveness or 0) >= 0.7
            else ReasonComponentType.RISK,
            inputs.price_competitiveness,
            Decimal(str(round(competitiveness_points, 4))),
            "market_price_comparison",
        ),
        ReasonComponent(
            "SEASONALITY",
            "季節性の裏付け",
            ReasonComponentType.POSITIVE
            if inputs.seasonality_score is not None
            else ReasonComponentType.ASSUMPTION,
            inputs.seasonality_score,
            Decimal(str(round(seasonality_points, 4))),
            "seasonality_evidence",
        ),
        ReasonComponent(
            "HYPOTHESIS_EVIDENCE",
            "利益仮説の裏付け",
            ReasonComponentType.POSITIVE
            if inputs.hypothesis_score is not None
            else ReasonComponentType.ASSUMPTION,
            inputs.hypothesis_score,
            Decimal(str(round(hypothesis_points, 4))),
            "profit_hypothesis",
        ),
        ReasonComponent(
            "EC_DELIVERY_EVIDENCE",
            "EC配送期間の裏付け",
            ReasonComponentType.POSITIVE
            if inputs.ec_delivery_score is not None
            else ReasonComponentType.ASSUMPTION,
            inputs.ec_delivery_score,
            Decimal(str(round(delivery_points, 4))),
            "ec_source_evidence",
        ),
    )
    return _score(
        sold_volume_points
        + sold_rate_points
        + similarity_points
        + competitiveness_points
        + seasonality_points
        + hypothesis_points
        + delivery_points
    ), components


def calculate_confidence(
    inputs: RecommendationInput,
    shipping: ShippingEstimate,
) -> tuple[int, tuple[ReasonComponent, ...]]:
    comparable_count_ratio = min(inputs.included_sold_comparable_count / 3, 1)
    dispersion_reliability = (
        0 if inputs.price_dispersion is None else 1 - min(inputs.price_dispersion, 1)
    )
    values = {
        "product_identity": (inputs.product_identity_confidence, 20),
        "model_number": (inputs.model_number_confidence, 15),
        "comparable_count": (comparable_count_ratio, 25),
        "comparable_similarity": (inputs.average_comparable_similarity or 0, 15),
        "price_dispersion": (dispersion_reliability, 10),
        "condition": (inputs.condition_confidence, 5),
        "shipping": (shipping.confidence, 5),
        "authenticity": (inputs.authenticity_confidence, 5),
    }
    points = sum(value * weight for value, weight in values.values())
    reasons = tuple(
        ReasonComponent(
            f"CONFIDENCE_{name.upper()}",
            f"信頼度: {name}",
            ReasonComponentType.POSITIVE if value >= 0.7 else ReasonComponentType.RISK,
            round(value, 6),
            Decimal(str(round(value * weight, 4))),
            "deterministic_confidence_v1",
        )
        for name, (value, weight) in values.items()
    )
    return _score(points), reasons


def calculate_overall_score(
    profit: int | None,
    return_on_cost: Decimal | None,
    sales_prospect: int,
    confidence: int,
    research_priority_score: float | None,
    major_risk_count: int,
    policy: RecommendationPolicy,
) -> int | None:
    if profit is None or return_on_cost is None:
        return None
    profit_ratio = _bounded(profit / max(policy.strong_profit_jpy, 1))
    return_ratio = _bounded(float(return_on_cost))
    score = (
        profit_ratio * 25
        + return_ratio * 20
        + sales_prospect * 0.25
        + confidence * 0.20
        + (research_priority_score or 0) * 0.10
        - min(30, major_risk_count * 15)
    )
    return _score(score)


def classify_recommendation(
    profit: int | None,
    return_on_cost: Decimal | None,
    sales_prospect: int,
    confidence: int,
    sufficient_comparables: bool,
    shipping_known: bool,
    major_risks: tuple[str, ...],
    policy: RecommendationPolicy,
) -> RecommendationTier:
    if profit is None or not shipping_known or profit < policy.minimum_candidate_profit_jpy:
        return RecommendationTier.REJECT
    if major_risks:
        return RecommendationTier.CANDIDATE
    if (
        profit >= policy.strong_profit_jpy
        and return_on_cost is not None
        and return_on_cost >= policy.strong_return_on_cost
        and sales_prospect >= policy.sales_prospect_threshold
        and confidence >= policy.strong_confidence_threshold
        and sufficient_comparables
    ):
        return RecommendationTier.STRONGLY_RECOMMENDED
    if (
        profit >= policy.recommended_profit_jpy
        and sales_prospect >= policy.sales_prospect_threshold
        and confidence >= policy.recommended_confidence_threshold
        and sufficient_comparables
    ):
        return RecommendationTier.RECOMMENDED
    return RecommendationTier.CANDIDATE


def _financial_reasons(
    inputs: RecommendationInput,
    shipping: ShippingEstimate,
    fee: int | None,
    profit: int | None,
    return_on_cost: Decimal | None,
) -> list[ReasonComponent]:
    reasons = [
        ReasonComponent(
            "MERCARI_FEE",
            "メルカリ販売手数料",
            ReasonComponentType.ASSUMPTION,
            fee,
            None,
            "versioned_fee_rule",
        ),
        ReasonComponent(
            "SHIPPING_ESTIMATE",
            "再販売送料の推定",
            ReasonComponentType.ASSUMPTION
            if shipping.amount_jpy is not None
            else ReasonComponentType.CONFIRMATION_REQUIRED,
            {
                "amount_jpy": shipping.amount_jpy,
                "source": shipping.source.value,
                "confidence": shipping.confidence,
            },
            None,
            "shipping_fallback",
        ),
    ]
    if inputs.estimated_sale_price_jpy is None:
        reasons.append(
            ReasonComponent(
                "SALE_PRICE_UNAVAILABLE",
                "相場価格を計算できる売却済み証拠がありません",
                ReasonComponentType.CONFIRMATION_REQUIRED,
                None,
                None,
                "price_statistics",
            )
        )
    if inputs.sourcing_price_jpy is None:
        reasons.append(
            ReasonComponent(
                "SOURCING_COST_UNAVAILABLE",
                "仕入価格が不明です",
                ReasonComponentType.CONFIRMATION_REQUIRED,
                None,
                None,
                "source_observation",
            )
        )
    if profit is not None:
        reasons.append(
            ReasonComponent(
                "EXPECTED_PROFIT",
                "決定論的な予想利益",
                ReasonComponentType.POSITIVE if profit >= 300 else ReasonComponentType.NEGATIVE,
                profit,
                None,
                "profit_calculator",
            )
        )
    if return_on_cost is not None:
        reasons.append(
            ReasonComponent(
                "RETURN_ON_COST",
                "仕入原価に対する利益率",
                ReasonComponentType.POSITIVE
                if return_on_cost >= Decimal("0.25")
                else ReasonComponentType.NEGATIVE,
                str(return_on_cost.quantize(Decimal("0.000001"))),
                None,
                "margin_calculator",
            )
        )
    return reasons


def _overall_reasons(
    profit: int,
    return_on_cost: Decimal,
    sales_prospect: int,
    confidence: int,
    research_priority_score: float | None,
    policy: RecommendationPolicy,
) -> tuple[ReasonComponent, ...]:
    components = (
        (
            "OVERALL_PROFIT",
            "総合点: 予想利益",
            _bounded(profit / max(policy.strong_profit_jpy, 1)) * 25,
        ),
        (
            "OVERALL_RETURN_ON_COST",
            "総合点: 仕入原価利益率",
            _bounded(float(return_on_cost)) * 20,
        ),
        ("OVERALL_SALES_PROSPECT", "総合点: 90日販売見込み", sales_prospect * 0.25),
        ("OVERALL_CONFIDENCE", "総合点: 信頼度", confidence * 0.20),
        (
            "OVERALL_RESEARCH_PRIORITY",
            "総合点: 調査優先度",
            (research_priority_score or 0) * 0.10,
        ),
    )
    return tuple(
        ReasonComponent(
            code,
            label,
            ReasonComponentType.POSITIVE if points > 0 else ReasonComponentType.ASSUMPTION,
            round(points, 4),
            Decimal(str(round(points, 4))),
            "overall_sourcing_score_v1",
        )
        for code, label, points in components
    )


def calculate_recommendation(
    inputs: RecommendationInput,
    policy: RecommendationPolicy,
) -> RecommendationResult:
    shipping = estimate_shipping(inputs, policy)
    sourcing_cost, fee, profit, return_on_cost, sales_margin = calculate_financials(
        inputs,
        policy,
        shipping,
    )
    sales_prospect, sales_reasons = calculate_sales_prospect(inputs, policy)
    confidence, confidence_reasons = calculate_confidence(inputs, shipping)
    overall = calculate_overall_score(
        profit,
        return_on_cost,
        sales_prospect,
        confidence,
        inputs.research_priority_score,
        len(inputs.major_risks),
        policy,
    )
    tier = classify_recommendation(
        profit,
        return_on_cost,
        sales_prospect,
        confidence,
        inputs.sufficient_comparables,
        shipping.amount_jpy is not None,
        inputs.major_risks,
        policy,
    )
    reasons = _financial_reasons(inputs, shipping, fee, profit, return_on_cost)
    reasons.extend(sales_reasons)
    reasons.extend(confidence_reasons)
    if profit is not None and return_on_cost is not None:
        reasons.extend(
            _overall_reasons(
                profit,
                return_on_cost,
                sales_prospect,
                confidence,
                inputs.research_priority_score,
                policy,
            )
        )
    if not inputs.sufficient_comparables:
        reasons.append(
            ReasonComponent(
                "INSUFFICIENT_COMPARABLES",
                "直近90日の採用可能な売却済み比較が3件未満です",
                ReasonComponentType.RISK,
                inputs.included_sold_comparable_count,
                Decimal("-20"),
                "price_statistics",
            )
        )
    for risk in inputs.major_risks:
        reasons.append(
            ReasonComponent(
                f"MAJOR_RISK_{risk.upper()}",
                risk,
                ReasonComponentType.RISK,
                True,
                Decimal("-15"),
                "product_analysis",
            )
        )
    reasons.append(
        ReasonComponent(
            "RECOMMENDATION_TIER",
            "4段階推奨分類",
            ReasonComponentType.POSITIVE
            if tier in {
                RecommendationTier.STRONGLY_RECOMMENDED,
                RecommendationTier.RECOMMENDED,
            }
            else ReasonComponentType.NEGATIVE,
            tier.value,
            None,
            policy.threshold_version,
        )
    )
    quantities = (
        tuple(
            QuantityEvaluation(
                quantity=quantity,
                total_sourcing_cost_jpy=sourcing_cost * quantity,
                total_expected_profit_jpy=(profit * quantity if profit is not None else None),
                per_unit_profit_jpy=profit,
            )
            for quantity in range(1, 5)
        )
        if sourcing_cost is not None
        else ()
    )
    return RecommendationResult(
        sourcing_cost_jpy=sourcing_cost,
        estimated_sale_price_jpy=inputs.estimated_sale_price_jpy,
        shipping=shipping,
        mercari_fee_jpy=fee,
        expected_profit_jpy=profit,
        return_on_cost=return_on_cost,
        sales_margin=sales_margin,
        sales_prospect_score=sales_prospect,
        confidence_score=confidence,
        overall_sourcing_score=overall,
        tier=tier,
        reasons=tuple(reasons),
        quantities=quantities,
        policy=policy,
    )


def recommendation_input_hash(
    inputs: RecommendationInput,
    policy: RecommendationPolicy,
) -> str:
    payload = {"inputs": asdict(inputs), "policy": asdict(policy)}
    snapshot = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(snapshot.encode()).hexdigest()


def integer_median(values: list[int]) -> int | None:
    return round(float(median(values))) if values else None
