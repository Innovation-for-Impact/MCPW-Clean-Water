"""Unit tests for GET /health."""
import pytest


@pytest.mark.asyncio
async def test_health_returns_200(client):
    resp = await client.get("/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_health_response_schema(client):
    resp = await client.get("/health")
    data = resp.json()
    assert data["status"] == "ok"
    assert "db" in data


@pytest.mark.asyncio
async def test_health_no_auth_required(client):
    """Health endpoint should work without any auth header."""
    resp = await client.get("/health")
    assert resp.status_code == 200
