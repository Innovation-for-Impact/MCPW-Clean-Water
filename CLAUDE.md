# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FastAPI async backend for Macomb County spill response. A reporter enters spill details (location, size, material), the system identifies affected jurisdictions via spatial query, and returns required contacts split into Response and Regulatory panels.

**Stack**: FastAPI + SQLAlchemy 2.x async + PostgreSQL/PostGIS + Alembic migrations + JWT auth (PyJWT) with RBAC (admin/responder/viewer).

## Commands

```bash
# Run tests (excludes PostGIS-dependent tests)
SECRET_KEY=test-key DATABASE_URL="sqlite+aiosqlite:///" python -m pytest tests/ -v --tb=short --ignore=tests/test_spatial.py --ignore=tests/test_postgis_e2e.py

# Run a single test file
SECRET_KEY=test-key DATABASE_URL="sqlite+aiosqlite:///" python -m pytest tests/test_auth.py -v

# Run a single test by name
SECRET_KEY=test-key DATABASE_URL="sqlite+aiosqlite:///" python -m pytest tests/test_auth.py -v -k "test_login_success"

# Run a subset of tests
SECRET_KEY=test-key DATABASE_URL="sqlite+aiosqlite:///" python -m pytest tests/test_health.py tests/test_auth.py tests/test_webhooks.py -v

# Docker: start services, run migrations, seed users
docker compose up -d
docker compose exec api alembic upgrade head
docker compose exec api python -m scripts.seed_users

# Alembic migrations (requires DATABASE_URL pointing to PostGIS)
alembic upgrade head
alembic revision --autogenerate -m "description"

# Run spatial tests against PostGIS (requires loaded data)
SECRET_KEY=test-key DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/cleanwater" TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/cleanwater" python -m pytest tests/test_spatial.py -v

# Run PostGIS end-to-end integration tests (incident → spatial lookup → rules → contacts → event)
SECRET_KEY=test-key DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/cleanwater" TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/cleanwater" python -m pytest tests/test_postgis_e2e.py -v

# Run ALL PostGIS tests together
SECRET_KEY=test-key DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/cleanwater" TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/cleanwater" python -m pytest tests/test_spatial.py tests/test_postgis_e2e.py -v

# Data pipeline: download, clip, assign IDs, load jurisdictions
python scripts/download_layers.py --all
python scripts/clip_and_reproject.py
python -m scripts.load_layers          # --dry-run to preview

# Waterway pipeline: load NHDPlus HR flowlines + build downstream links
python -m scripts.load_waterways -i data/raw/waterways/NHDPLUS_H_0409_HU4_GDB.gdb --layer NHDFlowline --clip data/raw/municipalities/macomb_county_boundary.geojson
python -m scripts.build_downstream_links -i data/raw/waterways/NHDPLUS_H_0409_HU4_GDB.gdb --layer NHDPlusFlow

# Contact verification report (requires PostGIS with loaded data)
SECRET_KEY=test-key DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/cleanwater" python -m scripts.verify_contacts

# Benchmark spatial queries (requires PostGIS with loaded data)
SECRET_KEY=test-key DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/cleanwater" python -m scripts.benchmark_spatial

# Quarterly GIS data refresh (download + clip + reload all layers)
DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/cleanwater" python -m scripts.refresh_gis_data
DATABASE_URL="..." python -m scripts.refresh_gis_data --dry-run        # preview only
DATABASE_URL="..." python -m scripts.refresh_gis_data --skip-download  # reload from existing data

# Generate TypeScript types from OpenAPI schema
SECRET_KEY=test-key DATABASE_URL="sqlite+aiosqlite:///" python -m scripts.generate_types  # outputs shared/api-types.ts
```

## Architecture

### Request Flow
1. Route handler (`src/api/routes/`) validates auth via `RequireRole` dependency
2. Handler calls service layer (`src/services/`) with DB session from `get_db` dependency
3. Service layer uses SQLAlchemy async ORM; spatial queries use GeoAlchemy2 functions (ST_MakePoint, ST_DWithin)
4. Models (`src/models/`) define PostGIS geometry columns via GeoAlchemy2

