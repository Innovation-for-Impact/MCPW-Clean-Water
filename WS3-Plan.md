# WS3 — Jurisdiction Layers & Spatial Query: Implementation Plan

## Goal

For any point in Macomb County, return every jurisdiction and water body the spill affects.

## Done When

The lookup returns the correct municipality, drain district, subwatershed, receiving water, and downstream path for every boundary test case.

## Dependencies

| Direction | Workstream | What |
| --- | --- | --- |
| Needs from | — | External GIS data sources (Macomb County, Michigan, USGS) |
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

- [ ] Create a data source inventory table:

  | Layer | Source | Format | URL | Last Updated | Owner | Status |
  | --- | --- | --- | --- | --- | --- | --- |
  | Municipal boundaries | Macomb County GIS Open Data | Shapefile/GeoJSON | TBD | TBD | Macomb County | |
  | County drain districts | Macomb County Public Works | Shapefile | TBD | TBD | Macomb County | |
  | Clinton River subwatersheds (HUC-12) | USGS WBD | GeoJSON/Shapefile | TBD | TBD | USGS | |
  | Water bodies | USGS NHD | GDB/Shapefile | TBD | TBD | USGS | |
  | Stream flowlines | USGS NHDPlus HR | GDB | TBD | TBD | USGS | |
  | Storm sewer outfalls | Macomb County Public Works | TBD | TBD | TBD | Macomb County | Pending request |
  | Lake St. Clair shoreline | Michigan GIS Open Data | Shapefile | TBD | TBD | State of Michigan | |
  | USCG/EPA response zone line | USCG / EPA | TBD | TBD | TBD | Federal | |

- [ ] Check sources in priority order:
  1. Macomb County GIS Open Data portal
  2. Michigan GIS Open Data portal
  3. USGS National Map (NHD, WBD)
  4. Direct request to Macomb County Public Works (storm sewers, drain districts)
- [ ] Document download URLs, file formats, coordinate systems, and freshness for each layer
- [ ] Identify gaps — layers that don't exist publicly or need a data-sharing request

#### 1.2 Collect and prepare the layers

- [ ] Download all available layers to `data/raw/`
  - Organize by layer name: `data/raw/municipalities/`, `data/raw/drain_districts/`, etc.
- [ ] Inspect each dataset
  - Verify geometry types (polygon, multipolygon, linestring)
  - Check attribute fields for usable name/ID columns
  - Note coordinate reference system (CRS) — will reproject to EPSG:4326
- [ ] Clip all layers to Macomb County boundary (plus a small buffer for edge cases)
  - Use `ogr2ogr -clipsrc` with the county boundary polygon
- [ ] Reproject everything to EPSG:4326 (WGS 84)
  - `ogr2ogr -t_srs EPSG:4326`
- [ ] Assign stable jurisdiction IDs
  - Format: `{layer_code}_{unique_id}` (e.g., `muni_mount_clemens`, `drain_north_branch_clinton`)
  - These IDs are the foreign key WS4 uses in the rules table — they must be stable across data refreshes
  - Document the ID scheme in a shared reference file

#### 1.3 Load into PostGIS

- [ ] Create the `jurisdictions` table (coordinate with WS5 on schema):
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
- [ ] Create the `waterways` table for flowlines:
  ```sql
  CREATE TABLE waterways (
      id SERIAL PRIMARY KEY,
      name VARCHAR(255),
      nhd_comid BIGINT UNIQUE,            -- NHD Common Identifier
      flow_direction VARCHAR(10),          -- downstream direction
      downstream_comid BIGINT,             -- next segment downstream
      geometry GEOMETRY(LineString, 4326) NOT NULL,
      has_beach_downstream BOOLEAN DEFAULT FALSE,
      has_intake_downstream BOOLEAN DEFAULT FALSE
  );
  ```
