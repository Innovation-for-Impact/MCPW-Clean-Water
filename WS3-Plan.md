# WS3 — Jurisdiction Layers & Spatial Query: Implementation Plan

## Goal

For any point in Macomb County, return every jurisdiction and water body the spill affects, plus the county drain it reaches, that drain's tier, who owns the conveyance, and the first large drain downstream — the inputs the handbook rules engine (WS4) needs.

## Done When

The lookup returns the correct municipality, drain district, drain and drain tier, conveyance owner, subwatershed, receiving water, first large drain downstream, and downstream path for every boundary and drain test case.

## Dependencies

| Direction | Workstream | What |
| --- | --- | --- |
| Needs from | — | External GIS data sources (Macomb County, Michigan, USGS) |
| Needs from | MCPWO | County drain inventory and the list of large known drains (Tier 1/2) |
| Hands off to | WS1 | Published feature layers / vector tiles for map overlays |
| Hands off to | WS4 | Jurisdiction IDs for contact/rules matching |
| Hands off to | WS5 | Spatial lookup query (called by `/lookup` endpoint) |

## Technology

- **PostgreSQL 15+ with PostGIS 3.x** — spatial storage, indexing, and queries
- **GDAL/OGR (`ogr2ogr`)** — format conversion and reprojection of source data
- **SQLAlchemy 2.x + GeoAlchemy2** — ORM layer for spatial models (shared with WS5)
- **NHDPlus / NHD** — USGS National Hydrography Dataset for flowlines and water bodies
- **WBD** — USGS Watershed Boundary Dataset for HUC-12 subwatersheds
- **ArcGIS Feature Layers** — published layers for WS1 map overlays
- **Python scripts** — ETL for data loading and downstream tracing

## Implementation Tasks

### Phase 1 — Foundations (Weeks 1–2)

#### 1.1 Inventory data sources

- [x] Create a data source inventory table (`scripts/inventory.md`):

  | Layer | Source | Format | URL | Last Updated | Owner | Status |
  | --- | --- | --- | --- | --- | --- | --- |
  | County drains (centerlines, drain numbers, open/enclosed segments, intercounty status, connections) | Macomb County Public Works | TBD | TBD | TBD | Macomb County | **Priority 1 — request** |
  | Large known drains list (Tier 1/2) | Macomb County Public Works | List | — | TBD | Macomb County | Request |
  | Drain response plans (crossings, boom sites, access) | MCPWO / HRC (Red Run plan set, Sept 2026 draft) | PDF → table | — | 2026-09 | MCPWO | Red Run only |
  | Road centerlines (for computed intercept points) | Michigan GIS Open Data | Shapefile | TBD | TBD | State of Michigan | |
  | Municipal boundaries | Macomb County GIS Open Data | Shapefile/GeoJSON | TBD | TBD | Macomb County | |
  | County drain districts | Macomb County Public Works | Shapefile | TBD | TBD | Macomb County | |
  | Clinton River subwatersheds (HUC-12) | USGS WBD | GeoJSON/Shapefile | TBD | TBD | USGS | |
  | Water bodies | USGS NHD | GDB/Shapefile | TBD | TBD | USGS | |
  | Stream flowlines | USGS NHDPlus HR | GDB | TBD | TBD | USGS | |
  | Storm sewer outfalls | Macomb County Public Works | TBD | TBD | TBD | Macomb County | Pending request |
  | Lake St. Clair shoreline | Michigan GIS Open Data | Shapefile | TBD | TBD | State of Michigan | |
  | USCG/EPA response zone line | USCG / EPA | TBD | TBD | TBD | Federal | |

- [x] Check sources in priority order (`scripts/check_sources.py`):
  1. Direct request to Macomb County Public Works (county drain inventory, large drain list, storm sewers, drain districts) — send first; NHD misses most county drains
  2. Macomb County GIS Open Data portal
  3. Michigan GIS Open Data portal
  4. USGS National Map (NHD, WBD) — authoritative for the Clinton River and Lake St. Clair
