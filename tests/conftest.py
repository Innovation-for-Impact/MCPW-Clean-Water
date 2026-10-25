"""
Shared fixtures for pytest.

Provides an async test client backed by an in-process SQLite database
so tests run without Docker/PostGIS. PostgreSQL-specific types (UUID,
JSONB, Geography) are compiled as TEXT for SQLite.

For integration tests that need PostGIS, set TEST_DATABASE_URL.
"""
import os
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ---------------------------------------------------------------------------
# Override env vars BEFORE importing application modules so that
# src.services.auth and src.models.database pick up test values.
# ---------------------------------------------------------------------------
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///")  # in-memory fallback

# ---------------------------------------------------------------------------
# Register SQLite type compilers for PostgreSQL-specific types.
# Must happen before models are imported.
# ---------------------------------------------------------------------------
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler  # noqa: E402

# Teach SQLite how to compile PostgreSQL-specific column types
SQLiteTypeCompiler.visit_UUID = lambda self, type_, **kw: "CHAR(32)"
SQLiteTypeCompiler.visit_JSONB = lambda self, type_, **kw: "TEXT"

# GeoAlchemy2 Geography/Geometry types use get_col_spec() internally.
# Override at the type level so SQLite gets plain TEXT.
import geoalchemy2  # noqa: E402

_orig_get_col_spec = geoalchemy2.Geography.get_col_spec


def _geography_col_spec_for_sqlite(self, **kw):
    return "TEXT"


# Monkey-patch only if we're using SQLite for tests
if "sqlite" in os.environ.get("TEST_DATABASE_URL", os.environ.get("DATABASE_URL", "sqlite")):
    geoalchemy2.Geography.get_col_spec = _geography_col_spec_for_sqlite
    if hasattr(geoalchemy2, "Geometry"):
        geoalchemy2.Geometry.get_col_spec = lambda self, **kw: "TEXT"

    # Disable GeoAlchemy2's after_create / before_drop listeners that try
    # to call spatial functions (CreateSpatialIndex, etc.) on SQLite
    import geoalchemy2.admin as _ga2_admin  # noqa: E402
    _ga2_admin.after_create = lambda *a, **kw: None
    _ga2_admin.before_drop = lambda *a, **kw: None
    # Also patch at the dialect-specific level
    import geoalchemy2.admin.dialects.sqlite as _ga2_sqlite  # noqa: E402
    _ga2_sqlite.after_create = lambda *a, **kw: None
    _ga2_sqlite.before_drop = lambda *a, **kw: None
    _ga2_sqlite.create_spatial_index = lambda *a, **kw: None

# Also handle the DDL compiler for spatial index creation
from sqlalchemy.dialects.sqlite.base import SQLiteDDLCompiler  # noqa: E402

_orig_visit_create_index = SQLiteDDLCompiler.visit_create_index


def _patched_visit_create_index(self, create, **kw):
    """Skip GIST indexes on SQLite (not supported)."""
    index = create.element
    if getattr(index, "dialect_options", {}).get("postgresql", {}).get("using") == "gist":
        return ""
    # Check for postgresql_using in the kwargs used at creation time
    if hasattr(index, "kwargs") and index.kwargs.get("postgresql_using") == "gist":
        return ""
    return _orig_visit_create_index(self, create, **kw)


SQLiteDDLCompiler.visit_create_index = _patched_visit_create_index

# ---------------------------------------------------------------------------
# Now import application modules
# ---------------------------------------------------------------------------
from src.api.dependencies import get_db  # noqa: E402
from src.api.main import app  # noqa: E402
from src.models import Base  # noqa: E402
from src.services.auth import create_access_token, hash_password  # noqa: E402

# ---------------------------------------------------------------------------
# Test database engine
# ---------------------------------------------------------------------------
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "sqlite+aiosqlite:///")

engine_test = create_async_engine(TEST_DATABASE_URL, echo=False)
async_session_test = async_sessionmaker(engine_test, expire_on_commit=False)

