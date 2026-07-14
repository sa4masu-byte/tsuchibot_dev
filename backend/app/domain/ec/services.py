import re

from backend.app.domain.ec.models import (
    ECEligibility,
    ECOffer,
    ECOfferEvaluation,
    ECPolicy,
    ECProductType,
    ECSearchKeyword,
    ECSearchStrategy,
)


def _normalize_keyword(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def build_ec_keywords(
    profit_patterns: tuple[str, ...],
    mercari_demand: tuple[str, ...],
    sale_discounts: tuple[str, ...],
    limit: int,
) -> tuple[ECSearchKeyword, ...]:
    if limit < 1:
        raise ValueError("EC keyword limit must be positive")
    result: list[ECSearchKeyword] = []
    seen: set[str] = set()
    groups = (
        (ECSearchStrategy.PROFIT_PATTERN, profit_patterns),
        (ECSearchStrategy.MERCARI_DEMAND, mercari_demand),
        (ECSearchStrategy.SALE_DISCOUNT, sale_discounts),
    )
    for strategy, values in groups:
        for value in values:
            normalized = _normalize_keyword(value)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(ECSearchKeyword(len(result) + 1, value.strip(), strategy))
            if len(result) == limit:
                return tuple(result)
    return tuple(result)


def should_explore_ec(
    useful_jimoty_candidates: int,
    policy: ECPolicy,
    *,
    complete_scan: bool = False,
    high_confidence_hypothesis: bool = False,
) -> bool:
    if useful_jimoty_candidates < 0:
        raise ValueError("useful candidate count cannot be negative")
    return (
        complete_scan
        or high_confidence_hypothesis
        or useful_jimoty_candidates < policy.minimum_useful_candidates
    )


def evaluate_ec_offer(offer: ECOffer, policy: ECPolicy) -> ECOfferEvaluation:
    rejected: list[str] = []
    confirmations: list[str] = []
    if not offer.available:
        rejected.append("unavailable")
    if offer.product_type is not ECProductType.GENERAL:
        rejected.append(f"excluded_product_type:{offer.product_type.value}")
    if (offer.brand or offer.character_name) and not offer.authenticity_supported:
        rejected.append("authenticity_unconfirmed")
    if offer.source.overseas:
        if not offer.selected_variant or not offer.variant_price_confirmed:
            confirmations.append("variant_price_unconfirmed")
        if offer.delivery_days is None:
            confirmations.append("delivery_days_unknown")
        elif offer.delivery_days > policy.overseas_delivery_days_max:
            rejected.append("delivery_over_limit")
        quality = (
            ("review_count", offer.review_count, policy.overseas_minimum_review_count),
            ("product_rating", offer.product_rating, policy.overseas_minimum_product_rating),
            ("seller_rating", offer.seller_rating, policy.overseas_minimum_seller_rating),
        )
        for name, value, minimum in quality:
            if value is None:
                confirmations.append(f"{name}_unknown")
            elif value < minimum:
                rejected.append(f"{name}_below_minimum")
    if rejected:
        eligibility = ECEligibility.REJECTED
        reasons = tuple(rejected + confirmations)
    elif confirmations:
        eligibility = ECEligibility.CONFIRMATION_REQUIRED
        reasons = tuple(confirmations)
    else:
        eligibility = ECEligibility.ELIGIBLE
        reasons = ("policy_requirements_satisfied",)
    return ECOfferEvaluation(
        offer=offer,
        eligibility=eligibility,
        sourcing_cost_jpy=offer.sourcing_cost_jpy,
        reason_codes=reasons,
    )


def practical_rakuten_offers(offers: tuple[ECOffer, ...]) -> tuple[ECOffer, ...]:
    rakuten = [offer for offer in offers if offer.source.value == "rakuten"]
    return tuple(
        sorted(
            rakuten,
            key=lambda offer: (
                not offer.available,
                offer.sourcing_cost_jpy,
                offer.delivery_days if offer.delivery_days is not None else 10_000,
                -(offer.shop_rating or 0),
                offer.source_item_id,
            ),
        )[:3]
    )