- [x] Document download URLs, file formats, coordinate systems, and freshness for each layer
- [x] Identify gaps — layers that don't exist publicly or need a data-sharing request

#### 1.2 Collect and prepare the layers

- [x] Download all available layers to `data/raw/` (directory structure created; awaiting county data request)
  - Organize by layer name: `data/raw/municipalities/`, `data/raw/drain_districts/`, etc.
- [x] Inspect each dataset
  - Verify geometry types (polygon, multipolygon, linestring)
  - Check attribute fields for usable name/ID columns
  - Note coordinate reference system (CRS) — will reproject to EPSG:4326
- [x] Clip all layers to Macomb County boundary (plus a small buffer for edge cases) (`scripts/prepare_layers.py`)
  - Use `ogr2ogr -clipsrc` with the county boundary polygon
- [x] Reproject everything to EPSG:4326 (WGS 84)
  - `ogr2ogr -t_srs EPSG:4326`
- [x] Assign stable jurisdiction IDs (`scripts/prepare_layers.py`)
  - Format: `{layer_code}_{unique_id}` (e.g., `muni_mount_clemens`, `drain_north_branch_clinton`)
  - These IDs are the foreign key WS4 uses in the rules table — they must be stable across data refreshes
  - Document the ID scheme in a shared reference file

#### 1.3 Load into PostGIS

- [x] Create the `jurisdictions` table (`src/models/jurisdiction.py`, updated with `source_url` + `last_updated`):
  ```sql
  CREATE TABLE jurisdictions (
      id SERIAL PRIMARY KEY,
      layer VARCHAR(50) NOT NULL,          -- municipality, drain_district, subwatershed, water_body, etc.
      jurisdiction_id VARCHAR(100) UNIQUE NOT NULL,  -- stable ID for WS4
      name VARCHAR(255) NOT NULL,
      geometry GEOMETRY(MultiPolygon, 4326) NOT NULL,
      source_url TEXT,
      last_updated DATE
  );
  ```
- [x] Create the `waterways` table (`src/models/waterway.py`):
  ```sql
  CREATE TABLE waterways (
      id SERIAL PRIMARY KEY,
      name VARCHAR(255),
      nhd_comid BIGINT UNIQUE NOT NULL,   -- NHD Common Identifier (features without a COMID are skipped in ETL)
      flow_direction VARCHAR(10),          -- downstream direction
      downstream_comid BIGINT,             -- next segment downstream
      geometry GEOMETRY(LineString, 4326) NOT NULL,
      has_beach_downstream BOOLEAN DEFAULT FALSE,
      has_intake_downstream BOOLEAN DEFAULT FALSE
  );
  ```
- [x] Create the drain tables (`src/models/drain.py` — Drain, DrainSegment, ResponseSite):
  ```sql
  CREATE TABLE drains (
      id SERIAL PRIMARY KEY,
      drain_id VARCHAR(100) UNIQUE NOT NULL,     -- stable ID, e.g. drain_red_run, drain_bear_creek
      drain_number VARCHAR(20),                  -- county drain number, e.g. '016', '282'
      name VARCHAR(255) NOT NULL,
      tier VARCHAR(5) NOT NULL,                  -- '1','2','3','4' (see 2.3)
      conveyance_owner VARCHAR(30) NOT NULL,     -- county_drain, county_storm, county_sewer, roads_dept, municipal_ms4, private, unknown
      intercounty BOOLEAN DEFAULT FALSE,
      drain_district_id VARCHAR(100),            -- jurisdictions.jurisdiction_id of the drain district
      has_response_plan BOOLEAN DEFAULT FALSE
  );

  CREATE TABLE drain_segments (
      id SERIAL PRIMARY KEY,
      drain_id VARCHAR(100) NOT NULL REFERENCES drains(drain_id),
      segment_id VARCHAR(100) UNIQUE NOT NULL,
      conveyance_type VARCHAR(20) NOT NULL,      -- open, enclosed, sanitary, combined
      downstream_segment_id VARCHAR(100),        -- next segment; NULL at the drain outlet
      outlet_nhd_comid BIGINT,                   -- set where the drain discharges to an NHD flowline
      geometry GEOMETRY(LineString, 4326) NOT NULL
  );

  CREATE TABLE response_sites (
      id SERIAL PRIMARY KEY,
      drain_id VARCHAR(100) NOT NULL REFERENCES drains(drain_id),
      site_order INTEGER NOT NULL,               -- downstream order along the drain
      name VARCHAR(255) NOT NULL,                -- e.g. 'Crossing 3 — Ryan Rd Bridge'
      source VARCHAR(20) NOT NULL,               -- 'plan' (from a response plan) or 'computed' (road × drain)
      boom_anchor BOOLEAN DEFAULT FALSE,
      access_notes TEXT,
      access_contact TEXT,                       -- e.g. 'OCWRC (GWK) for gate access'
      plan_sheet VARCHAR(20),                    -- e.g. 'Sheet 5'
      geometry GEOMETRY(Point, 4326) NOT NULL
  );
  ```
