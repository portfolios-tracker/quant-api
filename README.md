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
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=8123
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=
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
  -e CLICKHOUSE_HOST=your-clickhouse-host \
  -e CLICKHOUSE_PORT=8123 \
  -e CLICKHOUSE_USER=default \
  -e CLICKHOUSE_PASSWORD=your-password \
  portfolio-builder-api

# Or with custom port (useful for Railway deployment)
docker run -p 8080:8080 \
  -e PORT=8080 \
  -e CLICKHOUSE_HOST=your-clickhouse-host \
  -e CLICKHOUSE_PORT=8123 \
  -e CLICKHOUSE_USER=default \
  -e CLICKHOUSE_PASSWORD=your-password \
  portfolio-builder-api
```

### Railway Deployment

The service is configured for Railway deployment via `railway.toml`. Railway will automatically:

- Build the Docker image using the Dockerfile
- Set the `PORT` environment variable dynamically
- Configure health checks at `/health` endpoint

Required environment variables in Railway:

- `CLICKHOUSE_HOST`
- `CLICKHOUSE_PORT`
- `CLICKHOUSE_USER`
- `CLICKHOUSE_PASSWORD`

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

All numeric values use stringified decimals (e.g., `"0.1234"`) to avoid floating-point precision loss.
