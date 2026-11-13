# Block 2A — Quantitative Research Foundation

Block 2A adds a small, deterministic market-data and statistical-analysis
foundation in the independent package `qresearch/`. It is infrastructure, not a
trading strategy.

Scope boundaries:

- no strategies, backtests, execution, brokers, portfolios or risk management;
- no live or downloaded market data;
- no model training and no LFM3 calls;
- no integration with the Block 1 orchestrator, schemas, verifier, agent or
  logging;
- no third-party runtime dependency; `qresearch` uses the Python standard
  library only.

The package is designed so that a later block can consume its structured
`AnalysisResult` without reusing any of the Block 1 research machinery.

## Package layout

| File | Responsibility |
|---|---|
| `qresearch/__init__.py` | Public exports and package version. |
| `qresearch/errors.py` | `QResearchError`, `MarketDataError`, `CSVValidationError`, `PathSecurityError`, `CalculationError`. |
| `qresearch/validation.py` | Timestamp normalization and strict scalar/OHLCV checks. |
| `qresearch/models.py` | `MarketBar`, `MarketSeries`, `ValidationSummary`, result records and JSON-ready serialization. |
| `qresearch/returns.py` | Simple and logarithmic returns. |
| `qresearch/indicators.py` | Simple moving average and rolling volatility. |
| `qresearch/metrics.py` | Maximum drawdown. |
| `qresearch/csv_loader.py` | Sandboxed, read-only CSV importer and raw-file hashing. |
| `qresearch/analysis.py` | Canonical series hashing plus `analyze_series()` and `analyze_csv()`. |

Tests were added in separate files without changing the existing Block 1 tests:

- `tests/test_qresearch_models.py`
- `tests/test_qresearch_calculations.py`
- `tests/test_qresearch_csv_loader.py`
- `tests/test_qresearch_analysis.py`
- `tests/_qresearch_helpers.py` (synthetic test data only)

## Separation from Block 1 and LFM3

`qresearch` does not import `mdl` and does not call Ollama or LFM3. Nothing in
`mdl/`, the Tool Orchestrator, Block 1 schemas, the verifier, the agent, Block 1
logging or existing tests was modified. Integration with LFM3 is deliberately
left to a later, separately reviewed block.

## Market-data model

One `MarketBar` contains:

```text
timestamp, symbol, timeframe, open, high, low, close, volume
```

Validation rules:

- `timestamp` must be timezone-aware, either a `datetime` or an ISO-8601 string.
  It is normalized to UTC immediately. Naive timestamps are rejected.
- `symbol` and `timeframe` must be non-empty strings without leading or trailing
  whitespace.
- open, high, low and close must be finite and strictly positive.
- volume must be finite and non-negative.
- `high >= open`, `high >= close`, `high >= low`, `low <= open`, `low <= close`.
- Booleans, NaN and infinities are rejected as numbers.

A `MarketSeries` is non-empty and contains one consistent symbol and timeframe.
Timestamps must be unique and strictly increasing. Out-of-order rows are
rejected, not sorted. Duplicate rows are rejected, not deduplicated. Missing time
intervals are allowed and are never filled or interpolated: markets legitimately
have overnight, weekend and session gaps.

The model is immutable (`frozen=True`, `slots=True`). Invalid data cannot be
represented as a valid `MarketBar` or `MarketSeries`.

## CSV format

Required columns, in any order:

```text
timestamp,symbol,timeframe,open,high,low,close,volume
```

The header must contain exactly this set. Duplicate headers, missing columns,
extra columns, empty values, surrounding whitespace and malformed quoting are
rejected. Files must be valid UTF-8; a UTF-8 BOM is accepted. Blank lines are
rejected. Rows are validated in file order and the order is preserved.

Example:

```csv
timestamp,symbol,timeframe,open,high,low,close,volume
2024-01-01T00:00:00Z,DEMO,1h,100.0,102.0,98.0,101.0,1000
2024-01-01T01:00:00Z,DEMO,1h,101.0,103.0,100.0,102.5,1200
```

### Path sandbox

`load_market_csv(relative_path)` accepts a path relative to
`data/market_samples/` only. The implementation:

