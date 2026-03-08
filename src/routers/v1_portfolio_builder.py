import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from src.data.clickhouse_client import (
    fetch_adjusted_prices,
    get_clickhouse_client,
    period_to_dates,
)
from src.models.pydantic_schemas import (
    BacktestRequest,
    BacktestResponse,
    HealthCheckResponse,
    HistoricalPriceRequest,
    HistoricalPriceResponse,
    TickerSeries,
)
from src.quantitative.backtest_math import run_backtest
from src.utils.audit_logger import log_backtest_audit

logger = logging.getLogger(__name__)
router = APIRouter()

_BENCHMARK_TICKER = "VNINDEX"


@router.get("/health", response_model=HealthCheckResponse)
def health_check():
    return HealthCheckResponse()


@router.post(
    "/historical-prices",
    response_model=HistoricalPriceResponse,
    summary="Adjusted historical prices for backtesting",
    description=(
        "Returns backward-adjusted closing prices for the requested tickers over the "
        "given period.  VNINDEX is always included as the benchmark and is separated "
        "from the price_matrix in the response."
    ),
)
def get_historical_prices(
    body: HistoricalPriceRequest,
    client=Depends(get_clickhouse_client),
) -> HistoricalPriceResponse:
    """
    POST /api/v1/portfolio-builder/historical-prices

    Fetches adjusted_ohlcv data from ClickHouse and structures it for
    the backtesting UI.  VNINDEX is always queried as the benchmark.
    """
    start_date, end_date = period_to_dates(body.period)

    # Always fetch VNINDEX alongside the requested tickers
    tickers_to_query = list({_BENCHMARK_TICKER} | set(body.tickers))

    try:
        raw = fetch_adjusted_prices(tickers_to_query, start_date, end_date, client)
    except Exception as exc:
        logger.error(
            "ClickHouse unavailable while fetching historical prices "
            "(tickers=%s, period=%s): %s",
            body.tickers,
            body.period,
            exc,
        )
        raise HTTPException(
            status_code=503,
            detail="Data warehouse unavailable",
        ) from exc

    # --- Split benchmark from price_matrix ---
    benchmark_data = raw.get(_BENCHMARK_TICKER, {"dates": [], "adjusted_close": []})
    benchmark_dates: list[str] = benchmark_data["dates"]
    benchmark_close: list[str] = benchmark_data["adjusted_close"]

    price_matrix: dict[str, TickerSeries] = {}
    warnings: list[str] = []

    for ticker in body.tickers:
        if ticker == _BENCHMARK_TICKER:
            # Caller shouldn't request VNINDEX explicitly, but handle gracefully
            continue
        if ticker not in raw or not raw[ticker]["dates"]:
            warnings.append(f"No adjusted price data found for ticker '{ticker}'")
            continue
        td = raw[ticker]
        price_matrix[ticker] = TickerSeries(
            dates=td["dates"],
            adjusted_close=td["adjusted_close"],
        )

    if not benchmark_dates:
        warnings.append(f"No benchmark data found for '{_BENCHMARK_TICKER}'")

    return HistoricalPriceResponse(
        price_matrix=price_matrix,
        benchmark_dates=benchmark_dates,
        benchmark_close=benchmark_close,
        warnings=warnings,
    )


@router.post(
    "/backtest",
    response_model=BacktestResponse,
    summary="Run quantitative backtest on portfolio builder portfolio",
    description=(
        "Calculates equity curves and risk metrics (Sharpe Ratio, Max Drawdown, "
        "Annualized Return) for a set of tickers against the VN-Index benchmark. "
        "Accepts pre-fetched adjusted price data."
    ),
)
def post_backtest(body: BacktestRequest, request: Request) -> BacktestResponse:
    """
    POST /api/v1/portfolio-builder/backtest

    Pure computation — no external data fetching. Accepts the output of
    /historical-prices as input and returns equity curves + risk metrics.
    """
    # Validate that priceMatrix is non-empty after potential filtering
    if not body.price_matrix:
        raise HTTPException(
            status_code=422,
            detail="priceMatrix must contain at least one ticker",
        )

    try:
        result = run_backtest(body)
    except ValueError as exc:
        logger.warning("Backtest validation error: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Backtest computation failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Backtest computation failed",
        ) from exc

    # Story 4.2 — Fire-and-forget audit log (non-blocking)
    user_id = request.headers.get("x-audit-user-id")
    session_id = request.headers.get("x-audit-session-id") or "unknown"
    thread_id = request.headers.get("x-audit-thread-id")
    forwarded_for_header = request.headers.get("x-forwarded-for", "")
    first_forwarded_ip = forwarded_for_header.split(",")[0].strip() if forwarded_for_header else ""
    if first_forwarded_ip:
        ip_address = first_forwarded_ip
    elif request.client:
        ip_address = request.client.host
    else:
        ip_address = None

    if user_id:
        tickers = list(body.price_matrix.keys()) if body.price_matrix else []
        log_backtest_audit(
            user_id=user_id,
            session_id=session_id,
            thread_id=thread_id,
            request_payload={
                "tickers": tickers,
                "weightingMode": body.weighting_mode,
            },
            response_payload=result.model_dump(),
            response_timestamp=None,
            ip_address=ip_address,
        )

    return result
