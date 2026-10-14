# WS5 — Backend API & Data Model: Implementation Plan

## Progress Summary

| Phase | Status | Notes |
| --- | --- | --- |
| Phase 1 — Foundations | **Complete** | Stack, Docker, all Pydantic models, OpenAPI docs exported |
| Phase 2 — Core Build | **Complete** | All DB models, migrations, all endpoints, event publishing, webhooks, Accela stub |
| Phase 3.1–3.2 — Auth & Audit | **Complete** | JWT auth (PyJWT), RBAC (3 roles), audit trail with user ID in events |
| Phase 3.3 — WS3/WS4 Integration | **Blocked** | Waiting on WS3 spatial queries and WS4 rules engine |
| Phase 4.1 — Tests | **In Progress** | E2E script (34/34 passing); unit/integration tests pending |
| Phase 4.2 — Pilot Readiness | **Pending** | Waiting on WS6 scenarios and pilot demo |

**Key security hardening completed:**
- Replaced `python-jose` with `PyJWT` (CVE fixes)
- SSRF protection: DNS resolution + private IP checks at registration and dispatch time
- `SECRET_KEY` and `DATABASE_URL` raise `RuntimeError` if unset
- Single atomic transaction for incident + associations + event (no dual-commit)
- Webhook dispatch in background task with its own DB session

## Goal

One API that ties intake, spatial lookup, and contact rules together — and emits incident events for external consumers (dashboard, Accela).

## Done When

All endpoints are deployed with docs, the frontend can run a full lookup end to end, and incident events are available for external consumption.

## Dependencies

| Direction | Workstream | What |
| --- | --- | --- |
| Needs from | WS3 | Spatial lookup query (point/buffer → jurisdictions + downstream path) |
| Needs from | WS4 | Rules engine function (jurisdictions + incident → contacts) |
| Needs from | WS2 | Incident schema agreement (fields, validation rules) |
| Hands off to | WS1 | API URL + docs for frontend integration |
| Hands off to | WS2 | API contract + incident model for form submission |
| Hands off to | WS6 | API URL + docs for results panels |
| Hands off to | External | Incident events for dashboard and Accela platform |

## Technology

| Component | Technology |
| --- | --- |
| Framework | FastAPI (Python 3.11+) |
| Database | PostgreSQL 15+ with PostGIS 3.x |
| ORM | SQLAlchemy 2.x with GeoAlchemy2 |
| Migrations | Alembic |
| Containerization | Docker + Docker Compose |
| Testing | pytest + httpx (async test client) |
| Docs | Auto-generated OpenAPI (Swagger UI + ReDoc) |

## Implementation Tasks

### Phase 1 — Foundations (Weeks 1–2)

#### 1.1 Set up the stack

- [x] Create the backend project structure (see file structure below)
- [x] Set up FastAPI application with CORS middleware
  - Allow origins for the frontend dev server and production URL
- [x] Configure PostgreSQL + PostGIS connection
  - Use `asyncpg` for async database access via SQLAlchemy async engine
  - Connection string from environment variable (`DATABASE_URL`)
- [x] Write `Dockerfile` for the API service
  - Python 3.11+ slim image
  - Install PostGIS client libraries for GeoAlchemy2
- [x] Write `docker-compose.yml`
  - Services: `api` (FastAPI), `db` (PostgreSQL + PostGIS)
  - Persistent volume for database data
  - Environment variables from `.env` file
  - Health checks on both services
- [x] Verify `docker compose up` brings up a working API at `localhost:8000`
- [x] Add `GET /health` endpoint
  - Returns `{"status": "ok", "db": "connected"}` or appropriate error
  - Checks database connectivity

#### 1.2 Publish the API contract (Week 1 deliverable)

