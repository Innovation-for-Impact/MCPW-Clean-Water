# WS1 — Map & Geotagging UI: Implementation Plan

## Goal

A map where a reporter can find and pin a spill location in Macomb County in under a minute.

## Done When

A pin placed by search or click sends its coordinates to the intake form, and the buffer and overlay layers display correctly on desktop and phone.

## Dependencies

| Direction | Workstream | What |
| --- | --- | --- |
| Needs from | WS3 | Published jurisdiction layers (municipalities, drain districts, subwatersheds, water bodies) |
| Hands off to | WS2 | Pin coordinates + address for the intake form |
| Hands off to | WS5 | Pin + buffer geometry for spatial lookup |

## Technology

- **ArcGIS Maps SDK for JavaScript 4.x** — map rendering, geocoding, geometry
- **ArcGIS World Geocoding Service** — address search
- **ArcGIS Feature Layers / Vector Tiles** — overlay layers from WS3

## Implementation Tasks

### Phase 1 — Foundations (Weeks 1–2)

#### 1.1 Set up the app shell

- [ ] Scaffold the frontend project (Vite or similar bundler) with ArcGIS Maps SDK for JavaScript 4.x
- [ ] Obtain an ArcGIS developer API key
  - Store in `.env`; add `.env` to `.gitignore`
  - Document the required env var in the README
- [ ] Configure a `MapView` centered on Macomb County
  - Center: approximately 42.65°N, -82.93°W
  - Zoom level showing all of Macomb County with Lake St. Clair visible
  - Use a streets or topographic basemap appropriate for field use
- [ ] Set up the project structure
  - `/src/map/` — map initialization, view config
  - `/src/widgets/` — search, pin, buffer, layer toggle
  - `/src/utils/` — coordinate formatting, unit conversion
- [ ] Verify the map loads in Chrome, Safari, and Firefox on desktop and mobile viewports

#### 1.2 Add location search

- [ ] Add the ArcGIS `Search` widget to the map
  - Use ArcGIS World Geocoding Service as the source
- [ ] Restrict geocoding results to Macomb County
  - Set `countryCode: "US"` and use a bounding box or location bias centered on Macomb County so local addresses rank first
- [ ] On search result selection:
  - Center the map on the result
  - Drop a pin at the result location (feeds into task 1.3)
  - Populate the coordinate display

### Phase 2 — Core Build (Weeks 3–5)

#### 2.1 Pin the spill

- [ ] Click-to-pin: clicking the map places a `Graphic` point marker
  - Only one pin at a time; clicking again moves it
  - Pin is draggable for fine adjustment (`SketchViewModel` or custom drag handler)
- [ ] Coordinate display below the map
  - Format: decimal degrees (e.g., 42.6123, -82.9456)
  - Live-update as the pin moves
- [ ] Manual coordinate entry
  - Two input fields (lat, lon) that reposition the pin and re-center the map on submit
  - Validate coordinates are within Macomb County bounds; warn if outside
- [ ] Emit pin location to intake form (WS2)
  - Expose a callback or event (`onPinChange`) with `{ lat, lon, address }` payload
  - WS2 subscribes and auto-fills the location fields

#### 2.2 Draw the impact buffer

- [ ] Draw a circle (`Circle` geometry or `geometryEngine.geodesicBuffer`) around the pin
  - Radius determined by spill quantity using a radius lookup table (agreed with WS4)
  - Default radius when quantity is unknown (e.g., 100 m)
- [ ] Render the buffer as a semi-transparent polygon overlay
  - Visually distinct from jurisdiction layers (e.g., orange with 20% fill)
- [ ] Reactivity
  - Redraw when the pin moves (drag, search, manual entry)
  - Redraw when the spill size changes (listen for intake form updates from WS2)
- [ ] Pass the buffer geometry to WS5 for spatial query
  - Include in the `onPinChange` payload or a separate `onBufferChange` event

#### 2.3 Add overlay layers

