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

- **React 18** — UI framework (component-based, hooks for state and lifecycle)
- **Vite** — build tool and dev server
- **TypeScript** — type safety across components and ArcGIS types
- **`@arcgis/core`** — ArcGIS Maps SDK for JavaScript 4.x (ES modules, tree-shakable)
- **ArcGIS World Geocoding Service** — address search
- **ArcGIS Feature Layers / Vector Tiles** — overlay layers from WS3
- **React Context + `useReducer`** — shared state for pin, buffer, and lookup results across components

## Implementation Tasks

### Phase 1 — Foundations (Weeks 1–2)

#### 1.1 Set up the app shell

- [ ] Scaffold the frontend project with Vite + React 18 + TypeScript
  - `npm create vite@latest frontend -- --template react-ts`
  - Install `@arcgis/core` and copy ArcGIS assets to the public directory
  - Configure Vite to handle `@arcgis/core` CSS imports
- [ ] Obtain an ArcGIS developer API key
  - Store in `.env` as `VITE_ARCGIS_API_KEY`; add `.env` to `.gitignore`
  - Document the required env var in the README
- [ ] Create the `MapContext` (React Context + `useReducer`)
  - Shared state: `pin { lat, lon, address }`, `bufferRadius`, `lookupResult`, `activeOverlays`
  - Actions: `SET_PIN`, `SET_BUFFER`, `SET_LOOKUP_RESULT`, `TOGGLE_LAYER`
- [ ] Build the `<MapView />` component
  - Initialize the ArcGIS `MapView` inside a `useEffect` ref-based hook
  - Center: approximately 42.65°N, -82.93°W
  - Zoom level showing all of Macomb County with Lake St. Clair visible
  - Use a streets or topographic basemap appropriate for field use
  - Clean up the view on component unmount
- [ ] Set up the project structure (see file structure below)
- [ ] Verify the map loads in Chrome, Safari, and Firefox on desktop

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

- [ ] Build `<SpillPin />` component
  - Click-to-pin: listen for `MapView` click events; place a `Graphic` point marker
  - Only one pin at a time; clicking again moves it
  - Pin is draggable for fine adjustment (`SketchViewModel` or custom drag handler)
  - On pin place/move: dispatch `SET_PIN` to `MapContext`
- [ ] Build `<CoordinateDisplay />` component
  - Reads `pin` from `MapContext`
  - Format: decimal degrees (e.g., 42.6123, -82.9456)
  - Live-updates as the pin moves via context subscription
- [ ] Build `<CoordinateInput />` component
  - Two controlled input fields (lat, lon) that dispatch `SET_PIN` on submit
  - Repositions the pin and re-centers the map
  - Validate coordinates are within Macomb County bounds; warn if outside
- [ ] Pin state flows to intake form (WS2)
  - WS2 components subscribe to `MapContext` and auto-fill location fields
  - No prop drilling — all communication via shared context

#### 2.2 Draw the impact buffer

- [ ] Build `<ImpactBuffer />` component
  - Reads `pin` and `bufferRadius` from `MapContext`
  - Draw a circle using `geometryEngine.geodesicBuffer` from `@arcgis/core/geometry/geometryEngine`
  - Radius determined by spill quantity using a radius lookup table (agreed with WS4)
  - Default radius when quantity is unknown (e.g., 100 m)
- [ ] Render the buffer as a semi-transparent polygon overlay
  - Visually distinct from jurisdiction layers (e.g., orange with 20% fill)
- [ ] Reactivity via `useEffect` watching context state
  - Redraw when `pin` changes (drag, search, manual entry)
  - Redraw when `bufferRadius` changes (WS2 intake form dispatches `SET_BUFFER`)
- [ ] Pass the buffer geometry to WS5 for spatial query
  - Include buffer radius in context state; WS5 API call reads from `MapContext`

#### 2.3 Add overlay layers

- [ ] Consume published layers from WS3
  - Municipal boundaries (cities, townships, villages)
  - County drain districts
  - Clinton River subwatersheds (HUC-12)
  - Water bodies and stream flowlines (NHD)
