"""Cost-model validation and fill-price arithmetic."""

from __future__ import annotations

import math
from dataclasses import FrozenInstanceError

import pytest

from qbacktest import CostModel, InvalidCostError
from qbacktest.costs import (
    BPS_PER_UNIT,
    buy_fill_price,
    commission_amount,
    sell_fill_price,
    validate_bps,
)


def test_bps_per_unit_is_ten_thousand() -> None:
    assert BPS_PER_UNIT == 10_000


def test_rates_are_decimal_fractions() -> None:
    costs = CostModel(commission_bps=10.0, slippage_bps=25.0)

    assert costs.commission_rate == pytest.approx(0.001, abs=1e-15)
    assert costs.slippage_rate == pytest.approx(0.0025, abs=1e-15)


def test_buy_fill_price_is_adverse() -> None:
    costs = CostModel(commission_bps=0.0, slippage_bps=10.0)

    assert costs.buy_fill_price(100.0) == pytest.approx(100.1, abs=1e-9)
    assert costs.buy_fill_price(100.0) > 100.0


def test_sell_fill_price_is_adverse() -> None:
    costs = CostModel(commission_bps=0.0, slippage_bps=10.0)

    assert costs.sell_fill_price(100.0) == pytest.approx(99.9, abs=1e-9)
    assert costs.sell_fill_price(100.0) < 100.0


def test_commission_is_proportional_to_the_notional() -> None:
    costs = CostModel(commission_bps=10.0, slippage_bps=0.0)

    assert costs.commission_for(1000.0) == pytest.approx(1.0, abs=1e-12)
    assert costs.commission_for(0.0) == 0.0


def test_module_level_helpers_match_the_cost_model() -> None:
    assert buy_fill_price(100.0, slippage_bps=10.0) == pytest.approx(100.1, abs=1e-9)
    assert sell_fill_price(100.0, slippage_bps=10.0) == pytest.approx(99.9, abs=1e-9)
    assert commission_amount(1000.0, commission_bps=10.0) == pytest.approx(1.0, abs=1e-12)


@pytest.mark.parametrize("value", [-1.0, -0.0001, -100.0])
def test_negative_bps_are_rejected(value: float) -> None:
    with pytest.raises(InvalidCostError):
        validate_bps(value, field="commission_bps")


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_bps_are_rejected(value: float) -> None:
    with pytest.raises(InvalidCostError):
        validate_bps(value, field="commission_bps")


@pytest.mark.parametrize("value", ["10", None, True, [10.0]])
def test_non_numeric_bps_are_rejected(value: object) -> None:
    with pytest.raises(InvalidCostError):
        validate_bps(value, field="slippage_bps")


def test_bps_of_one_hundred_percent_or_more_are_rejected() -> None:
    with pytest.raises(InvalidCostError):
        validate_bps(10_000.0, field="commission_bps")
    with pytest.raises(InvalidCostError):
        validate_bps(10_000.0, field="slippage_bps")


def test_cost_model_validates_on_construction() -> None:
    with pytest.raises(InvalidCostError):
        CostModel(commission_bps=-1.0, slippage_bps=0.0)
    with pytest.raises(InvalidCostError):
        CostModel(commission_bps=0.0, slippage_bps=float("nan"))


def test_cost_model_is_frozen() -> None:
    costs = CostModel(commission_bps=10.0, slippage_bps=0.0)

    with pytest.raises(FrozenInstanceError):
        costs.commission_bps = 20.0  # type: ignore[misc]


def test_cost_model_to_dict_is_json_ready() -> None:
    costs = CostModel(commission_bps=10.0, slippage_bps=2.5)

    assert costs.to_dict() == {"commission_bps": 10.0, "slippage_bps": 2.5}
    assert math.isfinite(costs.commission_rate)
