# Block 2B — Deterministic Backtest Engine

Block 2B adds a small, deterministic backtest engine in the new, independent
package `qbacktest/`. It replays a discrete position signal over a validated
`qresearch.models.MarketSeries` and reports equity, trades and costs.

It is infrastructure, not a strategy. The package contains exactly two
baseline signals and no way to search for, tune or optimise anything.

Scope boundaries:

- no strategies beyond `buy_and_hold_signal` and `cash_signal`;
- no optimisation, parameter search, sweep, walk-forward or grid logic;
- no live data, no data download, no network access, no filesystem access;
- no model training, no LFM3/Ollama/LLM calls;
- no broker, order router, portfolio, risk manager or position sizing beyond
  "full notional, long or flat";
- no third-party runtime dependency: `qbacktest` uses the Python standard
  library plus the existing `qresearch` package;
- no file under `mdl/` or `qresearch/` was modified.

## Package layout

| File | Responsibility |
|---|---|
| `qbacktest/__init__.py` | Public exports and package version. |
| `qbacktest/errors.py` | `BacktestError`, `InvalidCostError`, `InvalidSignalError`, `InvalidSeriesError`. |
| `qbacktest/models.py` | `TradeRecord`, `BacktestResult` and JSON-ready serialization. |
| `qbacktest/costs.py` | `CostModel`, basis-point validation, adverse fill prices, commission. |
| `qbacktest/engine.py` | `run_backtest()` — the deterministic replay loop. |
| `qbacktest/metrics.py` | `total_return`, `exposure_fraction`, `commission_total`, `slippage_total`, `trade_count`. |
| `qbacktest/baselines.py` | `buy_and_hold_signal`, `cash_signal`. |

Tests were added in separate files without changing any existing test:

- `tests/test_qbacktest_engine.py`
- `tests/test_qbacktest_costs.py`
- `tests/test_qbacktest_metrics.py`
- `tests/test_qbacktest_models.py`
- `tests/test_qbacktest_baselines.py`
- `tests/test_qbacktest_scope_imports.py`
- `tests/_qbacktest_helpers.py` (synthetic test data only)

`qbacktest` reuses `qresearch.models.MarketSeries` / `MarketBar` as the input
data model and `qresearch.metrics.maximum_drawdown` for the drawdown
calculation. It does not re-implement either.

## Example usage

```python
from qbacktest import buy_and_hold_signal, run_backtest
from qresearch import MarketBar, MarketSeries

series = MarketSeries((
    MarketBar(timestamp=..., symbol="DEMO", timeframe="1m",
              open=100.0, high=100.0, low=100.0, close=100.0, volume=1000.0),
    # ...
))

result = run_backtest(
    series,
    buy_and_hold_signal(series),
    commission_bps=10.0,   # required keyword argument
    slippage_bps=5.0,     # required keyword argument
)
print(result.to_dict())
```

Both cost arguments are **required keyword arguments without defaults**. A
call that omits them raises `TypeError`; a call that passes a negative, NaN or
infinite value raises `InvalidCostError`.

## Conventions (implemented exactly)

### 1. Signals

- A signal is a sequence of `int`/`bool` positions with **exactly one entry per
  bar**, aligned to the bars of the series.
- Only `0` (flat) and `1` (long) are accepted; `bool` is accepted and mapped to
  `0`/`1`. Any other value, or a sequence whose length differs from the bar
  count, raises `InvalidSignalError`.
- `signal[t]` expresses the **desired position after observing bar `t`'s
  close**.

### 2. Execution — next-bar open, never the signal bar's close

- A change of desired position observed at bar `t` is executed at bar
  `t + 1`'s **open**. A signal is never executed at the close of the bar that
  produced it, and never at the open of the bar that produced it.
- The first bar's signal can therefore only be executed at the second bar's
  open; a run always starts flat for at least one bar.
- A change observed on the **final bar** has no next open. It is counted in
  `unexecuted_signals` and ignored — the position is not changed and no order
  is queued.
- `unexecuted_signals` counts *desired-position changes* that were still
  pending when the data ran out. A final-bar signal that does not change the
  desired position creates no pending order and is not counted.

### 3. Position

- Long (`1`) or flat (`0`) only. No leverage, no shorting, no partial sizing,
  no pyramiding, one symbol per run.
- A buy commits the **full notional** available in cash; a sell liquidates the
  whole position.

### 4. Costs

- `commission_bps` and `slippage_bps` are required keyword arguments, must be
  finite and `>= 0`, and must be strictly below `10_000` bps (100%). A
  commission of 100% or more cannot be funded by the available cash without
  creating a negative (short) position, and a slippage of 100% or more would
  create a non-positive fill price; both are rejected instead of silently
  repaired.
- One basis point is `1 / 10_000`.
- Fill prices (slippage is always adverse):
  - buy: `open * (1 + slippage)`;
  - sell: `open * (1 - slippage)`.
- Commission is charged on the **traded notional of every fill**.

Exact arithmetic of a fill:

