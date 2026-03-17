# Integration Guide

This document defines how the core repository and other internal services integrate with quant-api.

## Service Identity

- Service name: quant-api
- Repository: portfolios-tracker/quant-api
- Runtime: FastAPI

## API Base URL and Headers

Required consumer configuration:

- `QUANT_API_BASE_URL`
- `QUANT_API_TIMEOUT_MS` (recommended default `15000`)
- `QUANT_API_KEY` (if API-key guard is enabled)

Recommended request headers:

- `Content-Type: application/json`
- `x-request-id: <uuid>`
- `x-api-key: <QUANT_API_KEY>` (for protected endpoints)

## Contract Expectations

- Response envelope is always: `success`, `data`, `error`, `meta.staleness`
- Numeric values are serialized as strings where precision matters
- Consumer schema package: `@workspace/shared-types/client/quant-api`

## Change Management

When changing contract-sensitive payloads:

1. Update models and endpoint behavior in quant-api.
2. Update shared schema contracts in the core repository.
3. Run tests in both repositories.
4. Publish migration notes for any breaking changes.

## Local Connectivity Check

Run quant-api locally:

- `uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8100`

Verify health:

- `curl http://localhost:8100/health`
