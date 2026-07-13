from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class SearchStage(StrEnum):
    EXACT_MODEL = "exact_model"
    MANUFACTURER_MODEL = "manufacturer_model"
    SERIES_PRODUCT_TYPE = "series_product_type"
    MANUFACTURER_PRODUCT_TYPE = "manufacturer_product_type"
    SIMILAR_PRODUCT = "similar_product"


class ListingStatus(StrEnum):
    SOLD = "sold"
    ACTIVE = "active"


class ShippingResponsibility(StrEnum):
    SELLER = "seller"
    BUYER = "buyer"
    UNKNOWN = "unknown"


class ComparableDecision(StrEnum):
    INCLUDE = "include"
    EXCLUDE = "exclude"
    REVIEW = "review"


@dataclass(frozen=True, slots=True)
class ResearchTarget:
    source_title: str
    category: str | None = None
    manufacturer: str | None = None
    brand: str | None = None
    model_numbers: tuple[str, ...] = ()
    series: str | None = None
    product_type: str | None = None
    condition: str = "unknown"
    search_terms: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.source_title.strip():
            raise ValueError("source_title cannot be empty")


@dataclass(frozen=True, slots=True)
class SearchQuery:
    order: int
    text: str
    stage: SearchStage
    normalized_text: str
    generated_by: str = "deterministic-v1"

    def __post_init__(self) -> None:
        if self.order < 1:
            raise ValueError("query order must be positive")
        if not self.text.strip() or not self.normalized_text:
            raise ValueError("query text cannot be empty")


@dataclass(frozen=True, slots=True)
class MarketplaceListing:
    external_listing_id: str
    canonical_url: str
    title: str
    status: ListingStatus
    displayed_price_jpy: int
    sold_at: datetime | None = None
    listed_at: datetime | None = None
    condition: str | None = None
    shipping_method: str | None = None
    shipping_responsibility: ShippingResponsibility = ShippingResponsibility.UNKNOWN
    estimated_shipping_jpy: int | None = None
    image_url: str | None = None
    is_bundle: bool = False
    bundle_unit_count: int | None = None
    is_junk: bool = False
    is_reserved: bool = False
    normalized_attributes: dict[str, object] | None = None
    marketplace: str = "mercari"

    def __post_init__(self) -> None:
        for field_name, value in {
            "external_listing_id": self.external_listing_id,
            "canonical_url": self.canonical_url,
            "title": self.title,
            "marketplace": self.marketplace,
        }.items():
            if not value.strip():
                raise ValueError(f"{field_name} cannot be empty")
        if not self.canonical_url.startswith(("https://", "http://")):
            raise ValueError("canonical_url must be HTTP(S)")
        if self.displayed_price_jpy < 0:
            raise ValueError("displayed_price_jpy cannot be negative")
        if self.estimated_shipping_jpy is not None and self.estimated_shipping_jpy < 0:
            raise ValueError("estimated_shipping_jpy cannot be negative")
        if self.bundle_unit_count is not None and self.bundle_unit_count < 1:
            raise ValueError("bundle_unit_count must be positive")

    @property
    def effective_unit_price_jpy(self) -> int | None:
        if not self.is_bundle:
            return self.displayed_price_jpy
        if self.bundle_unit_count is None:
            return None
        return round(self.displayed_price_jpy / self.bundle_unit_count)


@dataclass(frozen=True, slots=True)
class ComparableEvidence:
    listing: MarketplaceListing
    model_similarity: float | None
    title_similarity: float
    condition_similarity: float
    attribute_similarity: float
    total_similarity: float
    default_decision: ComparableDecision
    current_decision: ComparableDecision
    decision_reason: str | None
    included_in_price: bool
    included_in_shipping: bool


@dataclass(frozen=True, slots=True)
class PriceStatistics:
    evidence_snapshot_hash: str
    included_count: int
    median_price_jpy: int | None
    lower_quartile_price_jpy: int | None
    minimum_price_jpy: int | None
    maximum_price_jpy: int | None
    dispersion: float | None
    sufficient_evidence: bool


@dataclass(frozen=True, slots=True)
class ShippingStatistics:
    source_type: str
    evidence_count: int
    median_shipping_jpy: int | None
    shipping_method: str | None
    confidence: float
    reason: str
