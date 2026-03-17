from typing import Literal
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class HealthCheckResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    status: str = "healthy"
    service_name: str = "quant-api"
    version: str = "0.1.0"


# ---------------------------------------------------------------------------
# Story 2.2 — Historical Prices (adjusted, for backtesting)
# ---------------------------------------------------------------------------


class TickerSeries(BaseModel):
    """Parallel date and adjusted-close arrays for a single ticker."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    dates: list[str]
    # String representation of Decimal to avoid floating-point rounding at the boundary.
    adjusted_close: list[str]  # serialised as "adjustedClose"


class HistoricalPriceRequest(BaseModel):
    """POST body for /api/v1/portfolio-builder/historical-prices."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    tickers: list[str]
    period: Literal["1Y", "3Y", "5Y"]


class HistoricalPriceResponse(BaseModel):
    """
    Response for /api/v1/portfolio-builder/historical-prices.

    price_matrix  → serialised as "priceMatrix"
    benchmark_*   → serialised as "benchmarkDates" / "benchmarkClose"

    VNINDEX is always excluded from price_matrix and placed in
    benchmark_dates / benchmark_close instead.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    price_matrix: dict[str, TickerSeries]
    benchmark_dates: list[str]
    benchmark_close: list[str]
    warnings: list[str]


# ---------------------------------------------------------------------------
# Story 2.3 — Quantitative Math Engine (Backtest)
# ---------------------------------------------------------------------------


class EqCurve(BaseModel):
    """Equity curve: parallel date and value arrays indexed to 100 at start."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    dates: list[str]
    values: list[str]


class RiskMetrics(BaseModel):
    """Risk metrics as stringified floats (4 decimal places)."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    annualized_return: str
    max_drawdown: str
    sharpe_ratio: str


class BacktestRequest(BaseModel):
    """POST body for /api/v1/portfolio-builder/backtest."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    price_matrix: dict[str, TickerSeries]
    benchmark_dates: list[str]
    benchmark_close: list[str]
    weighting_mode: Literal["equal", "conviction", "market_cap"]
    conviction_scores: dict[str, str] | None = None
    market_cap_scores: dict[str, str] | None = None


class BacktestResponse(BaseModel):
    """Response for /api/v1/portfolio-builder/backtest."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    portfolio_curve: EqCurve
    benchmark_curve: EqCurve
    metrics: RiskMetrics
    benchmark_metrics: RiskMetrics
    asset_weights: dict[str, str]
    warnings: list[str] = []
