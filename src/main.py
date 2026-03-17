from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.routers import v1_portfolio_builder

app = FastAPI(
    title="Portfolio Builder API",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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
    tags=["portfolio-builder"]
)
