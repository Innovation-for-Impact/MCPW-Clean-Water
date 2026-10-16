# WS4 — Contacts Directory & Rules Engine: Implementation Plan

## Goal

Given the jurisdictions, drain context and spill details, apply the MCPWO spill-response handbook (2018 draft protocol) and return who to contact and what to do — split into Response and Regulatory — with deadlines. The handbook rules work for every drain; drain-specific response plans (Red Run today) add field actions on top.

## Done When

Every test scenario returns the correct contact list, and every contact has a source link and a verified date.

## Dependencies

| Direction | Workstream | What |
| --- | --- | --- |
| Needs from | WS3 | Jurisdiction IDs, plus drain context: `drain_id`, drain tier, conveyance owner/type, first large drain downstream, next intercept point, upstream counties |
| Needs from | WS2 | Material category mapping (`material-categories.json`), `hazard_class`, `immediate_threat`, `reported_at` |
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
      priority INTEGER NOT NULL DEFAULT 100,    -- lower = more urgent (for sort order)
      -- Handbook / drain-context match columns (NULL = any)
      drain_tier VARCHAR(5),                    -- '1','2','3','4' (WS3 tiers)
      drain_id VARCHAR(100),                    -- drain-specific overlay rules, e.g. drain_red_run
      conveyance_owner VARCHAR(30),             -- county_drain, county_storm, county_sewer, roads_dept, municipal_ms4, private
      conveyance_type VARCHAR(20),              -- open, enclosed, sanitary, combined
      hazard_class VARCHAR(30),                 -- non_hazardous, hazardous, unknown
      after_hours BOOLEAN,                      -- TRUE = only after hours; FALSE = only business hours
      immediate_threat BOOLEAN,                 -- TRUE = only when a threat to public health/safety
      -- What the rule produces
      action_type VARCHAR(20) NOT NULL DEFAULT 'notify',  -- notify, field_action, refer
      action TEXT,                              -- e.g. 'Immediate site visit; run checklist and event log'
      handbook_ref VARCHAR(50)                  -- e.g. 'Protocol §6.3'
  );
  ```

- [ ] Design the rule matching logic:
  - A rule matches if ALL non-null conditions are satisfied:
    - `jurisdiction_type` matches one of the returned jurisdiction layers
    - `water_body` is NULL (any) or matches the incident water body
    - `material` is NULL (any) or matches the incident material category
    - `size_threshold_gal` is NULL (any size) or incident quantity >= threshold
    - `drain_tier`, `drain_id`, `conveyance_owner`, `conveyance_type` are NULL or match the WS3 drain context
    - `hazard_class` is NULL or matches the incident; treat `unknown` as `hazardous` for containment rules (handbook: booms only for non-hazardous material)
    - `after_hours` is NULL or matches whether the report time is outside business hours
    - `immediate_threat` is NULL or matches the incident flag
  - Multiple rules can match → multiple contacts returned
  - `priority` determines sort order within Response and Regulatory groups
  - Every rule keeps a contact (`contact_id` stays NOT NULL): for `field_action` and `refer` rules the contact is the party who acts or receives the referral

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
  | any (immediate_threat = TRUE) | any | any | NULL | 911 | yes | immediately | 1 |
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

#### 2.4 Encode the handbook rules

The base rule set comes from the 2018 MCPWO Draft Stormwater Spill Response Protocol and applies to a spill on any drain. Drain response plans (Red Run today) are overlay rules keyed on `drain_id`. Drain tiers come from WS3 (see WS3-Plan §2.3).

| # | Condition | Action / who | Match columns | Handbook ref |
| --- | --- | --- | --- | --- |
| R1 | Immediate threat to public health or safety | Call 911 first | `immediate_threat = TRUE` | §2, checklist |
| R2 | Any report | Route to MCPWO Environmental Engineer; backup Construction Engineer, then Table 1 | — | §6.1 |
| R3 | Minor: failed septic, leaking dumpster, storage pile, minor soil erosion | Next-business-day follow-up or refer to owning jurisdiction | `material` / incident type | §6.3 |
| R4 | Reaches a county drain, county storm water system, county sewer or facility | Immediate site visit; run checklist and event log | `conveyance_owner IN (county_*)` | §6.3 |
| R5 | Does not reach a county system (Tier 4) | Refer to owner (roads dept., municipality, private); county not lead | `drain_tier = '4'` | §3, §6.2 |
| R6 | From or into a county sanitary or combined sewer | Notify Operations & Flow Manager and Chapaton staff | `conveyance_type IN (sanitary, combined)` | §6.2 |
| R7 | Spill confirmed | Phone + email EGLE, County Health, affected municipality | municipality jurisdiction | Checklist |
| R8 | After hours | PEAS 1-800-292-4706 | `after_hours = TRUE` | Checklist |
| R9 | Any external notification made | Send internal email notification | — | §6.4 |
| R10 | Non-hazardous material | Boom/contain in county right-of-way; earthen dam if spill is the only flow | `hazard_class = non_hazardous` | Containment |
| R11 | Hazardous or unknown material | MCPWO does not boom; local fire / County HAZMAT / contractor (Table 2) | `hazard_class IN (hazardous, unknown)` | Containment, §6.2 |
| R12 | Oil to navigable water or a tributary | NRC / USCG; track costs for OPA 90 claim | `material = oil_fuel` + downstream path | Cost recovery |
| R13 | Sampling performed | Send results to EGLE, County Health, municipality | — | After incident |
| R14 | Close-out | Assign IDEP complaint number; log location in GIS | — | Follow-up |
| O1 | Tier 1 overlay (Red Run) | Next downstream crossing and boom site; access contacts (OCWRC, SMDA, Huron Academy); notify OCWRC if source is upstream in Oakland | `drain_id = drain_red_run` | HRC plan set |

- [ ] Seed R1–R14 and O1 via `scripts/seed_handbook_rules.py`, with `handbook_ref` on every row
- [ ] Re-verify every handbook contact before seeding: the 2018 draft still says MDEQ (EGLE since 2019), Table 3 lists only 8 communities (no Warren or Sterling Heights), and several emails have typos
- [ ] Confirm with MCPWO that the 2018 draft is still the working procedure, and how `hazard_class` should be decided for R10/R11
- [ ] Sewer overflows and NPDES-permitted facilities are excluded by the handbook: when WS3 sets `flags.excluded_procedure`, skip R1–R14 and flag for the separate procedure

### Phase 3 — Integrate (Weeks 6–7)

#### 3.1 Write the rules engine

- [ ] Implement `evaluate_rules(jurisdictions, incident)` in `src/services/rules_engine.py`
  - Input:
    - `jurisdictions`: list of `{ layer, jurisdiction_id, name }` from WS3
    - `incident`: `{ material, quantity_gallons, water_body, hazard_class, immediate_threat, reported_at }`
    - `drain_context`: WS3 `drain`, `first_major_drain_downstream`, `next_intercept_point`, `upstream_counties`, `flags.excluded_procedure`
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
        "actions": [Action, ...],                # field_action / refer rules: action text, who, handbook_ref
    }
    ```
    Each contact includes: agency, phone, after_hours_phone, email, hours, deadline, source_url, last_verified, legal_citation