1. rejects empty, absolute, drive-qualified and `..`-containing paths;
2. resolves the market-data root and the candidate path before opening;
3. verifies that the resolved candidate is inside the resolved root;
4. rejects directories and the root itself.

Files outside the sandbox are never opened. No files are written, downloaded or
modified. The loader does not create the market-data root; create
`data/market_samples/` yourself and place input files there. Paths still may not
escape that directory.

### Limits

- Maximum file size: `10 * 1024 * 1024` bytes (10 MB).
- Maximum records: `100_000`.
- The file is read into memory once, so the size limit also bounds memory use.

Errors include the relative source path and, for row problems, the CSV line
number.

### Content hash

`load_market_csv()` computes SHA-256 over the raw file bytes. This ties an
analysis to the exact input file, including formatting and header order.
`CSVLoadResult` reports:

- `content_sha256`
- `row_count`
- `symbol`
- `timeframe`
- `first_timestamp` and `last_timestamp`
- `source_path`
- `file_size_bytes`

## Deterministic calculations

### Returns

For prices `p`:

- simple return: `(p[t] / p[t-1]) - 1`
- log return: `ln(p[t] / p[t-1])`

The first observation has no predecessor and is represented by `None`, never by
a fabricated `0.0`. Empty input produces an empty tuple; a single observation
produces `(None,)`. Zero, negative, NaN and infinite prices are rejected.

### Simple moving average

`simple_moving_average(values, window)` uses a positive integer window and a
complete window only. The first `window - 1` positions are `None`. If the window
is larger than the input, every position is `None`. Partial averages are not
produced.

### Rolling volatility

`rolling_volatility(prices, window, ddof=1, annualization_factor=None)`:

- calculates log returns first, so the first `window` positions are `None`;
- calculates the sample standard deviation by default (`ddof=1`);
- supports explicit `ddof=0` for population standard deviation;
- rejects `ddof < 0` and `ddof >= window`;
- returns values on the same scale as the input returns;
- does **not** annualize unless the caller explicitly supplies a positive
  `annualization_factor`, in which case the result is multiplied by
  `sqrt(annualization_factor)`.

The annualization factor is not inferred from the timeframe. For example,
`252.0` is appropriate only if the caller has decided that the observations are
daily trading sessions.

### Maximum drawdown

`maximum_drawdown(prices)` uses close prices and returns:

- `max_drawdown`: a non-negative decimal proportion (`0.1` means 10%);
- peak and trough indices;
- peak and trough prices.

Edge cases:

- an empty series is invalid;
- a single observation, or a series with no decline, returns `0.0` with indices
  `0` and `0`;
- when several equal highs occur, the earliest peak is kept;
- when several troughs produce the same maximum decline, the first trough is
  kept.

`AnalysisResult.max_drawdown` additionally contains the peak and trough
timestamps. Drawdown is descriptive, not a signal or recommendation.

## Analysis result

`analyze_series()` and `analyze_csv()` return an immutable `AnalysisResult` with:

- symbol, timeframe and observation count;
- first and last timestamp;
- content SHA-256 and its source label;
- simple returns and log returns aligned to the observations;
- requested moving averages;
- requested rolling volatilities;
- maximum drawdown with peak/trough observations;
- validation metadata.

`to_dict()` is JSON-ready. Missing or insufficient values remain `null`/`None`
and are distinguishable from genuine numerical `0.0` values. The result contains
no predictions, recommendations, signals, scores or prices projected into the
future.

### Two hash sources

| Source label | Meaning |
|---|---|
| `canonical-series-sha256` | SHA-256 of the canonical in-memory series representation. |
| `csv-file-sha256` | SHA-256 of the raw CSV file bytes. |

The canonical representation is compact, key-sorted, UTF-8 JSON with a format
version (`qresearch.market-series.v1`). Timestamps are UTC ISO-8601 strings.
Equivalent series built from differently formatted CSV headers have the same
canonical series hash even though their raw-file hashes differ.

## Example usage

CSV input from `data/market_samples/`:

```python
from qresearch import analyze_csv

result = analyze_csv(
    "demo_1h.csv",
    moving_average_windows=(20,),
    volatility_windows=(20,),
    annualization_factor=252.0,
)
print(result.to_dict())
```

