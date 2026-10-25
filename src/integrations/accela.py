"""
Accela integration adapter.

v1: logs the mapped payload but does not call the Accela API.
When ACCELA_ENABLED=true: authenticates via OAuth2 client credentials
and creates a record via the Accela Construct API.

Configuration via environment variables:
    ACCELA_ENABLED=false (default off)
    ACCELA_API_URL      — base URL (e.g., "https://apis.accela.com")
    ACCELA_APP_ID       — OAuth2 client ID
    ACCELA_APP_SECRET   — OAuth2 client secret
    ACCELA_AGENCY       — Accela agency name
    ACCELA_ENVIRONMENT  — "PROD" or "TEST"
    ACCELA_RECORD_TYPE  — e.g., "ServiceRequest/Spill/Incident/NA"
"""

import logging
import os

import httpx

from src.schemas.event import IncidentEvent

logger = logging.getLogger(__name__)

ACCELA_ENABLED = os.environ.get("ACCELA_ENABLED", "false").lower() == "true"
ACCELA_API_URL = os.environ.get("ACCELA_API_URL", "")
ACCELA_APP_ID = os.environ.get("ACCELA_APP_ID", "")
ACCELA_APP_SECRET = os.environ.get("ACCELA_APP_SECRET", "")
ACCELA_AGENCY = os.environ.get("ACCELA_AGENCY", "")
ACCELA_ENVIRONMENT = os.environ.get("ACCELA_ENVIRONMENT", "TEST")
ACCELA_RECORD_TYPE = os.environ.get("ACCELA_RECORD_TYPE", "ServiceRequest/Spill/Incident/NA")

_TOKEN_CACHE: dict[str, str] = {}


class AccelaError(Exception):
    """Raised when an Accela API call fails."""


class AccelaAdapter:
    """Map incident events to Accela records."""

    def _map_record(self, event: IncidentEvent) -> dict:
        """Map an IncidentEvent to the Accela record creation payload."""
        return {
            "type": {"value": ACCELA_RECORD_TYPE},
            "name": f"Spill Incident {event.incident_id}",
            "description": (
                f"{event.material.value} spill at "
                f"({event.location.lat}, {event.location.lon})"
            ),
            "status": {"value": event.status.value},
            "customFields": [
                {"id": "material", "value": event.material.value},
                {"id": "materialDetail", "value": event.material_detail},
                {"id": "quantityGallons", "value": str(event.quantity_gallons or "")},
                {"id": "waterBody", "value": event.water_body.value},
                {"id": "jurisdictions", "value": ", ".join(j.name for j in event.jurisdictions)},
            ],
        }

    async def _get_token(self, client: httpx.AsyncClient) -> str:
        """Obtain an OAuth2 access token via client credentials grant."""
        if "access_token" in _TOKEN_CACHE:
            return _TOKEN_CACHE["access_token"]

        resp = await client.post(
            f"{ACCELA_API_URL}/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": ACCELA_APP_ID,
                "client_secret": ACCELA_APP_SECRET,
                "agency_name": ACCELA_AGENCY,
                "environment": ACCELA_ENVIRONMENT,
            },
        )
        if resp.status_code != 200:
            raise AccelaError(f"Token request failed: {resp.status_code} {resp.text}")

        token_data = resp.json()
        _TOKEN_CACHE["access_token"] = token_data["access_token"]
        return _TOKEN_CACHE["access_token"]

    async def create_record(self, event: IncidentEvent) -> dict:
        """Create an Accela record from an incident event.

        When ACCELA_ENABLED=false (default), logs the mapped payload and returns it.
        When enabled, authenticates and POSTs to the Accela Records API.
        """
        mapped = self._map_record(event)

        if not ACCELA_ENABLED:
            logger.info("Accela disabled: would create record: %s", mapped["name"])
            return mapped

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                token = await self._get_token(client)
                resp = await client.post(
                    f"{ACCELA_API_URL}/v4/records",
                    json=mapped,
                    headers={
                        "Authorization": token,
                        "x-accela-appid": ACCELA_APP_ID,
                        "x-accela-agency": ACCELA_AGENCY,
                        "Content-Type": "application/json",
                    },
                )
                if resp.status_code not in (200, 201):
                    logger.error(
                        "Accela record creation failed: %s %s", resp.status_code, resp.text
                    )
                    raise AccelaError(f"Record creation failed: {resp.status_code}")

                result = resp.json()
                record_id = result.get("result", [{}])[0].get("id", "unknown")
                logger.info("Accela record created: %s", record_id)
                return result

            except httpx.HTTPError as exc:
                logger.error("Accela HTTP error: %s", exc)
                raise AccelaError(f"HTTP error: {exc}") from exc
