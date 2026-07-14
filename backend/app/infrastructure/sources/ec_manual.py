from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from backend.app.application.ec import ECSourceProvider
from backend.app.domain.ec import (
    ECOffer,
    ECProductType,
    ECSearchKeyword,
    ECSource,
)


class _StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ManualECOfferInput(_StrictInput):
    source: ECSource
    source_item_id: str = Field(min_length=1)
    canonical_url: HttpUrl
    title: str = Field(min_length=1)
    displayed_price_jpy: int = Field(ge=0)
    sourcing_shipping_jpy: int = Field(default=0, ge=0)
    definite_coupon_jpy: int = Field(default=0, ge=0)
    points_reference_jpy: int = Field(default=0, ge=0)
    available: bool = True
    category: str | None = None
    product_type: ECProductType = ECProductType.GENERAL
    image_urls: list[HttpUrl] = Field(default_factory=list, max_length=5)
    selected_variant: str | None = None
    variant_price_confirmed: bool = True
    delivery_days: int | None = Field(default=None, ge=0)
    product_rating: float | None = Field(default=None, ge=0, le=5)
    review_count: int | None = Field(default=None, ge=0)
    seller_rating: float | None = Field(default=None, ge=0, le=5)
    seller_name: str | None = None
    shop_id: str | None = None
    shop_rating: float | None = Field(default=None, ge=0, le=5)
    brand: str | None = None
    character_name: str | None = None
    authenticity_supported: bool = False
    original_currency: str | None = None
    original_amount: str | None = None
    matched_keyword: str | None = None
    raw_metadata: dict[str, object] = Field(default_factory=dict)

    def to_domain(self) -> ECOffer:
        return ECOffer(
            source=self.source,
            source_item_id=self.source_item_id,
            canonical_url=str(self.canonical_url),
            title=self.title,
            displayed_price_jpy=self.displayed_price_jpy,
            sourcing_shipping_jpy=self.sourcing_shipping_jpy,
            definite_coupon_jpy=self.definite_coupon_jpy,
            points_reference_jpy=self.points_reference_jpy,
            available=self.available,
            category=self.category,
            product_type=self.product_type,
            image_urls=tuple(str(url) for url in self.image_urls),
            selected_variant=self.selected_variant,
            variant_price_confirmed=self.variant_price_confirmed,
            delivery_days=self.delivery_days,
            product_rating=self.product_rating,
            review_count=self.review_count,
            seller_rating=self.seller_rating,
            seller_name=self.seller_name,
            shop_id=self.shop_id,
            shop_rating=self.shop_rating,
            brand=self.brand,
            character_name=self.character_name,
            authenticity_supported=self.authenticity_supported,
            original_currency=self.original_currency,
            original_amount=self.original_amount,
            matched_keyword=self.matched_keyword,
            raw_metadata=self.raw_metadata,
        )


class ManualECDocument(_StrictInput):
    schema_version: Literal["ec-manual-v1"]
    useful_jimoty_candidates: int = Field(default=0, ge=0)
    complete_scan: bool = False
    high_confidence_hypothesis: bool = False
    profit_pattern_keywords: list[str] = Field(default_factory=list, max_length=20)
    mercari_demand_keywords: list[str] = Field(default_factory=list, max_length=20)
    sale_discount_keywords: list[str] = Field(default_factory=list, max_length=20)
    offers: list[ManualECOfferInput] = Field(default_factory=list, max_length=200)


class _ManualECAdapter(ECSourceProvider):
    parser_version = "ec-manual-v1"

    def __init__(self, offers: tuple[ECOffer, ...]) -> None:
        self._offers = offers

    async def collect(self, keywords: tuple[ECSearchKeyword, ...]) -> tuple[ECOffer, ...]:
        allowed = {item.value.casefold() for item in keywords}
        return tuple(
            offer
            for offer in self._offers
            if offer.source is self.source
            and (offer.matched_keyword is None or offer.matched_keyword.casefold() in allowed)
        )


class AmazonManualAdapter(_ManualECAdapter):
    source = ECSource.AMAZON


class RakutenManualAdapter(_ManualECAdapter):
    source = ECSource.RAKUTEN


class AliExpressManualAdapter(_ManualECAdapter):
    source = ECSource.ALIEXPRESS


class SheinManualAdapter(_ManualECAdapter):
    source = ECSource.SHEIN


def load_manual_ec_document(
    path: Path,
) -> tuple[ManualECDocument, tuple[ECSourceProvider, ...]]:
    document = ManualECDocument.model_validate_json(path.read_bytes())
    offers = tuple(item.to_domain() for item in document.offers)
    return document, (
        AmazonManualAdapter(offers),
        RakutenManualAdapter(offers),
        AliExpressManualAdapter(offers),
        SheinManualAdapter(offers),
    )
