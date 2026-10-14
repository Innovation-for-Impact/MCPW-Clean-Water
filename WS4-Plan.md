# WS4 — Contacts Directory & Rules Engine: Implementation Plan

## Goal

Given the jurisdictions and spill details, return exactly who to contact — split into Response and Regulatory — with deadlines.

## Done When

Every test scenario returns the correct contact list, and every contact has a source link and a verified date.

## Dependencies

| Direction | Workstream | What |
| --- | --- | --- |
| Needs from | WS3 | Jurisdiction IDs (stable identifiers for each layer feature) |
| Needs from | WS2 | Material category mapping (`material-categories.json`) |
| Hands off to | WS5 | Rules engine function callable from `/lookup` endpoint |
| Hands off to | WS6 | Contact lists for Response and Regulatory panels |

## Technology

- **PostgreSQL 15+** — contacts and rules storage (shared DB with WS3/WS5)
- **SQLAlchemy 2.x** — ORM for contacts, rules tables (shared with WS5)
- **Python** — rules engine logic
- **material-categories.json** — shared material mapping (authored by WS2, consumed here)
- **pytest** — scenario tests

## Implementation Tasks

### Phase 1 — Foundations (Weeks 1–2)

#### 1.1 Define the contact table

- [ ] Create the `contacts` table (coordinate with WS5 on schema):
  ```sql
  CREATE TABLE contacts (
      id SERIAL PRIMARY KEY,
      agency VARCHAR(255) NOT NULL,
      role VARCHAR(20) NOT NULL,                -- 'response' or 'regulatory'
      jurisdiction_id VARCHAR(100),             -- FK to jurisdictions.jurisdiction_id (nullable for county/state/federal)
      jurisdiction_scope VARCHAR(50),           -- 'municipal', 'county', 'state', 'federal'
      phone VARCHAR(30) NOT NULL,
      after_hours_phone VARCHAR(30),
      email VARCHAR(255),
      hours VARCHAR(100),                       -- e.g., "24/7", "M-F 8am-5pm"
      reporting_deadline VARCHAR(100),          -- e.g., "immediately", "within 24 hours"
      source_url TEXT NOT NULL,
      last_verified DATE NOT NULL,
      notes TEXT
  );
  ```

- [ ] Define the contact data model in SQLAlchemy (shared with WS5):
  ```python
  class Contact(Base):
      __tablename__ = "contacts"
      id: Mapped[int] = mapped_column(primary_key=True)
      agency: Mapped[str]
      role: Mapped[str]  # "response" | "regulatory"
      jurisdiction_id: Mapped[str | None]
      jurisdiction_scope: Mapped[str]
      phone: Mapped[str]
      after_hours_phone: Mapped[str | None]
      email: Mapped[str | None]
      hours: Mapped[str | None]
      reporting_deadline: Mapped[str | None]
      source_url: Mapped[str]
      last_verified: Mapped[date]
      notes: Mapped[str | None]
  ```

#### 1.2 Define the rules table

- [ ] Create the `rules` table:
  ```sql
  CREATE TABLE rules (
      id SERIAL PRIMARY KEY,
      jurisdiction_type VARCHAR(50) NOT NULL,   -- 'municipality', 'drain_district', 'subwatershed', 'shoreline', 'uscg_zone', 'epa_region'
      water_body VARCHAR(50),                   -- NULL = any; 'lake_st_clair', 'clinton_river', etc.
      material VARCHAR(50),                     -- NULL = any; 'oil_fuel', 'chemical_hazmat', 'sewage'
      size_threshold_gal FLOAT,                 -- NULL = any size; trigger above this quantity
      contact_id INTEGER NOT NULL REFERENCES contacts(id),
      required BOOLEAN NOT NULL DEFAULT TRUE,   -- required vs. optional notification
      deadline VARCHAR(100),                    -- overrides contact.reporting_deadline if set
      legal_citation TEXT,                      -- e.g., "40 CFR 302.4", "Michigan Part 5 Rules"
      priority INTEGER NOT NULL DEFAULT 100     -- lower = more urgent (for sort order)
  );
  ```

