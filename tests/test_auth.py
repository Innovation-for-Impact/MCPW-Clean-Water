"""Unit tests for POST /auth/login and POST /auth/register."""
import pytest


@pytest.mark.asyncio
async def test_login_valid_credentials(client, seed_users):
    resp = await client.post("/auth/login", json={
        "username": "test_admin",
        "password": "password123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_invalid_password(client, seed_users):
    resp = await client.post("/auth/login", json={
        "username": "test_admin",
        "password": "wrong_password",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client, seed_users):
    resp = await client.post("/auth/login", json={
        "username": "nobody",
        "password": "password123",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_missing_fields(client):
    resp = await client.post("/auth/login", json={"username": "test"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_token_contains_role(client, seed_users):
    """Decode the token and verify role claim is present."""
    import jwt
    import os

    resp = await client.post("/auth/login", json={
        "username": "test_responder",
        "password": "password123",
    })
    token = resp.json()["access_token"]
    payload = jwt.decode(token, os.environ["SECRET_KEY"], algorithms=["HS256"])
    assert payload["role"] == "responder"
    assert payload["username"] == "test_responder"


@pytest.mark.asyncio
async def test_register_as_admin(client, auth_headers):
    resp = await client.post(
        "/auth/register",
        json={"username": "new_user", "password": "newpass123"},
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "new_user"
    assert data["role"] == "viewer"


@pytest.mark.asyncio
async def test_register_as_non_admin_forbidden(client, auth_headers):
    resp = await client.post(
        "/auth/register",
        json={"username": "hacker", "password": "pass"},
        headers=auth_headers["responder"],
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_register_duplicate_username(client, auth_headers):
    resp = await client.post(
        "/auth/register",
        json={"username": "test_admin", "password": "password123"},
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_register_unauthenticated(client):
    resp = await client.post(
        "/auth/register",
        json={"username": "anon", "password": "pass"},
    )
    assert resp.status_code == 401
