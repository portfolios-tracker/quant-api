# Architecture

## Scope

quant-api is a standalone FastAPI service responsible for quantitative computations and backtesting APIs.

## Modules

- `src/routers`: HTTP endpoints
- `src/models`: Pydantic schemas
- `src/quantitative`: numerical/backtesting logic
- `src/data`: Supabase/Postgres access
- `src/utils`: audit and utility logic

## Dependencies

- Supabase Postgres for historical market data
- Supabase REST for audit logging
- Core repository as the primary consumer

## Runtime Notes

- CORS origins are environment-configurable via `CORS_ORIGINS`.
- Service is stateless and suitable for horizontal scaling.