### Key Architectural Patterns
- **Dependency injection**: `src/api/dependencies.py` provides `get_db` (async session) and `RequireRole` (hierarchical RBAC: admin > responder > viewer — e.g., `RequireRole("viewer")` grants access to all three roles)
- **App entry point**: `src/api/main.py` — FastAPI app with CORS and router registration
- **Database config**: `src/models/database.py` — reads `DATABASE_URL` env var, creates async engine and session factory. `Base` (DeclarativeBase) lives here.
- **Auth flow**: `src/services/auth.py` handles JWT creation/validation and password hashing. Requires `SECRET_KEY` env var.
- **Spatial service**: `src/services/spatial.py` — `lookup_jurisdictions`, `find_nearest_water`, `trace_downstream` (low-level PostGIS queries used by lookup and spatial tests)
- **Rules engine**: `src/services/rules_engine.py` — `evaluate_rules` matches jurisdiction layers + material + quantity against rules, returns deduplicated contacts sorted by priority
- **Lookup orchestration**: `src/services/lookup.py` — `run_lookup` ties spatial queries + rules engine together for `POST /lookup`
- **Spill parser**: `src/services/spill_parser.py` — `parse_spill_text` extracts structured fields from free text (water body, material, quantity, location, time)
- **Unit conversion**: `src/services/units.py` — `convert_to_gallons`, `convert_units`, `categorize_material` (loads keywords from `shared/material-categories.json`)
- **Buffer radius**: `src/services/buffer_radius.py` — `compute_buffer_radius` tiered lookup from quantity_gallons to radius_meters
- **CERCLA RQ**: `src/services/cercla.py` — `check_federal_reporting_required` checks spill against 40 CFR 302.4 thresholds
- **Contact verification**: `src/services/contact_verification.py` — `check_all_contacts`, `get_verification_summary` for admin reporting
- **Webhook delivery**: `src/models/webhook_delivery.py` — tracks delivery attempts, retries, dead-letter status
- **Rate limiting**: `src/api/rate_limit.py` — slowapi limiter, trusts `X-Forwarded-For` only when `TRUSTED_PROXY=true`
- **Alembic config**: `alembic.ini` sets `script_location = src/alembic`

### Models (all inherit from `Base` in `src/models/database.py`)
- `incident.py` — Geography POINT for spill location
- `jurisdiction.py` — Geography MULTIPOLYGON for jurisdiction boundaries
- `waterway.py` — Geography LINESTRING for waterways/downstream tracing
- `webhook_delivery.py` — webhook delivery tracking (attempts, retries, dead-letter)
- `user.py`, `event.py`, `webhook.py`, `contact.py`, `rule.py`, `association.py`

### API Endpoints
- **Health** (`health.py`): `GET /health` — no auth
- **Auth** (`auth.py`): `POST /auth/login` (rate-limited: 5/min per IP), `POST /auth/register` (admin only)
- **Layers** (`layers.py`): Public GeoJSON endpoints for WS1 map overlays — `GET /layers/jurisdictions` (list layers), `GET /layers/jurisdictions/{layer_name}` (FeatureCollection), `GET /layers/waterways` (flowlines with `named_only`/pagination params). No auth required.
- **Lookup** (`lookup.py`): `POST /lookup` — orchestrates WS3 spatial query + WS4 rules engine via `src/services/lookup.py`. Requires responder+.
- **Incidents** (`incidents.py`): `POST /incidents/parse` (viewer+, free-text → structured fields), `GET /incidents` (viewer+, filterable by status/material/water_body/date range), `POST /incidents` (responder+), `GET /incidents/{id}` (viewer+) — saves incident + emits event
- **Events** (`events.py`): `GET /events` (viewer+) — poll incident events for dashboard/Accela
- **Contacts** (`contacts.py`): CRUD, `GET` viewer+, `POST`/`DELETE` admin — service layer in `src/services/contacts.py`, `response_model` via Pydantic
- **Rules** (`rules.py`): CRUD, `GET` viewer+, `POST`/`DELETE` admin — service layer in `src/services/rules.py`, `response_model` via Pydantic
- **Webhooks** (`webhooks.py`): `POST`/`GET`/`DELETE` — admin only

### Testing Infrastructure
Tests use SQLite in-memory via `aiosqlite` (no Docker needed). `tests/conftest.py` applies extensive monkey-patches to make SQLAlchemy/GeoAlchemy2 work on SQLite:
- Compiles UUID → CHAR(32), JSONB → TEXT, Geography → TEXT
- Disables GeoAlchemy2 spatial admin hooks and GIST index creation
- Registers SQLite function stubs for PostGIS functions (ST_MakePoint, ST_SetSRID, ST_DWithin, ST_X, ST_Y, AsBinary, AsEWKB, etc.)
- Patches `async_session_factory` in `src.models.database` and `src.services.events` so background tasks (e.g., `dispatch_webhooks`) use the test DB
- The `setup_database` autouse fixture skips table create/drop when `TEST_DATABASE_URL` points to PostgreSQL (spatial tests use persistent data); it disposes the engine's connection pool after each test to avoid asyncpg event loop affinity issues
- `seed_users` uses get-or-create pattern so it works on persistent PostGIS databases across repeated test runs