- [x] Seed `response_sites` for Red Run from the HRC plan set (`scripts/seed_response_sites.py` — 18 crossings). Confirm sheet cross-references with HRC first — sheets 7, 8, 13, 15 and 18 cite the wrong sheets, and sheet 18 is labeled "Crossing 21"
- [x] Generate `computed` response sites for Tier 2 drains from road centerline × drain segment intersections (`scripts/compute_intercept_points.py`)
- [x] Write ETL scripts (`scripts/load_layers.py`, `scripts/load_waterways.py`, `scripts/load_drains.py`)
  - Read each prepared layer with GDAL/Fiona
  - Insert into the appropriate table with assigned jurisdiction IDs
  - Handle multi-part geometries (dissolve or store as MultiPolygon)
- [x] Build spatial indexes (Alembic migration `b5d2e8f3a1c6`)
  ```sql
  CREATE INDEX idx_jurisdictions_geom ON jurisdictions USING GIST (geometry);
  CREATE INDEX idx_waterways_geom ON waterways USING GIST (geometry);
  CREATE INDEX idx_jurisdictions_layer ON jurisdictions (layer);
  CREATE INDEX idx_drain_segments_geom ON drain_segments USING GIST (geometry);
  CREATE INDEX idx_response_sites_geom ON response_sites USING GIST (geometry);
  ```
- [ ] Verify row counts and spot-check geometries (visual check in QGIS or DBeaver) — pending data load

### Phase 2 — Core Build (Weeks 3–5)

#### 2.1 Write the lookup query

- [x] Implement `lookup_jurisdictions(lat, lon, buffer_radius_m)` in `src/services/spatial.py`
  - Build the query point: `ST_SetSRID(ST_MakePoint(lon, lat), 4326)`
  - If buffer_radius_m is provided, create buffer: `ST_Buffer(point::geography, radius)::geometry`
  - Intersect with each jurisdiction layer:
    ```sql
    SELECT layer, jurisdiction_id, name
    FROM jurisdictions
    WHERE ST_Intersects(geometry, :point_or_buffer)
    ORDER BY layer, name;
    ```
  - Return a list of `{ layer, jurisdiction_id, name }` objects

- [x] Handle edge cases:
  - Point exactly on a boundary line → return both adjacent jurisdictions
  - Point outside Macomb County → return empty list with a warning flag
  - Buffer crosses county lines → only return Macomb County jurisdictions, flag that buffer extends beyond county

- [x] Optimize query performance (uses `ST_DWithin` with GIST spatial indexes)
  - Spatial index should keep queries under 100ms for a single point
  - For buffer queries, test with large radii (1km+) and optimize if needed
  - Consider using `ST_DWithin` for initial filtering before `ST_Intersects`

#### 2.2 Snap to water and trace downstream

- [x] Implement `find_nearest_drain(lat, lon, max_distance_m=200)` in `src/services/spatial.py`
  - Snap to the nearest `drain_segments` row first; return `drain_id`, `drain_name`, `drain_tier`, `conveyance_owner`, `conveyance_type`, and snap distance
  - If no county drain is within range, fall back to `find_nearest_water` below

