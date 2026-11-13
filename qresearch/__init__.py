"""Deterministic quantitative-research foundation.

``qresearch`` is deliberately independent of the Block 1 ``mdl`` package.  It
provides strict market-data validation, a sandboxed CSV importer, pure
return/indicator/drawdown functions and a serializable analysis result.

It does not call LFM3, generate signals, backtest strategies or execute orders.
"""

from __future__ import annotations

__version__ = "0.1.0"

from qresearch.analysis import (
    CANONICAL_FORMAT,
    CANONICAL_HASH_SOURCE,
    CSV_HASH_SOURCE,
    analyze_csv,
    analyze_series,
    canonical_series_bytes,
    canonical_series_payload,
    canonical_series_sha256,
)
from qresearch.csv_loader import (
    ENCODING,
    MARKET_DATA_DIR,
    MAX_FILE_BYTES,
    MAX_RECORDS,
    REQUIRED_COLUMNS,
    CSVLoadResult,
    load_market_csv,
)
from qresearch.errors import (
    CalculationError,
    CSVValidationError,
    MarketDataError,
    PathSecurityError,
    QResearchError,
)
from qresearch.indicators import (
    rolling_volatility,
    rolling_volatility_from_log_returns,
    simple_moving_average,
)
from qresearch.metrics import (
    DrawdownResult,
    max_drawdown,
    maximum_drawdown,
)
from qresearch.models import (
    AnalysisResult,
    DrawdownObservation,
    MarketBar,
    MarketSeries,
    MovingAverageResult,
    RollingVolatilityResult,
    ValidationSummary,
)
from qresearch.returns import (
    log_return,
    log_returns,
    simple_return,
    simple_returns,
)
from qresearch.validation import (
    ensure_finite_number,
    ensure_nonnegative_finite,
    ensure_positive_finite,
    normalize_timestamp,
    validate_ohlcv,
)

__all__ = [
    "AnalysisResult",
    "CANONICAL_FORMAT",
    "CANONICAL_HASH_SOURCE",
    "CSVLoadResult",
    "CSVValidationError",
    "CSV_HASH_SOURCE",
    "CalculationError",
    "DrawdownObservation",
    "DrawdownResult",
    "ENCODING",
    "MARKET_DATA_DIR",
    "MAX_FILE_BYTES",
    "MAX_RECORDS",
    "MarketBar",
    "MarketDataError",
    "MarketSeries",
    "MovingAverageResult",
    "PathSecurityError",
    "QResearchError",
    "REQUIRED_COLUMNS",
    "RollingVolatilityResult",
    "ValidationSummary",
    "__version__",
    "analyze_csv",
    "analyze_series",
    "canonical_series_bytes",
    "canonical_series_payload",
    "canonical_series_sha256",
    "ensure_finite_number",
    "ensure_nonnegative_finite",
    "ensure_positive_finite",
    "load_market_csv",
    "log_return",
    "log_returns",
    "max_drawdown",
    "maximum_drawdown",
    "normalize_timestamp",
    "rolling_volatility",
    "rolling_volatility_from_log_returns",
    "simple_moving_average",
    "simple_return",
    "simple_returns",
    "validate_ohlcv",
]
