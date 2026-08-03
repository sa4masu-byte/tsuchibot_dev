import pytest
from backend.app.domain.inventory import (
    InventoryBalance,
    allocated_purchase_cost,
    charged_amount,
    realised_profit,
)


@pytest.mark.parametrize("quantity", [1, 2, 3, 4])
def test_inventory_accepts_phase_one_purchase_quantities(quantity: int) -> None:
    assert InventoryBalance(quantity).remaining_quantity == quantity


@pytest.mark.parametrize("quantity", [0, 5])
def test_inventory_rejects_out_of_range_purchase_quantities(quantity: int) -> None:
    with pytest.raises(ValueError, match="between 1 and 4"):
        InventoryBalance(quantity)


def test_inventory_rejects_sale_or_failure_beyond_remaining_quantity() -> None:
    balance = InventoryBalance(4, sold_quantity=2, failed_quantity=1)
    assert balance.remaining_quantity == 1
    with pytest.raises(ValueError, match="remaining inventory"):
        balance.require_available(2)


def test_charged_amount_is_deterministic_and_validated() -> None:
    assert charged_amount(3_000, 500, 300) == 3_200
    with pytest.raises(ValueError, match="coupon"):
        charged_amount(100, 0, 101)


def test_split_sale_cost_allocation_sums_to_exact_purchase_cost() -> None:
    first = allocated_purchase_cost(1_001, 3, 0, 1)
    second = allocated_purchase_cost(1_001, 3, 1, 1)
    final = allocated_purchase_cost(1_001, 3, 2, 1)
    assert (first, second, final) == (333, 334, 334)
    assert first + second + final == 1_001


def test_realised_profit_uses_only_actual_money_values() -> None:
    assert (
        realised_profit(
            sold_price_jpy=2_000,
            actual_fee_jpy=200,
            actual_shipping_jpy=210,
            allocated_purchase_cost_jpy=700,
        )
        == 890
    )
