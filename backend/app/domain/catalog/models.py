from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class Availability(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class ChangeKind(StrEnum):
    NEW = "new"
    UNCHANGED = "unchanged"
    PRICE_CHANGED = "price_changed"
    AVAILABILITY_CHANGED = "availability_changed"
    PRICE_AND_AVAILABILITY_CHANGED = "price_and_availability_changed"

    @property
    def requires_reevaluation(self) -> bool:
        return self is not ChangeKind.UNCHANGED


@dataclass(frozen=True, slots=True)
class NormalizedSourceProduct:
    source_type: str
    source_location_id: str
    source_item_id: str
    canonical_url: str
    title: str | None
    displayed_price_jpy: int | None
    category: str | None
    availability: Availability
    listing_timestamp: datetime | None
    image_urls: tuple[str, ...]
    raw_metadata: dict[str, object]
    parser_version: str

    def __post_init__(self) -> None:
        required = {
            "source_type": self.source_type,
            "source_location_id": self.source_location_id,
            "source_item_id": self.source_item_id,
            "canonical_url": self.canonical_url,
            "parser_version": self.parser_version,
        }
        for field_name, value in required.items():
            if not value.strip():
                raise ValueError(f"{field_name} cannot be empty")
        if not self.canonical_url.startswith(("https://", "http://")):
            raise ValueError("canonical_url must be HTTP(S)")
        if self.displayed_price_jpy is not None and self.displayed_price_jpy < 0:
            raise ValueError("displayed_price_jpy cannot be negative")

    @property
    def identity(self) -> tuple[str, str]:
        return self.source_type, self.source_item_id


@dataclass(frozen=True, slots=True)
class SourceProductState:
    source_type: str
    source_item_id: str
    canonical_url: str
    current_price_jpy: int | None
    current_availability: Availability


@dataclass(frozen=True, slots=True)
class ProductChange:
    kind: ChangeKind
    previous_price_jpy: int | None
    current_price_jpy: int | None
    previous_availability: Availability | None
    current_availability: Availability

    @property
    def requires_reevaluation(self) -> bool:
        return self.kind.requires_reevaluation

    @property
    def price_delta_jpy(self) -> int | None:
        if self.previous_price_jpy is None or self.current_price_jpy is None:
            return None
        return self.current_price_jpy - self.previous_price_jpy


def detect_change(
    previous: SourceProductState | None,
    current: NormalizedSourceProduct,
) -> ProductChange:
    if previous is None:
        return ProductChange(
            kind=ChangeKind.NEW,
            previous_price_jpy=None,
            current_price_jpy=current.displayed_price_jpy,
            previous_availability=None,
            current_availability=current.availability,
        )

    price_changed = previous.current_price_jpy != current.displayed_price_jpy
    availability_changed = previous.current_availability is not current.availability
    if price_changed and availability_changed:
        kind = ChangeKind.PRICE_AND_AVAILABILITY_CHANGED
    elif price_changed:
        kind = ChangeKind.PRICE_CHANGED
    elif availability_changed:
        kind = ChangeKind.AVAILABILITY_CHANGED
    else:
        kind = ChangeKind.UNCHANGED
    return ProductChange(
        kind=kind,
        previous_price_jpy=previous.current_price_jpy,
        current_price_jpy=current.displayed_price_jpy,
        previous_availability=previous.current_availability,
        current_availability=current.availability,
    )
