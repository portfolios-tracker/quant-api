# Consumer Integration Guide

This document defines how external consumers integrate with `quant-api`.

## Service Identity

- Service name: `quant-api`
- Repository: `portfolios-tracker/quant-api`
- Runtime: FastAPI

## Authentication

Use service-to-service authentication for non-public endpoints.

Recommended headers:

- `Content-Type: application/json`
- `x-api-key: <SERVICE_KEY>` when guard is enabled
- `x-request-id: <uuid>` for tracing

## API Contract

Consumer contract expectations:

- Response envelope: `success`, `data`, `error`, `meta.staleness`
- Numeric precision policy: avoid floating-point precision loss at boundaries

Consumer-side schema package:

- `@workspace/shared-types/client/quant-api`

## Change Management

When API payloads change:

1. Update API models in this repository.
2. Update shared contract schemas in `portfolios-tracker`.
3. Run integration tests in both repos.
4. Publish migration notes for any breaking changes.

## Local Run

Development command:

- `uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8080`

Health check example:

- `curl http://localhost:8080/health`

## CI Recommendations

- Validate tests on every pull request.
- Add schema compatibility checks for contract-sensitive endpoints.
- Block merge if envelope shape or required fields drift unexpectedly.
