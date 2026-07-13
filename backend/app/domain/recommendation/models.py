from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class RecommendationTier(StrEnum):
    STRONGLY_RECOMMENDED = "strongly_recommended"
    RECOMMENDED = "recommended"
    CANDIDATE = "candidate"
    REJECT = "reject"


class ReasonComponentType(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    RISK = "risk"
    ASSUMPTION = "assumption"
    CONFIRMATION_REQUIRED = "confirmation_required"


class ShippingEstimateSource(StrEnum):
    SAME_PRODUCT_MEDIAN = "same_product_median"
    SIMILAR_PRODUCT_MEDIAN = "similar_product_median"
    STANDARD_METHOD_MAPPING = "standard_method_mapping"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ReasonComponent:
    code: str
    label: str
    component_type: ReasonComponentType
    value: object | None
    score_delta: Decimal | None
    source: str

    def __post_init__(self) -> None:
        if not self.code.strip() or not self.label.strip() or not self.source.strip():
            raise ValueError("reason code, label, and source cannot be empty")


@dataclass(frozen=True, slots=True)
class ShippingEstimate:
    amount_jpy: int | None
    source: ShippingEstimateSource
    confidence: float
    evidence_count: int
    reason: str

    def __post_init__(self) -> None:
        if self.amount_jpy is not None and self.amount_jpy < 0:
            raise ValueError("shipping amount cannot be negative")
        if not 0 <= self.confidence <= 1:
            raise ValueError("shipping confidence must be between zero and one")
        if self.evidence_count < 0 or not self.reason.strip():
            raise ValueError("shipping evidence count and reason are invalid")


@dataclass(frozen=True, slots=True)
class RecommendationInput:
    sourcing_price_jpy: int | None
    sourcing_shipping_jpy: int = 0
    definite_coupon_jpy: int = 0
    estimated_sale_price_jpy: int | None = None
    same_product_shipping_median_jpy: int | None = None
    same_product_shipping_count: int = 0
    similar_product_shipping_median_jpy: int | None = None
    similar_product_shipping_count: int = 0
    shipping_method: str | None = None
    shipping_evidence_confidence: float = 0
    sold_count: int = 0
    active_count: int = 0
    included_sold_comparable_count: int = 0
    sufficient_comparables: bool = False
    average_comparable_similarity: float | None = None
    price_dispersion: float | None = None
    product_identity_confidence: float = 0
    model_number_confidence: float = 0
    condition_confidence: float = 0
    authenticity_confidence: float = 0
    price_competitiveness: float | None = None
    seasonality_score: float | None = None
    hypothesis_score: float | None = None
    ec_delivery_score: float | None = None
    research_priority_score: float | None = None
    major_risks: tuple[str, ...] = ()
    research_evidence_snapshot_hash: str = ""

    def __post_init__(self) -> None:
        money_values = {
            "sourcing_price_jpy": self.sourcing_price_jpy,
            "sourcing_shipping_jpy": self.sourcing_shipping_jpy,
            "definite_coupon_jpy": self.definite_coupon_jpy,
            "estimated_sale_price_jpy": self.estimated_sale_price_jpy,
            "same_product_shipping_median_jpy": self.same_product_shipping_median_jpy,
            "similar_product_shipping_median_jpy": self.similar_product_shipping_median_jpy,
        }
        for name, value in money_values.items():
            if value is not None and value < 0:
                raise ValueError(f"{name} cannot be negative")
        if (
            self.sourcing_price_jpy is not None
            and self.definite_coupon_jpy
            > self.sourcing_price_jpy + self.sourcing_shipping_jpy
        ):
            raise ValueError("definite coupon cannot exceed sourcing subtotal")
        for name, value in {
            "sold_count": self.sold_count,
            "active_count": self.active_count,
            "included_sold_comparable_count": self.included_sold_comparable_count,
            "same_product_shipping_count": self.same_product_shipping_count,
            "similar_product_shipping_count": self.similar_product_shipping_count,
        }.items():
            if value < 0:
                raise ValueError(f"{name} cannot be negative")
        confidence_values = {
            "shipping_evidence_confidence": self.shipping_evidence_confidence,
            "average_comparable_similarity": self.average_comparable_similarity,
            "product_identity_confidence": self.product_identity_confidence,
            "model_number_confidence": self.model_number_confidence,
            "condition_confidence": self.condition_confidence,
            "authenticity_confidence": self.authenticity_confidence,
            "price_competitiveness": self.price_competitiveness,
        }
        for name, confidence_value in confidence_values.items():
            if confidence_value is not None and not 0 <= confidence_value <= 1:
                raise ValueError(f"{name} must be between zero and one")
        for name, score_value in {
            "seasonality_score": self.seasonality_score,
            "hypothesis_score": self.hypothesis_score,
            "ec_delivery_score": self.ec_delivery_score,
            "research_priority_score": self.research_priority_score,
        }.items():
            if score_value is not None and not 0 <= score_value <= 100:
                raise ValueError(f"{name} must be between zero and 100")
        if self.price_dispersion is not None and self.price_dispersion < 0:
            raise ValueError("price_dispersion cannot be negative")


@dataclass(frozen=True, slots=True)
class RecommendationPolicy:
    config_version: str = "phase1-v1"
    fee_rule_version: str = "mercari-standard-2026-07"
    fee_rate_basis_points: int = 1000
    shipping_rule_version: str = "mercari-shipping-2026-07"
    standard_shipping_by_method: tuple[tuple[str, int], ...] = ()
    scoring_version: str = "phase1-scores-v1"
    threshold_version: str = "phase1-thresholds-v1"
    minimum_candidate_profit_jpy: int = 300
    recommended_profit_jpy: int = 500
    strong_profit_jpy: int = 1000
    sales_prospect_threshold: int = 70
    recommended_confidence_threshold: int = 65
    strong_confidence_threshold: int = 80
    strong_return_on_cost: Decimal = Decimal("0.5")
    maximum_sold_volume: int = 10

    def __post_init__(self) -> None:
        if not 0 <= self.fee_rate_basis_points <= 10000:
            raise ValueError("fee rate must be between zero and 10000 basis points")
        if self.maximum_sold_volume < 1:
            raise ValueError("maximum sold volume must be positive")
        if not 0 <= self.sales_prospect_threshold <= 100:
            raise ValueError("sales prospect threshold must be between zero and 100")
        if self.strong_return_on_cost < 0:
            raise ValueError("strong return on cost cannot be negative")
        if any(amount < 0 for _, amount in self.standard_shipping_by_method):
            raise ValueError("standard shipping amounts cannot be negative")
        if not (
            0
            <= self.minimum_candidate_profit_jpy
            <= self.recommended_profit_jpy
            <= self.strong_profit_jpy
        ):
            raise ValueError("profit thresholds must be ordered")
        if not (
            0
            <= self.recommended_confidence_threshold
            <= self.strong_confidence_threshold
            <= 100
        ):
            raise ValueError("confidence thresholds must be ordered")

    @property
    def standard_shipping_mapping(self) -> dict[str, int]:
        return dict(self.standard_shipping_by_method)


@dataclass(frozen=True, slots=True)
class QuantityEvaluation:
    quantity: int
    total_sourcing_cost_jpy: int
    total_expected_profit_jpy: int | None
    per_unit_profit_jpy: int | None

    def __post_init__(self) -> None:
        if not 1 <= self.quantity <= 4:
            raise ValueError("quantity must be between one and four")
        if self.total_sourcing_cost_jpy < 0:
            raise ValueError("total sourcing cost cannot be negative")


@dataclass(frozen=True, slots=True)
class RecommendationResult:
    sourcing_cost_jpy: int | None
    estimated_sale_price_jpy: int | None
    shipping: ShippingEstimate
    mercari_fee_jpy: int | None
    expected_profit_jpy: int | None
    return_on_cost: Decimal | None
    sales_margin: Decimal | None
    sales_prospect_score: int
    confidence_score: int
    overall_sourcing_score: int | None
    tier: RecommendationTier
    reasons: tuple[ReasonComponent, ...]
    quantities: tuple[QuantityEvaluation, ...]
    policy: RecommendationPolicy

    def __post_init__(self) -> None:
        if not 0 <= self.sales_prospect_score <= 100:
            raise ValueError("sales prospect score must be between zero and 100")
        if not 0 <= self.confidence_score <= 100:
            raise ValueError("confidence score must be between zero and 100")
        if self.overall_sourcing_score is not None and not (
            0 <= self.overall_sourcing_score <= 100
        ):
            raise ValueError("overall sourcing score must be between zero and 100")
        if not self.reasons:
            raise ValueError("recommendation must contain structured reasons")
