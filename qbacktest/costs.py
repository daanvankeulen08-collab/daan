"""Explicit, adverse transaction-cost model.

The engine has exactly two cost knobs and both are mandatory:

* ``commission_bps``: charged on the traded notional of every fill;
* ``slippage_bps``: always adverse, it moves the fill price against the order.

One basis point is ``1 / 10_000``.  Costs are pure functions of their inputs:
no randomness, no clock, no external state.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from qbacktest.errors import InvalidCostError

#: Basis points per unit (100% == 10_000 bps).
BPS_PER_UNIT = 10_000

#: Upper bound (exclusive) for both cost parameters.
#:
#: A commission of 100% or more cannot be funded by the available cash without
#: producing a negative (short) position, and a slippage of 100% or more would
#: produce a non-positive fill price.  Both would break the long/flat-only
#: contract, so they are rejected instead of silently repaired.
MAX_BPS_EXCLUSIVE = float(BPS_PER_UNIT)


def validate_bps(value: object, *, field: str) -> float:
    """Return ``value`` as a finite, non-negative basis-point value.

    Raises:
        InvalidCostError: if the value is not a real number, is NaN or
            infinite, is negative, or is not strictly below 10_000 bps.
    """

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidCostError(
            f"{field} must be a real number; got {type(value).__name__}"
        )
    number = float(value)
    if not math.isfinite(number):
        raise InvalidCostError(f"{field} must be finite; got {value!r}")
    if number < 0.0:
        raise InvalidCostError(f"{field} must be >= 0; got {value!r}")
    if number >= MAX_BPS_EXCLUSIVE:
        raise InvalidCostError(
            f"{field} must be < {BPS_PER_UNIT} bps (100%); got {value!r}"
        )
    return number


@dataclass(frozen=True, slots=True)
class CostModel:
    """A validated, immutable pair of transaction-cost parameters."""

    commission_bps: float
    slippage_bps: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "commission_bps",
            validate_bps(self.commission_bps, field="commission_bps"),
        )
        object.__setattr__(
            self,
            "slippage_bps",
            validate_bps(self.slippage_bps, field="slippage_bps"),
        )

    @property
    def commission_rate(self) -> float:
        """Commission as a decimal fraction of the traded notional."""

        return self.commission_bps / BPS_PER_UNIT

    @property
    def slippage_rate(self) -> float:
        """Slippage as a decimal fraction applied adversely to the fill."""

        return self.slippage_bps / BPS_PER_UNIT

    def buy_fill_price(self, open_price: float) -> float:
        """Return the buy fill price: ``open * (1 + slippage)``."""

        return open_price * (1.0 + self.slippage_rate)

    def sell_fill_price(self, open_price: float) -> float:
        """Return the sell fill price: ``open * (1 - slippage)``."""

        return open_price * (1.0 - self.slippage_rate)

    def commission_for(self, notional: float) -> float:
        """Return the commission charged on ``notional``."""

        return notional * self.commission_rate

    def to_dict(self) -> dict[str, float]:
        """Return a JSON-ready view of the cost parameters."""

        return {
            "commission_bps": self.commission_bps,
            "slippage_bps": self.slippage_bps,
        }


def buy_fill_price(open_price: float, *, slippage_bps: float) -> float:
    """Return the adverse buy fill price for a raw slippage parameter."""

    return CostModel(
        commission_bps=0.0, slippage_bps=slippage_bps
    ).buy_fill_price(open_price)


def sell_fill_price(open_price: float, *, slippage_bps: float) -> float:
    """Return the adverse sell fill price for a raw slippage parameter."""

    return CostModel(
        commission_bps=0.0, slippage_bps=slippage_bps
    ).sell_fill_price(open_price)


def commission_amount(notional: float, *, commission_bps: float) -> float:
    """Return the commission charged on ``notional``."""

    return CostModel(
        commission_bps=commission_bps, slippage_bps=0.0
    ).commission_for(notional)


__all__ = [
    "BPS_PER_UNIT",
    "CostModel",
    "MAX_BPS_EXCLUSIVE",
    "buy_fill_price",
    "commission_amount",
    "sell_fill_price",
    "validate_bps",
]
