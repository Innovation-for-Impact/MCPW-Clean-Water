"""
Benchmark spatial query performance against PostGIS.

Requires DATABASE_URL or TEST_DATABASE_URL pointing to PostGIS with loaded data.

Usage:
    SECRET_KEY=test-key DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/cleanwater" \
        python -m scripts.benchmark_spatial

Targets (from WS3 plan):
    - lookup_jurisdictions: median < 100ms, p95 < 200ms
    - trace_downstream (longest path): < 500ms
"""
import asyncio
import os
import random
import statistics
import time

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DB_URL = os.environ.get("TEST_DATABASE_URL", os.environ.get("DATABASE_URL", ""))

if "postgresql" not in DB_URL:
    print("ERROR: Requires a PostgreSQL/PostGIS DATABASE_URL or TEST_DATABASE_URL.")
    print(f"  Got: {DB_URL!r}")
    raise SystemExit(1)

# Macomb County bounding box (approximate)
MACOMB_BBOX = {
    "lat_min": 42.44,
    "lat_max": 42.72,
    "lon_min": -83.11,
    "lon_max": -82.72,
}


def random_point():
    lat = random.uniform(MACOMB_BBOX["lat_min"], MACOMB_BBOX["lat_max"])
    lon = random.uniform(MACOMB_BBOX["lon_min"], MACOMB_BBOX["lon_max"])
    return lat, lon


def report(label: str, times_ms: list[float]):
    times_ms.sort()
    n = len(times_ms)
    med = statistics.median(times_ms)
    p95 = times_ms[int(n * 0.95)] if n >= 20 else times_ms[-1]
    avg = statistics.mean(times_ms)
    mn = min(times_ms)
    mx = max(times_ms)
    print(f"\n  {label} ({n} calls)")
    print(f"    min={mn:.1f}ms  median={med:.1f}ms  p95={p95:.1f}ms  max={mx:.1f}ms  avg={avg:.1f}ms")
    return med, p95


async def main():
    engine = create_async_engine(DB_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    from src.services.spatial import find_nearest_water, lookup_jurisdictions, trace_downstream

    print("=" * 60)
    print("Spatial Query Benchmark")
    print("=" * 60)

    # ---- Benchmark lookup_jurisdictions ----
    n_points = 100
    points = [random_point() for _ in range(n_points)]
    lookup_times = []

    async with session_factory() as db:
        # Warm up
        await lookup_jurisdictions(42.5973, -82.8779, db=db)

        for lat, lon in points:
            t0 = time.perf_counter()
            await lookup_jurisdictions(lat, lon, db=db)
            elapsed = (time.perf_counter() - t0) * 1000
            lookup_times.append(elapsed)

    med, p95 = report("lookup_jurisdictions", lookup_times)
    lookup_ok = med < 100 and p95 < 200
    print(f"    TARGET: median < 100ms, p95 < 200ms → {'PASS' if lookup_ok else 'FAIL'}")

    # ---- Benchmark find_nearest_water ----
    nearest_times = []
    comids_found = []

    async with session_factory() as db:
        for lat, lon in points:
            t0 = time.perf_counter()
            result = await find_nearest_water(lat, lon, db=db)
            elapsed = (time.perf_counter() - t0) * 1000
            nearest_times.append(elapsed)
            if result:
                comids_found.append(result["nhd_comid"])

    report("find_nearest_water", nearest_times)

    # ---- Benchmark trace_downstream (longest path) ----
    if comids_found:
        trace_times = []
        max_path_len = 0

        async with session_factory() as db:
            # Test with all unique comids found
            unique_comids = list(set(comids_found))[:50]
            for comid in unique_comids:
                t0 = time.perf_counter()
                path = await trace_downstream(comid, db=db)
                elapsed = (time.perf_counter() - t0) * 1000
                trace_times.append(elapsed)
                if len(path) > max_path_len:
                    max_path_len = len(path)

        med, p95 = report("trace_downstream", trace_times)
        trace_ok = p95 < 500
        print(f"    TARGET: p95 < 500ms → {'PASS' if trace_ok else 'FAIL'}")
        print(f"    Longest path: {max_path_len} segments")
    else:
        print("\n  trace_downstream: SKIPPED (no waterways found near random points)")
        trace_ok = False

    # ---- Summary ----
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"  lookup_jurisdictions: {'PASS' if lookup_ok else 'FAIL'}")
    print(f"  trace_downstream:     {'PASS' if trace_ok else 'FAIL'}")
    print()

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
