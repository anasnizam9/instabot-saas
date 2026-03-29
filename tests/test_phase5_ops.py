import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_health_endpoint_includes_service_name(client: AsyncClient):
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "instabot-saas-api"


async def test_liveness_endpoint(client: AsyncClient):
    response = await client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json()["status"] == "alive"


async def test_readiness_endpoint(client: AsyncClient):
    response = await client.get("/api/v1/health/ready")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["checks"]["database"] == "ok"
    assert "scheduler" in data["checks"]


async def test_request_id_header_added(client: AsyncClient):
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