- [ ] Write ETL scripts in `scripts/load_layers.py`
  - Read each prepared layer with GDAL/Fiona
  - Insert into the appropriate table with assigned jurisdiction IDs
  - Handle multi-part geometries (dissolve or store as MultiPolygon)
- [ ] Build spatial indexes
  ```sql
  CREATE INDEX idx_jurisdictions_geom ON jurisdictions USING GIST (geometry);
  CREATE INDEX idx_waterways_geom ON waterways USING GIST (geometry);
  CREATE INDEX idx_jurisdictions_layer ON jurisdictions (layer);
  ```
- [ ] Verify row counts and spot-check geometries (visual check in QGIS or DBeaver)

### Phase 2 — Core Build (Weeks 3–5)

#### 2.1 Write the lookup query

- [ ] Implement `lookup_jurisdictions(lat, lon, buffer_radius_m)` in `src/services/spatial.py`
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

- [ ] Handle edge cases:
  - Point exactly on a boundary line → return both adjacent jurisdictions
  - Point outside Macomb County → return empty list with a warning flag
  - Buffer crosses county lines → only return Macomb County jurisdictions, flag that buffer extends beyond county

- [ ] Optimize query performance
  - Spatial index should keep queries under 100ms for a single point
  - For buffer queries, test with large radii (1km+) and optimize if needed
  - Consider using `ST_DWithin` for initial filtering before `ST_Intersects`

#### 2.2 Snap to water and trace downstream

- [ ] Implement `find_nearest_water(lat, lon, max_distance_m=500)` in `src/services/spatial.py`
  - Find the nearest waterway segment to the spill point:
    ```sql
    SELECT name, nhd_comid, ST_Distance(geometry::geography, point::geography) AS distance_m
    FROM waterways
    WHERE ST_DWithin(geometry::geography, point::geography, :max_distance_m)
    ORDER BY distance_m
    LIMIT 1;
    ```
  - Return the water body name and NHD COMID

- [ ] Implement `trace_downstream(start_comid)` in `src/services/spatial.py`
  - Recursive query following `downstream_comid` links:
    ```sql
    WITH RECURSIVE downstream AS (
        SELECT id, name, nhd_comid, downstream_comid, has_beach_downstream, has_intake_downstream
        FROM waterways WHERE nhd_comid = :start_comid
        UNION ALL
        SELECT w.id, w.name, w.nhd_comid, w.downstream_comid, w.has_beach_downstream, w.has_intake_downstream
        FROM waterways w
        JOIN downstream d ON w.nhd_comid = d.downstream_comid
    )
    SELECT DISTINCT name, nhd_comid, has_beach_downstream, has_intake_downstream
    FROM downstream;
    ```
  - Return ordered list of water body names from spill point to Lake St. Clair
  - Flag if any downstream segment has a beach or drinking-water intake

- [ ] Build the downstream connectivity data
  - Parse NHDPlus flow table to populate `downstream_comid` for each segment
  - Manually flag known beaches (e.g., Memorial Park Beach, Lake St. Clair Metropark)
  - Manually flag known drinking-water intakes (check with Macomb County Public Works)

- [ ] Handle edge cases:
  - Spill not near any mapped waterway → return "no water body found" with distance to nearest
  - Circular flow references (data error) → limit recursion depth to 100 segments
  - Multiple downstream branches (river splits) → follow all branches

### Phase 3 — Integrate (Weeks 6–7)

#### 3.1 Expose to WS5

- [ ] Register `lookup_jurisdictions` and `trace_downstream` as service functions callable from WS5's `/lookup` endpoint
  - WS5 calls: `jurisdictions = await lookup_jurisdictions(lat, lon, buffer_radius_m)`
  - WS5 calls: `nearest_water = await find_nearest_water(lat, lon)`
  - WS5 calls: `downstream = await trace_downstream(nearest_water.nhd_comid)`
