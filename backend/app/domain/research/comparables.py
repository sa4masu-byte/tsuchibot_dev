import hashlib
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from statistics import median

from backend.app.domain.research.models import (
    ComparableDecision,
    ComparableEvidence,
    ListingStatus,
    MarketplaceListing,
    PriceStatistics,
    ResearchTarget,
    ShippingStatistics,
)

_TOKEN = re.compile(r"[\w-]+", re.UNICODE)


def _normalized(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def _tokens(value: str) -> set[str]:
    return set(_TOKEN.findall(_normalized(value)))


def _token_similarity(left: str, right: str) -> float:
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _condition_similarity(target: str, listing: str | None) -> float:
    if target == "unknown" or not listing or listing == "unknown":
        return 0.6
    return 1.0 if _normalized(target) == _normalized(listing) else 0.25


class ComparableRanker:
    version = "comparable-ranking-v1"

    def rank(
        self,
        target: ResearchTarget,
        listings: tuple[MarketplaceListing, ...],
        evidence_period_start: datetime,
        evidence_period_end: datetime,
    ) -> tuple[ComparableEvidence, ...]:
        deduplicated = {listing.external_listing_id: listing for listing in listings}
        evidence = [
            self._evaluate(target, listing, evidence_period_start, evidence_period_end)
            for listing in deduplicated.values()
        ]
        return tuple(
            sorted(
                evidence,
                key=lambda item: (-item.total_similarity, item.listing.external_listing_id),
            )
        )

    def _evaluate(
        self,
        target: ResearchTarget,
        listing: MarketplaceListing,
        evidence_period_start: datetime,
        evidence_period_end: datetime,
    ) -> ComparableEvidence:
        normalized_title = _normalized(listing.title)
        model_similarity = (
            max(
                (
                    1.0 if _normalized(model) in normalized_title else 0.0
                    for model in target.model_numbers
                ),
                default=0.0,
            )
            if target.model_numbers
            else None
        )
        title_similarity = SequenceMatcher(
            None,
            _normalized(target.source_title),
            normalized_title,
        ).ratio()
        attributes = " ".join(
            value
            for value in (
                target.manufacturer,
                target.brand,
                target.series,
                target.product_type,
                target.category,
            )
            if value
        )
        attribute_similarity = _token_similarity(attributes, listing.title)
        condition_similarity = _condition_similarity(target.condition, listing.condition)
        weighted: list[tuple[float, float]] = [
            (title_similarity, 0.3),
            (attribute_similarity, 0.2),
            (condition_similarity, 0.1),
        ]
        if model_similarity is not None:
            weighted.append((model_similarity, 0.4))
        total = sum(value * weight for value, weight in weighted) / sum(
            weight for _, weight in weighted
        )
        if listing.is_reserved:
            total *= 0.9

        reason: str | None = None
        decision = ComparableDecision.INCLUDE
        if listing.is_bundle and listing.bundle_unit_count is None:
            decision = ComparableDecision.EXCLUDE
            reason = "bundle_unit_count_unknown"
        elif listing.is_junk and target.condition not in {"poor", "junk"}:
            decision = ComparableDecision.EXCLUDE
            reason = "junk_condition_mismatch"
        elif condition_similarity < 0.5:
            decision = ComparableDecision.REVIEW
            reason = "condition_mismatch"
        elif total < 0.45:
            decision = ComparableDecision.EXCLUDE
            reason = "low_similarity"
        elif listing.is_reserved or total < 0.65:
            decision = ComparableDecision.REVIEW
            reason = "manual_review_required"

        sold_in_period = listing.status is ListingStatus.SOLD and (
            (
                listing.sold_at is not None
                and evidence_period_start <= listing.sold_at <= evidence_period_end
            )
            or (
                listing.sold_at is None
                and listing.listed_at is not None
                and evidence_period_start <= listing.listed_at <= evidence_period_end
            )
        )
        included_in_price = decision is ComparableDecision.INCLUDE and sold_in_period
        included_in_shipping = (
            decision is not ComparableDecision.EXCLUDE
            and listing.estimated_shipping_jpy is not None
        )
        return ComparableEvidence(
            listing=listing,
            model_similarity=model_similarity,
            title_similarity=round(title_similarity, 6),
            condition_similarity=round(condition_similarity, 6),
            attribute_similarity=round(attribute_similarity, 6),
            total_similarity=round(total, 6),
            default_decision=decision,
            current_decision=decision,
            decision_reason=reason,
            included_in_price=included_in_price,
            included_in_shipping=included_in_shipping,
        )


def _integer_median(values: list[int]) -> int:
    return round(float(median(values)))


def calculate_price_statistics(
    evidence: tuple[ComparableEvidence, ...],
    minimum_sold_comparables: int = 3,
) -> PriceStatistics:
    if minimum_sold_comparables < 1:
        raise ValueError("minimum_sold_comparables must be positive")
    included = [
        (item.listing.external_listing_id, item.listing.effective_unit_price_jpy)
        for item in evidence
        if item.included_in_price and item.listing.effective_unit_price_jpy is not None
    ]
    included.sort(key=lambda item: item[0])
    snapshot = json.dumps(included, separators=(",", ":"), ensure_ascii=False)
    snapshot_hash = hashlib.sha256(snapshot.encode()).hexdigest()
    prices = sorted(price for _, price in included if price is not None)
    if not prices:
        return PriceStatistics(snapshot_hash, 0, None, None, None, None, None, False)

    midpoint = len(prices) // 2
    lower_half = prices[: midpoint + 1] if len(prices) == 1 else prices[:midpoint]
    median_price = _integer_median(prices)
    dispersion = (
        round((max(prices) - min(prices)) / median_price, 6) if median_price else None
    )
    return PriceStatistics(
        evidence_snapshot_hash=snapshot_hash,
        included_count=len(prices),
        median_price_jpy=median_price,
        lower_quartile_price_jpy=_integer_median(lower_half),
        minimum_price_jpy=min(prices),
        maximum_price_jpy=max(prices),
        dispersion=dispersion,
        sufficient_evidence=len(prices) >= minimum_sold_comparables,
    )


def calculate_shipping_statistics(
    evidence: tuple[ComparableEvidence, ...],
) -> ShippingStatistics:
    included = [item for item in evidence if item.included_in_shipping]
    amounts = sorted(
        item.listing.estimated_shipping_jpy
        for item in included
        if item.listing.estimated_shipping_jpy is not None
    )
    methods = Counter(
        item.listing.shipping_method
        for item in included
        if item.listing.shipping_method is not None
    )
    method = methods.most_common(1)[0][0] if methods else None
    count = len(amounts)
    return ShippingStatistics(
        source_type="mercari_listing",
        evidence_count=count,
        median_shipping_jpy=_integer_median(amounts) if amounts else None,
        shipping_method=method,
        confidence=round(min(1.0, count / 3), 6),
        reason="explicit_or_normalized_listing_shipping" if amounts else "no_shipping_evidence",
    )


def default_evidence_period(
    now: datetime,
    evidence_days: int = 90,
) -> tuple[datetime, datetime]:
    if evidence_days < 1:
        raise ValueError("evidence_days must be positive")
    return now - timedelta(days=evidence_days), now
