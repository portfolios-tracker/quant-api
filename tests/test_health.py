import httpx
import pytest
from src.main import app


@pytest.mark.asyncio
async def test_health_check():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/api/v1/portfolio-builder/health")

    assert response.status_code == 200
    data = response.json()

    # Check for camelCase keys
    assert "status" in data
    assert "serviceName" in data
    assert "version" in data

    # Check values
    assert data["status"] == "healthy"
    assert data["serviceName"] == "quant-api"
    assert data["version"] == "0.1.0"
