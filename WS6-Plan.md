# WS6 — Results UI, QA & Deployment: Implementation Plan

## Goal

Show the reporter a clear, actionable list of who to contact, and ship a reliable pilot.

## Done When

All test scenarios pass end to end, and the app is live at a shareable URL.

## Dependencies

| Direction | Workstream | What |
| --- | --- | --- |
| Needs from | WS1 | Map UI (shared React app) |
| Needs from | WS2 | Intake form submits to API |
| Needs from | WS3 | Jurisdiction data for test verification |
| Needs from | WS4 | Contact lists and expected results for test scenarios |
| Needs from | WS5 | API endpoints (`/lookup`, `/incidents`) returning lookup results |

## Technology

- **React 18 + TypeScript** — shared frontend app with WS1 and WS2
- **Vite** — build tool (shared)
- **React Context** — reads lookup results from shared state
- **html2canvas + jsPDF** (or similar) — PDF report export with map snapshot
- **Docker + Docker Compose** — containerized deployment
- **CI/CD** — GitHub Actions (or similar) for automated build, test, deploy
- **Hosting** — static site for frontend (e.g., Vercel, Netlify, S3+CloudFront); container for API (e.g., Cloud Run, ECS, Railway)
- **pytest + Playwright** — backend integration tests and frontend end-to-end tests

## Implementation Tasks

### Phase 1 — Foundations (Weeks 1–2)

#### 1.1 Set up the results UI shell

- [ ] Create the results panel layout in the shared React app
  - Two-panel layout below or beside the map: **Response** (left/top) and **Regulatory** (right/bottom)
  - Panels are empty until a lookup completes
  - Loading state while `/lookup` is in progress
- [ ] Create `ResultsContext` (React Context)
  - State: `lookupResult` (jurisdictions, contacts, downstream path, flags), `loading`, `error`
  - Populated after successful `POST /incidents` or `POST /lookup` response
  - Consumed by all results components

#### 1.2 Set up deployment infrastructure

- [ ] Configure Docker build for production
  - Frontend: multi-stage build (Vite build → nginx or static serve)
  - API: production Dockerfile with gunicorn/uvicorn
- [ ] Create `docker-compose.prod.yml` with production settings
  - Environment variables from `.env.production`
  - No dev dependencies or hot reload
- [ ] Set up CI pipeline (GitHub Actions):
  - On push to `main`: lint, type-check, run tests, build Docker images
  - On merge to `main`: deploy to staging
  - Manual promotion: staging → production

### Phase 2 — Core Build (Weeks 3–5)

#### 2.1 Build the results panels

- [ ] Build `<ResponsePanel />` component
  - Header: "Response — Act Now"
  - List of response contacts, sorted by priority (from WS4 rules engine)
  - Each contact card shows:
    - Agency name (bold)
    - Phone number as a `tel:` link (click-to-call on desktop softphones)
    - After-hours phone (if different, with label)
    - Email as a `mailto:` link
    - Office hours
    - Reporting deadline (e.g., "Immediately")
  - Visual urgency indicator (e.g., red accent for priority 1–10, orange for 11–50)

- [ ] Build `<RegulatoryPanel />` component
  - Header: "Regulatory — Required Notifications"
  - List of regulatory contacts, sorted by deadline urgency then priority
  - Each contact card shows:
    - Agency name (bold)
    - Phone number as a `tel:` link
    - Email as a `mailto:` link
    - Reporting deadline (prominent, e.g., "Within 24 hours")
    - Legal citation (small text, e.g., "40 CFR 302.4")
    - Source URL as a link ("Verify contact")
    - Last verified date (e.g., "Verified Oct 2026")
  - Visual deadline grouping:
    - "Immediately" contacts first (red)
    - "Within 24 hours" next (orange)
    - "Within 10 days" last (yellow)

- [ ] Build `<ContactCard />` shared component
  - Reused by both panels
  - Props: contact data, display variant (response vs. regulatory)
  - `tel:` and `mailto:` links styled as buttons for easy click-to-call/email
  - Expandable section for additional details (after-hours, notes, legal citation)

- [ ] Build `<JurisdictionSummary />` component
  - Shows which jurisdictions were matched (from lookup result)
  - Grouped by layer: municipality, drain district, subwatershed, etc.
  - Shows downstream path (e.g., "Red Run Drain → Clinton River → Lake St. Clair")
  - Flags: beach downstream, drinking-water intake downstream

#### 2.2 Add the incident summary

