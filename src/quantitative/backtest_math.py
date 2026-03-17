"""
quant-api/src/quantitative/backtest_math.py

Core quantitative functions for backtesting: alignment, weighting,
portfolio return calculation, equity curves, and risk metrics.
"""

import numpy as np
import pandas as pd
from decimal import Decimal
from typing import Optional

from src.models.pydantic_schemas import (
    BacktestRequest,
    BacktestResponse,
    EqCurve,
    RiskMetrics,
)

TRADING_DAYS_PER_YEAR = 252  # VN Stock Exchange standard


def align_series(
    price_matrix: dict[str, dict],  # {ticker: {"dates": [...], "adjustedClose": [...]}}
    benchmark_dates: list[str],
    benchmark_close: list[str],
) -> tuple[pd.DataFrame, pd.Series]:
    """
    Align all ticker price series and the benchmark to a common date range.
    Returns: (ticker_prices_df, benchmark_series) — both indexed by date, prices as float.
    """
    frames = {}
    for ticker, series in price_matrix.items():
        df = pd.DataFrame(
            {
                "date": pd.to_datetime(series["dates"]),
                ticker: [float(v) for v in series["adjustedClose"]],
            }
        ).set_index("date")
        frames[ticker] = df[ticker]

    benchmark_df = pd.DataFrame(
        {
            "date": pd.to_datetime(benchmark_dates),
            "VNINDEX": [float(v) for v in benchmark_close],
        }
    ).set_index("date")["VNINDEX"]

    combined = pd.concat(frames.values(), axis=1).dropna()
    common_dates = combined.index.intersection(benchmark_df.index)
    return combined.loc[common_dates], benchmark_df.loc[common_dates]


def calculate_weights(
    tickers: list[str],
    mode: str,
    conviction_scores: Optional[dict[str, str]] = None,
    market_cap_scores: Optional[dict[str, str]] = None,
) -> tuple[dict[str, float], list[str]]:
    """
    Compute portfolio weights for the given mode.

    Returns: (weights_dict, warnings_list)

    - "equal": all tickers receive equal weight.
    - "conviction": normalized conviction_scores; falls back to equal if scores
      are absent or all zero/invalid.
    - "market_cap": normalized market_cap_scores; same fallback rules as
      conviction mode.
    - Missing or invalid score values for a ticker are treated as 0.0.
    - If the total score across all tickers is non-positive, the function falls
      back to equal-weight allocation and emits a warning.
    """
    n = len(tickers)
    warnings: list[str] = []

    if mode == "equal":
        return {t: 1.0 / n for t in tickers}, warnings

    scores: Optional[dict[str, str]] = None
    if mode == "conviction":
        scores = conviction_scores
    elif mode == "market_cap":
        scores = market_cap_scores

    if not scores:
        warnings.append(
            f"Missing {mode} scores, falling back to equal-weight allocation"
        )
        return {t: 1.0 / n for t in tickers}, warnings

    raw: dict[str, float] = {}
    missing_tickers = []
    for t in tickers:
        try:
            raw[t] = float(Decimal(scores.get(t, "0")))
            if t not in scores:
                missing_tickers.append(t)
        except Exception:
            raw[t] = 0.0
            missing_tickers.append(t)

    if missing_tickers:
        warnings.append(
            f"Missing or invalid {mode} data for {len(missing_tickers)} ticker(s): {', '.join(missing_tickers[:3])}{'...' if len(missing_tickers) > 3 else ''}"
        )

    total = sum(raw.values())
    if total <= 0:
        warnings.append(
            f"All {mode} scores are zero or invalid, falling back to equal-weight allocation"
        )
        return {t: 1.0 / n for t in tickers}, warnings

    return {t: raw[t] / total for t in tickers}, warnings


def calculate_portfolio_returns(
    prices_df: pd.DataFrame,  # columns = tickers, rows = dates
    weights: dict[str, float],
) -> pd.Series:
    """
    Equal or conviction-weighted daily arithmetic returns.
    Uses pct_change() — safe for aligned daily prices.
    """
    returns_df = prices_df.pct_change().dropna()  # drops first row (NaN)

    weight_series = pd.Series({t: weights.get(t, 0.0) for t in prices_df.columns})
    weight_series = weight_series / weight_series.sum()  # re-normalize safety

    portfolio_returns = returns_df.mul(weight_series).sum(axis=1)
    return portfolio_returns


def calculate_equity_curve(returns: pd.Series, base: float = 100.0) -> pd.Series:
    """Cumulative product of (1 + daily_return), indexed to base at start."""
    return (1 + returns).cumprod() * base


