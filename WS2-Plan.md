# WS2 — Incident Intake & Parsing: Implementation Plan

## Goal

Turn whatever the reporter enters into one clean, structured incident record.

## Done When

The form and a one-line summary like "about 50 gallons of diesel in the Clinton River near Mount Clemens" both produce the same validated record for `POST /incidents`, and the resulting incident event is ready for external consumption.

## Dependencies

| Direction | Workstream | What |
| --- | --- | --- |
| Needs from | WS1 | Pin coordinates + address from the map (via `MapContext`) |
| Needs from | WS4 | Material category mapping (shared JSON) |
| Needs from | WS5 | Incident schema / API contract (Pydantic models) |
| Hands off to | WS5 | Validated `IncidentCreate` payload + event trigger |

## Technology

- **React 18** — UI framework (shared app with WS1)
- **TypeScript** — type safety, shared types with WS5 contract
- **React Context** — reads pin state from `MapContext` (WS1); provides form state via `IntakeContext`
- **React Hook Form** — form state management, field validation, error display
- **Zod** — schema validation (mirrors WS5 Pydantic models client-side)
- **material-categories.json** — shared mapping file consumed by WS2 (parsing) and WS4 (rules)

## Implementation Tasks

### Phase 1 — Foundations (Weeks 1–2)

#### 1.1 Agree the incident fields with WS5

- [ ] Finalize the incident field list against the WS5 `IncidentCreate` Pydantic model:

  | Field | Type | Required | Source |
  | --- | --- | --- | --- |
  | `location.lat` | float | Yes | Map pin (WS1) |
  | `location.lon` | float | Yes | Map pin (WS1) |
  | `location.address` | string | No | Map pin (WS1) / geocoder |
  | `water_body` | enum | Yes | Form dropdown |
  | `material` | enum | Yes | Form dropdown or parser |
  | `material_detail` | string | No | Form text or parser |
  | `quantity` | float | No | Form input or parser |
  | `quantity_unit` | enum | Yes (if quantity given) | Form dropdown or parser |
  | `quantity_gallons` | float | No | Computed (normalized) |
  | `time_observed` | datetime | Yes | Form input |
  | `reporter_name` | string | Yes | Form input |
  | `reporter_phone` | string | Yes | Form input |
  | `notes` | string | No | Form textarea |
  | `buffer_radius_m` | float | No | Computed from quantity |

- [ ] Create shared TypeScript types matching the WS5 schema
  - `src/types/incident.ts` — `IncidentCreate`, `Location`, `WaterBodyType`, `MaterialType`, `QuantityUnit`
  - Generate or manually sync from WS5's `openapi.json`

- [ ] Create the `IntakeContext` (React Context + `useReducer`)
  - State: all incident fields, validation errors, form mode (structured vs. free-text), submit status
  - Actions: `SET_FIELD`, `SET_PARSED_FIELDS`, `VALIDATE`, `RESET`, `SUBMIT`
  - Reads `pin` from `MapContext` and auto-fills location fields

#### 1.2 Create the material category mapping

- [ ] Create `shared/material-categories.json`
  ```json
  {
    "oil_fuel": ["diesel", "gasoline", "motor oil", "heating oil", "jet fuel", "crude oil", "fuel oil"],
    "chemical_hazmat": ["antifreeze", "paint", "solvent", "pesticide", "fertilizer", "acid", "bleach", "ammonia"],
    "sewage": ["sewage", "wastewater", "septic", "sanitary"],
    "unknown_other": []
  }
  ```
- [ ] Write a utility function `categorizeMaterial(detail: string): MaterialType`
  - Case-insensitive substring match against the mapping
  - Returns `unknown_other` if no match
- [ ] Coordinate with WS4 — they consume the same file for rules matching

### Phase 2 — Core Build (Weeks 3–5)

#### 2.1 Build the structured form

- [ ] Build `<IncidentForm />` component using React Hook Form + Zod validation
  - Register all fields from the schema; bind to `IntakeContext`
- [ ] Build form field components:

  **`<WaterBodySelect />`**
  - Dropdown with options: Lake St. Clair, Clinton River, tributary/creek, county drain, storm sewer, unknown
  - Maps display labels to `WaterBodyType` enum values

  **`<MaterialSelect />`**
  - Dropdown with categories: oil/fuel, chemical/hazmat, sewage, unknown/other
  - Optional free-text `material_detail` field appears after selection (e.g., "diesel")

  **`<QuantityInput />`**
  - Numeric input + unit dropdown (gal, bbl, L, lb)
  - "Unknown" checkbox disables the input and sets quantity to `null`
  - On change: compute `quantity_gallons` via normalization (see 2.3)

  **`<LocationFields />`**
  - Reads `pin` from `MapContext`; displays lat, lon, address as read-only when pin is set
  - "No pin set" warning if location is empty
  - Manual override toggle (falls back to `<CoordinateInput />` from WS1)

  **`<ReporterFields />`**
  - Name (text) and phone (tel input with formatting)
  - Both required; phone validated as US format

  **`<TimeObserved />`**
  - Datetime-local input
  - Defaults to current time; cannot be in the future

  **`<NotesField />`**
  - Optional textarea, max 2000 characters