# ---------------------------------------------------------------------------
# Register PostGIS-equivalent functions on SQLite connections
# ---------------------------------------------------------------------------
if "sqlite" in TEST_DATABASE_URL:
    from sqlalchemy import event

    def _st_x(geom):
        """Extract longitude from POINT(lon lat) WKT string."""
        if geom and isinstance(geom, str) and geom.startswith("POINT("):
            return float(geom.replace("POINT(", "").replace(")", "").split()[0])
        return None

    def _st_y(geom):
        """Extract latitude from POINT(lon lat) WKT string."""
        if geom and isinstance(geom, str) and geom.startswith("POINT("):
            return float(geom.replace("POINT(", "").replace(")", "").split()[1])
        return None

    @event.listens_for(engine_test.sync_engine, "connect")
    def _register_spatial_functions(dbapi_conn, connection_record):
        """Register lightweight PostGIS function stubs on each SQLite connection."""
        dbapi_conn.create_function("ST_MakePoint", 2, lambda lon, lat: f"POINT({lon} {lat})")
        dbapi_conn.create_function("ST_SetSRID", 2, lambda geom, srid: geom)
        dbapi_conn.create_function("ST_DWithin", 3, lambda g1, g2, dist: True)
        dbapi_conn.create_function("ST_GeomFromText", 2, lambda wkt, srid: wkt)
        dbapi_conn.create_function("ST_GeogFromText", 1, lambda wkt: wkt)
        dbapi_conn.create_function("ST_AsText", 1, lambda geom: geom)
        dbapi_conn.create_function("AsBinary", 1, lambda geom: geom)
        dbapi_conn.create_function("AsEWKB", 1, lambda geom: geom)
        dbapi_conn.create_function("ST_X", 1, _st_x)
        dbapi_conn.create_function("ST_Y", 1, _st_y)
        dbapi_conn.create_function("CreateSpatialIndex", 2, lambda table, col: True)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_test() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db

# Also patch the module-level session factory used by dispatch_webhooks
# (it bypasses FastAPI dependency injection).
import src.models.database as _db_mod  # noqa: E402
import src.services.events as _events_mod  # noqa: E402

_db_mod.async_session_factory = async_session_test
_events_mod.async_session_factory = async_session_test


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Create all tables before each test, drop after.

    Skipped when TEST_DATABASE_URL points to PostgreSQL (spatial tests use
    persistent data and manage their own setup).
    """
    if "sqlite" not in TEST_DATABASE_URL:
        yield
        return
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a DB session for direct model access in tests."""
    async with async_session_test() as session:
        yield session


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client hitting the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def seed_users(db_session: AsyncSession):
    """Create one user per role and return their details."""
    from src.models.user import User

    users = {}
    for role in ("admin", "responder", "viewer"):
        user = User(
            username=f"test_{role}",
            password_hash=hash_password("password123"),
            role=role,
        )
        db_session.add(user)
        await db_session.flush()
        users[role] = {"id": user.id, "username": user.username, "role": role}
    await db_session.commit()
    return users


@pytest_asyncio.fixture
async def auth_headers(seed_users):
    """Return a dict mapping role -> Authorization header."""
    headers = {}
    for role, info in seed_users.items():
        token = create_access_token(info["id"], info["username"], role)
        headers[role] = {"Authorization": f"Bearer {token}"}
    return headers


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_INCIDENT_BODY = {
    "location": {"lat": 42.5973, "lon": -82.8779, "address": "123 Main St"},
    "water_body": "clinton_river",
    "material": "oil_fuel",
    "material_detail": "diesel",
    "quantity": 10.0,
    "quantity_unit": "gal",
    "quantity_gallons": 10.0,
    "time_observed": datetime.now(timezone.utc).isoformat(),
    "reporter_name": "Test User",
    "reporter_phone": "555-0100",
    "notes": "Test incident",
}

SAMPLE_LOOKUP_BODY = {
    "location": {"lat": 42.5973, "lon": -82.8779},
    "material": "oil_fuel",
    "quantity_gallons": 10.0,
}
