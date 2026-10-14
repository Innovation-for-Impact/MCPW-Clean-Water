import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from src.models import Base  # noqa: F401 — registers all models with metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url from environment variable
database_url = os.environ.get("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

target_metadata = Base.metadata

# Tables managed by PostGIS/tiger that Alembic should ignore
EXCLUDE_TABLES = {
    "spatial_ref_sys", "topology", "layer",
    "county", "county_lookup", "countysub_lookup", "cousub",
    "state", "state_lookup", "place", "place_lookup",
    "faces", "edges", "addr", "addrfeat", "featnames",
    "bg", "tract", "tabblock", "tabblock20", "zcta5",
    "zip_lookup", "zip_lookup_all", "zip_lookup_base", "zip_state", "zip_state_loc",
    "loader_lookuptables", "loader_platform", "loader_variables",
    "direction_lookup", "secondary_unit_lookup", "street_type_lookup",
    "geocode_settings", "geocode_settings_default",
    "pagc_gaz", "pagc_lex", "pagc_rules",
}


def include_name(name, type_, parent_names):
    if type_ == "table":
        return name not in EXCLUDE_TABLES
    return True


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_name=include_name,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_name=include_name,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