- [ ] Build `<FormActions />` component
  - Submit button: disabled until all required fields pass Zod validation
  - Reset button: dispatches `RESET` to `IntakeContext`
  - Visual validation errors displayed inline per field

#### 2.2 Build the free-text parser

- [ ] Build `<FreeTextInput />` component
  - Single textarea input: "Describe the spill in one line"
  - "Parse" button triggers the parsing pipeline
  - Toggle between free-text and structured form modes

- [ ] Implement the parsing pipeline in `src/services/spillParser.ts`
  - Input: raw string
  - Output: `Partial<IncidentCreate>` (all fields optional — only fill what's found)

- [ ] Implement keyword/regex extraction rules:

  **Location**
  - Match city/township names in Macomb County (Mount Clemens, Sterling Heights, Clinton Township, etc.)
  - Match "near [place]", "at [place]", "on [road/street]"
  - Match coordinate patterns (decimal degrees, DMS)

  **Water body**
  - Match water body names: "Lake St. Clair", "Clinton River", "Red Run Drain", "storm drain", etc.
  - Map to `WaterBodyType` enum

  **Material**
  - Match material keywords against `material-categories.json`
  - Extract the specific material as `material_detail`

  **Quantity**
  - Match numeric patterns followed by unit words: "50 gallons", "2 barrels", "about 100 gal"
  - Handle qualifiers: "about", "approximately", "less than", "unknown"
  - Normalize unit abbreviations (gal, bbl, L, lb)

  **Time**
  - Match time expressions: "this morning", "2 hours ago", "at 3pm", "yesterday"
  - Convert relative times to absolute datetime

- [ ] Build `<ParsedFieldsReview />` component
  - Display parsed fields in the structured form, pre-filled and editable
  - Highlight which fields were auto-parsed (e.g., colored border or label)
  - Reporter must confirm or correct before submit — never submit unconfirmed parsed data
  - "Accept all" button fills the form; individual fields can be overridden

- [ ] Future: if regex accuracy is below 80% on the test set, add an optional LLM call
  - Send the summary to a language model with a structured output prompt
  - Parse the model response into the same `Partial<IncidentCreate>` shape
  - Gate behind a feature flag (`VITE_USE_LLM_PARSER=false` by default)

#### 2.3 Normalize and validate

- [ ] Implement quantity normalization in `src/utils/unitConversion.ts`
  - Conversion factors to gallons:
    - 1 bbl = 42 gal
    - 1 L = 0.264172 gal
    - 1 lb: depends on material density — use water density (8.34 lb/gal) as default; flag for review
  - Function: `toGallons(quantity: number, unit: QuantityUnit, material?: MaterialType): number`

- [ ] Implement Zod validation schema matching WS5's Pydantic model
  - Required fields: location (lat + lon), water_body, material, time_observed, reporter_name, reporter_phone
  - Conditional: quantity_unit required if quantity is provided
  - Range checks: lat 42.4–42.8, lon -83.2 to -82.6 (Macomb County bounds)
  - Phone: US format validation

- [ ] Block submit until validation passes
  - Display all errors inline; scroll to first error on failed submit attempt

#### 2.4 Emit incident events

- [ ] On form submit, dispatch validated `IncidentCreate` to WS5 via `POST /incidents`
  - WS5 handles event creation and publishing (see WS5-Plan)
  - WS2's responsibility: ensure the payload is clean, complete, and matches the event schema
- [ ] Display success/error state after submission
  - On success: show incident ID, link to results (WS6), and option to start a new report
  - On error: show API error message, keep form populated for retry
- [ ] Pass `buffer_radius_m` in the payload
  - Computed from `quantity_gallons` using the radius lookup table (shared with WS1)

### Phase 3 — Integrate (Weeks 6–7)

#### 3.1 Integration with WS1 and WS5

- [ ] Verify `MapContext` → `IntakeContext` flow
  - Pin placed on map → location fields auto-fill in the form
  - Pin moved → location fields update; validation re-runs
  - No pin → location fields empty; submit blocked with clear message
- [ ] Verify `POST /incidents` round-trip with WS5
  - Submit form → API saves incident → returns incident ID + lookup result
  - Lookup result flows to WS6 results panels
- [ ] Verify event emission
  - After successful `POST /incidents`, confirm event appears in `GET /events`

#### 3.2 Edge cases and error handling

- [ ] Handle API errors gracefully (network failure, 400 validation, 500 server error)
- [ ] Handle browser back/forward (warn if form has unsaved data)
- [ ] Handle duplicate submissions (disable submit button after first click; re-enable on error)

### Phase 4 — Pilot (Week 8)

#### 4.1 Build and run the test set

- [ ] Write 20+ sample summaries in `tests/parser-test-cases.json`
  - Each entry: `{ input: "...", expected: { water_body, material, material_detail, quantity, quantity_unit, ... } }`
  - Cover: all water body types, all material categories, various quantity formats, relative times, ambiguous inputs, missing fields
- [ ] Sample test cases:
  1. "about 50 gallons of diesel in the Clinton River near Mount Clemens"
  2. "oil sheen on Lake St. Clair by the marina"
  3. "sewage overflow from storm drain on Gratiot Ave, unknown quantity"
  4. "chemical spill at 42.6123, -82.9456 — antifreeze, maybe 5 gallons, happened 2 hours ago"
  5. "large fuel leak into Red Run Drain, Sterling Heights, several hundred gallons of gasoline"
  6. "unknown substance in county drain behind 21 Mile Road"
- [ ] Automated parser test runner
  - Run all test cases through `spillParser`; compare output to expected
  - Report accuracy per field and overall
  - All must pass before pilot
- [ ] Form validation tests
  - Submit with missing required fields → blocked with correct errors
  - Submit with out-of-range coordinates → warning
  - Submit with invalid phone → error

#### 4.2 Pilot readiness

- [ ] All WS6 end-to-end scenarios pass through the intake form
- [ ] Free-text parser passes all 20+ test cases
- [ ] Fix issues logged during the pilot demo

## Key Decisions & Constraints

| Decision | Notes |
| --- | --- |
| Frontend framework | React 18 + TypeScript (shared app with WS1) |
| Form library | React Hook Form + Zod (mirrors WS5 Pydantic validation) |
| Parser strategy | Keyword/regex first; LLM fallback behind feature flag, only if accuracy < 80% |
| Confirmation required | Parsed fields always shown for review; never auto-submit |
| Material mapping | Single shared `material-categories.json` used by WS2 and WS4 |
| Target platform | Desktop browsers; mobile is post-v1 |
| Unit normalization | All quantities normalized to gallons before API submission |

## Risks

| Risk | Mitigation |
| --- | --- |
| Free-text parsing errors | Always require user confirmation; never auto-submit parsed data |
| WS5 schema changes break the form | Generate or sync TS types from `openapi.json`; run type checks in CI |
| Ambiguous material names | Map conservatively to `unknown_other`; let the reporter override |
| Unit conversion for weight (lb) | Use water density as default; flag for manual review in notes |
| LLM parser adds latency/cost | Gate behind feature flag; regex-first by default |

## Open Questions

- [ ] Should the free-text parser support multi-line input or strictly one-line summaries?
- [ ] Should parsed confidence scores be shown to the reporter (e.g., "80% sure this is diesel")?
- [ ] Does the form need a "save draft" feature, or is session-only state acceptable for v1?
- [ ] Should the material mapping JSON be editable by admins in the UI, or only via code changes?

## File Structure (Proposed)

```
frontend/src/
  context/
    IntakeContext.tsx        # React Context + useReducer for form state
    intakeReducer.ts         # Reducer: SET_FIELD, SET_PARSED_FIELDS, VALIDATE, RESET, SUBMIT
  components/intake/
    IncidentForm.tsx         # Main form component (React Hook Form + Zod)
    WaterBodySelect.tsx      # Water body dropdown
    MaterialSelect.tsx       # Material category dropdown + detail field
    QuantityInput.tsx        # Quantity + unit + "unknown" toggle
    LocationFields.tsx       # Location display (reads MapContext)
    ReporterFields.tsx       # Name + phone inputs
    TimeObserved.tsx         # Datetime-local input
    NotesField.tsx           # Optional notes textarea
    FormActions.tsx          # Submit + reset buttons
    FreeTextInput.tsx        # One-line summary input + parse button
    ParsedFieldsReview.tsx   # Parsed results review with accept/override
  services/
    spillParser.ts           # Free-text parsing pipeline (regex/keyword)
    incidentApi.ts           # POST /incidents API call
  utils/
    unitConversion.ts        # toGallons() normalization
    validation.ts            # Zod schema for IncidentCreate
  types/
    incident.ts              # IncidentCreate, Location, enums (synced with WS5)
  shared/
    material-categories.json # Material name → category mapping (shared with WS4)
  tests/
    parser-test-cases.json   # 20+ sample summaries with expected outputs
    spillParser.test.ts      # Automated parser accuracy tests
    unitConversion.test.ts   # Unit conversion tests
    validation.test.ts       # Zod schema validation tests
```
