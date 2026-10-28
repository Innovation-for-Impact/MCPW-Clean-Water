# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FastAPI async backend for Macomb County spill response. A reporter enters spill details (location, size, material), the system identifies affected jurisdictions via spatial query, and returns required contacts split into Response and Regulatory panels.

**Stack**: FastAPI + SQLAlchemy 2.x async + PostgreSQL/PostGIS + Alembic migrations + JWT auth (PyJWT) with RBAC (admin/responder/viewer).

## Commands

```bash
# Run tests (excludes spatial tests that require PostGIS)
SECRET_KEY=test-key DATABASE_URL="sqlite+aiosqlite:///" python -m pytest tests/ -v --tb=short --ignore=tests/test_spatial.py

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

# Data pipeline: download, clip, assign IDs, load jurisdictions
python scripts/download_layers.py --all
python scripts/clip_and_reproject.py
python -m scripts.load_layers          # --dry-run to preview

# Waterway pipeline: load NHDPlus HR flowlines + build downstream links
python -m scripts.load_waterways -i data/raw/waterways/NHDPLUS_H_0409_HU4_GDB.gdb --layer NHDFlowline --clip data/raw/municipalities/macomb_county_boundary.geojson
python -m scripts.build_downstream_links -i data/raw/waterways/NHDPLUS_H_0409_HU4_GDB.gdb --layer NHDPlusFlow

# Benchmark spatial queries (requires PostGIS with loaded data)
SECRET_KEY=test-key DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/cleanwater" python -m scripts.benchmark_spatial
```

## Architecture

### Request Flow
1. Route handler (`src/api/routes/`) validates auth via `RequireRole` dependency
2. Handler calls service layer (`src/services/`) with DB session from `get_db` dependency
3. Service layer uses SQLAlchemy async ORM; spatial queries use GeoAlchemy2 functions (ST_MakePoint, ST_DWithin)
4. Models (`src/models/`) define PostGIS geometry columns via GeoAlchemy2

### Key Architectural Patterns
- **Dependency injection**: `src/api/dependencies.py` provides `get_db` (async session) and `RequireRole` (RBAC decorator accepting role strings)
- **App entry point**: `src/api/main.py` — FastAPI app with CORS and router registration
- **Database config**: `src/models/database.py` — reads `DATABASE_URL` env var, creates async engine and session factory. `Base` (DeclarativeBase) lives here.
- **Auth flow**: `src/services/auth.py` handles JWT creation/validation and password hashing. Requires `SECRET_KEY` env var.
- **Alembic config**: `alembic.ini` sets `script_location = src/alembic`

### Models (all inherit from `Base` in `src/models/database.py`)
- `incident.py` — Geography POINT for spill location
- `jurisdiction.py` — Geography MULTIPOLYGON for jurisdiction boundaries
- `waterway.py` — Geography LINESTRING for waterways/downstream tracing
- `user.py`, `event.py`, `webhook.py`, `contact.py`, `rule.py`, `association.py`

### API Endpoints
- **Layers** (`src/api/routes/layers.py`): Public GeoJSON endpoints for WS1 map overlays — `GET /layers/jurisdictions` (list layers), `GET /layers/jurisdictions/{layer_name}` (FeatureCollection), `GET /layers/waterways` (flowlines with `named_only`/pagination params). No auth required.
- **Lookup** (`src/api/routes/lookup.py`): `POST /lookup` — orchestrates WS3 spatial query + WS4 rules engine via `src/services/lookup.py`
- Contacts and rules routes do direct ORM CRUD without a dedicated service file

### Testing Infrastructure
Tests use SQLite in-memory via `aiosqlite` (no Docker needed). `tests/conftest.py` applies extensive monkey-patches to make SQLAlchemy/GeoAlchemy2 work on SQLite:
- Compiles UUID → CHAR(32), JSONB → TEXT, Geography → TEXT
- Disables GeoAlchemy2 spatial admin hooks and GIST index creation
- Registers SQLite function stubs for PostGIS functions (ST_MakePoint, ST_SetSRID, ST_DWithin, ST_X, ST_Y, AsBinary, AsEWKB, etc.)
- Patches `async_session_factory` in `src.models.database` and `src.services.events` so background tasks (e.g., `dispatch_webhooks`) use the test DB
- The `setup_database` autouse fixture skips table create/drop when `TEST_DATABASE_URL` points to PostgreSQL (spatial tests use persistent data)

**Important**: bcrypt is pinned to 4.0.1 because passlib is incompatible with bcrypt 5.x.

**Test status**: 127 unit tests pass on SQLite + 38 spatial tests pass on PostGIS (10 jurisdiction lookups, 10 nearest-water, 9 downstream traces, 9 downstream flags; 2 skipped for TC10 terminal segment). **165 total.**

## Environment Variables
- `SECRET_KEY` — **required**, used for JWT signing
- `DATABASE_URL` — **required**, async SQLAlchemy URL (e.g., `postgresql+asyncpg://...` or `sqlite+aiosqlite:///`)
- `TEST_DATABASE_URL` — optional, overrides DATABASE_URL for tests

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

## Outstanding Work

### Blocked — External Dependency
1. **Obtain drain district + storm sewer outfall data** from Macomb County Public Works (requires manual outreach — contact public.works@macombgov.org / 586-469-5325, GIS: gis.questions@macombgov.org / 586-469-5285)

### Remaining
- WS5 Phase 4.1: End-to-end integration test (submit incident → verify jurisdictions, contacts, and event are correct on PostGIS)
- WS5 Phase 4.2: Pilot readiness — waiting on WS6 scenarios
- WS3 Phase 3.2: Coordinate with WS1 on chosen layer format (GeoJSON endpoints are built; may need ArcGIS feature layers or vector tiles)
- Run `scripts/benchmark_spatial.py` against PostGIS to validate performance targets
