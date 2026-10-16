"""
WS3 Performance benchmarks — jurisdiction lookup and downstream trace timing.

Targets:
- Jurisdiction lookup: median < 100ms, p95 < 200ms (100 random points)
- Downstream trace:   longest path < 500ms

Usage:
    DATABASE_URL="postgresql+asyncpg://..." pytest tests/test_performance.py -v -s
"""

import random
import statistics
import time

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.database import async_session_factory
from src.services.spatial import (
    find_nearest_drain,
    lookup_jurisdictions,
    run_spatial_lookup,
    trace_downstream,
)

# Macomb County approximate bounding box for random point generation
MACOMB_BBOX = {
    "min_lat": 42.44,
    "max_lat": 42.73,
    "min_lon": -83.11,
    "max_lon": -82.68,
}

NUM_RANDOM_POINTS = 100


def random_point():
    lat = random.uniform(MACOMB_BBOX["min_lat"], MACOMB_BBOX["max_lat"])
    lon = random.uniform(MACOMB_BBOX["min_lon"], MACOMB_BBOX["max_lon"])
    return lat, lon


@pytest_asyncio.fixture
async def db():
    async with async_session_factory() as session:
        yield session


class TestLookupPerformance:
    """Benchmark jurisdiction lookup query times."""

    @pytest.mark.asyncio
    async def test_lookup_100_random_points(self, db: AsyncSession):
        """Jurisdiction lookup for 100 random points: median < 100ms, p95 < 200ms."""
        times_ms = []
        for _ in range(NUM_RANDOM_POINTS):
            lat, lon = random_point()
            start = time.perf_counter()
            await lookup_jurisdictions(db, lat, lon)
            elapsed_ms = (time.perf_counter() - start) * 1000
            times_ms.append(elapsed_ms)

        median = statistics.median(times_ms)
        p95 = sorted(times_ms)[int(0.95 * len(times_ms))]
        mean = statistics.mean(times_ms)

        print(f"\n  Lookup performance ({NUM_RANDOM_POINTS} points):")
        print(f"    Mean:   {mean:.1f}ms")
        print(f"    Median: {median:.1f}ms (target: <100ms)")
        print(f"    P95:    {p95:.1f}ms (target: <200ms)")
        print(f"    Min:    {min(times_ms):.1f}ms")
        print(f"    Max:    {max(times_ms):.1f}ms")

        assert median < 100, f"Median lookup time {median:.1f}ms exceeds 100ms target"
        assert p95 < 200, f"P95 lookup time {p95:.1f}ms exceeds 200ms target"

    @pytest.mark.asyncio
    async def test_lookup_with_buffer(self, db: AsyncSession):
        """Jurisdiction lookup with 1km buffer should still be fast."""
        times_ms = []
        for _ in range(20):
            lat, lon = random_point()
            start = time.perf_counter()
            await lookup_jurisdictions(db, lat, lon, buffer_radius_m=1000)
            elapsed_ms = (time.perf_counter() - start) * 1000
            times_ms.append(elapsed_ms)

        median = statistics.median(times_ms)
        print(f"\n  Buffered lookup (1km, 20 points): median={median:.1f}ms")
        assert median < 500, f"Buffered lookup median {median:.1f}ms exceeds 500ms"


class TestDownstreamTracePerformance:
    """Benchmark downstream trace for longest flow path."""

    @pytest.mark.asyncio
    async def test_longest_trace(self, db: AsyncSession):
        """Downstream trace for longest path (drain → Clinton River → Lake St. Clair): < 500ms."""
        # Use Red Run at Dequindre (most upstream point) for longest trace
        start = time.perf_counter()
        drain = await find_nearest_drain(db, 42.5125, -83.0880)
        if drain:
            await trace_downstream(db, drain=drain)
        elapsed_ms = (time.perf_counter() - start) * 1000

        print(f"\n  Longest downstream trace: {elapsed_ms:.1f}ms (target: <500ms)")
        assert elapsed_ms < 500, f"Trace time {elapsed_ms:.1f}ms exceeds 500ms target"

    @pytest.mark.asyncio
    async def test_full_lookup_performance(self, db: AsyncSession):
        """Full spatial lookup (jurisdictions + drain + trace) for 20 random points."""
        times_ms = []
        for _ in range(20):
            lat, lon = random_point()
            start = time.perf_counter()
            await run_spatial_lookup(db, lat, lon)
            elapsed_ms = (time.perf_counter() - start) * 1000
            times_ms.append(elapsed_ms)

        median = statistics.median(times_ms)
        p95 = sorted(times_ms)[int(0.95 * len(times_ms))]

        print(f"\n  Full spatial lookup (20 points):")
        print(f"    Median: {median:.1f}ms")
        print(f"    P95:    {p95:.1f}ms")
        assert median < 500, f"Full lookup median {median:.1f}ms exceeds 500ms"
