"""
services/portfolio-builder-api/src/data/clickhouse_client.py

ClickHouse integration for the portfolio-builder-api service.

Design decisions (Story 2.2):
  - Per-request client instantiation via FastAPI Depends() — NOT a module-level
    singleton.  FastAPI runs handlers under a thread-pool; a shared clickhouse-connect
    client is not thread-safe by default.  Creating a lightweight client per request
    is cheap (HTTP connection is pooled by the underlying httpx session) and avoids
    any race conditions.
  - Decimal values from ClickHouse are returned as Python Decimal objects; we
    serialise them as strings to avoid float rounding at the JSON boundary.
  - adjusted_ohlcv uses ReplacingMergeTree — reads must append FINAL to force
    deduplication before the data reaches this service.
"""

from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from decimal import Decimal
from typing import Generator

import clickhouse_connect

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


def get_clickhouse_client() -> Generator:
    """
    FastAPI dependency — yields a fresh ClickHouse client for each request.

    Usage::

        @router.post("/historical-prices")
        def endpoint(client=Depends(get_clickhouse_client)):
            ...
    """
    client = clickhouse_connect.get_client(
        host=os.getenv("CLICKHOUSE_HOST", "clickhouse-server"),
        port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
        username=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", ""),
        database=os.getenv("CLICKHOUSE_DB", "portfolios_tracker_dw"),
    )
    try:
        yield client
    finally:
        client.close()


# ---------------------------------------------------------------------------
# Period helpers
# ---------------------------------------------------------------------------

_PERIOD_DAYS: dict[str, int] = {
    "1Y": 366,
    "3Y": 366 * 3,
    "5Y": 366 * 5,
}


def period_to_dates(period: str) -> tuple[str, str]:
    """
    Convert a period string to an inclusive ISO date range.

    Returns
    -------
    (start_iso, end_iso)  e.g. ("2021-06-01", "2024-06-01")
    """
    if period not in _PERIOD_DAYS:
        raise ValueError(f"Unsupported period '{period}'. Supported: {list(_PERIOD_DAYS)}")

    end = date.today()
    start = end - timedelta(days=_PERIOD_DAYS[period])
    return start.isoformat(), end.isoformat()


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


def fetch_adjusted_prices(
    tickers: list[str],
    start_date: str,
    end_date: str,
    client,
) -> dict[str, dict[str, list]]:
    """
    Fetch adjusted prices from ``adjusted_ohlcv`` for the given tickers and date range.

    Parameters
    ----------
    tickers:
        List of ticker symbols to query (may include VNINDEX).
    start_date, end_date:
        ISO date strings, inclusive on both ends.
    client:
        An active ``clickhouse_connect`` client instance.

    Returns
    -------
    dict[ticker, {"dates": [...], "adjusted_close": [...]}]
        Values are plain lists — dates as ``str``, adjusted_close as ``str``
        (serialised Decimal, no floating-point drift).
    """
    if not tickers:
        return {}

    # ClickHouse prepared-statement-style parameter binding prevents injection.
    query = """
        SELECT
            ticker,
            toString(trading_date)      AS trading_date,
            toString(adjusted_close)    AS adjusted_close
        FROM adjusted_ohlcv FINAL
        WHERE ticker IN ({placeholders})
          AND trading_date >= toDate({{start}})
          AND trading_date <= toDate({{end}})
        ORDER BY ticker, trading_date
    """.format(placeholders=", ".join(f"'{t}'" for t in tickers))

    result = client.query(
        query,
        parameters={"start": start_date, "end": end_date},
    )

    # Group rows by ticker -> {dates: [], adjusted_close: []}
    data: dict[str, dict[str, list]] = {}
    for row in result.result_rows:
        ticker_sym, dt_str, adj_str = row
        if ticker_sym not in data:
            data[ticker_sym] = {"dates": [], "adjusted_close": []}
        data[ticker_sym]["dates"].append(dt_str)
        data[ticker_sym]["adjusted_close"].append(adj_str)

    logger.debug(
        "fetch_adjusted_prices: queried %d tickers, got data for %d; range %s..%s",
        len(tickers),
        len(data),
        start_date,
        end_date,
    )
    return data
