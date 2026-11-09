// Auto-generated from OpenAPI schema — do not edit manually.
// Generated from openapi.json (29 schemas)

export interface Contact {
  agency: string;
  role: ContactRole;
  jurisdiction_id: string;
  jurisdiction_scope?: string | null;
  phone: string;
  after_hours_phone?: string | null;
  email?: string | null;
  hours?: string | null;
  reporting_deadline?: string | null;
  source_url: string;
  last_verified: string;
  notes?: string | null;
}

export interface ContactBrief {
  id: number;
  agency: string;
}

export interface ContactCreate {
  agency: string;
  role: ContactRole;
  jurisdiction_id: string;
  jurisdiction_scope?: string | null;
  phone: string;
  after_hours_phone?: string | null;
  email?: string | null;
  hours?: string | null;
  reporting_deadline?: string | null;
  source_url: string;
  last_verified: string;
  notes?: string | null;
}

export interface ContactResponse {
  id: number;
  agency: string;
  role: string;
  jurisdiction_id: string;
  jurisdiction_scope?: string | null;
  phone: string;
  after_hours_phone?: string | null;
  email?: string | null;
  hours?: string | null;
  reporting_deadline?: string | null;
  source_url: string;
  last_verified: string;
  notes?: string | null;
}

export type ContactRole = "response" | "regulatory";

export interface Incident {
  location: Location;
  water_body: WaterBodyType;
  material: MaterialType;
  material_detail?: string | null;
  quantity?: number | null;
  quantity_unit?: QuantityUnit;
  quantity_gallons?: number | null;
  time_observed: string;
  reporter_name: string;
  reporter_phone: string;
  notes?: string | null;
  buffer_radius_m?: number | null;
  id: string;
  created_at: string;
  updated_at: string;
  status: IncidentStatus;
}

export interface IncidentCreate {
  location: Location;
  water_body: WaterBodyType;
  material: MaterialType;
  material_detail?: string | null;
  quantity?: number | null;
  quantity_unit?: QuantityUnit;
  quantity_gallons?: number | null;
  time_observed: string;
  reporter_name: string;
  reporter_phone: string;
  notes?: string | null;
  buffer_radius_m?: number | null;
}

export type IncidentStatus = "open" | "closed" | "under_review";

export interface IncidentSummary {
  id: string;
  water_body: string;
  material: string;
  quantity_gallons?: number | null;
  status: string;
  reporter_name: string;
  time_observed: string;
  created_at: string;
}

export interface Jurisdiction {
  layer: string;
  jurisdiction_id: string;
  name: string;
}

export interface Location {
  lat: number;
  lon: number;
  address?: string | null;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LookupRequest {
  location: Location;
  material?: MaterialType | null;
  quantity_gallons?: number | null;
  buffer_radius_m?: number | null;
}

export interface LookupResult {
  jurisdictions: Jurisdiction[];
  downstream_path: string[];
  response_contacts: Contact[];
  regulatory_contacts: Contact[];
}

export type MaterialType = "oil_fuel" | "chemical_hazmat" | "sewage" | "unknown_other";

export interface ParseRequest {
  text: string;
}

export interface ParseResponse {
  water_body?: string | null;
  material?: string | null;
  material_detail?: string | null;
  quantity?: number | null;
  quantity_unit?: string | null;
  quantity_gallons?: number | null;
  location?: Record<string, unknown> | null;
  address_hint?: string | null;
  time_observed?: string | null;
}

export type QuantityUnit = "gal" | "bbl" | "L" | "lb";

export interface RegisterRequest {
  username: string;
  password: string;
  role?: UserRole;
}

export interface RuleBrief {
  id: number;
}

export interface RuleCreate {
  jurisdiction_type: string;
  water_body?: string | null;
  material?: string | null;
  size_threshold?: number | null;
  contact_id: number;
  required?: boolean;
  deadline?: string | null;
  priority?: number;
  legal_citation?: string | null;
}

export interface RuleResponse {
  id: number;
  jurisdiction_type: string;
  water_body?: string | null;
  material?: string | null;
  size_threshold?: number | null;
  contact_id: number;
  required: boolean;
  deadline?: string | null;
  priority: number;
  legal_citation?: string | null;
}

export interface Token {
  access_token: string;
  token_type?: string;
}

export type UserRole = "responder" | "viewer" | "admin";

export type WaterBodyType = "lake_st_clair" | "clinton_river" | "tributary" | "county_drain" | "storm_sewer" | "unknown";

export interface WebhookCreate {
  url: string;
}

export interface WebhookResponse {
  id: number;
  url: string;
  active: boolean;
  created_at: string;
}