- [ ] Handle edge cases:
  - No jurisdictions returned (point outside county) → return only federal/state contacts (NRC, EGLE)
  - Unknown material → match all material-agnostic rules; flag that material-specific rules may apply
  - Unknown quantity → match all size-agnostic rules; flag that quantity thresholds were not evaluated
  - After-hours scenario → include after_hours_phone where available; flag contacts with limited hours
  - Tier 4 conveyance → return the R5 referral, plus rules that fire for the first county drain downstream (if any)
  - No drain within snap distance → run handbook rules without drain-context columns; flag that drain context is missing

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

  **Scenario 6: Diesel into enclosed Bear Creek (Tier 2), 24257 Mound Rd, Warren** (Oct 2018 incident)
  - Drain context: Bear Creek, tier 2, enclosed; first large drain downstream = Red Run
  - Expected: R2, R4 (site visit), R7 (EGLE, County Health, Warren), containment per R10/R11 depending on `hazard_class`, R12; O1 intercept at Red Run crossing 7

  **Scenario 7: Suspected oil, Vermander Drain via private ditch (Tier 3), 35350 Kelly Rd, Clinton Twp** (Dec 2025 incident)
  - Expected: R2, R4, R7 (Clinton Twp), R12; source tracing upstream to the private ditch

  **Scenario 8: Spill on Red Run at Ryan Rd (Tier 1)**
  - Expected: handbook rules + O1 (crossing 3 boom site; upstream site = Dequindre, access via OCWRC)

  **Scenario 9: Roads-dept storm sewer not tied to a county drain (Tier 4)**
  - Expected: R1 if applicable, R5 referral to Macomb County Dept. of Roads; no MCPWO site visit

  **Scenario 10: After-hours non-hazardous spill to a county drain**
  - Expected: R4, R8 (PEAS), R10 (booming)

  **Scenario 11: Minor incident — leaking dumpster**
  - Expected: R3 next-business-day follow-up; no immediate site visit

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
| 911 | Priority 1 when `immediate_threat` is true (handbook §2); otherwise the MCPWO hotline is the entry point |
| Rules source | 2018 MCPWO draft protocol is the base rule set for every drain; drain response plans are overlay rules keyed on `drain_id` |
| Field actions | Rules can return actions (`field_action`, `refer`), not only contacts |

## Risks

| Risk | Mitigation |
| --- | --- |
| Stale contacts (wrong number during a real spill) | Mandatory source URL; quarterly verification; show "last verified" in UI |
| Missing contacts for new jurisdictions | Flag unmatched jurisdiction IDs; fall back to county-level contacts |
| Regulatory rules change | Cite specific legal citations; monitor EGLE/EPA updates |
| CERCLA RQ lookup complexity | Start with common materials; expand as needed; flag "unknown RQ" |
| Municipal DPW numbers hard to find | Check municipal websites; call main number to confirm; document backup |

## Open Questions

- [x] Should the app recommend calling 911 for every spill, or only for hazardous materials / large spills? → Handbook: only when the spill is an immediate threat to public health and safety (R1)
- [ ] Is the 2018 draft protocol still MCPWO's working procedure, or is there a newer version?
- [ ] How should `hazard_class` be defined for the booming rule (R10/R11) — by material category or case by case?
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
  seed_handbook_rules.py       # R1–R14 + drain overlays (O1) from the 2018 protocol
  verify_contacts.py           # Verification checklist runner (print report)
  research/
    contacts_response.md       # Research notes: response agency contacts
    contacts_regulatory.md     # Research notes: regulatory agency contacts
    reporting_rules.md         # Research notes: triggers, deadlines, citations
    handbook_rules.md          # Protocol section → rule mapping

tests/
  test_rules_engine.py         # Scenario tests (5+ scenarios)
  test_contact_data.py         # Data integrity tests (no missing source URLs, etc.)
```
