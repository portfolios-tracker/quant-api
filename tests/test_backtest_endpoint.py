"""
services/quant-api/tests/test_backtest_endpoint.py

Integration-style tests for POST /api/v1/portfolio-builder/backtest (Story 2.3).

Strategy:
  - Use FastAPI TestClient (same pattern as test_historical_prices.py).
  - No external dependencies — backtest is pure computation.
  - Validates response shape, camelCase keys, and stringified float values.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.data.supabase_client import get_db_connection
from src.main import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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


def _make_valid_request() -> dict:
    """Build a minimal valid backtest request payload (camelCase)."""
    dates = [f"2024-01-{d:02d}" for d in range(2, 12)]  # 10 trading days
    return {
        "priceMatrix": {
            "TCB": {
                "dates": dates,
                "adjustedClose": [str(100 + i) for i in range(10)],
            },
            "VNM": {
                "dates": dates,
                "adjustedClose": [str(200 + i * 2) for i in range(10)],
            },
        },
        "benchmarkDates": dates,
        "benchmarkClose": [str(1000 + i * 5) for i in range(10)],
        "weightingMode": "equal",
    }


# ---------------------------------------------------------------------------
# Test 1: Valid request → HTTP 200, correct response shape with camelCase keys
# ---------------------------------------------------------------------------


class TestValidBacktest:
    """A valid request should return 200 with properly shaped camelCase response."""

    def test_response_200(self, client):
        resp = client.post("/api/v1/portfolio-builder/backtest", json=_make_valid_request())
        assert resp.status_code == 200

    def test_response_has_portfolio_curve(self, client):
        body = client.post("/api/v1/portfolio-builder/backtest", json=_make_valid_request()).json()
        assert "portfolioCurve" in body
        assert "dates" in body["portfolioCurve"]
        assert "values" in body["portfolioCurve"]

    def test_response_has_benchmark_curve(self, client):
        body = client.post("/api/v1/portfolio-builder/backtest", json=_make_valid_request()).json()
        assert "benchmarkCurve" in body
        assert "dates" in body["benchmarkCurve"]
        assert "values" in body["benchmarkCurve"]

    def test_response_has_metrics(self, client):
        body = client.post("/api/v1/portfolio-builder/backtest", json=_make_valid_request()).json()
        assert "metrics" in body
        for key in ("annualizedReturn", "maxDrawdown", "sharpeRatio"):
            assert key in body["metrics"]

    def test_response_has_benchmark_metrics(self, client):
        body = client.post("/api/v1/portfolio-builder/backtest", json=_make_valid_request()).json()
        assert "benchmarkMetrics" in body
        for key in ("annualizedReturn", "maxDrawdown", "sharpeRatio"):
            assert key in body["benchmarkMetrics"]

    def test_conviction_mode_accepted(self, client):
        payload = _make_valid_request()
        payload["weightingMode"] = "conviction"
        payload["convictionScores"] = {"TCB": "0.80", "VNM": "0.40"}
        resp = client.post("/api/v1/portfolio-builder/backtest", json=payload)
        assert resp.status_code == 200

    def test_market_cap_mode_accepted(self, client):
        payload = _make_valid_request()
        payload["weightingMode"] = "market_cap"
        payload["marketCapScores"] = {"TCB": "5000", "VNM": "15000"}
        resp = client.post("/api/v1/portfolio-builder/backtest", json=payload)
        assert resp.status_code == 200

    def test_response_has_asset_weights(self, client):
        body = client.post("/api/v1/portfolio-builder/backtest", json=_make_valid_request()).json()
        assert "assetWeights" in body
        for ticker in ("TCB", "VNM"):
            assert ticker in body["assetWeights"]
            # Each weight must be a parseable stringified float
            float(body["assetWeights"][ticker])


# ---------------------------------------------------------------------------
# Test 2: Empty priceMatrix → HTTP 422
# ---------------------------------------------------------------------------


class TestEmptyPriceMatrix:
    """An empty priceMatrix should be rejected with HTTP 422."""

    def test_empty_price_matrix_returns_422(self, client):
        payload = _make_valid_request()
        payload["priceMatrix"] = {}
        resp = client.post("/api/v1/portfolio-builder/backtest", json=payload)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Test 3: Response values are stringified floats, not native numbers
# ---------------------------------------------------------------------------


class TestStringifiedFloats:
    """All numeric values in the response must be strings, not JSON numbers."""

    def test_curve_values_are_strings(self, client):
        body = client.post("/api/v1/portfolio-builder/backtest", json=_make_valid_request()).json()
        for val in body["portfolioCurve"]["values"]:
            assert isinstance(val, str)
            float(val)  # must be parseable as float
        for val in body["benchmarkCurve"]["values"]:
            assert isinstance(val, str)
            float(val)

    def test_metrics_values_are_strings(self, client):
        body = client.post("/api/v1/portfolio-builder/backtest", json=_make_valid_request()).json()
        for key in ("annualizedReturn", "maxDrawdown", "sharpeRatio"):
            val = body["metrics"][key]
            assert isinstance(val, str)
            float(val)  # must be parseable
            val_b = body["benchmarkMetrics"][key]
            assert isinstance(val_b, str)
            float(val_b)

    def test_curve_dates_are_strings(self, client):
        body = client.post("/api/v1/portfolio-builder/backtest", json=_make_valid_request()).json()
        for d in body["portfolioCurve"]["dates"]:
            assert isinstance(d, str)
