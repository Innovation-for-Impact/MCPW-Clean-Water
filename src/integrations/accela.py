"""
Accela integration adapter.

v1: logs the mapped payload but does not call the Accela API.
Post-v1: calls Accela Construct API to create a service request, permit, or inspection record.

Configuration via environment variables:
    ACCELA_ENABLED=false (default off in v1)
    ACCELA_API_URL
    ACCELA_APP_ID
    ACCELA_APP_SECRET
    ACCELA_RECORD_TYPE (e.g., "ServiceRequest/Spill/Incident/NA")
"""

import logging
import os

from src.schemas.event import IncidentEvent

logger = logging.getLogger(__name__)

ACCELA_ENABLED = os.environ.get("ACCELA_ENABLED", "false").lower() == "true"
ACCELA_API_URL = os.environ.get("ACCELA_API_URL", "")
ACCELA_APP_ID = os.environ.get("ACCELA_APP_ID", "")
ACCELA_APP_SECRET = os.environ.get("ACCELA_APP_SECRET", "")
ACCELA_RECORD_TYPE = os.environ.get("ACCELA_RECORD_TYPE", "ServiceRequest/Spill/Incident/NA")


class AccelaAdapter:
    """Map incident events to Accela records."""

    async def create_record(self, event: IncidentEvent) -> dict:
        """Map an incident event to an Accela record.

        v1: logs the mapped payload; does not call Accela API.
        Post-v1: calls Accela Construct API to create a
        service request, permit, or inspection record.
        """
        mapped = {
            "type": ACCELA_RECORD_TYPE,
            "name": f"Spill Incident {event.incident_id}",
            "description": (
                f"{event.material.value} spill at "
                f"({event.location.lat}, {event.location.lon})"
            ),
            "status": event.status.value,
            "customFields": {
                "material": event.material.value,
                "materialDetail": event.material_detail,
                "quantityGallons": event.quantity_gallons,
                "waterBody": event.water_body.value,
                "jurisdictions": [j.name for j in event.jurisdictions],
            },
        }

        if ACCELA_ENABLED:
            logger.info("Accela integration enabled but API call not implemented in v1")
            # Post-v1: httpx.post(ACCELA_API_URL, json=mapped, headers=...)
        else:
            logger.info("Accela stub: would send record: %s", mapped)

        return mapped
