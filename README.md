# MCPW-Clean-Water — Clean Water Geotagging & Jurisdiction App

A web application for reporting water spills in Macomb County, MI. A reporter enters a spill summary (location, size, material), the app pins it on an ArcGIS map, identifies every affected jurisdiction, and lists who must be contacted — split into **Response** (who acts now) and **Regulatory** (who must be notified, and by when) panels.

## How It Works

1. Reporter enters a location (address, coordinates, or map click), estimated size, and material type.
2. App geocodes and drops a pin; size optionally draws an impact buffer.
3. Spatial query intersects the pin/buffer with jurisdiction layers (municipality, drain district, subwatershed, shoreline, Coast Guard sector, EPA region) and traces downstream receiving water.
4. Rules engine maps jurisdictions × material × size to required contacts.
5. Results display in Response and Regulatory panels with click-to-call/email links.

## Tech Stack

| Layer | Technology |
| --- | --- |
| Frontend | ArcGIS Maps SDK for JavaScript 4.x |
| Backend | FastAPI (Python) |
| Database | PostgreSQL + PostGIS |
| Data | Macomb County, Michigan, and USGS (NHD/WBD) GIS layers |

## Workstreams

| # | Workstream | Description |
| --- | --- | --- |
| WS1 | Map & Geotagging UI | Map with search, click-to-pin, and impact buffer |
| WS2 | Incident Intake & Parsing | Structured form + free-text parser → validated incident |
| WS3 | Jurisdiction Layers & Spatial Query | Point/buffer → list of jurisdictions + downstream path |
| WS4 | Contacts Directory & Rules Engine | Jurisdictions + material + size → contacts with deadlines |
| WS5 | Backend API & Data Model | REST API (`/lookup`, `/incidents`), DB, incident storage |
| WS6 | Results UI, QA & Deployment | Response/Regulatory panels, end-to-end tests, hosting |

## API Endpoints

- `POST /lookup` — location + spill details → jurisdictions + contacts
- `POST /incidents` — save an incident and its lookup result
- `GET /incidents/{id}` — fetch a saved incident
- `GET /health` — status check

## Getting Started

### Prerequisites

- Python 3.x
- PostgreSQL with PostGIS
- ArcGIS developer API key (store in env file, never in the repo)
- Docker Compose (for local development)

### Local Development

```bash
docker compose up
```

## Scope

**v1:** Spills to water in Macomb County (Lake St. Clair, Clinton River and tributaries, county drains, storm sewers). Single incident at a time, manual contact via call/email links, saved incident record.

**Out of scope for v1:** Automated notifications, plume modeling, mobile-native apps.

## Project Milestones

| Phase | Weeks | Work |
| --- | --- | --- |
| Foundations | 1–2 | Stack + schema, source GIS layers, contact schema, app shell |
| Core Build | 3–5 | Pin + buffer, form + parser, lookup query, seed contacts |
| Integrate | 6–7 | Rules engine, `/lookup` live, results panels, downstream trace |
| Pilot | 8 | End-to-end test scenarios, deploy, demo, verify contacts |

See [Architecture.md](Architecture.md) for full details on workstreams, risks, and open questions.
