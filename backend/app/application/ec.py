from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID, uuid4

from backend.app.application.catalog import RunContext
from backend.app.domain.catalog import Availability, NormalizedSourceProduct
from backend.app.domain.ec import (
    SOURCE_ORDER,
    ECEligibility,
    ECOffer,
    ECOfferEvaluation,
    ECPolicy,
    ECSearchKeyword,
    ECSource,
    build_ec_keywords,
    evaluate_ec_offer,
    should_explore_ec,
)


class ECSourceProvider(Protocol):
    source: ECSource
    parser_version: str

    async def collect(
        self, keywords: tuple[ECSearchKeyword, ...]
    ) -> tuple[ECOffer, ...]: ...


class ECExplorationRepository(Protocol):
    async def save(self, record: "ECExplorationRecord") -> None: ...


class CatalogCandidateIngestion(Protocol):
    async def execute(
        self, product: NormalizedSourceProduct, context: RunContext
    ) -> object: ...


@dataclass(frozen=True, slots=True)
class ECExplorationRequest:
    run_id: UUID
    observed_at: datetime
    useful_jimoty_candidates: int
    profit_pattern_keywords: tuple[str, ...] = ()
    mercari_demand_keywords: tuple[str, ...] = ()
    sale_discount_keywords: tuple[str, ...] = ()
    complete_scan: bool = False
    high_confidence_hypothesis: bool = False

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must include a timezone")


@dataclass(frozen=True, slots=True)
class ECSourceCollection:
    source: ECSource
    parser_version: str
    status: str
    offers: tuple[ECOffer, ...]
    error_category: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class ECExplorationRecord:
    id: UUID
    request: ECExplorationRequest
    policy: ECPolicy
    trigger_reason: str
    keywords: tuple[ECSearchKeyword, ...]
    collections: tuple[ECSourceCollection, ...]
    evaluations: tuple[ECOfferEvaluation, ...]
    status: str


class ConductECExploration:
    def __init__(
        self,
        providers: tuple[ECSourceProvider, ...],
        repository: ECExplorationRepository,
        catalog_ingestion: CatalogCandidateIngestion | None = None,
        policy: ECPolicy | None = None,
    ) -> None:
        self._providers = {provider.source: provider for provider in providers}
        self._repository = repository
        self._catalog_ingestion = catalog_ingestion
        self._policy = policy or ECPolicy()

    async def execute(self, request: ECExplorationRequest) -> ECExplorationRecord:
        if not should_explore_ec(
            request.useful_jimoty_candidates,
            self._policy,
            complete_scan=request.complete_scan,
            high_confidence_hypothesis=request.high_confidence_hypothesis,
        ):
            record = ECExplorationRecord(
                id=uuid4(),
                request=request,
                policy=self._policy,
                trigger_reason="sufficient_jimoty_candidates",
                keywords=(),
                collections=(),
                evaluations=(),
                status="not_required",
            )
            await self._repository.save(record)
            return record

        keywords = build_ec_keywords(
            request.profit_pattern_keywords,
            request.mercari_demand_keywords,
            request.sale_discount_keywords,
            self._policy.keyword_limit,
        )
        trigger_reason = (
            "complete_scan"
            if request.complete_scan
            else "high_confidence_hypothesis"
            if request.high_confidence_hypothesis
            else "insufficient_jimoty_candidates"
        )
        collections: list[ECSourceCollection] = []
        evaluations: list[ECOfferEvaluation] = []
        for source in SOURCE_ORDER:
            provider = self._providers.get(source)
            if provider is None:
                collections.append(
                    ECSourceCollection(
                        source=source,
                        parser_version="unavailable",
                        status="unavailable",
                        offers=(),
                        error_category="policy",
                        error_message="No permitted source adapter is configured.",
                    )
                )
                continue
            try:
                offers = await provider.collect(keywords)
                source_evaluations = tuple(
                    evaluate_ec_offer(offer, self._policy) for offer in offers
                )
                evaluations.extend(source_evaluations)
                collections.append(
                    ECSourceCollection(
                        source=source,
                        parser_version=provider.parser_version,
                        status="completed",
                        offers=offers,
                    )
                )
            except Exception as exc:
                collections.append(
                    ECSourceCollection(
                        source=source,
                        parser_version=provider.parser_version,
                        status="failed",
                        offers=(),
                        error_category=type(exc).__name__,
                        error_message=str(exc),
                    )
                )
        status = (
            "partial_failure"
            if any(item.status in {"failed", "unavailable"} for item in collections)
            else "completed"
        )
        record = ECExplorationRecord(
            id=uuid4(),
            request=request,
            policy=self._policy,
            trigger_reason=trigger_reason,
            keywords=keywords,
            collections=tuple(collections),
            evaluations=tuple(evaluations),
            status=status,
        )
        await self._repository.save(record)
        if self._catalog_ingestion is not None:
            for evaluation in evaluations:
                if evaluation.eligibility is ECEligibility.ELIGIBLE:
                    await self._catalog_ingestion.execute(
                        self._normalized_candidate(evaluation),
                        RunContext(request.run_id, request.observed_at),
                    )
        return record

    @staticmethod
    def _normalized_candidate(evaluation: ECOfferEvaluation) -> NormalizedSourceProduct:
        offer = evaluation.offer
        metadata: dict[str, object] = dict(offer.raw_metadata or {})
        metadata.update(
            {
                "sourcing_shipping_jpy": offer.sourcing_shipping_jpy,
                "definite_coupon_jpy": offer.definite_coupon_jpy,
                "points_reference_jpy": offer.points_reference_jpy,
                "sourcing_cost_jpy": evaluation.sourcing_cost_jpy,
                "delivery_days": offer.delivery_days,
                "selected_variant": offer.selected_variant,
                "product_rating": offer.product_rating,
                "review_count": offer.review_count,
                "seller_rating": offer.seller_rating,
                "authenticity_supported": offer.authenticity_supported,
                "ec_delivery_score": 100 if offer.delivery_days is not None else None,
                "ec_policy_version": "ec-phase1-v1",
            }
        )
        return NormalizedSourceProduct(
            source_type=offer.source.value,
            source_location_id=offer.source.value,
            source_item_id=offer.source_item_id,
            canonical_url=offer.canonical_url,
            title=offer.title,
            displayed_price_jpy=offer.displayed_price_jpy,
            category=offer.category,
            availability=(
                Availability.AVAILABLE if offer.available else Availability.UNAVAILABLE
            ),
            listing_timestamp=None,
            image_urls=offer.image_urls,
            raw_metadata=metadata,
            parser_version="ec-manual-v1",
        )
