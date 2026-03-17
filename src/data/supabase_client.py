"""
quant-api/src/data/supabase_client.py

Supabase (Postgres) integration for the quant-api service.

Canonical Supabase/Postgres integration for market data access
(see architecture-api.md).

Design decisions:
  - Per-request psycopg2 connection via FastAPI Depends() — psycopg2
    connections are cheap and not safe to share across threads without a pool.
  - Decimal values from Postgres are returned as Python Decimal objects; we
    serialise them as strings to avoid float rounding at the JSON boundary.
  - Uses SUPABASE_DB_URL env var for direct Postgres access (set to the Supabase
    connection-pooler or direct DB URL).
"""

from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from typing import Generator

import psycopg2

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


def get_db_connection() -> Generator:
    """
    FastAPI dependency — yields a fresh psycopg2 connection for each request.

    Usage::

        @router.post("/historical-prices")
        def endpoint(conn=Depends(get_db_connection)):
            ...
    """
    database_url = os.getenv("SUPABASE_DB_URL")
    if not database_url:
        raise RuntimeError("SUPABASE_DB_URL environment variable is not set")

    conn = psycopg2.connect(database_url, connect_timeout=10)
    try:
        yield conn
    finally:
        conn.close()


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
    conn,
) -> dict[str, dict[str, list]]:
    """
    Fetch adjusted prices from ``adjusted_price_daily`` for the given tickers
    and date range.

    Parameters
    ----------
    tickers:
        List of ticker symbols to query (may include VNINDEX).
    start_date, end_date:
        ISO date strings, inclusive on both ends.
    conn:
        An active psycopg2 connection.

    Returns
    -------
    dict[ticker, {"dates": [...], "adjusted_close": [...]}]
        Values are plain lists — dates as ``str``, adjusted_close as ``str``
        (serialised Decimal, no floating-point drift).
    """
    if not tickers:
        return {}

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                ticker,
                trading_date::text       AS trading_date,
                adjusted_close::text     AS adjusted_close
            FROM public.adjusted_price_daily
            WHERE ticker = ANY(%s)
              AND trading_date >= %s::date
              AND trading_date <= %s::date
            ORDER BY ticker, trading_date
            """,
            (tickers, start_date, end_date),
        )
        rows = cur.fetchall()

    data: dict[str, dict[str, list]] = {}
    for ticker_sym, dt_str, adj_str in rows:
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
