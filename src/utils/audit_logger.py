"""
services/portfolio-builder-api/src/utils/audit_logger.py

Story 4.2: AI Audit & Hallucination Logging — Python-side audit logger.

Persists backtest request/response pairs to the Supabase `audit_logs` table
using the Supabase REST API directly via httpx, without requiring the
`supabase-py` SDK (which is not yet a project dependency).

All errors are swallowed so audit failures never block user responses.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def log_backtest_audit(
    *,
    user_id: str,
    session_id: str,
    thread_id: str | None = None,
    request_payload: dict[str, Any],
    response_payload: dict[str, Any],
    market_data_query_timestamp: str | None = None,
    response_timestamp: str | None = None,
    ip_address: str | None = None,
) -> None:
    """
    Persist a backtest audit log entry to ``public.audit_logs``.

    This function is **fire-and-forget**: it logs errors to the Python logger
    but never raises, so the FastAPI response is never blocked.

    Parameters
    ----------
    user_id:
        Supabase Auth UUID of the calling user.
    session_id:
        Browser/device session identifier forwarded from the Next.js layer.
    thread_id:
        Optional assistant-ui thread identifier for multi-turn correlation.
    request_payload:
        Serialisable dict of the backtest request (tickers, weighting, dates, etc.).
    response_payload:
        Serialisable dict of the backtest response (equity curve, metrics, etc.).
    market_data_query_timestamp:
        ISO 8601 timestamp captured when market data was queried; falls back to now.
    response_timestamp:
        ISO 8601 timestamp of when the FastAPI response was generated; falls back to now.
    ip_address:
        Optional requester IP address.
    """
    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_service_role_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    if not supabase_url or not supabase_service_role_key:
        logger.warning(
            "[audit_logger] SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not configured — "
            "skipping audit log."
        )
        return

    now = _now_iso()
    row = {
        "user_id": user_id,
        "session_id": session_id,
        "thread_id": thread_id,
        "prompt_text": json.dumps(request_payload),
        "prompt_timestamp": now,
        "response_json": response_payload,
        "response_timestamp": response_timestamp or now,
        "llm_model_version": "portfolio-builder-api/backtest",
        "data_source_metadata": {
            "market_data_query_timestamp": market_data_query_timestamp or now,
            "tickers": request_payload.get("tickers", []),
            "weighting_mode": request_payload.get("weightingMode"),
        },
        "feature_type": "backtest",
        "ip_address": ip_address,
    }

    try:
        response = httpx.post(
            f"{supabase_url}/rest/v1/audit_logs",
            headers={
                "apikey": supabase_service_role_key,
                "Authorization": f"Bearer {supabase_service_role_key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            json=row,
            timeout=5.0,
        )
        if response.status_code not in (200, 201):
            logger.error(
                "[audit_logger] Supabase insert failed: status=%s body=%s",
                response.status_code,
                response.text[:200],
            )
    except Exception as exc:  # noqa: BLE001
        logger.error("[audit_logger] Unexpected error during audit logging: %s", exc)