- [ ] Design the rule matching logic:
  - A rule matches if ALL non-null conditions are satisfied:
    - `jurisdiction_type` matches one of the returned jurisdiction layers
    - `water_body` is NULL (any) or matches the incident water body
    - `material` is NULL (any) or matches the incident material category
    - `size_threshold_gal` is NULL (any size) or incident quantity >= threshold
  - Multiple rules can match → multiple contacts returned
  - `priority` determines sort order within Response and Regulatory groups

### Phase 2 — Core Build (Weeks 3–5)

#### 2.1 Research and seed contacts

- [ ] **Response contacts** (who acts now):

  | Agency | Scope | Phone | Source | Notes |
  | --- | --- | --- | --- | --- |
  | 911 / Local fire department | Per municipality | 911 | — | Always first for immediate hazards |
  | Municipal DPW | Per municipality | Varies | Municipal websites | Storm sewer, road drainage |
  | Macomb County Emergency Management | County-wide | TBD | County website | Coordinates multi-jurisdiction response |
  | USCG Sector Detroit | Lake St. Clair / navigable waters | TBD | USCG website | Oil/hazmat on navigable waters |

- [ ] **Regulatory contacts** (who must be notified):

  | Agency | Scope | Phone | Source | Deadline | Notes |
  | --- | --- | --- | --- | --- | --- |
  | National Response Center (NRC) | Federal | 1-800-424-8802 | nrc.uscg.mil | Immediately | Oil sheen on water, CERCLA RQ exceeded |
  | Michigan EGLE — PEAS hotline | State | 1-800-292-4706 | michigan.gov/egle | Immediately | All spills to water in Michigan |
  | Michigan EGLE — District 11 | State (SE Michigan) | TBD | michigan.gov/egle | Follow-up | Written follow-up within 10 days |
  | Macomb County Public Works | County | TBD | County website | Within 24 hours | Drains and sewers |
  | Macomb County Health Department | County | TBD | County website | Within 24 hours | Public health impact |
  | EPA Region 5 | Federal | TBD | epa.gov | Per CERCLA | CERCLA reportable quantities |

- [ ] For each contact:
  - Record the phone number, after-hours phone, email, and office hours
  - Record the official source URL where the number is published
  - Record the date verified
  - Store any notes about when/how to reach them

- [ ] Seed contacts into the database via a seed script (`scripts/seed_contacts.py`)

#### 2.2 Research reporting rules

- [ ] Document reporting triggers and deadlines for each agency:

  | Agency | Trigger | Deadline | Legal Citation |
  | --- | --- | --- | --- |
  | NRC | Oil sheen on navigable water; CERCLA RQ exceeded | Immediately | 40 CFR 302.4; CWA Section 311 |
  | EGLE PEAS | Any release to surface water, groundwater, or land | Immediately | Michigan Part 5 Rules (MCL 324.3111a) |
  | EGLE District | Follow-up written report | Within 10 days | Michigan Part 5 Rules |
  | USCG | Oil/hazmat on navigable waters (Lake St. Clair, Clinton River below certain point) | Immediately | 33 CFR 153 |
  | County Public Works | Discharge to county drain or sewer | Within 24 hours | County ordinance (cite specific) |
  | County Health | Potential public health impact | Within 24 hours | County health code (cite specific) |
  | EPA Region 5 | CERCLA reportable quantity exceeded | Per CERCLA schedule | 40 CFR 302 |

- [ ] For each rule, cite the specific regulation or ordinance
- [ ] Identify CERCLA reportable quantities for common materials:
  - Diesel/fuel oil: 25 gal (as petroleum)
  - Gasoline: 25 gal
  - Antifreeze (ethylene glycol): varies
  - Sewage: no federal RQ; state rules apply
- [ ] Store citations in the `rules.legal_citation` column

#### 2.3 Build the rules table entries

