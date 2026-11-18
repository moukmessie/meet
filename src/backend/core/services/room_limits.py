"""Read the limits of a room from an external service.

Used by multi-organization deployments: before delivering a LiveKit access
token for a room owned by an organization, Meet asks a platform that manages
organizations, plans and quotas for the limits to apply. The feature is
disabled when ROOM_LIMITS_URL is empty (default).

Failing open: only an explicit HTTP 200 answer can change the behavior. Any
other answer, an error, a timeout or an unreadable body delivers the token
without limits and logs a warning. Rooms without organization never trigger a
call.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from django.conf import settings

import requests
from rest_framework.exceptions import PermissionDenied

logger = logging.getLogger(__name__)

ENTRY_REFUSED_MESSAGES = {
    "monthly_minutes_exhausted": (
        "Le quota mensuel de minutes de l'organisation est épuisé : "
        "l'entrée dans cette salle est refusée."
    ),
}
DEFAULT_ENTRY_REFUSED_MESSAGE = "L'entrée dans cette salle est refusée."


class RoomEntryRefused(PermissionDenied):
    """The organization of the room is not allowed to host more participants."""

    default_detail = DEFAULT_ENTRY_REFUSED_MESSAGE
    default_code = "entry_refused"

    def __init__(self, reason, quota=None):
        super().__init__(code=reason)
        # Set after init: DRF would turn the numbers of the quota into strings.
        self.detail = {
            "detail": ENTRY_REFUSED_MESSAGES.get(reason, DEFAULT_ENTRY_REFUSED_MESSAGE),
            "code": reason,
            "quota": quota,
        }


@dataclass(frozen=True)
class RoomLimits:
    """Limits to apply to a room."""

    max_participants: Optional[int] = None


def get_room_limits(organization_id) -> Optional[RoomLimits]:
    """Return the limits of a room owned by an organization.

    Returns None when nothing applies (feature disabled, no organization,
    unavailable service). Raises RoomEntryRefused when the service refuses the
    entry with an explicit 200 answer.
    """
    url = settings.ROOM_LIMITS_URL
    if not url or organization_id is None:
        return None

    token = settings.ROOM_LIMITS_TOKEN or settings.ROOM_CREATION_CHECK_TOKEN
    try:
        response = requests.post(
            url,
            json={"organization_id": str(organization_id)},
            headers={"Authorization": f"Bearer {token}"},
            timeout=settings.ROOM_LIMITS_TIMEOUT,
        )
        if response.status_code != 200:
            logger.warning("Room limits unavailable: HTTP %s", response.status_code)
            return None
        result = response.json()
    except (requests.RequestException, ValueError) as error:
        logger.warning("Room limits unavailable: %s", type(error).__name__)
        return None

    if not isinstance(result, dict):
        logger.warning("Room limits unavailable: unexpected body")
        return None

    reason = result.get("entry_refused_reason")
    if reason:
        quota = result.get("quota")
        raise RoomEntryRefused(str(reason), quota if isinstance(quota, dict) else None)

    max_participants = result.get("max_participants")
    if (
        isinstance(max_participants, int)
        and not isinstance(max_participants, bool)
        and max_participants > 0
    ):
        return RoomLimits(max_participants=max_participants)
    return RoomLimits()
