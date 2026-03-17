# Deployment Guide

## Container Deployment

Build image:

```bash
docker build -t quant-api .
```

Run image:

```bash
docker run -p 8100:8100 \
  -e SUPABASE_URL=your-supabase-url \
  -e SUPABASE_SERVICE_ROLE_KEY=your-service-role-key \
  -e SUPABASE_DB_URL=your-postgres-connection-string \
  -e CORS_ORIGINS=https://your-core-app-domain \
  quant-api
```

## Railway Deployment

The repository includes `railway.toml` for Railway deployment.

Required environment variables:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_DB_URL`
- `CORS_ORIGINS`

Health endpoint:

- `/health`