- [ ] Seed rules into the database via `scripts/seed_rules.py`
- [ ] Example rules:

  | jurisdiction_type | water_body | material | size_threshold_gal | contact | required | deadline | priority |
  | --- | --- | --- | --- | --- | --- | --- | --- |
  | any | any | any | NULL | 911 | yes | immediately | 1 |
  | municipality | any | any | NULL | Municipal DPW (matched by jurisdiction_id) | yes | immediately | 10 |
  | any | any | any | NULL | Macomb County EM | yes | immediately | 20 |
  | shoreline | lake_st_clair | any | NULL | USCG Sector Detroit | yes | immediately | 15 |
  | any | any | any | NULL | EGLE PEAS hotline | yes | immediately | 50 |
  | any | any | any | NULL | NRC | yes | immediately | 51 |
  | any | any | oil_fuel | 25 | EPA Region 5 | yes | per CERCLA | 60 |
  | drain_district | any | any | NULL | County Public Works | yes | within 24 hours | 70 |
  | any | any | any | NULL | County Health Dept | yes | within 24 hours | 80 |
  | any | any | any | NULL | EGLE District 11 | yes | within 10 days | 90 |

- [ ] Ensure municipal-level contacts use `jurisdiction_id` to match the specific municipality's DPW
  - One contact row per municipality; one rule that matches `jurisdiction_type = municipality` and resolves to the correct contact via junction

### Phase 3 — Integrate (Weeks 6–7)

#### 3.1 Write the rules engine

- [ ] Implement `evaluate_rules(jurisdictions, incident)` in `src/services/rules_engine.py`
  - Input:
    - `jurisdictions`: list of `{ layer, jurisdiction_id, name }` from WS3
    - `incident`: `{ material, quantity_gallons, water_body }`
  - Logic:
    1. Query all rules from the `rules` table
    2. For each rule, check if it matches the incident:
       - `jurisdiction_type` matches any returned jurisdiction layer (or rule has a wildcard)
       - `water_body` is NULL or matches incident water body
       - `material` is NULL or matches incident material
       - `size_threshold_gal` is NULL or `incident.quantity_gallons >= threshold`
    3. For matched rules, look up the associated contact
    4. For municipality-scoped contacts, resolve to the specific contact matching the jurisdiction_id
    5. Deduplicate contacts (same contact may match via multiple rules — keep the highest-priority match)
  - Output:
    ```python
    {
        "response_contacts": [Contact, ...],     # role = "response", sorted by priority (ascending)
        "regulatory_contacts": [Contact, ...],   # role = "regulatory", sorted by priority (ascending)
    }
    ```
    Each contact includes: agency, phone, after_hours_phone, email, hours, deadline, source_url, last_verified, legal_citation

- [ ] Handle edge cases:
  - No jurisdictions returned (point outside county) → return only federal/state contacts (NRC, EGLE)
  - Unknown material → match all material-agnostic rules; flag that material-specific rules may apply
  - Unknown quantity → match all size-agnostic rules; flag that quantity thresholds were not evaluated
  - After-hours scenario → include after_hours_phone where available; flag contacts with limited hours

#### 3.2 Expose to WS5

- [ ] Register `evaluate_rules` as a service function callable from WS5's `/lookup` endpoint
  - WS5 calls: `contacts = await evaluate_rules(jurisdictions, incident)`
  - Returns response and regulatory contact lists
- [ ] Ensure the contact data in API responses includes all fields needed by WS6 results panels

#### 3.3 Integrate with WS2 material categories

- [ ] Verify that `material-categories.json` (authored by WS2) covers all materials referenced in rules
- [ ] Rules engine matches on the category enum (`oil_fuel`, `chemical_hazmat`, `sewage`, `unknown_other`), not the raw material detail string
- [ ] If WS2 adds new categories, rules must be updated to match

### Phase 4 — Pilot (Week 8)

#### 4.1 Set up contact verification

- [ ] Create a verification tracking system:
  - `last_verified` date on each contact row
  - Verification checklist: call the number, confirm it reaches the right agency, update the date
- [ ] Verify every contact before pilot use
  - Call each phone number and confirm it's correct
  - Check each email address (send a test if possible)
  - Update `last_verified` date and `source_url` if the source page changed
- [ ] Document the quarterly re-verification schedule
  - Assign an owner for re-checks
  - Set calendar reminders

#### 4.2 Write scenario tests

