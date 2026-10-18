# MCPW-Clean-Water — Clean Water Geotagging & Jurisdiction App

A web application for reporting water spills in Macomb County, MI. A reporter enters a spill summary (location, size, material), the app pins it on an ArcGIS map, identifies every affected jurisdiction, and lists who must be contacted — split into **Response** (who acts now) and **Regulatory** (who must be notified, and by when) panels.

## How It Works

1. Reporter enters a location (address, coordinates, or map click), estimated size, and material type.
2. App geocodes and drops a pin; size optionally draws an impact buffer.
3. Spatial query intersects the pin/buffer with jurisdiction layers (municipality, drain district, subwatershed, shoreline, Coast Guard sector, EPA region) and traces downstream receiving water.
4. Rules engine maps jurisdictions × material × size to required contacts.
5. Results display in Response and Regulatory panels with click-to-call/email links.

## Tech Stack

| Layer | Technology |
| --- | --- |
| Frontend | ArcGIS Maps SDK for JavaScript 4.x |
| Backend | FastAPI (Python) |
| Database | PostgreSQL + PostGIS |
| Data | Macomb County, Michigan, and USGS (NHD/WBD) GIS layers |

## Workstreams

| # | Workstream | Description |
| --- | --- | --- |
| WS1 | Map & Geotagging UI | Map with search, click-to-pin, and impact buffer |
| WS2 | Incident Intake & Parsing | Structured form + free-text parser → validated incident → event output for dashboard & Accela integration |
| WS3 | Jurisdiction Layers & Spatial Query | Point/buffer → jurisdictions + drain snap + downstream path + GeoJSON layers — **Phases 1–3 complete** |
| WS4 | Contacts Directory & Rules Engine | Jurisdictions + material + size → contacts with deadlines |
| WS5 | Backend API & Data Model | REST API (10 endpoints), DB, JWT auth, RBAC, audit trail, webhooks — **Phases 1–3 complete** |
| WS6 | Results UI, QA & Deployment | Response/Regulatory panels, end-to-end tests, hosting |

## API Endpoints

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `GET` | `/health` | No | Status check |
| `POST` | `/auth/login` | No | Authenticate, receive JWT |
| `POST` | `/auth/register` | Admin | Register a new user |
| `POST` | `/lookup` | Responder+ | Location + spill details → jurisdictions + contacts |
| `POST` | `/incidents` | Responder+ | Save incident, emit event |
| `GET` | `/incidents/{id}` | Viewer+ | Fetch saved incident |
| `GET` | `/events` | Viewer+ | Poll incident events (dashboard, Accela) |
| `GET` | `/layers/` | Viewer+ | List available jurisdiction layers |
| `GET` | `/layers/{name}` | Viewer+ | GeoJSON FeatureCollection for a layer (paginated) |
| `POST` | `/webhooks` | Admin | Register a webhook URL |
| `GET` | `/webhooks` | Admin | List registered webhooks |
| `DELETE` | `/webhooks/{id}` | Admin | Remove a webhook |

## Getting Started

### Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for running scripts outside Docker)

### Local Development

```bash
# 1. Copy env template and set SECRET_KEY
cp .env.example .env

# 2. Start services (API + PostGIS database)
docker compose up -d

# 3. Run database migrations
docker compose exec api alembic upgrade head

# 4. Seed dev users (admin/admin123, responder/responder123, viewer/viewer123)
docker compose exec api python -m scripts.seed_users

# 5. Run E2E tests
./scripts/test_e2e.sh
./scripts/test_e2e_ws3.sh   # WS3 layers & spatial lookup tests
```

API is available at `http://localhost:8000`. Interactive docs at `/docs` (Swagger) and `/redoc`.

### Authentication

```bash
# Get a JWT token
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"responder","password":"responder123"}'

# Use the token
curl http://localhost:8000/events \
  -H "Authorization: Bearer <token>"
```

## Scope

**v1:** Spills to water in Macomb County (Lake St. Clair, Clinton River and tributaries, county drains, storm sewers). Single incident at a time, manual contact via call/email links, saved incident record. Intake emits structured incident events consumable by an external dashboard and the Accela platform.

**Out of scope for v1:** Automated notifications, plume modeling, mobile-native apps, full Accela workflow automation (v1 provides the event hook only).

## Project Milestones

| Phase | Weeks | Work |
| --- | --- | --- |
| Foundations | 1–2 | Stack + schema, source GIS layers, contact schema, app shell |
| Core Build | 3–5 | Pin + buffer, form + parser, lookup query, seed contacts |
| Integrate | 6–7 | Rules engine, `/lookup` live, results panels, downstream trace |
| Pilot | 8 | End-to-end test scenarios, deploy, demo, verify contacts |

See [Architecture.md](Architecture.md) for full details on workstreams, risks, and open questions.