- [x] Define Pydantic models for all API types:

  **Incident**
  ```python
  class IncidentCreate(BaseModel):
      location: Location           # lat, lon, address
      water_body: WaterBodyType    # enum: lake_st_clair, clinton_river, tributary, county_drain, storm_sewer, unknown
      material: MaterialType       # enum: oil_fuel, chemical_hazmat, sewage, unknown_other
      material_detail: str | None  # e.g., "diesel", "antifreeze"
      quantity: float | None
      quantity_unit: QuantityUnit  # enum: gal, bbl, L, lb
      quantity_gallons: float | None  # normalized by WS2
      time_observed: datetime
      reporter_name: str
      reporter_phone: str
      notes: str | None
      buffer_radius_m: float | None

  class Incident(IncidentCreate):
      id: uuid.UUID
      created_at: datetime
      updated_at: datetime
      status: IncidentStatus  # enum: open, closed, under_review
  ```

  **Location**
  ```python
  class Location(BaseModel):
      lat: float
      lon: float
      address: str | None
  ```

  **Jurisdiction**
  ```python
  class Jurisdiction(BaseModel):
      layer: str           # e.g., "municipality", "drain_district"
      jurisdiction_id: str # stable ID from WS3
      name: str
  ```

  **Contact**
  ```python
  class Contact(BaseModel):
      agency: str
      role: ContactRole       # enum: response, regulatory
      jurisdiction_id: str
      phone: str
      after_hours_phone: str | None
      email: str | None
      hours: str | None
      reporting_deadline: str | None
      source_url: str
      last_verified: date
  ```

  **LookupResult**
  ```python
  class LookupRequest(BaseModel):
      location: Location
      material: MaterialType
      quantity_gallons: float | None
      buffer_radius_m: float | None

  class LookupResult(BaseModel):
      jurisdictions: list[Jurisdiction]
      downstream_path: list[str]
      response_contacts: list[Contact]
      regulatory_contacts: list[Contact]
  ```

  **IncidentEvent**
  ```python
  class IncidentEvent(BaseModel):
      event_id: uuid.UUID
      event_type: str          # "incident.created", "incident.updated"
      event_version: str       # "1.0"
      timestamp: datetime
      incident_id: uuid.UUID
      location: Location
      material: MaterialType
      material_detail: str | None
      quantity_gallons: float | None
      water_body: WaterBodyType
      jurisdictions: list[Jurisdiction]
      contacts: list[Contact]
      status: IncidentStatus
  ```

- [x] Share auto-generated OpenAPI docs with WS1, WS2, and WS6
  - Swagger UI at `/docs`
  - ReDoc at `/redoc`
  - Export `openapi.json` to the repo for version tracking

### Phase 2 — Core Build (Weeks 3–5)

#### 2.1 Set up the database

- [x] Define SQLAlchemy models for all tables:

  | Table | Key columns |
  | --- | --- |
  | `incidents` | id (UUID PK), location (Geography POINT), address, water_body, material, material_detail, quantity, quantity_unit, quantity_gallons, time_observed, reporter_name, reporter_phone, notes, buffer_radius_m, status, created_at, updated_at |
  | `jurisdictions` | id, layer, jurisdiction_id, name, geometry (Geography) |
  | `contacts` | id, agency, role, jurisdiction_id (FK), phone, after_hours_phone, email, hours, reporting_deadline, source_url, last_verified |
  | `rules` | id, jurisdiction_type, water_body, material, size_threshold, contact_id (FK), required (bool), deadline |
  | `incident_jurisdictions` | incident_id (FK), jurisdiction_id (FK) — join table |
  | `incident_contacts` | incident_id (FK), contact_id (FK), role, deadline |
  | `events` | id (UUID PK), event_type, event_version, timestamp, incident_id (FK), payload (JSONB) |

- [x] Create initial Alembic migration
  - `alembic init alembic`
  - Configure to use async engine
  - Generate and apply the initial migration
- [x] Add spatial indexes on `incidents.location` and `jurisdictions.geometry`
- [x] Seed jurisdiction data (coordinate with WS3 on import scripts)

#### 2.2 Build the endpoints

- [x] `POST /lookup`
  - Input: `LookupRequest` (location + material + quantity + buffer)
  - Call WS3 spatial query: intersect point/buffer with jurisdiction layers
  - Call WS4 rules engine: jurisdictions + material + size → contacts
  - Return: `LookupResult` with jurisdictions, downstream path, response contacts, regulatory contacts
  - No database write — this is a stateless query
  - *Note: currently uses mock spatial query and mock rules engine; will wire to WS3/WS4 in Phase 3.3*

- [x] `POST /incidents`
  - Input: `IncidentCreate`
  - Validate all fields; reject if required fields missing
  - Save to `incidents` table
  - Run the `/lookup` logic internally and store results in `incident_jurisdictions` and `incident_contacts`
  - Emit an incident event (see 2.3)
  - Return: `Incident` with id, created_at, and full lookup result
  - *Incident creation, association storage, and event emission are in a single atomic transaction*

