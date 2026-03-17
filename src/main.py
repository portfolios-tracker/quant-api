import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.routers import v1_portfolio_builder

app = FastAPI(
    title="Quant API",
    version="0.1.0"
)

cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root health check for Railway and Docker
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "quant-api"}

app.include_router(
    v1_portfolio_builder.router,
    prefix="/api/v1/portfolio-builder",
    tags=["quant-api"]
)