```text
BUY  (executed at bar t's open)
  fill_price  = open * (1 + slippage)
  budget      = cash                       # full notional, the strategy is flat
  commission  = budget * commission_bps / 10_000
  units       = (budget - commission) / fill_price
  cash        = cash - budget              # -> 0.0, nothing is borrowed
  slippage    = units * (fill_price - open)

SELL (executed at bar t's open)
  fill_price  = open * (1 - slippage)
  notional    = units * fill_price
  commission  = notional * commission_bps / 10_000
  cash        = cash + notional - commission
  units       = 0
  slippage    = units_before * (open - fill_price)
```

Worked example on the test fixture (`open = 100` at `t1`, `commission_bps = 10`,
`slippage_bps = 0`): `commission = 0.001`, `units = (1.0 - 0.001) / 100 =
0.00999`, and the final equity is `0.00999 * 120 = 1.1988`.

### 5. Equity and final state

- Initial equity is `1.0`.
- Equity is marked to market at **every bar's close**:
  `equity = cash + units * close`.
- The equity curve therefore has exactly one value per bar, in bar order.
- There is **no forced liquidation at the end** of the run. The remaining state
  is reported explicitly through `final_position` (`1` long, `0` flat) and
  `final_units` (`0.0` when flat). An open trade keeps `exit_index`,
  `exit_timestamp`, `exit_price` and `pnl` as `None`.

### 6. Drawdown

- `max_drawdown` is computed on the **equity curve** by
  `qresearch.metrics.maximum_drawdown` and is exposed as the qresearch
  `DrawdownResult` (`max_drawdown`, `peak_index`, `trough_index`, `peak_value`,
  `trough_value`).
- It is a decimal proportion, not a percentage, and it is descriptive, not a
  signal or a recommendation.

### 7. Determinism

- The engine is pure: no randomness, no clock, no global state, no I/O, no
  network, no model calls.
- Identical inputs produce identical outputs; `to_dict()` serialized with
  `json.dumps(..., sort_keys=True)` is byte-identical across runs.

## Metrics

`qbacktest/metrics.py` exposes exactly five metrics:

| Metric | Definition |
|---|---|
| `total_return` | `final_equity / initial_equity - 1` (decimal fraction). |
| `exposure_fraction` | Bars marked with an open position / total bars. |
| `commission_total` | Sum of the commission charged on every fill. |
| `slippage_total` | Sum of the slippage cost paid on every fill. |
| `trade_count` | Number of trades, including a trade that is still open. |

**No Sharpe ratio and no Sortino ratio are implemented.** The annualisation
convention is an open decision and is deliberately deferred to Block 2C; no
annualisation factor is guessed from the timeframe anywhere in this package.

`commission_total` and `slippage_total` are the sums of the per-trade
`commission_paid` / `slippage_paid` fields: every fill belongs to exactly one
trade, so the per-trade and per-run totals always agree.

## Results

`BacktestResult` is a frozen, slotted dataclass with:

- `symbol`, `timeframe`, `bar_count`;
- `first_timestamp`, `last_timestamp`;
- `equity_curve` — a tuple with one float per bar;
- `trades` — a tuple of `TradeRecord`;
- `commission_total`, `slippage_total`, `exposure_fraction`, `trade_count`;
- `unexecuted_signals`;
- `final_position`, `final_units`;
- `max_drawdown` — the qresearch `DrawdownResult`;
- `total_return`;
- `commission_bps`, `slippage_bps` — the validated parameters actually used.

`TradeRecord` is a frozen, slotted dataclass with `entry_index`,
`entry_timestamp`, `entry_price`, `exit_index`, `exit_timestamp`, `exit_price`,
`units`, `commission_paid`, `slippage_paid` and `pnl`.

- `commission_paid` / `slippage_paid` are the costs charged to that trade so
  far: the entry fill for an open trade, entry plus exit fills for a closed
  trade.
- `pnl` is the net profit of a closed trade:
  `units * (exit_fill_price - entry_fill_price) - commission_paid`. Slippage is
  already inside the fill prices and is not subtracted twice. `pnl` is `None`
  for an open trade.

### JSON serialization

`to_dict()` returns JSON-native values only:

- timestamps become UTC ISO-8601 strings (`2024-01-01T00:00:00Z`);
- tuples become lists, the drawdown becomes a plain dictionary;
- **`None` stays `null` and is never replaced by `0` or `0.0`** — an open
  trade's `exit_*` fields and `pnl` remain `null`, while a genuine zero cost
  remains the number `0.0`.

## Baselines

`qbacktest/baselines.py` contains the only two strategies in the package:

- `buy_and_hold_signal(series)` — all ones;
- `cash_signal(series)` — all zeros.

Both return a tuple with one entry per bar and reject anything that is not a
`MarketSeries`.

## Error handling

All package-specific exceptions derive from `BacktestError`:

- `InvalidCostError`: a commission or slippage parameter is not a finite,
  non-negative number below 10 000 bps;
- `InvalidSignalError`: the signal is not a sequence of `0`/`1` positions, or
  its length does not match the bar count;