- [x] `GET /incidents/{id}`
  - Return the saved incident with its jurisdiction and contact data
  - 404 if not found

- [x] `GET /events`
  - Query the `events` table, ordered by timestamp descending
  - Support query parameters:
    - `since` (ISO datetime) — return events after this timestamp
    - `limit` (int, default 50, max 200)
    - `incident_id` (UUID, optional) — filter to a specific incident
  - Return: `list[IncidentEvent]`

- [x] `GET /health`
  - Check DB connectivity; return status

#### 2.3 Event publishing & integration hooks

- [x] Implement the event publishing flow:
  - On `POST /incidents` (creation): write an `incident.created` event to the `events` table with the full incident payload as JSONB
  - On incident status update: write an `incident.updated` event
  - Each event gets a unique `event_id` (UUID) and `event_version: "1.0"`
  - *Event creation is atomic with incident creation (single DB transaction)*

- [x] Webhook support (optional, if dashboard needs push):
  - `webhook_urls` table: id, url, active, created_at
  - On event creation, POST the event payload to all active webhook URLs
  - Fire-and-forget with a short timeout (5s); log failures but don't retry in v1
  - Admin endpoints: `POST /webhooks`, `DELETE /webhooks/{id}`, `GET /webhooks`
  - *Webhook dispatch runs as a BackgroundTask with its own DB session*
  - *Concurrent delivery via asyncio.gather; SSRF protection at both registration and dispatch time*

- [x] Accela integration stub:
  - Create `src/integrations/accela.py` with an adapter interface:
    ```python
    class AccelaAdapter:
        async def create_record(self, event: IncidentEvent) -> dict:
            """Map an incident event to an Accela record.
            v1: logs the mapped payload; does not call Accela API.
            Post-v1: calls Accela Construct API to create a
            service request, permit, or inspection record."""
            pass
    ```
  - Define the event-to-Accela field mapping (incident fields → Accela record fields)
  - Log what *would* be sent to Accela for each incident event
  - Configuration via environment variables:
    - `ACCELA_ENABLED=false` (default off in v1)
    - `ACCELA_API_URL`, `ACCELA_APP_ID`, `ACCELA_APP_SECRET` (for post-v1)
    - `ACCELA_RECORD_TYPE` (e.g., "ServiceRequest/Spill/Incident/NA")

### Phase 3 — Integrate (Weeks 6–7)

#### 3.1 Add access control

- [x] Authentication
  - JWT-based auth with login endpoint (`POST /auth/login`)
  - User table: id, username, password_hash, role (responder, viewer, admin)
  - Password hashing with bcrypt (via passlib + bcrypt==4.0.1)
  - PyJWT for token creation/validation (replaced python-jose due to CVEs)
  - `SECRET_KEY` required via environment variable (RuntimeError if unset)
- [x] Authorization
  - Responders: can create incidents, run lookups
  - Viewers: read-only access to incidents and events
  - Admins: manage contacts, rules, webhooks, and users
  - Admin-only user registration endpoint (`POST /auth/register`)
- [x] Middleware
  - Require auth on all endpoints except `/health`, `/docs`, and `/auth/login`
  - All keys and passwords in environment variables, never in code
  - `RequireRole` dependency class for per-endpoint role enforcement

#### 3.2 Add an audit trail

- [x] Timestamp every incident record on create (`created_at`) and update (`updated_at`)
- [x] Log all state changes to the `events` table (doubles as audit log)
- [x] Include the authenticated user ID in each event payload (`created_by` field)

#### 3.3 Integration testing with WS3 and WS4

- [ ] Wire WS3 spatial query into `/lookup` — replace mock with live PostGIS queries *(blocked on WS3)*
- [ ] Wire WS4 rules engine into `/lookup` — replace mock with live rules table *(blocked on WS4)*
- [ ] End-to-end test: submit incident → verify jurisdictions, contacts, and event are correct

### Phase 4 — Pilot (Week 8)

#### 4.1 Write tests

- [x] E2E test script (`scripts/test_e2e.sh`) — 34 assertions across all endpoints
  - Covers: health, auth, RBAC, lookup, incidents, events, webhooks, SSRF, validation, registration
  - All 34 tests passing