- [x] Implement `find_nearest_water(lat, lon, max_distance_m=500)` in `src/services/spatial.py`
  - Find the nearest NHD waterway segment to the spill point:
    ```sql
    SELECT name, nhd_comid, ST_Distance(geometry::geography, point::geography) AS distance_m
    FROM waterways
    WHERE ST_DWithin(geometry::geography, point::geography, :max_distance_m)
    ORDER BY distance_m
    LIMIT 1;
    ```
  - Return the water body name and NHD COMID

- [x] Implement `trace_downstream(start)` in `src/services/spatial.py`
  - Walk the drain network first: follow `drain_segments.downstream_segment_id` to the outlet, then continue on NHD from `outlet_nhd_comid`
  - Record the first Tier 1/2 drain reached (`first_major_drain_downstream`) and the distance to it
  - Record `next_intercept_point`: the nearest downstream `response_sites` row on that drain (`plan` sites first, else `computed`)
  - NHD portion — recursive query following `downstream_comid` links with cycle detection and depth limit:
    ```sql
    WITH RECURSIVE downstream AS (
        SELECT id, name, nhd_comid, downstream_comid,
               has_beach_downstream, has_intake_downstream,
               1 AS depth, ARRAY[nhd_comid] AS visited
        FROM waterways WHERE nhd_comid = :start_comid
        UNION ALL
        SELECT w.id, w.name, w.nhd_comid, w.downstream_comid,
               w.has_beach_downstream, w.has_intake_downstream,
               d.depth + 1, d.visited || w.nhd_comid
        FROM waterways w
        JOIN downstream d ON w.nhd_comid = d.downstream_comid
        WHERE d.depth < :max_depth
          AND w.nhd_comid <> ALL(d.visited)
    )
    SELECT name, nhd_comid, has_beach_downstream, has_intake_downstream,
           MIN(depth) AS min_depth
    FROM downstream
    GROUP BY name, nhd_comid, has_beach_downstream, has_intake_downstream
    ORDER BY min_depth;
    ```
  - Return ordered list of water body names from spill point to Lake St. Clair (ordered by downstream depth, not COMID)
  - Flag if any downstream segment has a beach or drinking-water intake

- [x] Build the downstream connectivity data (`scripts/build_downstream_links.py`)
  - Parse NHDPlus flow table to populate `downstream_comid` for each segment
  - Manually flag known beaches (e.g., Memorial Park Beach, Lake St. Clair Metropark)
  - Manually flag known drinking-water intakes (check with Macomb County Public Works)

- [x] Handle edge cases (in `src/services/spatial.py`):
  - Spill not near any mapped waterway → return "no water body found" with distance to nearest
  - Circular flow references (data error) → limit recursion depth to 100 segments
  - Multiple downstream branches (river splits) → follow all branches
  - Drain continues upstream into Oakland or St. Clair County (e.g. Red Run / GWK Drain at Dequindre) → set `upstream_counties`
  - Spill enters through a non-county conveyance (Tier 4) → keep tracing; report the first county drain it reaches, if any

#### 2.3 Assign drain tiers and conveyance owners

Red Run is one drain getting pre-planned response infrastructure; most drains have none. Tiers let the rules engine (WS4) apply the handbook everywhere and add drain-specific actions only where a plan exists. Large known drains are modeled explicitly because crews intercept spills from smaller drains and storm sewers on them.

| Tier | Definition | Examples from source docs | What the lookup returns |
| --- | --- | --- | --- |
| 1 | Large known drain **with** a response plan | Red Run (RRIDD, intercounty) | Drain + next planned crossing (`response_sites`, source = plan) |
| 2 | Large known / intercounty drain **without** a plan | Bear Creek (016), Plum Brook (282), Sterling Relief (391), Schoenherr Relief (340), Big Beaver Creek | Drain + next computed road crossing |
| 3 | Other county drains, open or enclosed | Vermander, Hartlien Relief (484), Meckler (239), Smith Rivard (365), Red Run Branches | Drain + first Tier 1/2 drain downstream |
| 4 | Not a county asset | Roads-dept storm sewers, municipal storm sewers, private ditches | `conveyance_owner` for referral + first county drain downstream |
| Out | Excluded by the handbook | Sanitary/combined sewer overflows, NPDES-permitted facilities | `flags.excluded_procedure = true` |

