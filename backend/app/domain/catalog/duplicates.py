from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import StrEnum

from backend.app.domain.catalog.models import NormalizedSourceProduct


class DuplicateDecisionKind(StrEnum):
    EXACT = "exact"
    POTENTIAL = "potential"
    DISTINCT = "distinct"


@dataclass(frozen=True, slots=True)
class DuplicateDecision:
    kind: DuplicateDecisionKind
    matched_item_id: str | None
    reason: str
    confidence: float


class DuplicateDetectionService:
    """Finds duplicate evidence but never silently merges uncertain products."""

    def evaluate(
        self,
        candidate: NormalizedSourceProduct,
        existing: tuple[NormalizedSourceProduct, ...],
    ) -> DuplicateDecision:
        for product in existing:
            if candidate.identity == product.identity:
                return self._decision(
                    DuplicateDecisionKind.EXACT,
                    product,
                    "same_source_item_id",
                    1,
                )
        for product in existing:
            if candidate.canonical_url == product.canonical_url:
                return self._decision(DuplicateDecisionKind.EXACT, product, "same_canonical_url", 1)
        for product in existing:
            if self._same_image_price_location(candidate, product):
                return self._decision(
                    DuplicateDecisionKind.POTENTIAL,
                    product,
                    "image_hash_price_location_match",
                    0.95,
                )
        for product in existing:
            similarity = self._title_similarity(candidate.title, product.title)
            same_location = candidate.source_location_id == product.source_location_id
            prices_close = self._prices_close(
                candidate.displayed_price_jpy,
                product.displayed_price_jpy,
            )
            if same_location and prices_close and similarity >= 0.9:
                return self._decision(
                    DuplicateDecisionKind.POTENTIAL,
                    product,
                    "high_title_price_location_similarity",
                    round(similarity * 0.9, 3),
                )
        return DuplicateDecision(DuplicateDecisionKind.DISTINCT, None, "no_duplicate_evidence", 0)

    @staticmethod
    def _decision(
        kind: DuplicateDecisionKind,
        product: NormalizedSourceProduct,
        reason: str,
        confidence: float,
    ) -> DuplicateDecision:
        return DuplicateDecision(kind, product.source_item_id, reason, confidence)

    @staticmethod
    def _hashes(product: NormalizedSourceProduct) -> set[str]:
        value = product.raw_metadata.get("image_hashes", ())
        if not isinstance(value, list | tuple):
            return set()
        return {item for item in value if isinstance(item, str) and item}

    def _same_image_price_location(
        self,
        left: NormalizedSourceProduct,
        right: NormalizedSourceProduct,
    ) -> bool:
        return bool(self._hashes(left) & self._hashes(right)) and (
            left.displayed_price_jpy == right.displayed_price_jpy
            and left.source_location_id == right.source_location_id
        )

    @staticmethod
    def _title_similarity(left: str | None, right: str | None) -> float:
        if not left or not right:
            return 0
        return SequenceMatcher(None, left.casefold().strip(), right.casefold().strip()).ratio()

    @staticmethod
    def _prices_close(left: int | None, right: int | None) -> bool:
        if left is None or right is None:
            return False
        return abs(left - right) <= max(50, round(max(left, right) * 0.05))