- `InvalidSeriesError`: the input is not a non-empty `MarketSeries`.

Nothing is silently repaired, clamped, forward-filled or defaulted.

## Data status

**Synthetic data only.** The package contains no market data and reads no
files. The tests use one hand-written four-bar fixture:

```text
bar   open   close
t0    100    100
t1    100    110
t2    110     90
t3     90    120
```

with consistent highs/lows, volume `1000` and consecutive UTC one-minute
timestamps. Every expected number in the tests is hand-computed:

| Case | Hand-computed expectation |
|---|---|
| buy & hold, no costs | equity `(1.0, 1.10, 0.90, 1.20)`, `total_return == 0.20` |
| buy & hold drawdown | peak `1.10` → trough `0.90`, i.e. `2 / 11` |
| cash baseline | equity `(1.0, 1.0, 1.0, 1.0)`, no trades, drawdown `0.0` |
| `commission_bps = 10` | `units == 0.999 / 100 == 0.00999`, final equity `1.1988` |
| `slippage_bps = 10` | buy fill `100 * 1.001 == 100.1` |
| signal `[0, 0, 1, 0]` | entry at `t3` open `90`, equity `(1.0, 1.0, 1.0, 120/90)` |
| signal on the final bar only | `unexecuted_signals == 1`, no trades |

The expected values are written out in the test source; they are not copied
from the implementation output.

## Explicit exclusions

The following are **not** part of Block 2B and are deliberately absent:

- any strategy other than the two baselines;
- optimisation, parameter search, grid search, sweep, walk-forward, sensitivity
  analysis or any fitness function;
- Sharpe, Sortino, Calmar, volatility, alpha/beta, correlation or any other
  risk-adjusted or benchmark-relative metric, and every annualisation
  convention (deferred to Block 2C);
- live or historical market data ingestion, CSV/CSV-API loaders, caching,
  databases or file writing;
- network access, HTTP clients, LLM/Ollama/LFM3 calls, prompt construction;
- multi-asset, multi-timeframe, portfolio, leverage, shorting, partial sizing,
  pyramiding, margin or borrow modelling;
- order types beyond the implicit market-on-next-open fill, limit/stop
  orders, partial fills, volume constraints, liquidity or market-impact
  models;
- corporate-action adjustment, dividends, funding, tax or fee schedules
  beyond the flat commission rate;
- intrabar (high/low) path simulation: equity is marked at closes only;
- integration with the Block 1 orchestrator, schemas, verifier, agent or
  logging.

## Environment and verification

Environment used:

- Python 3.12.8
- `uv 0.12.7`
- no dependency added, removed or upgraded

Verification commands and results:

```text
.venv\Scripts\python.exe -m pytest -q -m "not live" -o addopts=""
    349 passed, 1 deselected in 9.66s
    (267 existing tests + 82 new tests, 0 failed)

uv pip check
    Checked 26 packages
    All installed packages are compatible

uv pip freeze
    unchanged (26 packages, identical before and after this block)

git status --porcelain -- mdl qresearch
    empty
```

New test breakdown:

| Test file | Tests |
|---|---:|
| `tests/test_qbacktest_engine.py` | 41 |
| `tests/test_qbacktest_costs.py` | 20 |
| `tests/test_qbacktest_metrics.py` | 8 |
| `tests/test_qbacktest_models.py` | 7 |
| `tests/test_qbacktest_baselines.py` | 4 |
| `tests/test_qbacktest_scope_imports.py` | 2 |
| **Total new** | **82** |

The scope guard mirrors the qresearch guard: the `qbacktest` modules are
parsed with `ast` only (never imported by the guard), the file list must be
non-empty, every file must have content, and the forbidden import roots are
identical to the qresearch set (`mdl`, `ollama`, `openai`, `anthropic`,
`httpx`, `requests`, `urllib`, `socket`, `http`, `torch`, `tensorflow`,
`keras`, `sklearn`, `pandas`, `transformers`, `peft`, `trl`, `bitsandbytes`).

## Known limitations and open decisions

- The engine assumes bars arrive in chronological order with no missing
  values; `MarketSeries` already guarantees uniqueness and ordering, but no
  gap or session diagnostics are produced here.
- Equity is marked at closes only, so intrabar drawdowns are invisible.
- `exposure_fraction` is a bar count, not a time-weighted exposure; irregular
  bar spacing is not normalised.
- `trade_count` counts round trips that were started, including one that is
  still open.
- `unexecuted_signals` reports pending orders only; it is not a count of
  ignored signal values.
- The 10 000 bps ceiling on the cost parameters is a structural guard, not a
  market convention.
- Annualisation, risk-adjusted metrics and benchmark-relative statistics are
  open decisions for Block 2C.

## Block 1 and Block 2A integrity

- No file under `mdl/` or `qresearch/` was modified.
- No existing test was modified; the Block 1 baseline of 267 passing tests is
  unchanged.
- No LFM3 or Ollama call was made.
- No dependency was installed or removed.
- No user market-data file was created, changed or deleted.