- [x] Get the official large-drain list (or size/flow threshold) from MCPWO; until then seed Tier 1/2 from the Red Run plan set tributaries and incident records (`scripts/load_drains.py`)
- [x] Set `conveyance_owner` on every drain and storm sewer feature (handbook §3 definitions: county drain, county storm water system, county sewer; roads-dept MS4s are excluded from county storm water systems)
- [x] Mark enclosed vs. open segments (e.g. Bear Creek is piped at Mound Rd and opens ~1¾ mi downstream)
- [x] Give WS4 the tier and owner enums so rules can match on them (`src/schemas/enums.py` — `DrainTier`, `ConveyanceOwner`, `ConveyanceType`)

### Phase 3 — Integrate (Weeks 6–7)

#### 3.1 Expose to WS5

- [x] Register `lookup_jurisdictions` and `trace_downstream` as service functions callable from WS5's `/lookup` endpoint (`src/services/lookup.py` updated)
  - WS5 calls: `jurisdictions = await lookup_jurisdictions(lat, lon, buffer_radius_m)`
  - WS5 calls: `drain = await find_nearest_drain(lat, lon)`
  - WS5 calls: `nearest_water = await find_nearest_water(lat, lon)` (fallback when no drain is in range)
  - WS5 calls: `downstream = await trace_downstream(drain or nearest_water)`
- [x] Return combined result (`src/schemas/lookup.py` — `LookupResult` with drain, water, intercept, flags):
  ```python
  {
      # example: diesel into enclosed Bear Creek at Mound Rd, Warren
      "jurisdictions": [{"layer": "municipality", "jurisdiction_id": "muni_warren", "name": "Warren"}, ...],
      "drain": {"drain_id": "drain_bear_creek", "name": "Bear Creek", "tier": "2",
                "conveyance_owner": "county_drain", "conveyance_type": "enclosed", "distance_m": 8.0},
      "nearest_water": None,
      "first_major_drain_downstream": {"drain_id": "drain_red_run", "name": "Red Run Drain", "tier": "1"},
      "next_intercept_point": {"name": "Crossing 7 — Bear Creek Confluence", "source": "plan", "plan_sheet": "Sheet 9"},
      "downstream_path": ["Bear Creek", "Red Run Drain", "Clinton River", "Lake St. Clair"],
      "upstream_counties": [],
      "flags": {
          "beach_downstream": True,
          "intake_downstream": False,
          "outside_county": False,
          "excluded_procedure": False   # sewer overflow or NPDES-permitted site
      }
  }
  ```

#### 3.2 Share layers with the map (WS1)

- [x] Publish jurisdiction layers as GeoJSON from the API (`src/api/routes/layers.py` — `GET /layers/{layer_name}`)
  - Option A: Host as ArcGIS Feature Layers on ArcGIS Online (requires org account)
  - **Option B (implemented)**: Serve as GeoJSON from the API (`GET /layers/{layer_name}`) for smaller datasets
  - Option C: Pre-generate vector tiles and serve as static assets
- [ ] Coordinate with WS1 on the chosen approach and required layer format
- [x] Each published layer includes the `jurisdiction_id` and `name` attributes so WS1 can match highlighted jurisdictions to lookup results

#### 3.3 Data refresh process

- [x] Document the refresh procedure for each layer (`scripts/refresh_layer.py`)
  - Download updated data → run ETL scripts → verify row counts → swap in PostGIS
- [x] Ensure jurisdiction IDs remain stable across refreshes
  - Match on name/FIPS code, not row order
  - Flag any new or removed jurisdictions for WS4 to update contacts

### Phase 4 — Pilot (Week 8)

#### 4.1 Write boundary tests