- [ ] Build `<IncidentSummary />` component
  - Copy-able block containing:
    - Location: address + coordinates
    - Water body: name
    - Material: category + detail
    - Quantity: value + unit (+ normalized gallons)
    - Time observed: formatted datetime
    - Reporter: name + phone
    - Downstream path
  - "Copy to clipboard" button
    - Copies as plain text, formatted for reading over the phone or pasting into an email
    - Format:
      ```
      SPILL REPORT
      Location: 123 Main St, Mount Clemens, MI (42.5973, -82.8779)
      Water Body: Clinton River
      Material: Diesel (oil/fuel)
      Quantity: ~50 gallons
      Time Observed: 2026-10-13 14:30 ET
      Reporter: John Smith, (586) 555-0123
      Downstream: Clinton River → Lake St. Clair
      ```
  - Visual confirmation on copy (brief "Copied!" tooltip)

#### 2.3 Add the incident report export

- [ ] Build `<ExportButton />` component
  - "Export PDF Report" button
- [ ] Implement PDF generation:
  - Capture map screenshot using `MapView.takeScreenshot()` (ArcGIS SDK) or `html2canvas`
  - Generate PDF with `jsPDF` (or `@react-pdf/renderer` for more control)
  - PDF contents:
    - Header: "Spill Incident Report" + incident ID + timestamp
    - Map snapshot with pin and buffer visible
    - Incident summary (same content as `<IncidentSummary />`)
    - Response contacts table
    - Regulatory contacts table with deadlines and citations
    - Jurisdiction list
    - Downstream path
    - Disclaimer text
  - Download as `spill-report-{incident_id}.pdf`

### Phase 3 — Integrate & QA (Weeks 6–7)

#### 3.1 Add the disclaimer

- [ ] Build `<Disclaimer />` component
  - Visible on the results page, always shown:
    > "This tool supports, but does not replace, legally required spill reporting. Contact information is verified periodically but may change. Always confirm current contact details with the listed source before reporting."
  - Styled as a notice banner (yellow/amber background)
  - Also included in the PDF export

#### 3.2 Wire up the full flow

- [ ] Connect intake form submission (WS2) → API call (WS5) → results display (WS6)
  - On submit: show loading state in results panels
  - On success: populate `ResultsContext` with lookup result; render panels
  - On error: show error message with retry option
- [ ] Connect map highlights (WS1) to lookup results
  - After results load, dispatch `SET_LOOKUP_RESULT` to `MapContext`
  - WS1's `<JurisdictionHighlight />` highlights matched jurisdictions

#### 3.3 Run end-to-end test scenarios

- [ ] Define test scenarios (aligned with WS4 scenario tests):

  **Scenario 1: Oil sheen on Lake St. Clair**
  - Input: Pin on Lake St. Clair near Harrison Township; material: oil/fuel; quantity: unknown
  - Expected jurisdictions: Harrison Township, USCG zone, EPA region
  - Expected response contacts: 911, Harrison Twp DPW, County EM, USCG Sector Detroit
  - Expected regulatory contacts: NRC (immediately), EGLE PEAS (immediately), County PW (24h), County Health (24h), EGLE District (10d)
  - Verify: contact phones, deadlines, sort order, jurisdiction highlights on map

  **Scenario 2: Chemical release in the Clinton River**
  - Input: Pin on Clinton River near Mount Clemens; material: chemical/hazmat (antifreeze); quantity: 10 gallons
  - Expected jurisdictions: Mount Clemens, Clinton River subwatershed, drain district
  - Expected response contacts: 911, Mount Clemens DPW, County EM
  - Expected regulatory contacts: NRC, EGLE PEAS, County PW, County Health, EGLE District
  - Verify: downstream path shows Clinton River → Lake St. Clair; no USCG (not on shoreline)

  **Scenario 3: Discharge from a storm drain**
  - Input: Pin in Sterling Heights near storm drain; material: unknown; quantity: unknown
  - Expected jurisdictions: Sterling Heights, drain district
  - Expected response contacts: 911, Sterling Heights DPW, County EM
  - Expected regulatory contacts: EGLE PEAS, County PW, County Health
  - Verify: flags for "material-specific rules may apply" and "quantity thresholds not evaluated"

  **Scenario 4: Sewage overflow into a county drain**
  - Input: Pin in Clinton Township near county drain; material: sewage; quantity: ~200 gallons
  - Expected jurisdictions: Clinton Township, drain district
  - Expected response contacts: 911, Clinton Twp DPW, County EM
  - Expected regulatory contacts: EGLE PEAS, County PW, County Health, EGLE District

- [ ] Implement automated E2E tests using Playwright:
  - For each scenario: fill the intake form → submit → verify results panels match expected contacts
  - Verify PDF export generates and contains correct content
  - Verify clipboard copy works

- [ ] Manual verification checklist:
  - [ ] Every contact phone number in the results is clickable (`tel:` link)
  - [ ] Every email is clickable (`mailto:` link)
  - [ ] "Last verified" dates are shown and recent
  - [ ] Disclaimer is visible on every results view
  - [ ] PDF export includes all required sections
  - [ ] Incident summary "Copy" button works

