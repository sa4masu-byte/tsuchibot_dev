from dataclasses import dataclass
from enum import StrEnum


class InventoryStatus(StrEnum):
    PURCHASED = "purchased"
    LISTED = "listed"
    PARTIALLY_SOLD = "partially_sold"
    SOLD = "sold"
    RETURNED = "returned"
    CANCELLED = "cancelled"
    UNSOLD_90_DAYS = "unsold_90_days"
    DAMAGED = "damaged"
    LOST = "lost"
    OTHER_FAILURE = "other_failure"


class NegativeOutcomeType(StrEnum):
    RETURNED = "returned"
    CANCELLED = "cancelled"
    UNSOLD_90_DAYS = "unsold_90_days"
    DAMAGED = "damaged"
    LOST = "lost"
    OTHER = "other"


class PreferenceSignal(StrEnum):
    WANT = "want"
    SLIGHTLY_INTERESTED = "slightly_interested"
    DO_NOT_WANT = "do_not_want"
    CANNOT_JUDGE = "cannot_judge"


class ResearchValueSignal(StrEnum):
    WORTH_RESEARCHING = "worth_researching"
    NOT_WORTH_RESEARCHING = "not_worth_researching"


@dataclass(frozen=True, slots=True)
class InventoryBalance:
    purchased_quantity: int
    sold_quantity: int = 0
    failed_quantity: int = 0

    def __post_init__(self) -> None:
        if not 1 <= self.purchased_quantity <= 4:
            raise ValueError("purchased quantity must be between 1 and 4")
        if self.sold_quantity < 0 or self.failed_quantity < 0:
            raise ValueError("inventory quantities cannot be negative")
        if self.sold_quantity + self.failed_quantity > self.purchased_quantity:
            raise ValueError("outcome quantity cannot exceed purchased quantity")

    @property
    def remaining_quantity(self) -> int:
        return self.purchased_quantity - self.sold_quantity - self.failed_quantity

    def require_available(self, quantity: int) -> None:
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        if quantity > self.remaining_quantity:
            raise ValueError("quantity cannot exceed remaining inventory")


def charged_amount(product_amount_jpy: int, shipping_jpy: int, coupon_jpy: int) -> int:
    if min(product_amount_jpy, shipping_jpy, coupon_jpy) < 0:
        raise ValueError("money amounts cannot be negative")
    amount = product_amount_jpy + shipping_jpy - coupon_jpy
    if amount < 0:
        raise ValueError("coupon cannot exceed product and shipping amount")
    return amount


def allocated_purchase_cost(
    total_purchase_cost_jpy: int,
    purchased_quantity: int,
    sold_quantity_before: int,
    sold_quantity: int,
) -> int:
    """Allocate cost cumulatively so split sales sum to the exact purchase cost."""
    if total_purchase_cost_jpy < 0:
        raise ValueError("purchase cost cannot be negative")
    balance = InventoryBalance(purchased_quantity, sold_quantity_before)
    balance.require_available(sold_quantity)
    cumulative_before = total_purchase_cost_jpy * sold_quantity_before // purchased_quantity
    cumulative_after = (
        total_purchase_cost_jpy * (sold_quantity_before + sold_quantity) // purchased_quantity
    )
    return cumulative_after - cumulative_before


def realised_profit(
    *,
    sold_price_jpy: int,
    actual_fee_jpy: int,
    actual_shipping_jpy: int,
    allocated_purchase_cost_jpy: int,
) -> int:
    if min(sold_price_jpy, actual_fee_jpy, actual_shipping_jpy) < 0:
        raise ValueError("money amounts cannot be negative")
    if actual_fee_jpy > sold_price_jpy:
        raise ValueError("selling fee cannot exceed sold price")
    return sold_price_jpy - actual_fee_jpy - actual_shipping_jpy - allocated_purchase_cost_jpy