- [ ] Build `<LayerToggle />` component
  - Render a checkbox list of available overlay layers
  - Toggle layer visibility via `MapContext` dispatch (`TOGGLE_LAYER`)
  - Each layer can be turned on/off independently
  - Default: municipalities on, others off
- [ ] Build `<JurisdictionHighlight />` component
  - Reads `lookupResult` from `MapContext`
  - After a `/lookup` response, highlight the jurisdictions that intersect the pin/buffer
  - Use a distinct renderer (bold outline, color fill) for matched jurisdictions
  - Clear highlights when the pin moves (new lookup needed) via `useEffect` on `pin` state

### Phase 3 — Integrate & Polish (Weeks 6–7)

#### 3.1 Polish for desktop

- [ ] Desktop layout
  - Map fills available viewport height; controls in a sidebar or panel alongside the map
  - Optimized for desktop screen widths (1024px+)
- [ ] "Use my location" button
  - Browser Geolocation API (`navigator.geolocation.getCurrentPosition`)
  - On success: drop pin, center map, populate coordinates
  - On failure/denial: show a clear message, do not block usage
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
| Frontend framework | React 18 + TypeScript, built with Vite |
| ArcGIS SDK | `@arcgis/core` 4.x (ES modules, tree-shakable) |
| State management | React Context + `useReducer` (no Redux needed at this scale) |
| Coordinate system | WGS 84 (EPSG:4326) for display and API; layers reprojected by WS3 |
| Buffer calculation | Geodesic (accounts for earth curvature) via `geometryEngine.geodesicBuffer` |
| Single pin | Only one active spill pin at a time; multi-incident is out of scope for v1 |
| Target platform | Desktop browsers (Chrome, Safari, Firefox); mobile is post-v1 |
| API key scope | Geocoding + basemaps; confirm license tier covers expected usage (see open questions) |

## Risks

| Risk | Mitigation |
| --- | --- |
| ArcGIS credit/licensing limits on geocoding | Cache results; confirm tier early; monitor usage |
| Layer data not ready from WS3 on time | Build layer toggle infrastructure with mock layers; swap in real data when available |

## Open Questions

- [ ] ArcGIS Online org account or developer API key only? (affects credit limits and layer hosting)
- [ ] Radius lookup table: what spill sizes map to what buffer radii? (coordinate with WS4)
- [ ] Should the map support offline/cached tiles for field use without connectivity?

## File Structure (Proposed)

```
frontend/
  public/
    assets/               # @arcgis/core assets (copied at build)
  src/
    App.tsx               # Root component, wraps MapProvider
    main.tsx              # Vite entry point
    context/
      MapContext.tsx       # React Context + useReducer (pin, buffer, lookupResult, activeOverlays)
      mapReducer.ts        # Reducer: SET_PIN, SET_BUFFER, SET_LOOKUP_RESULT, TOGGLE_LAYER
      types.ts             # Shared state types (Pin, BufferState, LookupResult)
    components/
      MapView.tsx          # ArcGIS MapView initialization (useEffect + ref)
      SpillPin.tsx         # Click-to-pin, drag to adjust
      ImpactBuffer.tsx     # Geodesic buffer circle, reactive to context
      CoordinateDisplay.tsx  # Read-only lat/lon display
      CoordinateInput.tsx    # Manual lat/lon entry
      LayerToggle.tsx      # Overlay layer checkbox panel
      JurisdictionHighlight.tsx  # Highlight matched jurisdictions after lookup
      GeolocateButton.tsx  # "Use my location" browser geolocation
      SearchWidget.tsx     # ArcGIS Search widget wrapper
    hooks/
      useMapView.ts        # Custom hook: init and teardown ArcGIS MapView
      useGeolocation.ts    # Custom hook: browser geolocation API
    utils/
      coordinates.ts       # Formatting, validation, bounds checking
      bufferTable.ts       # Spill quantity → buffer radius lookup
    types/
      arcgis.d.ts          # Additional ArcGIS type declarations if needed
  .env.example             # VITE_ARCGIS_API_KEY=
  vite.config.ts
  tsconfig.json
  package.json
```
