from dataclasses import dataclass
from enum import StrEnum


class ECSource(StrEnum):
    AMAZON = "amazon"
    RAKUTEN = "rakuten"
    ALIEXPRESS = "aliexpress"
    SHEIN = "shein"

    @property
    def overseas(self) -> bool:
        return self in {ECSource.ALIEXPRESS, ECSource.SHEIN}


SOURCE_ORDER = (
    ECSource.AMAZON,
    ECSource.RAKUTEN,
    ECSource.ALIEXPRESS,
    ECSource.SHEIN,
)


class ECSearchStrategy(StrEnum):
    PROFIT_PATTERN = "profit_pattern"
    MERCARI_DEMAND = "mercari_demand"
    SALE_DISCOUNT = "sale_discount"


class ECProductType(StrEnum):
    GENERAL = "general"
    FOOD = "food"
    MEDICINE = "medicine"
    COSMETICS = "cosmetics"
    SUPPLEMENT = "supplement"
    BATTERY = "battery"
    MAINS_ELECTRICAL = "mains_electrical"


class ECEligibility(StrEnum):
    ELIGIBLE = "eligible"
    CONFIRMATION_REQUIRED = "confirmation_required"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class ECSearchKeyword:
    order: int
    value: str
    strategy: ECSearchStrategy

    def __post_init__(self) -> None:
        if self.order < 1 or not self.value.strip():
            raise ValueError("EC keyword order and value are required")


@dataclass(frozen=True, slots=True)
class ECOffer:
    source: ECSource
    source_item_id: str
    canonical_url: str
    title: str
    displayed_price_jpy: int
    sourcing_shipping_jpy: int = 0
    definite_coupon_jpy: int = 0
    points_reference_jpy: int = 0
    available: bool = True
    category: str | None = None
    product_type: ECProductType = ECProductType.GENERAL
    image_urls: tuple[str, ...] = ()
    selected_variant: str | None = None
    variant_price_confirmed: bool = True
    delivery_days: int | None = None
    product_rating: float | None = None
    review_count: int | None = None
    seller_rating: float | None = None
    seller_name: str | None = None
    shop_id: str | None = None
    shop_rating: float | None = None
    brand: str | None = None
    character_name: str | None = None
    authenticity_supported: bool = False
    original_currency: str | None = None
    original_amount: str | None = None
    matched_keyword: str | None = None
    raw_metadata: dict[str, object] | None = None

    def __post_init__(self) -> None:
        required_values: dict[str, str] = {
            "source_item_id": self.source_item_id,
            "canonical_url": self.canonical_url,
            "title": self.title,
        }
        for field_name, required_value in required_values.items():
            if not required_value.strip():
                raise ValueError(f"{field_name} cannot be empty")
        if not self.canonical_url.startswith(("https://", "http://")):
            raise ValueError("canonical_url must be HTTP(S)")
        money_values: dict[str, int] = {
            "displayed_price_jpy": self.displayed_price_jpy,
            "sourcing_shipping_jpy": self.sourcing_shipping_jpy,
            "definite_coupon_jpy": self.definite_coupon_jpy,
            "points_reference_jpy": self.points_reference_jpy,
        }
        for field_name, money_value in money_values.items():
            if money_value < 0:
                raise ValueError(f"{field_name} cannot be negative")
        if self.definite_coupon_jpy > self.displayed_price_jpy + self.sourcing_shipping_jpy:
            raise ValueError("definite coupon cannot exceed sourcing subtotal")
        if self.delivery_days is not None and self.delivery_days < 0:
            raise ValueError("delivery_days cannot be negative")
        if self.review_count is not None and self.review_count < 0:
            raise ValueError("review_count cannot be negative")
        rating_values: dict[str, float | None] = {
            "product_rating": self.product_rating,
            "seller_rating": self.seller_rating,
            "shop_rating": self.shop_rating,
        }
        for field_name, rating_value in rating_values.items():
            if rating_value is not None and not 0 <= rating_value <= 5:
                raise ValueError(f"{field_name} must be between zero and five")

    @property
    def sourcing_cost_jpy(self) -> int:
        return (
            self.displayed_price_jpy
            + self.sourcing_shipping_jpy
            - self.definite_coupon_jpy
        )


@dataclass(frozen=True, slots=True)
class ECPolicy:
    version: str = "ec-phase1-v1"
    keyword_limit: int = 20
    minimum_useful_candidates: int = 3
    overseas_delivery_days_max: int = 7
    overseas_minimum_review_count: int = 20
    overseas_minimum_product_rating: float = 4.5
    overseas_minimum_seller_rating: float = 4.5


@dataclass(frozen=True, slots=True)
class ECOfferEvaluation:
    offer: ECOffer
    eligibility: ECEligibility
    sourcing_cost_jpy: int
    reason_codes: tuple[str, ...]