- [ ] Consume published layers from WS3
  - Municipal boundaries (cities, townships, villages)
  - County drain districts
  - Clinton River subwatersheds (HUC-12)
  - Water bodies and stream flowlines (NHD)
- [ ] Layer toggle control
  - Add a `LayerList` widget or custom toggle panel
  - Each layer can be turned on/off independently
  - Default: municipalities on, others off
- [ ] Jurisdiction highlighting
  - After a `/lookup` response, highlight the jurisdictions that intersect the pin/buffer
  - Use a distinct renderer (bold outline, color fill) for matched jurisdictions
  - Clear highlights when the pin moves (new lookup needed)

### Phase 3 — Integrate & Polish (Weeks 6–7)

#### 3.1 Make it field-ready

- [ ] Responsive layout
  - Test at 375px width (iPhone SE) and 768px (tablet)
  - Map fills available viewport height; controls stack below or in a collapsible panel
  - Touch targets at least 44×44px (Apple HIG)
- [ ] "Use my location" button
  - Browser Geolocation API (`navigator.geolocation.getCurrentPosition`)
  - On success: drop pin, center map, populate coordinates
  - On failure/denial: show a clear message, do not block usage
  - GPS accuracy indicator (optional): show accuracy radius if > 50 m
- [ ] Performance
  - Lazy-load overlay layers; don't block initial map render
  - Cache geocoding results to minimize ArcGIS credit usage
- [ ] Accessibility
  - Keyboard-navigable controls (search, coordinate entry, layer toggles)
  - ARIA labels on interactive map elements
  - Sufficient color contrast on buffer and highlight overlays

### Phase 4 — Pilot (Week 8)

#### 4.1 Pilot readiness

- [ ] Verify all WS1 functionality in the end-to-end test scenarios (WS6)
  - Pin placement via search, click, geolocation, and manual entry
  - Buffer draws and redraws correctly
  - Overlay layers toggle and highlight correctly
- [ ] Fix issues logged during the pilot demo
- [ ] Document the ArcGIS API key tier and credit usage to date

## Key Decisions & Constraints

| Decision | Notes |
| --- | --- |
| ArcGIS SDK version | 4.x (not 3.x); ES modules build |
| Coordinate system | WGS 84 (EPSG:4326) for display and API; layers reprojected by WS3 |
| Buffer calculation | Geodesic (accounts for earth curvature) via `geometryEngine.geodesicBuffer` |
| Single pin | Only one active spill pin at a time; multi-incident is out of scope for v1 |
| API key scope | Geocoding + basemaps; confirm license tier covers expected usage (see open questions) |

## Risks

| Risk | Mitigation |
| --- | --- |
| ArcGIS credit/licensing limits on geocoding | Cache results; confirm tier early; monitor usage |
| Poor GPS accuracy in field conditions | Show accuracy indicator; allow manual pin adjustment |
| Layer data not ready from WS3 on time | Build layer toggle infrastructure with mock layers; swap in real data when available |
| Mobile performance with multiple overlay layers | Lazy-load layers; use vector tiles where possible; test on low-end devices |

## Open Questions

- [ ] ArcGIS Online org account or developer API key only? (affects credit limits and layer hosting)
- [ ] Radius lookup table: what spill sizes map to what buffer radii? (coordinate with WS4)
- [ ] Should the map support offline/cached tiles for field use without connectivity?

## File Structure (Proposed)

```
src/
  map/
    MapView.js          # Map initialization and configuration
    BasemapConfig.js    # Basemap and center/zoom defaults
  widgets/
    SearchWidget.js     # Location search with county bias
    PinManager.js       # Click-to-pin, drag, coordinate display
    BufferManager.js    # Impact buffer drawing and reactivity
    LayerToggle.js      # Overlay layer toggle panel
    GeolocateButton.js  # "Use my location" button
  utils/
    coordinates.js      # Formatting, validation, bounds checking
    events.js           # onPinChange, onBufferChange event bus
```
