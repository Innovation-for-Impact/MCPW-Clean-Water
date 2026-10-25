# WS3 — Data Source Inventory

Last updated: 2026-10-25 (URLs verified against macomb_gis_data_sources.xlsx; HTTP checks 2026-10-22 — 12/13 return 200)

## Layer Inventory

| # | Layer | Source | Format | URL | CRS | Owner | Status |
|---|-------|--------|--------|-----|-----|-------|--------|
| 1 | Municipal boundaries (Minor Civil Divisions) | State of Michigan (DTMB/CSS) | Shapefile, GeoJSON, FileGDB | [Hub page](https://gis-michigan.opendata.arcgis.com/datasets/Michigan::minor-civil-divisions-cities-townships-/about) / [REST](https://gisagocss.state.mi.us/arcgis/rest/services/OpenData/michigan_geographic_framework/MapServer/2) | NAD83 / EPSG:3078 | State of Michigan | **Verified** — clip to Macomb County (FIPS 099) |
| 2 | County boundary (for clipping) | State of Michigan (DTMB/CSS) | Shapefile, GeoJSON, FileGDB | [Hub page](https://gis-michigan.opendata.arcgis.com/datasets/county-boundaries) / [REST](https://gisagocss.state.mi.us/arcgis/rest/services/OpenData/michigan_geographic_framework/MapServer/0) | NAD83 / EPSG:4269 | State of Michigan | **Verified** |
| 3 | Lake St. Clair shoreline | State of Michigan (DTMB/CSS) | Polygon layer | [REST](https://gisagocss.state.mi.us/arcgis/rest/services/OpenData/hydro/MapServer/13) | NAD83 | State of Michigan | **Corrected** — original great-lakes-shoreline slug was wrong |
| 4 | Clinton River subwatersheds (HUC-12) | USGS WBD | GeoJSON via REST | [REST query](https://hydro.nationalmap.gov/arcgis/rest/services/wbd/MapServer/6/query?where=HUC12+LIKE+%2704090003%25%27&outFields=*&f=geojson) | NAD83 | USGS | **Loaded** — 21 subwatersheds clipped to county, automated via `download_layers.py` |
| 5 | Water bodies + stream flowlines | USGS NHDPlus HR | FileGDB | [S3 direct](https://prd-tnm.s3.amazonaws.com/StagedProducts/Hydrography/NHDPlusHR/VPU/Current/GDB/NHDPLUS_H_0409_HU4_GDB.zip) | NAD83 | USGS | **Loaded** — 1,917 flowlines clipped to county, 1,889 with downstream links, automated via `download_layers.py` + `load_waterways.py` |
| 6 | County drain districts | Macomb County Public Works | TBD (vector data unconfirmed) | [Drain maps (PDF/interactive)](https://macombgov.org/departments/public-works/public-works-resources/macomb-county-drain-maps) / Contact: public.works@macombgov.org, 586-469-5325 | TBD | Macomb County | **Pending** — 475 drains viewable; check for REST feature service before requesting |
| 7 | Storm sewer outfalls | Macomb County Public Works | TBD | Contact: public.works@macombgov.org, 586-469-5325 | TBD | Macomb County | **Pending request** |
| 8 | USCG/EPA response zone line | USCG / EPA | TBD | TBD | TBD | Federal | **Unknown** |
| 9 | EGLE environmental data (intakes, NPDES, Part 201) | Michigan EGLE | REST service | [EGLE Hub](https://gis-egle.hub.arcgis.com/) / [RRD REST](https://gisagoegle.state.mi.us/arcgis/rest/services/EGLE/RRDOpenData/MapServer) | TBD | EGLE | **Verified** — Hub returns 200; RRD REST drops automated connections (works in browser); intake/NPDES layers not individually confirmed yet |

## HUC Reference — Clinton River Watershed

| Level | Code | Name |
|-------|------|------|
| HUC-4 (Subregion) | 0409 | Lake St. Clair |
| HUC-8 (Subbasin) | 04090003 | Clinton River |
| HUC-10/12 | nested within 04090003 | North Branch, Red Run, Middle Branch, etc. |

## Macomb County GIS Portals

| Portal | URL | Notes |
|--------|-----|-------|
| County GIS portal | https://gis.macombgov.org | Public; blocks bots; some layers org-only |
| Open Data Hub (MCMAP) | https://macomb-county-open-data-portal-mcmap.hub.arcgis.com | **Corrected** — original `data-macomb.opendata.arcgis.com` was not real |

## URL Corrections from Verification

| Original URL | Issue | Corrected URL |
|---|---|---|
| `/datasets/minor-civil-divisions` | Didn't resolve | `/datasets/Michigan::minor-civil-divisions-cities-townships-/about` |
| `/datasets/great-lakes-shoreline` | Didn't resolve | REST layer at `hydro/MapServer/13` |
| `NHDPlusHR/Beta/GDB/` | Path changed | `NHDPlusHR/VPU/Current/GDB/` |
| `data-macomb.opendata.arcgis.com` | Not a real Macomb site | `macomb-county-open-data-portal-mcmap.hub.arcgis.com` |

## Notes

- All layers will be reprojected to EPSG:4326 (WGS 84) before loading into PostGIS
- Layers clipped to Macomb County boundary (plus small buffer for edge cases)
- Jurisdiction IDs assigned using format: `{layer_code}_{unique_id}` (e.g., `muni_mount_clemens`)
- Michigan "Minor Civil Divisions" layer = municipal boundaries (cities/townships/villages)
- NHDPlus HR includes flowlines, catchments, and value-added attributes (flow direction, stream order)
- REST layers are queryable directly as JSON/GeoJSON

## Data Gaps

- **County drain districts**: 475 drains viewable via interactive maps, but vector download unconfirmed. Macomb County GIS portal (`gis.macombgov.org`) blocks all automated access — no hidden REST endpoints found. Requires formal data request to Public Works.
- **Storm sewer outfalls**: Not publicly available. Requires data-sharing request to Macomb County Public Works.
- **USCG/EPA response zone line**: Source and availability TBD. May need to digitize from published charts.
- **Public water supply intakes**: Available via EGLE hub but individual layer URL not yet confirmed. GLWA Lake St. Clair intake approximated from known location and flagged in waterways table.

## Refresh Procedure

1. Download updated data to `data/raw/{layer_name}/`
2. Run ETL scripts (clip, reproject, assign IDs)
3. Verify row counts and spot-check geometries
4. Load into PostGIS via `scripts/load_layers.py`
5. Ensure jurisdiction IDs remain stable (match on name/FIPS, not row order)