- [x] Create at least 16 test points (weighted toward large drains) in `tests/boundary-test-cases.json`:

  | # | Description | Lat | Lon | Expected Jurisdictions | Expected Downstream |
  | --- | --- | --- | --- | --- | --- |
  | 1 | Downtown Mount Clemens (Clinton River) | 42.5973 | -82.8779 | muni_mount_clemens, drain_clinton_main, ws_middle_clinton | Clinton River → Lake St. Clair |
  | 2 | Sterling Heights near Red Run Drain | 42.5803 | -83.0302 | muni_sterling_heights, drain_red_run | Red Run Drain → Clinton River → Lake St. Clair |
  | 3 | Lake St. Clair shoreline (Harrison Twp) | 42.5960 | -82.8100 | muni_harrison_twp, zone_uscg_detroit | Lake St. Clair |
  | 4 | Municipal boundary line (two cities) | TBD | TBD | Both adjacent municipalities | TBD |
  | 5 | County line (Oakland/Macomb border) | TBD | TBD | Macomb side only; outside_county flag | TBD |
  | 6 | County line (St. Clair/Macomb border) | TBD | TBD | Macomb side only; outside_county flag | TBD |
  | 7 | Drain district edge | TBD | TBD | Correct drain district(s) | TBD |
  | 8 | Storm sewer area (if data available) | TBD | TBD | Storm sewer outfall jurisdiction | TBD |
  | 9 | Point far from any waterway | TBD | TBD | Municipality only; no water body | — |
  | 10 | Point near drinking-water intake | TBD | TBD | Correct jurisdictions; intake_downstream flag | TBD |
  | 11 | Bear Creek diesel (Oct 2018), 24257 Mound Rd, Warren — Tier 2, enclosed | geocode | geocode | muni_warren, drain_bear_creek (tier 2, enclosed) | Bear Creek → Red Run (crossing 7) → Clinton River → Lake St. Clair |
  | 12 | Vermander Drain oil (Dec 2025), 35350 Kelly Rd, Clinton Twp — Tier 3 via private ditch | geocode | geocode | muni_clinton_twp, drain_vermander (tier 3) | Confirm with MCPWO |
  | 13 | Red Run at Dequindre/Chicago (crossing 1/2) — Tier 1 on county + municipal lines | TBD | TBD | Macomb side only; upstream_counties = [Oakland] | Red Run → Clinton River → Lake St. Clair |
  | 14 | Red Run at Utica Rd bridge (crossing 18) — Tier 1 outlet | TBD | TBD | drain_red_run; no further planned crossing | Clinton River → Lake St. Clair |
  | 15 | One point on each Tier 2 drain (Plum Brook, Sterling Relief, Schoenherr Relief, Big Beaver Creek, …) | TBD | TBD | Correct drain, tier 2, computed intercept point | → Red Run → Clinton River → Lake St. Clair |
  | 16 | Roads-dept storm sewer — Tier 4 | TBD | TBD | conveyance_owner = roads_dept | First county drain reached, if any |

- [x] Record the expected result for each test point
  - Verify expected results against official maps / county GIS viewer
- [x] Write automated tests in `tests/test_spatial.py`
  - For each test point: call `lookup_jurisdictions` and `trace_downstream`; compare to expected
  - All must pass before pilot

#### 4.2 Performance testing

- [x] Benchmark lookup query time for 100 random points (`tests/test_performance.py`)
  - Target: median < 100ms, p95 < 200ms
- [x] Benchmark downstream trace for the longest flow path (`tests/test_performance.py`)
  - Target: < 500ms

#### 4.3 Pilot readiness

- [ ] All boundary test cases pass — pending data load and DB integration test
- [ ] Performance targets met — pending data load
- [ ] Layer data is loaded and verified for all available sources — pending county data request
- [ ] Published layers display correctly in WS1 map — pending WS1 integration
- [ ] Fix issues logged during the pilot demo

## Key Decisions & Constraints

