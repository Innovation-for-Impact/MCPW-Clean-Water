# WS3 Data Source Inventory

Last updated: 2026-10-15

## Layer Inventory

| # | Layer | Source | Format | URL | CRS | Last Updated | Owner | Priority | Status |
|---|-------|--------|--------|-----|-----|--------------|-------|----------|--------|
| 1 | County drains (centerlines, drain numbers, open/enclosed segments, intercounty status, connections) | Macomb County Public Works | TBD (Shapefile or GDB expected) | Request pending | TBD | TBD | Macomb County | **P1** | **Request sent** |
| 2 | Large known drains list (Tier 1/2) | Macomb County Public Works | List / spreadsheet | N/A — internal list | N/A | TBD | Macomb County | **P1** | **Request sent** |
| 3 | Drain response plans (crossings, boom sites, access) | MCPWO / HRC (Red Run plan set, Sept 2026 draft) | PDF tables → CSV | N/A — provided by MCPWO | N/A | 2026-09 | MCPWO | **P1** | Red Run only; digitize from plan set |
| 4 | Municipal boundaries | Macomb County GIS Open Data | Shapefile / GeoJSON | https://gis-macomb.opendata.arcgis.com/ | EPSG:2253 (MI South) expected | TBD | Macomb County | **P1** | To download |
| 5 | County drain districts | Macomb County Public Works | Shapefile | Request pending | TBD | TBD | Macomb County | **P1** | **Request sent** |
| 6 | Road centerlines | Michigan GIS Open Data (Michigan Geographic Framework) | Shapefile | https://gis-michigan.opendata.arcgis.com/ | EPSG:3078 (MI GeoRef) expected | TBD | State of Michigan | P2 | To download |
| 7 | Clinton River subwatersheds (HUC-12) | USGS Watershed Boundary Dataset (WBD) | GeoJSON / Shapefile | https://apps.nationalmap.gov/downloader/ | EPSG:4326 | TBD | USGS | P2 | To download |
| 8 | Water bodies (lakes, ponds) | USGS National Hydrography Dataset (NHD) | GDB / Shapefile | https://apps.nationalmap.gov/downloader/ | EPSG:4326 | TBD | USGS | P2 | To download |
| 9 | Stream flowlines (with downstream connectivity) | USGS NHDPlus High Resolution | GDB | https://www.usgs.gov/national-hydrography/nhdplus-high-resolution | EPSG:4326 | TBD | USGS | **P1** | To download |
| 10 | Storm sewer outfalls | Macomb County Public Works | TBD | Request pending | TBD | TBD | Macomb County | P3 | **Request sent** — may not be shared |
| 11 | Lake St. Clair shoreline | Michigan GIS Open Data | Shapefile | https://gis-michigan.opendata.arcgis.com/ | TBD | TBD | State of Michigan | P2 | To download |
| 12 | USCG/EPA response zone line (federal jurisdiction boundary on Lake St. Clair) | USCG / EPA | TBD | TBD | TBD | TBD | Federal | P3 | Research needed |

## Priority Key

- **P1** — Required for Phase 1 load and core spatial queries (drain inventory, municipalities, NHDPlus)
- **P2** — Required for Phase 2 downstream tracing and subwatershed assignment
- **P3** — Nice to have; app functions without it (storm sewers, federal zone line)

## Data Request Log

| Date | Recipient | Layers Requested | Method | Response |
|------|-----------|------------------|--------|----------|
| TBD | Macomb County Public Works | County drain inventory (GIS), large drain list, drain districts, storm sewer outfalls | Email | Pending |
| TBD | MCPWO | Red Run response plan crossings (tabular, with lat/lon or sheet cross-refs) | Meeting / email | Red Run plan set received (Sept 2026 draft) |

## Notes

- All layers will be reprojected to **EPSG:4326 (WGS 84)** before loading into PostGIS.
- All layers will be clipped to Macomb County boundary + 500m buffer.
- Jurisdiction IDs follow the format `{layer_code}_{unique_id}` (e.g., `muni_mount_clemens`, `drain_red_run`). These are stable across data refreshes and serve as the foreign key for WS4 rules.
- NHD may miss most county drains — the county drain inventory from Public Works is the authoritative source for drain centerlines, tiers, and conveyance ownership.