- [ ] Unit tests for each endpoint using pytest + httpx async test client
  - Test happy paths and error cases (400, 404, 401)
  - Mock WS3/WS4 dependencies for unit tests
- [ ] Integration tests against a test database with PostGIS
  - Seed test jurisdiction and contact data
  - Verify full `/lookup` and `/incidents` flow
- [ ] Event tests
  - Verify events are created on incident creation
  - Verify `GET /events` filtering (since, limit, incident_id)
  - Verify webhook delivery (if implemented)
- [ ] Run tests automatically on every push (CI configuration in WS6)

#### 4.2 Pilot readiness

- [ ] All WS6 end-to-end test scenarios pass through the API
- [ ] API docs are current and accessible
- [ ] Fix issues logged during the pilot demo

## API Summary

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `GET` | `/health` | No | Status check |
| `POST` | `/auth/login` | No | Authenticate, receive JWT |
| `POST` | `/lookup` | Yes | Location + spill → jurisdictions + contacts |
| `POST` | `/incidents` | Yes | Save incident, emit event |
| `GET` | `/incidents/{id}` | Yes | Fetch saved incident |
| `GET` | `/events` | Yes | Poll incident events (dashboard, Accela) |
| `POST` | `/webhooks` | Admin | Register a webhook URL |
| `GET` | `/webhooks` | Admin | List registered webhooks |
| `DELETE` | `/webhooks/{id}` | Admin | Remove a webhook |

## Risks

| Risk | Mitigation |
| --- | --- |
| WS3/WS4 not ready on time | Build endpoints with mock responses first; swap in real queries when available |
| Event schema changes break external consumers | Version the event schema (`event_version`); maintain backwards compatibility |
| Accela API access not provisioned | v1 uses a stub adapter (log only); no hard dependency on Accela |
| Database performance with spatial queries | Spatial indexes on all geometry columns; monitor query times; optimize if > 200ms |
| Webhook reliability | v1 is fire-and-forget with logging; retry and dead-letter queue are post-v1 |

## Open Questions

- [ ] What Accela record type should incident events map to (service request, permit, inspection)?
- [ ] Does the county already have an Accela Construct API key and environment?
- [ ] What external dashboard will consume incident events — push (webhook) or pull (polling)?
- [ ] Does v1 need saved incident history, or lookup only? (Architecture says yes — confirm)
- [ ] Should the events endpoint support Server-Sent Events (SSE) for real-time streaming, or is polling sufficient for v1?

## File Structure (Proposed)

```
src/
  api/
    __init__.py
    main.py              # FastAPI app, CORS, middleware
    dependencies.py      # DB session, auth dependencies
    routes/
      __init__.py
      health.py          # GET /health
      auth.py            # POST /auth/login
      lookup.py          # POST /lookup
      incidents.py       # POST /incidents, GET /incidents/{id}
      events.py          # GET /events
      webhooks.py        # POST/GET/DELETE /webhooks
  models/
    __init__.py
    database.py          # SQLAlchemy engine, session
    incident.py          # Incident ORM model
    jurisdiction.py      # Jurisdiction ORM model
    contact.py           # Contact ORM model
    rule.py              # Rule ORM model
    event.py             # Event ORM model
    user.py              # User ORM model
    webhook.py           # Webhook ORM model
  schemas/
    __init__.py
    incident.py          # Pydantic models: IncidentCreate, Incident
    lookup.py            # Pydantic models: LookupRequest, LookupResult
    contact.py           # Pydantic models: Contact, ContactRole
    jurisdiction.py      # Pydantic models: Jurisdiction
    event.py             # Pydantic models: IncidentEvent
    auth.py              # Pydantic models: LoginRequest, Token
    enums.py             # Shared enums: MaterialType, WaterBodyType, etc.
  services/
    __init__.py
    lookup.py            # Orchestrates WS3 query + WS4 rules
    events.py            # Event creation and webhook dispatch
    auth.py              # JWT token creation and validation
  integrations/
    __init__.py
    accela.py            # Accela adapter (stub in v1)
  alembic/
    env.py
    versions/            # Migration files
  tests/
    __init__.py
    conftest.py          # Fixtures: test DB, test client, auth
    test_health.py
    test_lookup.py
    test_incidents.py
    test_events.py
docker-compose.yml
Dockerfile
.env.example             # Template with all required env vars
```
