# Portfolio Builder API

FastAPI service for quantitative backtesting and portfolio builder analysis.

## Setup

### Environment

Python 3.12+ required. Uses `uv` for dependency management.

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
cd services/portfolio-builder-api
uv sync
```

### Environment Variables

Create `.env` file:

```env
SUPABASE_URL=http://localhost:54321
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres
```

## Development

```bash
# Start development server (hot reload enabled)
pnpm dev

# Or directly with uv
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8100
```

API available at `http://localhost:8100`

## Docker Deployment

### Build Docker Image

```bash
docker build -t portfolio-builder-api .
```

### Run Docker Container

```bash
# Run with default port (8100)
docker run -p 8100:8100 \
  -e SUPABASE_URL=your-supabase-url \
  -e SUPABASE_SERVICE_ROLE_KEY=your-service-role-key \
  -e SUPABASE_DB_URL=your-postgres-connection-string \
  portfolio-builder-api

# Or with custom port (useful for Railway deployment)
docker run -p 8080:8080 \
  -e PORT=8080 \
  -e SUPABASE_URL=your-supabase-url \
  -e SUPABASE_SERVICE_ROLE_KEY=your-service-role-key \
  -e SUPABASE_DB_URL=your-postgres-connection-string \
  portfolio-builder-api
```

### Railway Deployment

The service is configured for Railway deployment via `railway.toml`. Railway will automatically:

- Build the Docker image using the Dockerfile
- Set the `PORT` environment variable dynamically
- Configure health checks at `/health` endpoint

Required environment variables in Railway:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_DB_URL`

## Testing

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_backtest_math.py

# Run with coverage
uv run pytest --cov=src tests/
```

## Architecture

- **Quantitative Math** (`src/quantitative/`) — Portfolio calculations, backtesting, weight allocation
- **Models** (`src/models/`) — Pydantic schemas matching `@workspace/shared-types/client`
- **API** (`src/api/`) — FastAPI routes and endpoints
- **Market Data Access** (`src/data/`) — Supabase-backed historical series queries for adjusted price inputs

All numeric values use stringified decimals (e.g., `"0.1234"`) to avoid floating-point precision loss.

The service is being standardized on Supabase as the only durable store for both semantic metadata and historical market series. There is no warehouse migration path to manage in this repository because no secondary analytical store has been provisioned.