- [ ] Return combined result:
  ```python
  {
      "jurisdictions": [{"layer": "municipality", "jurisdiction_id": "muni_mount_clemens", "name": "Mount Clemens"}, ...],
      "nearest_water": {"name": "Clinton River", "distance_m": 45.2},
      "downstream_path": ["Clinton River", "Lake St. Clair"],
      "flags": {
          "beach_downstream": True,
          "intake_downstream": False,
          "outside_county": False
      }
  }
  ```

#### 3.2 Share layers with the map (WS1)

- [ ] Publish jurisdiction layers as ArcGIS-compatible sources for WS1
  - Option A: Host as ArcGIS Feature Layers on ArcGIS Online (requires org account)
  - Option B: Serve as GeoJSON from the API (`GET /layers/{layer_name}`) for smaller datasets
  - Option C: Pre-generate vector tiles and serve as static assets
- [ ] Coordinate with WS1 on the chosen approach and required layer format
- [ ] Each published layer must include the `jurisdiction_id` and `name` attributes so WS1 can match highlighted jurisdictions to lookup results

#### 3.3 Data refresh process

- [ ] Document the refresh procedure for each layer
  - Download updated data → run ETL scripts → verify row counts → swap in PostGIS
- [ ] Ensure jurisdiction IDs remain stable across refreshes
  - Match on name/FIPS code, not row order
  - Flag any new or removed jurisdictions for WS4 to update contacts

### Phase 4 — Pilot (Week 8)

#### 4.1 Write boundary tests

- [ ] Create at least 10 test points in `tests/boundary-test-cases.json`:

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

- [ ] Record the expected result for each test point
  - Verify expected results against official maps / county GIS viewer
- [ ] Write automated tests in `tests/test_spatial.py`
  - For each test point: call `lookup_jurisdictions` and `trace_downstream`; compare to expected
  - All must pass before pilot

#### 4.2 Performance testing

- [ ] Benchmark lookup query time for 100 random points within Macomb County
  - Target: median < 100ms, p95 < 200ms
- [ ] Benchmark downstream trace for the longest flow path (county drain → Clinton River → Lake St. Clair)
  - Target: < 500ms

#### 4.3 Pilot readiness

- [ ] All boundary test cases pass
- [ ] Performance targets met
- [ ] Layer data is loaded and verified for all available sources
- [ ] Published layers display correctly in WS1 map
- [ ] Fix issues logged during the pilot demo

## Key Decisions & Constraints

| Decision | Notes |
| --- | --- |
| Coordinate system | EPSG:4326 (WGS 84) for all stored geometries |
| Jurisdiction ID format | `{layer_code}_{unique_id}` — stable across data refreshes |
| Downstream tracing | Recursive CTE on NHDPlus flow table; limited to 100 segments |
| Fallback on gaps | If a layer is missing (e.g., storm sewers), return the parent jurisdiction and set a flag |
| Scope | Macomb County only; points outside county return empty + flag |

## Risks

| Risk | Mitigation |
| --- | --- |
| Boundary data gaps (drain districts, storm sewers) | Fall back to parent jurisdiction and flag it; note gaps in the results |
| Storm sewer data not shared by Public Works | App works without it; flag as "storm sewer data unavailable" in results |
| NHD flowline connectivity gaps | Manual review of downstream links for Clinton River watershed; fill gaps |
| Stale boundary data | Document last-updated date per layer; refresh process documented |
| Slow spatial queries with large buffers | Spatial indexes + `ST_DWithin` pre-filter; benchmark and optimize |

## Open Questions

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
  refresh_layer.py             # Refresh a single layer from updated source

src/
  models/
    jurisdiction.py            # SQLAlchemy model for jurisdictions table
    waterway.py                # SQLAlchemy model for waterways table
  services/
    spatial.py                 # lookup_jurisdictions, find_nearest_water, trace_downstream

tests/
  boundary-test-cases.json     # 10+ test points with expected results
  test_spatial.py              # Automated boundary and downstream tests
  test_performance.py          # Benchmark queries
```