**PostGIS e2e tests** (`test_postgis_e2e.py`): Full-chain integration tests (incident → spatial lookup → rules → contacts → event). Uses `boundary-test-cases.json` test points with known expected jurisdictions. Creates its own engine per fixture invocation — asyncpg connections are bound to the event loop that created them, and pytest-asyncio creates a new loop per test, so module-level engines cause "attached to a different loop" errors.

**Important**: bcrypt is pinned to 4.0.1 because passlib is incompatible with bcrypt 5.x.

**Test status**: 207 unit tests pass on SQLite (including 8 rules engine scenarios, 28 spill parser tests, rate limit, units, CERCLA, incidents list, webhook delivery, parse endpoint tests) + 38 spatial tests on PostGIS + 9 PostGIS e2e tests. **254 total** (2 spatial skipped for TC10 terminal segment).

## Environment Variables
- `SECRET_KEY` — **required**, used for JWT signing
- `DATABASE_URL` — **required**, async SQLAlchemy URL (e.g., `postgresql+asyncpg://...` or `sqlite+aiosqlite:///`)
- `TEST_DATABASE_URL` — optional, overrides DATABASE_URL for tests
- `LOG_LEVEL` — optional, default `INFO` (DEBUG, INFO, WARNING, ERROR)
- `LOG_FORMAT` — optional, default `text` (set to `json` for structured JSON logs)
- `CORS_ORIGINS` — optional, comma-separated allowed origins (defaults to `localhost:3000,localhost:5173`)
- `ENVIRONMENT` — optional, set to `production` to block dev seed scripts and require `--confirm` on GIS refresh
- `TRUSTED_PROXY` — optional, set to `true` when behind a reverse proxy to trust `X-Forwarded-For` for rate limiting

## Dev Users (seeded via `python -m scripts.seed_users`)
- `admin` / `admin123` (admin role)
- `responder` / `responder123` (responder role)
- `viewer` / `viewer123` (viewer role)

## Workstreams
- **WS3**: Jurisdiction Layers & Spatial Query — data pipeline, ETL scripts in `scripts/`
- **WS5**: Backend API & Data Model — API endpoints, auth, RBAC, testing

## Data Pipeline Status
- **Loaded into PostGIS**: municipalities (41), shoreline (1), county boundary (1), subwatersheds (21) — 64 jurisdictions total
- **Loaded into PostGIS**: NHDPlus HR waterways (1,917 flowlines, 726 named, 1,889 with downstream links — 98.5% coverage)
- **Pending data request**: drain districts, storm sewer outfalls (Macomb County Public Works — contact public.works@macombgov.org / 586-469-5325, GIS: gis.questions@macombgov.org / 586-469-5285)
- **Scripts**: `download_layers.py` → `clip_and_reproject.py` → `load_layers.py` (jurisdictions), `load_waterways.py` → `build_downstream_links.py` (waterways)
- **Jurisdiction IDs**: format `{layer}_{slug}` (e.g., `muni_mt_clemens`, `shoreline_lake_st_clair`, `county_macomb`, `ws_plum_brook`)

## Known Issues
- Spatial tests (`test_spatial.py`) skip without `TEST_DATABASE_URL` pointing to PostGIS with loaded data.
- EGLE RRD REST endpoint (`gisagoegle.state.mi.us`) drops connections from automated clients; URL is valid but requires browser access.
- Macomb County GIS portal (`gis.macombgov.org`) blocks all automated access (no hidden REST endpoints for drain data).
- NHD does not include Lake St. Clair as a flowline — the Clinton River terminates at "Clinton River Spillway" near the lake.
- TC10 `trace_downstream` and `downstream_flags` tests skip because the nearest segment is terminal (no downstream path).
- SQLite `ST_DWithin` stub in `conftest.py` always returns `True` — spatial filtering bugs won't be caught by unit tests, only by PostGIS spatial tests.
- `RequestLoggingMiddleware` uses Starlette's `BaseHTTPMiddleware`, which creates a task per request and prevents streaming responses. Fine at current scale; revisit if adding SSE or large file downloads.
- `openapi.json` is committed for reference but not CI-verified (Pydantic version differences cause schema drift). Regenerate with: `SECRET_KEY=x DATABASE_URL="sqlite+aiosqlite:///" python -c "from src.api.main import app; import json; print(json.dumps(app.openapi(), indent=4))" > openapi.json`

## Outstanding Work