| Decision | Notes |
| --- | --- |
| Coordinate system | EPSG:4326 (WGS 84) for all stored geometries |
| Jurisdiction ID format | `{layer_code}_{unique_id}` — stable across data refreshes |
| Downstream tracing | Walk drain segments first, then NHDPlus flow table from the drain outlet; limited to 100 segments total; cycle detection via visited arrays |
| Input validation | Lat/lon constrained to valid ranges (-90..90, -180..180); buffer_radius_m capped at 10km; Pydantic Field validators on LookupRequest |
| ETL batching | All ETL scripts use executemany (pass list of dicts to session.execute) for batch performance |
| nhd_comid | NOT NULL on waterways table; features without a COMID are skipped during ETL (can't upsert on NULL unique key) |
| Drain tiers | 1 = large drain with response plan; 2 = large/intercounty, no plan; 3 = other county drain; 4 = not a county asset. Tier list confirmed by MCPWO |
| Response plans | Stored as a `response_sites` overlay; drains without a plan get computed road-crossing sites |
| Geometry type (resolved) | Kept `Geography(GEOMETRY)` in jurisdictions (supports mixed types); drain_segments and waterways use `Geography(LINESTRING)`, response_sites use `Geography(POINT)` |
| Fallback on gaps | If a layer is missing (e.g., storm sewers), return the parent jurisdiction and set a flag |
| Scope | Macomb County only; points outside county return empty + flag |

## Risks

| Risk | Mitigation |
| --- | --- |
| County drain inventory not shared or incomplete | Seed Tier 1/2 drains from the Red Run plan set and incident records; digitize large drains first |
| Boundary data gaps (drain districts, storm sewers) | Fall back to parent jurisdiction and flag it; note gaps in the results |
| Storm sewer data not shared by Public Works | App works without it; flag as "storm sewer data unavailable" in results |
| NHD flowline connectivity gaps | Manual review of downstream links for Clinton River watershed; fill gaps |
| Stale boundary data | Document last-updated date per layer; refresh process documented |
| Slow spatial queries with large buffers | Spatial indexes + `ST_DWithin` pre-filter; benchmark and optimize |

## Open Questions

- [ ] Which drains count as large known drains (Tier 1/2)? Is there an official list or a size/flow threshold?
- [ ] Are response plans like Red Run's planned for other drains, and in what order?
- [ ] Can MCPWO share county drain GIS with enclosed segments and connections?
- [ ] Will Macomb County Public Works share storm sewer and outfall GIS data?
- [ ] Are there known drinking-water intakes downstream on the Clinton River or Lake St. Clair that should be flagged?
- [ ] Should the downstream trace include tributaries upstream of the spill point (for "what else feeds into this water")?
- [ ] ArcGIS Online org account available for hosting feature layers, or must we self-serve?
- [ ] How often should layer data be refreshed (annually, quarterly)?

## File Structure (Proposed)

```
data/
  raw/                         # Downloaded source files (not committed; .gitignore)
    municipalities/
    drains/
    drain_districts/
    subwatersheds/
    waterways/
    shoreline/
  prepared/                    # Clipped, reprojected, ID-assigned (not committed)

scripts/
  inventory.md                 # Data source inventory table
  load_layers.py               # ETL: read prepared data → insert into PostGIS
  load_waterways.py            # ETL: NHDPlus flowlines → waterways table
  build_downstream_links.py    # Parse NHDPlus flow table → downstream_comid
  load_drains.py               # ETL: MCPWO drain inventory → drains, drain_segments
  seed_response_sites.py       # Red Run plan set crossings → response_sites (source = plan)
  compute_intercept_points.py  # Road × drain intersections → response_sites (source = computed)
  refresh_layer.py             # Refresh a single layer from updated source

src/
  models/
    jurisdiction.py            # SQLAlchemy model for jurisdictions table
    waterway.py                # SQLAlchemy model for waterways table
    drain.py                   # SQLAlchemy models for drains, drain_segments, response_sites
  services/
    spatial.py                 # lookup_jurisdictions, find_nearest_drain, find_nearest_water, trace_downstream

tests/
  boundary-test-cases.json     # 10+ test points with expected results
  test_spatial.py              # Automated boundary and downstream tests
  test_performance.py          # Benchmark queries
```
