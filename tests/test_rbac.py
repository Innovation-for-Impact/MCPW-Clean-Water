"""
RBAC integration tests — verify every endpoint enforces correct role requirements.

Role matrix:
  - /health, /auth/login: no auth
  - /lookup: responder, admin
  - /incidents POST: responder, admin
  - /incidents/{id} GET: viewer, responder, admin
  - /events GET: viewer, responder, admin
  - /webhooks POST/GET/DELETE: admin only
  - /auth/register POST: admin only
"""
import pytest

from tests.conftest import SAMPLE_INCIDENT_BODY, SAMPLE_LOOKUP_BODY


# ---------------------------------------------------------------------------
# No-auth endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_no_auth(client):
    assert (await client.get("/health")).status_code == 200


@pytest.mark.asyncio
async def test_login_no_auth(client, seed_users):
    resp = await client.post("/auth/login", json={
        "username": "test_admin", "password": "password123",
    })
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# /lookup — responder + admin only
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("role,expected", [
    ("responder", 200),
    ("admin", 200),
    ("viewer", 403),
])
async def test_lookup_rbac(client, auth_headers, role, expected):
    resp = await client.post(
        "/lookup", json=SAMPLE_LOOKUP_BODY, headers=auth_headers[role],
    )
    assert resp.status_code == expected


@pytest.mark.asyncio
async def test_lookup_no_token(client):
    assert (await client.post("/lookup", json=SAMPLE_LOOKUP_BODY)).status_code == 401


# ---------------------------------------------------------------------------
# /incidents POST — responder + admin only
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("role,expected", [
    ("responder", 201),
    ("admin", 201),
    ("viewer", 403),
])
async def test_create_incident_rbac(client, auth_headers, role, expected):
    resp = await client.post(
        "/incidents", json=SAMPLE_INCIDENT_BODY, headers=auth_headers[role],
    )
    assert resp.status_code == expected


@pytest.mark.asyncio
async def test_create_incident_no_token(client):
    assert (await client.post("/incidents", json=SAMPLE_INCIDENT_BODY)).status_code == 401


# ---------------------------------------------------------------------------
# /incidents/{id} GET — viewer, responder, admin
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_incident_all_roles(client, auth_headers):
    # Create an incident first
    resp = await client.post(
        "/incidents", json=SAMPLE_INCIDENT_BODY, headers=auth_headers["responder"],
    )
    iid = resp.json()["id"]

    for role in ("viewer", "responder", "admin"):
        get_resp = await client.get(
            f"/incidents/{iid}", headers=auth_headers[role],
        )
        assert get_resp.status_code == 200, f"{role} should be able to read incidents"


@pytest.mark.asyncio
async def test_get_incident_no_token(client, auth_headers):
    resp = await client.post(
        "/incidents", json=SAMPLE_INCIDENT_BODY, headers=auth_headers["responder"],
    )
    iid = resp.json()["id"]
    assert (await client.get(f"/incidents/{iid}")).status_code == 401


# ---------------------------------------------------------------------------
# /events GET — viewer, responder, admin
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["viewer", "responder", "admin"])
async def test_events_all_roles(client, auth_headers, role):
    assert (await client.get("/events", headers=auth_headers[role])).status_code == 200


@pytest.mark.asyncio
async def test_events_no_token(client):
    assert (await client.get("/events")).status_code == 401


# ---------------------------------------------------------------------------
# /webhooks — admin only
# ---------------------------------------------------------------------------

WEBHOOK_URL = "https://example.com/hook"


@pytest.mark.asyncio
@pytest.mark.parametrize("role,expected", [
    ("admin", None),  # 201 or 422 (DNS), both acceptable
    ("responder", 403),
    ("viewer", 403),
])
async def test_create_webhook_rbac(client, auth_headers, role, expected):
    resp = await client.post(
        "/webhooks", json={"url": WEBHOOK_URL}, headers=auth_headers[role],
    )
    if expected is None:
        assert resp.status_code in (201, 422)  # 422 if DNS blocked
    else:
        assert resp.status_code == expected


@pytest.mark.asyncio
async def test_create_webhook_no_token(client):
    assert (await client.post("/webhooks", json={"url": WEBHOOK_URL})).status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("role,expected", [
    ("admin", 200),
    ("responder", 403),
    ("viewer", 403),
])
async def test_list_webhooks_rbac(client, auth_headers, role, expected):
    resp = await client.get("/webhooks", headers=auth_headers[role])
    assert resp.status_code == expected


@pytest.mark.asyncio
async def test_list_webhooks_no_token(client):
    assert (await client.get("/webhooks")).status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("role,expected", [
    ("responder", 403),
    ("viewer", 403),
])
async def test_delete_webhook_non_admin(client, auth_headers, role, expected):
    resp = await client.delete("/webhooks/1", headers=auth_headers[role])
    assert resp.status_code == expected


@pytest.mark.asyncio
async def test_delete_webhook_no_token(client):
    assert (await client.delete("/webhooks/1")).status_code == 401


# ---------------------------------------------------------------------------
# /auth/register — admin only
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("role,expected", [
    ("admin", 201),
    ("responder", 403),
    ("viewer", 403),
])
async def test_register_rbac(client, auth_headers, role, expected):
    import uuid
    username = f"user_{uuid.uuid4().hex[:8]}"
    resp = await client.post(
        "/auth/register",
        json={"username": username, "password": "password123"},
        headers=auth_headers[role],
    )
    assert resp.status_code == expected


@pytest.mark.asyncio
async def test_register_no_token(client):
    assert (await client.post(
        "/auth/register", json={"username": "x", "password": "y"},
    )).status_code == 401