### Phase 4 — Pilot (Week 8)

#### 4.1 Deploy

- [ ] Deploy staging environment
  - Frontend: build and deploy to static hosting
  - API + DB: deploy container with PostGIS database
  - Verify all endpoints accessible; run smoke tests
- [ ] Configure separate staging and production environments
  - Different API URLs, database instances, ArcGIS API keys
  - Environment variables per environment
- [ ] Set up automated deployment
  - Merge to `main` → deploy to staging
  - Tag release → deploy to production (manual approval)
- [ ] Set up monitoring
  - API health check endpoint polled by uptime monitor
  - Error logging (structured JSON logs to stdout; aggregate in cloud provider's log viewer)

#### 4.2 Run the pilot demo

- [ ] Walk the team through every test scenario live on the staging environment
  - One scenario at a time; verify results against expected contacts
  - Log every issue found (UI bugs, wrong contacts, missing data, unclear labels)
- [ ] Assign fixes for all logged issues
  - Priority: wrong contacts > missing data > UI issues > cosmetic
- [ ] Fix and re-deploy; re-verify each fixed issue
- [ ] Final sign-off: all scenarios pass, all contacts verified, disclaimer visible

#### 4.3 Production launch

- [ ] Tag a release and deploy to production
- [ ] Verify production is working (run all scenarios against production URL)
- [ ] Share the production URL with stakeholders
- [ ] Document known limitations and post-v1 roadmap items

## Key Decisions & Constraints

| Decision | Notes |
| --- | --- |
| Frontend framework | React 18 + TypeScript (shared app with WS1, WS2) |
| PDF generation | Client-side (html2canvas + jsPDF or @react-pdf/renderer) |
| Target platform | Desktop browsers; mobile is post-v1 |
| Hosting split | Static site for frontend; container for API + DB |
| CI/CD | GitHub Actions; auto-deploy to staging on merge, manual promotion to production |
| E2E testing | Playwright for browser automation tests |
| Disclaimer | Always visible; included in PDF export |

## Risks

| Risk | Mitigation |
| --- | --- |
| Wrong contact displayed during a real spill | All contacts must be verified before pilot; show "last verified" and source URL |
| PDF export rendering issues | Test across Chrome, Safari, Firefox; fallback to print-to-PDF if library issues |
| Staging/production environment drift | Use identical Docker images; only env vars differ |
| CI pipeline breaks during pilot | Keep deployment manual as fallback; fix CI post-pilot |
| Performance under concurrent users | Unlikely for v1 (single team); load test if scaling planned |

## Open Questions

- [ ] Hosting provider preference (Vercel/Netlify for frontend? Cloud Run/Railway/ECS for API?)
- [ ] Domain name for the app?
- [ ] Who needs access to staging vs. production?
- [ ] Should the pilot demo be recorded for stakeholders who can't attend?
- [ ] Post-v1: should results be shareable via URL (e.g., `/incidents/{id}/report`)?

## File Structure (Proposed)

```
frontend/src/
  context/
    ResultsContext.tsx          # React Context for lookup results
    resultsReducer.ts           # Reducer: SET_RESULTS, SET_LOADING, SET_ERROR, CLEAR
  components/results/
    ResponsePanel.tsx           # "Act Now" contact list
    RegulatoryPanel.tsx         # "Required Notifications" contact list
    ContactCard.tsx             # Shared contact display component
    JurisdictionSummary.tsx     # Matched jurisdictions + downstream path
    IncidentSummary.tsx         # Copy-able incident details block
    ExportButton.tsx            # PDF export trigger
    Disclaimer.tsx              # Legal disclaimer banner
  services/
    pdfExport.ts                # PDF generation logic (map snapshot + report content)
    clipboard.ts                # Copy-to-clipboard utility

# Deployment
docker-compose.prod.yml        # Production compose file
.github/
  workflows/
    ci.yml                      # Lint, type-check, test on push
    deploy-staging.yml          # Deploy to staging on merge to main
    deploy-production.yml       # Deploy to production on release tag

# E2E Tests
e2e/
  scenarios/
    oil-sheen-lake.spec.ts      # Scenario 1: oil sheen on Lake St. Clair
    chemical-clinton-river.spec.ts  # Scenario 2: chemical in Clinton River
    storm-drain-discharge.spec.ts   # Scenario 3: storm drain discharge
    sewage-county-drain.spec.ts     # Scenario 4: sewage overflow
  helpers/
    fillIntakeForm.ts           # Shared helper: fill form fields
    verifyContacts.ts           # Shared helper: assert contact list matches expected
  playwright.config.ts
```
