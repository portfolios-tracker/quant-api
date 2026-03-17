# Setup Guide

## Prerequisites

- Python 3.12+
- uv package manager

## Local Setup

1. Install dependencies:

```bash
uv sync
```

2. Create environment file:

```bash
cp .env.example .env
```

3. Run service:

```bash
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8100
```

4. Verify service:

```bash
curl http://localhost:8100/health
```

## Test

```bash
uv run pytest -q
```