def calculate_metrics(returns: pd.Series, rf: float = 0.0) -> dict[str, str]:
    """
    returns: daily arithmetic returns Series.
    rf: annual risk-free rate (0.0 for PoC).

    Returns dict with stringified floats to 4 decimal places.
    """
    n = len(returns)
    if n < 2:
        return {
            "annualizedReturn": "0.0000",
            "maxDrawdown": "0.0000",
            "sharpeRatio": "0.0000",
        }

    # Annualized Return
    cumulative = (1 + returns).prod()
    years = n / TRADING_DAYS_PER_YEAR
    annualized_return = cumulative ** (1.0 / years) - 1.0

    # Max Drawdown
    equity = (1 + returns).cumprod()
    rolling_max = equity.cummax()
    drawdowns = (equity - rolling_max) / rolling_max
    max_drawdown = float(drawdowns.min())  # negative value

    # Sharpe Ratio (daily rf = 0.0 for PoC)
    daily_rf = (1 + rf) ** (1 / TRADING_DAYS_PER_YEAR) - 1
    excess_returns = returns - daily_rf
    std = excess_returns.std()
    sharpe = (
        (excess_returns.mean() / std) * np.sqrt(TRADING_DAYS_PER_YEAR)
        if std > 1e-10
        else 0.0
    )

    return {
        "annualizedReturn": f"{annualized_return:.4f}",
        "maxDrawdown": f"{max_drawdown:.4f}",
        "sharpeRatio": f"{sharpe:.4f}",
    }


def run_backtest(request: BacktestRequest) -> BacktestResponse:
    """
    Orchestrates: align → weight → returns → equity curve → metrics.
    Returns BacktestResponse (Pydantic model).
    """
    tickers = list(request.price_matrix.keys())
    # request.price_matrix values are existing TickerSeries models (from Story 2.2)
    # Access via .dates and .adjusted_close attributes, not dict keys
    price_dict = {
        t: {"dates": s.dates, "adjustedClose": s.adjusted_close}
        for t, s in request.price_matrix.items()
    }

    aligned_prices, benchmark_series = align_series(
        price_dict, request.benchmark_dates, request.benchmark_close
    )

    weights, warnings = calculate_weights(
        tickers,
        request.weighting_mode,
        request.conviction_scores,
        request.market_cap_scores,
    )

    # Precision guard: weight sum must equal 1.0 within ±0.0001 (AC #3).
    # The 0.0001 tolerance accounts for floating-point rounding in the
    # normalization step while remaining tight enough for financial accuracy.
    weight_sum = sum(weights.values())
    if abs(weight_sum - 1.0) > 0.0001:
        raise ValueError(
            f"Weight sum {weight_sum:.6f} deviates from 1.0 beyond ±0.0001 tolerance"
        )

    # Stringify weights to 3 decimal places for decimal.js-safe transport (AC #2).
    # Use largest-remainder method so the stringified weights always sum to exactly
    # "1.000" even after rounding each value independently.
    # Work in integer milli-units (thousandths) to avoid floating-point arithmetic.
    milli = {t: int(w * 1000) for t, w in weights.items()}
    remainders = {t: (w * 1000) - milli[t] for t, w in weights.items()}
    remainder_units = 1000 - sum(milli.values())
    # Give one extra milli-unit to the tickers with the largest fractional part
    # until the deficit is fully distributed.
    sorted_by_remainder = sorted(remainders, key=lambda t: remainders[t], reverse=True)
    adjusted: dict[str, int] = dict(milli)
    for i in range(min(remainder_units, len(sorted_by_remainder))):
        adjusted[sorted_by_remainder[i]] += 1
    asset_weights = {t: f"{v / 1000:.3f}" for t, v in adjusted.items()}

    portfolio_returns = calculate_portfolio_returns(aligned_prices, weights)
    bench_returns = benchmark_series.pct_change().dropna()
    # Reindex + dropna: benchmark may have a different first date after pct_change
    bench_returns = bench_returns.reindex(portfolio_returns.index).dropna()

    port_curve = calculate_equity_curve(portfolio_returns)
    bench_curve = calculate_equity_curve(bench_returns)

    port_metrics = calculate_metrics(portfolio_returns)
    bench_metrics = calculate_metrics(bench_returns)

    dates_str = [d.strftime("%Y-%m-%d") for d in port_curve.index]

    return BacktestResponse(
        portfolio_curve=EqCurve(
            dates=dates_str,
            values=[f"{v:.4f}" for v in port_curve.values],
        ),
        benchmark_curve=EqCurve(
            dates=dates_str,
            values=[
                f"{v:.4f}" for v in bench_curve.reindex(port_curve.index).ffill().values
            ],
        ),
        metrics=RiskMetrics(**port_metrics),
        benchmark_metrics=RiskMetrics(**bench_metrics),
        asset_weights=asset_weights,
        warnings=warnings,
    )