In-memory synthetic input:

```python
from datetime import datetime, timedelta, timezone

from qresearch import MarketBar, MarketSeries, analyze_series

start = datetime(2024, 1, 1, tzinfo=timezone.utc)
closes = [100.0, 101.0, 99.0, 102.0]
bars = tuple(
    MarketBar(
        timestamp=start + timedelta(hours=index),
        symbol="DEMO",
        timeframe="1h",
        open=close,
        high=close * 1.01,
        low=close * 0.99,
        close=close,
        volume=1000.0,
    )
    for index, close in enumerate(closes)
)
result = analyze_series(
    MarketSeries(bars),
    moving_average_windows=(2,),
    volatility_windows=(2,),
)
```

The package intentionally has no CSV-writing API and no network API.

## Error handling

All package-specific exceptions derive from `QResearchError`:

- `MarketDataError`: an observation or series violates the market-data contract;
- `CSVValidationError`: a CSV file, header or row is invalid;
- `PathSecurityError`: a path would escape the sandbox;
- `CalculationError`: a calculation request or argument is invalid.

Errors name the offending field, row or path where applicable. There are no
silent repairs, clamps, zero-fills, back-fills or fallback values.

## Environment and verification

Environment used:

- Python 3.12.8
- NumPy 2.4.3 available in the environment, but not imported by `qresearch`
- `uv 0.12.7`
- no dependency added or removed

Verification commands and results:

```text
python -m compileall -q qresearch
    OK

uv pip check
    Checked 26 packages
    All installed packages are compatible

python -m pytest
    266 passed, 1 deselected
```

The existing Block 1 baseline was `57 passed, 1 deselected`. Block 2A adds 209
tests:

| Test file | Tests |
|---|---:|
| `tests/test_qresearch_models.py` | 65 |
| `tests/test_qresearch_calculations.py` | 60 |
| `tests/test_qresearch_csv_loader.py` | 45 |
| `tests/test_qresearch_analysis.py` | 39 |
| **Total new** | **209** |

Tests use synthetic data and temporary directories. They monkeypatch
`qresearch.csv_loader.MARKET_DATA_DIR`; no real or user market-data file is read
or written. Expected numerical values are hand-calculated rather than copied
from the implementation.

## Known limitations

- CSV only, UTF-8 only, one symbol/timeframe per file; no merging of files.
- No adjustment for splits, dividends or other corporate actions; closes are
  used exactly as supplied.
- No live data, downloads, caching, database or file-writing API.
- No inference of timeframe regularity. Gaps are allowed by design; interval
  diagnostics are not part of this block.
- No missing-value imputation. Invalid or missing values are rejected.
- The loader does not create `data/market_samples/`; the directory must already
  exist.
- The whole CSV file is read into memory, bounded by the 10 MB limit.
- The canonical hash is versioned and currently based on Python's deterministic
  JSON/float serialization. Any format change must use a new format version.
- Annualization is caller-defined; the package never guesses a trading calendar.
- Drawdown is based on close prices only and does not model intraday excursions.
- This block produces descriptive statistics only. It makes no predictions and
  has no strategy, execution or risk-management capability.

## Block 2B suggestions (not implemented)

1. Define a read-only LFM3 integration contract around `AnalysisResult.to_dict()`
   with a versioned JSON schema and no free-form generated code.
2. Add deterministic interval/gap diagnostics (counts and distributions) without
   filling or repairing anything.
3. Add golden-file tests for canonical hashes and an independent NumPy-based
   cross-check of the numerical functions.
4. Add multi-file dataset manifests with explicit symbol/timeframe selection
   while preserving the existing path sandbox.
5. Decide separately whether adjusted-price handling belongs in a later block;
   it must not silently alter supplied observations.

## Block 1 integrity

- No file under `mdl/` was modified.
- No existing Block 1 test was modified.
- The Tool Orchestrator, Block 1 schemas, verifier, agent, logging and
  configuration were untouched.
- No LFM3 or Ollama call was made by Block 2A.
- No dependency was installed or removed.
- No user market-data file was created, changed or deleted.
- No Git commit or push was performed.
