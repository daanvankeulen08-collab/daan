"""Synthetic-data helpers shared by the qbacktest test modules.

These helpers are test-only.  They never read the real ``data/`` directory and
never touch the network; every expected number in the tests is hand-computed
from the fixture below.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Sequence

from qresearch.models import MarketBar, MarketSeries

BASE = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
SYMBOL = "SYNTH"
TIMEFRAME = "1m"

#: The canonical hand-computed fixture:
#:
#: ======  =====  =====
#: bar     open    close
#: ======  =====  =====
#: t0      100     100
#: t1      100     110
#: t2      110      90
#: t3       90     120
#: ======  =====  =====
FIXTURE_OHLC: tuple[tuple[float, float], ...] = (
    (100.0, 100.0),
    (100.0, 110.0),
    (110.0, 90.0),
    (90.0, 120.0),
)


def make_series_from(
    ohlc: Sequence[tuple[float, float]],
    *,
    symbol: str = SYMBOL,
    timeframe: str = TIMEFRAME,
) -> MarketSeries:
    """Build a one-minute synthetic series from ``(open, close)`` pairs.

    Highs and lows are the consistent envelope of the two prices, volume is
    fixed at 1000 and timestamps are consecutive UTC minutes.
    """

    bars = tuple(
        MarketBar(
            timestamp=BASE + timedelta(minutes=index),
            symbol=symbol,
            timeframe=timeframe,
            open=open_price,
            high=max(open_price, close),
            low=min(open_price, close),
            close=close,
            volume=1000.0,
        )
        for index, (open_price, close) in enumerate(ohlc)
    )
    return MarketSeries(bars)


def make_fixture_series() -> MarketSeries:
    """Return the canonical four-bar fixture used by the engine tests."""

    return make_series_from(FIXTURE_OHLC)


def make_empty_series() -> MarketSeries:
    """Return a ``MarketSeries`` that carries no bars.

    ``MarketSeries`` refuses to be *constructed* empty, so the frozen
    dataclass is instantiated without its validation and the empty tuple is
    injected directly.  This lets the engine's own emptiness guard be tested.
    """

    series = object.__new__(MarketSeries)
    object.__setattr__(series, "bars", ())
    return series
