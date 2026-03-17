"""
quant-api/tests/test_backtest_audit.py

Unit tests for src/utils/audit_logger.py (Story 4.2).

Strategy:
  - Mock httpx.post to avoid real network calls.
  - Verify JSON payload structure passed to Supabase REST API.
  - Verify error handling when Supabase returns non-2xx status.
  - Verify graceful handling of httpx exceptions.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.utils.audit_logger import log_backtest_audit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_response(status_code: int = 201, text: str = "") -> MagicMock:
    mock = MagicMock()
    mock.status_code = status_code
    mock.text = text
    return mock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLogBacktestAudit:
    """Unit tests for log_backtest_audit()."""

    @patch.dict(
        "os.environ",
        {
            "SUPABASE_URL": "https://test.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "test-service-key",
        },
    )
    @patch("src.utils.audit_logger.httpx.post")
    def test_sends_correct_payload(self, mock_post):
        mock_post.return_value = _make_mock_response(201)

        log_backtest_audit(
            user_id="user-uuid-123",
            session_id="session-abc",
            thread_id="thread-xyz",
            request_payload={"tickers": ["VNM", "TCB"], "weightingMode": "equal"},
            response_payload={"metrics": {"annualizedReturn": "0.12"}},
            market_data_query_timestamp="2026-03-05T04:00:00Z",
            response_timestamp="2026-03-05T04:00:01Z",
            ip_address="127.0.0.1",
        )

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args

        # Verify URL
        assert "audit_logs" in call_kwargs.args[0]

        # Verify headers
        headers = call_kwargs.kwargs["headers"]
        assert headers["Authorization"] == "Bearer test-service-key"
        assert "application/json" in headers["Content-Type"]

        # Verify payload
        payload = call_kwargs.kwargs["json"]
        assert payload["user_id"] == "user-uuid-123"
        assert payload["session_id"] == "session-abc"
        assert payload["thread_id"] == "thread-xyz"
        assert payload["feature_type"] == "backtest"
        assert payload["llm_model_version"] == "quant-api/backtest"
        assert payload["ip_address"] == "127.0.0.1"
        assert payload["response_json"] == {"metrics": {"annualizedReturn": "0.12"}}

        # prompt_text is serialized JSON of the request payload
        parsed_prompt = json.loads(payload["prompt_text"])
        assert parsed_prompt["tickers"] == ["VNM", "TCB"]
        assert parsed_prompt["weightingMode"] == "equal"

        # data_source_metadata includes market-data timestamp and tickers
        metadata = payload["data_source_metadata"]
        assert metadata["market_data_query_timestamp"] == "2026-03-05T04:00:00Z"
        assert metadata["tickers"] == ["VNM", "TCB"]
        assert metadata["weighting_mode"] == "equal"

    @patch.dict(
        "os.environ",
        {
            "SUPABASE_URL": "https://test.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "test-service-key",
        },
    )
    @patch("src.utils.audit_logger.httpx.post")
    def test_does_not_raise_on_non_2xx_response(self, mock_post):
        mock_post.return_value = _make_mock_response(500, "internal server error")

        # Should not raise
        log_backtest_audit(
            user_id="user-uuid",
            session_id="session-id",
            request_payload={"tickers": []},
            response_payload={},
        )

    @patch.dict(
        "os.environ",
        {
            "SUPABASE_URL": "https://test.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "test-service-key",
        },
    )
    @patch(
        "src.utils.audit_logger.httpx.post", side_effect=Exception("connection refused")
    )
    def test_does_not_raise_on_httpx_exception(self, mock_post):
        # Should not raise
        log_backtest_audit(
            user_id="user-uuid",
            session_id="session-id",
            request_payload={"tickers": []},
            response_payload={},
        )

    @patch.dict("os.environ", {"SUPABASE_URL": "", "SUPABASE_SERVICE_ROLE_KEY": ""})
    @patch("src.utils.audit_logger.httpx.post")
    def test_skips_when_env_not_configured(self, mock_post):
        log_backtest_audit(
            user_id="user-uuid",
            session_id="session-id",
            request_payload={},
            response_payload={},
        )
        mock_post.assert_not_called()

    @patch.dict(
        "os.environ",
        {
            "SUPABASE_URL": "https://test.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "test-service-key",
        },
    )
    @patch("src.utils.audit_logger.httpx.post")
    def test_thread_id_is_none_when_not_provided(self, mock_post):
        mock_post.return_value = _make_mock_response(201)

        log_backtest_audit(
            user_id="user-uuid",
            session_id="session-id",
            request_payload={},
            response_payload={},
        )

        payload = mock_post.call_args.kwargs["json"]
        assert payload["thread_id"] is None
