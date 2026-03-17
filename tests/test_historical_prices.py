"""
services/quant-api/tests/test_historical_prices.py

Integration-style tests for POST /api/v1/portfolio-builder/historical-prices (Story 2.2).

Strategy:
  - Use FastAPI TestClient + app.dependency_overrides to skip real DB connection.
  - Patch src.routers.v1_portfolio_builder.fetch_adjusted_prices to control return data.
  - Patch src.routers.v1_portfolio_builder.period_to_dates to return deterministic dates.
  - No network connections; no data-pipeline infrastructure required.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.data.supabase_client import get_db_connection

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_FIXED_START = "2023-06-01"
_FIXED_END   = "2024-06-01"


@pytest.fixture
def client():
    """TestClient with the DB dependency overridden to a no-op mock."""
    mock_db_conn = MagicMock()

    def override_get_db_connection():
        yield mock_db_conn

    app.dependency_overrides[get_db_connection] = override_get_db_connection
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()


def _make_series(n: int = 3, ticker: str = "XX") -> dict:
    """Helper: generate a fake fetch_adjusted_prices return dict entry."""
    return {
        "dates":          [f"2024-0{i+1}-01" for i in range(n)],
        "adjusted_close": [str(10000 + i * 100) for i in range(n)],
    }


# ---------------------------------------------------------------------------
# Test 1: Valid request → correct response shape
# ---------------------------------------------------------------------------


class TestValidRequest:
    """
    Given a valid request for two tickers (TCB, VNM) with period=1Y,
    the response must include:
     - priceMatrix keys: TCB, VNM (not VNINDEX)
     - benchmarkDates / benchmarkClose: VNINDEX data
     - warnings: empty list
     - HTTP 200
    """

    @patch("src.routers.v1_portfolio_builder.period_to_dates", return_value=(_FIXED_START, _FIXED_END))
    @patch("src.routers.v1_portfolio_builder.fetch_adjusted_prices")
    def test_response_200(self, mock_fetch, mock_period, client):
        mock_fetch.return_value = {
            "VNINDEX": _make_series(5, "VNINDEX"),
            "TCB":     _make_series(5, "TCB"),
            "VNM":     _make_series(5, "VNM"),
        }

        resp = client.post(
            "/api/v1/portfolio-builder/historical-prices",
            json={"tickers": ["TCB", "VNM"], "period": "1Y"},
        )

        assert resp.status_code == 200

    @patch("src.routers.v1_portfolio_builder.period_to_dates", return_value=(_FIXED_START, _FIXED_END))
    @patch("src.routers.v1_portfolio_builder.fetch_adjusted_prices")
    def test_price_matrix_contains_requested_tickers(self, mock_fetch, mock_period, client):
        mock_fetch.return_value = {
            "VNINDEX": _make_series(5),
            "TCB":     _make_series(5),
            "VNM":     _make_series(5),
        }

        resp = client.post(
            "/api/v1/portfolio-builder/historical-prices",
            json={"tickers": ["TCB", "VNM"], "period": "1Y"},
        )
        body = resp.json()

        assert set(body["priceMatrix"].keys()) == {"TCB", "VNM"}

    @patch("src.routers.v1_portfolio_builder.period_to_dates", return_value=(_FIXED_START, _FIXED_END))
    @patch("src.routers.v1_portfolio_builder.fetch_adjusted_prices")
    def test_vnindex_not_in_price_matrix(self, mock_fetch, mock_period, client):
        mock_fetch.return_value = {
            "VNINDEX": _make_series(5),
            "TCB":     _make_series(5),
        }

        resp = client.post(
            "/api/v1/portfolio-builder/historical-prices",
            json={"tickers": ["TCB"], "period": "1Y"},
        )

        assert "VNINDEX" not in resp.json()["priceMatrix"]

    @patch("src.routers.v1_portfolio_builder.period_to_dates", return_value=(_FIXED_START, _FIXED_END))
    @patch("src.routers.v1_portfolio_builder.fetch_adjusted_prices")
    def test_benchmark_populated_from_vnindex(self, mock_fetch, mock_period, client):
        vnindex_series = _make_series(5, "VNINDEX")
        mock_fetch.return_value = {
            "VNINDEX": vnindex_series,
            "TCB":     _make_series(5),
        }

        body = client.post(
            "/api/v1/portfolio-builder/historical-prices",
            json={"tickers": ["TCB"], "period": "1Y"},
        ).json()

        # _make_series returns snake_case keys; the response JSON uses camelCase
        assert body["benchmarkDates"] == vnindex_series["dates"]
        assert body["benchmarkClose"] == vnindex_series["adjusted_close"]

    @patch("src.routers.v1_portfolio_builder.period_to_dates", return_value=(_FIXED_START, _FIXED_END))
    @patch("src.routers.v1_portfolio_builder.fetch_adjusted_prices")
    def test_no_warnings_on_full_data(self, mock_fetch, mock_period, client):
        mock_fetch.return_value = {
            "VNINDEX": _make_series(5),
            "TCB":     _make_series(5),
        }

        body = client.post(
            "/api/v1/portfolio-builder/historical-prices",
            json={"tickers": ["TCB"], "period": "1Y"},
        ).json()

        assert body["warnings"] == []

    @patch("src.routers.v1_portfolio_builder.period_to_dates", return_value=(_FIXED_START, _FIXED_END))
    @patch("src.routers.v1_portfolio_builder.fetch_adjusted_prices")
    def test_price_matrix_series_structure(self, mock_fetch, mock_period, client):
        """Each priceMatrix entry must have 'dates' and 'adjustedClose' arrays."""
        mock_fetch.return_value = {
            "VNINDEX": _make_series(3),
            "TCB":     _make_series(3),
        }

        body = client.post(
            "/api/v1/portfolio-builder/historical-prices",
            json={"tickers": ["TCB"], "period": "1Y"},
        ).json()

        assert "dates" in body["priceMatrix"]["TCB"]
        assert "adjustedClose" in body["priceMatrix"]["TCB"]
        assert len(body["priceMatrix"]["TCB"]["dates"]) == 3
        assert len(body["priceMatrix"]["TCB"]["adjustedClose"]) == 3


# ---------------------------------------------------------------------------
# Test 2: Unknown ticker → warning, absent from priceMatrix
# ---------------------------------------------------------------------------


class TestMissingTicker:
    """
    When a requested ticker has no data, it should appear in warnings (not raise)
    and must be absent from priceMatrix.
    """

    @patch("src.routers.v1_portfolio_builder.period_to_dates", return_value=(_FIXED_START, _FIXED_END))
    @patch("src.routers.v1_portfolio_builder.fetch_adjusted_prices")
    def test_missing_ticker_in_warnings(self, mock_fetch, mock_period, client):
        # BADTICKER absent from fetch result → triggers warning path
        mock_fetch.return_value = {
            "VNINDEX": _make_series(3),
            "TCB":     _make_series(3),
            # BADTICKER deliberately omitted
        }

        body = client.post(
            "/api/v1/portfolio-builder/historical-prices",
            json={"tickers": ["TCB", "BADTICKER"], "period": "1Y"},
        ).json()

        assert any("BADTICKER" in w for w in body["warnings"])

    @patch("src.routers.v1_portfolio_builder.period_to_dates", return_value=(_FIXED_START, _FIXED_END))
    @patch("src.routers.v1_portfolio_builder.fetch_adjusted_prices")
    def test_missing_ticker_absent_from_price_matrix(self, mock_fetch, mock_period, client):
        mock_fetch.return_value = {
            "VNINDEX": _make_series(3),
            "TCB":     _make_series(3),
        }

        body = client.post(
            "/api/v1/portfolio-builder/historical-prices",
            json={"tickers": ["TCB", "BADTICKER"], "period": "1Y"},
        ).json()

        assert "BADTICKER" not in body["priceMatrix"]

    @patch("src.routers.v1_portfolio_builder.period_to_dates", return_value=(_FIXED_START, _FIXED_END))
    @patch("src.routers.v1_portfolio_builder.fetch_adjusted_prices")
    def test_known_ticker_still_present_when_other_is_missing(self, mock_fetch, mock_period, client):
        mock_fetch.return_value = {
            "VNINDEX": _make_series(3),
            "TCB":     _make_series(3),
        }

        body = client.post(
            "/api/v1/portfolio-builder/historical-prices",
            json={"tickers": ["TCB", "BADTICKER"], "period": "1Y"},
        ).json()

        assert "TCB" in body["priceMatrix"]

    @patch("src.routers.v1_portfolio_builder.period_to_dates", return_value=(_FIXED_START, _FIXED_END))
    @patch("src.routers.v1_portfolio_builder.fetch_adjusted_prices")
    def test_still_200_even_with_missing_ticker(self, mock_fetch, mock_period, client):
        """Missing ticker is a warning, not an error — HTTP 200 expected."""
        mock_fetch.return_value = {"VNINDEX": _make_series(3)}

        resp = client.post(
            "/api/v1/portfolio-builder/historical-prices",
            json={"tickers": ["TOTALLY_UNKNOWN"], "period": "3Y"},
        )

        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Test 3: Database unavailable → 503
# ---------------------------------------------------------------------------


class TestDatabaseFailure:
    """When the database raises any exception, the endpoint must return 503."""

    @patch("src.routers.v1_portfolio_builder.period_to_dates", return_value=(_FIXED_START, _FIXED_END))
    @patch("src.routers.v1_portfolio_builder.fetch_adjusted_prices", side_effect=ConnectionError("DB down"))
    def test_returns_503_on_connection_error(self, mock_fetch, mock_period, client):
        resp = client.post(
            "/api/v1/portfolio-builder/historical-prices",
            json={"tickers": ["TCB"], "period": "1Y"},
        )

        assert resp.status_code == 503

    @patch("src.routers.v1_portfolio_builder.period_to_dates", return_value=(_FIXED_START, _FIXED_END))
    @patch("src.routers.v1_portfolio_builder.fetch_adjusted_prices", side_effect=Exception("timeout"))
    def test_returns_503_detail_on_generic_exception(self, mock_fetch, mock_period, client):
        resp = client.post(
            "/api/v1/portfolio-builder/historical-prices",
            json={"tickers": ["TCB"], "period": "1Y"},
        )

        assert resp.status_code == 503
        assert resp.json()["detail"] == "Database unavailable"
