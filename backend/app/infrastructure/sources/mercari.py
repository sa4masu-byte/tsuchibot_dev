from collections.abc import Mapping
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from backend.app.application.research import MarketplaceSearchResult
from backend.app.domain.research import (
    ListingStatus,
    MarketplaceListing,
    ResearchTarget,
    SearchQuery,
    SearchStage,
    ShippingResponsibility,
)


class _StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ManualTargetInput(_StrictInput):
    source_title: str = Field(min_length=1)
    category: str | None = None
    manufacturer: str | None = None
    brand: str | None = None
    model_numbers: list[str] = Field(default_factory=list)
    series: str | None = None
    product_type: str | None = None
    condition: str = "unknown"
    search_terms: list[str] = Field(default_factory=list, max_length=10)

    def to_domain(self) -> ResearchTarget:
        return ResearchTarget(
            source_title=self.source_title,
            category=self.category,
            manufacturer=self.manufacturer,
            brand=self.brand,
            model_numbers=tuple(self.model_numbers),
            series=self.series,
            product_type=self.product_type,
            condition=self.condition,
            search_terms=tuple(self.search_terms),
        )


class ManualListingInput(_StrictInput):
    query_stage: SearchStage
    external_listing_id: str = Field(min_length=1)
    canonical_url: HttpUrl
    title: str = Field(min_length=1)
    status: ListingStatus
    displayed_price_jpy: int = Field(ge=0)
    sold_at: datetime | None = None
    listed_at: datetime | None = None
    condition: str | None = None
    shipping_method: str | None = None
    shipping_responsibility: ShippingResponsibility = ShippingResponsibility.UNKNOWN
    estimated_shipping_jpy: int | None = Field(default=None, ge=0)
    image_url: HttpUrl | None = None
    is_bundle: bool = False
    bundle_unit_count: int | None = Field(default=None, ge=1)
    is_junk: bool = False
    is_reserved: bool = False
    normalized_attributes: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def timestamps_have_timezones(self) -> "ManualListingInput":
        for value in (self.sold_at, self.listed_at):
            if value is not None and value.tzinfo is None:
                raise ValueError("listing timestamps must include a timezone")
        return self

    def to_domain(self) -> MarketplaceListing:
        return MarketplaceListing(
            external_listing_id=self.external_listing_id,
            canonical_url=str(self.canonical_url),
            title=self.title,
            status=self.status,
            displayed_price_jpy=self.displayed_price_jpy,
            sold_at=self.sold_at,
            listed_at=self.listed_at,
            condition=self.condition,
            shipping_method=self.shipping_method,
            shipping_responsibility=self.shipping_responsibility,
            estimated_shipping_jpy=self.estimated_shipping_jpy,
            image_url=str(self.image_url) if self.image_url else None,
            is_bundle=self.is_bundle,
            bundle_unit_count=self.bundle_unit_count,
            is_junk=self.is_junk,
            is_reserved=self.is_reserved,
            normalized_attributes=self.normalized_attributes,
        )


class ManualResearchDocument(_StrictInput):
    schema_version: Literal["mercari-manual-v1"]
    target: ManualTargetInput
    listings: list[ManualListingInput] = Field(max_length=100)


class ManualMercariAdapter:
    """Policy-safe fallback that normalizes user-provided evidence by search stage."""

    provider_name = "mercari_manual"
    parser_version = "mercari-manual-v1"

    def __init__(
        self,
        listings_by_stage: Mapping[SearchStage, tuple[MarketplaceListing, ...]],
        raw_result_ref: str = "manual:memory",
    ) -> None:
        self._listings_by_stage = dict(listings_by_stage)
        self._raw_result_ref = raw_result_ref

    async def search(
        self,
        query: SearchQuery,
        sold_limit: int,
        active_limit: int,
    ) -> MarketplaceSearchResult:
        listings = self._listings_by_stage.get(query.stage, ())
        sold = [listing for listing in listings if listing.status is ListingStatus.SOLD][
            :sold_limit
        ]
        active = [listing for listing in listings if listing.status is ListingStatus.ACTIVE][
            :active_limit
        ]
        return MarketplaceSearchResult(
            listings=tuple(sold + active),
            parser_version=self.parser_version,
            raw_result_ref=f"{self._raw_result_ref}:{query.stage.value}",
        )


def load_manual_research_document(
    path: Path,
) -> tuple[ResearchTarget, ManualMercariAdapter]:
    content = path.read_bytes()
    document = ManualResearchDocument.model_validate_json(content)
    grouped: dict[SearchStage, list[MarketplaceListing]] = {}
    for item in document.listings:
        grouped.setdefault(item.query_stage, []).append(item.to_domain())
    adapter = ManualMercariAdapter(
        {stage: tuple(listings) for stage, listings in grouped.items()},
        raw_result_ref=f"manual:{sha256(content).hexdigest()}",
    )
    return document.target.to_domain(), adapter