### Blocked — Waiting on External Teams
1. **WS5 Phase 4.2: Pilot readiness** — waiting on WS6 team to deliver scenario definitions for end-to-end validation.
2. **WS3 Phase 3.2: Layer format coordination** — GeoJSON endpoints are built. Waiting on WS1 to confirm if they need ArcGIS feature layers or vector tiles instead.
3. **Obtain drain district + storm sewer outfall data** — requires manual outreach to Macomb County Public Works (public.works@macombgov.org / 586-469-5325, GIS: gis.questions@macombgov.org / 586-469-5285). Once received, add to data pipeline and load into PostGIS.
4. **WS4 contact verification** — 14 municipal contacts sourced from 2018 data need phone re-verification before pilot. Requires manual calls.
5. **WS1/WS2/WS6 — UI workstreams** — all three are planning-only, no code started. WS1 (map) needs ArcGIS API key tier confirmation. WS2 (intake form) needs WS5 schema agreement. WS6 (results UI + deployment) needs WS1–WS5 integration-ready.

### Done
- [x] WS4 rules engine + contact directory + seed data (35 rules, 26 contacts)
- [x] CI pipeline (lint, unit tests, spatial tests)
- [x] Spatial benchmark — all targets PASS
- [x] Structured logging + request middleware
- [x] Docker hardening (non-root user, required secrets, resource limits)
- [x] Ruff linting enforced across codebase
- [x] RBAC hierarchy fix (admin > responder > viewer)
- [x] CORS origins configurable via env var
- [x] Production guard on seed scripts
- [x] openapi.json CI sync check
- [x] Rate limiting on `/auth/login` (slowapi, 5/min per IP, proxy-safe via `TRUSTED_PROXY` env var)
- [x] Refactored `contacts.py` and `rules.py` to service layer + `response_model`
- [x] Webhook retry + dead-letter queue (`WebhookDelivery` model, exponential backoff, 6 attempts max)
- [x] Unit conversion service (`src/services/units.py` — gal/bbl/L/lb conversions + material categorization)
- [x] CERCLA RQ lookup tables (`src/services/cercla.py` — 40 CFR 302.4 thresholds for 17 substances)
- [x] Historical incident query (`GET /incidents` — filter by status, material, water_body, date range)
- [x] Contact verification service (`src/services/contact_verification.py` — staleness, phone/email validation)
- [x] GIS data quarterly refresh script (`scripts/refresh_gis_data.py` — full pipeline orchestration)
- [x] Shared material categories JSON (`shared/material-categories.json` — sourced from MCPWO protocol)
- [x] Spill parser service (`src/services/spill_parser.py` — free-text → structured fields, protocol drain names)
- [x] Buffer radius lookup (`src/services/buffer_radius.py` — quantity → radius tiered table)
- [x] Parse endpoint (`POST /incidents/parse` — server-side spill text parsing for frontend auto-fill)
- [x] Parser test cases (22 scenarios in `tests/parser-test-cases.json` + edge case tests)
- [x] TypeScript type generation (`scripts/generate_types.py` → `shared/api-types.ts`)

## Breaking API Changes
- **`POST /lookup` — `material` field is now optional** (was required). Clients that omitted `material` previously got 422; now they get results filtered to material-agnostic rules only. Update frontend callers if they relied on the 422 for validation.

## CI

GitHub Actions workflows in `.github/workflows/`:
- **ci.yml** — three jobs:
  - **lint**: ruff format + lint (required check)
  - **unit-tests**: 137 SQLite-based tests on every push/PR to `main`
  - **spatial-tests**: PostGIS integration + benchmark, manual `workflow_dispatch` only (requires geodata cache)
- **cache-geodata.yml** — one-time `workflow_dispatch` to upload `data/raw/` (~260MB) into Actions cache for spatial-tests

## Linting

`ruff.toml` configures ruff for Python 3.11, line-length 120. Run `ruff check .` and `ruff format .` locally.

## Logging

- `src/logging_config.py` — structured logging config, controlled by `LOG_LEVEL` and `LOG_FORMAT` env vars
- `src/api/middleware.py` — `RequestLoggingMiddleware` logs method, path, status, duration, request_id on every request
- Set `LOG_FORMAT=json` for structured JSON output in production

## Docker

- `Dockerfile` — non-root `appuser`, slim image, `.dockerignore` excludes tests/data/docs
- `docker-compose.yml` — requires `POSTGRES_PASSWORD` and `SECRET_KEY` via `.env` (no hardcoded defaults for secrets), resource limits (1G db, 512M api), restart policies

## Benchmark Results (2026-11-04)

All spatial query performance targets **PASS** (run via `scripts/benchmark_spatial.py`):
- `lookup_jurisdictions` (100 calls): median=4.3ms, p95=9.1ms — target <100ms/<200ms
- `find_nearest_water` (100 calls): median=1.0ms, p95=2.5ms
- `trace_downstream` (50 calls): median=0.6ms, p95=2.1ms — target <500ms; longest path 42 segments
