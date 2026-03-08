# Build stage
FROM python:3.12-slim AS builder

WORKDIR /app

# Install system dependencies and uv
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://astral.sh/uv/install.sh | sh

# Copy dependency files
COPY services/portfolio-builder-api/pyproject.toml services/portfolio-builder-api/uv.lock ./

# Create virtual environment and install production dependencies
RUN /root/.local/bin/uv venv && \
    /root/.local/bin/uv sync --no-dev

# Runtime stage
FROM python:3.12-slim

WORKDIR /app

# Create non-root user for security
RUN groupadd -r fastapi && useradd -r -g fastapi fastapi

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY services/portfolio-builder-api/src/ ./src/

# Change ownership to non-root user
RUN chown -R fastapi:fastapi /app

# Switch to non-root user
USER fastapi

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PORT=8100

# Expose port (default 8100, Railway will override with $PORT)
EXPOSE ${PORT}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; import os; urllib.request.urlopen(f'http://localhost:{os.getenv(\"PORT\", \"8100\")}/health')" || exit 1

# Start uvicorn with explicit stdout logging config and dynamic port binding
CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT} --log-config /app/src/uvicorn-log-config.json"]