- [ ] Create test scenarios aligned with WS6 end-to-end tests:

  **Scenario 1: Oil sheen on Lake St. Clair**
  - Jurisdictions: Harrison Township, USCG zone, EPA region
  - Expected response: 911, Harrison Twp DPW, County EM, USCG Sector Detroit
  - Expected regulatory: NRC, EGLE PEAS, County Public Works, County Health, EPA Region 5 (if RQ exceeded)

  **Scenario 2: Chemical release in the Clinton River**
  - Jurisdictions: Mount Clemens, Clinton River subwatershed, drain district
  - Expected response: 911, Mount Clemens DPW, County EM
  - Expected regulatory: NRC, EGLE PEAS, EGLE District 11, County Public Works, County Health

  **Scenario 3: Discharge from a storm drain**
  - Jurisdictions: Sterling Heights, drain district
  - Expected response: 911, Sterling Heights DPW, County EM
  - Expected regulatory: EGLE PEAS, County Public Works, County Health

  **Scenario 4: Sewage overflow into a county drain**
  - Jurisdictions: Clinton Township, drain district
  - Expected response: 911, Clinton Twp DPW, County EM
  - Expected regulatory: EGLE PEAS, County Public Works, County Health

  **Scenario 5: Unknown material, unknown quantity**
  - Expected: all size-agnostic and material-agnostic rules fire; flags for "material-specific rules may apply" and "quantity thresholds not evaluated"

- [ ] Implement automated tests in `tests/test_rules_engine.py`
  - For each scenario: mock jurisdiction input, run `evaluate_rules`, compare output to expected contact list
  - Verify sort order (priority), deadlines, and required/optional flags
  - All must pass before pilot

#### 4.3 Pilot readiness

- [ ] All contacts verified (every row has a `last_verified` date within the last 30 days)
- [ ] All scenario tests pass
- [ ] Rules engine returns correct results for all WS6 end-to-end tests
- [ ] Fix issues logged during the pilot demo

## Key Decisions & Constraints

| Decision | Notes |
| --- | --- |
| Contact source requirement | Every contact must have a `source_url` pointing to an official page |
| Verification schedule | Quarterly re-verification of all contacts |
| Rule matching | All non-null conditions must match (AND logic); NULL = wildcard |
| Priority system | Lower number = higher urgency; Response before Regulatory |
| Material matching | Match on category enum, not raw material name |
| Municipal contacts | One contact per municipality; resolved via `jurisdiction_id` |
| 911 always first | Priority 1 rule for any spill (can be overridden per scenario if needed) |

## Risks

| Risk | Mitigation |
| --- | --- |
| Stale contacts (wrong number during a real spill) | Mandatory source URL; quarterly verification; show "last verified" in UI |
| Missing contacts for new jurisdictions | Flag unmatched jurisdiction IDs; fall back to county-level contacts |
| Regulatory rules change | Cite specific legal citations; monitor EGLE/EPA updates |
| CERCLA RQ lookup complexity | Start with common materials; expand as needed; flag "unknown RQ" |
| Municipal DPW numbers hard to find | Check municipal websites; call main number to confirm; document backup |

## Open Questions

- [ ] Should the app recommend calling 911 for every spill, or only for hazardous materials / large spills?
- [ ] Are there mutual aid agreements between municipalities that affect who responds?
- [ ] Should contacts include personal names/titles, or just agency and phone?
- [ ] How should after-hours contacts be handled in the UI (show both numbers, or switch based on time of day)?
- [ ] Are there additional county ordinances beyond state/federal rules that trigger specific contacts?

## File Structure (Proposed)

```
src/
  models/
    contact.py                 # SQLAlchemy model for contacts table
    rule.py                    # SQLAlchemy model for rules table
  services/
    rules_engine.py            # evaluate_rules(jurisdictions, incident) → contact lists
  shared/
    material-categories.json   # Shared with WS2 (symlink or import)

scripts/
  seed_contacts.py             # Insert all contacts into the database
  seed_rules.py                # Insert all rules into the database
  verify_contacts.py           # Verification checklist runner (print report)
  research/
    contacts_response.md       # Research notes: response agency contacts
    contacts_regulatory.md     # Research notes: regulatory agency contacts
    reporting_rules.md         # Research notes: triggers, deadlines, citations

tests/
  test_rules_engine.py         # Scenario tests (5+ scenarios)
  test_contact_data.py         # Data integrity tests (no missing source URLs, etc.)
```
