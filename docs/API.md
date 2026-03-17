# API Contract

## Base Path

Current versioned prefix:

- `/api/v1/portfolio-builder`

## Envelope

All endpoint responses use:

- `success`
- `data`
- `error`
- `meta.staleness`

## Primary Endpoints

- `GET /health`
- `POST /api/v1/portfolio-builder/historical-prices`
- `POST /api/v1/portfolio-builder/backtest`

## Precision Rules

Financial values should be serialized as strings at API boundaries to avoid float drift.

## Docs Endpoint

- OpenAPI JSON: `/openapi.json`
- Swagger UI: `/docs`
- ReDoc: `/redoc`
